import os
import json
from pathlib import Path

PENDING_DIR = Path(r"C:\PostQueue\pending")

if not PENDING_DIR.exists():
    print(f"Directory not found: {PENDING_DIR}")
    exit()

print(f"--- Inspecting {PENDING_DIR} ---")
found = False
for job_dir in PENDING_DIR.iterdir():
    if job_dir.is_dir():
        found = True
        print(f"\n[JOB] {job_dir.name}")
        json_path = job_dir / "job.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Print critical info first
                    print(f"  ID: {data.get('id')}")
                    print(f"  Platform: {data.get('platform')}")
                    print(f"  Status: {data.get('status')}")
                    print(f"  Media: {len(data.get('media', []))} items")
                    print("-" * 20)
                    # Print full JSON
                    print(json.dumps(data, indent=2))
            except Exception as e:
                print(f"Error reading json: {e}")
        else:
            print("No job.json found")

if not found:
    print("No jobs found in pending directory.")
