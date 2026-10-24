from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

APP_NAME = "Razer Battery Status"


class AlertKind(Enum):
    LOW_BATTERY = "low-battery"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FULLY_CHARGED = "fully-charged"


@dataclass(frozen=True)
class Alert:
    kind: AlertKind
    body: str


class WindowsNotifier:
    def send(self, alert: Alert) -> None:
        from win11toast import toast

        options = {}
        if alert.kind in (
            AlertKind.CONNECTED,
            AlertKind.DISCONNECTED,
            AlertKind.FULLY_CHARGED,
        ):
            options["audio"] = {"silent": "true"}
        toast(APP_NAME, alert.body, **options)


def send_test_notification() -> None:
    WindowsNotifier().send(
        Alert(
            AlertKind.CONNECTED,
            "Notifications are working. The battery monitor is ready.",
        )
    )
