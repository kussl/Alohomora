#!/usr/bin/env python3
import argparse, json, sys, time
import boto3
from botocore.exceptions import ClientError

PROFILE = "user_profile"

def sess(region=None):
    return boto3.Session(profile_name=PROFILE, region_name=region)

def outprinter(outfile):
    def write(msg=""):
        if outfile:
            with open(outfile, "a") as f:
                f.write(msg + ("\n" if not msg.endswith("\n") else ""))
        print(msg)
    return write

# ----------------- Route53 helpers -----------------
def _r53(region):
    # Route53 is global; boto ignores region, but we keep the signature consistent
    return sess(region).client("route53")

def hosted_zones(r53):
    res = r53.list_hosted_zones()
    return res["HostedZones"]

def zone_id_by_name(r53, zone_name):
    if not zone_name.endswith("."):
        zone_name = zone_name + "."
    for z in hosted_zones(r53):
        if z["Name"] == zone_name:
            return z["Id"].split("/")[-1]
    raise ValueError(f"Zone not found: {zone_name}")

def list_records(r53, zone_id):
    recs = []
    paginator = r53.get_paginator("list_resource_record_sets")
    for page in paginator.paginate(HostedZoneId=zone_id):
        recs.extend(page["ResourceRecordSets"])
    return recs

def upsert_a_record(r53, zone_id, name, ip):
    if not name.endswith("."):
        name = name + "."
    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Comment": "Upsert A record",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": name,
                        "Type": "A",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": ip}],
                    },
                }
            ],
        },
    )

def delete_record(r53, zone_id, name, rtype="A"):
    if not name.endswith("."):
        name = name + "."
    # find existing
    rec = None
    for r in list_records(r53, zone_id):
        if r["Name"] == name and r["Type"] == rtype:
            rec = r
            break
    if not rec:
        raise ValueError(f"Record not found: {name} [{rtype}]")
    # delete with full previous set
    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Comment": "Delete record",
            "Changes": [{"Action": "DELETE", "ResourceRecordSet": rec}],
        },
    )

# ----------------- EC2 helpers -----------------
def all_regions():
    # Use us-east-1 for the global DescribeRegions call
    ec2 = sess("us-east-1").client("ec2")
    return [r["RegionName"] for r in ec2.describe_regions(AllRegions=False)["Regions"]]

def j(fmt, data):
    return json.dumps(data, indent=2, default=str)

# ----------------- EC2 listing / power -----------------
def cmd_list(args, write):
    for region in all_regions():
        ec2 = sess(region).client("ec2")
        res = ec2.describe_instances()
        rows = []
        for r in res.get("Reservations", []):
            for inst in r.get("Instances", []):
                iid = inst["InstanceId"]
                itype = inst.get("InstanceType")
                state = inst.get("State", {}).get("Name")
                pub = inst.get("PublicIpAddress")
                name = None
                for tag in inst.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break
                rows.append((region, iid, itype, state, pub, name))
        if rows:
            write(f"== {region} ==")
            for row in rows:
                write("  " + " | ".join([str(x) if x is not None else "-" for x in row]))

def cmd_list_region(args, write):
    region = args.region
    ec2 = sess(region).client("ec2")
    res = ec2.describe_instances()
    for r in res.get("Reservations", []):
        for inst in r.get("Instances", []):
            iid = inst["InstanceId"]
            itype = inst.get("InstanceType")
            state = inst.get("State", {}).get("Name")
            pub = inst.get("PublicIpAddress")
            name = None
            for tag in inst.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break
            write(" | ".join([iid, itype or "-", state or "-", pub or "-", name or "-"]))

def cmd_start_region(args, write):
    region = args.region
    ec2 = sess(region).client("ec2")
    res = ec2.describe_instances()
    for r in res.get("Reservations", []):
        for inst in r.get("Instances", []):
            if inst.get("State", {}).get("Name") == "stopped":
                ec2.start_instances(InstanceIds=[inst["InstanceId"]])
                write(f"Starting {inst['InstanceId']}")

def cmd_stop_region(args, write):
    region = args.region
    ec2 = sess(region).client("ec2")
    res = ec2.describe_instances()
    for r in res.get("Reservations", []):
        for inst in r.get("Instances", []):
            if inst.get("State", {}).get("Name") == "running":
                ec2.stop_instances(InstanceIds=[inst["InstanceId"]])
                write(f"Stopping {inst['InstanceId']}")

def cmd_start(args, write):
    region, iid = args.region, args.instance_id
    ec2 = sess(region).client("ec2")
    ec2.start_instances(InstanceIds=[iid])
    write(f"Starting {iid}")

def cmd_stop(args, write):
    region, iid = args.region, args.instance_id
    ec2 = sess(region).client("ec2")
    ec2.stop_instances(InstanceIds=[iid])
    write(f"Stopping {iid}")

# ----------------- Route53 commands -----------------
def cmd_assign_subdomain(args, write):
    region = args.region
    r53 = _r53(region)

    # Pick a running instance in region (simplistic)
    ec2 = sess(region).client("ec2")
    res = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    )
    inst = None
    for r in res.get("Reservations", []):
        for i in r.get("Instances", []):
            inst = i
            break
        if inst:
            break
    if not inst:
        write("No running instances found.")
        return

    ip = inst.get("PublicIpAddress")
    if not ip:
        write("Selected instance has no public IP.")
        return

    zone_id = args.zone_id if hasattr(args, "zone_id") else None
    if not zone_id:
        write("You must provide --zone-id for assign-subdomain")
        return

    name = args.record_name if hasattr(args, "record_name") else None
    if not name:
        write("You must provide --record-name for assign-subdomain")
        return

    upsert_a_record(r53, zone_id, name, ip)
    write(f"Assigned {name} -> {ip}")

def cmd_list_subdomains(args, write):
    r53 = _r53(None)
    recs = list_records(r53, args.zone_id)
    for r in recs:
        tgt = ""
        if "ResourceRecords" in r:
            tgt = ", ".join([x["Value"] for x in r["ResourceRecords"]])
        elif "AliasTarget" in r:
            tgt = r["AliasTarget"]["DNSName"]
        write(f"{r['Name']} [{r['Type']}]  {tgt}")

def cmd_delete_subdomain(args, write):
    r53 = _r53(None)
    delete_record(r53, args.zone_id, args.record_name, rtype=args.type)
    write(f"Deleted {args.record_name} [{args.type}]")

# ----------------- Clone instance (AMI snapshot + launch) -----------------
def _waiter(ec2, name, **kw):
    w = ec2.get_waiter(name)
    w.wait(**kw)

def cmd_clone(args, write):
    region, iid = args.region, args.instance_id
    ec2 = sess(region).client("ec2")

    inst = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
    itype = inst["InstanceType"]
    subnet = inst["SubnetId"]
    sgids = [sg["GroupId"] for sg in inst.get("SecurityGroups", [])]
    keyname = inst.get("KeyName")

    write(f"Creating AMI from {iid} ...")
    ami = ec2.create_image(InstanceId=iid, Name=f"clone-{iid}-{int(time.time())}", NoReboot=True)
    ami_id = ami["ImageId"]
    write(f"AMI: {ami_id}  waiting to be available...")
    _waiter(ec2, "image_available", ImageIds=[ami_id])

    write("Launching new instance ...")
    run = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=itype,
        MinCount=1, MaxCount=1,
        SubnetId=subnet,
        SecurityGroupIds=sgids,
        KeyName=keyname,
    )
    new_iid = run["Instances"][0]["InstanceId"]
    write(f"New instance: {new_iid}")
    _waiter(ec2, "instance_running", InstanceIds=[new_iid])

    inst2 = ec2.describe_instances(InstanceIds=[new_iid])["Reservations"][0]["Instances"][0]
    write(f"Public IP: {inst2.get('PublicIpAddress') or '-'}")

# ----------------- Security group port helpers -----------------
def _instance_sg_ids(region, iid):
    ec2 = sess(region).client("ec2")
    inst = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
    return [sg["GroupId"] for sg in inst.get("SecurityGroups", [])]

def cmd_open_port(args, write):
    region, iid, port = args.region, args.instance_id, args.port
    proto, cidr = args.protocol, args.cidr
    ec2 = sess(region).client("ec2")
    for sg in _instance_sg_ids(region, iid):
        try:
            ec2.authorize_security_group_ingress(
                GroupId=sg,
                IpPermissions=[{"IpProtocol":proto,"FromPort":port,"ToPort":port,"IpRanges":[{"CidrIp":cidr}]}]
            )
            write(f"SG {sg}: opened {proto}/{port} from {cidr}")
        except ClientError as e:
            # Might already exist
            write(f"SG {sg}: authorize failed: {e}")

def cmd_close_port(args, write):
    region, iid, port = args.region, args.instance_id, args.port
    proto, cidr = args.protocol, args.cidr
    ec2 = sess(region).client("ec2")
    for sg in _instance_sg_ids(region, iid):
        sgd = ec2.describe_security_groups(GroupIds=[sg])["SecurityGroups"][0]
        found = False
        for p in sgd.get("IpPermissions", []):
            if p.get("IpProtocol") == proto and p.get("FromPort") == port and p.get("ToPort") == port:
                for r in p.get("IpRanges", []):
                    if r.get("CidrIp") == cidr:
                        found = True
        if found:
            try:
                ec2.revoke_security_group_ingress(
                    GroupId=sg,
                    IpPermissions=[{"IpProtocol":proto,"FromPort":port,"ToPort":port,"IpRanges":[{"CidrIp":cidr}]}]
                )
                write(f"SG {sg}: closed {proto}/{port} from {cidr}")
            except ClientError as e:
                write(f"SG {sg}: revoke failed: {e}")
        if not found:
            write(f"SG {sg}: no matching {proto}/{port} from {cidr} to revoke")

def cmd_list_ports(args, write):
    region, iid = args.region, args.instance_id
    ec2 = sess(region).client("ec2")
    for sg in _instance_sg_ids(region, iid):
        sgd = ec2.describe_security_groups(GroupIds=[sg])["SecurityGroups"][0]
        write(f"Security Group: {sg}  ({sgd.get('GroupName')})")
        if not sgd.get("IpPermissions"):
            write("  [no inbound rules]")
            continue
        for p in sgd["IpPermissions"]:
            proto = p.get("IpProtocol")
            fp, tp = p.get("FromPort"), p.get("ToPort")
            rngs = [r.get("CidrIp") for r in p.get("IpRanges", [])]
            if fp is not None and tp is not None:
                write(f"  {proto} {fp}-{tp}: {', '.join(rngs) if rngs else '(no IPv4 CIDRs)'}")
            else:
                write(f"  {proto} (all ports): {', '.join(rngs) if rngs else '(no IPv4 CIDRs)'}")

# --- BEGIN: upgrade helpers & command ---

import re

_SIZE_BASE_ORDER = {
    "nano": 1,
    "micro": 2,
    "small": 3,
    "medium": 4,
    "large": 5,
}
def _size_rank(size: str) -> int:
    """Order sizes within a family: nano < micro < small < medium < large < xlarge < 2xlarge < ... < metal."""
    s = size.strip().lower()
    if s in _SIZE_BASE_ORDER:
        return _SIZE_BASE_ORDER[s]
    m = re.fullmatch(r"(\d+)?xlarge", s)
    if m:
        n = int(m.group(1) or "1")
        return 5 + n
    if s == "metal":
        return 10_000
    return 9_999

def _split_instance_type(it: str):
    parts = it.split(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (it, "")

def _current_instance(ec2, instance_id: str):
    r = ec2.describe_instances(InstanceIds=[instance_id])
    resv = r["Reservations"][0]
    inst = resv["Instances"][0]
    return inst

def _instance_public_ip(inst: dict) -> str | None:
    return inst.get("PublicIpAddress")

def _list_family_types_in_region(ec2, family_prefix: str) -> list[str]:
    paginator = ec2.get_paginator("describe_instance_types")
    out = []
    for page in paginator.paginate():
        for it in page.get("InstanceTypes", []):
            itype = it.get("InstanceType")
            if itype and itype.startswith(family_prefix + "."):
                out.append(itype)
    return sorted(out, key=lambda x: _size_rank(x.split(".", 1)[1]))

def _family_upgrades_available(ec2, current_type: str) -> list[str]:
    fam, size = _split_instance_type(current_type)
    all_in_family = _list_family_types_in_region(ec2, fam)
    cur_rank = _size_rank(size)
    return [t for t in all_in_family if _size_rank(t.split(".",1)[1]) > cur_rank]

def _wait_state(ec2, instance_id: str, state: str, write):
    waiter_name = "instance_" + state
    waiter = ec2.get_waiter(waiter_name)
    write(f"Waiting for instance {instance_id} to be {state} ...")
    waiter.wait(InstanceIds=[instance_id])

def cmd_upgrade(args, write):
    region = args.region
    instance_id = args.instance_id
    new_type = args.apply
    dry = args.dry_run

    ec2 = sess(region).client("ec2")

    inst = _current_instance(ec2, instance_id)
    current_type = inst["InstanceType"]
    write(f"Instance: {instance_id}")
    write(f"Current type: {current_type}")

    upgrades = _family_upgrades_available(ec2, current_type)
    if not upgrades:
        write("No higher tiers available in this family (in this region).")
    else:
        write("Upgrade options (same family):")
        for t in upgrades:
            write(f"  - {t}")

    if not new_type:
        write("\nNo change requested. To apply, run for example:\n"
              f"  {sys.argv[0]} upgrade --region {region} --instance-id {instance_id} --apply {upgrades[0] if upgrades else 'FAMILY.SIZE'}\n"
              "Use --dry-run to check permissions without changing anything.")
        return

    if new_type not in upgrades:
        fam_cur, _ = _split_instance_type(current_type)
        fam_new, _ = _split_instance_type(new_type)
        if fam_cur == fam_new:
            write(f"Requested type {new_type} is not a higher tier vs current ({current_type}) or not available here.")
            sys.exit(1)
        else:
            write(f"Requested type {new_type} is a different family from {current_type}. Proceeding anyway...")

    write(f"\nAbout to {'(dry-run) ' if dry else ''}upgrade {instance_id}: {current_type} → {new_type}")
    try:
        write("Stopping instance...")
        ec2.stop_instances(InstanceIds=[instance_id], DryRun=dry)
        if not dry: _wait_state(ec2, instance_id, "stopped", write)

        write(f"Modifying instance type to {new_type} ...")
        ec2.modify_instance_attribute(InstanceId=instance_id, InstanceType={"Value": new_type}, DryRun=dry)

        write("Starting instance...")
        ec2.start_instances(InstanceIds=[instance_id], DryRun=dry)
        if not dry: _wait_state(ec2, instance_id, "running", write)

        if not dry:
            inst2 = _current_instance(ec2, instance_id)
            ip = _instance_public_ip(inst2)
            if ip:
                write(f"New public IP: {ip}")
            else:
                write("Instance has no public IP (private subnet or no public association).")
        write("Done.")
    except ClientError as e:
        write(f"AWS error during upgrade: {e}")
        sys.exit(2)

# --- END: upgrade helpers & command ---

# ----------------- CLI -----------------
def main():
    p = argparse.ArgumentParser(description="AWS EC2 + Route53 helper (boto3)")
    p.add_argument("--out", help="Append output to file")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    pr = sub.add_parser("list-region"); pr.add_argument("region")
    psr = sub.add_parser("start-region"); psr.add_argument("region")
    pstr = sub.add_parser("stop-region"); pstr.add_argument("region")

    ps = sub.add_parser("start"); ps.add_argument("region"); ps.add_argument("instance_id")
    pst = sub.add_parser("stop");  pst.add_argument("region"); pst.add_argument("instance_id")

    pas = sub.add_parser("assign-subdomain"); pas.add_argument("region")
    pls = sub.add_parser("list-subdomains"); pls.add_argument("zone_id")
    pds = sub.add_parser("delete-subdomain"); pds.add_argument("zone_id"); pds.add_argument("record_name"); pds.add_argument("--type", default="A")

    pcl = sub.add_parser("clone"); pcl.add_argument("region"); pcl.add_argument("instance_id")

    pop = sub.add_parser("open-port");  pop.add_argument("region"); pop.add_argument("instance_id"); pop.add_argument("port", type=int); pop.add_argument("--protocol", default="tcp", choices=["tcp","udp"]); pop.add_argument("--cidr", default="0.0.0.0/0")
    pcp = sub.add_parser("close-port"); pcp.add_argument("region"); pcp.add_argument("instance_id"); pcp.add_argument("port", type=int); pcp.add_argument("--protocol", default="tcp", choices=["tcp","udp"]); pcp.add_argument("--cidr", default="0.0.0.0/0")
    plp = sub.add_parser("list-ports"); plp.add_argument("region"); plp.add_argument("instance_id")

    # --- BEGIN: upgrade subcommand wiring ---
    pup = sub.add_parser("upgrade", help="List/perform instance type upgrade within the same family")
    pup.add_argument("--region", required=True, help="AWS region, e.g., eu-west-1")
    pup.add_argument("--instance-id", required=True, dest="instance_id", help="EC2 instance ID, e.g., i-0123456789abcdef0")
    pup.add_argument("--apply", help="Target instance type to apply (e.g., t3.medium). If omitted, only lists options.")
    pup.add_argument("--dry-run", action="store_true", help="Use AWS DryRun to verify permissions without changing anything.")
    # --- END: upgrade subcommand wiring ---

    args = p.parse_args()
    write = outprinter(args.out)

    try:
        if args.cmd == "list": cmd_list(args, write)
        elif args.cmd == "list-region": cmd_list_region(args, write)
        elif args.cmd == "start-region": cmd_start_region(args, write)
        elif args.cmd == "stop-region": cmd_stop_region(args, write)
        elif args.cmd == "start": cmd_start(args, write)
        elif args.cmd == "stop": cmd_stop(args, write)
        elif args.cmd == "assign-subdomain": cmd_assign_subdomain(args, write)
        elif args.cmd == "list-subdomains": cmd_list_subdomains(args, write)
        elif args.cmd == "delete-subdomain": cmd_delete_subdomain(args, write)
        elif args.cmd == "clone": cmd_clone(args, write)
        elif args.cmd == "open-port": cmd_open_port(args, write)
        elif args.cmd == "close-port": cmd_close_port(args, write)
        elif args.cmd == "list-ports": cmd_list_ports(args, write)
        elif args.cmd == "upgrade": cmd_upgrade(args, write)
    except ClientError as e:
        write(f"AWS error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
