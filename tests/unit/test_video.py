"""Unit tests for :mod:`macos.video`. They run on any platform."""

import pytest

import macos


def test_video_convert_command(commands, tmp_path):
    macos.video.convert(__file__, tmp_path / "out.mp4", quality="medium", start=5, duration=10.5)
    assert commands.calls[-1] == [
        "avconvert",
        "--source",
        __file__,
        "--output",
        str(tmp_path / "out.mp4"),
        "--preset",
        "PresetMediumQuality",
        "--replace",
        "--start",
        "5",
        "--duration",
        "10.5",
    ]
    macos.video.convert(__file__, tmp_path / "out.mov", hevc=True, height=2160)
    assert commands.calls[-1][6] == "PresetHEVC3840x2160"
    macos.video.convert(__file__, tmp_path / "out.m4v", height=720)
    assert commands.calls[-1][6] == "Preset1280x720"


def test_video_argument_checks(tmp_path):
    with pytest.raises(ValueError, match="negative"):
        macos.video.frame(__file__, at=-1)
    with pytest.raises(ValueError, match="can't write"):
        macos.video.convert(__file__, tmp_path / "out.avi")
    with pytest.raises(ValueError, match="quality"):
        macos.video.convert(__file__, tmp_path / "out.mp4", quality="best")
    with pytest.raises(ValueError, match="height must be one of"):
        macos.video.convert(__file__, tmp_path / "out.mp4", height=333)
    with pytest.raises(ValueError, match="with hevc=True"):
        macos.video.convert(__file__, tmp_path / "out.mp4", hevc=True, height=720)
    with pytest.raises(ValueError, match="only has the 'high' quality"):
        macos.video.convert(__file__, tmp_path / "out.mp4", hevc=True, quality="low")
    with pytest.raises(ValueError, match="duration"):
        macos.video.convert(__file__, tmp_path / "out.mp4", duration=0)
    with pytest.raises(ValueError, match="fps"):
        macos.video.to_gif(__file__, tmp_path / "out.gif", fps=0)
    with pytest.raises(ValueError, match="width"):
        macos.video.to_gif(__file__, tmp_path / "out.gif", width=0)
    with pytest.raises(ValueError, match="duration"):
        macos.video.to_gif(__file__, tmp_path / "out.gif", duration=0)
    with pytest.raises(ValueError, match=".gif"):
        macos.video.to_gif(__file__, tmp_path / "out.mp4")
    with pytest.raises(ValueError, match="can't write '.avi'"):
        macos.video.trim(__file__, tmp_path / "out.avi", 1)
    with pytest.raises(ValueError, match="at least one"):
        macos.video.concat([], tmp_path / "out.mov")
    with pytest.raises(ValueError, match="positive"):
        macos.video.speed(__file__, tmp_path / "out.mov", -1)
    with pytest.raises(ValueError, match="multiple of 90"):
        macos.video.rotate(__file__, tmp_path / "out.mov", 45)
    with pytest.raises(ValueError, match="at least 2 x 2"):
        macos.video.crop(__file__, tmp_path / "out.mov", (0, 0, 0, 10))
    with pytest.raises(ValueError, match="at least 2 x 2"):
        macos.video.crop(__file__, tmp_path / "out.mov", (0, 0, 1, 10))
    with pytest.raises(ValueError, match="volume"):
        macos.video.add_audio(__file__, __file__, tmp_path / "out.mov", volume=2)
    with pytest.raises(ValueError, match="negative"):
        macos.video.add_audio(__file__, __file__, tmp_path / "out.mov", at=-1)
    with pytest.raises(ValueError, match="language tag"):
        macos.video.add_language_track(__file__, __file__, tmp_path / "out.mov", "english")
    with pytest.raises(ValueError, match="tag"):
        macos.video.add_language_track(__file__, __file__, tmp_path / "out.mov", "en", original_language="pt_BR")
    with pytest.raises(ValueError, match="at least one"):
        macos.video.from_images([], tmp_path / "out.mov")
    with pytest.raises(ValueError, match="fps"):
        macos.video.from_images([__file__], tmp_path / "out.mov", fps=0)
    with pytest.raises(ValueError, match="every"):
        macos.video.frames(__file__, every=0)
