# Tabs

New tabs can change the active CDP session. After opening or switching tabs,
call `page_info()` and capture a screenshot before continuing the workflow.

Use `new_tab(url)` for first navigation so existing user or sandbox state is not
clobbered. If the active tab looks stale or internal, use `ensure_real_tab()`.
