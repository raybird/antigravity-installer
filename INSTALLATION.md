# Antigravity Installation Record

This file records the local machine state at the time Antigravity IDE and Antigravity 2.0 were installed.

## Installation Timestamp

- Date/time: `2026-05-29T09:35:30+08:00`
- Timezone: `Asia/Taipei`
- Working directory used: `/home/kevin`

## Operating System

- Distribution: `Ubuntu`
- Description: `Ubuntu 24.04.4 LTS`
- Release: `24.04`
- Codename: `noble`
- Architecture: `x86_64`

## Runtime Versions

- glibc / `ldd`: `2.39` (`Ubuntu GLIBC 2.39-0ubuntu8.7`)
- `libc6:amd64`: `2.39-0ubuntu8.7`
- `libc6:i386`: `2.39-0ubuntu8.7`
- `libstdc++6:amd64`: `14.2.0-4ubuntu2~24.04.1`
- `python3`: `3.12.3-0ubuntu2.1`

## Installed Antigravity Products

- Antigravity 2.0 app download marker: `2.0.6`
- Antigravity IDE download marker: `stable`
- Antigravity IDE product base version observed in `product.json`: `1.107.0`

## Install Paths

- Antigravity app: `/opt/antigravity/Antigravity-x64`
- Antigravity IDE: `/opt/antigravity-ide/Antigravity-IDE`
- App command: `/usr/local/bin/antigravity -> /opt/antigravity/Antigravity-x64/antigravity`
- IDE command: `/usr/local/bin/antigravity-ide -> /opt/antigravity-ide/Antigravity-IDE/antigravity-ide`
- App desktop entry: `/usr/share/applications/antigravity.desktop`
- IDE desktop entry: `/usr/share/applications/antigravity-ide.desktop`
- App icon: `/usr/share/icons/hicolor/512x512/apps/antigravity.png`
- IDE icon: `/usr/share/icons/hicolor/512x512/apps/antigravity-ide.png`

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
/home/kevin/antigravity-backups/antigravity-userdata-20260529-092007.tar.gz
```

Backup size observed: `1.1G`.

Included paths:

- `/home/kevin/.config/Antigravity`
- `/home/kevin/.cache/antigravity`
- `/home/kevin/.gemini/antigravity`
- `/home/kevin/.gemini/antigravity-cli`
- `/home/kevin/.gemini/antigravity-browser-profile`

## Initial Launch Notes

Both binaries were smoke-tested by launching them under `timeout`.

Observed App startup:

- App version printed in logs: `v2.0.6`
- Local server started on a dynamic `https://127.0.0.1:<port>/`
- Logs path: `/home/kevin/.config/Antigravity/logs/`

Observed IDE startup/migration messages:

- Secure mode migration from agent preferences to override store ran.
- OAuth token migration from legacy state sync ran and found no agent manager init state.
- Browser allowlist migration from `browserAllowlist.txt` ran.
- Sidebar workspace migration ran and found no agent manager init state.
- Artifact review migration ran and found no agent manager init state.

No Antigravity background processes were left running after the smoke tests.
