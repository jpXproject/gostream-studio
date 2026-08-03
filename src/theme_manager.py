# src/theme_manager.py
# GoCapture Studio - Theme Manager
# Developed by jpXCode

THEMES = {
    "1. Dracula": {
        "bg": "#282a36",
        "widget": "#44475a",
        "widget_border": "#6272a4",
        "highlight": "#bd93f9",
        "highlight_hover": "#ff79c6",
        "text": "#f8f8f2",
        "text_secondary": "#6272a4",
        "preview_bg": "#1e1f29",
        "btn_record": "#ff5555",
        "btn_stop": "#ff5555",
        "btn_pause": "#f1fa8c",
        "border_radius": "8px",
    },
    "2. Monokai Pro": {
        "bg": "#2d2a2e",
        "widget": "#403e41",
        "widget_border": "#5a575b",
        "highlight": "#ffd866",
        "highlight_hover": "#78dce8",
        "text": "#fcfcfa",
        "text_secondary": "#939293",
        "preview_bg": "#1a181a",
        "btn_record": "#ff6188",
        "btn_stop": "#ff6188",
        "btn_pause": "#ffd866",
        "border_radius": "8px",
    },
    "3. Nord (Arctic)": {
        "bg": "#2e3440",
        "widget": "#3b4252",
        "widget_border": "#4c566a",
        "highlight": "#88c0d0",
        "highlight_hover": "#81a1c1",
        "text": "#e5e9f0",
        "text_secondary": "#7b88a1",
        "preview_bg": "#1b1f2b",
        "btn_record": "#bf616a",
        "btn_stop": "#bf616a",
        "btn_pause": "#ebcb8b",
        "border_radius": "8px",
    },
    "4. Midnight Espresso": {
        "bg": "#1e150f",
        "widget": "#33261d",
        "widget_border": "#4c382b",
        "highlight": "#e6b88a",
        "highlight_hover": "#d4a373",
        "text": "#f0e3d0",
        "text_secondary": "#8c6e52",
        "preview_bg": "#110c08",
        "btn_record": "#c95a4a",
        "btn_stop": "#c95a4a",
        "btn_pause": "#d4a373",
        "border_radius": "8px",
    },
    "5. Synthwave 84": {
        "bg": "#241b2f",
        "widget": "#36294c",
        "widget_border": "#523d75",
        "highlight": "#f92aad",
        "highlight_hover": "#36f9f6",
        "text": "#e0d4f0",
        "text_secondary": "#8b73b0",
        "preview_bg": "#140f1c",
        "btn_record": "#f92aad",
        "btn_stop": "#f92aad",
        "btn_pause": "#36f9f6",
        "border_radius": "8px",
    }
}


def get_theme_style(theme_name: str) -> str:
    """Generate QSS string dari theme dictionary (termasuk panel dock ala OBS)."""
    t = THEMES.get(theme_name, THEMES["1. Dracula"])

    qss = f"""
    QMainWindow, QDialog {{
        background-color: {t['bg']};
        color: {t['text']};
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        font-size: 13px;
    }}
    QWidget {{
        background-color: {t['bg']};
        color: {t['text']};
    }}
    QLabel#preview {{
        background-color: {t['preview_bg']};
        border: 2px solid {t['widget_border']};
        border-radius: 12px;
        color: {t['text_secondary']};
        font-size: 20px;
        font-weight: bold;
    }}
    QLabel#stat_badge {{
        color: {t['text']};
        font-family: "Consolas", "Courier New", monospace;
        font-size: 12px;
        font-weight: bold;
        background-color: {t['widget']};
        padding: 4px 10px;
        border-radius: 6px;
        border: 1px solid {t['widget_border']};
    }}
    QLabel#timer_badge {{
        color: {t['btn_record']};
        font-family: "Consolas", "Courier New", monospace;
        font-size: 18px;
        font-weight: bold;
        background-color: {t['widget']};
        padding: 2px 14px;
        border-radius: 6px;
        border: 1px solid {t['widget_border']};
    }}
    QStatusBar {{
        background-color: {t['widget']};
        color: {t['text']};
        border-top: 1px solid {t['widget_border']};
    }}
    QStatusBar::item {{ border: none; }}
    QDockWidget {{
        color: {t['highlight']};
        font-weight: bold;
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }}
    QDockWidget::title {{
        background-color: {t['widget']};
        border: 1px solid {t['widget_border']};
        border-radius: 6px;
        padding: 5px 10px;
        margin: 2px;
    }}
    QDockWidget > QWidget {{
        background-color: {t['bg']};
    }}
    QListWidget {{
        background-color: {t['preview_bg']};
        border: 1px solid {t['widget_border']};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 6px;
        margin: 2px 0;
        color: {t['text']};
    }}
    QListWidget::item:selected {{
        background-color: {t['highlight']};
        color: {t['bg']};
        font-weight: bold;
    }}
    QListWidget::item:hover {{
        background-color: {t['widget']};
    }}
    QTabWidget::pane {{
        background-color: {t['widget']};
        border: 1px solid {t['widget_border']};
        border-radius: 8px;
    }}
    QTabBar::tab {{
        background-color: {t['bg']};
        color: {t['text_secondary']};
        padding: 8px 14px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        border: 1px solid {t['widget_border']};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{
        background-color: {t['widget']};
        color: {t['highlight']};
        border-bottom: 2px solid {t['highlight']};
    }}
    QTabBar::tab:hover {{
        background-color: {t['widget']};
        color: {t['text']};
    }}
    QGroupBox {{
        background-color: {t['widget']};
        border: 1px solid {t['widget_border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {t['highlight']};
    }}
    QPushButton {{
        background-color: {t['widget']};
        color: {t['text']};
        border: 1px solid {t['widget_border']};
        border-radius: {t['border_radius']};
        padding: 8px 16px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {t['highlight']};
        color: {t['bg']};
        border: 1px solid {t['highlight']};
    }}
    QPushButton:pressed {{
        background-color: {t['highlight_hover']};
    }}
    QPushButton:disabled {{
        background-color: {t['bg']};
        color: {t['text_secondary']};
        border: 1px solid {t['bg']};
    }}
    QPushButton#btn_record {{
        background-color: {t['btn_record']};
        color: white;
        border: none;
        font-size: 15px;
    }}
    QPushButton#btn_record:hover {{ background-color: {t['btn_record']}; color: white; }}
    QPushButton#btn_stop {{
        background-color: {t['btn_stop']};
        color: white;
        border: none;
        font-size: 15px;
    }}
    QPushButton#btn_stop:hover {{ background-color: {t['btn_stop']}; color: white; }}
    QPushButton#btn_pause {{
        background-color: {t['btn_pause']};
        color: {t['bg']};
        border: none;
        font-size: 15px;
    }}
    QPushButton#btn_pause:hover {{ background-color: {t['btn_pause']}; color: {t['bg']}; }}
    QComboBox, QSpinBox, QLineEdit {{
        background-color: {t['bg']};
        color: {t['text']};
        border: 1px solid {t['widget_border']};
        border-radius: 6px;
        padding: 6px 10px;
        selection-background-color: {t['highlight']};
    }}
    QComboBox:hover, QSpinBox:hover {{
        border: 1px solid {t['highlight']};
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {t['bg']};
        color: {t['text']};
        border: 1px solid {t['widget_border']};
        selection-background-color: {t['highlight']};
        selection-color: {t['bg']};
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t['widget_border']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {t['highlight']};
        width: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{ background: {t['highlight_hover']}; }}
    QCheckBox {{ color: {t['text']}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 4px;
        border: 2px solid {t['widget_border']};
        background: {t['bg']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {t['highlight']};
        border: 2px solid {t['highlight']};
    }}
    QScrollBar:vertical {{
        background: {t['bg']}; width: 12px; border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['widget_border']}; border-radius: 6px; min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t['highlight']}; }}
    QPlainTextEdit#log_panel {{
        background-color: {t['preview_bg']};
        color: {t['text']};
        border: 1px solid {t['widget_border']};
        border-radius: 6px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 12px;
        selection-background-color: {t['highlight']};
    }}
    QMessageBox {{
        background-color: {t['bg']};
    }}
    """
    return qss
