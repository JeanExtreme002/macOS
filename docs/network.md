# Network

{mod}`macos.network` tells you whether the Mac is online, its address on the
local network, turns Wi-Fi on and off, and connects VPNs.

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
result.loaded_latency            # 1126.6 ms, while busy: how laggy calls get
result.responsiveness            # 53.3: the same as a score, in round trips per minute (RPM)
```

It takes 15 to 60 seconds and moves a few hundred megabytes: mind a
metered connection. `sequential=True` measures download and upload one
after the other, which reads each more exactly. It goes through
`networkQuality`, which comes with macOS.

## Wi-Fi signal

{func}`~macos.network.wifi_signal` tells how good the Wi-Fi connection is, or
`None` when not on Wi-Fi:

```python
signal = macos.network.wifi_signal()
signal.rssi, signal.quality       # (-62, 'good'): -50 is excellent, below -80 poor
signal.snr                        # 33 dB above the noise
signal.band, signal.channel       # ('5GHz', 157)
signal.transmit_rate              # 866.0 Mbit/s: the link's speed, not the internet's
```

Walk around with it to find a room's dead spots, or tell a weak signal
from a slow internet. It needs no permission; the network's name, which
macOS keeps behind the Location permission, isn't part of it.

## Interfaces, DNS and proxies

```python
for found in macos.network.interfaces():
    if found.active:
        print(found.display_name or found.name, found.ipv4, found.mac)   # Wi-Fi ('192.168.0.8',) a4:83:...

macos.network.dns_servers()   # ['192.168.0.1', '8.8.8.8']
macos.network.proxies()       # Proxies(http=None, https='proxy.example.com:8080', socks=None, ...)
```

{func}`~macos.network.interfaces` lists every interface (Wi-Fi, Ethernet,
Thunderbolt, VPN tunnels) with its addresses; an interface is `active` when
it has an address to talk with. {func}`~macos.network.dns_servers` and
{func}`~macos.network.proxies` are the ones in use now, whether set in
System Settings, by the network or by a VPN or a profile.

## VPN

```python
macos.network.vpns()                  # [VPN(name='Office', kind='L2TP', status='disconnected', ...)]
macos.network.connect_vpn("Office")
macos.network.disconnect_vpn("Office")
```

{func}`~macos.network.vpns` lists the VPNs set up in System Settings › VPN,
with their `status`: `'connected'`, `'connecting'`, `'disconnecting'` or
`'disconnected'`. {func}`~macos.network.connect_vpn` connects one, by name or
`id`, and waits until it's connected, up to `timeout` seconds (30 by
default), raising {class}`~macos.MacOSError` if it fails; `wait=False`
returns at once. It uses the password saved with the VPN: one that asks each
time may show its prompt. {func}`~macos.network.disconnect_vpn` disconnects it.

A script that needs the office network can connect only while it runs:

```python
macos.network.connect_vpn("Office")
try:
    sync_reports()
finally:
    macos.network.disconnect_vpn("Office")
```

Each VPN's `kind` is its protocol, such as `'L2TP'` or `'IPSec'`, or for a VPN
app, the app's bundle ID. VPN apps that don't add theirs to System Settings
aren't listed, and IKEv2 VPNs may not be either: macOS has long left them out
of what the command line sees.

## Reference

- {func}`macos.network.is_online`
- {func}`macos.network.ip`
- {func}`macos.network.interface`
- {func}`macos.network.wifi_power`
- {func}`macos.network.set_wifi_power`
- {func}`macos.network.speed_test`
- {class}`macos.network.SpeedTest`
- {class}`macos.network.WiFiSignal`
- {func}`macos.network.wifi_signal`
- {class}`macos.network.NetworkInterface`
- {func}`macos.network.interfaces`
- {func}`macos.network.dns_servers`
- {class}`macos.network.Proxies`
- {func}`macos.network.proxies`
- {class}`macos.network.VPN`
- {func}`macos.network.vpns`
- {func}`macos.network.connect_vpn`
- {func}`macos.network.disconnect_vpn`
