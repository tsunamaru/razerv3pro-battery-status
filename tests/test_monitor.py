from __future__ import annotations

from razer_battery_status.hid_backend import BatterySnapshot, HidTarget
from razer_battery_status.monitor import AlertState
from razer_battery_status.notifications import AlertKind

TARGET = HidTarget(
    path=b"test",
    product_id=0x00C3,
    product_string="Razer DeathAdder V3 Pro",
)


def snapshot(percent_raw: int, *, charging: bool) -> BatterySnapshot:
    return BatterySnapshot(TARGET, percent_raw, charging)


def kinds(alerts):
    return [alert.kind for alert in alerts]


def test_initial_normal_state_is_silent() -> None:
    state = AlertState()

    assert state.observe(snapshot(128, charging=False)) == []


def test_initial_low_battery_alerts_once() -> None:
    state = AlertState()

    assert kinds(state.observe(snapshot(25, charging=False))) == [
        AlertKind.LOW_BATTERY
    ]
    assert state.observe(snapshot(24, charging=False)) == []


def test_exactly_ten_percent_does_not_alert() -> None:
    state = AlertState()

    # 25.5/255 is exactly 10%; raw values are integral, so 26 is above it.
    assert state.observe(snapshot(26, charging=False)) == []


def test_charging_transitions_are_reported() -> None:
    state = AlertState()
    state.observe(snapshot(100, charging=False))

    assert kinds(state.observe(snapshot(101, charging=True))) == [AlertKind.CONNECTED]
    assert kinds(state.observe(snapshot(102, charging=False))) == [
        AlertKind.DISCONNECTED
    ]


def test_charging_resets_low_battery_latch() -> None:
    state = AlertState()
    state.observe(snapshot(20, charging=False))
    state.observe(snapshot(21, charging=True))
    alerts = state.observe(snapshot(20, charging=False))

    assert kinds(alerts) == [AlertKind.DISCONNECTED, AlertKind.LOW_BATTERY]


def test_recovery_hysteresis_resets_latch() -> None:
    state = AlertState()
    state.observe(snapshot(20, charging=False))
    state.observe(snapshot(31, charging=False))  # Just over 12%.

    assert kinds(state.observe(snapshot(20, charging=False))) == [
        AlertKind.LOW_BATTERY
    ]


def test_reaching_full_charge_alerts_once() -> None:
    state = AlertState()
    state.observe(snapshot(253, charging=True))  # Displays as 99%.

    assert kinds(state.observe(snapshot(254, charging=True))) == [
        AlertKind.FULLY_CHARGED
    ]
    assert state.observe(snapshot(255, charging=True)) == []


def test_initial_full_charge_is_silent() -> None:
    state = AlertState()

    assert state.observe(snapshot(255, charging=True)) == []


def test_full_charge_does_not_alert_while_discharging() -> None:
    state = AlertState()
    state.observe(snapshot(253, charging=False))

    assert state.observe(snapshot(254, charging=False)) == []


def test_full_charge_latch_resets_below_hysteresis() -> None:
    state = AlertState()
    state.observe(snapshot(253, charging=True))
    state.observe(snapshot(254, charging=True))
    state.observe(snapshot(249, charging=True))  # Displays as 98%.

    assert kinds(state.observe(snapshot(254, charging=True))) == [
        AlertKind.FULLY_CHARGED
    ]
