# Keyboard

{mod}`macos.keyboard` types text and presses keys and shortcuts in the app in
front, as if typed on the keyboard. It also switches keyboard layouts and
controls the keyboard backlight.

```python
import macos

macos.keyboard.type("Hello, world!")
macos.keyboard.press("enter")
macos.keyboard.press("cmd+shift+4")   # the screenshot shortcut
```

Typing and pressing keys need the [Accessibility permission](permissions.md#accessibility).
Layouts and the backlight need none.

## Typing text

{func}`~macos.keyboard.type` types any text, accents and emoji included,
whatever the keyboard layout. New lines press Enter and tabs press Tab:

```python
macos.keyboard.type("Olá! 👋\nSecond line")
```

Some apps (remote desktops, games, web forms with autocomplete) lose
keystrokes that arrive too fast. `interval` sets a pause between characters,
in seconds:

```python
macos.keyboard.type("slow and steady", interval=0.05)
```

## Keys and shortcuts

{func}`~macos.keyboard.press` presses a key, or a shortcut with modifiers
joined by `+`:

```python
macos.keyboard.press("cmd+c")          # copy
macos.keyboard.press("cmd+tab")        # switch apps
macos.keyboard.press("down", times=3)
macos.keyboard.press("cmd+plus")       # zoom in
```

- **Modifiers**: `cmd`, `shift`, `option` (or `alt`), `ctrl` and `fn`.
- **Characters** are found on the current keyboard layout, so `"cmd+z"` is
  undo on an AZERTY or Dvorak keyboard too. Letters work in either case:
  add `shift` for Shift.
- **Names**: `enter`, `tab`, `space`, `delete` (backspace), `forward_delete`,
  `escape`, `left`, `right`, `up`, `down`, `home`, `end`, `page_up`,
  `page_down`, `f1` to `f20`, `plus` and `minus`.

The keystrokes go to the app in front: bring one forward first with
{meth}`App.activate() <macos.apps.App.activate>` or {func}`macos.apps.open`.

```python
macos.apps.open("TextEdit")
macos.keyboard.press("cmd+n")
macos.keyboard.type("Written by Python")
```

## Holding keys

{func}`~macos.keyboard.hold` keeps keys down while a `with` block runs, for
Shift-clicks, Cmd-clicks, Option-drags, or a key held in a game:

```python
with macos.keyboard.hold("shift"):
    macos.mouse.click(100, 200)
    macos.mouse.click(100, 400)   # selects everything in between

with macos.keyboard.hold("cmd", "option"):
    macos.mouse.drag(600, 300)
```

Keys are written as for {func}`~macos.keyboard.press`. They are released at
the end of the block, even when it raises.

## Watching keys

{func}`~macos.keyboard.watch` yields a {class}`~macos.keyboard.KeyPress` for each
key pressed, in any app. Its `shortcut` is written as {func}`~macos.keyboard.press`
takes it:

```python
for key in macos.keyboard.watch():
    print(key.shortcut, repr(key.text))   # cmd+shift+k 'K'
```

It only listens: the keys still reach the app in front. To take a shortcut for
yourself, see [Hotkeys](hotkeys.md). It needs the [Input Monitoring
permission](permissions.md#input-monitoring), and macOS hides what's typed in
password fields.

## Caps Lock

```python
macos.keyboard.caps_lock()   # True when on
```

Handy to warn before typing a password. It needs no permission.

## Keyboard layouts

```python
macos.keyboard.layouts()          # ['ABC', 'Brazilian']
macos.keyboard.layout()           # 'Brazilian'
macos.keyboard.set_layout("ABC")
```

{func}`~macos.keyboard.layouts` lists the layouts and input methods enabled in
the menu bar's input menu; add more in System Settings › Keyboard › Text
Input. {func}`~macos.keyboard.set_layout` takes a name from that list, its
identifier (such as `'com.apple.keylayout.ABC'`), or part of its name when
only one layout matches.

## Keyboard backlight

On Macs with a backlit keyboard:

```python
macos.keyboard.brightness()                # 0.4, from 0.0 (off) to 1.0
macos.keyboard.set_brightness(1.0)
macos.keyboard.auto_brightness()           # True: follows the room's light
macos.keyboard.set_auto_brightness(False)
```

With automatic brightness on, macOS keeps adjusting the backlight after
{func}`~macos.keyboard.set_brightness`. On a Mac without a backlit keyboard
these functions raise {class}`~macos.NotSupportedError`.

They use a private macOS framework, since there's no public one.

## Reference

- {func}`macos.keyboard.type`
- {func}`macos.keyboard.press`
- {func}`macos.keyboard.hold`
- {func}`macos.keyboard.caps_lock`
- {func}`macos.keyboard.layouts`
- {func}`macos.keyboard.layout`
- {func}`macos.keyboard.set_layout`
- {func}`macos.keyboard.has_permission`
- {func}`macos.keyboard.request_permission`
- {func}`macos.keyboard.brightness`
- {func}`macos.keyboard.set_brightness`
- {func}`macos.keyboard.auto_brightness`
- {func}`macos.keyboard.set_auto_brightness`
- {func}`macos.keyboard.watch`
- {class}`macos.keyboard.KeyPress`
