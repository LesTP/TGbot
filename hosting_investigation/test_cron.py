#!/usr/bin/env python3
"""
Cron Job Test Script

Upload this script to your WordPress host and set up a cron job to run it.
It writes timestamps to a file so you can verify cron is working.

Usage:
1. Upload this file to your host
2. Make executable: chmod +x test_cron.py
3. Get full path: pwd
4. Add to crontab: crontab -e
5. Add line: * * * * * /usr/bin/python3 /full/path/to/test_cron.py
6. Wait 2 minutes and check the timestamp file
7. IMPORTANT: Remove the cron entry after testing!
"""

import os
import sys
from datetime import datetime

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    timestamp_file = os.path.join(script_dir, "cron_timestamp.txt")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if os.path.exists(timestamp_file):
            with open(timestamp_file, "r") as f:
                lines = f.readlines()
            lines = lines[-9:]
        else:
            lines = []

        lines.append(f"{current_time} - Cron job executed successfully\n")

        with open(timestamp_file, "w") as f:
            f.writelines(lines)

        print(f"[{current_time}] Timestamp written to {timestamp_file}")
        return 0

    except Exception as e:
        print(f"[{current_time}] Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
