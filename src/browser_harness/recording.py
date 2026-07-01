"""Polling-based walkthrough recording for browser-harness."""

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path


class Recorder:
    """Capture a short browser walkthrough by polling screenshots.

    The recorder has no hidden browser-side background state: every frame is a
    bounded screenshot request whose result is visible in the command output or
    sidecar manifest.
    """

    def __init__(
        self,
        out="/tmp/browser-harness-recording.mp4",
        fps=8,
        width=1280,
        max_seconds=30,
        min_seconds=2.0,
        min_frames=3,
        frame_dir=None,
        screenshot_func=None,
    ):
        self.out = Path(out)
        self.fps = fps
        self.width = width
        self.max_seconds = max_seconds
        self.min_seconds = min_seconds
        self.min_frames = min_frames
        self.frame_dir = Path(frame_dir) if frame_dir else self.out.with_suffix("").parent / f"{self.out.with_suffix('').name}_frames"
        self.manifest_path = Path(f"{self.out}.json")
        self.screenshot_func = screenshot_func
        self.frames = []
        self.started_at = None
        self.finished_at = None
        self.active = False
        self.paused = False
        self._manifest = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def start(self, capture=False):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.frame_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = time.time()
        self.finished_at = None
        self.active = True
        self.paused = False
        self._manifest = None
        if capture:
            self.snap("start")
        return self

    def pause(self):
        self.paused = True
        return self

    def resume(self, capture=False):
        self.paused = False
        if capture:
            self.snap("resume")
        return self

    def snap(self, label=None):
        if not self.active:
            self.start(capture=False)
        if self.paused:
            return None
        if self.started_at and time.time() - self.started_at > self.max_seconds:
            self.active = False
            return None
        path = self.frame_dir / f"frame_{len(self.frames):06d}.png"
        self._capture(path)
        self.frames.append(
            {"path": str(path), "at": time.time(), "label": label, **_file_fingerprint(path)}
        )
        return str(path)

    def beat(self, seconds=1.0):
        deadline = time.time() + seconds
        interval = 1.0 / max(float(self.fps), 0.1)
        while time.time() < deadline and self.active:
            self.snap()
            time.sleep(interval)
        return self

    def stop(self):
        self.active = False
        return self.finish()

    def finish(self):
        if self._manifest is not None:
            return self._manifest
        self.finished_at = self.finished_at or time.time()
        manifest = self._base_manifest()
        if len(self.frames) < self.min_frames:
            manifest.update(
                ok=False,
                reviewer_usable=False,
                failure_reason=f"too few frames: {len(self.frames)} < {self.min_frames}",
            )
            return self._write_manifest(manifest)

        if manifest["distinct_frame_count"] < self.min_frames:
            manifest.update(
                ok=False,
                reviewer_usable=False,
                failure_reason=f"too few distinct frames: {manifest['distinct_frame_count']} < {self.min_frames}",
                fallback_artifact_path=str(self.frame_dir),
            )
            return self._write_manifest(manifest)

        encoder, artifact, error = self._encode()
        manifest.update(
            ok=artifact is not None,
            encoder=encoder,
            artifact_path=str(artifact) if artifact else None,
            failure_reason=error,
        )
        manifest["reviewer_usable"] = self._reviewer_usable(manifest)
        if not artifact:
            manifest["fallback_artifact_path"] = str(self.frame_dir)
        return self._write_manifest(manifest)

    def _capture(self, path):
        capture = self.screenshot_func
        if capture is None:
            from helpers import capture_screenshot

            capture = capture_screenshot
        try:
            capture(str(path), full=False)
        except TypeError:
            capture(str(path))

    def _base_manifest(self):
        wall_duration = 0.0
        if self.started_at:
            wall_duration = (self.finished_at or time.time()) - self.started_at
        encoded_duration = len(self.frames) / max(float(self.fps), 0.1)
        frame_hashes = [frame.get("sha256") for frame in self.frames if frame.get("sha256")]
        distinct_frame_count = len(set(frame_hashes))
        return {
            "ok": False,
            "reviewer_usable": False,
            "out": str(self.out),
            "manifest_path": str(self.manifest_path),
            "frame_dir": str(self.frame_dir),
            "frame_count": len(self.frames),
            "distinct_frame_count": distinct_frame_count,
            "duplicate_frame_count": max(0, len(frame_hashes) - distinct_frame_count),
            "fps": self.fps,
            "width": self.width,
            "duration_seconds": round(encoded_duration, 3),
            "wall_duration_seconds": round(wall_duration, 3),
            "min_seconds": self.min_seconds,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "frames": self.frames,
            "quality_bar": {
                "reviewer_demo": "H.264 MP4, >=8 fps, about 1280 px wide, 2-30s, legible UI text, >=3 visible states",
                "diagnostic": "3 fps PNG sequence is acceptable when it preserves enough state to debug",
            },
        }

    def _encode(self):
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            ok, err = self._run_ffmpeg(system_ffmpeg)
            if ok:
                return "ffmpeg", self.out, None
        else:
            err = "ffmpeg not found"

        imageio_ffmpeg = _imageio_ffmpeg_exe()
        if imageio_ffmpeg:
            ok, err = self._run_ffmpeg(imageio_ffmpeg)
            if ok:
                return "imageio-ffmpeg", self.out, None

        return "png-sequence", self.frame_dir, err

    def _run_ffmpeg(self, exe):
        pattern = str(self.frame_dir / "frame_%06d.png")
        scale = f"scale=min({int(self.width)}\\,iw):-2:flags=lanczos,format=yuv420p"
        cmd = [
            exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(self.fps),
            "-i",
            pattern,
            "-vf",
            scale,
            "-movflags",
            "+faststart",
            str(self.out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, None
        except Exception as exc:
            stderr = getattr(exc, "stderr", "") or str(exc)
            return False, stderr.strip()

    def _reviewer_usable(self, manifest):
        return (
            manifest.get("ok")
            and manifest.get("encoder") in {"ffmpeg", "imageio-ffmpeg"}
            and manifest["frame_count"] >= self.min_frames
            and manifest["distinct_frame_count"] >= self.min_frames
            and self.fps >= 8
            and self.width >= 1200
            and manifest["duration_seconds"] >= self.min_seconds
            and manifest["duration_seconds"] <= 30
        )

    def _write_manifest(self, manifest):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        self._manifest = manifest
        return manifest


def _imageio_ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _file_fingerprint(path):
    try:
        data = Path(path).read_bytes()
    except OSError:
        return {"sha256": None, "bytes": None}
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
