#!/usr/bin/env python3
"""Small GTK front end for install.py.

Shows the installed and available versions of each product and runs the
installer for the ones you pick. Everything it reports comes from install.py,
so the GUI and the CLI can never disagree.
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM_PYTHON = "/usr/bin/python3"

try:
    import gi
except ModuleNotFoundError:
    # PyGObject is a system package, so a pyenv or venv interpreter usually
    # cannot see it. Re-exec once under the system Python before giving up.
    if os.environ.get("ANTIGRAVITY_GUI_REEXEC") != "1" and Path(SYSTEM_PYTHON).exists():
        os.environ["ANTIGRAVITY_GUI_REEXEC"] = "1"
        os.execv(SYSTEM_PYTHON, [SYSTEM_PYTHON, str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit(
        "gui.py needs PyGObject. On Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0"
    )

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

sys.path.insert(0, str(HERE))
import install  # noqa: E402


PRODUCT_ORDER = ["app", "ide"]
INSTALL_SCRIPT = HERE / "install.py"


def install_command(products, system_mode):
    """Build the argv that installs the given products."""
    base = [sys.executable, str(INSTALL_SCRIPT), *products]
    if not system_mode:
        return base
    # pkexec drops the environment, so the install mode is passed through env(1).
    return ["pkexec", "env", "ANTIGRAVITY_INSTALL_MODE=system", *base]


class ManagerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Antigravity Manager")
        self.set_default_size(640, 460)
        self.set_border_width(12)
        # Prefer the file shipped next to gui.py so the window has an icon even
        # when running from a clone, before anything is registered with a theme.
        icon_file = HERE / "antigravity-manager.svg"
        if icon_file.exists():
            self.set_icon_from_file(str(icon_file))
        else:
            self.set_icon_name("antigravity-manager")
        self.busy = False
        self.available = {}
        self.rows = {}

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(outer)

        grid = Gtk.Grid(column_spacing=16, row_spacing=8)
        outer.pack_start(grid, False, False, 0)
        for column, title in enumerate(("產品", "已安裝", "線上最新", "狀態", "")):
            label = Gtk.Label(xalign=0)
            label.set_markup(f"<b>{title}</b>")
            grid.attach(label, column, 0, 1, 1)

        for row, product in enumerate(PRODUCT_ORDER, start=1):
            name = Gtk.Label(label=install.PRODUCTS[product]["name"], xalign=0)
            installed = Gtk.Label(label="…", xalign=0)
            latest = Gtk.Label(label="…", xalign=0)
            status = Gtk.Label(label="檢查中", xalign=0)
            action = Gtk.Button(label="更新")
            action.set_sensitive(False)
            action.connect("clicked", self.on_install_clicked, [product])
            for column, widget in enumerate((name, installed, latest, status, action)):
                grid.attach(widget, column, row, 1, 1)
            self.rows[product] = {
                "installed": installed,
                "latest": latest,
                "status": status,
                "action": action,
            }

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(controls, False, False, 0)

        self.refresh_button = Gtk.Button(label="重新檢查")
        self.refresh_button.connect("clicked", lambda _button: self.refresh())
        controls.pack_start(self.refresh_button, False, False, 0)

        self.all_button = Gtk.Button(label="全部安裝／更新")
        self.all_button.connect("clicked", self.on_install_clicked, list(PRODUCT_ORDER))
        controls.pack_start(self.all_button, False, False, 0)

        self.system_check = Gtk.CheckButton(label="系統安裝（/opt，需要授權）")
        self.system_check.set_active(True)
        controls.pack_end(self.system_check, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        outer.pack_start(scroller, True, True, 0)

        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        self.log.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroller.add(self.log)

        self.status_bar = Gtk.Label(label="", xalign=0)
        outer.pack_start(self.status_bar, False, False, 0)

        self.refresh()

    # -- helpers ---------------------------------------------------------

    def append_log(self, text):
        buffer = self.log.get_buffer()
        buffer.insert(buffer.get_end_iter(), text)
        self.log.scroll_to_mark(buffer.get_insert(), 0.0, False, 0.0, 0.0)

    def set_busy(self, busy, message=""):
        self.busy = busy
        self.refresh_button.set_sensitive(not busy)
        self.all_button.set_sensitive(not busy)
        for product, widgets in self.rows.items():
            stale = self.rows[product]["status"].get_text() != "已是最新"
            widgets["action"].set_sensitive(not busy and stale and product in self.available)
        self.status_bar.set_text(message)

    def run_in_thread(self, target):
        threading.Thread(target=target, daemon=True).start()

    # -- version check ---------------------------------------------------

    def refresh(self):
        if self.busy:
            return
        self.set_busy(True, "正在讀取官方下載頁…")
        for widgets in self.rows.values():
            widgets["status"].set_text("檢查中")
        self.run_in_thread(self._check_worker)

    def _check_worker(self):
        try:
            page = install.fetch_text(install.DOWNLOAD_PAGE)
            results = {}
            for product in PRODUCT_ORDER:
                available, _url = install.parse_download(page, product)
                results[product] = (available, install.installed_version(product))
        except Exception as error:  # noqa: BLE001 - surfaced in the UI
            GLib.idle_add(self._check_failed, str(error))
            return
        GLib.idle_add(self._check_done, results)

    def _check_failed(self, message):
        self.append_log(f"檢查失敗: {message}\n")
        for widgets in self.rows.values():
            widgets["status"].set_text("檢查失敗")
        self.set_busy(False, "檢查失敗")

    def _check_done(self, results):
        outdated = 0
        for product, (available, found) in results.items():
            widgets = self.rows[product]
            self.available[product] = available
            widgets["latest"].set_text(available)
            if found is None:
                widgets["installed"].set_text("—")
                widgets["status"].set_text("未安裝")
                widgets["action"].set_label("安裝")
                outdated += 1
            else:
                current, root = found
                widgets["installed"].set_text(current)
                widgets["installed"].set_tooltip_text(str(root))
                if current == available:
                    widgets["status"].set_text("已是最新")
                else:
                    widgets["status"].set_text("可更新")
                    widgets["action"].set_label("更新")
                    outdated += 1
        summary = "全部已是最新" if not outdated else f"{outdated} 個項目可安裝或更新"
        self.set_busy(False, summary)

    # -- install ---------------------------------------------------------

    def on_install_clicked(self, _button, products):
        if self.busy:
            return
        targets = [p for p in products if self.rows[p]["status"].get_text() != "已是最新"]
        if not targets:
            self.status_bar.set_text("沒有需要安裝或更新的項目")
            return
        system_mode = self.system_check.get_active()
        command = install_command(targets, system_mode)
        self.append_log("\n$ " + " ".join(command) + "\n")
        self.set_busy(True, "安裝中，請稍候…")
        self.run_in_thread(lambda: self._install_worker(command))

    def _install_worker(self, command):
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as error:
            GLib.idle_add(self._install_done, 127, str(error))
            return
        for line in process.stdout:
            GLib.idle_add(self.append_log, line)
        process.wait()
        GLib.idle_add(self._install_done, process.returncode, "")

    def _install_done(self, returncode, error):
        if error:
            self.append_log(f"無法執行安裝程式: {error}\n")
        if returncode == 0:
            self.set_busy(False, "安裝完成，重新檢查版本…")
            self.refresh()
            return
        # pkexec exits 126 when the authorisation dialog is dismissed.
        message = "已取消授權" if returncode == 126 else f"安裝失敗（結束碼 {returncode}）"
        self.append_log(message + "\n")
        self.set_busy(False, message)


def main():
    if not INSTALL_SCRIPT.exists():
        raise SystemExit(f"install.py not found next to gui.py: {INSTALL_SCRIPT}")
    window = ManagerWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
