# System

{mod}`macos.system` tells you about the Mac your code runs on.

```python
import macos

macos.system.version()            # '15.6.1'
macos.system.build()              # '24G90'
macos.system.model()              # 'MacBook Pro'
macos.system.model_identifier()   # 'Mac14,9'
macos.system.processor()          # 'Apple M2 Pro'
macos.system.memory()             # 17179869184 (bytes)
macos.system.computer_name()      # "Alice's MacBook Pro"
macos.system.uptime()             # datetime.timedelta(days=3, seconds=7200)
macos.system.idle_time()          # datetime.timedelta(seconds=312)
```

{func}`~macos.system.memory` is in bytes: divide by `2**30` for GB.
{func}`~macos.system.uptime` counts from the last restart, including the time
the Mac spent asleep.

## Running while the user is away

{func}`~macos.system.idle_time` is the time since the last keyboard, mouse or
trackpad input. It lets a script do heavy work only when nobody is using the
Mac:

```python
import time
from datetime import timedelta

while True:
    if macos.system.idle_time() > timedelta(minutes=10):
        run_heavy_job()
    time.sleep(60)
```

## Reference

- {func}`macos.system.version`
- {func}`macos.system.build`
- {func}`macos.system.model`
- {func}`macos.system.model_identifier`
- {func}`macos.system.processor`
- {func}`macos.system.memory`
- {func}`macos.system.computer_name`
- {func}`macos.system.uptime`
- {func}`macos.system.idle_time`
