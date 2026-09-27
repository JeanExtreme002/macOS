# Installation

Install from PyPI:

```bash
pip install macos
```

`macos` has no dependencies and needs no compiler: it's pure Python on top of
[ctypes](https://docs.python.org/3/library/ctypes.html) and the command-line
tools that ship with macOS.

## Requirements

- macOS
- Python 3.9 or later

## Other operating systems

The package *imports* on any OS, so it's safe to use in cross-platform code and
to build docs on Linux. Calling one of its functions outside macOS raises
{class}`~macos.NotSupportedError`:

```python
import sys
import macos

if sys.platform == "darwin":
    macos.notify("Hello from a Mac")
```

## Checking the version

```python
>>> import macos
>>> macos.__version__
'0.1.0'
```
