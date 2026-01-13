import os
import requests
import socket
from dotenv import load_dotenv

# Load env from current directory
load_dotenv()

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://social.sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')

def test_network():
    print("\n--- Network Connectivity Test ---")
    try:
        domain = DASHBOARD_URL.replace('https://', '').replace('http://', '').split('/')[0]
        print(f"Testing connection to {domain}:443...")
        socket.create_connection((domain, 443), timeout=5)
        print("[OK] Success: Can reach server")
        return True
    except Exception as e:
        print(f"[FAIL] Failure: Cannot reach server: {e}")
        return False

def test_api_connection():
    print("\n--- API Connection Test ---")
    # Using the pending endpoint as a test since we know it exists
    url = f"{DASHBOARD_URL}/api/queue/pending" # or whatever the relevant endpoint is
    # The user suggested /api/queue/test but pending is known to work/exist for fetching
    # Let's try the one suggested first just in case
    test_url = f"{DASHBOARD_URL}/api/queue/test"
    
    headers = {"X-API-Key": API_KEY}
    
    print(f"Testing URL: {test_url}")
    print(f"API Key (masked): {API_KEY[:8]}...{API_KEY[-4:] if API_KEY else 'NONE'}")
    
    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 404:
            print("Note: 404 might just mean the test endpoint doesn't exist.")
            print("Trying /api/queue/pending...")
            pending_url = f"{DASHBOARD_URL}/api/queue/pending"
            resp2 = requests.get(pending_url, headers=headers, timeout=10)
            print(f"Pending Status: {resp2.status_code}")
            return resp2.ok
            
        return response.ok
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    test_network()
    test_api_connection()
