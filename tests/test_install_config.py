import contextlib
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import install


FIXTURES = Path(__file__).parent / "fixtures"
APP_URL = (
    "https://storage.googleapis.com/antigravity-public/antigravity-hub/"
    "2.8.0-5810824271495168/linux-x64/Antigravity.tar.gz"
)
IDE_URL = (
    "https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/"
    "2.5.2-6697361355964416/linux-x64/Antigravity%20IDE.tar.gz"
)


def download_page() -> str:
    return (FIXTURES / "download_page.html").read_text()


class ProductConfigTest(unittest.TestCase):
    def test_app_product_does_not_define_restart_helper(self):
        self.assertNotIn("restart_command", install.PRODUCTS["app"])

    def test_every_product_defines_a_url_override_env(self):
        for product, cfg in install.PRODUCTS.items():
            with self.subTest(product=product):
                self.assertIn("url_override_env", cfg)

    def test_removes_legacy_restart_helper(self):
        with TemporaryDirectory() as tmp:
            restart_helper = Path(tmp) / "antigravity-restart"
            restart_helper.write_text("#!/bin/sh\n")

            install.remove_legacy_restart_helper(restart_helper)

            self.assertFalse(restart_helper.exists())


class ParseDownloadPageTest(unittest.TestCase):
    """The download page is plain HTML since the site moved to Astro."""

    def setUp(self):
        self.page = download_page()

    def test_parses_app_linux_x64_download(self):
        version, url = install.parse_download(self.page, "app")

        self.assertEqual(version, "2.8.0")
        self.assertEqual(url, APP_URL)

    def test_parses_ide_linux_x64_download(self):
        version, url = install.parse_download(self.page, "ide")

        self.assertEqual(version, "2.5.2")
        self.assertEqual(url, IDE_URL)

    def test_ignores_arm_builds(self):
        for product in install.PRODUCTS:
            with self.subTest(product=product):
                _, url = install.parse_download(self.page, product)

                self.assertNotIn("linux-arm", url)

    def test_unescapes_html_entities_in_href(self):
        page = f'<a href="{APP_URL}?a=1&amp;b=2">x64</a>'

        _, url = install.parse_download(page, "app")

        self.assertEqual(url, f"{APP_URL}?a=1&b=2")

    def test_missing_link_reports_the_override_env(self):
        with self.assertRaises(SystemExit) as raised:
            install.parse_download("<html></html>", "ide")

        self.assertIn("ANTIGRAVITY_IDE_URL", str(raised.exception))


class UrlOverrideTest(unittest.TestCase):
    def test_ide_url_override_takes_precedence(self):
        with patch.dict("os.environ", {"ANTIGRAVITY_IDE_URL": IDE_URL}):
            version, url = install.parse_download(download_page(), "ide")

        self.assertEqual(version, "2.5.2")
        self.assertEqual(url, IDE_URL)

    def test_app_url_override_takes_precedence(self):
        with patch.dict("os.environ", {"ANTIGRAVITY_APP_URL": APP_URL}):
            version, url = install.parse_download(download_page(), "app")

        self.assertEqual(version, "2.8.0")
        self.assertEqual(url, APP_URL)

    def test_override_works_without_a_download_page(self):
        """The escape hatch must survive the page becoming unparseable."""
        with patch.dict("os.environ", {"ANTIGRAVITY_IDE_URL": IDE_URL}):
            version, url = install.parse_download("", "ide")

        self.assertEqual(version, "2.5.2")
        self.assertEqual(url, IDE_URL)

    def test_override_rejects_a_url_for_the_wrong_product(self):
        with patch.dict("os.environ", {"ANTIGRAVITY_IDE_URL": APP_URL}):
            with self.assertRaises(SystemExit):
                install.override_url("ide")

    def test_no_override_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(install.override_url("ide"))


@contextlib.contextmanager
def fake_install_root(product, version, alt_version=None):
    """Point a product's install roots at temp dirs holding version markers.

    ALT_OPT is redirected too, so the real /opt on the developer's machine can
    never leak into a test result.
    """
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = tmp / "primary" / install.PRODUCTS[product]["install_root"].name
        alt_opt = tmp / "alt"
        alt = alt_opt / root.name
        for target, value in ((root, version), (alt, alt_version)):
            if value is not None:
                target.mkdir(parents=True)
                (target / install.VERSION_MARKER).write_text(value + "\n")
        with patch.dict(install.PRODUCTS[product], {"install_root": root}):
            with patch.object(install, "ALT_OPT", alt_opt):
                yield root, alt


class InstalledVersionTest(unittest.TestCase):
    def test_reads_and_strips_the_version_marker(self):
        with fake_install_root("ide", "2.5.2") as (root, _):
            self.assertEqual(install.installed_version("ide"), ("2.5.2", root))

    def test_none_when_not_installed(self):
        with fake_install_root("ide", None):
            self.assertIsNone(install.installed_version("ide"))

    def test_none_when_marker_is_blank(self):
        with fake_install_root("ide", "   "):
            self.assertIsNone(install.installed_version("ide"))

    def test_falls_back_to_the_other_install_mode(self):
        """--check must find a system install even without ANTIGRAVITY_INSTALL_MODE."""
        with fake_install_root("ide", None, alt_version="2.5.2") as (_, alt):
            self.assertEqual(install.installed_version("ide"), ("2.5.2", alt))

    def test_prefers_the_current_mode_over_the_fallback(self):
        with fake_install_root("ide", "2.5.2", alt_version="2.1.1") as (root, _):
            self.assertEqual(install.installed_version("ide"), ("2.5.2", root))


class CheckProductsTest(unittest.TestCase):
    def run_check(self, products):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                install.check_products(products, download_page())
                code = 0
            except SystemExit as exit_error:
                code = exit_error.code
        return code, out.getvalue()

    def test_exits_zero_when_up_to_date(self):
        with fake_install_root("ide", "2.5.2"):
            code, output = self.run_check(["ide"])

        self.assertEqual(code, 0)
        self.assertIn("up to date", output)

    def test_exits_one_when_an_update_is_available(self):
        with fake_install_root("ide", "2.1.1") as (root, _):
            code, output = self.run_check(["ide"])

        self.assertEqual(code, 1)
        self.assertIn("update available", output)
        self.assertIn(f"installed 2.1.1 at {root}, available 2.5.2", output)

    def test_exits_one_when_not_installed(self):
        with fake_install_root("ide", None):
            code, output = self.run_check(["ide"])

        self.assertEqual(code, 1)
        self.assertIn("not installed", output)

    def test_reports_every_requested_product(self):
        with fake_install_root("ide", "2.5.2"), fake_install_root("app", "2.1.4"):
            code, output = self.run_check(["ide", "app"])

        self.assertEqual(code, 1)
        self.assertIn("Antigravity IDE:", output)
        self.assertIn("Antigravity:", output)
        self.assertIn("To update: app", output)


class SkipWhenCurrentTest(unittest.TestCase):
    """install_product must not re-download a version already in place."""

    @contextlib.contextmanager
    def download_forbidden(self):
        out = io.StringIO()
        with patch.object(install, "download", side_effect=RuntimeError("downloaded")):
            with contextlib.redirect_stdout(out):
                yield out

    def test_skips_when_the_installed_version_matches(self):
        with fake_install_root("ide", "2.5.2") as (root, _):
            with self.download_forbidden() as out:
                changed = install.install_product("ide", download_page())

        self.assertFalse(changed)
        self.assertIn("already installed", out.getvalue())
        self.assertIn(str(root), out.getvalue())

    def test_force_reinstalls_the_same_version(self):
        with fake_install_root("ide", "2.5.2"):
            with self.download_forbidden():
                with self.assertRaises(RuntimeError):
                    install.install_product("ide", download_page(), force=True)

    def test_does_not_skip_on_a_stale_version(self):
        with fake_install_root("ide", "2.1.1"):
            with self.download_forbidden():
                with self.assertRaises(RuntimeError):
                    install.install_product("ide", download_page())

    def test_does_not_skip_because_the_other_install_mode_is_current(self):
        """A user-local install must never satisfy a system install request."""
        with fake_install_root("ide", None, alt_version="2.5.2"):
            with self.download_forbidden():
                with self.assertRaises(RuntimeError):
                    install.install_product("ide", download_page())


class InstallGuiTest(unittest.TestCase):
    @contextlib.contextmanager
    def staging(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            targets = {
                "GUI_DATA": tmp / "share" / "antigravity-installer",
                "GUI_COMMAND": tmp / "bin" / "antigravity-manager",
                "GUI_DESKTOP": tmp / "applications" / "antigravity-manager.desktop",
                "GUI_ICON": tmp / "icons" / "scalable" / "apps" / install.GUI_ICON_FILE,
                "BIN": tmp / "bin",
                "APPS": tmp / "applications",
            }
            with contextlib.ExitStack() as stack:
                for name, value in targets.items():
                    stack.enter_context(patch.object(install, name, value))
                out = io.StringIO()
                stack.enter_context(contextlib.redirect_stdout(out))
                yield targets

    def test_copies_both_scripts_and_makes_them_executable(self):
        with self.staging() as targets:
            self.assertTrue(install.install_gui())

            for name in ("gui.py", "install.py"):
                copied = targets["GUI_DATA"] / name
                self.assertTrue(copied.exists(), name)
                self.assertTrue(copied.stat().st_mode & 0o111, f"{name} not executable")

    def test_launcher_points_at_the_installed_copy(self):
        with self.staging() as targets:
            install.install_gui()

            launcher = targets["GUI_COMMAND"].read_text()
            self.assertIn(str(targets["GUI_DATA"] / "gui.py"), launcher)
            self.assertTrue(targets["GUI_COMMAND"].stat().st_mode & 0o111)

    def test_desktop_entry_executes_the_launcher(self):
        with self.staging() as targets:
            install.install_gui()

            entry = targets["GUI_DESKTOP"].read_text()
            self.assertIn("Type=Application", entry)
            self.assertIn(f"Exec={targets['GUI_COMMAND']}", entry)

    def test_installs_the_icon_and_references_it_by_name(self):
        with self.staging() as targets:
            install.install_gui()

            self.assertTrue(targets["GUI_ICON"].exists())
            self.assertIn("<svg", targets["GUI_ICON"].read_text())
            # A copy next to gui.py gives the window an icon immediately.
            self.assertTrue((targets["GUI_DATA"] / install.GUI_ICON_FILE).exists())
            self.assertIn("Icon=antigravity-manager\n", targets["GUI_DESKTOP"].read_text())

    def test_falls_back_to_a_stock_icon_when_the_svg_is_missing(self):
        with self.staging() as targets:
            with patch.object(install, "GUI_ICON_FILE", "not-shipped.svg"):
                install.install_gui()

            entry = targets["GUI_DESKTOP"].read_text()
            self.assertIn(f"Icon={install.GUI_ICON_FALLBACK}\n", entry)
            self.assertFalse(targets["GUI_ICON"].exists())

    def test_reinstall_overwrites_an_existing_launcher(self):
        with self.staging() as targets:
            install.install_gui()
            targets["GUI_COMMAND"].write_text("#!/bin/sh\nstale\n")
            install.install_gui()

            self.assertNotIn("stale", targets["GUI_COMMAND"].read_text())


class GuiRuntimeProblemsTest(unittest.TestCase):
    """--install-gui warns instead of leaving a menu entry that does nothing."""

    @staticmethod
    def probe(returncode):
        return patch.object(
            install.subprocess, "run", return_value=SimpleNamespace(returncode=returncode)
        )

    def test_silent_when_gtk_and_pkexec_are_present(self):
        with patch.object(install.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            with self.probe(0):
                self.assertEqual(install.gui_runtime_problems(), [])

    def test_reports_missing_pygobject(self):
        with patch.object(install.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            with self.probe(1):
                problems = install.gui_runtime_problems()

        self.assertEqual(len(problems), 1)
        self.assertIn("PyGObject", problems[0])
        self.assertIn("python3-gi", problems[0])

    def test_reports_missing_pkexec(self):
        with patch.object(
            install.shutil,
            "which",
            side_effect=lambda name: None if name == "pkexec" else f"/usr/bin/{name}",
        ):
            with self.probe(0):
                problems = install.gui_runtime_problems()

        self.assertEqual(len(problems), 1)
        self.assertIn("pkexec", problems[0])

    def test_reports_both(self):
        with patch.object(install.shutil, "which", return_value=None):
            with self.probe(1):
                problems = install.gui_runtime_problems()

        self.assertEqual(len(problems), 2)


class ExtractDownloadVersionTest(unittest.TestCase):
    def test_extracts_version_from_ide_download_url(self):
        self.assertEqual(install.extract_download_version(IDE_URL), "2.5.2")

    def test_extracts_version_from_app_download_url(self):
        self.assertEqual(install.extract_download_version(APP_URL), "2.8.0")

    def test_unknown_when_no_version_in_url(self):
        url = "https://example.com/linux-x64/Antigravity.tar.gz"

        self.assertEqual(install.extract_download_version(url), "unknown")


if __name__ == "__main__":
    unittest.main()
