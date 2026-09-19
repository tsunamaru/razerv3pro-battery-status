from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

import hid

from .protocol import (
    BATTERY_COMMAND_ID,
    CHARGING_COMMAND_ID,
    FEATURE_REPORT_SIZE,
    STATUS_BUSY,
    STATUS_FAILURE,
    STATUS_NOT_SUPPORTED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    ProtocolError,
    RazerResponse,
    build_request,
    parse_response,
)


RAZER_VENDOR_ID = 0x1532

# Original and alternate product IDs. This PC currently uses the alternate pair.
WIRED_PRODUCT_IDS = frozenset({0x00B6, 0x00C2})
WIRELESS_PRODUCT_IDS = frozenset({0x00B7, 0x00C3})
SUPPORTED_PRODUCT_IDS = WIRED_PRODUCT_IDS | WIRELESS_PRODUCT_IDS

CONTROL_INTERFACE = 0
CONTROL_USAGE_PAGE = 0x0001
CONTROL_USAGE = 0x0002

MAX_QUERY_ATTEMPTS = 4
RECEIVER_WAIT_SECONDS = 0.060


class DeviceUnavailable(RuntimeError):
    """No supported or responding mouse HID collection was available."""


@dataclass(frozen=True)
class HidTarget:
    path: bytes
    product_id: int
    product_string: str

    @property
    def wired(self) -> bool:
        return self.product_id in WIRED_PRODUCT_IDS

    @property
    def connection_name(self) -> str:
        return "wired" if self.wired else "wireless"

    @property
    def fingerprint(self) -> tuple[int, bytes]:
        return self.product_id, self.path


@dataclass(frozen=True)
class BatterySnapshot:
    target: HidTarget
    battery_raw: int
    charging: bool

    @property
    def percent(self) -> float:
        return self.battery_raw * 100.0 / 255.0

    @property
    def display_percent(self) -> int:
        return int(self.percent + 0.5)


class HidBackend:
    def __init__(self) -> None:
        self._query_lock = threading.Lock()

    def enumerate_targets(self) -> list[HidTarget]:
        targets: list[HidTarget] = []
        for info in hid.enumerate(RAZER_VENDOR_ID, 0):
            if not self._is_supported_collection(info):
                continue
            path = info.get("path")
            if isinstance(path, str):
                path = path.encode()
            if not isinstance(path, bytes):
                continue
            targets.append(
                HidTarget(
                    path=path,
                    product_id=int(info["product_id"]),
                    product_string=info.get("product_string")
                    or "Razer DeathAdder V3 Pro",
                )
            )
        return sorted(targets, key=lambda target: (not target.wired, target.product_id))

    @staticmethod
    def _is_supported_collection(info: dict[str, Any]) -> bool:
        path = info.get("path", b"")
        path_text = path.decode(errors="ignore") if isinstance(path, bytes) else str(path)
        return (
            int(info.get("product_id", -1)) in SUPPORTED_PRODUCT_IDS
            and int(info.get("interface_number", -1)) == CONTROL_INTERFACE
            and int(info.get("usage_page", -1)) == CONTROL_USAGE_PAGE
            and int(info.get("usage", -1)) == CONTROL_USAGE
            and "rzvirtual" not in path_text.lower()
        )

    def read_any(self, targets: Iterable[HidTarget]) -> BatterySnapshot:
        errors: list[str] = []
        for target in targets:
            try:
                return self.read_status(target)
            except (OSError, ProtocolError, DeviceUnavailable) as exc:
                errors.append(f"{target.connection_name} 0x{target.product_id:04x}: {exc}")
        detail = "; ".join(errors) if errors else "no supported HID collection found"
        raise DeviceUnavailable(detail)

    def read_status(self, target: HidTarget) -> BatterySnapshot:
        with self._query_lock:
            device = hid.device()
            try:
                device.open_path(target.path)
                battery_raw = self._query(device, BATTERY_COMMAND_ID).arguments[1]
                charging_raw = self._query(device, CHARGING_COMMAND_ID).arguments[1]
                if charging_raw not in (0, 1):
                    raise ProtocolError(f"invalid charging value {charging_raw}")
                return BatterySnapshot(
                    target=target,
                    battery_raw=battery_raw,
                    charging=bool(charging_raw),
                )
            except OSError as exc:
                raise DeviceUnavailable(str(exc)) from exc
            finally:
                device.close()

    @staticmethod
    def _query(device: Any, command_id: int) -> RazerResponse:
        request = build_request(command_id)
        last_error: Exception | None = None

        for attempt in range(MAX_QUERY_ATTEMPTS):
            try:
                bytes_written = device.send_feature_report(request)
                if bytes_written != len(request):
                    raise DeviceUnavailable(
                        f"short feature-report write ({bytes_written}/{len(request)})"
                    )
                time.sleep(RECEIVER_WAIT_SECONDS)
                raw_response = device.get_feature_report(0, FEATURE_REPORT_SIZE)
                response = parse_response(
                    raw_response,
                    expected_command_id=command_id,
                )
                if response.status == STATUS_SUCCESS:
                    return response
                if response.status == STATUS_BUSY:
                    last_error = ProtocolError("device busy")
                elif response.status == STATUS_TIMEOUT:
                    last_error = ProtocolError("device timed out")
                elif response.status == STATUS_NOT_SUPPORTED:
                    raise ProtocolError("command not supported")
                elif response.status == STATUS_FAILURE:
                    raise ProtocolError("command failed")
                else:
                    raise ProtocolError(
                        f"unknown response status 0x{response.status:02x}"
                    )
            except (OSError, ProtocolError, DeviceUnavailable) as exc:
                last_error = exc

            if attempt + 1 < MAX_QUERY_ATTEMPTS:
                time.sleep(0.050 * (attempt + 1))

        raise DeviceUnavailable(str(last_error or "query failed"))
