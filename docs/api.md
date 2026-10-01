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
.. autofunction:: macos.clipboard.watch
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
.. autofunction:: macos.appearance.set_mode
.. autofunction:: macos.appearance.is_auto
.. autofunction:: macos.appearance.accent_color
.. autofunction:: macos.appearance.wait_for_change
.. autofunction:: macos.appearance.set_auto_mode
.. autofunction:: macos.appearance.set_accent_color
.. autodata:: macos.appearance.ACCENT_COLORS
.. autofunction:: macos.appearance.menu_bar_hidden
.. autofunction:: macos.appearance.set_hide_menu_bar
.. autofunction:: macos.appearance.scroll_bars
.. autofunction:: macos.appearance.set_scroll_bars
.. autofunction:: macos.appearance.font_smoothing
.. autofunction:: macos.appearance.set_font_smoothing
```

## macos.apps

```{eval-rst}
.. module:: macos.apps

.. autofunction:: macos.apps.running
.. autofunction:: macos.apps.frontmost
.. autofunction:: macos.apps.get
.. autofunction:: macos.apps.open
.. autofunction:: macos.apps.open_with
.. autoclass:: macos.apps.App
   :members: is_running, is_active, is_hidden, activate, hide, unhide, quit
.. autofunction:: macos.apps.default_for
.. autofunction:: macos.apps.default_browser
.. autofunction:: macos.apps.set_default_for
.. autofunction:: macos.apps.login_items
.. autofunction:: macos.apps.add_login_item
.. autofunction:: macos.apps.remove_login_item
.. autoclass:: macos.apps.LoginItem
.. autofunction:: macos.apps.install_from_dmg
.. autofunction:: macos.apps.is_quarantined
.. autofunction:: macos.apps.unquarantine
.. autoclass:: macos.apps.InstalledApp
.. autofunction:: macos.apps.installed
.. autofunction:: macos.apps.uninstall
```

## macos.keyboard

```{eval-rst}
.. module:: macos.keyboard

.. autofunction:: macos.keyboard.type
.. autofunction:: macos.keyboard.press
.. autofunction:: macos.keyboard.hold
.. autofunction:: macos.keyboard.caps_lock
.. autofunction:: macos.keyboard.watch
.. autoclass:: macos.keyboard.KeyPress
.. autofunction:: macos.keyboard.layouts
.. autofunction:: macos.keyboard.layout
.. autofunction:: macos.keyboard.set_layout
.. autofunction:: macos.keyboard.has_permission
.. autofunction:: macos.keyboard.request_permission
.. autofunction:: macos.keyboard.brightness
.. autofunction:: macos.keyboard.set_brightness
.. autofunction:: macos.keyboard.auto_brightness
.. autofunction:: macos.keyboard.set_auto_brightness
.. autofunction:: macos.keyboard.key_repeat
.. autofunction:: macos.keyboard.set_key_repeat
.. autofunction:: macos.keyboard.press_and_hold
.. autofunction:: macos.keyboard.set_press_and_hold
.. autofunction:: macos.keyboard.standard_function_keys
.. autofunction:: macos.keyboard.set_standard_function_keys
.. autofunction:: macos.keyboard.autocorrect
.. autofunction:: macos.keyboard.set_autocorrect
.. autofunction:: macos.keyboard.smart_quotes
.. autofunction:: macos.keyboard.set_smart_quotes
.. autofunction:: macos.keyboard.smart_dashes
.. autofunction:: macos.keyboard.set_smart_dashes
.. autofunction:: macos.keyboard.auto_capitalization
.. autofunction:: macos.keyboard.set_auto_capitalization
.. autofunction:: macos.keyboard.double_space_period
.. autofunction:: macos.keyboard.set_double_space_period
.. autofunction:: macos.keyboard.full_keyboard_access
.. autofunction:: macos.keyboard.set_full_keyboard_access
.. autofunction:: macos.keyboard.remap
.. autofunction:: macos.keyboard.remappings
.. autofunction:: macos.keyboard.clear_remappings
.. autofunction:: macos.keyboard.fn_key_action
.. autofunction:: macos.keyboard.set_fn_key_action
.. autofunction:: macos.keyboard.inline_predictions
.. autofunction:: macos.keyboard.set_inline_predictions
.. autofunction:: macos.keyboard.app_shortcuts
.. autofunction:: macos.keyboard.set_app_shortcut
.. autodata:: macos.keyboard.SYSTEM_SHORTCUTS
.. autofunction:: macos.keyboard.system_shortcuts
.. autofunction:: macos.keyboard.set_system_shortcut
.. autofunction:: macos.keyboard.backlight_timeout
.. autofunction:: macos.keyboard.set_backlight_timeout
```

## macos.mouse

```{eval-rst}
.. module:: macos.mouse

.. autofunction:: macos.mouse.position
.. autofunction:: macos.mouse.move
.. autofunction:: macos.mouse.click
.. autofunction:: macos.mouse.drag
.. autofunction:: macos.mouse.scroll
.. autofunction:: macos.mouse.click_text
.. autofunction:: macos.mouse.watch
.. autoclass:: macos.mouse.Click
.. autofunction:: macos.mouse.has_permission
.. autofunction:: macos.mouse.request_permission
.. autofunction:: macos.mouse.tracking_speed
.. autofunction:: macos.mouse.set_tracking_speed
.. autofunction:: macos.mouse.scroll_speed
.. autofunction:: macos.mouse.set_scroll_speed
.. autofunction:: macos.mouse.double_click_speed
.. autofunction:: macos.mouse.set_double_click_speed
.. autofunction:: macos.mouse.acceleration
.. autofunction:: macos.mouse.set_acceleration
```

## macos.windows

```{eval-rst}
.. module:: macos.windows

.. autofunction:: macos.windows.list
.. autofunction:: macos.windows.focused
.. autofunction:: macos.windows.wait_for
.. autoclass:: macos.windows.Window
   :members: title, position, size, frame, minimized, fullscreen, move, resize, set_frame, center, focus, minimize, restore, close, set_fullscreen, screenshot, snap
.. autodata:: macos.windows.LAYOUTS
   :no-value:
.. autofunction:: macos.windows.tile
.. autofunction:: macos.windows.tile_all
.. autofunction:: macos.windows.has_permission
.. autofunction:: macos.windows.request_permission
.. autofunction:: macos.windows.double_click_title_bar
.. autofunction:: macos.windows.set_double_click_title_bar
.. autofunction:: macos.windows.tiling
.. autofunction:: macos.windows.set_tiling
.. autofunction:: macos.windows.click_wallpaper_to_show_desktop
.. autofunction:: macos.windows.set_click_wallpaper_to_show_desktop
.. autofunction:: macos.windows.animations
.. autofunction:: macos.windows.set_animations
```

## macos.hotkeys

```{eval-rst}
.. module:: macos.hotkeys

.. autofunction:: macos.hotkeys.register
.. autofunction:: macos.hotkeys.unregister
.. autofunction:: macos.hotkeys.run
.. autofunction:: macos.hotkeys.stop
.. autofunction:: macos.hotkeys.wait
.. autoclass:: macos.hotkeys.Hotkey
   :members: unregister
.. autofunction:: macos.hotkeys.has_permission
.. autofunction:: macos.hotkeys.request_permission
```

## macos.events

```{eval-rst}
.. module:: macos.events

.. autofunction:: macos.events.on
.. autofunction:: macos.events.off
.. autofunction:: macos.events.run
.. autofunction:: macos.events.stop
.. autofunction:: macos.events.wait
.. autoclass:: macos.events.Event
.. autoclass:: macos.events.Handler
   :members: remove
.. autodata:: macos.events.NAMES
   :no-value:
```

## macos.schedule

```{eval-rst}
.. module:: macos.schedule

.. autofunction:: macos.schedule.add
.. autofunction:: macos.schedule.remove
.. autofunction:: macos.schedule.jobs
.. autofunction:: macos.schedule.get
.. autofunction:: macos.schedule.run_now
.. autofunction:: macos.schedule.pause
.. autofunction:: macos.schedule.resume
.. autoclass:: macos.schedule.Job
```

## macos.browser

```{eval-rst}
.. module:: macos.browser

.. autofunction:: macos.browser.tabs
.. autofunction:: macos.browser.current_tab
.. autofunction:: macos.browser.open
.. autofunction:: macos.browser.run_js
.. autoclass:: macos.browser.Tab
   :members: activate, close, reload, go
.. autodata:: macos.browser.BROWSERS
   :no-value:
```

## macos.maps

```{eval-rst}
.. module:: macos.maps

.. autofunction:: macos.maps.geocode
.. autofunction:: macos.maps.reverse_geocode
.. autoclass:: macos.maps.Place
.. autofunction:: macos.maps.open
.. autofunction:: macos.maps.directions
```

## macos.music

```{eval-rst}
.. module:: macos.music

.. autofunction:: macos.music.now_playing
.. autofunction:: macos.music.play
.. autofunction:: macos.music.pause
.. autofunction:: macos.music.play_pause
.. autofunction:: macos.music.next
.. autofunction:: macos.music.previous
.. autofunction:: macos.music.volume
.. autofunction:: macos.music.set_volume
.. autofunction:: macos.music.seek
.. autoclass:: macos.music.Track
```

## macos.auth

```{eval-rst}
.. module:: macos.auth

.. autofunction:: macos.auth.confirm
.. autofunction:: macos.auth.is_available
.. autofunction:: macos.auth.required
```

## macos.defaults

```{eval-rst}
.. module:: macos.defaults

.. autofunction:: macos.defaults.read
.. autofunction:: macos.defaults.write
.. autofunction:: macos.defaults.delete
.. autofunction:: macos.defaults.keys
.. autodata:: macos.defaults.GLOBAL
.. autofunction:: macos.defaults.restored
```

## macos.dock

```{eval-rst}
.. module:: macos.dock

.. autofunction:: macos.dock.autohide
.. autofunction:: macos.dock.set_autohide
.. autofunction:: macos.dock.size
.. autofunction:: macos.dock.set_size
.. autofunction:: macos.dock.position
.. autofunction:: macos.dock.set_position
.. autofunction:: macos.dock.apps
.. autofunction:: macos.dock.add_app
.. autofunction:: macos.dock.remove_app
.. autofunction:: macos.dock.restart
.. autoclass:: macos.dock.DockApp
.. autodata:: macos.dock.HOT_CORNER_ACTIONS
.. autofunction:: macos.dock.hot_corners
.. autofunction:: macos.dock.set_hot_corner
.. autofunction:: macos.dock.autohide_delay
.. autofunction:: macos.dock.set_autohide_delay
.. autofunction:: macos.dock.magnification
.. autofunction:: macos.dock.set_magnification
.. autofunction:: macos.dock.show_recents
.. autofunction:: macos.dock.set_show_recents
.. autofunction:: macos.dock.minimize_effect
.. autofunction:: macos.dock.set_minimize_effect
.. autofunction:: macos.dock.show_indicators
.. autofunction:: macos.dock.set_show_indicators
.. autofunction:: macos.dock.minimize_to_app
.. autofunction:: macos.dock.set_minimize_to_app
.. autofunction:: macos.dock.autohide_duration
.. autofunction:: macos.dock.set_autohide_duration
.. autofunction:: macos.dock.add_spacer
.. autofunction:: macos.dock.remove_spacers
.. autofunction:: macos.dock.auto_rearrange_spaces
.. autofunction:: macos.dock.set_auto_rearrange_spaces
.. autofunction:: macos.dock.separate_spaces_per_display
.. autofunction:: macos.dock.set_separate_spaces_per_display
.. autofunction:: macos.dock.hot_corner_modifiers
.. autofunction:: macos.dock.dim_hidden_apps
.. autofunction:: macos.dock.set_dim_hidden_apps
.. autofunction:: macos.dock.only_open_apps
.. autofunction:: macos.dock.set_only_open_apps
.. autofunction:: macos.dock.launch_animation
.. autofunction:: macos.dock.set_launch_animation
.. autofunction:: macos.dock.group_windows_by_app
.. autofunction:: macos.dock.set_group_windows_by_app
.. autofunction:: macos.dock.switch_to_space_with_app
.. autofunction:: macos.dock.set_switch_to_space_with_app
.. autoclass:: macos.dock.DockFolder
.. autofunction:: macos.dock.folders
.. autofunction:: macos.dock.add_folder
.. autofunction:: macos.dock.remove_folder
```

## macos.trackpad

```{eval-rst}
.. module:: macos.trackpad

.. autofunction:: macos.trackpad.tap_to_click
.. autofunction:: macos.trackpad.set_tap_to_click
.. autofunction:: macos.trackpad.natural_scrolling
.. autofunction:: macos.trackpad.set_natural_scrolling
.. autofunction:: macos.trackpad.tracking_speed
.. autofunction:: macos.trackpad.set_tracking_speed
.. autofunction:: macos.trackpad.three_finger_drag
.. autofunction:: macos.trackpad.set_three_finger_drag
.. autofunction:: macos.trackpad.secondary_click
.. autofunction:: macos.trackpad.set_secondary_click
.. autofunction:: macos.trackpad.click_pressure
.. autofunction:: macos.trackpad.set_click_pressure
.. autodata:: macos.trackpad.GESTURES
.. autofunction:: macos.trackpad.gestures
.. autofunction:: macos.trackpad.set_gesture
```

## macos.printer

```{eval-rst}
.. module:: macos.printer

.. autofunction:: macos.printer.printers
.. autofunction:: macos.printer.default
.. autofunction:: macos.printer.set_default
.. autofunction:: macos.printer.print_file
.. autofunction:: macos.printer.jobs
.. autofunction:: macos.printer.cancel
.. autoclass:: macos.printer.Printer
.. autoclass:: macos.printer.PrintJob
```

## macos.settings

```{eval-rst}
.. module:: macos.settings

.. autofunction:: macos.settings.export
.. autofunction:: macos.settings.apply
.. autofunction:: macos.settings.names
```

## macos.time_machine

```{eval-rst}
.. module:: macos.time_machine

.. autofunction:: macos.time_machine.destinations
.. autofunction:: macos.time_machine.backup_now
.. autofunction:: macos.time_machine.stop_backup
.. autofunction:: macos.time_machine.is_backing_up
.. autofunction:: macos.time_machine.progress
.. autofunction:: macos.time_machine.last_backup
.. autofunction:: macos.time_machine.exclude
.. autofunction:: macos.time_machine.include
.. autofunction:: macos.time_machine.is_excluded
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
.. autofunction:: macos.power.low_power_mode
.. autoclass:: macos.power.Battery
.. autofunction:: macos.power.keep_awake
.. autofunction:: macos.power.sleep_blockers
.. autoclass:: macos.power.SleepBlocker
.. autofunction:: macos.power.sleep
.. autofunction:: macos.power.sleep_display
.. autoclass:: macos.power.Adapter
.. autofunction:: macos.power.adapter
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
.. autofunction:: macos.finder.is_alias
.. autofunction:: macos.finder.resolve_alias
.. autofunction:: macos.finder.make_alias
.. autofunction:: macos.finder.watch
.. autofunction:: macos.finder.wait_for_change
.. autofunction:: macos.finder.selection
.. autofunction:: macos.finder.current_folder
.. autofunction:: macos.finder.compress
.. autofunction:: macos.finder.extract
.. autofunction:: macos.finder.quick_look
.. autofunction:: macos.finder.show_hidden_files
.. autofunction:: macos.finder.set_show_hidden_files
.. autofunction:: macos.finder.show_extensions
.. autofunction:: macos.finder.set_show_extensions
.. autofunction:: macos.finder.show_path_bar
.. autofunction:: macos.finder.set_show_path_bar
.. autofunction:: macos.finder.show_status_bar
.. autofunction:: macos.finder.set_show_status_bar
.. autofunction:: macos.finder.restart
.. autoclass:: macos.finder.Event
.. autofunction:: macos.finder.show_desktop_icons
.. autofunction:: macos.finder.set_show_desktop_icons
.. autofunction:: macos.finder.default_view
.. autofunction:: macos.finder.set_default_view
.. autofunction:: macos.finder.show_library_folder
.. autofunction:: macos.finder.set_show_library_folder
.. autofunction:: macos.finder.new_window_folder
.. autofunction:: macos.finder.set_new_window_folder
.. autofunction:: macos.finder.search_scope
.. autofunction:: macos.finder.set_search_scope
.. autofunction:: macos.finder.show_full_path_in_title
.. autofunction:: macos.finder.set_show_full_path_in_title
.. autofunction:: macos.finder.folders_first
.. autofunction:: macos.finder.set_folders_first
.. autofunction:: macos.finder.extension_change_warning
.. autofunction:: macos.finder.set_extension_change_warning
.. autofunction:: macos.finder.remove_old_trash_items
.. autofunction:: macos.finder.set_remove_old_trash_items
.. autofunction:: macos.finder.drives_on_desktop
.. autofunction:: macos.finder.set_show_drives_on_desktop
.. autofunction:: macos.finder.quit_menu
.. autofunction:: macos.finder.set_quit_menu
.. autofunction:: macos.finder.desktop_view
.. autofunction:: macos.finder.set_desktop_view
.. autofunction:: macos.finder.set_icon
.. autofunction:: macos.finder.remove_icon
.. autofunction:: macos.finder.has_custom_icon
.. autofunction:: macos.finder.largest
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
.. autofunction:: macos.vision.horizon
.. autofunction:: macos.vision.aesthetics
.. autoclass:: macos.vision.Aesthetics
.. autofunction:: macos.vision.body_pose
.. autoclass:: macos.vision.Pose
.. autofunction:: macos.vision.hand_pose
.. autoclass:: macos.vision.Hand
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
.. autofunction:: macos.image.straighten
.. autofunction:: macos.image.blur_faces
.. autofunction:: macos.image.enhance
.. autofunction:: macos.image.effect
.. autofunction:: macos.image.blur_background
.. autofunction:: macos.image.replace_background
.. autofunction:: macos.image.watermark
.. autofunction:: macos.image.contact_sheet
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
.. autofunction:: macos.pdf.watermark
.. autofunction:: macos.pdf.ocr
.. autofunction:: macos.pdf.compress
.. autofunction:: macos.pdf.grayscale
.. autofunction:: macos.pdf.render
.. autofunction:: macos.pdf.from_images
.. autoclass:: macos.pdf.Metadata
.. autoclass:: macos.pdf.FormField
.. autofunction:: macos.pdf.form_fields
.. autofunction:: macos.pdf.fill_form
.. autofunction:: macos.pdf.sign
.. autofunction:: macos.pdf.add_text
.. autoclass:: macos.pdf.Bookmark
.. autofunction:: macos.pdf.bookmarks
.. autofunction:: macos.pdf.set_bookmarks
.. autofunction:: macos.pdf.images
.. autofunction:: macos.pdf.redact
.. autoclass:: macos.pdf.Redaction
```

## macos.document

```{eval-rst}
.. module:: macos.document

.. autofunction:: macos.document.convert
.. autofunction:: macos.document.text
```

## macos.video

```{eval-rst}
.. module:: macos.video

.. autofunction:: macos.video.info
.. autofunction:: macos.video.frame
.. autofunction:: macos.video.convert
.. autofunction:: macos.video.to_gif
.. autofunction:: macos.video.frames
.. autofunction:: macos.video.trim
.. autofunction:: macos.video.concat
.. autofunction:: macos.video.speed
.. autofunction:: macos.video.rotate
.. autofunction:: macos.video.crop
.. autofunction:: macos.video.mute
.. autofunction:: macos.video.reverse
.. autofunction:: macos.video.add_audio
.. autofunction:: macos.video.add_language_track
.. autofunction:: macos.video.from_images
.. autoclass:: macos.video.VideoInfo
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
.. autofunction:: macos.audio.input_volume
.. autofunction:: macos.audio.set_input_volume
.. autofunction:: macos.audio.input_muted
.. autofunction:: macos.audio.mute_input
.. autofunction:: macos.audio.record
.. autofunction:: macos.audio.input_level
.. autofunction:: macos.audio.has_permission
.. autofunction:: macos.audio.request_permission
.. autofunction:: macos.audio.record_until_silence
.. autofunction:: macos.audio.info
.. autofunction:: macos.audio.convert
.. autofunction:: macos.audio.trim
.. autofunction:: macos.audio.concat
.. autofunction:: macos.audio.fade
.. autofunction:: macos.audio.gain
.. autofunction:: macos.audio.reverse
.. autofunction:: macos.audio.speed
.. autofunction:: macos.audio.classify
.. autoclass:: macos.audio.AudioInfo
.. autoclass:: macos.audio.Device
```

## macos.camera

```{eval-rst}
.. module:: macos.camera

.. autofunction:: macos.camera.devices
.. autofunction:: macos.camera.photo
.. autofunction:: macos.camera.record
.. autoclass:: macos.camera.Camera
.. autofunction:: macos.camera.has_permission
.. autofunction:: macos.camera.request_permission
```

## macos.bluetooth

```{eval-rst}
.. module:: macos.bluetooth

.. autofunction:: macos.bluetooth.power
.. autofunction:: macos.bluetooth.set_power
.. autofunction:: macos.bluetooth.devices
.. autofunction:: macos.bluetooth.connect
.. autofunction:: macos.bluetooth.disconnect
.. autoclass:: macos.bluetooth.Device
```

## macos.sound

```{eval-rst}
.. module:: macos.sound

.. autofunction:: macos.sound.play
.. autofunction:: macos.sound.beep
.. autofunction:: macos.sound.names
.. autofunction:: macos.sound.alert_sound
.. autofunction:: macos.sound.set_alert_sound
.. autofunction:: macos.sound.alert_volume
.. autofunction:: macos.sound.set_alert_volume
.. autofunction:: macos.sound.ui_sounds
.. autofunction:: macos.sound.set_ui_sounds
```

## macos.network

```{eval-rst}
.. module:: macos.network

.. autofunction:: macos.network.is_online
.. autofunction:: macos.network.ip
.. autofunction:: macos.network.interface
.. autofunction:: macos.network.wifi_power
.. autofunction:: macos.network.set_wifi_power
.. autoclass:: macos.network.SpeedTest
.. autofunction:: macos.network.speed_test
.. autoclass:: macos.network.WiFiSignal
.. autofunction:: macos.network.wifi_signal
.. autoclass:: macos.network.NetworkInterface
.. autofunction:: macos.network.interfaces
.. autofunction:: macos.network.dns_servers
.. autoclass:: macos.network.Proxies
.. autofunction:: macos.network.proxies
.. autoclass:: macos.network.VPN
.. autofunction:: macos.network.vpns
.. autofunction:: macos.network.connect_vpn
.. autofunction:: macos.network.disconnect_vpn
.. autoclass:: macos.network.Bandwidth
.. autofunction:: macos.network.bandwidth
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
.. autofunction:: macos.screen.record
.. autofunction:: macos.screen.find_text
.. autofunction:: macos.screen.wait_for_text
.. autofunction:: macos.screen.color_at
.. autofunction:: macos.screen.screenshot_folder
.. autofunction:: macos.screen.set_screenshot_folder
.. autofunction:: macos.screen.screenshot_format
.. autofunction:: macos.screen.set_screenshot_format
.. autofunction:: macos.screen.screenshot_shadow
.. autofunction:: macos.screen.set_screenshot_shadow
.. autoclass:: macos.screen.TextMatch
   :members: center
.. autofunction:: macos.screen.start_screensaver
.. autofunction:: macos.screen.brightness
.. autofunction:: macos.screen.set_brightness
.. autofunction:: macos.screen.night_shift
.. autofunction:: macos.screen.set_night_shift
.. autofunction:: macos.screen.true_tone
.. autofunction:: macos.screen.set_true_tone
.. autofunction:: macos.screen.lock
.. autofunction:: macos.screen.is_locked
.. autofunction:: macos.screen.is_asleep
.. autofunction:: macos.screen.screensaver_delay
.. autofunction:: macos.screen.set_screensaver_delay
.. autofunction:: macos.screen.screenshot_thumbnail
.. autofunction:: macos.screen.set_screenshot_thumbnail
.. autofunction:: macos.screen.screenshot_name
.. autofunction:: macos.screen.set_screenshot_name
.. autofunction:: macos.screen.screenshot_target
.. autofunction:: macos.screen.set_screenshot_target
.. autofunction:: macos.screen.night_shift_schedule
.. autofunction:: macos.screen.set_night_shift_schedule
.. autofunction:: macos.screen.night_shift_strength
.. autofunction:: macos.screen.set_night_shift_strength
.. autoclass:: macos.screen.DisplayMode
.. autofunction:: macos.screen.display_modes
.. autofunction:: macos.screen.display_mode
.. autofunction:: macos.screen.set_display_mode
.. autofunction:: macos.screen.set_main_display
.. autofunction:: macos.screen.mirrored
.. autofunction:: macos.screen.mirror
.. autofunction:: macos.screen.stop_mirroring
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
.. autofunction:: macos.system.cpu_usage
.. autofunction:: macos.system.memory_usage
.. autoclass:: macos.system.MemoryUsage
   :members: free, percent
.. autofunction:: macos.system.wait_for_idle
.. autofunction:: macos.system.wait_for_activity
.. autofunction:: macos.system.volumes
.. autofunction:: macos.system.eject
.. autofunction:: macos.system.mount_image
.. autofunction:: macos.system.unmount_image
.. autofunction:: macos.system.available_updates
.. autoclass:: macos.system.Update
.. autofunction:: macos.system.fonts
.. autofunction:: macos.system.thermal_state
.. autofunction:: macos.system.lid_closed
.. autofunction:: macos.system.camera_in_use
.. autofunction:: macos.system.microphone_in_use
.. autoclass:: macos.system.Volume
.. autofunction:: macos.system.ds_store_on_network
.. autofunction:: macos.system.set_ds_store_on_network
.. autofunction:: macos.system.ds_store_on_usb
.. autofunction:: macos.system.set_ds_store_on_usb
.. autofunction:: macos.system.keep_windows_on_quit
.. autofunction:: macos.system.set_keep_windows_on_quit
.. autofunction:: macos.system.battery_percentage_shown
.. autofunction:: macos.system.set_show_battery_percentage
.. autofunction:: macos.system.save_to_icloud_by_default
.. autofunction:: macos.system.set_save_to_icloud_by_default
.. autofunction:: macos.system.expanded_save_dialog
.. autofunction:: macos.system.set_expanded_save_dialog
.. autofunction:: macos.system.clock_format
.. autofunction:: macos.system.set_clock_format
.. autofunction:: macos.system.measurement_units
.. autofunction:: macos.system.set_measurement_units
.. autofunction:: macos.system.temperature_unit
.. autofunction:: macos.system.set_temperature_unit
.. autofunction:: macos.system.open_photos_on_device_connect
.. autofunction:: macos.system.set_open_photos_on_device_connect
.. autofunction:: macos.system.menu_bar_spacing
.. autofunction:: macos.system.set_menu_bar_spacing
.. autodata:: macos.system.MENU_BAR_ITEMS
.. autofunction:: macos.system.menu_bar_items
.. autofunction:: macos.system.set_menu_bar_items
.. autoclass:: macos.system.SecurityStatus
.. autofunction:: macos.system.security_status
.. autoclass:: macos.system.Process
.. autofunction:: macos.system.processes
.. autofunction:: macos.system.process
.. autofunction:: macos.system.kill
.. autoclass:: macos.system.Port
.. autofunction:: macos.system.ports
.. autofunction:: macos.system.port_owner
.. autoclass:: macos.system.Connection
.. autofunction:: macos.system.connections
.. autofunction:: macos.system.open_files
.. autofunction:: macos.system.who_uses
.. autoclass:: macos.system.NetworkUsage
.. autofunction:: macos.system.network_usage
.. autoclass:: macos.system.EnergyUsage
.. autofunction:: macos.system.energy_usage
.. autoclass:: macos.system.GPUUsage
.. autofunction:: macos.system.gpu_usage
.. autoclass:: macos.system.DiskHealth
.. autofunction:: macos.system.disk_health
.. autoclass:: macos.system.CrashReport
.. autofunction:: macos.system.crash_reports
.. autoclass:: macos.system.LogEntry
.. autofunction:: macos.system.logs
.. autoclass:: macos.system.StartupItem
.. autofunction:: macos.system.startup_items
.. autoclass:: macos.system.USBDevice
.. autofunction:: macos.system.usb_devices
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
