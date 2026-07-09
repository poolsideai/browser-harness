import os
import subprocess
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch

import pytest

from browser_harness import run


def test_stdin_executes_code():
    stdout = StringIO()
    fake_stdin = StringIO("print('hello from stdin')")

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("sys.stdin", fake_stdin), \
         patch("sys.stdout", stdout):
        run.main()

    assert stdout.getvalue().strip() == "hello from stdin"


def test_c_flag_is_rejected():
    with patch.object(sys, "argv", ["browser-harness", "-c", "print('old path')"]), \
         patch("sys.stdin", StringIO("print('ignored')")):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("-c should be rejected")


def test_no_args_interactive_stdin_prints_usage():
    fake_stdin = StringIO("")
    fake_stdin.isatty = lambda: True

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", fake_stdin):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("interactive no-args invocation should exit with usage")


def test_no_args_empty_stdin_prints_usage():
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("")):
        try:
            run.main()
        except SystemExit as e:
            assert "browser-harness <<'PY'" in str(e)
        else:
            raise AssertionError("empty stdin should exit with usage")


def test_cloud_bootstrap_is_removed(monkeypatch):
    """Cloud bootstrap stays disabled even with the historical opt-in env."""
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.ensure_daemon") as mock_ensure:
        run.main()
    mock_ensure.assert_called_once()


def test_explicit_bu_cdp_url_still_uses_local_daemon_path(monkeypatch):
    """Explicit CDP endpoints remain supported by the daemon, without cloud bootstrap."""
    monkeypatch.setenv("BU_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.ensure_daemon") as mock_ensure:
        run.main()
    mock_ensure.assert_called_once()


def test_explicit_bu_cdp_ws_still_uses_local_daemon_path(monkeypatch):
    """Explicit WebSocket endpoints remain supported by the daemon, without cloud bootstrap."""
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/abc")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")
    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.ensure_daemon") as mock_ensure:
        run.main()
    mock_ensure.assert_called_once()


def test_cli_doctor_fix_snap_invokes_guide():
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--fix-snap"]), \
         patch("browser_harness.run.run_doctor_fix_snap", return_value=0) as m:
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 0
    m.assert_called_once()


def test_cli_doctor_rejects_unknown_flags():
    err = StringIO()
    with patch.object(sys, "argv", ["browser-harness", "doctor", "--bogus"]), patch("sys.stderr", err):
        with pytest.raises(SystemExit) as ei:
            run.main()
    assert ei.value.code == 2
    assert "usage" in err.getvalue().lower()

def test_runtime_reconfigures_stdout_and_stderr_to_utf8_in_isolated_process():
    """Unicode diagnostics must survive an ASCII inherited stream configuration."""
    repo_src = Path(__file__).resolve().parents[2] / "src"
    env = {
        **os.environ,
        "PYTHONIOENCODING": "ascii",
        "PYTHONPATH": str(repo_src),
    }
    script = (
        "import sys\n"
        "from browser_harness import run\n"
        "sys.stdout.write('stdout: café\\n')\n"
        "sys.stderr.write('stderr: naïve\\n')\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stdout == b"stdout: caf\xc3\xa9\n"
    assert completed.stderr == b"stderr: na\xc3\xafve\n"


def test_skill_command_emits_packaged_utf8_content(capsys):
    """`browser-harness skill` emits the bundled package resource without byte drift."""
    from importlib import resources

    expected = resources.files("browser_harness").joinpath("SKILL.md").read_bytes().decode("utf-8")
    with patch.object(sys, "argv", ["browser-harness", "skill"]):
        run.main()

    assert capsys.readouterr().out == expected
