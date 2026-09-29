"""Unit tests for :mod:`macos.keyboard`. They run on any platform."""

import pytest

import macos


def test_press_holds_the_modifiers_around_the_key(fake_events):
    macos.keyboard.press("cmd+shift+c")

    keys = [(event["code"], event["down"], event["flags"]) for event in fake_events.posted]
    cmd, shift = 1 << 20, 1 << 17
    assert keys == [
        (55, True, cmd),
        (56, True, cmd | shift),
        (8, True, cmd | shift),
        (8, False, cmd | shift),
        (56, False, cmd),
        (55, False, 0),
    ]


def test_press_a_modifier_alone_sets_its_flag(fake_events):
    macos.keyboard.press("shift")
    macos.keyboard.press("cmd+option")

    keys = [(event["code"], event["down"], event["flags"]) for event in fake_events.posted]
    shift, cmd, option = 1 << 17, 1 << 20, 1 << 19
    assert keys == [
        (56, True, shift),
        (56, False, 0),
        (55, True, cmd),
        (58, True, cmd | option),
        (58, False, cmd),
        (55, False, 0),
    ]


def test_press_adds_shift_for_shifted_characters(fake_events):
    macos.keyboard.press("cmd++")
    macos.keyboard.press("C")  # letters are keys: no Shift

    codes = [event["code"] for event in fake_events.posted if event["down"]]
    assert codes == [55, 56, 24, 8]


def test_type_sends_text_in_pieces_and_presses_enter_and_tab(fake_events):
    macos.keyboard.type("héllo 😀\n\tok")

    typed = [(event["code"], event["text"]) for event in fake_events.posted if event["down"]]
    assert typed == [(0, "héllo 😀"), (36, None), (48, None), (0, "ok")]
    assert [event["text"] for event in fake_events.posted if not event["down"]] == ["héllo 😀", None, None, "ok"]


def test_type_one_character_at_a_time_with_an_interval(fake_events, monkeypatch):
    monkeypatch.setattr(macos.keyboard.time, "sleep", lambda seconds: None)

    macos.keyboard.type("a😀", interval=0.01)

    assert [event["text"] for event in fake_events.posted if event["down"]] == ["a", "😀"]


def test_typing_splits_long_text_without_breaking_characters():
    pieces = macos.keyboard._chunks("ab😀" * 10, 5)

    assert "".join(pieces) == "ab😀" * 10
    assert all(len(piece.encode("utf-16-le")) // 2 <= 5 for piece in pieces)


def test_events_need_the_accessibility_permission(fake_events, monkeypatch):
    from macos import _events

    monkeypatch.setattr(_events, "has_permission", lambda: False)

    for call in (lambda: macos.keyboard.type("x"), lambda: macos.mouse.click(), lambda: macos.mouse.scroll(1)):
        with pytest.raises(macos.PermissionDeniedError, match="Accessibility"):
            call()
    assert fake_events.posted == []


def test_hold_keeps_modifiers_down_for_clicks_and_keys(fake_events):
    shift, cmd = 1 << 17, 1 << 20

    with macos.keyboard.hold("shift"):
        macos.mouse.click(5, 5)
        with macos.keyboard.hold("cmd"):
            macos.keyboard.press("c")

    posted = [(event["kind"], event.get("code"), event.get("down"), event["flags"]) for event in fake_events.posted]
    assert posted == [
        ("key", 56, True, shift),
        (5, None, None, shift),  # the click and its move carry Shift
        (1, None, None, shift),
        (2, None, None, shift),
        ("key", 55, True, shift | cmd),
        ("key", 8, True, shift | cmd),
        ("key", 8, False, shift | cmd),
        ("key", 55, False, shift),
        ("key", 56, False, 0),
    ]
    assert macos._events.HELD == []


def test_hold_releases_the_keys_when_the_block_fails(fake_events):
    with pytest.raises(RuntimeError):
        with macos.keyboard.hold("cmd+shift"):
            raise RuntimeError("boom")

    released = [(event["code"], event["flags"]) for event in fake_events.posted if not event["down"]]
    assert released == [(56, 1 << 20), (55, 0)]
    assert macos._events.HELD == []


def test_shortcuts_off_the_main_thread_use_a_us_keyboard():
    import threading

    parsed = []
    worker = threading.Thread(target=lambda: parsed.extend(macos.keyboard._parse(keys) for keys in ("cmd+plus", "?", "a")))
    worker.start()
    worker.join()

    cmd = [(1 << 20, 55)]
    assert parsed == [(cmd, 24, True), ([], 44, True), ([], 0, False)]  # Shift+= types "+"


def test_caps_lock(fake_events):
    assert macos.keyboard.caps_lock() is False
    fake_events.flags_state = (1 << 16) | (1 << 17)  # Caps Lock and Shift
    assert macos.keyboard.caps_lock() is True


def test_keyboard_argument_checks():
    with pytest.raises(ValueError, match="0.0 to 1.0"):
        macos.keyboard.set_brightness(1.5)
    with pytest.raises(ValueError, match="interval"):
        macos.keyboard.type("x", interval=-1)
    with pytest.raises(ValueError, match="times"):
        macos.keyboard.press("enter", times=0)
    with pytest.raises(ValueError, match="needs a key"):
        macos.keyboard.press("  ")
    with pytest.raises(ValueError, match="not a modifier"):
        macos.keyboard.press("hyper+c")
    with pytest.raises(ValueError, match="no key after"):
        macos.keyboard.press("cmd+")
    with pytest.raises(ValueError, match="unknown key"):
        macos.keyboard.press("cmd+launch")
    with pytest.raises(ValueError, match="at least one key"):
        macos.keyboard.hold().__enter__()


def test_key_press_shortcut():
    key = macos.keyboard.KeyPress(key="k", modifiers=("cmd", "shift"), text="K", code=40, repeat=False)

    assert key.shortcut == "cmd+shift+k"
    assert macos.keyboard.KeyPress("enter", (), "", 36, False).shortcut == "enter"
    assert macos.keyboard._KEY_NAMES[36] == "enter" and macos.keyboard._KEY_NAMES[51] == "delete"
