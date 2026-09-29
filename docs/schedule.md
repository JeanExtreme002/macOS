# Schedule

{mod}`macos.schedule` runs your Python scripts on a schedule, or when you log
in, with launchd: the Mac's cron, without writing its XML by hand.

```python
import macos

macos.schedule.add("backup", "~/scripts/backup.py", every=3600)       # every hour
macos.schedule.add("report", "report.py", at="09:00")                 # every day at 9
macos.schedule.add("sync", "sync.py", at="18:30", weekdays=["mon", "fri"])
macos.schedule.add("hello", "hello.py", at_login=True)
```

A job keeps running after your script ends and after a restart, as long as
you're logged in. When the Mac was asleep at the scheduled time, the job runs
when it wakes up.

## Adding a job

{func}`~macos.schedule.add` takes a name (letters, digits, `.`, `_`, `-`),
the script, and when to run it:

- `every`: seconds between runs, or a {class}`~datetime.timedelta`.
- `at`: a time of day, `"09:00"` or a {class}`~datetime.time`, or a list of
  them; with `weekdays` (`["mon", "wed", "fri"]`), only on those days.
- `at_login=True`: each time you log in, and once right away.

```python
macos.schedule.add("tidy", "tidy_downloads.py", at=["08:00", "20:00"])
macos.schedule.add("scrape", "scrape.py", every=900, args=["--quiet"], python="~/venvs/scrape/bin/python")
```

The script runs with the same Python that added it (or `python=`, such as a
virtual environment's), in its own folder, with `args` as its arguments.
Adding a name again replaces that job.

macOS announces the new job with a *Background Items Added* notification,
and lists it in System Settings › General › Login Items & Extensions. The
script runs outside your terminal, so it doesn't get the terminal's
[permissions](permissions.md): macOS asks for them again, for Python.

## Checking on jobs

```python
for job in macos.schedule.jobs():
    print(job.name, job.every or job.at, job.last_exit_status)

job = macos.schedule.get("backup")
print(job.log.read_text())         # what the script printed, and its errors

macos.schedule.run_now("backup")   # run it once now, besides its schedule
macos.schedule.pause("backup")     # off its schedule, until resume("backup")
macos.schedule.remove("backup")
```

Each {class}`~macos.schedule.Job` tells whether it's `running`, and how the
last run ended (`last_exit_status`, 0 for success). The script's output and
errors go to `job.log`, in `~/Library/Logs/pymacos`.
{func}`~macos.schedule.pause` keeps a job without running it, even after a
restart, and `job.paused` tells; {func}`~macos.schedule.resume` puts it back on
its schedule. Pausing or removing a job also stops a run in progress.

## Reference

- {func}`macos.schedule.add`
- {func}`macos.schedule.remove`
- {func}`macos.schedule.jobs`
- {func}`macos.schedule.get`
- {func}`macos.schedule.run_now`
- {func}`macos.schedule.pause`
- {func}`macos.schedule.resume`
- {class}`macos.schedule.Job`
