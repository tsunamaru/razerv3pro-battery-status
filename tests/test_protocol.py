from __future__ import annotations

import pytest

from razer_battery_status.protocol import (
    BATTERY_COMMAND_ID,
    CHARGING_COMMAND_ID,
    FEATURE_REPORT_SIZE,
    POWER_COMMAND_CLASS,
    STATUS_SUCCESS,
    TRANSACTION_ID,
    ProtocolError,
    build_request,
    calculate_crc,
    parse_response,
)


def make_response(command_id: int, value: int) -> bytes:
    payload = bytearray(FEATURE_REPORT_SIZE - 1)
    payload[0] = STATUS_SUCCESS
    payload[1] = TRANSACTION_ID
    payload[5] = 2
    payload[6] = POWER_COMMAND_CLASS
    payload[7] = command_id
    payload[9] = value
    payload[88] = calculate_crc(payload)
    return b"\x00" + bytes(payload)


def test_builds_battery_request() -> None:
    request = build_request(BATTERY_COMMAND_ID)

    assert len(request) == FEATURE_REPORT_SIZE
    assert request[0] == 0
    assert request[2] == TRANSACTION_ID
    assert request[6] == 2
    assert request[7:9] == bytes((POWER_COMMAND_CLASS, BATTERY_COMMAND_ID))
    assert request[89] == 0x85


def test_parses_charging_response() -> None:
    response = parse_response(
        make_response(CHARGING_COMMAND_ID, 1),
        expected_command_id=CHARGING_COMMAND_ID,
    )

    assert response.status == STATUS_SUCCESS
    assert response.arguments[1] == 1


def test_rejects_bad_checksum() -> None:
    response = bytearray(make_response(BATTERY_COMMAND_ID, 127))
    response[10] ^= 0x01

    with pytest.raises(ProtocolError, match="checksum"):
        parse_response(response, expected_command_id=BATTERY_COMMAND_ID)


def test_rejects_mismatched_command() -> None:
    with pytest.raises(ProtocolError, match="does not match"):
        parse_response(
            make_response(CHARGING_COMMAND_ID, 1),
            expected_command_id=BATTERY_COMMAND_ID,
        )


def test_rejects_short_response_payload() -> None:
    response = bytearray(make_response(BATTERY_COMMAND_ID, 127))
    response[6] = 1
    response[89] = calculate_crc(response[1:])

    with pytest.raises(ProtocolError, match="too short"):
        parse_response(response, expected_command_id=BATTERY_COMMAND_ID)
