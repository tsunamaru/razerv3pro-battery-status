from __future__ import annotations

import sys
from types import ModuleType

import pytest

from razer_battery_status.notifications import (
    APP_NAME,
    Alert,
    AlertKind,
    WindowsNotifier,
)


@pytest.mark.parametrize(
    "kind",
    [
        AlertKind.CONNECTED,
        AlertKind.DISCONNECTED,
        AlertKind.FULLY_CHARGED,
    ],
)
def test_non_alert_status_notifications_are_silent(monkeypatch, kind) -> None:
    calls = []
    fake_module = ModuleType("win11toast")
    fake_module.toast = lambda *args, **kwargs: calls.append((args, kwargs))
    monkeypatch.setitem(sys.modules, "win11toast", fake_module)

    WindowsNotifier().send(Alert(kind, "Charging state changed"))

    assert calls == [
        ((APP_NAME, "Charging state changed"), {"audio": {"silent": "true"}})
    ]


def test_low_battery_notification_keeps_default_sound(monkeypatch) -> None:
    calls = []
    fake_module = ModuleType("win11toast")
    fake_module.toast = lambda *args, **kwargs: calls.append((args, kwargs))
    monkeypatch.setitem(sys.modules, "win11toast", fake_module)

    WindowsNotifier().send(Alert(AlertKind.LOW_BATTERY, "Battery is low"))

    assert calls == [((APP_NAME, "Battery is low"), {})]
