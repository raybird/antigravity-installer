#!/usr/bin/env python3
"""GTK front end for install.py.

The GUI deliberately keeps version and installation decisions in install.py.
It adds a focused presentation layer around that shared installer so the
selected installation target, current state, and next action stay explicit.
"""
import os
import shlex
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
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

sys.path.insert(0, str(HERE))
import install  # noqa: E402


PRODUCT_ORDER = ["app", "ide"]
PRODUCT_DESCRIPTIONS = {
    "app": "Agent platform for building and running Antigravity workflows",
    "ide": "Development environment for working with Antigravity projects",
}
PRODUCT_ICONS = {
    "app": "application-x-executable-symbolic",
    "ide": "text-editor-symbolic",
}
INSTALLABLE_STATES = {"missing", "update"}
STATUS_META = {
    "checking": ("檢查中", "process-working-symbolic", "status-checking"),
    "latest": ("已是最新", "emblem-ok-symbolic", "status-latest"),
    "update": ("可更新", "software-update-available-symbolic", "status-update"),
    "missing": ("未安裝", "list-add-symbolic", "status-missing"),
    "error": ("檢查失敗", "dialog-error-symbolic", "status-error"),
    "unknown": ("版本未知", "dialog-warning-symbolic", "status-error"),
}
STATUS_CLASSES = {meta[2] for meta in STATUS_META.values()}

APP_CSS = """
.hero {
  border-left: 4px solid #7C6BFF;
  padding-left: 12px;
}

.hero-title {
  font-size: 20px;
  font-weight: 700;
}

.hero-subtitle,
.product-description,
.version-caption,
.target-detail,
.status-line {
  color: @insensitive_fg_color;
}

.summary-card {
  background-color: @theme_selected_bg_color;
  border-radius: 10px;
  padding: 8px 12px;
}

.summary-count {
  font-size: 20px;
  font-weight: 700;
}

.section-label {
  font-weight: 700;
}

.product-card,
.target-card {
  background-color: @theme_base_color;
  border: 1px solid @borders;
  border-radius: 10px;
}

.product-card:hover {
  border-color: #7C6BFF;
}

.product-name {
  font-size: 15px;
  font-weight: 700;
}

.version-value {
  font-family: monospace;
  font-weight: 600;
}

.version-arrow {
  color: #7C6BFF;
  font-size: 16px;
  font-weight: 700;
}

.status-badge {
  border-radius: 999px;
  padding: 4px 8px;
  font-weight: 600;
}

.status-latest {
  background-color: #dcefe1;
  color: #216e39;
}

.status-update {
  background-color: #e5e0ff;
  color: #4937b8;
}

.status-missing {
  background-color: #eeeef0;
  color: #55555c;
}

.status-checking {
  background-color: #eeeef0;
  color: #55555c;
}

.status-error {
  background-color: #f8dfdf;
  color: #a12626;
}

.target-card {
  padding: 0;
}

.target-option {
  border-radius: 8px;
  padding: 6px;
}

.target-option:hover {
  background-color: @theme_unfocused_bg_color;
}
"""


def install_command(products, system_mode):
    """Build the argv that installs the given products."""
    base = [sys.executable, str(HERE / "install.py"), *products]
    if not system_mode:
        return base
    # pkexec drops the environment, so the install mode is passed through env(1).
    return ["pkexec", "env", "ANTIGRAVITY_INSTALL_MODE=system", *base]


class ManagerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Antigravity Manager")
        self.set_default_size(720, 680)
        self.set_size_request(560, 480)
        self.set_border_width(0)

        icon_file = HERE / "antigravity-manager.svg"
        if icon_file.exists():
            self.set_icon_from_file(str(icon_file))
        else:
            self.set_icon_name("antigravity-manager")

        self.busy = False
        self.check_ready = False
        self.results = {}
        self.rows = {}
        self.system_mode = self.preferred_install_mode()

        self.load_css()
        self.build_header()
        self.build_body()

        self.user_radio.set_active(not self.system_mode)
        self.system_radio.set_active(self.system_mode)
        self.refresh()

    # -- construction ----------------------------------------------------

    @staticmethod
    def load_css():
        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS.encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def build_header(self):
        header = Gtk.HeaderBar()
        header.set_title("Antigravity Manager")
        header.set_subtitle("Linux x86_64 · 版本管理")
        header.set_show_close_button(True)
        self.set_titlebar(header)

        self.refresh_button = Gtk.Button.new_from_icon_name(
            "view-refresh-symbolic",
            Gtk.IconSize.BUTTON,
        )
        self.refresh_button.set_tooltip_text("重新檢查官方版本")
        self.refresh_button.connect("clicked", lambda _button: self.refresh())
        header.pack_end(self.refresh_button)

    def build_body(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_border_width(12)
        self.add(outer)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hero.get_style_context().add_class("hero")
        hero_icon = self.manager_image(40)
        hero.pack_start(hero_icon, False, False, 0)

        hero_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="管理 Antigravity", xalign=0)
        title.get_style_context().add_class("hero-title")
        subtitle = Gtk.Label(
            label="查看版本狀態，選擇安裝位置並保持工具更新。",
            xalign=0,
        )
        subtitle.set_line_wrap(True)
        subtitle.get_style_context().add_class("hero-subtitle")
        hero_copy.pack_start(title, False, False, 0)
        hero_copy.pack_start(subtitle, False, False, 0)
        hero.pack_start(hero_copy, True, True, 0)

        summary_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        summary_card.set_halign(Gtk.Align.END)
        summary_card.get_style_context().add_class("summary-card")
        self.summary_count = Gtk.Label(label="—", xalign=1)
        self.summary_count.get_style_context().add_class("summary-count")
        self.summary_detail = Gtk.Label(label="正在檢查…", xalign=1)
        self.summary_detail.get_style_context().add_class("hero-subtitle")
        summary_card.pack_start(self.summary_count, False, False, 0)
        summary_card.pack_start(self.summary_detail, False, False, 0)
        hero.pack_end(summary_card, False, False, 0)
        outer.pack_start(hero, False, False, 0)

        self.product_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.pack_start(self.product_list, False, False, 0)
        for product in PRODUCT_ORDER:
            self.product_list.pack_start(
                self.build_product_card(product),
                False,
                False,
                0,
            )

        target_frame = Gtk.Frame()
        target_frame.set_shadow_type(Gtk.ShadowType.NONE)
        target_frame.get_style_context().add_class("target-card")
        target_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        target_content.set_border_width(8)
        target_frame.add(target_content)

        target_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        target_title = Gtk.Label(label="安裝位置", xalign=0)
        target_title.get_style_context().add_class("section-label")
        self.target_hint = Gtk.Label(xalign=1)
        self.target_hint.get_style_context().add_class("target-detail")
        target_heading.pack_start(target_title, True, True, 0)
        target_heading.pack_end(self.target_hint, False, False, 0)
        target_content.pack_start(target_heading, False, False, 0)

        target_options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.user_radio = Gtk.RadioButton.new_with_label(None, "僅目前使用者")
        self.system_radio = Gtk.RadioButton.new_with_label_from_widget(
            self.user_radio,
            "系統範圍",
        )
        self.user_radio.connect("toggled", self.on_target_toggled)
        self.system_radio.connect("toggled", self.on_target_toggled)
        target_options.pack_start(
            self.target_option(self.user_radio, "~/.local · 不需要授權"),
            True,
            True,
            0,
        )
        target_options.pack_start(
            self.target_option(self.system_radio, "/opt · 需要管理員授權"),
            True,
            True,
            0,
        )
        target_content.pack_start(target_options, False, False, 0)
        outer.pack_start(target_frame, False, False, 0)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.action_note = Gtk.Label(xalign=0)
        self.action_note.set_line_wrap(True)
        self.action_note.get_style_context().add_class("target-detail")
        action_row.pack_start(self.action_note, True, True, 0)

        self.all_button = Gtk.Button(label="等待檢查")
        self.all_button.get_style_context().add_class("suggested-action")
        self.all_button.connect("clicked", self.on_install_clicked, list(PRODUCT_ORDER))
        action_row.pack_end(self.all_button, False, False, 0)
        outer.pack_start(action_row, False, False, 0)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.activity = Gtk.Spinner()
        self.activity.set_no_show_all(True)
        self.activity.set_visible(False)
        status_row.pack_start(self.activity, False, False, 0)
        self.status_bar = Gtk.Label(label="", xalign=0)
        self.status_bar.set_line_wrap(True)
        self.status_bar.get_style_context().add_class("status-line")
        status_row.pack_start(self.status_bar, True, True, 0)
        outer.pack_start(status_row, False, False, 0)

        self.log_expander = Gtk.Expander(label="顯示安裝記錄")
        self.log_expander.set_expanded(False)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_size_request(-1, 90)
        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        self.log.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log.set_left_margin(8)
        self.log.set_right_margin(8)
        scroller.add(self.log)
        self.log_expander.add(scroller)
        outer.pack_start(self.log_expander, False, False, 0)

        self.update_target_view()

    def build_product_card(self, product):
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.get_style_context().add_class("product-card")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        content.set_border_width(8)
        frame.add(content)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(
            PRODUCT_ICONS[product],
            Gtk.IconSize.DIALOG,
        )
        icon.set_pixel_size(32)
        heading.pack_start(icon, False, False, 0)

        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=install.PRODUCTS[product]["name"], xalign=0)
        name.get_style_context().add_class("product-name")
        description = Gtk.Label(label=PRODUCT_DESCRIPTIONS[product], xalign=0)
        description.set_line_wrap(True)
        description.get_style_context().add_class("product-description")
        copy.pack_start(name, False, False, 0)
        copy.pack_start(description, False, False, 0)
        heading.pack_start(copy, True, True, 0)

        status_box, status_icon, status = self.status_badge()
        heading.pack_end(status_box, False, False, 0)
        content.pack_start(heading, False, False, 0)

        versions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        installed_box, installed = self.version_block("已安裝")
        latest_box, latest = self.version_block("官方最新")
        arrow = Gtk.Label(label="→")
        arrow.get_style_context().add_class("version-arrow")
        versions.pack_start(installed_box, False, False, 0)
        versions.pack_start(arrow, False, False, 0)
        versions.pack_start(latest_box, False, False, 0)
        content.pack_start(versions, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path = Gtk.Label(label="尚未檢查", xalign=0)
        path.set_line_wrap(True)
        path.get_style_context().add_class("version-caption")
        footer.pack_start(path, True, True, 0)
        action = Gtk.Button(label="更新")
        action.connect("clicked", self.on_install_clicked, [product])
        footer.pack_end(action, False, False, 0)
        content.pack_start(footer, False, False, 0)

        self.rows[product] = {
            "installed": installed,
            "latest": latest,
            "path": path,
            "status_box": status_box,
            "status_icon": status_icon,
            "status": status,
            "action": action,
        }
        self.set_row_state(product, "checking")
        return frame

    @staticmethod
    def version_block(caption):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        caption_label = Gtk.Label(label=caption, xalign=0)
        caption_label.get_style_context().add_class("version-caption")
        value = Gtk.Label(label="—", xalign=0)
        value.get_style_context().add_class("version-value")
        box.pack_start(caption_label, False, False, 0)
        box.pack_start(value, False, False, 0)
        return box, value

    @staticmethod
    def status_badge():
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.get_style_context().add_class("status-badge")
        icon = Gtk.Image()
        icon.set_pixel_size(14)
        label = Gtk.Label()
        box.pack_start(icon, False, False, 0)
        box.pack_start(label, False, False, 0)
        return box, icon, label

    @staticmethod
    def target_option(radio, detail):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.get_style_context().add_class("target-option")
        box.pack_start(radio, False, False, 0)
        detail_label = Gtk.Label(label=detail, xalign=0)
        detail_label.get_style_context().add_class("target-detail")
        box.pack_start(detail_label, False, False, 0)
        return box

    @staticmethod
    def manager_image(size):
        icon_file = HERE / "antigravity-manager.svg"
        if icon_file.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_file),
                    size,
                    size,
                    True,
                )
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except GLib.Error:
                pass
        image = Gtk.Image.new_from_icon_name(
            "system-software-install",
            Gtk.IconSize.DIALOG,
        )
        image.set_pixel_size(size)
        return image

    def preferred_install_mode(self):
        # Follow an existing installation when possible. A fresh install keeps
        # the repository's documented system-wide default.
        if any(
            install.installed_version_for_mode(product, True)
            for product in PRODUCT_ORDER
        ):
            return True
        if any(
            install.installed_version_for_mode(product, False)
            for product in PRODUCT_ORDER
        ):
            return False
        return True

    # -- state and presentation -----------------------------------------

    def target_label(self):
        return "系統範圍（/opt）" if self.system_mode else "目前使用者（~/.local）"

    def set_row_state(self, product, state):
        row = self.rows[product]
        label, icon_name, css_class = STATUS_META[state]
        row["status"].set_text(label)
        row["status_icon"].set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        style = row["status_box"].get_style_context()
        for class_name in STATUS_CLASSES:
            style.remove_class(class_name)
        style.add_class("status-badge")
        style.add_class(css_class)

    def classify_product(self, product):
        data = self.results[product]
        data["target"] = install.installed_version_for_mode(product, self.system_mode)
        data["other"] = install.installed_version_for_mode(product, not self.system_mode)
        available = data["available"]
        if available == "unknown":
            state = "unknown"
        elif data["target"] is None:
            state = "missing"
        elif data["target"][0] == available:
            state = "latest"
        else:
            state = "update"
        data["state"] = state

    def render_product(self, product):
        row = self.rows[product]
        data = self.results.get(product)
        if data is None:
            row["installed"].set_text("—")
            row["latest"].set_text("—")
            row["path"].set_text("尚未檢查")
            row["path"].set_tooltip_text(None)
            self.set_row_state(product, "checking")
            return

        available = data["available"]
        target = data["target"]
        other = data["other"]
        row["installed"].set_text(target[0] if target else "—")
        row["latest"].set_text(available if available != "unknown" else "未知")

        if target:
            path_text = f"安裝位置：{target[1]}"
            row["path"].set_tooltip_text(str(target[1]))
        elif other:
            path_text = f"目標尚未安裝 · 另一位置已有 {other[0]}"
            row["path"].set_tooltip_text(str(other[1]))
        else:
            path_text = f"目標：{self.target_label()}"
            row["path"].set_tooltip_text(None)
        row["path"].set_text(path_text)

        state = data["state"]
        row["action"].set_label("安裝" if state == "missing" else "更新")
        self.set_row_state(product, state)

    def update_target_view(self):
        self.target_hint.set_text(
            "下一次安裝會寫入 /opt，並要求授權"
            if self.system_mode
            else "只影響目前使用者，不需要授權"
        )
        self.action_note.set_text(
            f"將安裝到 {self.target_label()}。"
        )
        for product in self.results:
            self.classify_product(product)
            self.render_product(product)
        self.update_summary()
        self.update_action_controls()

    def update_summary(self):
        if not self.check_ready:
            self.summary_count.set_text("—")
            self.summary_detail.set_text("正在檢查官方版本…")
            return
        installed_count = sum(
            bool(self.results[product]["target"])
            for product in PRODUCT_ORDER
        )
        actionable = self.actionable_products()
        self.summary_count.set_text(f"{installed_count}/{len(PRODUCT_ORDER)} 已安裝")
        if actionable:
            self.summary_detail.set_text(f"{len(actionable)} 個項目可安裝或更新")
        else:
            self.summary_detail.set_text("全部已是最新")

    def actionable_products(self):
        if not self.check_ready:
            return []
        return [
            product
            for product in PRODUCT_ORDER
            if self.results.get(product, {}).get("state") in INSTALLABLE_STATES
        ]

    def update_action_controls(self):
        actionable = set(self.actionable_products())
        if not self.check_ready:
            self.all_button.set_label("等待檢查")
        elif not actionable:
            self.all_button.set_label("全部已是最新")
        else:
            self.all_button.set_label(f"安裝／更新 {len(actionable)} 個項目")
        self.all_button.set_sensitive(bool(actionable) and not self.busy)
        for product, row in self.rows.items():
            row["action"].set_sensitive(
                product in actionable and not self.busy
            )

    def set_busy(self, busy, message=""):
        self.busy = busy
        self.refresh_button.set_sensitive(not busy)
        self.user_radio.set_sensitive(not busy)
        self.system_radio.set_sensitive(not busy)
        if busy:
            self.activity.start()
            self.activity.set_visible(True)
        else:
            self.activity.stop()
            self.activity.set_visible(False)
        self.status_bar.set_text(message)
        self.update_action_controls()

    def on_target_toggled(self, button):
        if not button.get_active():
            return
        self.system_mode = button is self.system_radio
        self.update_target_view()
        if self.check_ready and not self.busy:
            self.status_bar.set_text(f"已切換安裝位置：{self.target_label()}")

    # -- helpers ---------------------------------------------------------

    def append_log(self, text):
        buffer = self.log.get_buffer()
        buffer.insert(buffer.get_end_iter(), text)
        self.log.scroll_to_mark(buffer.get_insert(), 0.0, False, 0.0, 0.0)
        self.log_expander.set_expanded(True)

    def run_in_thread(self, target):
        threading.Thread(target=target, daemon=True).start()

    # -- version check ---------------------------------------------------

    def refresh(self):
        if self.busy:
            return
        self.check_ready = False
        self.results = {}
        for product in PRODUCT_ORDER:
            self.set_row_state(product, "checking")
            self.rows[product]["installed"].set_text("—")
            self.rows[product]["latest"].set_text("—")
            self.rows[product]["path"].set_text("正在讀取官方版本…")
        self.update_summary()
        self.set_busy(True, "正在讀取官方下載頁…")
        self.run_in_thread(self._check_worker)

    def _check_worker(self):
        system_mode = self.system_mode
        try:
            page = install.fetch_text(install.DOWNLOAD_PAGE)
            results = {}
            for product in PRODUCT_ORDER:
                available, _url = install.parse_download(page, product)
                results[product] = {
                    "available": available,
                    "target": install.installed_version_for_mode(product, system_mode),
                    "other": install.installed_version_for_mode(product, not system_mode),
                }
        except (Exception, SystemExit) as error:  # noqa: BLE001 - surfaced in the UI
            GLib.idle_add(self._check_failed, str(error))
            return
        GLib.idle_add(self._check_done, results)

    def _check_failed(self, message):
        self.check_ready = False
        self.results = {}
        self.append_log(f"檢查失敗: {message}\n")
        for product in PRODUCT_ORDER:
            self.rows[product]["installed"].set_text("—")
            self.rows[product]["latest"].set_text("—")
            self.rows[product]["path"].set_text("請重新檢查")
            self.set_row_state(product, "error")
        self.update_summary()
        self.set_busy(False, "檢查失敗，請檢查網路後重新檢查")

    def _check_done(self, results):
        self.results = results
        self.check_ready = True
        self.update_target_view()
        self.set_busy(
            False,
            "全部已是最新"
            if not self.actionable_products()
            else f"{len(self.actionable_products())} 個項目可安裝或更新",
        )

    # -- install ---------------------------------------------------------

    def confirm_system_install(self, products):
        if not self.system_mode:
            return True
        names = "、".join(install.PRODUCTS[product]["name"] for product in products)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
        )
        dialog.set_title("確認系統安裝")
        dialog.set_markup(f"要將 {names} 安裝到系統範圍嗎？")
        dialog.format_secondary_text(
            "接下來會出現系統管理員授權視窗，安裝位置為 /opt。"
        )
        dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        dialog.add_button("繼續", Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def on_install_clicked(self, _button, products):
        if self.busy:
            return
        targets = [
            product
            for product in products
            if self.results.get(product, {}).get("state") in INSTALLABLE_STATES
        ]
        if not targets:
            self.status_bar.set_text("目前沒有需要安裝或更新的項目")
            return
        if not self.confirm_system_install(targets):
            self.status_bar.set_text("已取消安裝")
            return

        command = install_command(targets, self.system_mode)
        names = "、".join(install.PRODUCTS[product]["name"] for product in targets)
        self.append_log(f"\n開始安裝：{names}\n$ {shlex.join(command)}\n")
        self.set_busy(True, f"正在安裝 {names}，請稍候…")
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
        for line in process.stdout or ():
            GLib.idle_add(self.append_log, line)
        process.wait()
        GLib.idle_add(self._install_done, process.returncode, "")

    def _install_done(self, returncode, error):
        if error:
            self.append_log(f"無法執行安裝程式: {error}\n")
        if returncode == 0:
            self.append_log("安裝完成，正在重新檢查版本…\n")
            self.refresh()
            return
        if returncode == 126:
            message = "已取消授權，未進行安裝"
        elif returncode == 127 and error:
            message = f"找不到安裝程式：{error}"
        else:
            message = f"安裝失敗（結束碼 {returncode}）"
        self.append_log(message + "\n")
        self.set_busy(False, message)


def main():
    if not (HERE / "install.py").exists():
        raise SystemExit(f"install.py not found next to gui.py: {HERE / 'install.py'}")
    window = ManagerWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
