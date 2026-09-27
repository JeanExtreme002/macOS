# Errors

Every exception the package raises on purpose derives from
{class}`~macos.MacOSError`, so a single `except` catches them all:

```python
try:
    macos.screenshot("screen.png")
except macos.MacOSError as error:
    print("macOS said no:", error)
```

Where a builtin exception means the same thing, the `macos` exception also
subclasses it, so existing handlers keep working: `except PermissionError`
catches {class}`~macos.PermissionDeniedError`, and `except LookupError` catches
{class}`~macos.AppNotFoundError`.

| Exception | Raised when |
|---|---|
| {class}`~macos.NotSupportedError` | Not running on macOS, or a required system tool is missing |
| {class}`~macos.PermissionDeniedError` | A privacy permission is missing, or the user denied access |
| {class}`~macos.AppNotFoundError` | No app matches the name, or it didn't start in time |
| {class}`~macos.KeychainError` | The Keychain returned an error (see its `status`) |
| {class}`~macos.CommandError` | A system command failed (see its `returncode` and `stderr`) |

Invalid arguments, such as an unsupported screenshot format, raise the usual
`ValueError`.

## Reference

- [Exceptions in the API reference](api.md#exceptions)
