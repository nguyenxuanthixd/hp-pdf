"""Cua so chinh HP Cons PDF."""
from __future__ import annotations

import os

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QIcon, QKeySequence,
                         QPixmap, QShortcut)
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QFileDialog,
                             QInputDialog, QLabel, QLineEdit, QMainWindow,
                             QMenu, QMessageBox, QPushButton, QSizePolicy,
                             QSpinBox, QTabWidget, QToolBar, QToolButton,
                             QVBoxLayout, QWidget)

from .. import APP_NAME, APP_VERSION
from ..config import config
from ..core.document import DocumentModel, is_password_error
from ..resources import icon_path, logo_path
from ..utils.errors import friendly_message
from ..utils.fileutils import suffixed_output
from .dialogs.common import default_out_dir
from .dialogs.merge_split import MergeDialog, SplitDialog
from .dialogs.progress import run_task, show_done, show_error
from .dialogs.stamp import PageNumberDialog, WatermarkDialog
from .dialogs.tools import (CompressDialog, ConvertDialog, InsertDialog,
                            OcrDialog, SecurityDialog)
from .document_tab import DocumentTab
from .icons import get_icon
from .render_thread import RenderThread

ZOOM_PRESETS = ["50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%"]

SHAPE_LABELS = {
    "rect": ("shape", "Chữ nhật"),
    "ellipse": ("shape-ellipse", "Elip"),
    "arrow": ("shape-arrow", "Mũi tên"),
    "line": ("shape-line", "Đường thẳng"),
    "pen": ("pen-tool", "Vẽ tay"),
}

HL_LABELS = {
    "highlight": ("highlighter", "Đánh dấu"),
    "hl-ellipse": ("hl-ellipse", "Đánh dấu elip"),
}


class MainWindow(QMainWindow):
    # Tat ca cua so dang mo (cua so dau tien la cua so chinh)
    _instances: list["MainWindow"] = []
    # Clipboard trang DUNG CHUNG moi cua so (copy trang giua cac cua so)
    _page_clipboard: list[dict] = []

    def __init__(self):
        super().__init__()
        MainWindow._instances.append(self)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(icon_path()))
        self.resize(1280, 820)
        self.setAcceptDrops(True)
        self._drag_tab_index: int | None = None

        self.render_thread = RenderThread(self)
        self.render_thread.start()

        self.annot_color = "#E53935"
        self._current_shape = "rect"
        self.sidebar_visible = True
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        # Nhieu tab -> cuon + rut gon ten, KHONG mat tab nao
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # Nut goc phai: danh sach TAT CA file dang mo (bam de nhay toi)
        self._tab_list_btn = QToolButton()
        self._tab_list_btn.setText("☰ Danh sách")
        self._tab_list_btn.setToolTip("Danh sách tất cả file đang mở")
        self._tab_list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_list_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self._tab_list_btn.setStyleSheet(
            "QToolButton{background:#1B75BB;color:white;border:none;"
            "border-radius:4px;padding:3px 10px;margin:2px 6px;"
            "font-weight:bold;font-size:10pt;}"
            "QToolButton:hover{background:#155a90;}"
            "QToolButton::menu-indicator{image:none;}")
        self._tab_list_menu = QMenu(self._tab_list_btn)
        self._tab_list_btn.setMenu(self._tab_list_menu)
        self._tab_list_menu.aboutToShow.connect(self._fill_tab_list_menu)
        self.tabs.setCornerWidget(self._tab_list_btn, Qt.Corner.TopRightCorner)
        # Chuot phai tab + keo tab ra ngoai de tach cua so
        bar = self.tabs.tabBar()
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._tab_context_menu)
        bar.installEventFilter(self)
        # Chuyen tab bang Ctrl+Tab / Ctrl+Shift+Tab (thay cho cuon chuot)
        sc_next = QShortcut(QKeySequence("Ctrl+Tab"), self)
        sc_next.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc_next.activated.connect(lambda: self._cycle_tab(1))
        sc_prev = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        sc_prev.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc_prev.activated.connect(lambda: self._cycle_tab(-1))

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.tabs)
        self.setCentralWidget(central)

        self._build_actions()
        self._build_menu()
        self._build_main_toolbar()
        self._build_view_toolbar()
        self._build_statusbar()
        self._build_empty_state()
        self._update_ui_state()

        self._update_worker = None
        # Tu dong kiem tra cap nhat khi khoi dong (chi o cua so DAU TIEN,
        # chay ngam sau vai giay; offline thi bo qua im lang)
        if (self is MainWindow._instances[0]
                and config.get("auto_check_update", True)):
            QTimer.singleShot(3500, lambda: self.check_updates(manual=False))

    # ================= Actions =================
    def _build_actions(self):
        def act(name, text, slot, shortcut=None, need_doc=True):
            a = QAction(get_icon(name), text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setProperty("need_doc", need_doc)
            return a

        self.act_toggle_sidebar = QAction(
            get_icon("sidebar"), "Ẩn/hiện thanh trang", self)
        self.act_toggle_sidebar.setCheckable(True)
        self.act_toggle_sidebar.setChecked(True)
        self.act_toggle_sidebar.setShortcut(QKeySequence("F4"))
        self.act_toggle_sidebar.setToolTip(
            "Ẩn/hiện thanh trang thu nhỏ bên trái (F4)")
        self.act_toggle_sidebar.toggled.connect(self._toggle_sidebar)

        self.act_open = act("open", "Mở file", self.open_files, "Ctrl+O", False)
        self.act_save = act("save", "Lưu", self.quick_save, "Ctrl+S")
        self.act_save.setToolTip(
            "Lưu (Ctrl+S): ghi mọi chỉnh sửa THẲNG vào file đang mở.\n"
            "Muốn lưu ra file khác, dùng \"Lưu thành...\" (Ctrl+Shift+S).")
        self.act_save_as = act("save", "Lưu thành...", self.save_as,
                               "Ctrl+Shift+S")
        self.act_print = act("print", "In...", self.print_doc, "Ctrl+P")
        self.act_print.setToolTip(
            "In (Ctrl+P): chọn máy in + phạm vi trang, rồi mở thẳng thiết lập "
            "của máy in.")
        self.act_undo = act("undo", "Hoàn tác", self.undo, "Ctrl+Z")
        self.act_merge = act("merge", "Ghép file", self.show_merge, None, False)
        self.act_split = act("split", "Tách file", self.show_split)
        self.act_rot_l = act("rotate-l", "Xoay trái 90°", lambda: self.rotate(270),
                             "Ctrl+Shift+-")
        self.act_rot_r = act("rotate-r", "Xoay phải 90°", lambda: self.rotate(90),
                             "Ctrl+Shift++")
        self.act_delete = act("delete", "Xóa trang", self.delete_pages, "Ctrl+Del")
        self.act_insert = act("insert", "Chèn trang từ PDF khác...", self.show_insert)
        self.act_extract = act("extract", "Trích xuất trang...", self.extract_pages)
        self.act_number = act("number", "Đánh số trang...", self.show_number)
        self.act_wm = act("watermark", "Watermark / Đóng dấu...", self.show_watermark)
        self.act_ocr = act("ocr", "OCR (nhận diện chữ)...", self.show_ocr)
        self.act_convert = act("convert", "Chuyển đổi...", self.show_convert, None, False)
        self.act_compress = act("compress", "Nén PDF...", self.show_compress)
        self.act_security = act("lock", "Bảo mật...", self.show_security)

        # ----- Cong cu chinh sua (checkable) -----
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)

        def tool_act(icon, text, tool):
            a = QAction(get_icon(icon), text, self)
            a.setCheckable(True)
            a.setData(tool)
            self.tool_group.addAction(a)
            return a

        self.act_tool_pan = tool_act("pan", "Xem", "pan")
        self.act_tool_pan.setToolTip(
            "Xem & chọn chữ: rê vào chữ để quét chọn rồi Ctrl+C để copy;\n"
            "kéo chỗ trống để di chuyển trang. Nhấn ESC ở công cụ khác để quay về đây.")
        self.act_tool_select = tool_act("select", "Chọn", "select")
        self.act_tool_select.setToolTip(
            "Chọn đối tượng: quét chuột để chọn nhiều — vùng có chữ sẽ ƯU TIÊN "
            "chọn chữ (nền ô không bị kéo theo);\nmuốn chọn nền/hình tô màu thì "
            "bấm thẳng vào nó. Giữ Ctrl + bấm để chọn thêm/bỏ từng đối tượng.\n"
            "Kéo để di chuyển • Delete để xóa • nháy đúp chữ để sửa.")
        self.act_tool_text = tool_act("text-tool", "Thêm chữ", "text")
        self.act_tool_text.setToolTip("Bấm vào vị trí trên trang để thêm chữ mới")
        self.act_tool_hl = tool_act("highlighter", "Đánh dấu", "highlight")
        self.act_tool_hl.setToolTip("Quét chuột để bôi đánh dấu (highlight)")
        self.act_tool_shape = tool_act("shape", "Vẽ hình", "rect")
        self.act_tool_shape.setToolTip("Kéo chuột để vẽ hình — bấm mũi tên để đổi loại hình")
        self.act_tool_erase = tool_act("erase", "Xóa vùng", "erase")
        self.act_tool_erase.setToolTip(
            "Quét vùng là XÓA NGAY mọi chữ/hình nằm trong vùng "
            "(Ctrl+Z để hoàn tác).\nVới file scan hãy dùng \"Che trắng\".")
        self.act_tool_cover = tool_act("cover", "Che trắng", "cover")
        self.act_tool_cover.setToolTip(
            "Quét vùng để phủ trắng đè lên nội dung — dùng cho file scan.\n"
            "Lớp che chọn/di chuyển/xóa được bằng công cụ Chọn.")
        self.act_tool_pan.setChecked(True)
        self.tool_group.triggered.connect(self._on_tool_changed)
        self.tool_actions = [self.act_tool_pan, self.act_tool_select,
                             self.act_tool_text, self.act_tool_hl,
                             self.act_tool_shape, self.act_tool_erase,
                             self.act_tool_cover]

        self.doc_actions = [self.act_save, self.act_save_as, self.act_print,
                            self.act_undo, self.act_split, self.act_rot_l,
                            self.act_rot_r, self.act_delete, self.act_insert,
                            self.act_extract, self.act_number, self.act_wm,
                            self.act_ocr, self.act_compress, self.act_security]

    def _build_menu(self):
        m_file = self.menuBar().addMenu("&Tệp")
        m_file.addAction(self.act_open)
        self.menu_recent = m_file.addMenu("Mở gần đây")
        self._refresh_recent_menu()
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addAction(self.act_print)
        m_file.addSeparator()
        act_close_tab = QAction("Đóng tab hiện tại", self)
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(
            lambda: self._close_tab(self.tabs.currentIndex()))
        m_file.addAction(act_close_tab)
        m_file.addSeparator()
        act_quit = QAction("Thoát", self)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_page = self.menuBar().addMenu("&Trang")
        for a in (self.act_rot_l, self.act_rot_r, self.act_delete,
                  self.act_insert, self.act_extract):
            m_page.addAction(a)

        m_tools = self.menuBar().addMenu("&Công cụ")
        for a in (self.act_merge, self.act_split, self.act_number, self.act_wm,
                  self.act_ocr, self.act_convert, self.act_compress,
                  self.act_security):
            m_tools.addAction(a)
        m_tools.addSeparator()
        act_outdir = QAction("Chọn thư mục xuất mặc định...", self)
        act_outdir.triggered.connect(self._pick_out_dir)
        m_tools.addAction(act_outdir)

        m_view = self.menuBar().addMenu("&Xem")
        m_view.addAction(self.act_toggle_sidebar)

        m_help = self.menuBar().addMenu("Trợ &giúp")
        act_update = QAction("Kiểm tra cập nhật...", self)
        act_update.triggered.connect(lambda: self.check_updates(manual=True))
        m_help.addAction(act_update)
        self.act_auto_update = QAction("Tự động kiểm tra cập nhật khi mở app",
                                       self)
        self.act_auto_update.setCheckable(True)
        self.act_auto_update.setChecked(bool(config.get("auto_check_update", True)))
        self.act_auto_update.toggled.connect(
            lambda v: config.set("auto_check_update", v))
        m_help.addAction(self.act_auto_update)
        m_help.addSeparator()
        act_about = QAction("Giới thiệu", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    # ================= Toolbar =================
    def _menu_button(self, icon_name: str, text: str, actions) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(get_icon(icon_name))
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn)
        for a in actions:
            menu.addAction(a)
        btn.setMenu(menu)
        return btn

    def _color_icon(self, color: str, size: int = 30) -> QIcon:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        from PyQt6.QtGui import QPainter
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(QColor("#B0B4B8"))
        p.drawRoundedRect(4, 4, size - 8, size - 8, 5, 5)
        p.end()
        return QIcon(pm)

    def _build_main_toolbar(self):
        """MOT hang cong cu duy nhat: file | trang | chinh sua | tim kiem."""
        tb = QToolBar("Công cụ chính")
        tb.setMovable(False)
        tb.setIconSize(QSize(26, 26))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addAction(self.act_print)
        tb.addAction(self.act_undo)
        tb.addSeparator()
        self.act_insert.setIconText("Chèn trang")
        tb.addAction(self.act_insert)
        self.act_rot_l.setIconText("Xoay trái")
        self.act_rot_r.setIconText("Xoay phải")
        tb.addAction(self.act_rot_l)
        tb.addAction(self.act_rot_r)

        # Nut menu "Trang": gom cac thao tac trang
        self.btn_page_menu = self._menu_button(
            "page-menu", "Trang",
            [self.act_rot_l, self.act_rot_r, self.act_delete,
             self.act_insert, self.act_extract])
        tb.addWidget(self.btn_page_menu)

        # Nut menu "Cong cu": gom cac chuc nang xu ly file
        self.btn_tools_menu = self._menu_button(
            "tools-menu", "Công cụ",
            [self.act_number, self.act_wm, self.act_ocr, self.act_convert,
             self.act_compress, self.act_security])
        tb.addWidget(self.btn_tools_menu)
        tb.addSeparator()

        # Nhom cong cu chinh sua
        tb.addAction(self.act_tool_pan)
        tb.addAction(self.act_tool_select)
        tb.addAction(self.act_tool_text)

        # Nut "Danh dau" co menu chon kieu (o vuong / elip)
        self.btn_hl = QToolButton()
        self.btn_hl.setDefaultAction(self.act_tool_hl)
        self.btn_hl.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_hl.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        hl_menu = QMenu(self.btn_hl)
        for key, (icon, label) in HL_LABELS.items():
            a = hl_menu.addAction(get_icon(icon), label)
            a.setData(key)
        hl_menu.triggered.connect(self._on_hl_picked)
        self.btn_hl.setMenu(hl_menu)
        tb.addWidget(self.btn_hl)

        # Nut "Ve hinh" co menu chon loai hinh
        self.btn_shape = QToolButton()
        self.btn_shape.setDefaultAction(self.act_tool_shape)
        self.btn_shape.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_shape.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        shape_menu = QMenu(self.btn_shape)
        for key, (icon, label) in SHAPE_LABELS.items():
            a = shape_menu.addAction(get_icon(icon), label)
            a.setData(key)
        shape_menu.triggered.connect(self._on_shape_picked)
        self.btn_shape.setMenu(shape_menu)
        tb.addWidget(self.btn_shape)

        tb.addAction(self.act_tool_erase)
        tb.addAction(self.act_tool_cover)

        # Nut chon mau
        self.btn_color = QToolButton()
        self.btn_color.setIcon(self._color_icon(self.annot_color))
        self.btn_color.setText("Màu")
        self.btn_color.setToolTip("Chọn màu cho chữ / hình vẽ / đánh dấu")
        self.btn_color.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_color.clicked.connect(self._pick_color)
        tb.addWidget(self.btn_color)
        tb.addSeparator()

        # Ghep / Tach file: dua ve cuoi theo yeu cau
        tb.addAction(self.act_merge)
        tb.addAction(self.act_split)

        # Day o tim kiem sang phai
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("Tìm kiếm...  (Ctrl+F)")
        self.ed_search.setFixedWidth(190)
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.returnPressed.connect(lambda: self._search(False))
        tb.addWidget(self.ed_search)
        act_sprev = QAction(get_icon("up"), "Kết quả trước", self)
        act_sprev.triggered.connect(lambda: self._search(True))
        act_snext = QAction(get_icon("down"), "Kết quả sau", self)
        act_snext.triggered.connect(lambda: self._search(False))
        tb.addAction(act_sprev)
        tb.addAction(act_snext)
        self.lb_search = QLabel("")
        tb.addWidget(self.lb_search)

        act_focus_search = QAction(self)
        act_focus_search.setShortcut(QKeySequence("Ctrl+F"))
        act_focus_search.triggered.connect(
            lambda: (self.ed_search.setFocus(), self.ed_search.selectAll()))
        self.addAction(act_focus_search)

        # Ctrl+A: chon tat ca trang (dang go chu thi van la chon het chu)
        act_sel_all = QAction(self)
        act_sel_all.setShortcut(QKeySequence("Ctrl+A"))
        act_sel_all.triggered.connect(self._select_all_pages)
        self.addAction(act_sel_all)

        self.addToolBar(tb)

    def _build_view_toolbar(self):
        """Dieu khien xem chuyen xuong thanh trang thai (gon 1 tang toolbar)."""
        sb = self.statusBar()

        def tool_btn(icon, tip, slot, checkable=False):
            b = QToolButton()
            b.setIcon(get_icon(icon, size=22))
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            return b

        sb.addPermanentWidget(tool_btn("prev", "Trang trước",
                                       lambda: self._goto_delta(-1)))
        self.sp_page = QSpinBox()
        self.sp_page.setRange(1, 1)
        self.sp_page.setFixedWidth(62)
        self.sp_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sp_page.editingFinished.connect(self._goto_spin)
        sb.addPermanentWidget(self.sp_page)
        self.lb_pagecount = QLabel(" / 0 ")
        sb.addPermanentWidget(self.lb_pagecount)
        sb.addPermanentWidget(tool_btn("next", "Trang sau",
                                       lambda: self._goto_delta(1)))

        sb.addPermanentWidget(tool_btn("zoom-out", "Thu nhỏ",
                                       lambda: self._view_call("zoom_out")))
        self.cb_zoom = QComboBox()
        self.cb_zoom.setEditable(True)
        self.cb_zoom.addItems(ZOOM_PRESETS)
        self.cb_zoom.setFixedWidth(82)
        self.cb_zoom.lineEdit().returnPressed.connect(self._zoom_from_combo)
        self.cb_zoom.activated.connect(lambda _: self._zoom_from_combo())
        sb.addPermanentWidget(self.cb_zoom)
        sb.addPermanentWidget(tool_btn("zoom-in", "Phóng to",
                                       lambda: self._view_call("zoom_in")))

        self.btn_fit_w = tool_btn("fit-width", "Vừa chiều ngang",
                                  lambda: self._set_fit("fit-width"), True)
        self.btn_fit_w.setChecked(True)
        self.btn_fit_p = tool_btn("fit-page", "Vừa cả trang",
                                  lambda: self._set_fit("fit-page"), True)
        sb.addPermanentWidget(self.btn_fit_w)
        sb.addPermanentWidget(self.btn_fit_p)

    def _build_statusbar(self):
        self.lb_status_file = QLabel(
            "Chưa mở file nào — kéo-thả file PDF vào đây hoặc bấm \"Mở file\"")
        self.statusBar().addWidget(self.lb_status_file, 1)

    def _build_empty_state(self):
        """Man hinh chao khi chua mo file."""
        self.empty = QWidget()
        v = QVBoxLayout(self.empty)
        v.addStretch(2)
        logo = QLabel()
        pm = QPixmap(logo_path())
        if not pm.isNull():
            logo.setPixmap(pm.scaledToHeight(
                110, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(logo)
        t = QLabel(APP_NAME)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-size: 15pt; color: #4A4F54; font-weight: 600;")
        v.addWidget(t)
        hint = QLabel("Kéo-thả file PDF vào cửa sổ này, hoặc:")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hint)
        btn = QPushButton("Mở file PDF...")
        btn.setObjectName("primary")
        btn.setFixedWidth(220)
        btn.clicked.connect(self.open_files)
        v.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.btn_welcome_merge = QPushButton("Ghép file PDF...")
        self.btn_welcome_merge.setFixedWidth(220)
        self.btn_welcome_merge.clicked.connect(self.show_merge)
        v.addWidget(self.btn_welcome_merge, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addStretch(3)
        self.tabs.addTab(self.empty, "Bắt đầu")
        self.tabs.tabBar().setTabButton(
            0, self.tabs.tabBar().ButtonPosition.RightSide, None)

    # ================= Cong cu chinh sua =================
    def _on_tool_changed(self, action: QAction):
        tool = action.data()
        tab = self.current_tab()
        if tab:
            tab.view.set_tool(tool)

    def _on_shape_picked(self, action: QAction):
        key = action.data()
        self._current_shape = key
        icon, label = SHAPE_LABELS[key]
        self.act_tool_shape.setIcon(get_icon(icon))
        self.act_tool_shape.setText(label)
        self.act_tool_shape.setData(key)
        self.act_tool_shape.setChecked(True)
        self._on_tool_changed(self.act_tool_shape)

    def _on_hl_picked(self, action: QAction):
        key = action.data()
        icon, label = HL_LABELS[key]
        self.act_tool_hl.setIcon(get_icon(icon))
        self.act_tool_hl.setText(label)
        self.act_tool_hl.setData(key)
        self.act_tool_hl.setChecked(True)
        self._on_tool_changed(self.act_tool_hl)

    def _pick_color(self):
        col = QColorDialog.getColor(QColor(self.annot_color), self,
                                    "Chọn màu")
        if not col.isValid():
            return
        self.annot_color = col.name()
        self.btn_color.setIcon(self._color_icon(self.annot_color))
        tab = self.current_tab()
        if tab:
            tab.view.annot_color = self.annot_color
            tab.view.apply_color_to_selection(self.annot_color)

    def _toggle_sidebar(self, checked: bool):
        self.sidebar_visible = checked
        # Ap cho MOI tab (nut mui ten dong bo tren tat ca)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab):
                w.thumbs.setVisible(checked)
                w.update_toggle_button(checked)

    # ================= Tabs / mo file =================
    def current_tab(self) -> DocumentTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentTab) else None

    def current_model(self) -> DocumentModel | None:
        tab = self.current_tab()
        return tab.model if tab else None

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Mở file PDF", config.get("last_open_dir", ""),
            "File PDF (*.pdf)")
        for f in files:
            self.open_path(f)
        if files:
            config.set("last_open_dir", os.path.dirname(files[0]))

    def open_path(self, path: str):
        path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab) and w.model.path == path:
                self.tabs.setCurrentIndex(i)
                return
        password = ""
        for attempt in range(4):
            try:
                model = DocumentModel(path, password)
                break
            except Exception as e:
                if is_password_error(e):
                    if attempt >= 3:
                        show_error(self, "Mật khẩu không đúng (đã thử 3 lần).")
                        return
                    pw, ok = QInputDialog.getText(
                        self, "File có mật khẩu",
                        f"File \"{os.path.basename(path)}\" được bảo vệ bằng "
                        "mật khẩu.\nNhập mật khẩu để mở:",
                        QLineEdit.EchoMode.Password)
                    if not ok:
                        return
                    password = pw
                    continue
                show_error(self, friendly_message(e))
                return
        tab = DocumentTab(model, self.render_thread)
        self._add_doc_tab(tab)
        config.add_recent(path)
        self._refresh_recent_menu()

    # ================= Nhieu cua so: tach / gop tab =================
    def _wire_tab(self, tab: DocumentTab):
        tab.stateChanged.connect(self._update_ui_state)
        tab.thumbs.extractRequested.connect(self._extract_indices)
        tab.thumbs.pdfFilesDropped.connect(self._merge_dropped_files)
        tab.thumbs.copyRequested.connect(self._copy_pages)
        tab.thumbs.pasteRequested.connect(self._paste_pages)
        tab.thumbs.clipboard_count = lambda: len(MainWindow._page_clipboard)
        tab.view.panRequested.connect(self._back_to_pan)
        tab.sidebarToggleRequested.connect(self._toggle_sidebar_from_button)

    def _toggle_sidebar_from_button(self):
        # Nut mui ten trong tab -> dao trang thai chung (dong bo menu/F4)
        self.act_toggle_sidebar.setChecked(not self.sidebar_visible)

    def _unwire_tab(self, tab: DocumentTab):
        pairs = [(tab.stateChanged, self._update_ui_state),
                 (tab.thumbs.extractRequested, self._extract_indices),
                 (tab.thumbs.pdfFilesDropped, self._merge_dropped_files),
                 (tab.thumbs.copyRequested, self._copy_pages),
                 (tab.thumbs.pasteRequested, self._paste_pages),
                 (tab.view.panRequested, self._back_to_pan)]
        for sig, slot in pairs:
            try:
                sig.disconnect(slot)
            except TypeError:
                pass

    def _add_doc_tab(self, tab: DocumentTab):
        """Gan 1 tab tai lieu vao cua so nay (mo moi hoac nhan tu cua so khac)."""
        self._wire_tab(tab)
        tab.thumbs.setVisible(self.sidebar_visible)
        tab.update_toggle_button(self.sidebar_visible)
        idx = self.tabs.addTab(tab, tab.model.display_name)
        self.tabs.setTabToolTip(idx, tab.model.path)
        self.tabs.setCurrentIndex(idx)
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is getattr(self, "empty", None):
                self.tabs.removeTab(i)
                break
        # Mo tai lieu -> bung het man hinh (theo yeu cau Sep)
        if not self.isMaximized() and not self.isFullScreen():
            self.showMaximized()
        self._update_ui_state()

    def _take_tab(self, index: int) -> DocumentTab | None:
        w = self.tabs.widget(index)
        if not isinstance(w, DocumentTab):
            return None
        self._unwire_tab(w)
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            if self is not MainWindow._instances[0]:
                self.close()  # cua so phu het tab thi tu dong
            else:
                self._build_empty_state()
        self._update_ui_state()
        return w

    def detach_tab(self, index: int, global_pos=None):
        """Tach tab thanh cua so rieng."""
        if self.tabs.count() <= 1 and self is not MainWindow._instances[0] \
                and isinstance(self.tabs.widget(index), DocumentTab):
            return  # cua so phu chi co 1 tab: tach = chinh no, bo qua
        tab = self._take_tab(index)
        if tab is None:
            return
        win = MainWindow()
        win.resize(self.size())
        if global_pos is not None:
            win.move(global_pos.x() - 300, max(0, global_pos.y() - 20))
        win.show()
        tab.rebind_render_thread(win.render_thread)
        win._add_doc_tab(tab)

    def _move_tab_to(self, index: int, target: "MainWindow"):
        tab = self._take_tab(index)
        if tab is None:
            return
        tab.rebind_render_thread(target.render_thread)
        target._add_doc_tab(tab)
        target.raise_()
        target.activateWindow()

    def _fill_tab_list_menu(self):
        """Menu liet ke TAT CA file dang mo trong cua so nay -> nhay toi."""
        self._tab_list_menu.clear()
        cur = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not isinstance(w, DocumentTab):
                continue
            name = w.model.display_name
            a = self._tab_list_menu.addAction(
                ("● " if i == cur else "     ") + name)
            a.triggered.connect(lambda _c=False, idx=i: self.tabs.setCurrentIndex(idx))
        if self._tab_list_menu.isEmpty():
            self._tab_list_menu.addAction("(Chưa mở file nào)").setEnabled(False)

    def _tab_context_menu(self, pos):
        bar = self.tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0 or not isinstance(self.tabs.widget(index), DocumentTab):
            return
        menu = QMenu(self)
        act_detach = menu.addAction("Tách ra cửa sổ riêng")
        others = [w for w in MainWindow._instances if w is not self]
        move_map = {}
        if others:
            if len(others) == 1:
                a = menu.addAction(f"Gộp về cửa sổ: {others[0].windowTitle()}")
                move_map[a] = others[0]
            else:
                sub = menu.addMenu("Chuyển sang cửa sổ")
                for w in others:
                    a = sub.addAction(w.windowTitle())
                    move_map[a] = w
        menu.addSeparator()
        act_close = menu.addAction("Đóng tab")
        chosen = menu.exec(bar.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_detach:
            self.detach_tab(index, bar.mapToGlobal(pos))
        elif chosen == act_close:
            self._close_tab(index)
        elif chosen in move_map:
            self._move_tab_to(index, move_map[chosen])

    def _cycle_tab(self, delta: int):
        n = self.tabs.count()
        if n > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + delta) % n)

    def eventFilter(self, obj, event):
        # Keo tab ra ngoai thanh tab -> tach thanh cua so rieng
        if obj is self.tabs.tabBar():
            et = event.type()
            # Chan CUON CHUOT doi tab (hay bam nham) -> dung Ctrl+Tab thay the
            if et == event.Type.Wheel:
                return True
            if et == event.Type.MouseButtonPress and \
                    event.button() == Qt.MouseButton.LeftButton:
                self._drag_tab_index = obj.tabAt(event.position().toPoint())
            elif et == event.Type.MouseButtonRelease and \
                    event.button() == Qt.MouseButton.LeftButton:
                idx = self._drag_tab_index
                self._drag_tab_index = None
                if idx is not None and idx >= 0 and \
                        isinstance(self.tabs.widget(idx), DocumentTab):
                    gp = event.globalPosition().toPoint()
                    from PyQt6.QtCore import QRect
                    # Tha len cua so KHAC -> gop tab vao cua so do (keo ve/qua lai)
                    target = None
                    for w in MainWindow._instances:
                        if w is not self and w.isVisible() and \
                                w.frameGeometry().contains(gp):
                            target = w
                            break
                    if target is not None:
                        QTimer.singleShot(
                            0, lambda i=idx, t=target: self._move_tab_to(i, t))
                    else:
                        bar_rect = QRect(obj.mapToGlobal(QPoint(0, 0)),
                                         obj.size())
                        zone = bar_rect.adjusted(-60, -40, 60, 120)
                        if not zone.contains(gp):
                            QTimer.singleShot(
                                0, lambda i=idx, g=gp: self.detach_tab(i, g))
        return super().eventFilter(obj, event)

    def _close_tab(self, index: int):
        w = self.tabs.widget(index)
        if not isinstance(w, DocumentTab):
            return
        if w.model.modified:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Chưa lưu chỉnh sửa")
            box.setText(
                f"Tài liệu \"{w.model.display_name}\" có chỉnh sửa chưa lưu "
                "(xoay/xóa/sắp xếp/chèn trang/ghi chú).")
            btn_save = box.addButton("Lưu và đóng",
                                     QMessageBox.ButtonRole.AcceptRole)
            btn_discard = box.addButton("Đóng không lưu",
                                        QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_save)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_cancel:
                return
            if clicked == btn_save:
                if not self.quick_save(w):
                    return
        self.tabs.removeTab(index)
        w.close_document()
        w.deleteLater()
        if self.tabs.count() == 0:
            if self is not MainWindow._instances[0]:
                self.close()  # cua so phu het tab -> tu dong
            else:
                self._build_empty_state()
        self._update_ui_state()

    def _on_tab_changed(self, _index: int):
        tab = self.current_tab()
        if tab:
            checked = self.tool_group.checkedAction()
            tab.view.set_tool(checked.data() if checked else "pan")
            tab.view.annot_color = self.annot_color
            tab.thumbs.setVisible(self.sidebar_visible)
        # Lazy render: chi tab DANG XEM render thumbnail; tab an huy yeu cau
        # dang cho de khong tranh khoa pdfium lam trang dang xem giat.
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab):
                w.thumbs.set_active(w is tab)
        self._update_ui_state()
        self.lb_search.setText("")

    def _back_to_pan(self):
        """ESC trong khung xem -> quay ve cong cu Xem (pan)."""
        self.act_tool_pan.setChecked(True)
        tab = self.current_tab()
        if tab:
            tab.view.set_tool("pan")

    # ================= Hoan tac =================
    def undo(self):
        tab = self.current_tab()
        if not tab:
            return
        tab.view.flush_pending_edits()
        desc = tab.model.undo()
        if desc is None:
            self.statusBar().showMessage("Không còn thao tác để hoàn tác.", 4000)
            return
        tab.refresh()
        tab.invalidate_search_cache()
        self.statusBar().showMessage(f"Đã hoàn tác: {desc}", 5000)
        self._update_ui_state()

    # ================= In tai lieu =================
    def print_doc(self):
        """In: chon may in + pham vi -> mo THANG hop thoai goc cua driver
        (giao dien native, day du) -> in qua GDI giu nguyen moi thiet lap.
        Thiet lap duoc ghi nho trong phien (dong file thi ve mac dinh)."""
        tab = self.current_tab()
        if not tab:
            return
        from PyQt6.QtPrintSupport import QPrinterInfo

        from ..core import winprint
        from .dialogs.print_dialog import PrintDialog

        names = [i.printerName() for i in QPrinterInfo.availablePrinters()]
        if not names:
            self._print_with_dialog()
            return
        default_info = QPrinterInfo.defaultPrinter()
        default_name = default_info.printerName() if default_info and \
            not default_info.isNull() else names[0]
        last = tab.print_printer or config.get("last_printer", "")

        def get_preview(page_index, max_px):
            return self._render_preview_pixmap(tab, page_index, max_px)

        prefs = config.get("print_prefs", {}) or {}
        dlg = PrintDialog(tab.model.page_count, tab.view.current_page,
                          names, default_name, last, int(self.winId()),
                          get_preview, self, prefs=prefs)
        if not dlg.exec():
            return
        name = dlg.selected_printer()
        config.set("last_printer", name)
        # Nho tuy chinh in cho lan sau
        config.set("print_prefs", {
            "copies": dlg.copies(),
            "color": dlg.color_mode(),
            "paper": dlg.paper(),
            "duplex": dlg.duplex(),
            "orientation": dlg.orientation(),
            "scale_mode": dlg.scale_mode(),
            "custom_percent": dlg.custom_percent(),
        })
        pages = dlg.page_indices()

        # Ap thiet lap tu hop thoai vao DEVMODE (huong giay, den trang).
        # So ban xu ly bang cach nhan doi danh sach trang (collated) cho
        # chac an voi moi driver -> khong dung dmCopies de tranh in gap doi.
        dm = dlg.devmode_bytes()
        orient = dlg.orientation()
        try:
            dm = winprint.set_devmode_fields(
                dm,
                orientation=None if orient == "auto" else orient,
                color=dlg.color_mode(),
                paper=dlg.paper(),
                duplex=dlg.duplex())
        except Exception:
            pass
        tab.print_printer = name
        tab.print_devmode = dm  # nho cho lan in sau (trong phien)
        copies = dlg.copies()
        if copies > 1:
            pages = pages * copies
        self._gdi_print(tab, name, dm, pages,
                        scale_mode=dlg.scale_mode(),
                        custom_percent=dlg.custom_percent())

    def _render_preview_pixmap(self, tab, page_index, max_px):
        """Anh xem truoc cho hop thoai in (render nho, kem ghi chu)."""
        from PyQt6.QtGui import QPainter, QPixmap

        from .pdf_view import _draw_annot
        from .render_thread import pil_to_qimage

        model = tab.model
        # uoc luong ti le de canh dai nhat ~ max_px
        pw, ph = 595, 842
        try:
            sz = model.page_size(page_index)
            if sz:
                pw, ph = sz
        except Exception:
            pass
        scale = max(0.2, min(2.0, max_px / max(pw, ph)))
        pil = model.render_page(page_index, scale)
        img = pil_to_qimage(pil)
        ref = model.pages[page_index]
        if ref.annots:
            ap = QPainter(img)
            ap.setRenderHint(QPainter.RenderHint.Antialiasing)
            for an in ref.annots:
                _draw_annot(ap, an, scale, False)
            ap.end()
        return QPixmap.fromImage(img)

    def _gdi_print(self, tab, name, devmode, pages,
                   scale_mode="fit", custom_percent=100.0):
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QImage, QPainter, QTransform
        from PyQt6.QtWidgets import QApplication, QProgressDialog

        from ..core import winprint
        from .pdf_view import _draw_annot
        from .render_thread import pil_to_qimage

        model = tab.model
        progress = QProgressDialog("Đang chuẩn bị trang in...", "Hủy",
                                   0, len(pages), self)
        progress.setWindowTitle("Đang in")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        import threading
        cancel = threading.Event()

        def get_bgr(i, max_w, max_h):
            # Render KHOP do phan giai vung in cua may in (max_w x max_h px)
            # de in NET 1:1, khong bi phong to gay mo. Gioi han canh dai <= CAP
            # px de khong ton qua nhieu bo nho voi ban ve kho lon.
            pw_pt, ph_pt = model.page_size(i)
            long_pt = max(pw_pt, ph_pt, 1)
            short_pt = max(min(pw_pt, ph_pt), 1)
            long_px = max(max_w, max_h)
            short_px = min(max_w, max_h)
            scale = min(long_px / long_pt, short_px / short_pt)
            # CAP du lon de anh KHOP vung in (1:1, khong bi phong -> khong mo);
            # chi gioi han voi trang cuc lon de khong tran bo nho.
            CAP = 10000
            scale = min(scale, CAP / long_pt)
            scale = max(scale, 1.0)
            dpi = scale * 72.0
            pil = model.render_page(i, scale, for_print=True)
            img = pil_to_qimage(pil)
            ref = model.pages[i]
            if ref.annots:
                ap = QPainter(img)
                ap.setRenderHint(QPainter.RenderHint.Antialiasing)
                for an in ref.annots:
                    _draw_annot(ap, an, scale, False)
                ap.end()
            # Tu xoay cho vua chieu giay
            if (img.width() > img.height()) != (max_w > max_h):
                img = img.transformed(QTransform().rotate(90))
            img = img.convertToFormat(QImage.Format.Format_BGR888)
            w, h = img.width(), img.height()
            data = bytes(img.constBits().asstring(img.sizeInBytes()))
            return (w, h, data, dpi)

        def prog(k, total, msg):
            progress.setValue(k)
            progress.setLabelText(msg)
            QApplication.processEvents()
            if progress.wasCanceled():
                cancel.set()

        # IN VECTOR truc tiep (net nhat, nhu Excel) khi trang KHONG co ghi chu
        # minh them. Co ghi chu -> in anh (get_bgr) de giu ghi chu.
        import pypdfium2.raw as pdfium_c

        from ..core.document import PDFIUM_LOCK
        has_annots = any(model.pages[i].annots for i in pages)
        draw_page = None
        if not has_annots:
            def draw_page(hdc, i, hres, vres, dpi_x, dpi_y):
                ref = model.pages[i]
                disp_w, disp_h = model.page_size(i)   # da tinh ref.rotation
                auto = 90 if ((disp_w > disp_h) != (hres > vres)) else 0
                final_w, final_h = (disp_h, disp_w) if auto else (disp_w, disp_h)
                fw = final_w * dpi_x / 72.0
                fh = final_h * dpi_y / 72.0
                if scale_mode == "actual":
                    r = 1.0
                elif scale_mode == "custom":
                    r = custom_percent / 100.0
                else:
                    r = min(hres / max(fw, 1), vres / max(fh, 1))
                dw, dh = int(fw * r), int(fh * r)
                dx, dy = (hres - dw) // 2, (vres - dh) // 2
                rot = ((ref.rotation + auto) // 90) % 4
                flags = pdfium_c.FPDF_PRINTING | pdfium_c.FPDF_ANNOT
                with PDFIUM_LOCK:
                    page = ref.source.doc[ref.index]
                    try:
                        pdfium_c.FPDF_RenderPage(hdc, page.raw, dx, dy, dw, dh,
                                                 rot, flags)
                    finally:
                        page.close()

        result = winprint.gdi_print(name, devmode, pages, get_bgr,
                                    doc_name=model.display_name,
                                    progress=prog, cancel=cancel,
                                    scale_mode=scale_mode,
                                    custom_percent=custom_percent,
                                    draw_page=draw_page)
        progress.setValue(len(pages))
        if result is winprint.UNAVAILABLE:
            self._print_with_dialog()
            return
        if not cancel.is_set():
            self.statusBar().showMessage(
                f"Đã gửi {result} trang tới máy in \"{name}\".", 6000)

    def _print_with_dialog(self):
        tab = self.current_tab()
        if not tab:
            return
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

        model = tab.model
        n = model.page_count
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(model.display_name)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("In tài liệu")
        dlg.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, True)
        dlg.setOption(QPrintDialog.PrintDialogOption.PrintCurrentPage, True)
        dlg.setMinMax(1, n)
        if dlg.exec() != QPrintDialog.DialogCode.Accepted:
            return
        pr = printer.printRange()
        if pr == QPrinter.PrintRange.PageRange:
            a = max(1, printer.fromPage())
            b = printer.toPage() or n
            pages = list(range(a - 1, min(b, n)))
        elif pr == QPrinter.PrintRange.CurrentPage:
            pages = [tab.view.current_page]
        else:
            pages = list(range(n))
        if not pages:
            pages = list(range(n))
        self._render_to_printer(printer, pages)

    def _render_to_printer(self, printer, pages: list[int],
                           auto_rotate: bool = True):
        """Ve cac trang (kem ghi chu) ra may in.

        auto_rotate=True: tu xoay trang ngang cho vua giay doc va nguoc lai
        (dung khi huong = Tu dong). False: giu dung huong nguoi dung chon."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainter, QTransform
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtWidgets import QApplication, QProgressDialog

        from .pdf_view import _draw_annot
        from .render_thread import pil_to_qimage

        tab = self.current_tab()
        if not tab or not pages:
            return
        model = tab.model
        dpi = min(printer.resolution() or 300, 300)
        progress = QProgressDialog("Đang chuẩn bị trang in...", "Hủy",
                                   0, len(pages), self)
        progress.setWindowTitle("Đang in")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        painter = QPainter()
        if not painter.begin(printer):
            show_error(self, "Không khởi động được máy in.\n"
                             "Hãy kiểm tra máy in đã bật và sẵn sàng chưa.")
            return
        canceled = False
        try:
            for k, i in enumerate(pages):
                progress.setValue(k)
                progress.setLabelText(
                    f"Đang in trang {i + 1} ({k + 1}/{len(pages)})...")
                QApplication.processEvents()
                if progress.wasCanceled():
                    printer.abort()
                    canceled = True
                    break
                if k:
                    printer.newPage()
                scale = dpi / 72.0
                img = pil_to_qimage(model.render_page(i, scale))
                ref = model.pages[i]
                if ref.annots:
                    ap = QPainter(img)
                    ap.setRenderHint(QPainter.RenderHint.Antialiasing)
                    for an in ref.annots:
                        _draw_annot(ap, an, scale, False)
                    ap.end()
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                if auto_rotate and (img.width() > img.height()) != \
                        (page_rect.width() > page_rect.height()):
                    img = img.transformed(QTransform().rotate(90))
                ratio = min(page_rect.width() / img.width(),
                            page_rect.height() / img.height())
                w, h = img.width() * ratio, img.height() * ratio
                painter.drawImage(
                    QRectF((page_rect.width() - w) / 2,
                           (page_rect.height() - h) / 2, w, h), img)
        finally:
            painter.end()
            progress.setValue(len(pages))
        if not canceled:
            self.statusBar().showMessage(
                f"Đã gửi {len(pages)} trang tới máy in "
                f"\"{printer.printerName() or 'mặc định'}\".", 6000)

    # ================= Copy / dan trang, gop file tha vao =================
    def _copy_pages(self, pages: list[int]):
        tab = self.current_tab()
        if not tab or not pages:
            return
        MainWindow._page_clipboard = tab.model.copy_page_data(pages)
        self.statusBar().showMessage(
            f"Đã copy {len(pages)} trang — chuột phải hoặc Ctrl+V trên thanh "
            "trang thu nhỏ để dán (kể cả ở cửa sổ khác).", 6000)

    def _paste_pages(self, at: int):
        tab = self.current_tab()
        if not tab or not MainWindow._page_clipboard:
            return
        try:
            n = tab.model.paste_pages(MainWindow._page_clipboard, at)
        except Exception as e:
            show_error(self, friendly_message(e))
            return
        tab.refresh()
        tab.invalidate_search_cache()
        self.statusBar().showMessage(f"Đã dán {n} trang vào vị trí {at + 1}.", 5000)

    def _merge_dropped_files(self, paths: list[str], drop_row: int):
        """Tha file PDF vao thanh trang -> hoi VI TRI GHEP roi gop (Ctrl+Z hoan tac)."""
        tab = self.current_tab()
        if not tab:
            for p in paths:
                self.open_path(p)
            return
        from .dialogs.merge_drop import MergeDropDialog
        from .dialogs.merge_split import check_pdf_password
        dlg = MergeDropDialog(paths, tab.model.page_count, drop_row, self)
        if not dlg.exec():
            return
        at = dlg.insert_at()
        at = max(0, min(at, tab.model.page_count))
        total = 0
        for p in paths:
            pw = check_pdf_password(self, p)
            if pw is None:
                continue
            try:
                n = tab.model.insert_from_pdf(p, at + total, password=pw)
                total += n
            except Exception as e:
                show_error(self, friendly_message(e))
        if total:
            tab.refresh()
            tab.invalidate_search_cache()
            vitri = f"trước trang {at + 1}" if at < tab.model.page_count - total \
                else "cuối tài liệu"
            self.statusBar().showMessage(
                f"Đã gộp {total} trang vào {vitri} (Ctrl+Z để hoàn tác) — "
                "dùng \"Lưu\" để xuất file.", 8000)

    # ================= Cap nhat (auto-update) =================
    def check_updates(self, manual: bool = False):
        """Kiem tra ban moi tren GitHub. manual=True: bao ket qua ca khi khong
        co ban moi / loi mang. manual=False (tu dong): chi bao khi CO ban moi."""
        from ..core import updater
        from ..core.worker import Worker

        if getattr(self, "_update_worker", None) is not None:
            return  # dang kiem tra

        worker = Worker(lambda progress, cancel: updater.check_latest())
        self._update_worker = worker

        def done(info):
            self._update_worker = None
            if info is None:
                if manual:
                    QMessageBox.information(
                        self, "Cập nhật",
                        f"Bạn đang dùng phiên bản mới nhất ({APP_VERSION}).")
                return
            if not manual and info.version == config.get("skip_update_version", ""):
                return  # nguoi dung da chon bo qua ban nay
            self._offer_update(info)

        def fail(msg):
            self._update_worker = None
            if manual:
                show_error(self, msg, title="Kiểm tra cập nhật")

        worker.finished_ok.connect(done)
        worker.failed.connect(fail)
        worker.start()

    @staticmethod
    def _clean_notes(raw: str) -> str:
        """Loc noi dung cap nhat: bo dong chua LINK/URL va tieu de tu dong
        cua GitHub (What's Changed / Full Changelog) -> chi con noi dung."""
        out = []
        for ln in (raw or "").splitlines():
            s = ln.strip()
            low = s.lower()
            if "http://" in low or "https://" in low:
                continue
            if low.startswith("full changelog"):
                continue
            if low in ("## what's changed", "what's changed", "##"):
                continue
            # bo ky hieu markdown dau dong cho de doc
            s = s.lstrip("#").strip()
            if s.startswith("* "):
                s = "•" + s[1:]
            out.append(s)
        text = "\n".join(out).strip()
        return text

    def _offer_update(self, info):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Có bản cập nhật mới")
        notes = self._clean_notes(info.notes)
        if len(notes) > 1500:
            notes = notes[:1500] + "..."
        box.setText(
            f"Đã có phiên bản mới <b>{info.version}</b> "
            f"(bạn đang dùng {APP_VERSION}).")
        if notes:
            box.setInformativeText("Nội dung cập nhật:\n" + notes)
        btn_install = box.addButton("Tải & cài đặt",
                                    QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Để sau", QMessageBox.ButtonRole.RejectRole)
        btn_skip = box.addButton("Bỏ qua bản này",
                                 QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_skip:
            config.set("skip_update_version", info.version)
            return
        if clicked == btn_install:
            self._download_and_install(info)

    def _download_and_install(self, info):
        import sys
        import tempfile

        from ..core import updater

        dest = os.path.join(tempfile.gettempdir(), info.asset_name)

        def job(progress, cancel):
            return updater.download(info, dest, progress=progress, cancel=cancel)

        status, payload = run_task(self, "Đang tải bản cập nhật...", job)
        if status == "error":
            show_error(self, payload)
            return
        if status != "ok":
            return  # nguoi dung huy

        if not getattr(sys, "frozen", False):
            # Dang chay tu ma nguon (dev) -> chi mo file cai, khong tu dong
            QMessageBox.information(
                self, "Đã tải xong",
                f"Đã tải bản cài đặt:\n{payload}\n\n"
                "(Đang chạy từ mã nguồn nên không tự cài — hãy chạy file trên.)")
            return

        ret = QMessageBox.question(
            self, "Cài đặt cập nhật",
            "Đã tải xong. Cài đặt ngay bây giờ?\n"
            "HP Cons PDF sẽ tự đóng để cập nhật, rồi mở lại.")
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._run_updater_and_quit(payload)

    def _run_updater_and_quit(self, installer_path: str):
        """Chay installer (dong app -> cai -> mo lai) qua 1 file .bat trung gian."""
        import subprocess
        import sys
        import tempfile

        from PyQt6.QtWidgets import QApplication

        app_exe = sys.executable  # HPConsPDF.exe khi da dong goi
        bat = os.path.join(tempfile.gettempdir(), "hpconspdf_update.bat")
        # /VERYSILENT: cai im lang; /FORCECLOSEAPPLICATIONS: dong app dang chay
        content = (
            "@echo off\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            f'"{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES '
            "/NORESTART /FORCECLOSEAPPLICATIONS\r\n"
            f'start "" "{app_exe}"\r\n'
            'del "%~f0"\r\n')
        try:
            with open(bat, "w", encoding="mbcs") as f:
                f.write(content)
            DETACHED = 0x00000008  # DETACHED_PROCESS
            subprocess.Popen(["cmd", "/c", bat], creationflags=DETACHED,
                             close_fds=True)
        except Exception as e:
            show_error(self, friendly_message(e))
            return
        # Dong toan bo cua so de installer ghi de file
        for w in list(MainWindow._instances):
            w.close()
        QApplication.instance().quit()

    def _update_ui_state(self):
        tab = self.current_tab()
        has_doc = tab is not None
        for a in self.doc_actions + self.tool_actions:
            a.setEnabled(has_doc)
        if hasattr(self, "btn_page_menu"):
            self.btn_page_menu.setEnabled(has_doc)
            self.btn_color.setEnabled(has_doc)
            self.act_toggle_sidebar.setEnabled(has_doc)
        if has_doc:
            model = tab.model
            self.act_undo.setEnabled(bool(model.undo_stack))
            n = model.page_count
            self.sp_page.blockSignals(True)
            self.sp_page.setRange(1, max(n, 1))
            self.sp_page.setValue(tab.view.current_page + 1)
            self.sp_page.blockSignals(False)
            self.lb_pagecount.setText(f" / {n}  ")
            mark = " (đã chỉnh sửa)" if model.modified else ""
            self.lb_status_file.setText(f"{model.path}  —  {n} trang{mark}")
            i = self.tabs.currentIndex()
            title = model.display_name + (" *" if model.modified else "")
            self.tabs.setTabText(i, title)
            self.cb_zoom.setEditText(f"{round(tab.view.zoom * 100)}%")
            self.btn_fit_w.setChecked(tab.view.fit_mode == "fit-width")
            self.btn_fit_p.setChecked(tab.view.fit_mode == "fit-page")
            self.setWindowTitle(f"{model.display_name} — {APP_NAME}")
        else:
            self.sp_page.setRange(1, 1)
            self.lb_pagecount.setText(" / 0  ")
            self.setWindowTitle(APP_NAME)
            self.lb_status_file.setText(
                "Chưa mở file nào — kéo-thả file PDF vào đây hoặc bấm \"Mở file\"")

    def _refresh_recent_menu(self):
        self.menu_recent.clear()
        rec = [p for p in config.get("recent_files", []) if os.path.exists(p)]
        if not rec:
            a = self.menu_recent.addAction("(Trống)")
            a.setEnabled(False)
            return
        for p in rec:
            a = self.menu_recent.addAction(os.path.basename(p))
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, path=p: self.open_path(path))

    # ================= Dieu huong / zoom / tim =================
    def _view_call(self, method: str):
        tab = self.current_tab()
        if tab:
            getattr(tab.view, method)()
            self._update_ui_state()

    def _goto_delta(self, d: int):
        tab = self.current_tab()
        if tab:
            tab.view.goto_page(tab.view.current_page + d)

    def _goto_spin(self):
        tab = self.current_tab()
        if tab:
            tab.view.goto_page(self.sp_page.value() - 1)

    def _zoom_from_combo(self):
        tab = self.current_tab()
        if not tab:
            return
        text = self.cb_zoom.currentText().replace("%", "").strip()
        try:
            z = float(text) / 100.0
        except ValueError:
            return
        self.btn_fit_w.setChecked(False)
        self.btn_fit_p.setChecked(False)
        tab.view.set_zoom(z, fit_mode=None)

    def _set_fit(self, mode: str):
        tab = self.current_tab()
        self.btn_fit_w.setChecked(mode == "fit-width")
        self.btn_fit_p.setChecked(mode == "fit-page")
        if tab:
            tab.view.set_fit_mode(mode)
            self._update_ui_state()

    def _search(self, backwards: bool):
        tab = self.current_tab()
        if not tab:
            return
        term = self.ed_search.text().strip()
        if not term:
            tab.clear_search()
            self.lb_search.setText("")
            return
        result = tab.search(term, backwards=backwards)
        if result is None:
            self.lb_search.setText("  Không tìm thấy")
        else:
            cur, total = result
            self.lb_search.setText(f"  Trang có kết quả: {cur}/{total}")

    # ================= Thao tac trang =================
    def _select_all_pages(self):
        """Ctrl+A: chon tat ca trang; dang o o nhap chu thi chon het chu."""
        from PyQt6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit)):
            fw.selectAll()
            return
        tab = self.current_tab()
        if tab:
            tab.thumbs.selectAll()
            self.statusBar().showMessage(
                f"Đã chọn tất cả {tab.model.page_count} trang — xoay/xóa/copy "
                "sẽ áp dụng cho cả loạt.", 5000)

    def _selected_or_current(self, tab: DocumentTab) -> list[int]:
        pages = tab.thumbs.selected_pages()
        return pages if pages else [tab.view.current_page]

    def rotate(self, angle: int):
        tab = self.current_tab()
        if tab:
            tab.rotate_pages(self._selected_or_current(tab), angle)

    def delete_pages(self):
        tab = self.current_tab()
        if not tab:
            return
        pages = self._selected_or_current(tab)
        names = ", ".join(str(p + 1) for p in pages[:12])
        if len(pages) > 12:
            names += "..."
        ret = QMessageBox.question(
            self, "Xóa trang",
            f"Xóa {len(pages)} trang ({names}) khỏi tài liệu đang mở?\n"
            "(File gốc trên đĩa không bị thay đổi — dùng \"Lưu thành...\" để "
            "xuất file mới.)")
        if ret == QMessageBox.StandardButton.Yes:
            try:
                tab.delete_pages(pages)
            except Exception as e:
                show_error(self, friendly_message(e))

    def extract_pages(self):
        tab = self.current_tab()
        if not tab:
            return
        self._extract_indices(self._selected_or_current(tab))

    def _extract_indices(self, pages: list[int]):
        tab = self.current_tab()
        if not tab or not pages:
            return
        model = tab.model
        dest = suffixed_output(model.path, "_extracted",
                               out_dir=default_out_dir(model.path))

        def job(progress, cancel):
            return model.save_as(dest, indices=pages, progress=progress,
                                 cancel=cancel)

        status, payload = run_task(self, "Đang trích xuất trang...", job)
        if status == "ok":
            show_done(self, f"Đã trích xuất {len(pages)} trang ra file:\n{payload}",
                      open_path=payload)
        elif status == "error":
            show_error(self, payload)

    def quick_save(self, tab=None) -> bool:
        """Luu Ctrl+S: ghi moi chinh sua THANG vao file dang mo.

        An toan OneDrive: ghi ra file tam CUNG thu muc roi thay the nguyen tu
        (os.replace) sau khi da dong handle pdfium. Xong thi nap lai tai lieu
        tu dia (chinh sua da nam trong file, bo dem hoan tac lam lai tu dau).
        """
        tab = tab if isinstance(tab, DocumentTab) else self.current_tab()
        if not tab:
            return False
        model = tab.model
        path = model.path
        tmp_dest = os.path.join(os.path.dirname(path),
                                "~" + os.path.basename(path) + ".dang-luu")

        def job(progress, cancel):
            return model.save_as(tmp_dest, progress=progress, cancel=cancel,
                                 overwrite=True)

        status, payload = run_task(self, "Đang lưu...", job)
        if status != "ok":
            if status == "error":
                show_error(self, payload)
            try:
                if os.path.exists(tmp_dest):
                    os.remove(tmp_dest)
            except OSError:
                pass
            return False

        from ..core.document import PDFIUM_LOCK
        try:
            model._invalidate_tp_cache()
            with PDFIUM_LOCK:
                model.main_source.close()
                for s in model.extra_sources:
                    s.close()
                os.replace(tmp_dest, path)
        except OSError:
            show_error(self,
                       "Không ghi được vào file gốc — file có thể đang mở "
                       "trong chương trình khác hoặc đang bị OneDrive khóa.\n"
                       f"Bản lưu tạm vẫn còn tại:\n{tmp_dest}\n"
                       "Sếp có thể dùng \"Lưu thành...\" để lưu ra chỗ khác.")
            return False
        self._reload_tab_from_disk(tab)
        self.statusBar().showMessage(f"Đã lưu: {path}", 6000)
        return True

    def _reload_tab_from_disk(self, tab: DocumentTab):
        """Nap lai tai lieu tu dia sau khi luu vao file goc."""
        old = tab.model
        path, pw = old.path, old.main_source.password
        cur = tab.view.current_page
        try:
            new_model = DocumentModel(path, pw)
        except Exception as e:
            show_error(self, friendly_message(e))
            return
        tab.model = new_model
        tab.view.set_model(new_model)
        tab.thumbs.set_model(new_model)
        old.close()
        tab.view.goto_page(cur)
        tab.invalidate_search_cache()
        self._update_ui_state()

    def save_as(self):
        tab = self.current_tab()
        if tab:
            self._do_save_as(tab)

    def _do_save_as(self, tab: DocumentTab) -> bool:
        model = tab.model
        suggested = suffixed_output(model.path, "_edited",
                                    out_dir=default_out_dir(model.path))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Lưu thành file mới", suggested, "File PDF (*.pdf)")
        if not dest:
            return False
        if os.path.abspath(dest) == os.path.abspath(model.path):
            show_error(self, "Không thể ghi đè file gốc.\n"
                             "Vui lòng chọn tên file khác — ứng dụng luôn "
                             "giữ nguyên file gốc để an toàn.")
            return False

        def job(progress, cancel):
            return model.save_as(dest, progress=progress, cancel=cancel)

        status, payload = run_task(self, "Đang lưu file...", job)
        if status == "ok":
            model.modified = False
            self._update_ui_state()
            show_done(self, f"Đã lưu:\n{payload}", open_path=payload)
            return True
        if status == "error":
            show_error(self, payload)
        return False

    # ================= Hop thoai cong cu =================
    def show_merge(self):
        MergeDialog(self).exec()

    def show_split(self):
        model = self.current_model()
        if model:
            SplitDialog(model.path, len(model.main_source.doc),
                        model.main_source.password, self).exec()

    def show_insert(self):
        tab = self.current_tab()
        if not tab:
            return
        dlg = InsertDialog(tab.model, tab.view.current_page, self)
        if dlg.exec():
            tab.refresh()
            tab.invalidate_search_cache()

    def show_number(self):
        model = self.current_model()
        if model:
            PageNumberDialog(model, self).exec()

    def show_watermark(self):
        tab = self.current_tab()
        if tab:
            WatermarkDialog(tab.model, tab.view.current_page, self).exec()

    def show_ocr(self):
        model = self.current_model()
        if model:
            OcrDialog(model, self).exec()

    def show_convert(self):
        ConvertDialog(self.current_model(), self).exec()

    def show_compress(self):
        model = self.current_model()
        if model:
            CompressDialog(model, self).exec()

    def show_security(self):
        model = self.current_model()
        if model:
            SecurityDialog(model, self).exec()

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục xuất mặc định", config.get("out_dir", ""))
        if d:
            config.set("out_dir", d)
            self.statusBar().showMessage(f"Thư mục xuất mặc định: {d}", 5000)

    def _show_about(self):
        QMessageBox.about(
            self, f"Giới thiệu {APP_NAME}",
            f"<b>{APP_NAME}</b> — phiên bản {APP_VERSION}<br><br>"
            "Công cụ xử lý PDF nội bộ cho team đấu thầu HP Cons.<br>"
            "Xem, ghép, tách, chỉnh sửa/ghi chú, đánh số trang, watermark, "
            "OCR, nén và bảo mật file PDF.<br><br>"
            "Mọi thao tác đều tạo file mới — file gốc luôn được giữ nguyên.")

    # ================= Keo tha & dong =================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
                u.toLocalFile().lower().endswith(".pdf")
                for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.toLocalFile().lower().endswith(".pdf")]
        if not files:
            event.ignore()
            return
        event.acceptProposedAction()
        # Tha len THANH TRANG THU NHO cua tab hien tai -> GOP; noi khac -> tab moi
        tab = self.current_tab()
        if tab is not None and tab.thumbs.isVisible():
            gpos = self.mapToGlobal(event.position().toPoint())
            tp = tab.thumbs.mapFromGlobal(gpos)
            if tab.thumbs.rect().contains(tp):
                it = tab.thumbs.itemAt(tp)
                row = tab.thumbs.row(it) if it is not None else -1
                self._merge_dropped_files(files, row)
                return
        for f in files:
            self.open_path(f)

    def closeEvent(self, event):
        dirty = [self.tabs.widget(i) for i in range(self.tabs.count())
                 if isinstance(self.tabs.widget(i), DocumentTab)
                 and self.tabs.widget(i).model.modified]
        if dirty:
            names = "\n".join("• " + t.model.display_name for t in dirty)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Chưa lưu chỉnh sửa")
            box.setText(f"Các tài liệu sau có chỉnh sửa chưa lưu:\n{names}")
            btn_save = box.addButton("Lưu và thoát",
                                     QMessageBox.ButtonRole.AcceptRole)
            btn_discard = box.addButton("Thoát không lưu",
                                        QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_save)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_cancel:
                event.ignore()
                return
            if clicked == btn_save:
                # Luu tung tai lieu con chinh sua; huy neu 1 file luu that bai
                for i in range(self.tabs.count()):
                    w = self.tabs.widget(i)
                    if isinstance(w, DocumentTab) and w.model.modified:
                        if not self.quick_save(w):
                            event.ignore()
                            return
        self.render_thread.stop()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentTab):
                w.close_document()
        if self in MainWindow._instances:
            MainWindow._instances.remove(self)
        event.accept()
