import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
