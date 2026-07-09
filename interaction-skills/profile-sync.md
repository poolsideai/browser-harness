# Profile Sync Removed

This fork excludes Browser Use Cloud and remote profile sync. Do not call
`list_cloud_profiles()`, `sync_local_profile()`, `start_remote_daemon()`, or
`stop_remote_daemon()`; they are intentionally not available through the
browser-harness CLI/script surface.

Use a local Chrome profile or an explicit CDP endpoint instead:

```bash
BU_CDP_URL=http://127.0.0.1:9222 browser-harness <<'PY'
print(page_info())
PY
```
