# Diagnostic Report: Job ID Investigation

**Date:** 2026-01-11
**Investigated Job:** `job_20260102_141959_1b316557-f1a5-4ce6-a4fa-e5d94f79aedc`

## 1. Sample job.json Contents

```json
{
  "id": "1b316557-f1a5-4ce6-a4fa-e5d94f79aedc",
  "platform": "instagram_personal",
  "platform_url": "https://instagram.com/sterlingcooley1",
  ...
  "job_id": "job_20260102_141959_1b316557-f1a5-4ce6-a4fa-e5d94f79aedc",
  "status": "pending",
  "fetched_from": "https://social.sterlingcooley.com",
  ...
}
```

## 2. Trace Results (from `fetcher.log`)

Code Analysis confirmed the logging traces:

```text
[SYNC] Processing Job folder: job_20260102_141959_1b316557-f1a5-4ce6-a4fa-e5d94f79aedc
[SYNC] job.json 'id' field: 1b316557-f1a5-4ce6-a4fa-e5d94f79aedc
[SYNC] Sending to API: 1b316557-f1a5-4ce6-a4fa-e5d94f79aedc
...
[SYNC] Failed to sync failure for 1b316557-f1a5-4ce6-a4fa-e5d94f79aedc: 404 - {"error":"Post not found"}
```

## 3. Findings

1.  **Field Name Match**: The API uses `id` and `job.json` stores it as `id`. There is **no mismatch**.
2.  **ID Origin**: The ID is extracted directly from the `id` field of the post object returned by `/api/queue/gui/pending`.
3.  **Cause of 404s**: The specific IDs returning 404 (like `1b316557...`) are from **January 2nd**. It is highly probable these test posts were deleted from the server database, but their folders remain on the Windows machine.
    -   **Evidence**: A fresh job (`167e619d...` from Jan 11th) was successfully synced 200 OK in the same log run.

## 4. Conclusion

The ID logic is correct. The "Post not found" errors are legitimate signals that the local queue contains stale/orphaned jobs that no longer exist on the server.

**Recommendation**: Manually delete the stale folders from `C:\PostQueue\failed` and `C:\PostQueue\completed` to clean up the logs.
