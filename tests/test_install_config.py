import unittest

import install


class ProductConfigTest(unittest.TestCase):
    def test_app_product_does_not_define_restart_helper(self):
        self.assertNotIn("restart_command", install.PRODUCTS["app"])


if __name__ == "__main__":
    unittest.main()
