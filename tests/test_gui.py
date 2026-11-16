"""Exercise GUI state transitions without requiring GTK or a display."""
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import install

def manager_methods():
    source = Path(__file__).resolve().parents[1] / "gui.py"
    tree = ast.parse(source.read_text())
    window = next(node for node in tree.body
                  if isinstance(node, ast.ClassDef) and node.name == "ManagerWindow")
    methods = [node for node in window.body
               if isinstance(node, ast.FunctionDef)
               and node.name in {"refresh", "_check_done", "update_manager_banner",
                                 "_install_done", "handle_install_output",
                                 "show_progress", "pulse_progress", "stop_progress_pulse"}]
    namespace = {"PRODUCT_ORDER": ["app", "ide"], "install": install, "json": json,
                 "GLib": Mock()}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class InstallCompletionTest(unittest.TestCase):
    def test_success_starts_version_check_after_busy_install(self):
        methods = manager_methods()
        window = SimpleNamespace(
            busy=True,
            append_log=Mock(),
            show_progress=Mock(),
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


class ProgressDisplayTest(unittest.TestCase):
    def setUp(self):
        self.methods = manager_methods()
        self.window = SimpleNamespace(show_progress=Mock(), append_log=Mock())

    def send(self, event):
        self.methods["handle_install_output"](
            self.window, install.PROGRESS_PREFIX + json.dumps(event) + "\n",
        )

    def test_download_shows_actual_percentage_and_size(self):
        self.send(dict(product="app", phase="download", received=1048576, total=4194304))
        text, fraction = self.window.show_progress.call_args.args
        self.assertIn("25%", text)
        self.assertIn("1.0 MiB / 4.0 MiB", text)
        self.assertEqual(fraction, 0.25)
        self.window.append_log.assert_not_called()

    def test_unknown_download_size_uses_indeterminate_progress(self):
        self.send(dict(product="ide", phase="download", received=1048576, total=0))
        self.window.show_progress.assert_called_once_with("Antigravity IDE · 正在下載 · 1.0 MiB")

    def test_install_stages_use_indeterminate_progress(self):
        for phase in ("extract", "copy", "configure", "done"):
            with self.subTest(phase=phase):
                self.send(dict(product="app", phase=phase))
                self.assertEqual(len(self.window.show_progress.call_args.args), 1)

    def test_normal_and_malformed_output_remains_in_log(self):
        for line in ("Installed Antigravity\n", install.PROGRESS_PREFIX + "broken\n"):
            self.methods["handle_install_output"](self.window, line)
            self.window.append_log.assert_called_with(line)

    def test_determinate_progress_stops_existing_pulse(self):
        window = SimpleNamespace(progress_bar=Mock(), progress_timer=123)
        window.stop_progress_pulse = lambda: self.methods["stop_progress_pulse"](window)
        self.methods["show_progress"](window, "下載 25%", 0.25)
        self.methods["GLib"].source_remove.assert_called_once_with(123)
        self.assertIsNone(window.progress_timer)
        window.progress_bar.set_fraction.assert_called_once_with(0.25)

    def test_repeated_indeterminate_updates_share_one_timer(self):
        window = SimpleNamespace(progress_bar=Mock(), progress_timer=None, pulse_progress=Mock())
        for text in ("正在下載", "正在解壓縮"):
            self.methods["show_progress"](window, text)
        self.methods["GLib"].timeout_add.assert_called_once_with(100, window.pulse_progress)

    def test_manager_progress_event_uses_manager_display_name(self):
        self.send(dict(product="manager", phase="download", received=524288, total=1048576))
        text, fraction = self.window.show_progress.call_args.args
        self.assertIn("Antigravity Manager", text)
        self.assertIn("50%", text)
        self.assertEqual(fraction, 0.5)


class ManagerSelfUpdateGuiTest(unittest.TestCase):
    def setUp(self):
        self.methods = manager_methods()

    def test_manager_update_completion_marks_pending_restart(self):
        window = SimpleNamespace(
            busy=True,
            active_install_kind="manager",
            manager_updated_pending_restart=False,
            append_log=Mock(),
            show_progress=Mock(),
            set_row_state=Mock(),
            update_summary=Mock(),
            run_in_thread=Mock(),
            _check_worker=Mock(),
            rows={product: {field: Mock() for field in ("installed", "latest", "path")}
                  for product in ("app", "ide")},
        )
        window.set_busy = lambda busy, message="": setattr(window, "busy", busy)
        window.refresh = lambda: self.methods["refresh"](window)

        self.methods["_install_done"](window, 0, "")

        self.assertTrue(window.manager_updated_pending_restart)
        self.assertEqual(window.active_install_kind, "products")
        window.run_in_thread.assert_called_once_with(window._check_worker)

    def test_banner_shows_update_available_then_restart_after_update(self):
        window = SimpleNamespace(
            install_progress_active=False,
            manager_updated_pending_restart=False,
            manager_update_info=None,
            manager_banner=Mock(),
            manager_banner_label=Mock(),
            manager_update_button=Mock(),
            update_target_view=Mock(),
            actionable_products=Mock(return_value=[]),
            set_busy=Mock(),
        )
        window.update_manager_banner = lambda: self.methods["update_manager_banner"](window)

        self.methods["_check_done"](
            window, {}, {"current": "1.3.0", "latest": "1.4.0", "update_available": True},
        )
        window.manager_banner.set_visible.assert_called_with(True)
        window.manager_update_button.set_label.assert_called_with("立即更新管理器")

        window.manager_updated_pending_restart = True
        self.methods["update_manager_banner"](window)
        window.manager_update_button.set_label.assert_called_with("重新啟動管理器")


if __name__ == "__main__":
    unittest.main()
