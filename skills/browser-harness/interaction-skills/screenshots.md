# Screenshots

Use screenshots as the default browser observation loop.

```bash
browser-harness -c 'capture_screenshot("/tmp/shot.png"); print(page_info())'
```

For reviewer artifacts, save screenshots under `/tmp/evidence`. Use
`full=True` for reviewer-facing full-page screenshots and `full=False` for
analysis screenshots that should match the visible viewport.

After every meaningful browser action, capture or inspect visible state before
assuming it worked.
