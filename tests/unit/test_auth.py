import pytest

from browser_harness import auth


def test_load_auth_file_maps_invalid_utf8_to_auth_error(tmp_path):
    """A corrupt auth file must report the actionable auth failure, not leak a decoder error."""
    path = tmp_path / "auth.json"
    path.write_bytes(b'{"browser_use":{"api_key":"bad\xff"}}')

    with pytest.raises(auth.AuthError, match="auth file is not valid JSON"):
        auth.load_auth_file(path)
