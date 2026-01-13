# Reporter API Fix - Instagram Support

## What Was Fixed

### 1. **reporter.py** - Correct API Payload Format
All API calls now send the correct payload format per GUI-QUEUE-API.md:

**Success:**
```json
{
  "id": "post-uuid",
  "platform_post_id": "optional_url"
}
```

**Failure:**
```json
{
  "id": "post-uuid",
  "error": "[Step: workflow_selection] Error message",
  "retry": true,
  "screenshot": null
}
```

**Processing:**
```json
{
  "id": "post-uuid",
  "status": "processing"
}
```

### 2. **fetcher.py** - Platform String Handling
Now handles platform variations like:
- `instagram_vagus` → `instagram`
- `instagram_ultra` → `instagram`
- `facebook_personal` → `facebook`

### 3. **orchestrator.py** - Instagram Workflow Support
- Instagram workflow is now initialized and ready
- Added debug logging for platform matching issues

## How to Apply These Fixes

### On Ubuntu Server (ubuntu-brain):

```bash
# 1. Navigate to the project
cd ~/ProxMox/Ubu-Cont

# 2. Clean Python cache (IMPORTANT!)
python3 cleanup_cache.py

# 3. Restart the service
sudo systemctl restart ubuntu-brain

# Or if running with PM2:
pm2 restart ubuntu-brain

# 4. Check logs
sudo journalctl -u ubuntu-brain -f
# Or for PM2:
pm2 logs ubuntu-brain
```

### Verify It's Working

The logs should now show:
```
✓ Reported SUCCESS for post abc-123
✗ Reported FAILURE for post abc-123: [Step: workflow_selection] Error
⏳ Reported PROCESSING for post abc-123
```

Instead of:
```
[GUI FAILED] Schema Error: Missing id
```

## Testing Instagram Posts

1. Create an Instagram post via your dashboard
2. Watch the logs - you should see:
   ```
   PROCESSING POST: abc-123
   Platform: instagram
   Platform value: instagram
   Available workflows: [<Platform.SKOOL: 'skool'>, <Platform.INSTAGRAM: 'instagram'>]
   ```

3. The Instagram workflow will execute through 15 OSP color-coded steps

## Troubleshooting

### Still Getting "Schema Error: Missing id"?
- **Cause:** Python cache not cleared or service not restarted
- **Fix:** Run `python3 cleanup_cache.py` and restart the service

### Still Getting "Unsupported platform: instagram"?
- **Cause:** Old code still loaded or Instagram workflow not initialized
- **Fix:** Check the debug logs showing `Available workflows` - Instagram should be in the list
- **Verify:** Ensure `src/workflows/instagram_workflow.py` exists

### Instagram Workflow Not Executing?
- **Cause:** Windows 10 OSP panel may not be visible
- **Fix:** Ensure Chrome with OSP panel is open on Windows 10
- **Check:** VNC connection to Windows 10 is working

## Files Modified

1. `src/reporter.py` - Fixed all API payload formats
2. `src/fetcher.py` - Added platform string parsing
3. `src/orchestrator.py` - Added Instagram workflow + debug logging
4. `cleanup_cache.py` - New utility to clear Python cache

## Next Steps

When adding Facebook support:
1. Create `src/workflows/facebook_workflow.py` (copy from Instagram template)
2. Update `orchestrator.py` to initialize Facebook workflow
3. That's it! The fetcher and reporter already support it.
