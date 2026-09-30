"""Unit tests for :mod:`macos.maps`. They run on any platform."""

import threading

import pytest

import macos
from macos import maps

PLACE = maps.Place("Eiffel Tower", "5 Avenue Anatole France", "Paris", "Île-de-France", "75007", "France", "FR",
                   48.8584, 2.2945, "Europe/Paris")  # fmt: skip


def test_results_and_errors():
    assert maps._result([PLACE], None) == [PLACE]
    assert maps._result([], (8, "No result")) == []  # nothing found isn't an error
    with pytest.raises(macos.MacOSError, match="could not reach Apple's geocoding service"):
        maps._result([], (2, "The network is down"))
    with pytest.raises(macos.MacOSError, match="error 10"):
        maps._result([], (10, "Canceled"))


def test_argument_checks():
    with pytest.raises(ValueError, match="address must not be empty"):
        maps.geocode("  ")
    for latitude, longitude in ((91, 0), (0, 181), (-90.5, 0)):
        with pytest.raises(ValueError, match="latitude must be"):
            maps.reverse_geocode(latitude, longitude)


def test_only_the_main_thread_gets_answers():
    failures = []

    def ask():
        try:
            maps._ask("geocodeAddressString:completionHandler:", 0, timeout=1)
        except macos.MacOSError as error:
            failures.append(str(error))

    thread = threading.Thread(target=ask)
    thread.start()
    thread.join()
    assert failures == ["geocoding answers on the main thread: call it from there"]


def test_open_and_directions(fake_run):
    maps.open("Avenida Paulista, 1578, São Paulo")
    assert fake_run.args == ["open", "maps://?q=Avenida%20Paulista%2C%201578%2C%20S%C3%A3o%20Paulo"]
    maps.open(PLACE)
    assert fake_run.args[-1] == "maps://?ll=48.8584%2C2.2945&q=Eiffel%20Tower"
    maps.open((-22.95, -43.21))
    assert fake_run.args[-1] == "maps://?ll=-22.95%2C-43.21&q=-22.95%2C-43.21"
    maps.directions((48.8584, 2.2945), start="Gare du Nord", by="walk")
    assert fake_run.args[-1] == "maps://?daddr=48.8584%2C2.2945&dirflg=w&saddr=Gare%20du%20Nord"
    maps.directions("Congonhas")
    assert fake_run.args[-1] == "maps://?daddr=Congonhas&dirflg=d"
    with pytest.raises(ValueError, match="by must be"):
        maps.directions("Congonhas", by="bike")
    with pytest.raises(ValueError, match="must not be empty"):
        maps.open(" ")
