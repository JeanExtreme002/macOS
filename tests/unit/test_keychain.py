"""Unit tests for :mod:`macos.keychain`. They run on any platform."""

import sys

import pytest

import macos


# Outside macOS the platform guard (NotSupportedError) rightly fires first.
@pytest.mark.skipif(sys.platform != "darwin", reason="loads the Security framework")
@pytest.mark.parametrize("service, account", [("svc\0x", "alice"), ("svc", "al\0ice")])
def test_keychain_rejects_nul_characters(service, account):
    with pytest.raises(ValueError, match="NUL"):
        macos.keychain.get(service, account)
