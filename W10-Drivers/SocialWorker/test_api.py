import requests
import os
import sys

# Configuration from user request
API_BASE = "https://social.sterlingcooley.com"
# Use the key provided in the prompt
API_KEY = "76667e385a2bd41349fd190d7f97f20220f0a5ec3bdf641d3c1f2a58623261ce"

print(f"--- API Diagnostic Test ---")
print(f"Target: {API_BASE}")
print(f"Key: {API_KEY[:8]}...")

# Test 1: Basic connectivity (No Auth)
print("\nTest 1: Check /api/queue/test (No Auth)")
try:
    url = f"{API_BASE}/api/queue/test"
    print(f"  GET {url}")
    r = requests.get(url, timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 2: Get pending items (With Auth)
print("\nTest 2: Check /api/queue/gui/pending (With Auth)")
try:
    url = f"{API_BASE}/api/queue/gui/pending"
    print(f"  GET {url}")
    headers = {"X-API-Key": API_KEY}
    r = requests.get(url, headers=headers, timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text[:200]}...") # Truncate massive responses
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 3: SSL Verification Check (User suggested cause #1)
print("\nTest 3: SSL Verification Check (verify=False)")
try:
    url = f"{API_BASE}/api/queue/test"
    print(f"  GET {url} (verify=False)")
    r = requests.get(url, timeout=10, verify=False)
    # Suppress InsecureRequestWarning for cleaner output in real app, but here usually fine
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

input("\nPress Enter to exit...")
