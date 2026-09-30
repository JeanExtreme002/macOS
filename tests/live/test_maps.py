"""Tests of :mod:`macos.maps` against Apple's geocoding service. Skipped outside macOS."""

import pytest

import macos


def _or_skip(call):
    try:
        return call()
    except macos.MacOSError as error:
        if "could not reach" in str(error):
            pytest.skip("Apple's geocoding service is out of reach: {}".format(error))
        raise


def test_geocode_and_back():
    place = _or_skip(lambda: macos.maps.geocode("1 Infinite Loop, Cupertino"))[0]
    assert place.country_code == "US" and place.city == "Cupertino"
    assert abs(place.latitude - 37.33) < 0.05 and abs(place.longitude + 122.03) < 0.05
    back = _or_skip(lambda: macos.maps.reverse_geocode(place.latitude, place.longitude))
    assert back is not None and back.country_code == "US" and back.time_zone == "America/Los_Angeles"
