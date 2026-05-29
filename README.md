# Antigravity Installer

Small installer for Google Antigravity on Linux x64. It reads the current official download page, resolves the latest Linux x64 tarballs, and installs one or both products:

- `app`: Antigravity 2.0 desktop app
- `ide`: Antigravity IDE

This script was created because the legacy APT package named `antigravity` can lag behind the new Antigravity 2.0 product split and can conflict with the new `antigravity` command.

See also [`INSTALLATION.md`](./INSTALLATION.md) for the redacted OS, runtime, version, and install state captured during setup, [`INSTALL_NOTES.md`](./INSTALL_NOTES.md) for the installation narrative and troubleshooting history, and [`KNOWN_ISSUES.md`](./KNOWN_ISSUES.md) for current Linux-specific issues and workarounds.

## Current Machine Layout

On this machine, the preferred installation is system-wide:

- Antigravity app: `/opt/antigravity/Antigravity-x64`
- Antigravity IDE: `/opt/antigravity-ide/Antigravity-IDE`
- Command wrappers: `/usr/local/bin/antigravity`, `/usr/local/bin/antigravity-ide`
- Desktop entries: `/usr/share/applications/antigravity.desktop`, `/usr/share/applications/antigravity-ide.desktop`
- Icons: `/usr/share/icons/hicolor/512x512/apps/`

The installer also sets Electron `chrome-sandbox` to root-owned `4755` during system install. Command wrappers launch with `--ozone-platform=x11` to avoid GNOME Wayland/Vulkan startup issues observed on Ubuntu 24.04. The IDE wrapper calls the official `bin/antigravity-ide` CLI so `antigravity-ide .` returns control to the terminal after handing the request to the IDE.

## Requirements

- Ubuntu or another glibc-based Linux distribution
- x86_64 CPU
- Python 3.10+
- Network access to `https://antigravity.google/download`
- `sudo` for system-wide install

## Usage

Install both the IDE and the Antigravity 2.0 app system-wide:

```bash
cd ~/antigravity-installer
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
```

Install only the IDE:

```bash
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide
```

Install only the Antigravity 2.0 app:

```bash
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py app
```

User-local install is also supported when sudo is unavailable:

```bash
cd ~/antigravity-installer
./install.py ide app
```

User-local install writes to:

- `~/.local/opt/antigravity*`
- `~/.local/bin/antigravity*`
- `~/.local/share/applications/`
- `~/.local/share/icons/`

Make sure `~/.local/bin` appears before `/usr/bin` in `PATH` if a legacy APT package is still installed.

## Updating

Run the same install command again. The installer downloads the current official tarball and replaces the install root atomically enough for normal desktop use:

```bash
cd ~/antigravity-installer
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
```

When replacing an existing install, the previous install root is moved to a `.previous` sibling, for example:

- `/opt/antigravity.previous`
- `/opt/antigravity-ide.previous`

These can be removed manually after the new version is confirmed working.

## Verify

Check command wrappers:

```bash
which antigravity
which antigravity-ide
ls -l /usr/local/bin/antigravity /usr/local/bin/antigravity-ide
head -5 /usr/local/bin/antigravity /usr/local/bin/antigravity-ide
```

Check sandbox permissions:

```bash
ls -l /opt/antigravity/Antigravity-x64/chrome-sandbox
ls -l /opt/antigravity-ide/Antigravity-IDE/chrome-sandbox
```

Expected mode for system install is `-rwsr-xr-x` with owner `root root`.

Launch from terminal:

```bash
antigravity
antigravity-ide
```

If the App appears not to open while an existing background instance is present, restart only the App without touching the IDE:

```bash
antigravity-restart
```

For foreground debugging logs:

```bash
ANTIGRAVITY_FOREGROUND=1 antigravity --enable-logging=stderr --v=0
```

## User Data and Backups

The installer does not delete user data. Existing settings, sessions, browser profile data, and migration state may live under paths such as:

- `~/.config/Antigravity`
- `~/.cache/antigravity`
- `~/.gemini/antigravity`
- `~/.gemini/antigravity-cli`
- `~/.gemini/antigravity-browser-profile`
- `~/.antigravity-ide`

Before the first install on this machine, a backup was created at:

```text
<HOME>/antigravity-backups/antigravity-userdata-<BACKUP_TIMESTAMP>.tar.gz
```

Keep that backup until old conversations, projects, browser allowlists, auth state, and IDE settings are confirmed in the new versions.

## Legacy APT Package

The legacy package can be checked with:

```bash
apt-cache policy antigravity
```

If it is installed and you plan to use the new Antigravity 2.0 app as `antigravity`, remove the legacy package without purging user data:

```bash
sudo apt remove antigravity
```

Avoid `purge` unless you have reviewed what package-owned config files it would remove.

## Uninstall

System-wide uninstall of files created by this installer:

```bash
sudo rm -rf /opt/antigravity /opt/antigravity.previous \
  /opt/antigravity-ide /opt/antigravity-ide.previous \
  /usr/local/bin/antigravity /usr/local/bin/antigravity-ide \
  /usr/share/applications/antigravity.desktop \
  /usr/share/applications/antigravity-ide.desktop \
  /usr/share/icons/hicolor/512x512/apps/antigravity.png \
  /usr/share/icons/hicolor/512x512/apps/antigravity-ide.png
```

This does not remove user data under `~/.config`, `~/.cache`, `~/.gemini`, or `~/.antigravity-ide`.
