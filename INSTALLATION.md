# Antigravity Installation Record

This file records the local machine state at the time Antigravity IDE and Antigravity 2.0 were installed.

It is a snapshot, not a live view. Run `./install.py --check ide app` for the current state.

## Installation Timestamp

- Date/time: `<INSTALL_TIMESTAMP>`
- Timezone: `<LOCAL_TIMEZONE>`
- Working directory used: `<HOME>`

## Operating System

- Distribution: `Ubuntu`
- Description: `Ubuntu 24.04.4 LTS`
- Release: `24.04`
- Codename: `noble`
- Architecture: `x86_64`

## Runtime Versions

- glibc / `ldd`: `2.39` (`Ubuntu GLIBC 2.39-0ubuntu8.7`)
- `libc6:amd64`: `2.39-0ubuntu8.8`
- `libc6:i386`: `2.39-0ubuntu8.8`
- `libstdc++6:amd64`: `14.2.0-4ubuntu2~24.04.1`
- `python3`: `3.12.3-0ubuntu2.1`

## Installed Antigravity Products

Versions recorded by this installer in `<install root>/.userlocal-version`:

- Antigravity 2.0 app: `2.8.0`
- Antigravity IDE: `2.5.2`
- Antigravity IDE product base version observed via `bin/antigravity-ide --version`: `1.107.0`

The first records of this machine showed `2.0.10` for the app and `stable` for the IDE. That `stable` was not a version: version extraction fell back to a path segment because the IDE download URL did not carry a `<semver>-<build>` component in the form the parser expected. Both products now resolve to real version numbers.

## Install Paths

- Antigravity app: `/opt/antigravity/Antigravity-x64`
- Antigravity IDE: `/opt/antigravity-ide/Antigravity-IDE`
- App command wrapper: `/usr/local/bin/antigravity` runs `/opt/antigravity/Antigravity-x64/antigravity --ozone-platform=x11`
- IDE command wrapper: `/usr/local/bin/antigravity-ide` runs `/opt/antigravity-ide/Antigravity-IDE/bin/antigravity-ide --ozone-platform=x11`
- App desktop entry: `/usr/share/applications/antigravity.desktop`
- IDE desktop entry: `/usr/share/applications/antigravity-ide.desktop`
- App icon: `/usr/share/icons/hicolor/512x512/apps/antigravity.png`
- IDE icon: `/usr/share/icons/hicolor/512x512/apps/antigravity-ide.png`

Previous install roots are kept as `.previous` siblings until removed by hand:

- `/opt/antigravity.previous`
- `/opt/antigravity-ide.previous`

## Manager GUI

Installed only when `--install-gui` is passed:

- Scripts and icon: `/usr/local/share/antigravity-installer/`
- Command: `/usr/local/bin/antigravity-manager`
- Desktop entry: `/usr/share/applications/antigravity-manager.desktop`
- Icon: `/usr/share/icons/hicolor/scalable/apps/antigravity-manager.svg`

## Sandbox State

Both Electron sandbox helpers were set to root-owned setuid mode during system install.

Expected state:

```text
-rwsr-xr-x root root /opt/antigravity/Antigravity-x64/chrome-sandbox
-rwsr-xr-x root root /opt/antigravity-ide/Antigravity-IDE/chrome-sandbox
```

## Legacy Package State

The legacy APT package was removed without purge.

Observed after removal:

```text
antigravity:
  Installed: (none)
  Candidate: 1.23.2-1776332190
```

The old APT repository still exposes `1.23.2-1776332190`, so reinstalling from APT would bring back the legacy package and may recreate `/usr/bin/antigravity`.

## User Data Backup

Before migration/install, existing Antigravity user data was backed up to:

```text
<HOME>/antigravity-backups/antigravity-userdata-<BACKUP_TIMESTAMP>.tar.gz
```

Backup size observed: `1.1G`.

Included paths:

- `<HOME>/.config/Antigravity`
- `<HOME>/.cache/antigravity`
- `<HOME>/.gemini/antigravity`
- `<HOME>/.gemini/antigravity-cli`
- `<HOME>/.gemini/antigravity-browser-profile`

## Initial Launch Notes

These were recorded during the first install, when the app was `2.0.10`.

Both binaries were smoke-tested by launching them under `timeout`.

Observed App startup:

- App version printed in logs: `v2.0.10`
- Local server started on a dynamic `https://127.0.0.1:<port>/`
- Logs path: `<HOME>/.config/Antigravity/logs/`

Observed IDE startup/migration messages:

- Secure mode migration from agent preferences to override store ran.
- OAuth token migration from legacy state sync ran and found no agent manager init state.
- Browser allowlist migration from `browserAllowlist.txt` ran.
- Sidebar workspace migration ran and found no agent manager init state.
- Artifact review migration ran and found no agent manager init state.

No Antigravity background processes were left running after the smoke tests.
