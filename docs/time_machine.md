# Time Machine

{mod}`macos.time_machine` starts Time Machine backups and follows them.

```python
import macos

macos.time_machine.destinations()   # ['Backup Disk']
macos.time_machine.backup_now()
macos.time_machine.is_backing_up()  # True
macos.time_machine.progress()       # 0.42
macos.time_machine.last_backup()    # datetime.datetime(2026, 9, 28, 23, 10, 4)
```

It uses the `tmutil` command that ships with macOS.

## Backing up

{func}`~macos.time_machine.backup_now` starts a backup, like *Back Up Now* in
the Time Machine menu, and returns at once; `wait=True` returns when it's done.
It raises {class}`~macos.MacOSError` when no backup disk is set up.
{func}`~macos.time_machine.stop_backup` stops the one in progress.

```python
macos.time_machine.backup_now(wait=True)
macos.notify("Backup done")
```

## Following a backup

{func}`~macos.time_machine.is_backing_up` tells whether a backup is running, and
{func}`~macos.time_machine.progress` how far it is, from 0.0 to 1.0 (`None` when
none runs, or while it's getting ready).
{func}`~macos.time_machine.last_backup` returns when the latest backup was made;
it needs the backup disk to be connected, and may need Full Disk Access for the
app running Python.

## Reference

- {func}`macos.time_machine.destinations`
- {func}`macos.time_machine.backup_now`
- {func}`macos.time_machine.stop_backup`
- {func}`macos.time_machine.is_backing_up`
- {func}`macos.time_machine.progress`
- {func}`macos.time_machine.last_backup`
