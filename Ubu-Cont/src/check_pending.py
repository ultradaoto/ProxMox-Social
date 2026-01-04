import sys
import os

# Ensure src directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_monitor import APIMonitor

def main():
    print("--- Checking for Pending Posts ---")
    monitor = APIMonitor()
    posts = monitor.get_pending_posts()
    
    if posts:
        print("\nPENDING POSTS:")
        for post in posts:
            print(f"- ID: {post.get('id')}")
            print(f"  Platform: {post.get('platform')}")
            print(f"  Caption: {post.get('caption')[:50]}...")
    else:
        print("\nNo posts pending or error occurred.")

if __name__ == "__main__":
    main()
