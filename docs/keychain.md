# Keychain

{mod}`macos.keychain` stores passwords in the macOS Keychain, encrypted and
tied to the user's login.

```python
import macos

macos.keychain.set("my-app", "alice", "s3cret")
macos.keychain.get("my-app", "alice")      # 's3cret'
macos.keychain.delete("my-app", "alice")   # True
macos.keychain.get("my-app", "alice")      # None
```

Each item is identified by a **service** (usually your app's name) and an **account** (usually a user name).

{func}`~macos.keychain.set` replaces the
password if the item already exists. {func}`~macos.keychain.delete` returns
`False` if there was nothing to delete.

## Keeping secrets out of your code

Store an API token once:

```python
macos.keychain.set("openai", "default", "sk-...")
```

Then read it wherever you need it, instead of keeping it in a `.env` file or in
the source code:

```python
api_key = macos.keychain.get("openai", "default")
```

## Seeing the items in Keychain Access

The items are *generic passwords* in the **login** keychain:

1. Open **Keychain Access** (search for it with Spotlight).
2. Select the **login** keychain and the **Passwords** tab.
3. Search for your service name. The item's *Name* is the service and its
   *Account* is the account.

The **Passwords** app in recent macOS versions doesn't list these items; use
Keychain Access. From the terminal:

```bash
security find-generic-password -s my-app -a alice -w
```

## Security

The password goes straight to the Security framework. It is never passed on a
command line, where every user on the Mac could see it in the process list.

## Limitations

- Service and account names can't contain NUL characters (`"\0"`): the keychain
  would silently cut them there and address a different item, so `macos`
  raises `ValueError`.
- If the stored data isn't UTF-8 text (e.g. binary data written by another
  app), {func}`~macos.keychain.get` raises {class}`~macos.KeychainError`.

## Reference

- {func}`macos.keychain.set`
- {func}`macos.keychain.get`
- {func}`macos.keychain.delete`
