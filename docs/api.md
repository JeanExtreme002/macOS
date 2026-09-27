# API

The complete public API, generated from the source code. The feature pages
explain how to use each part.

## Top-level functions

```{eval-rst}
.. autofunction:: macos.notify
.. autofunction:: macos.say
.. autofunction:: macos.screenshot
```

## macos.clipboard

```{eval-rst}
.. module:: macos.clipboard

.. autofunction:: macos.clipboard.copy
.. autofunction:: macos.clipboard.paste
.. autofunction:: macos.clipboard.clear
.. autofunction:: macos.clipboard.change_count
.. autofunction:: macos.clipboard.copy_image
.. autofunction:: macos.clipboard.paste_image
.. autofunction:: macos.clipboard.has_image
```

## macos.notifications

```{eval-rst}
.. module:: macos.notifications

.. autofunction:: macos.notifications.is_allowed
```

## macos.appearance

```{eval-rst}
.. module:: macos.appearance

.. autofunction:: macos.appearance.is_dark
.. autofunction:: macos.appearance.mode
.. autofunction:: macos.appearance.is_auto
```

## macos.apps

```{eval-rst}
.. module:: macos.apps

.. autofunction:: macos.apps.running
.. autofunction:: macos.apps.frontmost
.. autofunction:: macos.apps.get
.. autofunction:: macos.apps.open
.. autoclass:: macos.apps.App
   :members: is_running, is_active, is_hidden, activate, hide, unhide, quit
```

## macos.keychain

```{eval-rst}
.. module:: macos.keychain

.. autofunction:: macos.keychain.set
.. autofunction:: macos.keychain.get
.. autofunction:: macos.keychain.delete
```

## macos.speech

```{eval-rst}
.. module:: macos.speech

.. autofunction:: macos.speech.voices
.. autoclass:: macos.speech.Voice
```

## macos.power

```{eval-rst}
.. module:: macos.power

.. autofunction:: macos.power.battery
.. autoclass:: macos.power.Battery
.. autofunction:: macos.power.keep_awake
```

## macos.shortcuts

```{eval-rst}
.. module:: macos.shortcuts

.. autofunction:: macos.shortcuts.run
.. autofunction:: macos.shortcuts.list
```

## macos.finder

```{eval-rst}
.. module:: macos.finder

.. autofunction:: macos.finder.reveal
.. autofunction:: macos.finder.trash
.. autofunction:: macos.finder.tags
.. autofunction:: macos.finder.set_tags
.. autofunction:: macos.finder.add_tags
.. autofunction:: macos.finder.remove_tags
```

## macos.volume

```{eval-rst}
.. module:: macos.volume

.. autofunction:: macos.volume.get
.. autofunction:: macos.volume.set
.. autofunction:: macos.volume.mute
.. autofunction:: macos.volume.unmute
.. autofunction:: macos.volume.is_muted
```

## macos.spotlight

```{eval-rst}
.. module:: macos.spotlight

.. autofunction:: macos.spotlight.search
.. autofunction:: macos.spotlight.search_name
.. autofunction:: macos.spotlight.metadata
```

## macos.screen

```{eval-rst}
.. module:: macos.screen

.. autofunction:: macos.screen.has_permission
.. autofunction:: macos.screen.request_permission
```

## Exceptions

```{eval-rst}
.. autoexception:: macos.MacOSError
.. autoexception:: macos.NotSupportedError
.. autoexception:: macos.PermissionDeniedError
.. autoexception:: macos.AppNotFoundError
.. autoexception:: macos.ShortcutNotFoundError
.. autoexception:: macos.KeychainError
.. autoexception:: macos.CommandError
```
