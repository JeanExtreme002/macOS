"""Unit tests for :mod:`macos.vision`. They run on any platform."""

import pytest

import macos


def test_best_shot_picks_the_best_faces(monkeypatch):
    scores = {"blurry.jpg": 0.2, "none.jpg": None, "sharp.jpg": 0.7, "also-sharp.jpg": 0.7}
    monkeypatch.setattr(macos.vision, "_load", lambda: None)
    monkeypatch.setattr(macos.vision, "_face_quality", lambda image: scores[image])

    assert macos.vision.best_shot(["blurry.jpg", "none.jpg", "sharp.jpg", "also-sharp.jpg"]) == "sharp.jpg"
    assert macos.vision.best_shot(["none.jpg"]) is None
    with pytest.raises(ValueError):
        macos.vision.best_shot([])


def test_duplicates_groups_through_chains_in_the_given_order(monkeypatch):
    # Feature prints are stood in by numbers; their distance is the difference.
    monkeypatch.setattr(macos.vision, "_load", lambda: None)
    monkeypatch.setattr(macos.vision, "_feature_print", lambda image: image)
    monkeypatch.setattr(macos.vision, "_distance", lambda first, second: abs(first - second))
    monkeypatch.setattr(macos.vision._objc, "send", lambda *args, **kwargs: None)

    # 1.0 ~ 1.2 ~ 1.4 chain into one group, though 1.0 and 1.4 are far apart.
    groups = macos.vision.duplicates([5.0, 1.0, 9.0, 1.2, 5.1, 1.4], threshold=0.3)

    assert groups == [[5.0, 5.1], [1.0, 1.2, 1.4]]


def test_joint_names_are_readable():
    assert macos.vision._snake("LeftShoulder") == "left_shoulder"
    assert macos.vision._snake("ThumbCMC") == "thumb_cmc"
    assert macos.vision._snake("IndexTip") == "index_tip"
    assert len(macos.vision._BODY_JOINTS) == 19 and len(macos.vision._HAND_JOINTS) == 21


def test_vision_argument_checks():
    with pytest.raises(ValueError):
        macos.vision.classify(b"image", limit=0)
    with pytest.raises(ValueError, match="threshold"):
        macos.vision.duplicates([b"image"], threshold=0)
    with pytest.raises(ValueError, match="positive"):
        macos.vision.smart_crop(b"image", 0, 100)
    with pytest.raises(ValueError, match="max_hands"):
        macos.vision.hand_pose(b"image", max_hands=0)


def test_text_spans_ignore_case_whatever_the_length():
    from macos.vision import _spans

    assert _spans("Click Submit, then submit", "SUBMIT") == [(6, 12), (19, 25)]
    assert _spans("Straße STRASSE", "strasse") == [(0, 6), (7, 14)]  # "ß" folds to "ss"
    assert _spans("ßA", "a") == [(1, 2)]
    assert _spans("anything", "") == []


def test_pdfs_are_refused_before_vision_sees_a_blank_image(tmp_path):
    from macos.vision import _refuse_pdf

    document = tmp_path / "scan.png"  # the name doesn't matter, the bytes do
    document.write_bytes(b"%PDF-1.7\n...")
    for image in (b"%PDF-1.4\n...", bytearray(b"\r\n%PDF-1.4\n..."), document, str(document)):
        with pytest.raises(ValueError, match="macos.pdf.render"):
            _refuse_pdf(image)
        with pytest.raises(ValueError, match="macos.pdf.render"):
            macos.vision.smart_crop(image, 100, 100)

    _refuse_pdf(b"\x89PNG\r\n\x1a\n")
    _refuse_pdf(tmp_path / "missing.png")  # left to the usual FileNotFoundError
