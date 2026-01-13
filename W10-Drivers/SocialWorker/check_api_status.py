import requests
import os
import json
from dotenv import load_dotenv

# Load env from explicit path to be sure
env_path = r"C:\ProxMox-Social\W10-Drivers\SocialWorker\.env"
load_dotenv(env_path)

api_key = os.getenv("API_KEY")
base_url = os.getenv("DASHBOARD_URL")

if not api_key or not base_url:
    print("ERROR: Could not load API_KEY or DASHBOARD_URL from .env")
    exit(1)

print(f"--- Checking API Status ---")
print(f"URL: {base_url}")

def check_pending():
    url = f"{base_url}/api/queue/gui/pending"
    try:
        print(f"\nQuerying PENDING: {url}")
        resp = requests.get(url, headers={"X-API-Key": api_key}, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Count: {len(data)}")
            for item in data:
                print(f" [PENDING] ID: {item.get('id')} | Platform: {item.get('platform')}")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_pending()
