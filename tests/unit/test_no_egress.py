import os
import subprocess
import sys
import urllib.parse
import urllib.request
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from browser_harness import run
from browser_harness import telemetry


DENIED_HOSTS = {
    "api.browser-use.com",
    "eu.i.posthog.com",
    "pypi.org",
}


def _host_from_url(url):
    if isinstance(url, urllib.request.Request):
        return url.host
    return urllib.parse.urlparse(str(url)).hostname


@pytest.fixture
def deny_phone_home(monkeypatch):
    seen = []

    def guarded_open(url, *args, **kwargs):
        hosts = set(DENIED_HOSTS)
        hosts.add(urllib.parse.urlparse(os.environ.get("BH_POSTHOG_HOST", "")).hostname)
        hosts.add(urllib.parse.urlparse(os.environ.get("BROWSER_USE_CLOUD_API_URL", "")).hostname)
        hosts.discard(None)
        host = _host_from_url(url)
        seen.append(host)
        if host in hosts:
            raise AssertionError(f"unexpected phone-home to {host}")
        return SimpleNamespace(read=lambda: b"{}", close=lambda: None, headers={})

    monkeypatch.setattr(urllib.request, "urlopen", guarded_open)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda self, fullurl, *a, **kw: guarded_open(fullurl, *a, **kw))
    return seen


def test_telemetry_disabled_in_clean_process():
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "BH_TELEMETRY": "1",
        "BROWSER_HARNESS_TELEMETRY": "1",
    }
    code = "from browser_harness import telemetry; print(telemetry.is_enabled())"
    result = subprocess.run([sys.executable, "-c", code], cwd=os.getcwd(), env=env, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "False"


def test_trivial_script_and_cli_dispatch_do_not_phone_home(monkeypatch, deny_phone_home):
    monkeypatch.setenv("BH_POSTHOG_HOST", "https://eu.i.posthog.com")
    monkeypatch.setenv("BROWSER_USE_CLOUD_API_URL", "https://api.browser-use.com")
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")

    cases = [
        (["browser-harness"], {"stdin": "print('ok')", "patch": "browser_harness.run.ensure_daemon", "return": None}),
        (["browser-harness", "--version"], {"patch": "browser_harness.run._version", "return": "0.test"}),
        (["browser-harness", "--doctor"], {"patch": "browser_harness.run.run_doctor", "return": 0, "exit": 0}),
        (["browser-harness", "doctor"], {"patch": "browser_harness.run.run_doctor", "return": 0, "exit": 0}),
        (["browser-harness", "doctor", "--fix-snap"], {"patch": "browser_harness.run.run_doctor_fix_snap", "return": 0, "exit": 0}),
        (["browser-harness", "skill"], {}),
        (["browser-harness", "--reload"], {"patch": "browser_harness.run.restart_daemon", "return": None}),
        (["browser-harness", "--update", "-y"], {"patch": "browser_harness.run.run_update", "return": 0, "exit": 0}),
    ]

    for argv, cfg in cases:
        stdin = StringIO(cfg.get("stdin", ""))
        stdout = StringIO()
        context = patch(cfg["patch"], return_value=cfg["return"]) if "patch" in cfg else patch("sys.stdout", stdout)
        with patch.object(sys, "argv", argv), patch("sys.stdin", stdin), patch("sys.stdout", stdout), context:
            if "exit" in cfg:
                with pytest.raises(SystemExit) as exc:
                    run.main()
                assert exc.value.code == cfg["exit"]
            else:
                run.main()

    assert not any(host in DENIED_HOSTS for host in deny_phone_home)


def test_cloud_autospawn_cannot_call_remote_daemon(monkeypatch, deny_phone_home):
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setenv("BU_AUTOSPAWN", "1")

    with patch.object(sys, "argv", ["browser-harness"]), \
         patch("sys.stdin", StringIO("x = 1")), \
         patch("browser_harness.run.ensure_daemon"), \
         patch("browser_harness.admin.start_remote_daemon", side_effect=AssertionError("cloud bootstrap called")):
        run.main()


def test_cloud_and_auth_are_not_public_cli_or_script_surface():
    assert telemetry.is_enabled() is False
    assert not hasattr(run, "start_remote_daemon")
    assert not hasattr(run, "stop_remote_daemon")
    assert not hasattr(run, "sync_local_profile")
    assert not hasattr(run, "list_cloud_profiles")
    assert "auth " not in run.HELP
    assert "telemetry " not in run.HELP
