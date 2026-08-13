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
ICONS = (
    Path("/usr/share/icons/hicolor/512x512/apps")
    if SYSTEM_INSTALL
    else LOCAL / "share" / "icons" / "hicolor" / "512x512" / "apps"
)


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


def install_product(product: str, page: str) -> None:
    cfg = PRODUCTS[product]
    version, url = parse_download(page, product)
    root = cfg["install_root"]
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
        (staged / ".userlocal-version").write_text(version + "\n")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("products", nargs="+", choices=sorted(PRODUCTS))
    args = parser.parse_args()

    if os.uname().machine not in {"x86_64", "amd64"}:
        raise SystemExit(f"Unsupported architecture for this installer: {os.uname().machine}")

    # Validate every override up front, then skip the download page entirely
    # when it has nothing left to resolve. This keeps the overrides usable as
    # an escape hatch when the page layout changes.
    overrides = [override_url(product) for product in args.products]
    page = "" if all(overrides) else fetch_text(DOWNLOAD_PAGE)
    for product in args.products:
        install_product(product, page)

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(APPS)], check=False)
    if shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-q", str(LOCAL / "share" / "icons" / "hicolor")], check=False)


if __name__ == "__main__":
    main()
