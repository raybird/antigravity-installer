# Known Issues

This file records observed Antigravity Linux issues and local workarounds.

## Antigravity App Does Not Relaunch Reliably After Close/Quit

### Status

Open upstream issue / local workaround only.

This appears to be an Antigravity 2.0 Linux app lifecycle issue. It has not been fully fixed locally; the current repo only provides safer launch helpers.

### Environment Observed

- Ubuntu 24.04.x
- GNOME on Wayland
- Antigravity 2.0 app installed from official Linux x64 tarball
- Antigravity IDE installed separately from official Linux x64 tarball
- App launched through `/usr/local/bin/antigravity`
- IDE launched through `/usr/local/bin/antigravity-ide`

### Symptoms

After opening Antigravity IDE, or after closing/quitting Antigravity App, launching the App again may appear to do nothing.

Observed cases:

- Running `antigravity` returns immediately but no visible App window appears.
- Running `antigravity .` from a project directory does not open that directory in the App.
- Closing the App window and launching again can fail to show a window.
- Using the tray icon `Quit` and launching again can still fail to show a window.

### What Was Ruled Out

This does not look like a direct IDE/App profile lock conflict.

The App and IDE use separate Electron user-data profiles:

```text
~/.config/Antigravity
~/.config/Antigravity IDE
```

The IDE can remain open while the App starts successfully when the App is launched from a clean process state.

MCP config migration also does not appear to be the cause. The App and IDE can start with valid MCP config present.

### Likely Cause

The likely cause is App lifecycle / single-instance / tray quit behavior on Linux.

Observed behavior suggests:

```text
Close window or tray Quit does not always leave the app in a clean relaunchable state.
Relaunching antigravity may hand off to an existing/stale single-instance process.
That stale process does not reliably restore or show a visible window.
```

This means `antigravity` may successfully return at the process level while the user sees no App window.

### `antigravity .` Is Not Reliable

`antigravity-ide` has an explicit CLI interface and supports path arguments:

```bash
antigravity-ide .
```

The App command does not appear to provide equivalent folder-opening CLI behavior:

```bash
antigravity .
```

In practice, the `.` argument appears to be ignored or only participates in Electron single-instance handoff. Use the App UI to select/create projects, and use `antigravity-ide .` when the goal is to open a repository in the IDE.

### Current Workaround

No restart helper is currently installed because the stale-process diagnosis is not confirmed.

For foreground debugging:

```bash
ANTIGRAVITY_FOREGROUND=1 antigravity --enable-logging=stderr --v=0
```

### Upstream Expectation

A proper upstream fix should make these paths reliable on Linux:

- Window close vs application quit semantics.
- Tray `Quit` fully terminating App state.
- Relaunch showing a visible App window.
- Single-instance handoff restoring/focusing the existing App window.
- Optional CLI documentation clarifying whether `antigravity .` is supported.
