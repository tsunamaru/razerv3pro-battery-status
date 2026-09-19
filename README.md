# Razer Battery Status

A headless Windows monitor for the Razer DeathAdder V3 Pro. It talks directly
to the mouse through HID feature reports and does not depend on Razer Synapse.

There is no window, tray icon, or configuration file. It produces Windows
notifications for:

- battery below 10% while discharging;
- a silent charging transition ("connected");
- a silent discharging transition ("disconnected");
- a silent notification when charging reaches 100%.

The low-battery alert keeps the normal Windows notification sound.

Mouse sleep and temporary HID errors are treated as unknown state, not as a
disconnect.

## Commands

Install the locked environment and run the tests:

```powershell
uv sync --dev
uv run pytest
```

Read the current status once:

```powershell
uv run razer-battery-status once
```

Test Windows notifications:

```powershell
uv run razer-battery-status notify-test
```

Run the monitor in the foreground:

```powershell
uv run razer-battery-status monitor
```

Install and start the per-user logon task (the environment must already have
been created with `uv sync`):

```powershell
.\scripts\install-startup.ps1
```

Disable Synapse auto-start while preserving its original command in a backup
registry value:

```powershell
.\scripts\disable-synapse-startup.ps1
```

Restore Synapse auto-start later if needed:

```powershell
.\scripts\restore-synapse-startup.ps1
```

Remove the task:

```powershell
.\scripts\uninstall-startup.ps1
```

The scheduled task runs `.venv\Scripts\pythonw.exe` directly. `uv` owns and
locks that environment, while the background process has no console window.

Diagnostic logs are capped and stored at
`%LOCALAPPDATA%\razer-battery-status\monitor.log`.

## Synapse coexistence

Razer Synapse and this monitor use the same request/response channel. If
`RazerAppEngine.exe` is running, the mouse can return timeouts or a response
intended for the other process. Close Synapse and disable its auto-start (or
uninstall it) before relying on the monitor. The monitor process never starts,
stops, or reconfigures Synapse itself; the explicit helper script above only
moves the current user's startup command to a recoverable backup value.

The Razer services and device packages may remain installed; this program uses
the standard Windows HID API and does not call those services.
