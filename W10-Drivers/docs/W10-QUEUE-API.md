# OSP "SUCCESS" Button Logic & API Flow

This document explains exactly how the "SUCCESS" button works and where the code responsible for sending the API message is located.

## Executive Summary

**The "SUCCESS" button in the GUI does NOT send the API message directly.**

Instead, the system uses a **decoupled architecture**:
1.  **OSP GUI (`osp_gui.py`)**: When you click "SUCCESS", it simply **moves the job folder** from `pending` to `completed`.
2.  **Fetcher Service (`fetcher.py`)**: Monitors the `completed` folder. When it sees a file there, **IT sends the API request** and then archives the job.

---

## Part 1: The GUI Action (Input)

**File:** `W10-Drivers\SocialWorker\osp_gui.py`

When you click the "SUCCESS" button, the GUI executes `mark_complete()`. This function only performs a file system operation.

```python
# osp_gui.py

def mark_complete(self):
    """
    SUCCESS button clicked.
    Per simplified spec: Report success to API and move to next job.
    """
    log_ws("UI: SUCCESS button clicked")
    self.record_interaction({"action": "success"}, source="osp", label="Marked Success")
    
    # MOVES THE FOLDER - NO API CALL HERE
    if self.queue.complete_current():
        self.update_status("Success! Moving to next job...")
        self.refresh_queue()
        self.update_display()
```

The `complete_current()` method physically moves the directory:
```python
shutil.move(str(job.path), str(dest)) # Moves C:\PostQueue\pending\job_x -> C:\PostQueue\completed\job_x
```

---

## Part 2: The API Call (Output)

**File:** `W10-Drivers\SocialWorker\fetcher.py`

The `fetcher.py` script runs in the background (every 5 minutes by default). It finds the job in `C:\PostQueue\completed` and sends the success signal.

## 4. OSP "Success" Button Workflow (Decoupled)

The "Success" button in the OSP GUI does **not** make an API call immediately. This is a decoupled architecture designed for stability.

1.  **User Action**: User clicks "MARK SUCCESS" in `osp_gui.py`.
2.  **Local Move**: The GUI moves the job folder from `C:\PostQueue\pending\job_ID` to `C:\PostQueue\completed\job_ID`.
    *   *Note: This checks `job.json` to ensure the ID is valid.*
3.  **Polling Delay**: The background service `fetcher.py` checks the `completed` folder every **5 minutes** (or configured interval).
4.  **Sync**: When `fetcher.py` sees the folder in `completed`:
    *   It reads the **original ID** from `job.json`.
    *   It sends `POST /api/queue/gui/complete`.
    *   On success (200 OK), it moves the folder to `archived/completed`.
    *   On failure (404 Not Found), it moves the folder to `archived/completed` to prevent infinite retries (assuming the job was deleted on server).

**Takeaway:** There is a natural delay between clicking "Success" and the website updating. This is normal behavior.

**This is the exact code responsible for the API call:**

```python
# fetcher.py

# 1. Define the Endpoint
url = f"{DASHBOARD_URL}/api/queue/gui/complete"

# 2. Construct the Payload
payload = {
    'id': post_id,           # The ID from social.sterlingcooley.com
    'status': 'success',
    'completed_at': datetime.now().isoformat()
}

# 3. SEND THE REQUEST
response = safe_request('POST', url, headers=self._get_headers(), json=payload, timeout=30)
```

### Summary of Flow
1.  **User**: Clicks "SUCCESS" in `osp_gui.py`.
2.  **osp_gui.py**: Moves folder to `C:\PostQueue\completed\`.
3.  **fetcher.py**: Wakes up (or is running), sees folder in `completed`.
4.  **fetcher.py**: Reads `job.json` to get the `id`.
5.  **fetcher.py**: **Sends POST request to `https://social.sterlingcooley.com/api/queue/gui/complete`**.
6.  **fetcher.py**: Moves job to `C:\PostQueue\archived\completed`.
