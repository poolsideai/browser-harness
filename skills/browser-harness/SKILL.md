---
name: browser-harness
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the running browser in the environment.
---

# browser-harness

Direct browser control via CDP. Use this skill when a task needs browser
automation, navigation, scraping, downloads/uploads, auth validation,
interactive verification, screenshots, or demos.

## Separation Of Concerns

- The agent profile decides whether the task needs browser work.
- `evidence-gathering` decides what proof is required and when a recording is
  warranted.
- This skill explains how to drive the browser.
- `interaction-skills/recording.md` explains how to capture, inspect, retry, and
  accept recordings.

## Usage

```bash
browser-harness -c 'ensure_real_tab(); print(page_info())'
```

Helpers are pre-imported. Use `new_tab(url)` for first navigation so you do not
clobber an existing tab. Use `capture_screenshot(path, full=False)` to inspect
visible state and `click_at_xy(x, y)` for compositor-level clicks.

## Interaction Skills

Read the relevant file when you hit that mechanic:

- `interaction-skills/recording.md` for optional walkthrough recording
- `interaction-skills/screenshots.md` for visual inspection
- `interaction-skills/dialogs.md` for alerts, confirms, prompts, and beforeunload
- `interaction-skills/downloads.md` for file downloads and exported artifacts
- `interaction-skills/tabs.md` for multi-tab flows

If the task needs temporal proof such as motion, sequence, timing, or a demo
flow, read `interaction-skills/recording.md` before recording. This trigger
intentionally duplicates the evidence-gathering policy trigger so agents can
find recording guidance from either evidence planning or browser mechanics.

## What Actually Works

- Screenshot first, then decide whether to click, inspect DOM, or navigate.
- After every meaningful action, re-screenshot or assert state before assuming
  it worked.
- Use `drain_events()` to preserve browser, console, and network evidence.
- Use raw `cdp("Domain.method", ...)` when helpers do not cover the case.
- Recording uses `Recorder`, which polls screenshots. Do not use CDP screencast
  as the default recording path.

## Recording Axiom

No asynchronous background recording state the agent cannot inspect from the
last command's return. The supported v1 recording path is polling screenshots
with `Recorder`, with a manifest beside the artifact.
