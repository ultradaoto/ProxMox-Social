import requests
import json
import uuid
from datetime import datetime

# Config
API_BASE = "https://social.sterlingcooley.com"
API_KEY = "76667e385a2bd41349fd190d7f97f20220f0a5ec3bdf641d3c1f2a58623261ce"
DUMMY_ID = str(uuid.uuid4()) # Generate a random VALID UUID

print("--- Testing Success Sync Logic (Attempt 2: UUID) ---")

url = f"{API_BASE}/api/queue/gui/complete"
print(f"Target URL: {url}")
print(f"Dummy UUID: {DUMMY_ID}")

payload = {
    'id': DUMMY_ID,
    'status': 'success',
    'completed_at': datetime.now().isoformat()
}

headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

print("\nSending POST request...")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("\n[SUCCESS] Server accepted the request.")
    elif response.status_code == 404:
         print("\n[SUCCESS] 404 received as expected for fake ID.")
         print("This proves we hit the application logic correctly.")
    elif response.status_code == 500:
        print("\n[FAIL] Server Error 500 (Still crashing?)")
    else:
        print(f"\n[WARNING] Unexpected: {response.status_code}")
        
except Exception as e:
    print(f"\n[FAIL] Request error: {e}")

input("\nPress Enter to exit...")
