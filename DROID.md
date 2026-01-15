# CRITICAL: Windows PowerShell Compatibility

This project runs on Windows PowerShell 5.1 which does NOT support `&&` for command chaining.

**ALWAYS use semicolons (;) instead of && when chaining commands:**
- ❌ `git add -A && git commit -m "msg"`  
- ✅ `git add -A; git commit -m "msg"`

Or use pwsh explicitly:
- ✅ `pwsh -Command "git add -A && git commit -m 'msg'"`