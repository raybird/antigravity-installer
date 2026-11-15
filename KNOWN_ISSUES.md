# Known Issues

This file records observed Antigravity Linux issues and local workarounds.

## Manager Shows a Gear Icon or gui.py

The manager identity was fixed in `v1.1.1`. Older installed copies may still identify their Wayland windows using the Python script name, so the desktop cannot match the window to `antigravity-manager.desktop`, even when the SVG is installed.

Update the system manager from an updated clone:

```bash
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py --install-gui
```

Using only `sudo ./install.py --install-gui` does not select system mode and may update a copy under root's home instead. Updating a clone also does not refresh an installed copy by itself.

Close existing manager windows and launch **Antigravity Manager** from the application menu. If a previously pinned gear entry remains, remove that pin and pin the manager's application-menu entry again.

For a system installation, these read-only checks confirm the identity settings and icon copies:

```bash
grep -nE 'set_prgname|set_program_class' /usr/local/share/antigravity-installer/gui.py
grep -E '^(Name|Exec|Icon|StartupWMClass)=' /usr/share/applications/antigravity-manager.desktop
sha256sum antigravity-manager.svg \
  /usr/local/share/antigravity-installer/antigravity-manager.svg \
  /usr/share/icons/hicolor/scalable/apps/antigravity-manager.svg
```

Run the checksum command from the updated clone. The identity values should use `antigravity-manager`, and all three SVG checksums should match. User-local installations use the corresponding paths under `~/.local`.

## Manager Stops at the Post-install Version Check

Fixed in `v1.1.1`. The success handler previously called refresh while the manager was still busy, causing the refresh request to be ignored. Update the manager using the command above.

Since `v1.2.0`, a progress bar shows the download percentage and transferred size when available. Unknown download sizes and installation stages use an animated indicator. After installation, the manager checks versions again; if that network check fails, the UI reports that installation completed but version checking failed, and the refresh button becomes available for retry.

## Antigravity App Does Not Relaunch Reliably After Close/Quit

### Status

Open upstream issue / local workaround only. **Not re-verified on current versions.**

This appears to be an Antigravity 2.0 Linux app lifecycle issue. It has not been fully fixed locally; the current repo only provides safer launch helpers.

Everything below was observed on app `2.0.x`. The app has since moved several minor versions, and the behaviour has not been retested, so treat this as history rather than a current defect report. If it no longer reproduces, delete this section instead of leaving it to rot.

### Environment Observed

- Ubuntu 24.04.x
- GNOME on Wayland
- Antigravity 2.0 app `2.0.x` installed from official Linux x64 tarball
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
