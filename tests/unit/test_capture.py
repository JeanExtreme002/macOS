"""Unit tests for the Camera and Microphone permissions."""

import pytest

import macos


def test_capture_permission_denied(monkeypatch):
    from macos import _capture

    monkeypatch.setattr(_capture, "request_permission", lambda media: False)

    with pytest.raises(macos.PermissionDeniedError, match="Camera permission"):
        _capture.require_permission(_capture.VIDEO)
    with pytest.raises(macos.PermissionDeniedError, match="Microphone permission"):
        _capture.require_permission(_capture.AUDIO)
