# Recording

Screenshots are cheaper and sufficient for static proof. Record only when the
thing being proven is temporal: a multi-step flow, motion, timing, an animation,
or a demo where the reviewer needs to see the sequence.

## Design Axiom

Use polling only. The recorder must not rely on asynchronous browser-side state
that the agent cannot inspect from the last command's return. Each frame is a
bounded `capture_screenshot()` request, and the result is summarized in a JSON
manifest beside the artifact.

## Reviewer Versus Diagnostic Captures

Reviewer-facing demos need a higher bar:

- H.264 MP4 output
- at least 8 fps
- about 1280 px wide
- 2-30 seconds unnarrated
- legible UI text
- at least three distinct visible states

Diagnostic captures can be lighter:

- 3 fps is acceptable
- a PNG sequence is acceptable if MP4 encoding is unavailable
- the artifact only needs to preserve enough state to debug the failure

## Workflow

Recording is a four-stage loop: **explore → dry-run → record → inspect**. Skip
any stage and the recording usually fails or shows nothing useful. The example
below maps 1:1 to the stages.

Browser-harness only executes code through `-c`. For longer recording scripts,
it is fine to draft a file first, but run it as
`browser-harness -c "$(cat /tmp/record_demo.py)"`, not
`browser-harness /tmp/record_demo.py`.

### 1. Explore — figure out what the demo should show

Before opening `Recorder`, navigate the page manually and pick the action
sequence the demo will reproduce. Capture a screenshot, read it, decide on
click targets and expected state transitions.

```python
new_tab(preview_url); wait_for_load(); wait(2)
capture_screenshot("/tmp/explore_initial.png", full=False)
print(page_info())
# Read /tmp/explore_initial.png — pick click targets, decide the sequence.
```

### 2. Dry-run — prove the action sequence works without recording

Run the exact action sequence with `capture_screenshot` between every action.
Confirm the screenshots show what you expect: the page is authenticated,
routed, populated; clicks land on the right targets; state transitions look
right. Empty body text, blank/white screenshots, unchanged screenshots, or
missing expected DOM state means the dry-run failed — fix waits, auth,
routing, or selectors before moving on.

```python
capture_screenshot("/tmp/dry_1.png", full=False)
click_at_xy(x1, y1); wait(0.5)
capture_screenshot("/tmp/dry_2.png", full=False)
type_text("forge"); wait(0.5)
capture_screenshot("/tmp/dry_3.png", full=False)
# Iterate until /tmp/dry_*.png show the demo you want.
```

### 3. Record — same action shape, wrapped in `Recorder`

Open `Recorder` *after* the page is verifiably ready (re-navigate if needed),
then snap once after every meaningful action. Do not snap-then-wait-then-snap
on a static page; `Recorder` is polling-based and identical-page snaps are
rejected as duplicates by the acceptance check.

```python
new_tab(preview_url); wait_for_load(); wait(2)
with Recorder("/tmp/evidence/walkthrough.mp4", fps=8, width=1280) as rec:
    rec.snap("loaded")
    click_at_xy(x1, y1); wait(0.5)
    rec.snap("opened_panel")
    type_text("forge"); wait(0.5)
    rec.snap("filtered")
manifest = rec.finish()
```

### 4. Inspect — read the manifest, retry if it failed

```python
print(manifest["ok"], manifest["reviewer_usable"], manifest.get("failure_reason"))
print(f"distinct frames: {manifest['distinct_frame_count']}")
```

If `reviewer_usable` is false, follow the retry taxonomy below and re-record.
Do not present a failed recording as evidence even if a file exists.

## Mechanics

`Recorder` is polling-based, not a hidden background screen recorder. It only
captures frames when you explicitly call `rec.snap()` or `rec.beat()`. A few
sparse `snap()` calls produce a keyframe-style MP4, not a real-time recording.

Use `rec.beat(seconds)` *during* a known animation or loading window — for
example while a spinner resolves or an animation plays. Do not use it as a
finalizer on a static page; that just produces duplicate frames the
acceptance check will reject.

Use `rec.pause()` before false starts or setup clicks you do not want in the
demo, and `rec.resume()` once the page is ready again.

`Recorder.start()` defaults to `capture=False` — no baseline frame is taken
on `__enter__`. Frame 0 is your first explicit `snap()`. Pass
`capture=True` only if you need a baseline (rare, e.g., recording a reload
where the pre-reload state is meaningful).

## Acceptance

Read the manifest after recording:

```python
print(manifest["ok"], manifest["reviewer_usable"], manifest.get("failure_reason"))
print(manifest["artifact_path"])
```

If `frame_count < 3`, the recording failed. Do not present it as reviewer
evidence even if a file exists.

If `distinct_frame_count < 3` or `duplicate_frame_count` shows most frames are
the same, the recording failed. Do not present blank or repeated-frame videos as
reviewer evidence.

`duration_seconds` is the encoded artifact duration and must be long enough to
read. `wall_duration_seconds` is how long the script spent between recorder
start and finish. If the wall time is long but encoded duration is tiny, the
script did not sample enough frames; add `rec.beat()` during waits or actions
and dry-run again.

If `reviewer_usable` is false because the encoder fell back to a PNG sequence,
use it only as diagnostic evidence unless the user explicitly accepts that
format.

## Actionable Retry Taxonomy

- Selector or readiness timing: add a stronger wait/assertion, dry-run again,
  then re-record.
- Cookie banner or one-time modal: dismiss it, verify the clean state, then
  re-record.
- Expired auth: fix auth, verify the authenticated page with a screenshot, then
  re-record.
- CAPTCHA or login wall needing human credentials: stop and escalate.
- Backend or recorder architecture failure: preserve artifacts and stop clearly;
  do not loop on the same broken recording backend.

## Interaction Footguns

- Dialogs can pause the page's JS thread. Resolve the dialog before recording
  the flow unless the dialog itself is the demo.
- New tabs can detach or change the active CDP session. Call `page_info()` and
  capture a screenshot after tab changes before continuing the recording.
- Downloads produce separate browser events and filesystem artifacts. Record the
  click if useful, but still attach the downloaded file or event evidence.
- Auth/profile changes should be verified before recording. Do not record a
  login wall unless the login wall is the behavior being demonstrated.
