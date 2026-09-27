# Speech

{func}`macos.say` speaks text out loud with the system voices.

```python
import macos

macos.say("Hello from Python")
```

Choose a voice and a speed in words per minute (about 175 to 200 is normal):

```python
macos.say("Olá, tudo bem?", voice="Luciana", rate=180)
```

By default `say` waits until the speech ends. Pass `wait=False` to return right
away while it plays:

```python
macos.say("Starting the backup", wait=False)
run_backup()
```

## Voices

{func}`macos.speech.voices` lists the installed voices:

```python
for voice in macos.speech.voices():
    print(voice.name, voice.locale, voice.sample)
```

```text
Albert en_US Hello! My name is Albert.
Luciana pt_BR Olá, meu nome é Luciana.
...
```

More voices can be downloaded in System Settings › Accessibility › Spoken
Content › System Voice › Manage Voices.

An unknown voice name is not an error: macOS falls back to the default voice.
Names are matched loosely, so `"luciana"` works too.

## Reference

- {func}`macos.say`
- {func}`macos.speech.voices`
- {class}`macos.speech.Voice`
