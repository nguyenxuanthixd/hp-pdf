"""Bang mau thuong hieu HP Cons + stylesheet phang."""

GRAY = "#4A4F54"      # xam dam logo
GREEN = "#5FBF2D"     # xanh la logo
BLUE = "#1B75BB"      # xanh duong logo
WHITE = "#FFFFFF"
BG = "#F5F6F7"
BORDER = "#DDE0E3"

STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {WHITE};
    color: {GRAY};
}}
QWidget {{
    font-family: "Segoe UI";
    font-size: 10pt;
    color: {GRAY};
}}
QToolBar {{
    background: {WHITE};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px 6px;
    spacing: 2px;
}}
QToolBar#viewBar {{
    padding: 2px 6px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    color: {GRAY};
}}
QToolBar QToolButton {{
    font-size: 8.5pt;
    padding: 2px 6px;
}}
QStatusBar QToolButton {{
    padding: 1px 4px;
}}
QStatusBar QSpinBox, QStatusBar QComboBox {{
    padding: 2px 6px;
}}
QToolButton:hover {{
    background: #EEF7E8;
    border-color: {GREEN};
}}
QToolButton:pressed {{
    background: #DFF0D3;
}}
QToolButton:disabled {{
    color: #B0B4B8;
}}
QToolButton:checked {{
    background: #E3EFF8;
    border-color: {BLUE};
}}
QMenuBar {{
    background: {WHITE};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: #EEF7E8;
    border-radius: 4px;
}}
QMenu {{
    background: {WHITE};
    border: 1px solid {BORDER};
}}
QMenu::item {{
    padding: 6px 28px 6px 16px;
}}
QMenu::item:selected {{
    background: #E3EFF8;
}}
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
}}
QTabBar::tab {{
    background: {BG};
    color: {GRAY};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {WHITE};
    border-top: 2px solid {GREEN};
}}
QTabBar::close-button {{
    subcontrol-position: right;
}}
QStatusBar {{
    background: {BG};
    border-top: 1px solid {BORDER};
    color: {GRAY};
}}
QListWidget {{
    background: {BG};
    border: none;
    border-right: 1px solid {BORDER};
}}
QListWidget::item {{
    color: {GRAY};
    padding: 4px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background: #CFE5F5;
    border: 1px solid {BLUE};
}}
QScrollArea {{
    border: none;
    background: #ECEDEF;
}}
QPushButton {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 18px;
    color: {GRAY};
}}
QPushButton:hover {{
    border-color: {BLUE};
    background: #F2F8FC;
}}
QPushButton:disabled {{
    color: #B0B4B8;
    background: {BG};
}}
QPushButton#primary {{
    background: {GREEN};
    border-color: {GREEN};
    color: white;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: #52A826;
}}
QPushButton#primary:disabled {{
    background: #B7DDA1;
    border-color: #B7DDA1;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: {BLUE};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {BLUE};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QProgressBar {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    height: 20px;
    color: {GRAY};
}}
QProgressBar::chunk {{
    background: {GREEN};
    border-radius: 5px;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {BLUE};
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {GREEN};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
}}
QSplitter::handle {{
    background: {BORDER};
    width: 2px;
}}
QToolTip {{
    background: {GRAY};
    color: white;
    border: none;
    padding: 5px 8px;
}}
"""
