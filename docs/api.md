# API

The complete public API, generated from the source code. The feature pages
explain how to use each part.

## Top-level functions

```{eval-rst}
.. autofunction:: macos.open
.. autofunction:: macos.open_with
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
.. autofunction:: macos.clipboard.wait_for_change
.. autofunction:: macos.clipboard.copy_files
.. autofunction:: macos.clipboard.paste_files
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
.. autofunction:: macos.appearance.accent_color
.. autofunction:: macos.appearance.wait_for_change
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
.. autofunction:: macos.apps.default_for
.. autofunction:: macos.apps.default_browser
```

## macos.keychain

```{eval-rst}
.. module:: macos.keychain

.. autofunction:: macos.keychain.set
.. autofunction:: macos.keychain.get
.. autofunction:: macos.keychain.delete
.. autofunction:: macos.keychain.accounts
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
.. autofunction:: macos.power.sleep
.. autofunction:: macos.power.sleep_display
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
.. autofunction:: macos.finder.thumbnail
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

## macos.vision

```{eval-rst}
.. module:: macos.vision

.. autofunction:: macos.vision.text
.. autofunction:: macos.vision.lines
.. autofunction:: macos.vision.languages
.. autoclass:: macos.vision.TextLine
.. autofunction:: macos.vision.barcodes
.. autoclass:: macos.vision.Barcode
.. autofunction:: macos.vision.classify
.. autofunction:: macos.vision.faces
.. autofunction:: macos.vision.remove_background
.. autofunction:: macos.vision.animals
.. autofunction:: macos.vision.scan_document
.. autofunction:: macos.vision.smart_crop
.. autofunction:: macos.vision.image_distance
.. autofunction:: macos.vision.duplicates
.. autofunction:: macos.vision.best_shot
.. autoclass:: macos.vision.Animal
```

## macos.image

```{eval-rst}
.. module:: macos.image

.. autofunction:: macos.image.info
.. autofunction:: macos.image.metadata
.. autofunction:: macos.image.taken_at
.. autofunction:: macos.image.location
.. autofunction:: macos.image.strip_metadata
.. autofunction:: macos.image.set_taken_at
.. autofunction:: macos.image.set_location
.. autofunction:: macos.image.convert
.. autofunction:: macos.image.resize
.. autofunction:: macos.image.crop
.. autofunction:: macos.image.rotate
.. autofunction:: macos.image.flip
.. autofunction:: macos.image.blur_faces
.. autofunction:: macos.image.dominant_colors
.. autofunction:: macos.image.qr_code
.. autoclass:: macos.image.ImageInfo
```

## macos.pdf

```{eval-rst}
.. module:: macos.pdf

.. autofunction:: macos.pdf.page_count
.. autofunction:: macos.pdf.text
.. autofunction:: macos.pdf.metadata
.. autofunction:: macos.pdf.merge
.. autofunction:: macos.pdf.extract
.. autofunction:: macos.pdf.rotate
.. autofunction:: macos.pdf.encrypt
.. autofunction:: macos.pdf.render
.. autofunction:: macos.pdf.from_images
.. autoclass:: macos.pdf.Metadata
```

## macos.language

```{eval-rst}
.. module:: macos.language

.. autofunction:: macos.language.detect
.. autofunction:: macos.language.guess
.. autofunction:: macos.language.sentiment
.. autofunction:: macos.language.similarity
.. autofunction:: macos.language.embedding
.. autofunction:: macos.language.entities
.. autofunction:: macos.language.keywords
.. autoclass:: macos.language.Entity
```

## macos.audio

```{eval-rst}
.. module:: macos.audio

.. autofunction:: macos.audio.devices
.. autofunction:: macos.audio.outputs
.. autofunction:: macos.audio.inputs
.. autofunction:: macos.audio.default_output
.. autofunction:: macos.audio.default_input
.. autofunction:: macos.audio.set_output
.. autofunction:: macos.audio.set_input
.. autoclass:: macos.audio.Device
```

## macos.sound

```{eval-rst}
.. module:: macos.sound

.. autofunction:: macos.sound.play
.. autofunction:: macos.sound.beep
.. autofunction:: macos.sound.names
```

## macos.network

```{eval-rst}
.. module:: macos.network

.. autofunction:: macos.network.is_online
.. autofunction:: macos.network.ip
.. autofunction:: macos.network.interface
.. autofunction:: macos.network.wifi_power
.. autofunction:: macos.network.set_wifi_power
```

## macos.screen

```{eval-rst}
.. module:: macos.screen

.. autofunction:: macos.screen.has_permission
.. autofunction:: macos.screen.request_permission
.. autofunction:: macos.screen.displays
.. autoclass:: macos.screen.Display
.. autofunction:: macos.screen.wallpaper
.. autofunction:: macos.screen.set_wallpaper
.. autofunction:: macos.screen.start_screensaver
```

## macos.dialog

```{eval-rst}
.. module:: macos.dialog

.. autofunction:: macos.dialog.alert
.. autofunction:: macos.dialog.confirm
.. autofunction:: macos.dialog.prompt
.. autofunction:: macos.dialog.choose
.. autofunction:: macos.dialog.choose_file
.. autofunction:: macos.dialog.choose_files
.. autofunction:: macos.dialog.choose_folder
```

## macos.system

```{eval-rst}
.. module:: macos.system

.. autofunction:: macos.system.version
.. autofunction:: macos.system.build
.. autofunction:: macos.system.model
.. autofunction:: macos.system.model_identifier
.. autofunction:: macos.system.processor
.. autofunction:: macos.system.memory
.. autofunction:: macos.system.computer_name
.. autofunction:: macos.system.uptime
.. autofunction:: macos.system.idle_time
.. autofunction:: macos.system.volumes
.. autofunction:: macos.system.eject
.. autofunction:: macos.system.fonts
.. autoclass:: macos.system.Volume
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
