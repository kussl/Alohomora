#!/usr/bin/env python3
"""
Minimal production simulator for Alohomora EC2 deployment.
"""

import json
import requests
import sys
import datetime
import os
import time
import psutil
import socket, ssl
from urllib.parse import urlparse
import certifi


def measure_connect_tls(url: str, timeout: float = 10.0):
    """
    Measure DNS resolve, TCP connect, and TLS handshake time to the host in 'url'.
    Returns a dict with durations in milliseconds. Never raises; embeds 'error' on failure.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    result = {
        "url": url,
        "host": host,
        "port": port,
        "scheme": parsed.scheme,
        "dns_ms": None,
        "tcp_ms": None,
        "tls_ms": None,
        "total_ms": None,
        "timestamp": time.time()
    }

    try:
        # DNS
        t0 = time.time()
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        t1 = time.time()
        result["dns_ms"] = (t1 - t0) * 1000.0

        # TCP connect
        family, socktype, proto, canonname, sockaddr = infos[0]
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        t2 = time.time()
        sock.connect(sockaddr)
        t3 = time.time()
        result["tcp_ms"] = (t3 - t2) * 1000.0

        # TLS handshake (only if https)
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            # Use the same CA bundle as 'requests' to avoid trust-store mismatch
            ctx.load_verify_locations(cafile=certifi.where())
            t4 = time.time()
            ssock = ctx.wrap_socket(sock, server_hostname=host)  # handshake happens here
            t5 = time.time()
            result["tls_ms"] = (t5 - t4) * 1000.0
            ssock.close()
        else:
            sock.close()


        # Totals (only if we got pieces)
        total = 0.0
        for k in ("dns_ms", "tcp_ms", "tls_ms"):
            if result[k] is not None:
                total += result[k]
        result["total_ms"] = total if total > 0 else None

    except Exception as e:
        # Non-fatal: capture error string and continue
        try:
            sock.close()
        except Exception:
            pass
        result["error"] = f"{type(e).__name__}: {e}"

    return result


class PerformanceMetrics:
    """Collect and store performance metrics"""

    def __init__(self):
        self.metrics = {
            "timestamps": {},
            "latencies": {},
            "resource_usage": {},
            "cache_stats": {},
            "metadata": {},
            "connection_setup": []  # NEW: per-host DNS/TCP/TLS measurements
        }
        self.start_time = time.time()

    def record_timestamp(self, event_name):
        """Record timestamp for an event"""
        self.metrics["timestamps"][event_name] = time.time()

    def record_latency(self, operation, duration_ms):
        """Record latency for an operation"""
        if operation not in self.metrics["latencies"]:
            self.metrics["latencies"][operation] = []
        self.metrics["latencies"][operation].append(duration_ms)

    def record_response(self, operation, response, start_time):
        """Record response details and calculate latency"""
        duration_ms = (time.time() - start_time) * 1000
        self.record_latency(operation, duration_ms)

        # Store response metadata
        if operation not in self.metrics["metadata"]:
            self.metrics["metadata"][operation] = []

        self.metrics["metadata"][operation].append({
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "timestamp": time.time()
        })

    def record_cache_hit(self, source):
        """Record cache hit/miss"""
        if "hit" not in self.metrics["cache_stats"]:
            self.metrics["cache_stats"]["hit"] = 0
            self.metrics["cache_stats"]["miss"] = 0

        if source == "replica":
            self.metrics["cache_stats"]["hit"] += 1
        elif source == "main":
            self.metrics["cache_stats"]["miss"] += 1

    def record_resource_usage(self, stage):
        """Record CPU and memory usage"""
        process = psutil.Process()
        self.metrics["resource_usage"][stage] = {
            "cpu_percent": process.cpu_percent(interval=0.1),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "timestamp": time.time()
        }

    def record_connection_setup(self, info: dict):
        """Record DNS/TCP/TLS timing info for a host"""
        self.metrics["connection_setup"].append(info)

    def get_summary(self):
        """Get summary statistics"""
        summary = {
            "total_duration_sec": time.time() - self.start_time,
            "latencies_summary": {},
            "cache_hit_rate": 0.0,
            "resource_usage": self.metrics["resource_usage"]
        }

        # Calculate latency statistics
        for operation, durations in self.metrics["latencies"].items():
            if durations:
                sorted_durations = sorted(durations)
                n = len(sorted_durations)
                summary["latencies_summary"][operation] = {
                    "min_ms": min(sorted_durations),
                    "max_ms": max(sorted_durations),
                    "mean_ms": sum(sorted_durations) / n,
                    "p50_ms": sorted_durations[int(n * 0.50)],
                    "p95_ms": sorted_durations[int(n * 0.95)] if n > 1 else sorted_durations[0],
                    "p99_ms": sorted_durations[int(n * 0.99)] if n > 1 else sorted_durations[0],
                    "count": n
                }

        # Calculate cache hit rate
        total_cache = self.metrics["cache_stats"].get("hit", 0) + self.metrics["cache_stats"].get("miss", 0)
        if total_cache > 0:
            summary["cache_hit_rate"] = self.metrics["cache_stats"].get("hit", 0) / total_cache

        return summary

    def save_to_file(self, filename="performance_metrics.json"):
        """Save all metrics to file"""
        output = {
            "summary": self.get_summary(),
            "raw_metrics": self.metrics,
            "timestamp": datetime.datetime.now().isoformat()
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)

        return filename


def load_production_config():
    """Load server URLs and system IDs from deployment files"""

    # Load registered systems
    with open('registered_systems.json', 'r') as f:
        systems = json.load(f)

    config = {
        "servers": {
            "main": "https://main.datarivers.io",
            "app1": "https://app1.datarivers.io",
            "app2": "https://app2.datarivers.io",
            "replica1": "https://replica1.datarivers.io"
        },
        "system_ids": {
            "app1": systems["app1"]["system_id"],
            "app2": systems["app2"]["system_id"],
            "replica1": systems["replica1"]["system_id"]
        }
    }

    return config


def health_check_servers(servers):
    """Verify all production servers are reachable"""

    for name, url in servers.items():
        try:
            response = requests.get(f"{url}/hello", timeout=10, verify=True)
            if response.status_code == 200:
                print(f"  ✓ {name}: {url}")
            else:
                print(f"  ✗ {name}: {url} (status {response.status_code})")
                return False
        except Exception as e:
            print(f"  ✗ {name}: {url} ({e})")
            return False

    return True


def simulate_single_user(servers, system_ids, workflow_data, metrics=None, debug=False, session=None):
    """Execute one complete user workflow"""

    user_id = "employee_001"

    # Measure connection/TLS setup to app1 before first request
    if metrics:
        metrics.record_connection_setup(measure_connect_tls(servers['app1']))

    # Step 1: App1 creates session
    if metrics:
        metrics.record_timestamp("session_create_start")
    start_time = time.time()

    session_response = (session or requests).post(
        f"{servers['app1']}/new_session",
        json={"user_id": user_id},
        timeout=10,
        verify=True
    )

    if metrics:
        metrics.record_response("session_create", session_response, start_time)
        metrics.record_timestamp("session_create_end")

    if session_response.status_code != 201:
        print(f"  ✗ Failed to create session: {session_response.text}")
        return False

    session_id = session_response.json()["session_id"]
    print(f"  ✓ Session created on app1 (id: {session_id[:8]}...)")
    if debug:
        print(f"[DEBUG] session_response: {session_response.json()}")

    # Step 2: App1 registers token
    token = f"token_{user_id}_{session_id[:8]}"

    if metrics:
        metrics.record_timestamp("token_register_start")
    start_time = time.time()

    token_response = (session or requests).post(
        f"{servers['app1']}/register_token",
        json={
            "session_id": session_id,
            "token": token,
            "workflow_id": workflow_data["workflow_id"],
            "function_id": workflow_data["func1_id"],
            "system_id": system_ids["app1"],
            "user_id": user_id
        },
        timeout=10,
        verify=True
    )

    if metrics:
        metrics.record_response("token_register", token_response, start_time)
        metrics.record_timestamp("token_register_end")

    if token_response.status_code != 201:
        print(f"  ✗ Failed to register token: {token_response.text}")
        return False

    token_id = token_response.json()["alohomora_token_id"]
    print(f"  ✓ Token registered (id: {token_id[:8]}...) for system {system_ids['app1']}")
    if debug:
        print(f"[DEBUG] token_response: {token_response.json()}")

    # Step 3: Realistic pause between app1 registration and app2 usage
    print(f"  ⏳ Simulating 1s user workflow delay...")
    if metrics:
        metrics.record_timestamp("sync_wait_start")
    time.sleep(10)  # Realistic 1 second delay
    if metrics:
        metrics.record_timestamp("sync_wait_end")

    # Measure connection/TLS setup to app2 before first request
    if metrics:
        metrics.record_connection_setup(measure_connect_tls(servers['app2']))

    # Step 4: App2 executes function with token validation (replica-first)
    if metrics:
        metrics.record_timestamp("function_execute_start")
    start_time = time.time()

    function_response = (session or requests).post(
        f"{servers['app2']}/function",
        json={
            "function_id": workflow_data["func2_id"],
            "token": token_id,
            "user_id": user_id,
            "system_id": system_ids["app1"]
        },
        timeout=10,
        verify=True
    )

    if metrics:
        metrics.record_response("function_execute", function_response, start_time)
        metrics.record_timestamp("function_execute_end")

    if function_response.status_code != 200:
        print(f"  ✗ Function execution failed: {function_response.text}")
        return False

    function_data = function_response.json()
    if debug:
        print(f"[DEBUG] function_response: {function_data}")
        if "replica_response" in function_data:
            print(f"[DEBUG] replica_response: {function_data['replica_response']}")
    token_source = function_data.get("token_source", "unknown")

    if metrics:
        metrics.record_cache_hit(token_source)

    if function_data.get("success", False):
        print(f"  ✓ Function executed successfully (token source: {token_source})")
    else:
        print(f"  ✗ Function failed: {function_data.get('error', 'Unknown error')}")
        return False

    return True


def save_simulation_log(workflow_data, session_data=None, token_data=None):
    """Save simulation data to log file"""
    log_file = "simulation_log.json"
    timestamp = datetime.datetime.now().isoformat()

    log_entry = {
        "timestamp": timestamp,
        "workflow": workflow_data,
        "session": session_data,
        "token": token_data
    }

    # Append to log file
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(log_entry)

    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)

    print(f"  ✓ Logged to {log_file}")


def cleanup_simulation_data(main_url, workflow_id=None, function_ids=None):
    """Clean up simulation data from main server"""
    print("[CLEANUP] Removing simulation data...")

    # Note: This requires delete endpoints on the main server
    # For now, we'll just log what should be deleted

    if workflow_id:
        print(f"  • Workflow: {workflow_id[:8]}...")

    if function_ids:
        for func_id in function_ids:
            print(f"  • Function: {func_id[:8]}...")

    print("  ℹ Manual cleanup: DELETE FROM workflows WHERE workflow_id=?")
    print("  ℹ Manual cleanup: DELETE FROM system_functions WHERE function_id IN (?)")
    print("  ℹ Manual cleanup: DELETE FROM shared_tokens WHERE workflow_id=?")


def register_workflow(main_url, app1_system_id, app2_system_id):
    """Register two-step employee onboarding workflow"""

    # Register function 1: Initial employee profile (app1)
    func1_response = requests.post(
        f"{main_url}/register_function",
        json={
            "system_id": app1_system_id,
            "function_name": "employee_profile",
            "url": "https://app1.datarivers.io/employee_profile"
        },
        timeout=10,
        verify=True
    )

    if func1_response.status_code != 201:
        print(f"  ✗ Failed to register employee_profile: {func1_response.text}")
        return None

    func1_id = func1_response.json()["function_id"]
    print(f"  ✓ Function 'employee_profile' registered (id: {func1_id[:8]}...)")

    # Register function 2: Healthcare setup (app2)
    func2_response = requests.post(
        f"{main_url}/register_function",
        json={
            "system_id": app2_system_id,
            "function_name": "healthcare_setup",
            "url": "https://app2.datarivers.io/healthcare_setup"
        },
        timeout=10,
        verify=True
    )

    if func2_response.status_code != 201:
        print(f"  ✗ Failed to register healthcare_setup: {func2_response.text}")
        return None

    func2_id = func2_response.json()["function_id"]
    print(f"  ✓ Function 'healthcare_setup' registered (id: {func2_id[:8]}...)")

    # Register workflow: employee_profile → healthcare_setup
    workflow_response = requests.post(
        f"{main_url}/register_workflow",
        json={
            "system_id": app1_system_id,
            "workflow_graph": {
                "vertices": {
                    func1_id: {"f": "employee_profile", "s": app1_system_id},
                    func2_id: {"f": "healthcare_setup", "s": app2_system_id}
                },
                "adj": {
                    func1_id: [func2_id]
                }
            }
        },
        timeout=10,
        verify=True
    )

    if workflow_response.status_code != 201:
        print(f"  ✗ Failed to register workflow: {workflow_response.text}")
        return None

    workflow_id = workflow_response.json()["workflow_id"]
    print(f"  ✓ Workflow registered (id: {workflow_id[:8]}...)")

    workflow_data = {
        "workflow_id": workflow_id,
        "func1_id": func1_id,
        "func2_id": func2_id
    }

    # Log workflow registration
    save_simulation_log(workflow_data)

    return workflow_data


def single_round():
    """Execute one complete lifecycle test"""

    print("=== Alohomora Production Test - Single Round ===")
    print()

    workflow_data = None
    metrics = PerformanceMetrics()

    try:
        # Record initial resource usage
        metrics.record_resource_usage("start")

        # Step 1: Load configuration
        print("[SETUP] Loading configuration...")
        config = load_production_config()
        print(f"  ✓ Main server: {config['servers']['main']}")
        print(f"  ✓ App1: {config['servers']['app1']} (system: {config['system_ids']['app1'][:8]}...)")
        print(f"  ✓ App2: {config['servers']['app2']} (system: {config['system_ids']['app2'][:8]}...)")
        print(f"  ✓ Replica1: {config['servers']['replica1']} (system: {config['system_ids']['replica1'][:8]}...)")
        print()

        # Step 2: Health check
        print("[HEALTH CHECK] Verifying servers...")
        if not health_check_servers(config['servers']):
            print("\n✗ Health check failed")
            sys.exit(1)
        print()

        metrics.record_resource_usage("after_health_check")

        # Step 3: Register workflow
        print("[WORKFLOW SETUP] Registering employee onboarding workflow...")
        workflow_data = register_workflow(
            config['servers']['main'],
            config['system_ids']['app1'],
            config['system_ids']['app2']
        )

        if not workflow_data:
            print("\n✗ Workflow registration failed")
            sys.exit(1)
        print()

        metrics.record_resource_usage("after_workflow_setup")

        # Step 4: Simulate single user
        print("[USER SIMULATION] Running employee onboarding for employee_001...")
        if not simulate_single_user(config['servers'], config['system_ids'], workflow_data, metrics, debug=True):
            print("\n✗ User simulation failed")
            cleanup_simulation_data(
                config['servers']['main'],
                workflow_data.get('workflow_id'),
                [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
            )
            sys.exit(1)

        metrics.record_resource_usage("after_simulation")

        print("\n✓ Single round complete")

        # Save performance metrics
        metrics_file = metrics.save_to_file()
        print(f"\n[METRICS] Performance data saved to {metrics_file}")

        # Print summary
        summary = metrics.get_summary()
        print(f"\n[METRICS] Summary:")
        print(f"  Total duration: {summary['total_duration_sec']:.2f}s")
        print(f"  Cache hit rate: {summary['cache_hit_rate']:.1%}")

        if summary['latencies_summary']:
            print(f"\n  Latencies:")
            for op, stats in summary['latencies_summary'].items():
                print(f"    {op}:")
                print(f"      Mean: {stats['mean_ms']:.1f}ms, P95: {stats['p95_ms']:.1f}ms, P99: {stats['p99_ms']:.1f}ms")

        # Cleanup after success
        print()
        cleanup_simulation_data(
            config['servers']['main'],
            workflow_data.get('workflow_id'),
            [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
        )

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Cleaning up...")
        if workflow_data:
            cleanup_simulation_data(
                config['servers']['main'],
                workflow_data.get('workflow_id'),
                [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
            )
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        if workflow_data:
            cleanup_simulation_data(
                config['servers']['main'],
                workflow_data.get('workflow_id'),
                [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
            )
        sys.exit(1)

def single_round_cache(duration_sec=180, lambda_rps=0.5):
    """Cache hit-rate experiment (uniform/Poisson traffic to app2 over a duration)."""

    print("=== Alohomora Cache Experiment - Single Round (Hit Rate & Source Mix) ===")
    print(f"  Config: duration={duration_sec}s, λ={lambda_rps:.2f} req/s")
    print()

    # --- Experiment knobs (use parameters now) -------------------------------
    EXP_DURATION_SEC = duration_sec
    LAMBDA_RPS = lambda_rps
    JITTER_WARMUP_SEC = 2
    DEBUG = True

    workflow_data = None
    metrics = PerformanceMetrics()

    try:
        # Record initial resource usage
        metrics.record_resource_usage("start")

        # Step 1: Load configuration
        print("[SETUP] Loading configuration...")
        config = load_production_config()
        print(f"  ✓ Main server: {config['servers']['main']}")
        print(f"  ✓ App1: {config['servers']['app1']} (system: {config['system_ids']['app1'][:8]}...)")
        print(f"  ✓ App2: {config['servers']['app2']} (system: {config['system_ids']['app2'][:8]}...)")
        print(f"  ✓ Replica1: {config['servers']['replica1']} (system: {config['system_ids']['replica1'][:8]}...)")
        print()

        # Step 2: Health check
        print("[HEALTH CHECK] Verifying servers...")
        if not health_check_servers(config['servers']):
            print("\n✗ Health check failed")
            sys.exit(1)
        print()

        metrics.record_resource_usage("after_health_check")

        # Step 3: Register workflow
        print("[WORKFLOW SETUP] Registering employee onboarding workflow...")
        workflow_data = register_workflow(
            config['servers']['main'],
            config['system_ids']['app1'],
            config['system_ids']['app2']
        )

        if not workflow_data:
            print("\n✗ Workflow registration failed")
            sys.exit(1)
        print()

        metrics.record_resource_usage("after_workflow_setup")

        # --- App1: create session + register token (once) ----------------------
        user_id = "employee_001"

        # Measure connection/TLS setup to app1 before first request
        metrics.record_connection_setup(measure_connect_tls(config['servers']['app1']))

        # Create session
        metrics.record_timestamp("session_create_start")
        t0 = time.time()
        r = requests.post(
            f"{config['servers']['app1']}/new_session",
            json={"user_id": user_id},
            timeout=10, verify=True
        )
        metrics.record_response("session_create", r, t0)
        metrics.record_timestamp("session_create_end")
        if r.status_code != 201:
            print(f"  ✗ Failed to create session: {r.text}")
            sys.exit(1)
        session_id = r.json()["session_id"]
        print(f"  ✓ Session created on app1 (id: {session_id[:8]}...)")
        if DEBUG: print(f"[DEBUG] session_response: {r.json()}")

        # Register token
        token = f"token_{user_id}_{session_id[:8]}"
        metrics.record_timestamp("token_register_start")
        t0 = time.time()
        r = requests.post(
            f"{config['servers']['app1']}/register_token",
            json={
                "session_id": session_id,
                "token": token,
                "workflow_id": workflow_data["workflow_id"],
                "function_id": workflow_data["func1_id"],
                "system_id": config["system_ids"]["app1"],
                "user_id": user_id
            },
            timeout=10, verify=True
        )
        metrics.record_response("token_register", r, t0)
        metrics.record_timestamp("token_register_end")
        if r.status_code != 201:
            print(f"  ✗ Failed to register token: {r.text}")
            sys.exit(1)
        token_id = r.json()["alohomora_token_id"]
        print(f"  ✓ Token registered (id: {token_id[:8]}...) for system {config['system_ids']['app1']}")
        if DEBUG: print(f"[DEBUG] token_response: {r.json()}")
        print(f"  ⏳ Warmup {JITTER_WARMUP_SEC}s...")
        time.sleep(JITTER_WARMUP_SEC)

        # Measure connection/TLS setup to app2 once before starting traffic
        metrics.record_connection_setup(measure_connect_tls(config['servers']['app2']))

        # --- Step 4: Generate Poisson requests to app2 for EXP_DURATION_SEC ----
        print(f"[USER TRAFFIC] Sending requests to app2 for {EXP_DURATION_SEC}s "
              f"at ~{LAMBDA_RPS:.2f} req/s (Poisson inter-arrivals)")
        start_ts = time.time()
        sent = 0
        ok = 0

        while True:
            now = time.time()
            if now - start_ts >= EXP_DURATION_SEC:
                break

            # One verification request to app2 (replica-first path in your backend)
            metrics.record_timestamp("function_execute_start")
            t0 = time.time()
            resp = requests.post(
                f"{config['servers']['app2']}/function",
                json={
                    "function_id": workflow_data["func2_id"],
                    "token": token_id,
                    "user_id": user_id,
                    "system_id": config["system_ids"]["app1"]
                },
                timeout=10, verify=True
            )
            metrics.record_response("function_execute", resp, t0)
            metrics.record_timestamp("function_execute_end")

            sent += 1
            if resp.status_code == 200 and resp.json().get("success", False):
                ok += 1
                token_source = resp.json().get("token_source", "unknown")
                metrics.record_cache_hit(token_source)
                if DEBUG and sent % 10 == 0:
                    print(f"    • #{sent} ok (source: {token_source})")
            else:
                err = getattr(resp, "text", "no-body")
                print(f"    ✗ app2 call failed (status={resp.status_code}): {err}")

            # Sleep with exponential inter-arrival (Poisson process)
            # Avoid extremely small/large waits with min/max clamp
            import random
            inter = random.expovariate(LAMBDA_RPS)
            inter = max(0.05, min(inter, 3.0))
            time.sleep(inter)

        metrics.record_resource_usage("after_simulation")

        # --- Wrap-up & reporting ----------------------------------------------
        print(f"\n✓ Cache experiment complete: {ok}/{sent} successful")

        metrics_file = metrics.save_to_file("performance_metrics_cache_hit.json")
        print(f"\n[METRICS] Performance data saved to {metrics_file}")

        summary = metrics.get_summary()
        print(f"\n[METRICS] Summary:")
        print(f"  Total duration: {summary['total_duration_sec']:.2f}s")
        print(f"  Cache hit rate: {summary['cache_hit_rate']:.1%}")

        if summary['latencies_summary']:
            print(f"\n  Latencies:")
            for op, stats in summary['latencies_summary'].items():
                print(f"    {op}:")
                print(f"      Mean: {stats['mean_ms']:.1f}ms, P95: {stats['p95_ms']:.1f}ms, P99: {stats['p99_ms']:.1f}ms")

        print()
        cleanup_simulation_data(
            config['servers']['main'],
            workflow_data.get('workflow_id'),
            [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
        )

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Cleaning up...")
        if workflow_data:
            cleanup_simulation_data(
                config['servers']['main'],
                workflow_data.get('workflow_id'),
                [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
            )
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        if workflow_data:
            cleanup_simulation_data(
                config['servers']['main'],
                workflow_data.get('workflow_id'),
                [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
            )
        sys.exit(1)

def simulate_user_cache_concurrency(servers, system_ids, workflow_data, metrics,
                                    user_id, repeats=5, warmup_s=15, gap_s=2, debug=False,session=None):
    """Same as simulate_single_user but shaped to reveal replica hits under concurrency."""
    # Measure connection/TLS setup to app1 before first request
    metrics.record_connection_setup(measure_connect_tls(servers['app1']))

    # 1) session
    metrics.record_timestamp("session_create_start")
    t0 = time.time()
    r = (session or requests).post(f"{servers['app1']}/new_session", json={"user_id": user_id}, timeout=10, verify=True)
    metrics.record_response("session_create", r, t0)
    metrics.record_timestamp("session_create_end")
    if r.status_code != 201: return False
    session_id = r.json()["session_id"]

    # 2) token register
    token = f"token_{user_id}_{session_id[:8]}"
    metrics.record_timestamp("token_register_start")
    t0 = time.time()
    r = (session or requests).post(f"{servers['app1']}/register_token", json={
        "session_id": session_id,
        "token": token,
        "workflow_id": workflow_data["workflow_id"],
        "function_id": workflow_data["func1_id"],
        "system_id": system_ids["app1"],
        "user_id": user_id
    }, timeout=10, verify=True)
    metrics.record_response("token_register", r, t0)
    metrics.record_timestamp("token_register_end")
    if r.status_code != 201: return False
    token_id = r.json()["alohomora_token_id"]

    # 3) warmup: wait past the next replica sync so cache can see the token
    import random
    time.sleep(max(0, warmup_s + random.uniform(-5, 5)))

    # Measure connection/TLS setup to app2 before first request
    metrics.record_connection_setup(measure_connect_tls(servers['app2']))

    # 4) multiple app2 calls → will show cache hits if replica-first works
    for i in range(repeats):
        metrics.record_timestamp("function_execute_start")
        t0 = time.time()
        rr = (session or requests).post(f"{servers['app2']}/function", json={
            "function_id": workflow_data["func2_id"],
            "token": token_id,
            "user_id": user_id,
            "system_id": system_ids["app1"]
        }, timeout=10, verify=True)
        metrics.record_response("function_execute", rr, t0)
        metrics.record_timestamp("function_execute_end")
        if rr.status_code != 200 or not rr.json().get("success", False):
            return False
        metrics.record_cache_hit(rr.json().get("token_source", "unknown"))
        if i < repeats - 1:
            time.sleep(max(0, gap_s + random.uniform(-2, 2)))

    return True

def load_test(pattern, max_users, duration_sec=60, warmup_s=60):
    """Run load test with n concurrent users following a traffic pattern"""
    from concurrent.futures import ThreadPoolExecutor
    import math, random
    JITTER_S = 3 

    print(f"=== Load Test: {pattern} pattern, {max_users} users ===\n")

    # Setup
    config = load_production_config()
    workflow_data = register_workflow(
        config['servers']['main'],
        config['system_ids']['app1'],
        config['system_ids']['app2']
    )
    if not workflow_data:
        print("✗ Setup failed")
        return

    # --- NEW: normalize pattern (e.g., linear_cached -> linear)
    base_pattern = pattern
    if pattern.endswith("_cached"):
        base_pattern = pattern.rsplit("_", 1)[0]  # drop the suffix

    # Calculate arrival times based on (base_)pattern
    arrival_times = []
    for i in range(max_users):
        t = i / max_users
        if base_pattern == "linear":
            arrival_times.append(t * duration_sec)
        elif base_pattern == "exponential":
            arrival_times.append(duration_sec * (1 - math.exp(-3 * t)))
        elif base_pattern == "step":
            # 5 steps; avoid div-by-zero for small max_users
            buckets = max(1, max_users // 5)
            step = i // buckets
            arrival_times.append((step / 5) * duration_sec)
        elif base_pattern == "constant":
            arrival_times.append(0)
        else:
            # Fallback: treat as linear
            arrival_times.append(t * duration_sec)

    # De-sync arrivals a bit to avoid herd bursts
    for i in range(len(arrival_times)):
        arrival_times[i] = max(0.0, arrival_times[i] + random.uniform(-JITTER_S, JITTER_S))


    # Sanity: ensure length matches
    if len(arrival_times) != max_users:
        arrival_times = (arrival_times + [0] * max_users)[:max_users]

    metrics = PerformanceMetrics()
    start_time = time.time()
    results = []

    def run_user(user_id, arrival_time):
        wait = arrival_time - (time.time() - start_time)
        if wait > 0:
            time.sleep(wait)

        # Reuse one TCP/TLS session per user thread
        with requests.Session() as sess:
            try:
                if pattern == "linear_cached":
                    return simulate_user_cache_concurrency(
                        config['servers'], config['system_ids'], workflow_data, metrics,
                        user_id=user_id, repeats=5, warmup_s=warmup_s, gap_s=5, session=sess
                    )
                else:
                    return simulate_single_user(
                        config['servers'], config['system_ids'], workflow_data, metrics, session=sess
                    )
            except Exception as e:
                print(f"  ✗ {user_id} failed: {type(e).__name__}")
                return False


    with ThreadPoolExecutor(max_workers=max_users) as executor:
        futures = [executor.submit(run_user, f"user_{i}", arrival_times[i]) for i in range(max_users)]
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                print(f"  ✗ Future failed: {type(e).__name__}")
                results.append(False)

    # Summary
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r)
    print(f"\n✓ Completed: {successful}/{max_users} successful in {total_time:.1f}s")
    print(f"  Throughput: {max_users/total_time:.2f} users/sec")

    # Save results to organized directory
    import os
    import subprocess

    result_dir = f"load_test_results/{pattern}_{max_users}_users"
    os.makedirs(result_dir, exist_ok=True)

    metrics_file = f"{result_dir}/metrics.json"
    metrics.save_to_file(metrics_file)
    print(f"\n[RESULTS] Saved to {metrics_file}")

    # Download server metrics logs
    print("\n[METRICS] Downloading server logs...")

    cmd = f"scp main:~/server/main_metrics.jsonl {result_dir}/"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✓ Downloaded main server metrics")
    else:
        print(f"  ⚠ Failed to download main metrics: {result.stderr}")

    cmd = f"scp replica1:~/replica/replica1_metrics.jsonl {result_dir}/"
    result = subprocess.run(cmd.split(), capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✓ Downloaded replica1 metrics")
    else:
        print(f"  ⚠ Failed to download replica1 metrics: {result.stderr}")

    cleanup_simulation_data(
        config['servers']['main'],
        workflow_data.get('workflow_id'),
        [workflow_data.get('func1_id'), workflow_data.get('func2_id')]
    )

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "load":
        # Usage: python3 simulation.py load <pattern> <users> [duration]
        pattern = sys.argv[2] if len(sys.argv) > 2 else "linear"
        users = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        duration = int(sys.argv[4]) if len(sys.argv) > 4 else 60
        warmup_s = int(sys.argv[5]) if len(sys.argv) > 2 else 60

        load_test(pattern, users, duration, warmup_s=warmup_s)

    elif len(sys.argv) > 1 and sys.argv[1] == "single_round_cache":
        # Usage: python3 simulation.py single_round_cache [duration_sec] [lambda_rps]
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 180
        lambda_rps = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        warmup_s = int(sys.argv[4]) if len(sys.argv) > 2 else 60

        print(f"=== Running cache hit-rate experiment ===")
        print(f"  Duration: {duration}s, λ={lambda_rps:.2f} req/s\n")

        single_round_cache(duration_sec=duration, lambda_rps=lambda_rps, warmup_s=warmup_s)

    else:
        single_round()
