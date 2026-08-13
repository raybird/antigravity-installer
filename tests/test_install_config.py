import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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
