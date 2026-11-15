"""Exercise GUI state transitions without requiring GTK or a display."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def manager_methods():
    source = Path(__file__).resolve().parents[1] / "gui.py"
    tree = ast.parse(source.read_text())
    window = next(node for node in tree.body
                  if isinstance(node, ast.ClassDef) and node.name == "ManagerWindow")
    methods = [node for node in window.body
               if isinstance(node, ast.FunctionDef)
               and node.name in {"refresh", "_install_done"}]
    namespace = {"PRODUCT_ORDER": ["app", "ide"]}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class InstallCompletionTest(unittest.TestCase):
    def test_success_starts_version_check_after_busy_install(self):
        methods = manager_methods()
        window = SimpleNamespace(
            busy=True,
            append_log=Mock(),
            set_row_state=Mock(),
            update_summary=Mock(),
            run_in_thread=Mock(),
            _check_worker=Mock(),
            rows={product: {field: Mock() for field in ("installed", "latest", "path")}
                  for product in ("app", "ide")},
        )

        def set_busy(busy, message=""):
            window.busy = busy

        window.set_busy = set_busy
        window.refresh = lambda: methods["refresh"](window)
        methods["_install_done"](window, 0, "")

        window.run_in_thread.assert_called_once_with(window._check_worker)
        self.assertTrue(window.busy)
        self.assertFalse(window.check_ready)


if __name__ == "__main__":
    unittest.main()
