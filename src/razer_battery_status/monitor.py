from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event

from .hid_backend import BatterySnapshot, DeviceUnavailable, HidBackend
from .notifications import Alert, AlertKind, WindowsNotifier

LOW_BATTERY_PERCENT = 10.0
LOW_BATTERY_RESET_PERCENT = 12.0

DEVICE_SCAN_INTERVAL_SECONDS = 5.0
DISCHARGING_QUERY_INTERVAL_SECONDS = 300.0
CHARGING_QUERY_INTERVAL_SECONDS = 60.0
ERROR_RETRY_INTERVAL_SECONDS = 30.0


@dataclass
class AlertState:
    charging: bool | None = None
    low_battery_latched: bool = False
    full_battery_latched: bool = False

    def observe(self, snapshot: BatterySnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        percent = snapshot.percent
        display_percent = snapshot.display_percent
        previous_charging = self.charging

        if previous_charging is not None and snapshot.charging != previous_charging:
            if snapshot.charging:
                alerts.append(
                    Alert(
                        AlertKind.CONNECTED,
                        f"Mouse connected — charging at {display_percent}%.",
                    )
                )
            else:
                alerts.append(
                    Alert(
                        AlertKind.DISCONNECTED,
                        f"Mouse disconnected — discharging at {display_percent}%.",
                    )
                )
        self.charging = snapshot.charging

        if previous_charging is None:
            # Establish a silent baseline when the monitor starts at 100%.
            self.full_battery_latched = display_percent >= 100
        elif (
            display_percent >= 100
            and not self.full_battery_latched
            and (snapshot.charging or previous_charging)
        ):
            alerts.append(
                Alert(
                    AlertKind.FULLY_CHARGED,
                    "Mouse is fully charged (100%).",
                )
            )
            self.full_battery_latched = True
        elif display_percent <= 98:
            # Hysteresis prevents a noisy 99/100% boundary from re-alerting.
            self.full_battery_latched = False

        if snapshot.charging or percent >= LOW_BATTERY_RESET_PERCENT:
            self.low_battery_latched = False

        if (
            not snapshot.charging
            and percent < LOW_BATTERY_PERCENT
            and not self.low_battery_latched
        ):
            alerts.append(
                Alert(
                    AlertKind.LOW_BATTERY,
                    f"Mouse battery is low: {display_percent}% remaining.",
                )
            )
            self.low_battery_latched = True

        return alerts


class BatteryMonitor:
    def __init__(
        self,
        backend: HidBackend | None = None,
        notifier: WindowsNotifier | None = None,
    ) -> None:
        self.backend = backend or HidBackend()
        self.notifier = notifier or WindowsNotifier()
        self.alert_state = AlertState()
        self.log = logging.getLogger(__name__)

    def run(self, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        last_fingerprint: tuple[tuple[int, bytes], ...] | None = None
        next_query_at = 0.0

        self.log.info("monitor started")
        while not stop_event.is_set():
            now = time.monotonic()
            try:
                targets = self.backend.enumerate_targets()
            except OSError as exc:
                self.log.warning("HID enumeration failed: %s", exc)
                targets = []

            fingerprint = tuple(target.fingerprint for target in targets)
            if last_fingerprint is None or fingerprint != last_fingerprint:
                self.log.info("device set changed: %s", fingerprint)
                next_query_at = now
                last_fingerprint = fingerprint

            if targets and now >= next_query_at:
                try:
                    snapshot = self.backend.read_any(targets)
                except DeviceUnavailable as exc:
                    self.log.warning("status unavailable: %s", exc)
                    next_query_at = now + ERROR_RETRY_INTERVAL_SECONDS
                else:
                    self.log.info(
                        "battery=%d%% charging=%s connection=%s pid=0x%04x",
                        snapshot.display_percent,
                        snapshot.charging,
                        snapshot.target.connection_name,
                        snapshot.target.product_id,
                    )
                    for alert in self.alert_state.observe(snapshot):
                        try:
                            self.notifier.send(alert)
                        except Exception:
                            self.log.exception("notification failed: %s", alert.kind.value)
                    interval = (
                        CHARGING_QUERY_INTERVAL_SECONDS
                        if snapshot.charging
                        else DISCHARGING_QUERY_INTERVAL_SECONDS
                    )
                    next_query_at = now + interval

            stop_event.wait(DEVICE_SCAN_INTERVAL_SECONDS)

        self.log.info("monitor stopped")
