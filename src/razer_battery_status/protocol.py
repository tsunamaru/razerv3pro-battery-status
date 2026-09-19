from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from operator import xor


REPORT_ID = 0x00
REPORT_SIZE = 90
FEATURE_REPORT_SIZE = REPORT_SIZE + 1
TRANSACTION_ID = 0x1F
POWER_COMMAND_CLASS = 0x07
BATTERY_COMMAND_ID = 0x80
CHARGING_COMMAND_ID = 0x84

STATUS_BUSY = 0x01
STATUS_SUCCESS = 0x02
STATUS_FAILURE = 0x03
STATUS_TIMEOUT = 0x04
STATUS_NOT_SUPPORTED = 0x05


class ProtocolError(RuntimeError):
    """The mouse returned an invalid or unexpected Razer report."""


def calculate_crc(report: bytes | bytearray) -> int:
    if len(report) != REPORT_SIZE:
        raise ValueError(f"expected {REPORT_SIZE} report bytes, got {len(report)}")
    return reduce(xor, report[2:88], 0)


def build_request(command_id: int) -> bytes:
    report = bytearray(REPORT_SIZE)
    report[1] = TRANSACTION_ID
    report[5] = 0x02
    report[6] = POWER_COMMAND_CLASS
    report[7] = command_id
    report[88] = calculate_crc(report)
    return bytes([REPORT_ID]) + bytes(report)


@dataclass(frozen=True)
class RazerResponse:
    status: int
    transaction_id: int
    remaining_packets: int
    protocol_type: int
    data_size: int
    command_class: int
    command_id: int
    arguments: bytes


def parse_response(
    data: bytes | bytearray,
    *,
    expected_command_id: int,
) -> RazerResponse:
    raw = bytes(data)
    if len(raw) == FEATURE_REPORT_SIZE:
        if raw[0] != REPORT_ID:
            raise ProtocolError(f"unexpected report id 0x{raw[0]:02x}")
        raw = raw[1:]
    elif len(raw) != REPORT_SIZE:
        raise ProtocolError(
            f"expected {REPORT_SIZE} or {FEATURE_REPORT_SIZE} bytes, got {len(raw)}"
        )

    if calculate_crc(raw) != raw[88]:
        raise ProtocolError("response checksum mismatch")
    if raw[1] != TRANSACTION_ID:
        raise ProtocolError(f"unexpected transaction id 0x{raw[1]:02x}")
    if int.from_bytes(raw[2:4], "big") != 0:
        raise ProtocolError("multi-packet responses are not supported")
    if raw[4] != 0:
        raise ProtocolError(f"unexpected protocol type 0x{raw[4]:02x}")
    if raw[5] < 2:
        raise ProtocolError(f"response payload is too short ({raw[5]} bytes)")
    if raw[6] != POWER_COMMAND_CLASS or raw[7] != expected_command_id:
        raise ProtocolError(
            "response command does not match request "
            f"(0x{raw[6]:02x}/0x{raw[7]:02x})"
        )

    return RazerResponse(
        status=raw[0],
        transaction_id=raw[1],
        remaining_packets=int.from_bytes(raw[2:4], "big"),
        protocol_type=raw[4],
        data_size=raw[5],
        command_class=raw[6],
        command_id=raw[7],
        arguments=raw[8:88],
    )
