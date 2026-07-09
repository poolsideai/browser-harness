import base64
import subprocess
from pathlib import Path
from unittest.mock import patch

from browser_harness.recording import Recorder


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_png(path, full=False):
    Path(path).write_bytes(PNG_BYTES)
    return path


def _write_distinct_png():
    counter = {"value": 0}

    def write(path, full=False):
        counter["value"] += 1
        Path(path).write_bytes(PNG_BYTES + bytes([counter["value"]]))
        return path

    return write


def test_recorder_fails_loudly_when_too_few_frames(tmp_path):
    rec = Recorder(
        out=tmp_path / "demo.mp4",
        min_frames=3,
        screenshot_func=_write_png,
    )

    rec.start(capture=False)
    rec.snap("only-frame")
    manifest = rec.stop()

    assert manifest["ok"] is False
    assert manifest["frame_count"] == 1
    assert "too few frames" in manifest["failure_reason"]
    assert Path(manifest["manifest_path"]).exists()


def test_recorder_keeps_diagnostic_png_sequence_without_encoder(tmp_path):
    rec = Recorder(
        out=tmp_path / "demo.mp4",
        min_frames=3,
        screenshot_func=_write_distinct_png(),
    )

    with patch("browser_harness.recording.shutil.which", return_value=None), patch("browser_harness.recording._imageio_ffmpeg_exe", return_value=None):
        rec.start(capture=False)
        rec.snap("one")
        rec.snap("two")
        rec.snap("three")
        manifest = rec.stop()

    assert manifest["ok"] is True
    assert manifest["encoder"] == "png-sequence"
    assert manifest["reviewer_usable"] is False
    assert manifest["distinct_frame_count"] == 3
    assert Path(manifest["artifact_path"]).is_dir()


def test_recorder_fails_loudly_when_frames_are_duplicates(tmp_path):
    rec = Recorder(
        out=tmp_path / "demo.mp4",
        min_frames=3,
        screenshot_func=_write_png,
    )

    rec.start(capture=False)
    rec.snap("one")
    rec.snap("two")
    rec.snap("three")
    manifest = rec.stop()

    assert manifest["ok"] is False
    assert manifest["frame_count"] == 3
    assert manifest["distinct_frame_count"] == 1
    assert manifest["duplicate_frame_count"] == 2
    assert "too few distinct frames" in manifest["failure_reason"]
    assert Path(manifest["fallback_artifact_path"]).is_dir()


def test_pause_and_resume_skip_false_start_frames(tmp_path):
    rec = Recorder(
        out=tmp_path / "demo.mp4",
        min_frames=1,
        screenshot_func=_write_png,
    )

    with patch("browser_harness.recording.shutil.which", return_value=None), patch("browser_harness.recording._imageio_ffmpeg_exe", return_value=None):
        rec.start(capture=False)
        rec.pause()
        assert rec.snap("false-start") is None
        rec.resume()
        assert rec.snap("real-frame") is not None
        manifest = rec.stop()

    assert manifest["frame_count"] == 1
    assert manifest["frames"][0]["label"] == "real-frame"


def test_recorder_falls_back_to_imageio_and_marks_qualified_video_reviewer_usable(tmp_path):
    out = tmp_path / "demo.mp4"
    rec = Recorder(
        out=out,
        fps=8,
        width=1280,
        min_seconds=0.25,
        min_frames=3,
        screenshot_func=_write_distinct_png(),
    )

    def encode_with_imageio_after_system_failure(cmd, **kwargs):
        if cmd[0] == "system-ffmpeg":
            raise subprocess.CalledProcessError(1, cmd, stderr="system encoder failed")
        if cmd[0] == "imageio-ffmpeg":
            Path(cmd[-1]).write_bytes(b"encoded-by-imageio")
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(f"unexpected encoder: {cmd[0]}")

    with patch("browser_harness.recording.shutil.which", return_value="system-ffmpeg"), \
         patch("browser_harness.recording._imageio_ffmpeg_exe", return_value="imageio-ffmpeg"), \
         patch("browser_harness.recording.subprocess.run", side_effect=encode_with_imageio_after_system_failure):
        rec.start(capture=False)
        rec.snap("one")
        rec.snap("two")
        rec.snap("three")
        manifest = rec.stop()

    assert manifest["ok"] is True
    assert manifest["encoder"] == "imageio-ffmpeg"
    assert manifest["reviewer_usable"] is True
    assert manifest["failure_reason"] is None
    assert Path(manifest["artifact_path"]).read_bytes() == b"encoded-by-imageio"


def test_recorder_stops_at_max_seconds_and_finishes_without_reencoding(tmp_path):
    out = tmp_path / "demo.mp4"
    rec = Recorder(
        out=out,
        max_seconds=1,
        min_frames=1,
        screenshot_func=_write_png,
    )
    encoding_attempt = {"count": 0}

    def encode_once_per_invocation(cmd, **kwargs):
        encoding_attempt["count"] += 1
        Path(cmd[-1]).write_bytes(f"encoded-{encoding_attempt['count']}".encode())
        return subprocess.CompletedProcess(cmd, 0)

    with patch("browser_harness.recording.time.time", side_effect=[100.0, 100.0, 100.0, 101.01, 101.01]), \
         patch("browser_harness.recording.shutil.which", return_value="ffmpeg"), \
         patch("browser_harness.recording.subprocess.run", side_effect=encode_once_per_invocation):
        rec.start(capture=False)
        assert rec.snap("kept") is not None
        assert rec.snap("after-limit") is None
        manifest = rec.stop()
        artifact_before_repeat_finish = out.read_bytes()
        repeat_manifest = rec.finish()

    assert manifest["frame_count"] == 1
    assert manifest["frames"][0]["label"] == "kept"
    assert repeat_manifest == manifest
    assert out.read_bytes() == artifact_before_repeat_finish
