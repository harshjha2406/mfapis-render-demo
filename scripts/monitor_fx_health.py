import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts/check_fx_health.py"
LOG = Path.home() / ".local/state/mfapis/monitor.jsonl"

CYCLES = int(os.getenv("MFAPIS_MONITOR_CYCLES", "3"))
INTERVAL = int(os.getenv("MFAPIS_MONITOR_INTERVAL_SECONDS", "60"))

if CYCLES < 0 or INTERVAL < 5:
    raise SystemExit("Invalid monitor configuration")

LOG.parent.mkdir(parents=True, exist_ok=True)

def market_open():
    ny = datetime.now(ZoneInfo("America/New_York"))
    day = ny.weekday()
    minute = ny.hour * 60 + ny.minute

    if day == 5:
        return False
    if day == 6:
        return minute >= 17 * 60 + 5
    if day == 4:
        return minute < 16 * 60 + 59

    # Approximate weekday daily maintenance break
    return not (16 * 60 + 59 <= minute < 17 * 60 + 5)

failures = 0

print("MFAPIs automatic monitor started.", flush=True)

try:
    cycles = count(1) if CYCLES == 0 else range(1, CYCLES + 1)

    for cycle in cycles:
        now = datetime.now(timezone.utc).isoformat()
        print(f"\nMONITOR CYCLE {cycle}", flush=True)

        if not market_open():
            status = "MARKET_CLOSED"
            failures = 0
            print("Market closed or scheduled break.")

        else:
            try:
                result = subprocess.run(
                    [sys.executable, str(CHECKER)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )

                print(result.stdout, flush=True)

                if result.stderr:
                    print(result.stderr, flush=True)

                status = "PASS" if result.returncode == 0 else "FAIL"

            except (subprocess.TimeoutExpired, OSError) as error:
                status = "FAIL"
                print("Health check error:", error)

            if status == "PASS":
                if failures:
                    print("RECOVERED: Health check is passing.")
                failures = 0
            else:
                failures += 1
                print("Consecutive failures:", failures)

                if failures >= 3:
                    print("ALERT: FX data health check is failing!")

        with LOG.open("a") as file:
            file.write(json.dumps({
                "timestamp": now,
                "cycle": cycle,
                "status": status,
                "consecutive_failures": failures
            }) + "\n")

        print("MONITOR STATUS:", status, flush=True)

        if CYCLES == 0 or cycle < CYCLES:
            time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("\nMonitor stopped by user.")

print("Monitoring session completed.")
