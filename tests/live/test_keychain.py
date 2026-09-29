"""Tests of :mod:`macos.keychain` against the real system. Skipped outside macOS."""

import uuid

import macos


def test_keychain_round_trip():
    service = "macos-tests-{}".format(uuid.uuid4())
    try:
        assert macos.keychain.get(service, "user") is None

        macos.keychain.set(service, "user", "sé cret")
        assert macos.keychain.get(service, "user") == "sé cret"

        macos.keychain.set(service, "user", "replaced")
        assert macos.keychain.get(service, "user") == "replaced"
    finally:
        assert macos.keychain.delete(service, "user") is True

    assert macos.keychain.delete(service, "user") is False
    assert macos.keychain.get(service, "user") is None


def test_keychain_accounts():
    service = "macos-tests-{}".format(uuid.uuid4())
    try:
        assert macos.keychain.accounts(service) == []
        macos.keychain.set(service, "bob", "1")
        macos.keychain.set(service, "alice", "2")
        assert macos.keychain.accounts(service) == ["alice", "bob"]
    finally:
        macos.keychain.delete(service, "bob")
        macos.keychain.delete(service, "alice")
