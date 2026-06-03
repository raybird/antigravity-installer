import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import install


class ProductConfigTest(unittest.TestCase):
    def test_app_product_does_not_define_restart_helper(self):
        self.assertNotIn("restart_command", install.PRODUCTS["app"])

    def test_removes_legacy_restart_helper(self):
        with TemporaryDirectory() as tmp:
            restart_helper = Path(tmp) / "antigravity-restart"
            restart_helper.write_text("#!/bin/sh\n")

            install.remove_legacy_restart_helper(restart_helper)

            self.assertFalse(restart_helper.exists())

    def test_ide_url_override_takes_precedence(self):
        override_url = "https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.0.4-6381998290370560/linux-x64/Antigravity%20IDE.tar.gz"

        with patch.dict("os.environ", {"ANTIGRAVITY_IDE_URL": override_url}):
            version, url = install.parse_download("", "ide")

        self.assertEqual(version, "2.0.4")
        self.assertEqual(url, override_url)

    def test_extracts_version_from_download_url(self):
        url = "https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/2.0.4-6381998290370560/linux-x64/Antigravity%20IDE.tar.gz"

        self.assertEqual(install.extract_download_version(url), "2.0.4")


if __name__ == "__main__":
    unittest.main()
