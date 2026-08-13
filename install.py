#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import gzip
import urllib.request
from pathlib import Path


DOWNLOAD_PAGE = "https://antigravity.google/download"
HOME = Path.home()
SYSTEM_INSTALL = os.environ.get("ANTIGRAVITY_INSTALL_MODE") == "system"
LOCAL = Path("/usr/local") if SYSTEM_INSTALL else HOME / ".local"
BIN = Path("/usr/local/bin") if SYSTEM_INSTALL else LOCAL / "bin"
OPT = Path("/opt") if SYSTEM_INSTALL else LOCAL / "opt"
APPS = Path("/usr/share/applications") if SYSTEM_INSTALL else LOCAL / "share" / "applications"
ICON_THEME = (
    Path("/usr/share/icons/hicolor")
    if SYSTEM_INSTALL
    else LOCAL / "share" / "icons" / "hicolor"
)
ICONS = ICON_THEME / "512x512" / "apps"


PRODUCTS = {
    "app": {
        "archive_name": "Antigravity.tar.gz",
        "url_tail": "/linux-x64/Antigravity.tar.gz",
        "url_override_env": "ANTIGRAVITY_APP_URL",
        "expected_top": "Antigravity-x64",
        "install_root": OPT / "antigravity",
        "command": BIN / "antigravity",
        "desktop": APPS / "antigravity.desktop",
        "icon": ICONS / "antigravity.png",
        "name": "Antigravity",
        "comment": "Google Antigravity 2.0 agent platform",
        "startup_wm_class": "Antigravity",
        "binary": "antigravity",
    },
    "ide": {
        "archive_name": "Antigravity-IDE.tar.gz",
        "url_tail": "/linux-x64/Antigravity%20IDE.tar.gz",
        "url_override_env": "ANTIGRAVITY_IDE_URL",
        "expected_top": "Antigravity IDE",
        "install_top": "Antigravity-IDE",
        "install_root": OPT / "antigravity-ide",
        "command": BIN / "antigravity-ide",
        "desktop": APPS / "antigravity-ide.desktop",
        "icon": ICONS / "antigravity-ide.png",
        "name": "Antigravity IDE",
        "comment": "Google Antigravity IDE",
        "startup_wm_class": "Antigravity IDE",
        "binary": "antigravity-ide",
        "command_binary": "bin/antigravity-ide",
    },
}

LEGACY_APP_RESTART_COMMAND = BIN / "antigravity-restart"

# Written into each install root so --check can compare against the download page.
VERSION_MARKER = ".userlocal-version"

# The install root of the mode this run is *not* using. --check looks in both so
# it reports the truth without needing ANTIGRAVITY_INSTALL_MODE to be set.
ALT_OPT = HOME / ".local" / "opt" if SYSTEM_INSTALL else Path("/opt")

# --install-gui copies gui.py and install.py here, so the launcher keeps working
# after the directory this script was run from is gone.
GUI_DATA = LOCAL / "share" / "antigravity-installer"
GUI_COMMAND = BIN / "antigravity-manager"
GUI_DESKTOP = APPS / "antigravity-manager.desktop"
GUI_ICON_FILE = "antigravity-manager.svg"
# gui.py falls back to this interpreter when the one on PATH cannot import gi.
SYSTEM_PYTHON = "/usr/bin/python3"
GUI_ICON = ICON_THEME / "scalable" / "apps" / GUI_ICON_FILE
# Used when the SVG is not alongside install.py; every icon theme ships this one.
GUI_ICON_FALLBACK = "system-software-install"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = res.read()
        if data.startswith(b"\x1f\x8b") or res.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode("utf-8", errors="replace")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as res, dest.open("wb") as out:
        shutil.copyfileobj(res, out)


def override_url(product: str) -> str | None:
    """Return the user-supplied tarball URL for a product, if one is set."""
    cfg = PRODUCTS[product]
    env = cfg["url_override_env"]
    url = os.environ.get(env)
    if not url:
        return None
    if cfg["url_tail"] not in url:
        raise SystemExit(f"{env} does not look like a {cfg['name']} Linux x64 tarball URL")
    return url


def extract_download_version(url: str) -> str:
    version_match = re.search(r'/([0-9]+\.[0-9]+\.[0-9]+)-[^/]+/', url)
    if version_match:
        return version_match.group(1)
    version_match = re.search(r'/antigravity(?:-hub|-ide)?/([^/]+)/', url)
    return version_match.group(1).split("-", 1)[0] if version_match else "unknown"


def parse_download(page: str, product: str) -> tuple[str, str]:
    cfg = PRODUCTS[product]
    url = override_url(product)
    if url:
        return extract_download_version(url), url

    tail = re.escape(cfg["url_tail"])
    matches = re.findall(r'href="(https://[^"]+' + tail + r'(?:[?#][^"]*)?)"', page)
    urls = list(dict.fromkeys(html.unescape(match) for match in matches))
    if not urls:
        raise SystemExit(
            f"Could not find the Linux x64 download for {product} on {DOWNLOAD_PAGE}. "
            f"The page layout may have changed; set {cfg['url_override_env']} "
            f"to the tarball URL to install anyway."
        )
    if len(urls) > 1:
        print(f"Warning: {len(urls)} Linux x64 URLs found for {product}; using the first:")
        for candidate in urls:
            print(f"  {candidate}")
    return extract_download_version(urls[0]), urls[0]


def extract_icon(asar: Path, output: Path) -> None:
    with asar.open("rb") as archive:
        archive.read(4)
        header_size = int.from_bytes(archive.read(4), "little")
        archive.read(4)
        json_size = int.from_bytes(archive.read(4), "little")
        header = json.loads(archive.read(json_size).decode())
    icon = header["files"]["icon.png"]
    with asar.open("rb") as archive:
        archive.seek(8 + header_size + int(icon["offset"]))
        output.write_bytes(archive.read(int(icon["size"])))


def safe_replace(src: Path, dest: Path) -> None:
    previous = dest.with_suffix(".previous")
    if previous.exists():
        shutil.rmtree(previous)
    if dest.exists():
        dest.rename(previous)
    src.rename(dest)


def remove_legacy_restart_helper(path: Path) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()


def install_product(product: str, page: str, force: bool = False) -> bool:
    """Install one product. Returns False when it was already up to date."""
    cfg = PRODUCTS[product]
    version, url = parse_download(page, product)
    root = cfg["install_root"]
    # Only the root about to be written counts here. installed_version() also
    # looks at the other install mode, and skipping on that would leave the
    # requested mode uninstalled.
    if not force and read_version_marker(root) == version:
        print(f"{cfg['name']} {version} is already installed at {root}; use --force to reinstall")
        return False
    top = cfg.get("install_top", cfg["expected_top"])
    target_dir = root / top
    binary = target_dir / cfg["binary"]
    command_binary = target_dir / cfg.get("command_binary", cfg["binary"])

    print(f"Downloading {cfg['name']} {version}...")
    with tempfile.TemporaryDirectory(prefix=f"antigravity-{product}.") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / cfg["archive_name"]
        download(url, archive)

        with tarfile.open(archive, "r:gz") as tar:
            names = tar.getnames()
            if not names:
                raise SystemExit("Downloaded archive is empty")
            top_dir = names[0].split("/", 1)[0]
            if top_dir != cfg["expected_top"]:
                raise SystemExit(f"Unexpected archive directory: {top_dir}")
            # filter="data" blocks path traversal and strips setuid bits; the
            # installer re-applies setuid to chrome-sandbox itself below.
            # The keyword only exists on Python 3.11.4+.
            extract_args = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
            tar.extractall(tmp_path, **extract_args)

        extracted = tmp_path / cfg["expected_top"]
        if product == "ide":
            normalized = tmp_path / cfg["install_top"]
            if normalized.exists():
                shutil.rmtree(normalized)
            extracted.rename(normalized)
            extracted = normalized

        launcher = extracted / cfg["binary"]
        if not launcher.exists():
            candidates = list(extracted.glob("antigravity*"))
            raise SystemExit(f"Launcher not found. Candidates: {candidates}")
        command_launcher = extracted / cfg.get("command_binary", cfg["binary"])
        if not command_launcher.exists():
            raise SystemExit(f"Command launcher not found: {command_launcher}")

        staged = root.with_suffix(".new")
        if staged.exists():
            shutil.rmtree(staged)
        staged.mkdir(parents=True)
        shutil.copytree(extracted, staged / top, symlinks=True)
        (staged / VERSION_MARKER).write_text(version + "\n")
        sandbox = staged / top / "chrome-sandbox"
        if SYSTEM_INSTALL and sandbox.exists():
            os.chown(sandbox, 0, 0)
            sandbox.chmod(0o4755)

        icon_staged = tmp_path / "icon.png"
        
        asar_path = staged / top / "resources" / "app.asar"
        if asar_path.exists():
            extract_icon(asar_path, icon_staged)
        else:
            fallback_icon = staged / top / "resources" / "app" / "resources" / "linux" / "code.png"
            if not fallback_icon.exists():
                raise SystemExit(f"Could not find icon source for {cfg['name']}")
            shutil.copy2(fallback_icon, icon_staged)

        root.parent.mkdir(parents=True, exist_ok=True)
        safe_replace(staged, root)
        BIN.mkdir(parents=True, exist_ok=True)
        if cfg["command"].exists() or cfg["command"].is_symlink():
            cfg["command"].unlink()
        launch_flags = "--ozone-platform=x11"
        if product == "app":
            cfg["command"].write_text(
                "#!/bin/sh\n"
                "if [ \"${ANTIGRAVITY_FOREGROUND:-}\" = \"1\" ]; then\n"
                f"  exec {shlex.quote(str(command_binary))} {launch_flags} \"$@\"\n"
                "fi\n"
                f"setsid {shlex.quote(str(command_binary))} {launch_flags} \"$@\" >/tmp/antigravity-launch.log 2>&1 &\n"
            )
        else:
            cfg["command"].write_text(
                "#!/bin/sh\n"
                f"exec {shlex.quote(str(command_binary))} {launch_flags} \"$@\"\n"
            )
        cfg["command"].chmod(0o755)
        if product == "app":
            remove_legacy_restart_helper(LEGACY_APP_RESTART_COMMAND)

        ICONS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_staged, cfg["icon"])

        APPS.mkdir(parents=True, exist_ok=True)
        cfg["desktop"].write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    f"Name={cfg['name']}",
                    f"Comment={cfg['comment']}",
                    f"Exec={cfg['command']} %U",
                    f"Icon={cfg['icon']}",
                    "Terminal=false",
                    "Type=Application",
                    "Categories=Development;IDE;",
                    "StartupNotify=true",
                    f"StartupWMClass={cfg['startup_wm_class']}",
                    "",
                ]
            )
        )
        cfg["desktop"].chmod(cfg["desktop"].stat().st_mode | stat.S_IXUSR)

    print(f"Installed {cfg['name']} {version} at {target_dir}")
    return True


def install_roots(product: str) -> list[Path]:
    """Where this product may be installed: the current mode's root, then the other."""
    root = PRODUCTS[product]["install_root"]
    alt = ALT_OPT / root.name
    return [root] if alt == root else [root, alt]


def read_version_marker(root: Path) -> str | None:
    """Return the version recorded in one specific install root."""
    try:
        version = (root / VERSION_MARKER).read_text().strip()
    except OSError:
        return None
    return version or None


def gui_runtime_problems() -> list[str]:
    """Report what the GUI needs at run time but this machine does not have.

    These are warnings, not errors: the launcher is still worth installing
    because the missing packages can be added afterwards. Without this the only
    symptom is a menu entry that does nothing when clicked.
    """
    problems = []
    probe = "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk"
    # Mirror what gui.py does: try PATH first, then the system interpreter.
    interpreters = [shutil.which("python3"), SYSTEM_PYTHON]
    for interpreter in interpreters:
        if not interpreter or not Path(interpreter).exists():
            continue
        try:
            probed = subprocess.run([interpreter, "-c", probe], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if probed.returncode == 0:
            break
    else:
        problems.append(
            "PyGObject with GTK 3 is missing, so the GUI will not start. "
            "On Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0"
        )
    if not shutil.which("pkexec"):
        problems.append(
            "pkexec is missing, so the GUI cannot run a system install. "
            "On Ubuntu: sudo apt install policykit-1"
        )
    return problems


def install_gui() -> bool:
    """Install gui.py plus a launcher command and desktop entry."""
    source_dir = Path(__file__).resolve().parent
    sources = [source_dir / "gui.py", source_dir / "install.py"]
    missing = [source for source in sources if not source.exists()]
    if missing:
        raise SystemExit(f"Cannot install the GUI, missing: {', '.join(str(m) for m in missing)}")

    GUI_DATA.mkdir(parents=True, exist_ok=True)
    for source in sources:
        target = GUI_DATA / source.name
        shutil.copy2(source, target)
        target.chmod(0o755)

    BIN.mkdir(parents=True, exist_ok=True)
    if GUI_COMMAND.exists() or GUI_COMMAND.is_symlink():
        GUI_COMMAND.unlink()
    # gui.py re-execs itself under the system Python when the one on PATH
    # cannot import gi, so plain python3 is enough here.
    GUI_COMMAND.write_text(
        "#!/bin/sh\n"
        f"exec python3 {shlex.quote(str(GUI_DATA / 'gui.py'))} \"$@\"\n"
    )
    GUI_COMMAND.chmod(0o755)

    # The icon is optional so a bare install.py + gui.py pair still works.
    icon_source = source_dir / GUI_ICON_FILE
    icon_name = GUI_ICON_FALLBACK
    if icon_source.exists():
        GUI_ICON.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_source, GUI_ICON)
        # A second copy next to gui.py gives the window an icon even before the
        # icon theme cache picks the new file up.
        shutil.copy2(icon_source, GUI_DATA / GUI_ICON_FILE)
        icon_name = GUI_ICON.stem
    else:
        print(f"Warning: {GUI_ICON_FILE} not found, using the {icon_name} icon")

    APPS.mkdir(parents=True, exist_ok=True)
    GUI_DESKTOP.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Name=Antigravity Manager",
                "Comment=Check versions and install or update Google Antigravity",
                f"Exec={GUI_COMMAND}",
                f"Icon={icon_name}",
                "Terminal=false",
                "Type=Application",
                "Categories=Development;",
                "StartupNotify=true",
                "",
            ]
        )
    )
    GUI_DESKTOP.chmod(GUI_DESKTOP.stat().st_mode | stat.S_IXUSR)

    print(f"Installed Antigravity Manager at {GUI_COMMAND}")
    for problem in gui_runtime_problems():
        print(f"Warning: {problem}")
    return True


def installed_version(product: str) -> tuple[str, Path] | None:
    """Return the recorded version and its install root, in either install mode."""
    for root in install_roots(product):
        version = read_version_marker(root)
        if version:
            return version, root
    return None


def check_products(products: list[str], page: str) -> None:
    """Report installed vs available versions. Exits 1 if anything is stale."""
    stale = []
    for product in products:
        cfg = PRODUCTS[product]
        available, _ = parse_download(page, product)
        found = installed_version(product)
        if found is None:
            stale.append(product)
            print(f"{cfg['name']}: not installed, available {available}")
            continue
        current, root = found
        status = "up to date" if current == available else "update available"
        if current != available:
            stale.append(product)
        print(f"{cfg['name']}: installed {current} at {root}, available {available} ({status})")
    if stale:
        print(f"\nTo update: {' '.join(stale)}")
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install or update Google Antigravity on Linux x64.",
    )
    # choices= is not used here: with nargs="*" argparse validates the empty
    # default against it, which would forbid a GUI-only run.
    parser.add_argument(
        "products",
        nargs="*",
        default=[],
        metavar="{" + ",".join(sorted(PRODUCTS)) + "}",
    )
    parser.add_argument(
        "--install-gui",
        action="store_true",
        help="install the Antigravity Manager GUI, its launcher command and its "
        "desktop entry; can be combined with products",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="report installed vs available versions and exit without downloading; "
        "exit status is 1 when any product is missing or out of date",
    )
    mode.add_argument(
        "--force",
        action="store_true",
        help="reinstall even when the installed version already matches the "
        "available version, for repairing a damaged install",
    )
    args = parser.parse_args()

    unknown = [product for product in args.products if product not in PRODUCTS]
    if unknown:
        parser.error(
            f"invalid product: {', '.join(unknown)} "
            f"(choose from {', '.join(sorted(PRODUCTS))})"
        )
    if not args.products and not args.install_gui:
        parser.error("name at least one product, or pass --install-gui")
    if args.check and args.install_gui:
        parser.error("--install-gui cannot be combined with --check")

    if os.uname().machine not in {"x86_64", "amd64"}:
        raise SystemExit(f"Unsupported architecture for this installer: {os.uname().machine}")

    # Validate every override up front, then skip the download page entirely
    # when it has nothing left to resolve. This keeps the overrides usable as
    # an escape hatch when the page layout changes.
    overrides = [override_url(product) for product in args.products]
    page = "" if all(overrides) else fetch_text(DOWNLOAD_PAGE)

    if args.check:
        check_products(args.products, page)
        return

    installed = [install_product(product, page, force=args.force) for product in args.products]
    if args.install_gui:
        installed.append(install_gui())
    if not any(installed):
        return

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(APPS)], check=False)
    # Only refresh a directory that is a real icon theme root. Forcing a cache
    # into one without an index.theme (the user-local hicolor) leaves a stale
    # cache behind for every other application writing icons there.
    if shutil.which("gtk-update-icon-cache") and (ICON_THEME / "index.theme").exists():
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", str(ICON_THEME)], check=False)


if __name__ == "__main__":
    main()
