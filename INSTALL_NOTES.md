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

- The official download page changes shape without notice, so the script has to locate the Linux x64 download URLs at runtime rather than hardcode them.
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

## Download Page Rewrite Broke The Installer (2026-08-13)

Roughly seven weeks after the 2026-06-24 install, the installer stopped working entirely:

```text
Could not find the Antigravity download bundle
```

The download page had been rebuilt as an Astro static site. The original parser assumed a client-rendered frontend: it searched the HTML for a `main-*.js` bundle, fetched it, then sliced product sections out of the minified JavaScript using literal markers such as `id:"antigravity-2"`. The new page ships no `main-*.js` at all, so the very first step failed and nothing downstream ever ran.

Two things made this worse than a simple breakage:

- It failed silently in the sense that nobody noticed for seven weeks. The installed versions simply drifted (IDE `2.1.1` vs `2.5.2` upstream, App `2.1.4` vs `2.8.0`), and nothing surfaces that gap until someone runs the installer.
- The `ANTIGRAVITY_IDE_URL` escape hatch could not rescue it. `main()` fetched the bundle before `parse_download()` ever checked the override, so the override was unreachable precisely when it was needed.

The new page is easier to parse: the tarball URLs sit directly in the HTML as ordinary `href` attributes. The bundle indirection and the minified-JS section markers were deleted, and each product is now located by its existing `url_tail`, which is already unique per product:

```text
app: /linux-x64/Antigravity.tar.gz
ide: /linux-x64/Antigravity%20IDE.tar.gz
```

Note that the App tarball also moved hosts, from `edgedl.me.gvt1.com` to `storage.googleapis.com`, and its path segment changed from `antigravity` to `antigravity-hub`. Version extraction survived that unchanged because it matches the `<semver>-<build>` path segment rather than the host.

Changes made in response:

- Parse the download page HTML directly; drop `find_bundle_url()` and the `section_start` / `section_end` markers.
- Check URL overrides before any network request, and skip fetching the page entirely when every requested product has one. Overrides are validated up front so a bad URL fails before a download starts.
- Add `ANTIGRAVITY_APP_URL` so the App has the same escape hatch as the IDE.
- Extract tarballs with `filter="data"` where available, which blocks path traversal and removes the Python 3.14 default-change hazard. The filter strips setuid bits, but the installer sets `chrome-sandbox` to `4755` itself afterwards, so behaviour is unchanged.
- Add `tests/fixtures/download_page.html`, a trimmed excerpt of the real page, and cover the parser with it. The old code had zero coverage on this path, which is why the break went unnoticed.

The lesson worth keeping: the fragile part of this installer is not the install logic, it is the dependency on someone else's marketing page. That part needs both a test that pins the current shape and an override that works when the shape changes.

## Making It Usable Without A Clone (2026-08-13)

Fixing the parser exposed a second problem: knowing whether an update existed at all required cloning the repo and reading version markers by hand. Three things were added on top of the fix.

**`--check`.** Compares the recorded version in each install root against the download page and exits `1` if anything is stale, so it can drive a scheduled check. It deliberately looks in both the system and the user-local root, because a read-only report that answers "not installed" for something installed two directories over is worse than no report at all. That was the first implementation's actual behaviour and it had to be corrected.

**Skip when current, `--force` to override.** Re-running the installer used to re-download roughly 1.2 GB regardless. The version comparison only consults the root the run would write to, *not* the cross-mode lookup `--check` uses: a user-local install must never satisfy a system install request. There is a test pinning exactly that.

**`install.sh`.** A `curl … | sudo sh` bootstrap. Install mode is derived from whether it runs as root, which removes the awkward `curl … | sudo env ANTIGRAVITY_INSTALL_MODE=system sh`. It verifies the download is non-empty and starts with the expected shebang, which catches a proxy or error page being executed as Python.

The tradeoff is stated in `README.md` rather than hidden: piping a URL into a root shell runs whatever that URL serves at that moment, and `main` moves. Pinning a ref requires setting it in both the URL and `ANTIGRAVITY_INSTALLER_REF`, because `install.sh` fetches `install.py` separately.

## The Manager GUI

The GUI exists because reading version numbers is the most common reason to touch this repo, and that should not require a terminal.

**GTK, not tkinter.** tkinter is standard library, but no Python on this machine had it: neither the pyenv build nor the system one, and `python3-tk` was absent. PyGObject with GTK 3 was already present, being a system package on Ubuntu GNOME. So the GUI needs no extra install on the target machine, at the cost of not being importable from an arbitrary virtualenv.

That last part is a real trap: PyGObject lives in the system Python, while `python3` on a developer machine often points at pyenv or asdf. `gui.py` re-execs itself once under `/usr/bin/python3` when `import gi` fails, so it works either way.

**pkexec, not a root GUI.** Installing needs root for `/opt`, but running the whole window as root is the wrong shape. The GUI stays unprivileged and spawns `pkexec env ANTIGRAVITY_INSTALL_MODE=system python3 install.py …`, which produces the standard desktop authorisation dialog. `pkexec` exits `126` when that dialog is dismissed, which is reported as cancelled rather than failed.

**No duplicated logic.** Every version the GUI shows comes from calling `install.py`, and every install it performs shells out to `install.py`. The GUI cannot report something the CLI would not, because it has no version logic of its own.

**Its own icon.** `--install-gui` places `antigravity-manager.svg` in the hicolor theme. Reusing the Antigravity app icon was rejected: the manager would be indistinguishable from the app in the application menu, and the icon only exists once the app is installed. The shipped icon is optional, and a stock `system-software-install` is used when it is absent.

While wiring that up, a long-standing path bug surfaced: on system install, icons are written to `/usr/share/icons/hicolor` but `gtk-update-icon-cache` was being pointed at `/usr/local/share/icons/hicolor`. The cache for the directory actually written was never refreshed. Both now derive from one `ICON_THEME` constant.

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
4. Install everything, including the manager GUI, without cloning:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/raybird/antigravity-installer/main/install.sh \
     | sudo sh -s -- ide app --install-gui
   ```

   From a clone the equivalent is:

   ```bash
   sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app --install-gui
   ```

5. Verify wrappers, sandbox permissions, and startup. Afterwards `./install.py --check ide app` reports the state at any time without `sudo`.
6. If the IDE MCP page is empty, check whether the old config exists at `~/.gemini/antigravity/mcp_config.json` and whether the new config at `~/.gemini/config/mcp_config.json` is empty.

## IDE Open, App Appears Not To Open

A later observation was that after Antigravity IDE was already open, running `antigravity` could appear to do nothing.

Reproduction showed that IDE and App do not share the same Electron profile:

```text
~/.config/Antigravity IDE
~/.config/Antigravity
```

So this does not look like a direct profile lock conflict between IDE and App.

One possible explanation was Electron single-instance behavior for the App. If an App instance is already running in the background, running `antigravity` again can return immediately and only try to focus the existing window. That diagnosis is not confirmed, so the installer no longer creates a restart helper.

The App wrapper is also detached by default, so running this from a terminal returns immediately:

```bash
antigravity
```

For foreground debugging and logs, run:

```bash
ANTIGRAVITY_FOREGROUND=1 antigravity --enable-logging=stderr --v=0
```
