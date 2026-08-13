# Agent Instructions

This repository contains a Linux installer and installation record for Google Antigravity IDE and Antigravity 2.0.

## Primary Files

- `README.md`: user-facing usage, update, verify, and uninstall instructions.
- `INSTALLATION.md`: public, redacted machine-state example using placeholders.
- `INSTALL_NOTES.md`: public installation narrative, decisions, and troubleshooting history.
- `KNOWN_ISSUES.md`: public list of observed Linux-specific issues and workarounds.
- `INSTALLATION.local.md`: local-only machine record. This file is ignored by git and must not be committed.
- `install.py`: installer script.
- `install.sh`: bootstrap for `curl … | sudo sh`. Fetches `install.py` from this repo and runs it, so its default ref (`main`) must always hold a working `install.py`.

## Fresh Ubuntu Checklist

For a fresh Ubuntu x86_64 machine:

1. Read `README.md` first.
2. Confirm the machine is x86_64 and has Python 3.10+.
3. Check whether a legacy APT package is installed:

   ```bash
   apt-cache policy antigravity
   ```

4. If the legacy package is installed and the new Antigravity 2.0 app should own the `antigravity` command, remove it without purging user data:

   ```bash
   sudo apt remove antigravity
   ```

5. Before migration or reinstall, back up existing user data if any of these paths exist:

   ```text
   ~/.config/Antigravity
   ~/.cache/antigravity
   ~/.gemini/antigravity
   ~/.gemini/antigravity-cli
   ~/.gemini/antigravity-browser-profile
   ~/.antigravity-ide
   ```

6. Install system-wide:

   ```bash
   sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
   ```

7. Verify command wrappers:

   ```bash
   which antigravity
   which antigravity-ide
   ls -l /usr/local/bin/antigravity /usr/local/bin/antigravity-ide
   head -5 /usr/local/bin/antigravity /usr/local/bin/antigravity-ide
   ```

8. Verify Electron sandbox permissions:

   ```bash
   ls -l /opt/antigravity/Antigravity-x64/chrome-sandbox
   ls -l /opt/antigravity-ide/Antigravity-IDE/chrome-sandbox
   ```

   Expected owner/mode for system install: `root root` and `-rwsr-xr-x`.

9. Launch smoke tests only if a GUI/session is available:

   ```bash
   antigravity
   antigravity-ide
   ```

   For foreground App debugging logs, use:

   ```bash
   ANTIGRAVITY_FOREGROUND=1 antigravity --enable-logging=stderr --v=0
   ```

10. Check that no stray processes remain after any automated smoke test:

    ```bash
    pgrep -af 'Antigravity|antigravity|language_server'
    ```

## Update Flow

First check whether an update is even needed. This touches nothing and needs no `sudo`:

```bash
./install.py --check ide app
```

Exit status is `0` when everything is current, `1` when any product is stale or missing.

To update both products, run the same installer command again:

```bash
sudo env ANTIGRAVITY_INSTALL_MODE=system ./install.py ide app
```

Quit a running Antigravity app or IDE before updating it, and never run the update from a terminal hosted inside the IDE being replaced. The install root is swapped underneath the running process, so lazily loaded resources start resolving to the new version.

The installer moves the old install roots to `.previous` siblings, such as `/opt/antigravity.previous` and `/opt/antigravity-ide.previous`.

After confirming the new version works, the `.previous` directories may be removed manually.

## Repository Hygiene

- Do not commit `INSTALLATION.local.md`.
- Do not commit machine-specific absolute home paths, backup timestamps, usernames, emails, hostnames, or credentials.
- Use placeholders such as `<HOME>`, `<LOCAL_TIMEZONE>`, `<INSTALL_TIMESTAMP>`, and `<BACKUP_TIMESTAMP>` in public docs.
- Never write sudo passwords, API keys, OAuth tokens, SSH keys, or browser/session data into this repository.
- Keep `install.py` standard-library only unless there is a strong reason to add dependencies.
- After edits, run:

  ```bash
  python3 -m py_compile install.py
  python3 -m unittest discover -s tests
  git status --short
  ```

## Download Page Parsing

`install.py` resolves tarball URLs by reading `https://antigravity.google/download` and matching `href="…<url_tail>"` for each product. This is the most fragile part of the installer: it depends on the shape of a page nobody here controls, and a silent break leaves the machine unable to update.

Rules for changing it:

- `tests/fixtures/download_page.html` is a trimmed excerpt of the real page. When the page changes, capture a fresh excerpt and update the fixture and the expected versions in `tests/test_install_config.py` together.
- Keep the fixture authentic. Do not hand-write idealized markup; copy the real `<li>`/`<a>` elements.
- Every product must keep a `url_override_env`. That override is the escape hatch when the page breaks, so it must never depend on the page being parseable.

## Git Notes

This repo may use a local git identity different from the machine global identity. Check local config before committing:

```bash
git config --local --get user.name
git config --local --get user.email
```
