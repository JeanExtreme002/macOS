# Network

{mod}`macos.network` tells you whether the Mac is online, its address on the
local network, and turns Wi-Fi on and off.

```python
import macos

macos.network.is_online()      # True
macos.network.ip()             # '192.168.0.8'
macos.network.interface()      # 'en0'
```

## Online or offline

{func}`~macos.network.is_online` checks locally whether there's a connection
that can reach the internet, without contacting any server: the same check
apps use to show "you're offline". A Wi-Fi login page (as in hotels) still
counts as online.

```python
if not macos.network.is_online():
    macos.notify("Waiting for the network...")
```

## Address

{func}`~macos.network.ip` returns the Mac's IPv4 address on the local network,
and {func}`~macos.network.interface` the interface internet traffic goes
through (`'en0'` is usually Wi-Fi). Both return `None` when offline.

To open a local server from your phone, show its address as a QR code and
point the phone's camera at it:

```python
from pathlib import Path

code = Path("server.png")
code.write_bytes(macos.image.qr_code("http://{}:8000".format(macos.network.ip())))
macos.open(code)
```

## Wi-Fi

```python
macos.network.wifi_power()           # True
macos.network.set_wifi_power(False)  # like the switch in Control Center
```

Both raise {class}`~macos.NotSupportedError` on a Mac without Wi-Fi. The Wi-Fi
network's name isn't available: since macOS 14, reading it needs the Location
permission.

## Speed test

{func}`~macos.network.speed_test` measures the connection's download and
upload speed, and its latency, against Apple's servers:

```python
result = macos.network.speed_test()
result.download, result.upload   # (43.61, 39.42): megabits per second
result.latency                   # 54.6 ms, idle
result.loaded_latency            # 53.3 ms, while busy: how laggy calls get
```

It takes 15 to 60 seconds and moves a few hundred megabytes: mind a
metered connection. `sequential=True` measures download and upload one
after the other, which reads each more exactly. It goes through
`networkQuality`, which comes with macOS.

## Reference

- {func}`macos.network.is_online`
- {func}`macos.network.ip`
- {func}`macos.network.interface`
- {func}`macos.network.wifi_power`
- {func}`macos.network.set_wifi_power`
- {func}`macos.network.speed_test`
- {class}`macos.network.SpeedTest`
