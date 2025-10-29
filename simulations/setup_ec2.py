#!/usr/bin/env python3
"""
Minimal EC2 setup script for Alohomora production experiments.
Installs required software on EC2 instances via SSH.
"""

import subprocess
import sys
import csv


def read_machines(csv_file):
    """Read machine configurations from CSV"""
    machines = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            machines.append(row)
    return machines


def ssh_exec(hostname, command, timeout=60):
    """Execute command on remote host via SSH with timeout"""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new', hostname, command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"


def rollback_installation(hostname):
    """Rollback partial installation on failure"""
    print(f"Rolling back installation on {hostname}...")

    rollback_commands = [
        "python3 -m pip uninstall -y flask requests psutil numpy",
        "sudo apt-get remove -y certbot",
        "sudo apt-get autoremove -y"
    ]

    for cmd in rollback_commands:
        ssh_exec(hostname, cmd, timeout=60)

    print(f"  ✓ Rollback complete")


def install_dependencies(hostname):
    """Install Python and required packages on remote host"""
    print(f"Installing dependencies on {hostname}...")

    commands = [
        ("sudo apt-get update -y", 120),
        ("sudo apt-get install -y python3 python3-pip python3-venv certbot nginx", 300),
        ("python3 -m pip install --user --break-system-packages flask requests psutil numpy pyyaml gunicorn", 180),
    ]

    for cmd, timeout in commands:
        rc, stdout, stderr = ssh_exec(hostname, cmd, timeout=timeout)
        if rc != 0:
            print(f"  ERROR on {hostname}: {stderr}")
            rollback_installation(hostname)
            return False
        print(f"  ✓ {cmd.split()[0]}")

    return True


def rollback_certificate(hostname, domain):
    """Rollback certificate on failure"""
    print(f"  Rolling back certificate for {domain}...")
    ssh_exec(hostname, f"sudo certbot delete --non-interactive --cert-name {domain} 2>/dev/null || true", timeout=30)


def setup_letsencrypt(hostname, domain):
    """Setup Let's Encrypt certificate for domain"""
    print(f"Setting up Let's Encrypt for {domain}...")

    # Stop nginx temporarily to free port 80
    print(f"  Stopping nginx temporarily...")
    ssh_exec(hostname, "sudo systemctl stop nginx 2>/dev/null || true", timeout=10)

    # Get certificate using standalone mode (requires port 80)
    cmd = f"sudo certbot certonly --standalone --non-interactive --agree-tos --email admin@datarivers.io -d {domain}"

    rc, stdout, stderr = ssh_exec(hostname, cmd, timeout=120)

    # Restart nginx regardless of certbot result
    ssh_exec(hostname, "sudo systemctl start nginx 2>/dev/null || true", timeout=10)

    if rc != 0:
        print(f"  ✗ Certificate acquisition failed: {stderr}")
        return False

    print(f"  ✓ Certificate obtained for {domain}")
    return True


def test_connection(hostname):
    """Test SSH connectivity before setup"""
    print(f"Testing connection to {hostname}...")
    rc, stdout, stderr = ssh_exec(hostname, "echo 'connected'", timeout=10)

    if rc == 0 and "connected" in stdout:
        print(f"  ✓ Connected")
        return True
    else:
        print(f"  ✗ Connection failed: {stderr}")
        return False


def verify_installation(hostname):
    """Verify Python and packages are installed"""
    print(f"Verifying installation on {hostname}...")

    rc, stdout, stderr = ssh_exec(hostname, "python3 -c 'import flask, requests, psutil, numpy; print(\"OK\")'")

    if rc == 0 and "OK" in stdout:
        print(f"  ✓ Verified")
        return True
    else:
        print(f"  ✗ Verification failed: {stderr}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 setup_ec2.py <machines.csv> [machine_name...] [--skip-certs]")
        sys.exit(1)

    machines_file = sys.argv[1]
    skip_certs = "--skip-certs" in sys.argv

    # Extract machine name filters (arguments that are not flags)
    machine_filters = [arg for arg in sys.argv[2:] if not arg.startswith('--')]

    machines = read_machines(machines_file)

    # Filter machines if specific names provided
    if machine_filters:
        machines = [m for m in machines if m['hostname'] in machine_filters]
        print(f"Filtered to {len(machines)} machine(s): {', '.join(machine_filters)}\n")

    print(f"Setting up {len(machines)} machines...\n")

    failed = []
    for machine in machines:
        hostname = machine['hostname']
        role = machine['role']
        domain = machine.get('domain', '') 

        print(f"--- {hostname} ({role}) ---")

        if not test_connection(hostname):
            failed.append(hostname)
            continue

        if not install_dependencies(hostname):
            failed.append(hostname)
            continue

        if not verify_installation(hostname):
            failed.append(hostname)
            continue

        if not skip_certs and domain:
            if not setup_letsencrypt(hostname, domain):
                print(f"  ⚠ Certificate setup failed, continuing...")

        print(f"✓ {hostname} setup complete\n")

    print("\n=== Setup Summary ===")
    print(f"Total: {len(machines)}")
    print(f"Success: {len(machines) - len(failed)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print(f"Failed machines: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
