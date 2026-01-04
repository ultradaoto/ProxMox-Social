import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://social.sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')

class APIMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['X-API-Key'] = API_KEY
        self.dashboard_url = DASHBOARD_URL
        print(f"[API Monitor] Initialized with URL: {self.dashboard_url}")
        print(f"[API Monitor] API Key present: {bool(API_KEY)} (Length: {len(API_KEY)})")
    
    def get_pending_posts(self) -> List[Dict]:
        """Check API for pending posts. Returns list or empty list."""
        url = f"{self.dashboard_url}/api/queue/gui/pending"
        
        try:
            print(f"[API Monitor] Checking: {url}")
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                posts = response.json()
                print(f"[API Monitor] Found {len(posts)} pending post(s)")
                return posts
            
            elif response.status_code == 204:
                print("[API Monitor] No pending posts (204 No Content)")
                return []
            
            elif response.status_code == 401:
                print(f"[API Monitor] Authentication FAILED (401). Check API_KEY.")
                return []
                
            else:
                print(f"[API Monitor] Unexpected status: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[API Monitor] Error checking API: {e}")
            return []
    
    def report_success(self, post_id: str, platform_post_id: str = None):
        """Report successful posting to API."""
        url = f"{self.dashboard_url}/api/queue/gui/complete"
        try:
            print(f"[API Monitor] Reporting success for {post_id}")
            self.session.post(url, json={
                "id": post_id,
                "platform_post_id": platform_post_id
            })
        except Exception as e:
            print(f"[API Monitor] Error reporting success: {e}")
    
    def report_failure(self, post_id: str, error: str, retry: bool = True):
        """Report failed posting to API."""
        url = f"{self.dashboard_url}/api/queue/gui/failed"
        try:
            print(f"[API Monitor] Reporting failure for {post_id}: {error}")
            self.session.post(url, json={
                "id": post_id,
                "error": error,
                "retry": retry
            })
        except Exception as e:
            print(f"[API Monitor] Error reporting failure: {e}")
