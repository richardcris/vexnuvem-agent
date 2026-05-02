from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette


APP_STYLE = """
QWidget {
    color: #EAF7FF;
    font-family: "Bahnschrift";
    font-size: 10pt;
}

QMainWindow, QWidget#RootWidget {
    background-color: #07101B;
}

QDialog, QMessageBox {
    background-color: #07101B;
}

QMessageBox QLabel {
    color: #EAF7FF;
    background: transparent;
}

QMessageBox QTextEdit,
QMessageBox QPlainTextEdit {
    background-color: #081420;
    color: #EAF7FF;
    border: 1px solid rgba(90, 180, 255, 0.25);
    border-radius: 12px;
}

QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #091526,
        stop:0.55 #0C1D32,
        stop:1 #06111D);
    border-right: 1px solid rgba(67, 172, 255, 0.35);
}

QFrame#Card, QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0B1626,
        stop:1 #0F2237);
    border: 1px solid rgba(89, 191, 255, 0.28);
    border-radius: 18px;
}

QFrame#DeveloperBadge {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(10, 26, 42, 0.96),
        stop:1 rgba(12, 40, 63, 0.94));
    border: 1px solid rgba(116, 211, 255, 0.38);
    border-radius: 20px;
}

QGroupBox {
    margin-top: 14px;
    padding: 18px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 6px;
    color: #8AD5FF;
    font-size: 11pt;
}

QPushButton {
    background-color: #0E2438;
    border: 1px solid rgba(88, 191, 255, 0.25);
    border-radius: 14px;
    padding: 10px 16px;
}

QPushButton:hover {
    background-color: #14314D;
    border: 1px solid rgba(88, 191, 255, 0.6);
}

QPushButton:pressed {
    background-color: #0B1E30;
}

QPushButton[accent="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00A6FF,
        stop:1 #1C7DFF);
    color: #021522;
    font-weight: 700;
    border: none;
}

QPushButton[nav="true"] {
    text-align: left;
    padding: 14px 18px;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    font-size: 11pt;
}

QPushButton[nav="true"][active="true"] {
    background-color: rgba(20, 69, 108, 0.9);
    border: 1px solid rgba(92, 202, 255, 0.65);
}

QPushButton[sidebarLink="true"] {
    text-align: left;
    padding: 12px 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(14, 45, 70, 0.98),
        stop:1 rgba(18, 95, 148, 0.98));
    border: 1px solid rgba(108, 210, 255, 0.55);
    border-radius: 16px;
    font-size: 10.5pt;
    font-weight: 700;
}

QPushButton[sidebarLink="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(20, 63, 98, 1.0),
        stop:1 rgba(27, 124, 191, 1.0));
    border: 1px solid rgba(134, 226, 255, 0.75);
}

QPushButton[sidebarLink="true"]:pressed {
    background-color: #103452;
}

QLineEdit, QComboBox, QSpinBox, QTimeEdit, QListWidget, QTableWidget {
    background-color: #081420;
    border: 1px solid rgba(90, 180, 255, 0.25);
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #1296E0;
}

QHeaderView::section {
    background-color: #10263A;
    color: #9DDCFF;
    padding: 8px;
    border: none;
}

QProgressBar {
    background-color: #081420;
    border: 1px solid rgba(90, 180, 255, 0.25);
    border-radius: 10px;
    text-align: center;
}

QProgressBar::chunk {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00A6FF,
        stop:1 #55E0FF);
}

QScrollArea {
    border: none;
}

QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}

QCheckBox::indicator:unchecked {
    border-radius: 6px;
    border: 1px solid rgba(90, 180, 255, 0.4);
    background-color: #081420;
}

QCheckBox::indicator:checked {
    border-radius: 6px;
    border: 1px solid #22B8FF;
    background-color: #22B8FF;
}

QLabel[headline="true"] {
    font-size: 18pt;
    font-weight: 700;
}

QLabel[subtle="true"] {
    color: #89A7BE;
}

QLabel[developerKicker="true"] {
    color: #7DBFE6;
    font-size: 9pt;
    font-weight: 600;
}

QLabel[developerCompany="true"] {
    color: #F3FBFF;
    font-size: 17pt;
    font-weight: 700;
}

QLabel[developerName="true"] {
    color: #69D4FF;
    font-size: 11pt;
    font-weight: 700;
}

QFrame#DeveloperAccent {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #12B8FF,
        stop:1 #7BF0FF);
    border: none;
    border-radius: 2px;
}
"""


def apply_theme(app) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#07101B"))
    palette.setColor(QPalette.WindowText, QColor("#EAF7FF"))
    palette.setColor(QPalette.Base, QColor("#081420"))
    palette.setColor(QPalette.AlternateBase, QColor("#0B1626"))
    palette.setColor(QPalette.ToolTipBase, QColor("#EAF7FF"))
    palette.setColor(QPalette.ToolTipText, QColor("#07101B"))
    palette.setColor(QPalette.Text, QColor("#EAF7FF"))
    palette.setColor(QPalette.Button, QColor("#0E2438"))
    palette.setColor(QPalette.ButtonText, QColor("#EAF7FF"))
    palette.setColor(QPalette.Highlight, QColor("#22B8FF"))
    palette.setColor(QPalette.HighlightedText, QColor("#021522"))
    app.setPalette(palette)
    app.setFont(QFont("Bahnschrift", 10))
    app.setStyleSheet(APP_STYLE)
