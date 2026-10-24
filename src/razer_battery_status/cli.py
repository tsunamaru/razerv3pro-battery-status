from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .hid_backend import DeviceUnavailable, HidBackend
from .monitor import BatteryMonitor
from .notifications import send_test_notification

MUTEX_NAME = "Local\\RazerBatteryStatusMonitor"
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self) -> None:
        self.handle: int | None = None

    def __enter__(self) -> SingleInstance:
        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self.handle:
            raise OSError("could not create monitor mutex")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(self.handle)
            self.handle = None
            raise RuntimeError("the battery monitor is already running")
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None


def configure_logging(*, console: bool) -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    log_dir = local_app_data / "razer-battery-status"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "monitor.log"

    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_path,
            maxBytes=256 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
    ]
    if console:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_path


def read_once() -> int:
    backend = HidBackend()
    targets = backend.enumerate_targets()
    try:
        snapshot = backend.read_any(targets)
    except DeviceUnavailable as exc:
        print(f"Battery status unavailable: {exc}", file=sys.stderr)
        return 2

    state = "charging" if snapshot.charging else "discharging"
    print(
        f"Battery: {snapshot.display_percent}% ({snapshot.battery_raw}/255) | "
        f"{state} | {snapshot.target.connection_name} | "
        f"VID_1532/PID_{snapshot.target.product_id:04X}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Headless battery alerts for a Razer DeathAdder V3 Pro"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="once",
        choices=("once", "monitor", "notify-test"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(console=args.command != "monitor")

    if args.command == "once":
        return read_once()
    if args.command == "notify-test":
        send_test_notification()
        print("Test notification sent.")
        return 0

    try:
        with SingleInstance():
            BatteryMonitor().run()
    except RuntimeError as exc:
        logging.getLogger(__name__).info("%s", exc)
        return 0
    except KeyboardInterrupt:
        return 0
    return 0
