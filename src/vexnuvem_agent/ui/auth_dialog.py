from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from ..models import AuthConfig


def normalize_auth_username(value: str) -> str:
    return value.strip().casefold()


def load_logo_pixmap() -> QPixmap:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        logo_path = Path(sys._MEIPASS) / "logo.png"
    else:
        logo_path = Path(__file__).resolve().parents[3] / "logo.png"
    return QPixmap(str(logo_path))


def create_logo_label(logo_pixmap: QPixmap, max_width: int, max_height: int) -> QLabel:
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if logo_pixmap.isNull():
        label.setText("VexNuvem")
        label.setProperty("headline", True)
        label.setFont(QFont("Bahnschrift", 20, QFont.Weight.Bold))
        return label

    scaled = logo_pixmap.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    label.setPixmap(scaled)
    label.setMinimumHeight(scaled.height())
    return label


class AccessLoginDialog(QDialog):
    def __init__(
        self,
        auth_config: AuthConfig,
        parent=None,
        require_username: bool = True,
        title: str = "Acesso ao VexNuvem",
        description: str = "Informe usuario e senha para abrir o agente.",
    ) -> None:
        super().__init__(parent)
        self.auth_config = auth_config
        self.require_username = require_username
        self.logo_pixmap = load_logo_pixmap()

        self.setModal(True)
        self.setWindowTitle(title)
        self.resize(420, 420 if require_username else 360)
        if not self.logo_pixmap.isNull():
            self.setWindowIcon(QIcon(self.logo_pixmap))

        logo_label = create_logo_label(self.logo_pixmap, max_width=260, max_height=180)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Bahnschrift", 18, QFont.Weight.Bold))
        description_label = QLabel(description)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setProperty("subtle", True)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Usuario")
        self.username_edit.setText(auth_config.username)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Senha")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self._validate_credentials)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #d64545;")
        self.error_label.hide()

        form = QFormLayout()
        if require_username:
            form.addRow("Usuario", self.username_edit)
        else:
            self.username_edit.hide()
        form.addRow("Senha", self.password_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Entrar" if require_username else "Liberar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(self._validate_credentials)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(logo_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        layout.addWidget(buttons)

        if require_username:
            self.username_edit.selectAll()
            self.username_edit.setFocus()
        else:
            self.password_edit.setFocus()

    def _validate_credentials(self) -> None:
        username_ok = True
        if self.require_username:
            username_ok = normalize_auth_username(self.username_edit.text()) == normalize_auth_username(
                self.auth_config.username
            )

        if username_ok and self.password_edit.text() == self.auth_config.password:
            self.accept()
            return

        self.password_edit.clear()
        self.error_label.setText("Usuario ou senha incorretos.")
        self.error_label.show()
        if self.require_username:
            self.username_edit.setFocus()
            self.username_edit.selectAll()
        else:
            self.password_edit.setFocus()