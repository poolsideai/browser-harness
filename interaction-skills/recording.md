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
- under 30 seconds unnarrated
- legible UI text
- at least three distinct visible states

Diagnostic captures can be lighter:

- 3 fps is acceptable
- a PNG sequence is acceptable if MP4 encoding is unavailable
- the artifact only needs to preserve enough state to debug the failure

## Basic Pattern

Explore the page first. Do a dry run with screenshots and assertions before
recording. When the flow is deterministic, wrap the same actions with
`Recorder`.

The dry run must prove the page is visually and semantically ready. Empty body
text, a blank/white screenshot, unchanged screenshots, or missing expected DOM
state means the dry run failed. Fix waits, auth, routing, or selectors before
recording.

Browser-harness only executes code through `-c`. For longer recording scripts,
it is fine to draft a file first, but run it as
`browser-harness -c "$(cat /tmp/record_demo.py)"`, not
`browser-harness /tmp/record_demo.py`.

```python
from pathlib import Path

Path("/tmp/evidence").mkdir(parents=True, exist_ok=True)

with Recorder("/tmp/evidence/walkthrough.mp4", fps=8, width=1280) as rec:
    new_tab("http://localhost:3000")
    wait_for_load()
    wait(1)
    rec.snap("loaded")

    type_text("forge")
    wait(1)
    rec.snap("filtered")

    # Keep the final state visible long enough to be legible.
    wait(1)
    rec.snap("final")

manifest = rec.finish()
print(manifest)
```

Use `rec.pause()` before false starts or setup clicks you do not want in the
demo, and `rec.resume(capture=True)` once the page is ready again.

`Recorder` is polling-based, not a hidden background screen recorder. It only
captures frames when you call `rec.snap()` or `rec.beat()`. A few sparse
`snap()` calls produce a keyframe-style MP4, not a real-time recording. Use
`rec.beat(seconds)` to sample a short wait period, for example while a spinner
resolves, an animation plays, or a state should remain readable.

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

`duration_seconds` is the encoded artifact duration. `wall_duration_seconds` is
how long the script spent between recorder start and finish. If the wall time is
long but encoded duration is tiny, the script did not sample enough frames; add
`rec.beat()` during waits or actions and dry-run again.

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
