#!/usr/bin/env python3
"""
Continuous metrics logger for server resource monitoring.
Runs independently and logs CPU/memory metrics to file.
"""

import psutil
import time
import json
import datetime
import os
import sys


def log_metrics(log_file, interval=1):
    """Log system metrics continuously"""

    print(f"Starting metrics logger: {log_file}")
    print(f"Logging interval: {interval}s")
    print("Press Ctrl+C to stop")

    # Get the main process (gunicorn master or python)
    # Look for processes listening on typical ports
    target_pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if process is listening on our ports (8000, 8001, 8002)
            connections = proc.connections()
            for conn in connections:
                if conn.status == 'LISTEN' and conn.laddr.port in [8000, 8001, 8002]:
                    target_pids.append(proc.info['pid'])
                    print(f"Monitoring PID {proc.info['pid']} ({proc.info['name']}) on port {conn.laddr.port}")
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

    if not target_pids:
        print("Warning: No server processes found on ports 8000-8002")
        print("Logging system-wide metrics instead")

    try:
        with open(log_file, 'w') as f:
            while True:
                timestamp = time.time()

                # System-wide metrics
                system_metrics = {
                    "timestamp": timestamp,
                    "datetime": datetime.datetime.now().isoformat(),
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_available_mb": psutil.virtual_memory().available / 1024 / 1024,
                }

                # Per-process metrics for server processes
                if target_pids:
                    process_metrics = []
                    for pid in target_pids:
                        try:
                            proc = psutil.Process(pid)
                            process_metrics.append({
                                "pid": pid,
                                "cpu_percent": proc.cpu_percent(interval=0.1),
                                "memory_mb": proc.memory_info().rss / 1024 / 1024,
                                "num_threads": proc.num_threads(),
                                "connections": len(proc.connections())
                            })
                        except psutil.NoSuchProcess:
                            target_pids.remove(pid)

                    system_metrics["processes"] = process_metrics

                # Write as single line JSON
                f.write(json.dumps(system_metrics) + '\n')
                f.flush()

                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\nMetrics logging stopped. Log saved to: {log_file}")


if __name__ == "__main__":
    # Determine log file name based on location
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        # Auto-detect based on directory
        current_dir = os.path.basename(os.getcwd())
        log_file = f"metrics_log.jsonl"

    # Determine interval
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    log_metrics(log_file, interval)
