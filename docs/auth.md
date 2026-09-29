# Authentication

{mod}`macos.auth` asks the user to confirm it's them, with Touch ID, their
login password or their Apple Watch, before a script does something sensitive.

```python
import macos

if macos.auth.confirm("unlock the production credentials"):
    token = macos.keychain.get("deploy", "prod")
    deploy(token)
```

macOS shows its own prompt, *"Python wants to unlock the production
credentials"*, and checks the fingerprint or the password itself: the script
never sees them, it only learns whether the user confirmed.

## Confirming

{func}`~macos.auth.confirm` returns `True` when the user confirms, and `False`
when they cancel, fail, or don't answer within `timeout` seconds (2 minutes by
default). `reason` completes the prompt's sentence, so write it as what the
script is about to do.

By default the user may type their login password instead of using Touch ID,
so it works on any Mac, and with the lid closed. `only_touch_id=True` accepts
only the fingerprint:

```python
macos.auth.confirm("delete the old backups", only_touch_id=True)
```

{func}`~macos.auth.is_available` tells, without asking, whether it can:

```python
macos.auth.is_available(only_touch_id=True)   # False on a Mac without Touch ID
```

## Protecting a function

The {func}`~macos.auth.required` decorator asks each time the function is
called, before it runs. When the user doesn't confirm, the call raises
{class}`~macos.PermissionDeniedError` and the function doesn't run:

```python
@macos.auth.required("deploy to production")
def deploy():
    ...

deploy()   # Touch ID first
```

## What it protects

It's a check before an action, like `sudo` asking for a password: it stops
someone else using the Mac from running the script's sensitive part. It isn't
encryption: a Keychain item isn't locked behind Touch ID, since that takes an
app signed with Apple's entitlements, which Python isn't.

## Reference

- {func}`macos.auth.confirm`
- {func}`macos.auth.is_available`
- {func}`macos.auth.required`
