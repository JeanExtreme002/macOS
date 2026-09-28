# Video

{mod}`macos.video` reads videos, grabs their frames and converts them, with
AVFoundation, the framework behind QuickTime Player. Any format QuickTime opens
works (MOV, MP4, M4V, HEVC, ProRes...), with no ffmpeg to install.

```python
import macos

macos.video.info("clip.mov")
# VideoInfo(duration=12.5, width=1920, height=1080, fps=30.0, codec='h264', has_audio=True)

macos.video.convert("clip.mov", "clip.mp4", quality="medium")
```

## Frames

{func}`~macos.video.frame` returns the frame shown at a time, in seconds, as
PNG bytes, turned upright like the video plays:

```python
from pathlib import Path

Path("cover.png").write_bytes(macos.video.frame("clip.mov", at=3.0))
Path("thumb.png").write_bytes(macos.video.frame("clip.mov", at=3.0, size=320))
```

`size` limits the longest side, for thumbnails.

## Converting

{func}`~macos.video.convert` converts, compresses, resizes and trims:

```python
macos.video.convert("screen.mov", "share.mp4", quality="medium")   # smaller
macos.video.convert("clip.mov", "clip.mp4", hevc=True)             # HEVC (H.265)
macos.video.convert("4k.mov", "hd.mp4", height=1080)               # resized
macos.video.convert("talk.mov", "intro.mp4", start=0, duration=10) # the first 10 s
macos.video.convert("talk.mov", "talk.m4a")                        # the sound only
```

- The output's extension sets the container: `.mp4`, `.mov`, `.m4v`, or `.m4a`
  for the sound only.
- `quality` is `"high"` (the default), `"medium"` or `"low"`, a small preview.
- `height` fits the video in 640×480, 960×540, 1280×720, 1920×1080 or
  3840×2160 (`height=480` to `2160`), keeping its proportions: a 16:9 video at
  `height=480` becomes 640×360.
- `hevc=True` encodes in HEVC, smaller than H.264 at the same quality, at the
  high quality or at `height=1080` or `2160`.

It uses the `avconvert` command that ships with macOS, and replaces the output
if it exists. To record the screen, see {func}`macos.screen.record`.

## Reference

- {func}`macos.video.info`
- {func}`macos.video.frame`
- {func}`macos.video.convert`
- {class}`macos.video.VideoInfo`
