# Installation Notes

This document records the practical installation path, decisions, and problems encountered while setting up Google Antigravity IDE and Antigravity 2.0 on Ubuntu.

The goal is not to be a perfect official guide. It is a field note for future agents or maintainers who need to understand why this repository installs Antigravity the way it does.

## Starting Point

The machine already had a legacy APT package named `antigravity` installed. That package exposed `/usr/bin/antigravity` and reported version `1.23.2-*` from the old APT repository.

The new Antigravity product split is different:

- Antigravity 2.0 app uses the `antigravity` command.
- Antigravity IDE uses the `antigravity-ide` command.
- The official download page currently provides tarballs rather than the old APT package path for the new split.

Because of the command conflict, the legacy APT package was removed without purge. User data was backed up before migration.

## Backup First

Before changing packages or writing new config, existing Antigravity/Gemini user data was archived. The public docs use placeholders for the exact local path and timestamp:

```text
<HOME>/antigravity-backups/antigravity-userdata-<BACKUP_TIMESTAMP>.tar.gz
```

The backup included paths like:

```text
<HOME>/.config/Antigravity
<HOME>/.cache/antigravity
<HOME>/.gemini/antigravity
<HOME>/.gemini/antigravity-cli
<HOME>/.gemini/antigravity-browser-profile
```

This mattered because 2.0 migrates some state, but not every old workspace/conversation/config location is guaranteed to map one-to-one.

## Installer Shape

The installer was written as a small standard-library Python script rather than a shell-only script.

Reasons:

- The official download page is a frontend app; the script has to resolve the current JavaScript bundle and extract Linux x64 download URLs.
- The download page may return gzip-compressed HTML, so the fetch logic handles gzip explicitly.
- The App and IDE tarballs have different layouts.
- The IDE archive top-level directory contains a space, so the installer normalizes it to `Antigravity-IDE` for stable paths.
- Desktop files, icons, command wrappers, sandbox permissions, and install roots are easier to manage carefully in Python.

The installer supports two modes:

- System install: `/opt`, `/usr/local/bin`, `/usr/share/applications`, `/usr/share/icons`
- User-local install: `~/.local/opt`, `~/.local/bin`, `~/.local/share/applications`, `~/.local/share/icons`

System mode is selected with:

```bash
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
```

## Sandbox Handling

Electron apps need a working sandbox setup on Linux. During system install, the installer sets `chrome-sandbox` to root-owned setuid mode:

```text
-rwsr-xr-x root root .../chrome-sandbox
```

This avoids having to launch with `--no-sandbox` on Ubuntu 24.04.

## Icon Extraction

The App tarball stores its icon in `resources/app.asar`, so the installer includes a minimal ASAR reader to extract `icon.png`.

The IDE tarball does not use the same `resources/app.asar` layout. For IDE, the installer falls back to:

```text
resources/app/resources/linux/code.png
```

This is why the icon code has two paths.

## MCP Migration

After installing the new IDE, the MCP UI initially appeared empty. The IDE was looking at:

```text
~/.gemini/config/mcp_config.json
```

That file existed but was `0 bytes`, so the empty UI was expected.

The old MCP config existed at:

```text
~/.gemini/antigravity/mcp_config.json
```

It used the standard `mcpServers` object and contained four server entries:

```text
serena
mcp-memory-libsql
gitnexus
chrome-devtools
```

The old config was copied to the new path and both files were tightened to mode `600`, because MCP config can contain environment variables or credentials.

The original empty file was backed up with an `.empty-<timestamp>.bak` suffix.

## App Startup Problem

After migration, Antigravity 2.0 appeared to fail to open. Logs showed the app and language server were actually starting, but Ubuntu crash reports also existed under `/var/crash`.

The important terminal warning was:

```text
'--ozone-platform=wayland' is not compatible with Vulkan. Consider switching to '--ozone-platform=x11' or disabling Vulkan
```

The machine was running GNOME on Wayland. The workaround was to launch Antigravity with X11 ozone:

```bash
--ozone-platform=x11
```

A first attempt also used `--disable-vulkan`, but Antigravity IDE reported:

```text
Warning: 'disable-vulkan' is not in the list of known options, but still passed to Electron/Chromium.
```

Because that flag was noisy and unnecessary after switching to X11 ozone, it was removed.

The remaining warning:

```text
GetVSyncParametersIfAvailable() failed
```

has been observed under Chromium/X11 and is treated as non-fatal when the app window opens and the language server starts.

## Wrapper Launcher Design

The first working launcher used `/usr/local/bin` symlinks directly to the installed binaries. That was too fragile for two reasons.

First, editing a symlink path with `tee` writes through to the target binary. This briefly overwrote the installed executable with a shell wrapper. The fix was to rerun the installer and restore the tarball contents, then replace the symlink with a real wrapper file.

Second, launching Antigravity IDE by directly executing the Electron binary caused `antigravity-ide .` to keep the terminal attached to the GUI process.

The final design is:

```text
/usr/local/bin/antigravity
  -> shell wrapper that execs /opt/antigravity/Antigravity-x64/antigravity --ozone-platform=x11 "$@"

/usr/local/bin/antigravity-ide
  -> shell wrapper that execs /opt/antigravity-ide/Antigravity-IDE/bin/antigravity-ide --ozone-platform=x11 "$@"
```

Using the IDE's official `bin/antigravity-ide` CLI wrapper is important. It lets commands like this return control to the terminal after handing the request to the IDE:

```bash
antigravity-ide .
```

## Version Drift During Setup

During the initial install, the App resolved to `2.0.6`. During a later reinstall, the official download page resolved to `2.0.10`.

This is expected because the installer intentionally resolves the latest available URLs from the official page at runtime.

`INSTALLATION.md` records the public, redacted current observed state. `INSTALLATION.local.md` may exist locally for exact machine-specific values and is ignored by git.

## Repository Hygiene

This repo is intended to be public-safe.

Public files use placeholders such as:

```text
<HOME>
<LOCAL_TIMEZONE>
<INSTALL_TIMESTAMP>
<BACKUP_TIMESTAMP>
```

The following should not be committed:

- `INSTALLATION.local.md`
- machine-specific backup paths or timestamps
- local MCP databases such as `mcp-memory-libsql.db`
- sudo passwords
- OAuth tokens
- API keys
- SSH/private keys
- browser/session data

A local MCP memory server created `mcp-memory-libsql.db` in the repo directory during debugging. It was added to `.gitignore` and should remain untracked.

## Current Recommended Flow

For another Ubuntu x86_64 machine:

1. Read `README.md` and `AGENTS.md`.
2. Back up existing Antigravity/Gemini user data if present.
3. Remove legacy APT `antigravity` without purge if it owns the old command.
4. Run:

   ```bash
   sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
   ```

5. Verify wrappers, sandbox permissions, and startup.
6. If the IDE MCP page is empty, check whether the old config exists at `~/.gemini/antigravity/mcp_config.json` and whether the new config at `~/.gemini/config/mcp_config.json` is empty.

## IDE Open, App Appears Not To Open

A later observation was that after Antigravity IDE was already open, running `antigravity` could appear to do nothing.

Reproduction showed that IDE and App do not share the same Electron profile:

```text
~/.config/Antigravity IDE
~/.config/Antigravity
```

So this does not look like a direct profile lock conflict between IDE and App.

The more likely explanation is Electron single-instance behavior for the App. If an App instance is already running in the background, running `antigravity` again can return immediately and only try to focus the existing window. If that window is hidden, on another workspace, or in a bad state, it looks like the App failed to open.

To make this easier to recover from, the installer creates:

```bash
antigravity-restart
```

That helper kills only the Antigravity 2.0 App process and its standalone App language server, then starts the App again. It intentionally does not kill Antigravity IDE.

The App wrapper is also detached by default, so running this from a terminal returns immediately:

```bash
antigravity
```

For foreground debugging and logs, run:

```bash
ANTIGRAVITY_FOREGROUND=1 antigravity --enable-logging=stderr --v=0
```
