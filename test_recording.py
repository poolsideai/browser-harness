import base64
from pathlib import Path
from unittest.mock import patch

from recording import Recorder


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_png(path, full=False):
    Path(path).write_bytes(PNG_BYTES)
    return path


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
        screenshot_func=_write_png,
    )

    with patch("recording.shutil.which", return_value=None), patch("recording._imageio_ffmpeg_exe", return_value=None):
        rec.start(capture=False)
        rec.snap("one")
        rec.snap("two")
        rec.snap("three")
        manifest = rec.stop()

    assert manifest["ok"] is True
    assert manifest["encoder"] == "png-sequence"
    assert manifest["reviewer_usable"] is False
    assert Path(manifest["artifact_path"]).is_dir()


def test_pause_and_resume_skip_false_start_frames(tmp_path):
    rec = Recorder(
        out=tmp_path / "demo.mp4",
        min_frames=1,
        screenshot_func=_write_png,
    )

    with patch("recording.shutil.which", return_value=None), patch("recording._imageio_ffmpeg_exe", return_value=None):
        rec.start(capture=False)
        rec.pause()
        assert rec.snap("false-start") is None
        rec.resume()
        assert rec.snap("real-frame") is not None
        manifest = rec.stop()

    assert manifest["frame_count"] == 1
    assert manifest["frames"][0]["label"] == "real-frame"
