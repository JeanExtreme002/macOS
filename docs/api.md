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
.. autoexception:: macos.KeychainError
.. autoexception:: macos.CommandError
```
