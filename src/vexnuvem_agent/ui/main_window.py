from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback

from PySide6.QtCore import QThread, QTime, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..backup_service import BackupEngine, format_bytes
from ..config import ConfigManager, filters_to_text, text_to_filters
from ..models import AppConfig, AuthConfig, BackupSource, FtpServerConfig, ProtectionConfig, ScheduleConfig, UpdateConfig
from ..paths import INSTALLED_APP_EXE, TEMP_DIR
from ..protection_service import RansomwareProtectionService
from ..scheduler_service import SchedulerService
from ..startup_service import apply_start_with_windows, is_windows_startup_supported
from ..storage import BackupHistoryStore
from ..update_state import (
    PendingUpdateNotice,
    clear_pending_update_notice,
    load_pending_update_notice,
    save_pending_update_notice,
)
from ..update_service import GitHubUpdateService, UpdateInfo, UpdateCheckResult
from .auth_dialog import AccessLoginDialog, create_logo_label, load_logo_pixmap


WEEKDAY_LABELS = {
    "mon": "Seg",
    "tue": "Ter",
    "wed": "Qua",
    "thu": "Qui",
    "fri": "Sex",
    "sat": "Sab",
    "sun": "Dom",
}


class CardFrame(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")


class MetricCard(CardFrame):
    def __init__(self, title: str, value: str = "--", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setProperty("subtle", True)
        title_label.setFont(QFont("Bahnschrift", 10))

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Bahnschrift", 19, QFont.Weight.Bold))

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class StatusCard(CardFrame):
    def __init__(self, title: str, description: str = "", button_text: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setFont(QFont("Bahnschrift", 15, QFont.Weight.Bold))
        self.status_label = QLabel("--")
        self.status_label.setProperty("subtle", True)
        self.status_label.setWordWrap(True)
        self.description_label = QLabel(description)
        self.description_label.setProperty("subtle", True)
        self.description_label.setWordWrap(True)
        self.action_button = QPushButton(button_text) if button_text else None

        layout.addWidget(title_label)
        layout.addWidget(self.status_label)
        if description:
            layout.addWidget(self.description_label)
        layout.addStretch(1)
        if self.action_button is not None:
            layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)


class BackupWorker(QThread):
    progress_changed = Signal(int, str)
    backup_succeeded = Signal(dict)
    backup_failed = Signal(str)

    def __init__(self, backup_engine: BackupEngine, trigger: str) -> None:
        super().__init__()
        self.backup_engine = backup_engine
        self.trigger = trigger

    def run(self) -> None:
        try:
            result = self.backup_engine.run_backup(self.trigger, self._forward_progress)
            self.backup_succeeded.emit(result)
        except Exception as exc:
            self.backup_failed.emit(str(exc))

    def _forward_progress(self, percent: int, message: str) -> None:
        self.progress_changed.emit(percent, message)


class UpdateCheckWorker(QThread):
    update_checked = Signal(object, bool)
    update_failed = Signal(str, bool)

    def __init__(
        self,
        update_service: GitHubUpdateService,
        current_version: str,
        update_config: UpdateConfig,
        manual: bool,
    ) -> None:
        super().__init__()
        self.update_service = update_service
        self.current_version = current_version
        self.update_config = update_config
        self.manual = manual

    def run(self) -> None:
        try:
            result = self.update_service.check_for_updates(self.current_version, self.update_config)
            self.update_checked.emit(result, self.manual)
        except Exception as exc:
            self.update_failed.emit(str(exc), self.manual)


class UpdateInstallWorker(QThread):
    download_progress = Signal(int, int)
    install_ready = Signal(object, str, bool)
    install_failed = Signal(str, bool)

    def __init__(
        self,
        update_service: GitHubUpdateService,
        info: UpdateInfo,
        download_dir: Path,
        manual: bool,
    ) -> None:
        super().__init__()
        self.update_service = update_service
        self.info = info
        self.download_dir = download_dir
        self.manual = manual

    def run(self) -> None:
        try:
            installer_path = self.update_service.download_installer(
                self.info,
                self.download_dir,
                progress_callback=self._forward_progress,
            )
            self.install_ready.emit(self.info, str(installer_path), self.manual)
        except Exception as exc:
            self.install_failed.emit(str(exc), self.manual)

    def _forward_progress(self, received_bytes: int, total_bytes: int) -> None:
        self.download_progress.emit(received_bytes, total_bytes)


class UpdateProgressDialog(QDialog):
    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.version = version
        self.setWindowTitle("Atualizando o VexNuvem Agent")
        self.setModal(True)
        self.setMinimumWidth(460)

        title_label = QLabel(f"Atualizando para a versao {version}")
        title_label.setFont(QFont("Bahnschrift", 15, QFont.Weight.Bold))
        self.status_label = QLabel("Preparando download da nova versao...")
        self.status_label.setWordWrap(True)
        self.progress_label = QLabel("Aguarde enquanto o instalador e baixado.")
        self.progress_label.setWordWrap(True)
        self.progress_label.setProperty("subtle", True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

    def update_download(self, received_bytes: int, total_bytes: int) -> None:
        if total_bytes > 0:
            percent = max(0, min(int((received_bytes / total_bytes) * 100), 100))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.progress_label.setText(
                f"{format_bytes(received_bytes)} de {format_bytes(total_bytes)} baixados"
            )
            return

        self.progress_bar.setRange(0, 0)
        if received_bytes > 0:
            self.progress_label.setText(f"{format_bytes(received_bytes)} baixados")

    def show_installing(self) -> None:
        self.status_label.setText("Download concluido. Abrindo o instalador da nova versao...")
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(
            "O aplicativo sera fechado por alguns segundos para concluir a instalacao e a versao instalada sera aberta automaticamente."
        )


class WhatsNewDialog(QDialog):
    def __init__(self, notice: PendingUpdateNotice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.notice = notice
        self.setWindowTitle("Novidades desta versao")
        self.resize(720, 520)
        self.setModal(True)

        title_label = QLabel(f"VexNuvem Agent atualizado para {notice.version}")
        title_label.setFont(QFont("Bahnschrift", 16, QFont.Weight.Bold))

        subtitle_parts: list[str] = []
        if notice.previous_version:
            subtitle_parts.append(f"Versao anterior: {notice.previous_version}")
        if notice.published_at:
            subtitle_parts.append(f"Release publicada em: {notice.published_at}")
        subtitle_label = QLabel(" | ".join(subtitle_parts) or "Confira as melhorias desta versao abaixo.")
        subtitle_label.setWordWrap(True)
        subtitle_label.setProperty("subtle", True)

        notes_view = QTextBrowser()
        notes_view.setOpenExternalLinks(True)
        notes_view.setMarkdown(notice.notes or "## Novidades\n\nSem observacoes detalhadas nesta release.")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Entendi")
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(notes_view, 1)
        layout.addWidget(buttons)


class FtpServerDialog(QDialog):
    def __init__(self, server: FtpServerConfig | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Servidor FTP")
        self.setModal(True)
        self.resize(460, 320)

        self.name_edit = QLineEdit(server.name if server else "Servidor FTP")
        self.host_edit = QLineEdit(server.host if server else "")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(server.port if server else 21)
        self.username_edit = QLineEdit(server.username if server else "")
        self.password_edit = QLineEdit(server.password if server else "")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.remote_dir_edit = QLineEdit(server.remote_dir if server else "/")
        self.passive_checkbox = QCheckBox("Modo passivo")
        self.passive_checkbox.setChecked(server.passive_mode if server else True)
        self.enabled_checkbox = QCheckBox("Servidor habilitado")
        self.enabled_checkbox.setChecked(server.enabled if server else True)

        form = QFormLayout()
        form.addRow("Nome", self.name_edit)
        form.addRow("Host", self.host_edit)
        form.addRow("Porta", self.port_spin)
        form.addRow("Usuario", self.username_edit)
        form.addRow("Senha", self.password_edit)
        form.addRow("Diretorio remoto", self.remote_dir_edit)
        form.addRow("", self.passive_checkbox)
        form.addRow("", self.enabled_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def to_server(self) -> FtpServerConfig:
        return FtpServerConfig(
            name=self.name_edit.text().strip() or "Servidor FTP",
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            remote_dir=self.remote_dir_edit.text().strip() or "/",
            passive_mode=self.passive_checkbox.isChecked(),
            enabled=self.enabled_checkbox.isChecked(),
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_manager: ConfigManager,
        history_store: BackupHistoryStore,
        backup_engine: BackupEngine,
        scheduler_service: SchedulerService,
        update_service: GitHubUpdateService,
        protection_service: RansomwareProtectionService,
        app_version: str,
        default_update_repository: str,
        started_from_windows_startup: bool,
        authenticated_session: bool,
        logger,
    ) -> None:
        super().__init__()
        self.config_manager = config_manager
        self.history_store = history_store
        self.backup_engine = backup_engine
        self.scheduler_service = scheduler_service
        self.update_service = update_service
        self.protection_service = protection_service
        self.app_version = app_version
        self.default_update_repository = default_update_repository.strip()
        self.started_from_windows_startup = started_from_windows_startup
        self.session_authenticated = authenticated_session
        self.logger = logger

        self.config = self.config_manager.load()
        self.current_sources = [BackupSource.from_dict(item.to_dict()) for item in self.config.sources]
        self.current_ftp_servers = [FtpServerConfig.from_dict(item.to_dict()) for item in self.config.ftp_servers]
        self.nav_buttons: list[QPushButton] = []
        self.weekday_checkboxes: dict[str, QCheckBox] = {}
        self.backup_worker: BackupWorker | None = None
        self._last_trigger = "manual"
        self._force_close = False
        self.remote_status_snapshot: dict | None = None
        self.logo_pixmap = load_logo_pixmap()
        self.update_worker: UpdateCheckWorker | None = None
        self.update_install_worker: UpdateInstallWorker | None = None
        self.update_progress_dialog: UpdateProgressDialog | None = None
        self.update_prompted_version = ""
        self.pending_update_check_after_startup_backup = False

        self.setWindowTitle("VexNuvem Agent")
        if not self.logo_pixmap.isNull():
            self.setWindowIcon(QIcon(self.logo_pixmap))
        self.resize(1480, 920)

        self._build_ui()
        self._create_tray_icon()
        self._connect_signals()
        self._load_config_into_form()
        self._refresh_views()
        self.scheduler_service.apply_config(self.config)
        self.protection_service.apply_config(self.config)
        self._schedule_startup_actions()
        self._schedule_post_update_notice()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content()

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)
        self._switch_page(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 28, 20, 28)
        layout.setSpacing(18)

        sidebar_logo = self._create_logo_label(max_width=240, max_height=180)
        layout.addWidget(sidebar_logo)

        for index, title in enumerate(["Dashboard", "Configuracoes", "Historico", "Agendamento"]):
            button = QPushButton(title)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, current=index: self._switch_page(current))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        sidebar_card = CardFrame()
        sidebar_card_layout = QVBoxLayout(sidebar_card)
        sidebar_card_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_card_layout.setSpacing(8)
        info_title = QLabel("Instalacao")
        info_title.setProperty("subtle", True)
        self.sidebar_client_label = QLabel("--")
        self.sidebar_client_label.setFont(QFont("Bahnschrift", 12, QFont.Weight.Bold))
        self.sidebar_client_id_label = QLabel("--")
        self.sidebar_client_id_label.setProperty("subtle", True)
        self.sidebar_version_label = QLabel(f"Versao {self.app_version}")
        self.sidebar_version_label.setProperty("subtle", True)
        self.sidebar_status_label = QLabel("Pronto")
        self.sidebar_protection_label = QLabel(self.protection_service.status_message)
        self.sidebar_protection_label.setProperty("subtle", True)
        self.sidebar_protection_label.setWordWrap(True)
        self.sidebar_update_label = QLabel(self._default_update_status_message())
        self.sidebar_update_label.setProperty("subtle", True)
        self.sidebar_update_label.setWordWrap(True)
        sidebar_card_layout.addWidget(info_title)
        sidebar_card_layout.addWidget(self.sidebar_client_label)
        sidebar_card_layout.addWidget(self.sidebar_client_id_label)
        sidebar_card_layout.addWidget(self.sidebar_version_label)
        sidebar_card_layout.addSpacing(10)
        sidebar_card_layout.addWidget(self.sidebar_status_label)
        sidebar_card_layout.addWidget(self.sidebar_protection_label)
        sidebar_card_layout.addWidget(self.sidebar_update_label)
        layout.addWidget(sidebar_card)

        layout.addStretch(1)
        return sidebar

    def _build_content(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        top_bar = QHBoxLayout()
        self.header_logo_label = self._create_logo_label(max_width=370, max_height=140)
        top_bar.addWidget(self.header_logo_label)
        self.page_subtitle_label = QLabel("")
        self.page_subtitle_label.hide()
        top_bar.addStretch(1)

        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self._refresh_views)
        self.save_button = QPushButton("Salvar Configuracoes")
        self.save_button.setProperty("accent", True)
        self.save_button.clicked.connect(self.save_configuration)
        top_bar.addWidget(self.refresh_button)
        top_bar.addWidget(self.save_button)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_dashboard_page())
        self.stack.addWidget(self._build_settings_page())
        self.stack.addWidget(self._build_history_page())
        self.stack.addWidget(self._build_schedule_page())

        layout.addLayout(top_bar)
        layout.addWidget(self.stack, 1)
        return wrapper

    def _create_logo_label(self, max_width: int, max_height: int) -> QLabel:
        return create_logo_label(self.logo_pixmap, max_width=max_width, max_height=max_height)

    @staticmethod
    def _load_logo_pixmap() -> QPixmap:
        return load_logo_pixmap()

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        hero = CardFrame()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(10)
        hero_title = QLabel("Backup inteligente com failover e telemetria")
        hero_title.setFont(QFont("Bahnschrift", 18, QFont.Weight.Bold))
        self.dashboard_client_name = QLabel("Cliente")
        self.dashboard_client_name.setFont(QFont("Bahnschrift", 15, QFont.Weight.DemiBold))
        self.dashboard_client_id = QLabel("Client ID")
        self.dashboard_client_id.setProperty("subtle", True)
        self.last_backup_status_label = QLabel("Nunca executado")
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(self.dashboard_client_name)
        hero_layout.addWidget(self.dashboard_client_id)
        hero_layout.addWidget(self.last_backup_status_label)
        layout.addWidget(hero)

        status_cards_layout = QGridLayout()
        status_cards_layout.setHorizontalSpacing(16)
        status_cards_layout.setVerticalSpacing(16)

        self.dashboard_update_card = StatusCard(
            "Atualizacoes",
            description="Consulta releases do GitHub e mostra quando ha uma nova versao pronta para instalar.",
            button_text="Verificar agora",
        )
        self.dashboard_update_card.action_button.clicked.connect(self._check_for_updates_manually)
        self.dashboard_update_card.set_status(self._default_update_status_message())

        self.dashboard_protection_card = StatusCard(
            "Protecao anti-ransomware",
            description="Monitora sinais de criptografia maliciosa nas pastas protegidas e pode acionar o Defender.",
            button_text="Verificacao rapida do Defender",
        )
        self.dashboard_protection_card.action_button.clicked.connect(self._trigger_manual_protection_scan)
        self.dashboard_protection_card.set_status(self.protection_service.status_message)

        status_cards_layout.addWidget(self.dashboard_update_card, 0, 0)
        status_cards_layout.addWidget(self.dashboard_protection_card, 0, 1)
        layout.addLayout(status_cards_layout)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(16)
        stats_grid.setVerticalSpacing(16)
        self.metric_total = MetricCard("Backups executados")
        self.metric_success = MetricCard("Execucoes com sucesso")
        self.metric_volume = MetricCard("Volume enviado")
        self.metric_next_run = MetricCard("Proxima execucao")
        stats_grid.addWidget(self.metric_total, 0, 0)
        stats_grid.addWidget(self.metric_success, 0, 1)
        stats_grid.addWidget(self.metric_volume, 0, 2)
        stats_grid.addWidget(self.metric_next_run, 0, 3)
        layout.addLayout(stats_grid)

        action_card = CardFrame()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(22, 22, 22, 22)
        action_layout.setSpacing(12)
        action_title = QLabel("Execucao manual")
        action_title.setFont(QFont("Bahnschrift", 16, QFont.Weight.Bold))
        self.backup_status_live_label = QLabel("Pronto para iniciar um novo backup.")
        self.backup_status_live_label.setProperty("subtle", True)
        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.setRange(0, 100)
        self.backup_progress_bar.setValue(0)
        self.backup_now_button = QPushButton("Fazer Backup Agora")
        self.backup_now_button.setProperty("accent", True)
        self.backup_now_button.clicked.connect(lambda: self.start_backup("manual"))
        action_layout.addWidget(action_title)
        action_layout.addWidget(self.backup_status_live_label)
        action_layout.addWidget(self.backup_progress_bar)
        action_layout.addWidget(self.backup_now_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(action_card)

        remote_card = CardFrame()
        remote_layout = QVBoxLayout(remote_card)
        remote_layout.setContentsMargins(18, 18, 18, 18)
        remote_layout.setSpacing(10)
        remote_header = QHBoxLayout()
        remote_title = QLabel("Status remoto da API")
        remote_title.setFont(QFont("Bahnschrift", 15, QFont.Weight.Bold))
        self.refresh_remote_status_button = QPushButton("Consultar Status")
        self.refresh_remote_status_button.clicked.connect(self._refresh_remote_status)
        remote_header.addWidget(remote_title)
        remote_header.addStretch(1)
        remote_header.addWidget(self.refresh_remote_status_button)
        self.remote_status_label = QLabel("API desativada.")
        self.remote_status_label.setProperty("subtle", True)
        self.remote_company_label = QLabel("Empresa: --")
        self.remote_company_label.setProperty("subtle", True)
        self.remote_backup_label = QLabel("Ultimo backup remoto: --")
        self.remote_backup_label.setProperty("subtle", True)
        self.remote_totals_label = QLabel("Backups remotos: -- | Falhas remotas: --")
        self.remote_totals_label.setProperty("subtle", True)
        remote_layout.addLayout(remote_header)
        remote_layout.addWidget(self.remote_status_label)
        remote_layout.addWidget(self.remote_company_label)
        remote_layout.addWidget(self.remote_backup_label)
        remote_layout.addWidget(self.remote_totals_label)
        layout.addWidget(remote_card)

        recent_card = CardFrame()
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(18, 18, 18, 18)
        recent_layout.setSpacing(12)
        recent_title = QLabel("Historico recente")
        recent_title.setFont(QFont("Bahnschrift", 15, QFont.Weight.Bold))
        self.recent_history_table = QTableWidget(0, 4)
        self.recent_history_table.setHorizontalHeaderLabels(["Data", "Status", "Tamanho", "Servidor"])
        self.recent_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_history_table.verticalHeader().setVisible(False)
        self.recent_history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_history_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(self.recent_history_table)
        layout.addWidget(recent_card, 1)

        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        client_group = QGroupBox("Cliente")
        client_layout = QFormLayout(client_group)
        self.client_name_edit = QLineEdit()
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("agent_xxxxxxxx")
        client_id_row = QWidget()
        client_id_layout = QHBoxLayout(client_id_row)
        client_id_layout.setContentsMargins(0, 0, 0, 0)
        client_id_layout.setSpacing(10)
        copy_client_id_button = QPushButton("Copiar Agent ID")
        copy_client_id_button.clicked.connect(self._copy_client_id)
        client_id_layout.addWidget(self.client_id_edit, 1)
        client_id_layout.addWidget(copy_client_id_button)
        self.background_checkbox = QCheckBox("Permitir execucao em segundo plano pela bandeja")
        self.start_with_windows_checkbox = QCheckBox("Iniciar com o Windows")
        self.start_with_windows_checkbox.setEnabled(is_windows_startup_supported())
        self.access_username_edit = QLineEdit()
        self.access_password_edit = QLineEdit()
        self.access_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.access_password_edit.setPlaceholderText("Deixe em branco para manter a senha atual")
        client_hint = QLabel(
            "Use aqui o Agent ID gerado no painel Base44 para esse cliente. Esse valor e enviado em todos os backups."
        )
        client_hint.setProperty("subtle", True)
        client_hint.setWordWrap(True)
        startup_hint = QLabel(
            "Quando iniciado pelo Windows, o agente verifica se existe um backup automatico vencido e executa a rotina em segundo plano."
        )
        startup_hint.setProperty("subtle", True)
        startup_hint.setWordWrap(True)
        access_hint = QLabel(
            "Primeiro acesso padrao: usuario admin e senha admin. Altere aqui para proteger o painel."
        )
        access_hint.setProperty("subtle", True)
        access_hint.setWordWrap(True)
        client_layout.addRow("Nome do cliente", self.client_name_edit)
        client_layout.addRow("Agent ID", client_id_row)
        client_layout.addRow("", client_hint)
        client_layout.addRow("", self.background_checkbox)
        client_layout.addRow("", self.start_with_windows_checkbox)
        client_layout.addRow("", startup_hint)
        client_layout.addRow("Usuario de acesso", self.access_username_edit)
        client_layout.addRow("Nova senha de acesso", self.access_password_edit)
        client_layout.addRow("", access_hint)

        sources_group = QGroupBox("Fontes e filtros")
        sources_layout = QVBoxLayout(sources_group)
        self.sources_list = QListWidget()
        self.sources_list.setMinimumHeight(138)
        self.sources_empty_label = QLabel("Nenhuma pasta ou arquivo selecionado ainda.")
        self.sources_empty_label.setProperty("subtle", True)
        sources_buttons = QHBoxLayout()
        add_folder_button = QPushButton("Adicionar Pasta")
        add_folder_button.clicked.connect(self._add_folder_source)
        add_file_button = QPushButton("Adicionar Arquivo")
        add_file_button.clicked.connect(self._add_file_sources)
        remove_source_button = QPushButton("Remover Selecionado")
        remove_source_button.clicked.connect(self._remove_selected_source)
        sources_buttons.addWidget(add_folder_button)
        sources_buttons.addWidget(add_file_button)
        sources_buttons.addWidget(remove_source_button)
        self.filters_edit = QLineEdit()
        self.filters_edit.setPlaceholderText("Ex.: .fdb, .sql, .zip")
        filters_hint = QLabel(
            "Somente arquivos com essas extensoes entram no ZIP final. Deixe vazio para incluir todo o conteudo da pasta."
        )
        filters_hint.setProperty("subtle", True)
        filters_hint.setWordWrap(True)
        sources_layout.addWidget(self.sources_list)
        sources_layout.addWidget(self.sources_empty_label)
        sources_layout.addLayout(sources_buttons)
        sources_layout.addWidget(QLabel("Filtros de extensao"))
        sources_layout.addWidget(self.filters_edit)
        sources_layout.addWidget(filters_hint)

        ftp_group = QGroupBox("Servidores FTP")
        ftp_layout = QVBoxLayout(ftp_group)
        self.ftp_summary_label = QLabel("Nenhum servidor configurado.")
        self.ftp_summary_label.setProperty("subtle", True)
        self.ftp_table = QTableWidget(0, 5)
        self.ftp_table.setMinimumHeight(220)
        self.ftp_table.setHorizontalHeaderLabels(["Nome", "Host", "Porta", "Diretorio", "Ativo"])
        self.ftp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ftp_table.verticalHeader().setVisible(False)
        self.ftp_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ftp_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ftp_buttons = QHBoxLayout()
        add_ftp_button = QPushButton("Novo Servidor")
        add_ftp_button.clicked.connect(self._add_ftp_server)
        edit_ftp_button = QPushButton("Editar")
        edit_ftp_button.clicked.connect(self._edit_selected_ftp_server)
        remove_ftp_button = QPushButton("Remover")
        remove_ftp_button.clicked.connect(self._remove_selected_ftp_server)
        ftp_buttons.addWidget(add_ftp_button)
        ftp_buttons.addWidget(edit_ftp_button)
        ftp_buttons.addWidget(remove_ftp_button)
        ftp_layout.addWidget(self.ftp_summary_label)
        ftp_layout.addWidget(self.ftp_table)
        ftp_layout.addLayout(ftp_buttons)

        api_group = QGroupBox("Monitoramento remoto")
        api_layout = QFormLayout(api_group)
        self.api_enabled_checkbox = QCheckBox("Enviar status para API Base44")
        self.api_endpoint_edit = QLineEdit()
        self.api_endpoint_edit.setPlaceholderText("https://SUA_URL/api ou https://SEU_APP.base44.app/functions")
        self.api_token_edit = QLineEdit()
        self.api_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_token_edit.setPlaceholderText("Opcional quando a API exigir autenticacao Bearer")
        api_hint = QLabel(
            "A Base44 geralmente identifica o cliente pelo Agent ID configurado acima. Se a sua API exigir autenticacao, informe um token Bearer neste campo."
        )
        api_hint.setWordWrap(True)
        api_hint.setProperty("subtle", True)
        api_actions_row = QWidget()
        api_actions_layout = QHBoxLayout(api_actions_row)
        api_actions_layout.setContentsMargins(0, 0, 0, 0)
        api_actions_layout.setSpacing(10)
        self.test_api_button = QPushButton("Testar API")
        self.test_api_button.clicked.connect(self._test_api_connection)
        self.open_dashboard_status_button = QPushButton("Ver Status no Dashboard")
        self.open_dashboard_status_button.clicked.connect(lambda: self._switch_page(0))
        api_actions_layout.addWidget(self.test_api_button)
        api_actions_layout.addWidget(self.open_dashboard_status_button)
        api_actions_layout.addStretch(1)
        self.settings_api_status_label = QLabel("Aguardando teste da API.")
        self.settings_api_status_label.setProperty("subtle", True)
        self.settings_api_status_label.setWordWrap(True)
        api_layout.addRow("", self.api_enabled_checkbox)
        api_layout.addRow("Endpoint base", self.api_endpoint_edit)
        api_layout.addRow("Token API", self.api_token_edit)
        api_layout.addRow("", api_hint)
        api_layout.addRow("", api_actions_row)
        api_layout.addRow("Status atual", self.settings_api_status_label)

        updates_group = QGroupBox("Atualizacoes automaticas")
        updates_layout = QFormLayout(updates_group)
        self.update_enabled_checkbox = QCheckBox("Verificar novas versoes ao abrir o programa")
        self.update_repository_edit = QLineEdit()
        self.update_repository_edit.setPlaceholderText(self.default_update_repository or "usuario/repositorio")
        self.update_token_edit = QLineEdit()
        self.update_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.update_token_edit.setPlaceholderText("Opcional para repositorio privado")
        version_label = QLabel(f"Versao atual do app: {self.app_version}")
        version_label.setProperty("subtle", True)
        update_hint = QLabel(
            "Informe o repositorio GitHub que publica as releases do instalador. Se o repositorio for privado, informe tambem um token GitHub com permissao Contents: Read."
        )
        update_hint.setWordWrap(True)
        update_hint.setProperty("subtle", True)
        update_actions_row = QWidget()
        update_actions_layout = QHBoxLayout(update_actions_row)
        update_actions_layout.setContentsMargins(0, 0, 0, 0)
        update_actions_layout.setSpacing(10)
        self.check_updates_button = QPushButton("Verificar Atualizacoes")
        self.check_updates_button.clicked.connect(self._check_for_updates_manually)
        update_actions_layout.addWidget(self.check_updates_button)
        update_actions_layout.addStretch(1)
        self.settings_update_status_label = QLabel(self._default_update_status_message())
        self.settings_update_status_label.setProperty("subtle", True)
        self.settings_update_status_label.setWordWrap(True)
        updates_layout.addRow("Versao instalada", version_label)
        updates_layout.addRow("Repositorio GitHub", self.update_repository_edit)
        updates_layout.addRow("Token GitHub", self.update_token_edit)
        updates_layout.addRow("", self.update_enabled_checkbox)
        updates_layout.addRow("", update_hint)
        updates_layout.addRow("", update_actions_row)
        updates_layout.addRow("Status", self.settings_update_status_label)

        protection_group = QGroupBox("Protecao anti-ransomware")
        protection_layout = QFormLayout(protection_group)
        self.protection_enabled_checkbox = QCheckBox("Ativar monitor em tempo real nas pastas configuradas")
        self.protection_auto_scan_checkbox = QCheckBox("Acionar verificacao rapida do Microsoft Defender ao detectar risco")
        self.protection_threshold_spin = QSpinBox()
        self.protection_threshold_spin.setRange(2, 50)
        self.protection_threshold_spin.setSuffix(" eventos")
        self.protection_status_label = QLabel(self.protection_service.status_message)
        self.protection_status_label.setProperty("subtle", True)
        self.protection_status_label.setWordWrap(True)
        protection_hint = QLabel(
            "O alerta dispara imediatamente se surgir um arquivo com cara de pedido de resgate e tambem reage a rajadas de extensoes tipicas de criptografia."
        )
        protection_hint.setProperty("subtle", True)
        protection_hint.setWordWrap(True)
        protection_actions_row = QWidget()
        protection_actions_layout = QHBoxLayout(protection_actions_row)
        protection_actions_layout.setContentsMargins(0, 0, 0, 0)
        protection_actions_layout.setSpacing(10)
        self.protection_scan_button = QPushButton("Rodar verificacao do Defender agora")
        self.protection_scan_button.clicked.connect(self._trigger_manual_protection_scan)
        protection_actions_layout.addWidget(self.protection_scan_button)
        protection_actions_layout.addStretch(1)
        protection_layout.addRow("", self.protection_enabled_checkbox)
        protection_layout.addRow("", self.protection_auto_scan_checkbox)
        protection_layout.addRow("Limite de eventos", self.protection_threshold_spin)
        protection_layout.addRow("", protection_hint)
        protection_layout.addRow("", protection_actions_row)
        protection_layout.addRow("Status atual", self.protection_status_label)

        settings_save_button = QPushButton("Salvar Painel de Configuracoes")
        settings_save_button.setProperty("accent", True)
        settings_save_button.clicked.connect(self.save_configuration)

        layout.addWidget(client_group)
        layout.addWidget(sources_group)
        layout.addWidget(ftp_group)
        layout.addWidget(api_group)
        layout.addWidget(updates_group)
        layout.addWidget(protection_group)
        layout.addWidget(settings_save_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        scroll.setWidget(container)
        page_layout.addWidget(scroll)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(16)
        self.history_total_metric = MetricCard("Total")
        self.history_error_metric = MetricCard("Falhas")
        self.history_last_metric = MetricCard("Ultima finalizacao")
        cards_layout.addWidget(self.history_total_metric, 0, 0)
        cards_layout.addWidget(self.history_error_metric, 0, 1)
        cards_layout.addWidget(self.history_last_metric, 0, 2)
        layout.addLayout(cards_layout)

        table_card = CardFrame()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(12)
        title_row = QHBoxLayout()
        title = QLabel("Historico detalhado")
        title.setFont(QFont("Bahnschrift", 15, QFont.Weight.Bold))
        refresh_history_button = QPushButton("Atualizar Historico")
        refresh_history_button.clicked.connect(self._refresh_views)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(refresh_history_button)
        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels(["Inicio", "Fim", "Status", "Trigger", "Tamanho", "Servidor", "Erro"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table_layout.addLayout(title_row)
        table_layout.addWidget(self.history_table)
        layout.addWidget(table_card, 1)
        return page

    def _build_schedule_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        schedule_group = QGroupBox("Agendamento")
        schedule_layout = QFormLayout(schedule_group)
        self.schedule_enabled_checkbox = QCheckBox("Ativar backup automatico")
        self.schedule_mode_combo = QComboBox()
        self.schedule_mode_combo.addItem("Horario diario", "daily")
        self.schedule_mode_combo.addItem("Intervalo em horas", "interval")
        self.schedule_mode_combo.addItem("Dias especificos da semana", "weekdays")
        self.schedule_time_edit = QTimeEdit()
        self.schedule_time_edit.setDisplayFormat("HH:mm")
        self.schedule_interval_spin = QSpinBox()
        self.schedule_interval_spin.setRange(1, 168)
        self.schedule_interval_spin.setSuffix(" h")

        weekdays_container = QWidget()
        weekdays_layout = QHBoxLayout(weekdays_container)
        weekdays_layout.setContentsMargins(0, 0, 0, 0)
        weekdays_layout.setSpacing(10)
        for key, label in WEEKDAY_LABELS.items():
            checkbox = QCheckBox(label)
            self.weekday_checkboxes[key] = checkbox
            weekdays_layout.addWidget(checkbox)
        weekdays_layout.addStretch(1)

        self.time_row = QWidget()
        time_layout = QHBoxLayout(self.time_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.addWidget(self.schedule_time_edit)
        time_layout.addStretch(1)

        self.interval_row = QWidget()
        interval_layout = QHBoxLayout(self.interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.addWidget(self.schedule_interval_spin)
        interval_layout.addStretch(1)

        self.weekdays_row = weekdays_container

        schedule_layout.addRow("", self.schedule_enabled_checkbox)
        schedule_layout.addRow("Modo", self.schedule_mode_combo)
        schedule_layout.addRow("Horario", self.time_row)
        schedule_layout.addRow("Intervalo", self.interval_row)
        schedule_layout.addRow("Dias da semana", self.weekdays_row)

        execution_group = QGroupBox("Estrategia de backup")
        execution_layout = QFormLayout(execution_group)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 10)
        self.compression_spin = QSpinBox()
        self.compression_spin.setRange(1, 9)
        self.schedule_next_run_label = QLabel("Sem proxima execucao")
        execution_layout.addRow("Retentativas autom. FTP", self.retry_spin)
        execution_layout.addRow("Nivel de compressao", self.compression_spin)
        execution_layout.addRow("Proxima execucao", self.schedule_next_run_label)

        save_schedule_button = QPushButton("Salvar Agendamento")
        save_schedule_button.setProperty("accent", True)
        save_schedule_button.clicked.connect(self.save_configuration)

        layout.addWidget(schedule_group)
        layout.addWidget(execution_group)
        layout.addWidget(save_schedule_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _connect_signals(self) -> None:
        self.scheduler_service.backup_requested.connect(self.start_backup)
        self.scheduler_service.next_run_changed.connect(self._update_next_run_labels)
        self.protection_service.status_changed.connect(self._handle_protection_status_changed)
        self.protection_service.threat_detected.connect(self._handle_protection_threat_detected)
        self.schedule_enabled_checkbox.toggled.connect(self._update_schedule_visibility)
        self.schedule_mode_combo.currentIndexChanged.connect(self._update_schedule_visibility)

    def _create_tray_icon(self) -> None:
        tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon)
        self.tray_icon = QSystemTrayIcon(tray_icon, self)
        tray_menu = QMenu(self)

        open_action = QAction("Abrir painel", self)
        open_action.triggered.connect(self._restore_from_tray)
        exit_action = QAction("Encerrar agente", self)
        exit_action.triggered.connect(self._quit_from_tray)

        tray_menu.addAction(open_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _switch_page(self, index: int) -> None:
        if index == 1 and self.stack.currentIndex() != 1:
            if not self._authorize_settings_access():
                return
        self.stack.setCurrentIndex(index)
        subtitles = {
            0: "Painel central de backup, upload e monitoramento.",
            1: "Gerencie cliente, fontes, filtros, FTP e API.",
            2: "Consulte o historico completo de execucoes e falhas.",
            3: "Defina horario, intervalo ou recorrencia semanal.",
        }
        self.page_subtitle_label.setText(subtitles.get(index, ""))
        for button_index, button in enumerate(self.nav_buttons):
            is_active = button_index == index
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _load_config_into_form(self) -> None:
        self.config = self.config_manager.load()
        self.current_sources = [BackupSource.from_dict(item.to_dict()) for item in self.config.sources]
        self.current_ftp_servers = [FtpServerConfig.from_dict(item.to_dict()) for item in self.config.ftp_servers]

        self.client_name_edit.setText(self.config.client_name)
        self.client_id_edit.setText(self.config.client_id)
        self.background_checkbox.setChecked(self.config.run_in_background)
        self.start_with_windows_checkbox.setChecked(self.config.start_with_windows)
        self.access_username_edit.setText(self.config.auth.username)
        self.access_password_edit.clear()
        self.protection_enabled_checkbox.setChecked(self.config.protection.enabled)
        self.protection_auto_scan_checkbox.setChecked(self.config.protection.auto_defender_scan)
        self.protection_threshold_spin.setValue(max(2, self.config.protection.suspicious_event_threshold))
        self.filters_edit.setText(filters_to_text(self.config.filters))
        self.api_enabled_checkbox.setChecked(self.config.api.enabled)
        self.api_endpoint_edit.setText(self.config.api.endpoint)
        self.api_token_edit.setText(self.config.api.token)
        self.update_enabled_checkbox.setChecked(self.config.update.enabled)
        self.update_repository_edit.setText(self.config.update.repository or self.default_update_repository)
        self.update_token_edit.setText(self.config.update.token)

        self.schedule_enabled_checkbox.setChecked(self.config.schedule.enabled)
        self.schedule_mode_combo.setCurrentIndex(max(0, self.schedule_mode_combo.findData(self.config.schedule.mode)))
        parsed_time = QTime.fromString(self.config.schedule.time_of_day, "HH:mm")
        self.schedule_time_edit.setTime(parsed_time if parsed_time.isValid() else QTime(22, 0))
        self.schedule_interval_spin.setValue(max(1, self.config.schedule.interval_hours))
        for key, checkbox in self.weekday_checkboxes.items():
            checkbox.setChecked(key in self.config.schedule.weekdays)

        self.retry_spin.setValue(max(1, self.config.max_retries))
        self.compression_spin.setValue(max(1, min(self.config.compression_level, 9)))

        self._refresh_sources_list()
        self._refresh_ftp_table()
        self._update_schedule_visibility()

    def _refresh_views(self) -> None:
        self.config = self.config_manager.load()
        summary = self.history_store.get_summary()
        records = self.history_store.list_records(200)

        self.sidebar_client_label.setText(self.config.client_name)
        self.sidebar_client_id_label.setText(f"Agent ID {self.config.client_id}")
        self.sidebar_version_label.setText(f"Versao {self.app_version}")
        self.sidebar_status_label.setText(self.config.last_backup_status)
        self._handle_protection_status_changed(self.protection_service.status_message)

        self.dashboard_client_name.setText(self.config.client_name)
        self.dashboard_client_id.setText(f"Agent ID: {self.config.client_id}")
        self.last_backup_status_label.setText(
            f"Ultimo resultado: {self.config.last_backup_status} | Ultima execucao: {self._format_datetime(self.config.last_backup_at)}"
        )

        if not self.sidebar_update_label.text().strip():
            self._set_update_status(self._default_update_status_message())

        self.metric_total.set_value(str(summary["total_backups"]))
        self.metric_success.set_value(str(summary["success_count"]))
        self.metric_volume.set_value(format_bytes(summary["total_bytes"]))
        self.metric_next_run.set_value(self.scheduler_service.describe_next_run())

        self.history_total_metric.set_value(str(summary["total_backups"]))
        self.history_error_metric.set_value(str(summary["error_count"]))
        self.history_last_metric.set_value(self._format_datetime(summary["last_finished_at"]))

        self._populate_recent_history_table(records[:8])
        self._populate_history_table(records)
        self._update_next_run_labels(self.scheduler_service.describe_next_run())
        self._refresh_remote_status()

    def save_configuration(self) -> None:
        config = self._build_config_from_form()
        try:
            self.config_manager.save(config)
            self._sync_windows_startup_setting(config)
            self.config = config
            self.scheduler_service.apply_config(config)
            self.protection_service.apply_config(config)
            self._load_config_into_form()
            self._refresh_views()
            QMessageBox.information(self, "VexNuvem", "Configuracoes salvas com sucesso.")
        except Exception as exc:
            QMessageBox.critical(self, "VexNuvem", f"Falha ao salvar configuracoes: {exc}")

    def start_backup(self, trigger: str = "manual") -> None:
        if self.backup_worker and self.backup_worker.isRunning():
            if trigger == "manual":
                QMessageBox.warning(self, "VexNuvem", "Ja existe um backup em andamento.")
            return

        self._last_trigger = trigger
        self.backup_progress_bar.setValue(0)
        self.backup_status_live_label.setText("Preparando backup...")
        self.backup_now_button.setEnabled(False)

        self.backup_worker = BackupWorker(self.backup_engine, trigger)
        self.backup_worker.progress_changed.connect(self._handle_backup_progress)
        self.backup_worker.backup_succeeded.connect(self._handle_backup_success)
        self.backup_worker.backup_failed.connect(self._handle_backup_failure)
        self.backup_worker.finished.connect(self._handle_backup_finished)
        self.backup_worker.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._force_close and self.config.run_in_background and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "VexNuvem",
                "O agente continua em execucao em segundo plano.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return
        super().closeEvent(event)

    def _build_config_from_form(self) -> AppConfig:
        config = AppConfig.from_dict(self.config.to_dict())
        config.client_name = self.client_name_edit.text().strip() or "Cliente sem nome"
        config.client_id = self.client_id_edit.text().strip() or config.client_id
        config.sources = [BackupSource.from_dict(item.to_dict()) for item in self.current_sources]
        config.filters = text_to_filters(self.filters_edit.text())
        config.ftp_servers = [FtpServerConfig.from_dict(item.to_dict()) for item in self.current_ftp_servers]
        config.api.enabled = self.api_enabled_checkbox.isChecked()
        config.api.endpoint = self.api_endpoint_edit.text().strip()
        config.api.token = self.api_token_edit.text().strip()
        config.update = UpdateConfig(
            enabled=self.update_enabled_checkbox.isChecked(),
            repository=self.update_repository_edit.text().strip(),
            token=self.update_token_edit.text().strip(),
        )
        config.auth = AuthConfig(
            username=self.access_username_edit.text().strip() or config.auth.username or "admin",
            password=self.access_password_edit.text() or config.auth.password or "admin",
        )
        config.protection = ProtectionConfig(
            enabled=self.protection_enabled_checkbox.isChecked(),
            auto_defender_scan=self.protection_auto_scan_checkbox.isChecked(),
            suspicious_event_threshold=self.protection_threshold_spin.value(),
            suspicious_extensions=list(config.protection.suspicious_extensions),
            ransom_note_names=list(config.protection.ransom_note_names),
        )
        config.schedule = ScheduleConfig(
            enabled=self.schedule_enabled_checkbox.isChecked(),
            mode=self.schedule_mode_combo.currentData(),
            time_of_day=self.schedule_time_edit.time().toString("HH:mm"),
            interval_hours=self.schedule_interval_spin.value(),
            weekdays=[key for key, checkbox in self.weekday_checkboxes.items() if checkbox.isChecked()],
        )
        config.max_retries = self.retry_spin.value()
        config.compression_level = self.compression_spin.value()
        config.run_in_background = self.background_checkbox.isChecked()
        config.start_with_windows = self.start_with_windows_checkbox.isChecked()
        return config

    def _refresh_sources_list(self) -> None:
        self.sources_list.clear()
        for source in self.current_sources:
            label = f"[{source.source_type.upper()}] {source.path}"
            self.sources_list.addItem(label)
        self.sources_empty_label.setVisible(not self.current_sources)

    def _refresh_ftp_table(self) -> None:
        self.ftp_table.setRowCount(len(self.current_ftp_servers))
        for row, server in enumerate(self.current_ftp_servers):
            values = [server.name, server.host, str(server.port), server.remote_dir, "Sim" if server.enabled else "Nao"]
            for column, value in enumerate(values):
                self.ftp_table.setItem(row, column, QTableWidgetItem(value))
        active_servers = sum(1 for server in self.current_ftp_servers if server.enabled)
        total_servers = len(self.current_ftp_servers)
        if total_servers:
            self.ftp_summary_label.setText(
                f"{active_servers} servidor(es) ativo(s) de {total_servers} cadastrado(s). Ordem define prioridade de failover."
            )
        else:
            self.ftp_summary_label.setText("Nenhum servidor configurado.")

    def _populate_recent_history_table(self, records: list[dict]) -> None:
        self.recent_history_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                self._format_datetime(record.get("finished_at") or record.get("started_at")),
                record.get("status", ""),
                format_bytes(int(record.get("size_bytes", 0) or 0)),
                record.get("ftp_server", "-"),
            ]
            for column, value in enumerate(values):
                self.recent_history_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _populate_history_table(self, records: list[dict]) -> None:
        self.history_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                self._format_datetime(record.get("started_at")),
                self._format_datetime(record.get("finished_at")),
                record.get("status", ""),
                record.get("trigger_type", ""),
                format_bytes(int(record.get("size_bytes", 0) or 0)),
                record.get("ftp_server", "-"),
                record.get("error_message", ""),
            ]
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _add_folder_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if folder:
            self.current_sources.append(BackupSource(path=folder, source_type="folder"))
            self._refresh_sources_list()

    def _add_file_sources(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar arquivos")
        for file_path in files:
            self.current_sources.append(BackupSource(path=file_path, source_type="file"))
        if files:
            self._refresh_sources_list()

    def _remove_selected_source(self) -> None:
        row = self.sources_list.currentRow()
        if row < 0:
            return
        self.current_sources.pop(row)
        self._refresh_sources_list()

    def _add_ftp_server(self) -> None:
        dialog = FtpServerDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_ftp_servers.append(dialog.to_server())
            self._refresh_ftp_table()

    def _edit_selected_ftp_server(self) -> None:
        row = self.ftp_table.currentRow()
        if row < 0:
            return
        dialog = FtpServerDialog(server=self.current_ftp_servers[row], parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_ftp_servers[row] = dialog.to_server()
            self._refresh_ftp_table()

    def _remove_selected_ftp_server(self) -> None:
        row = self.ftp_table.currentRow()
        if row < 0:
            return
        self.current_ftp_servers.pop(row)
        self._refresh_ftp_table()

    def _update_schedule_visibility(self) -> None:
        enabled = self.schedule_enabled_checkbox.isChecked()
        mode = self.schedule_mode_combo.currentData()

        self.schedule_mode_combo.setEnabled(enabled)
        self.schedule_time_edit.setEnabled(enabled and mode in {"daily", "weekdays"})
        self.schedule_interval_spin.setEnabled(enabled and mode == "interval")
        for checkbox in self.weekday_checkboxes.values():
            checkbox.setEnabled(enabled and mode == "weekdays")

        self.time_row.setVisible(mode in {"daily", "weekdays"})
        self.interval_row.setVisible(mode == "interval")
        self.weekdays_row.setVisible(mode == "weekdays")

    def _handle_backup_progress(self, percent: int, message: str) -> None:
        self.backup_progress_bar.setValue(percent)
        self.backup_status_live_label.setText(message)
        self.sidebar_status_label.setText(message)

    def _handle_backup_success(self, result: dict) -> None:
        self._load_config_into_form()
        self._refresh_views()
        self.backup_progress_bar.setValue(100)
        self.backup_status_live_label.setText("Backup concluido com sucesso.")
        if self._last_trigger == "manual":
            QMessageBox.information(
                self,
                "VexNuvem",
                f"Backup concluido e enviado para {result.get('ftp_server', '-')}.",
            )
        elif self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "VexNuvem",
                "Backup automatico concluido com sucesso.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def _handle_backup_failure(self, error_message: str) -> None:
        self._load_config_into_form()
        self._refresh_views()
        self.backup_status_live_label.setText(error_message)
        self.sidebar_status_label.setText(error_message)
        if self._last_trigger == "manual":
            QMessageBox.critical(self, "VexNuvem", f"Falha no backup: {error_message}")
        elif self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "VexNuvem",
                f"Falha no backup automatico: {error_message}",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )

    def _handle_backup_finished(self) -> None:
        self.backup_now_button.setEnabled(True)
        if self.pending_update_check_after_startup_backup:
            self.pending_update_check_after_startup_backup = False
            QTimer.singleShot(1200, self.check_for_updates_on_startup)

    def _update_next_run_labels(self, next_run: str) -> None:
        self.metric_next_run.set_value(next_run)
        self.schedule_next_run_label.setText(next_run)

    def _copy_client_id(self) -> None:
        QApplication.clipboard().setText(self.client_id_edit.text())
        QMessageBox.information(self, "VexNuvem", "Agent ID copiado para a area de transferencia.")

    def _test_api_connection(self) -> None:
        try:
            config = self._build_config_from_form()
        except Exception as exc:
            self.settings_api_status_label.setText(f"Falha ao montar configuracao: {exc}")
            return

        if not config.api.enabled or not config.api.endpoint:
            message = "Ative a API e informe um endpoint antes de testar."
            self.settings_api_status_label.setText(message)
            QMessageBox.warning(self, "VexNuvem", message)
            return

        self.settings_api_status_label.setText("Testando conexao com a API...")
        QApplication.processEvents()
        success, payload = self.backup_engine.api_client.fetch_client_status(config.api, config.client_id)
        if success and isinstance(payload, dict):
            client = payload.get("client", {})
            message = f"API online. Cliente remoto: {client.get('name', '--')} | Status: {client.get('status', '--')}"
            self.settings_api_status_label.setText(message)
            QMessageBox.information(self, "VexNuvem", message)
            self._refresh_remote_status(config_override=config)
            return

        message = f"Falha na API: {payload}"
        self.settings_api_status_label.setText(message)
        QMessageBox.warning(self, "VexNuvem", message)

    def _refresh_remote_status(self, config_override: AppConfig | None = None) -> None:
        active_config = config_override or self.config
        api_config = active_config.api
        if not api_config.enabled or not api_config.endpoint:
            self.remote_status_snapshot = None
            disabled_message = "API desativada ou sem endpoint configurado."
            self.remote_status_label.setText(disabled_message)
            self.remote_company_label.setText("Empresa: --")
            self.remote_backup_label.setText("Ultimo backup remoto: --")
            self.remote_totals_label.setText("Backups remotos: -- | Falhas remotas: --")
            if hasattr(self, "settings_api_status_label"):
                self.settings_api_status_label.setText(disabled_message)
            return

        self.remote_status_label.setText("Consultando status remoto...")
        if hasattr(self, "settings_api_status_label"):
            self.settings_api_status_label.setText("Consultando status remoto...")
        QApplication.processEvents()
        success, payload = self.backup_engine.api_client.fetch_client_status(api_config, active_config.client_id)
        if not success:
            self.remote_status_snapshot = None
            failure_message = f"Falha na API: {payload}"
            self.remote_status_label.setText(failure_message)
            self.remote_company_label.setText("Empresa: --")
            self.remote_backup_label.setText("Ultimo backup remoto: --")
            self.remote_totals_label.setText("Backups remotos: -- | Falhas remotas: --")
            if hasattr(self, "settings_api_status_label"):
                self.settings_api_status_label.setText(failure_message)
            return

        self.remote_status_snapshot = payload if isinstance(payload, dict) else None
        client = payload.get("client", {}) if isinstance(payload, dict) else {}
        remote_status = client.get("status", "--")
        remote_name = client.get("name", active_config.client_name)
        remote_company = client.get("company", "--")
        success_message = f"Cliente remoto: {remote_name} | Status: {remote_status}"
        self.remote_status_label.setText(success_message)
        self.remote_company_label.setText(f"Empresa: {remote_company}")
        self.remote_backup_label.setText(
            f"Ultimo backup remoto: {self._format_datetime(client.get('last_backup'))}"
        )
        self.remote_totals_label.setText(
            f"Backups remotos: {client.get('total_backups', '--')} | Falhas remotas: {client.get('total_failures', '--')}"
        )
        if hasattr(self, "settings_api_status_label"):
            self.settings_api_status_label.setText(success_message)

    def check_for_updates_on_startup(self) -> None:
        self._start_update_check(manual=False)

    def _check_for_updates_manually(self) -> None:
        self._start_update_check(manual=True)

    def _start_update_check(self, manual: bool) -> None:
        if self.update_worker and self.update_worker.isRunning():
            if manual:
                QMessageBox.information(self, "VexNuvem", "A verificacao de atualizacao ja esta em andamento.")
            return

        source_config = self._build_config_from_form() if manual else self.config_manager.load()
        update_config = UpdateConfig.from_dict(source_config.update.to_dict())
        update_config.repository = self._resolve_update_repository(source_config)

        if manual and not update_config.repository:
            message = "Informe o repositorio GitHub das releases para verificar atualizacoes."
            self._set_update_status(message)
            QMessageBox.warning(self, "VexNuvem", message)
            return

        self._set_update_status("Verificando se existe uma nova versao disponivel...")
        self.update_worker = UpdateCheckWorker(
            update_service=self.update_service,
            current_version=self.app_version,
            update_config=update_config,
            manual=manual,
        )
        self.update_worker.update_checked.connect(self._handle_update_check_success)
        self.update_worker.update_failed.connect(self._handle_update_check_failure)
        self.update_worker.finished.connect(self._handle_update_check_finished)
        self.update_worker.start()

    def _handle_update_check_success(self, result: UpdateCheckResult, manual: bool) -> None:
        self._set_update_status(result.message)

        if result.status == "update_available" and result.info:
            if manual or result.info.latest_version != self.update_prompted_version:
                self.update_prompted_version = result.info.latest_version
                self._begin_update_installation(result.info, manual)
            return

        if manual:
            if result.status == "up_to_date":
                QMessageBox.information(self, "VexNuvem", result.message)
            elif result.status == "unconfigured":
                QMessageBox.warning(self, "VexNuvem", result.message)
            elif result.status == "disabled":
                QMessageBox.information(self, "VexNuvem", result.message)

    def _handle_update_check_failure(self, message: str, manual: bool) -> None:
        failure_message = f"Falha ao verificar atualizacoes: {message}"
        self.logger.warning(failure_message)
        self._set_update_status(failure_message)
        if manual:
            QMessageBox.warning(self, "VexNuvem", failure_message)

    def _handle_update_check_finished(self) -> None:
        self.update_worker = None

    def _begin_update_installation(self, info: UpdateInfo, manual: bool) -> None:
        if not self._can_self_update():
            message = (
                "Nova versao encontrada, mas a atualizacao automatica so funciona no app instalado pelo setup. "
                "Use o instalador publicado na release para atualizar esta instancia."
            )
            self._set_update_status(message)
            if manual:
                QMessageBox.information(self, "VexNuvem", message)
            return

        if self.update_install_worker and self.update_install_worker.isRunning():
            if manual:
                QMessageBox.information(self, "VexNuvem", "A atualizacao automatica ja esta sendo preparada.")
            return

        self._set_update_status(f"Baixando a versao {info.latest_version} para atualizar automaticamente...")
        download_dir = TEMP_DIR / "updates"
        self._ensure_update_progress_dialog(info)
        self.update_install_worker = UpdateInstallWorker(
            update_service=self.update_service,
            info=info,
            download_dir=download_dir,
            manual=manual,
        )
        self.update_install_worker.download_progress.connect(self._handle_update_install_progress)
        self.update_install_worker.install_ready.connect(self._handle_update_install_ready)
        self.update_install_worker.install_failed.connect(self._handle_update_install_failure)
        self.update_install_worker.finished.connect(self._handle_update_install_finished)
        self.update_install_worker.start()

    def _handle_update_install_progress(self, received_bytes: int, total_bytes: int) -> None:
        if self.update_progress_dialog is None:
            return
        self.update_progress_dialog.update_download(received_bytes, total_bytes)

    def _handle_update_install_ready(self, info: UpdateInfo, installer_path: str, manual: bool) -> None:
        try:
            launcher_path = self.update_service.create_windows_upgrade_launcher(
                installer_path=Path(installer_path),
                launcher_dir=TEMP_DIR / "updates",
                current_pid=os.getpid(),
                restart_executable=self._resolve_restart_executable(),
            )
            save_pending_update_notice(
                PendingUpdateNotice(
                    version=info.latest_version,
                    previous_version=info.current_version,
                    notes=info.notes,
                    published_at=info.published_at,
                    release_url=info.release_url,
                )
            )
            if self.update_progress_dialog is not None:
                self.update_progress_dialog.show_installing()
            self.update_service.launch_upgrade_launcher(launcher_path)
        except Exception as exc:
            clear_pending_update_notice()
            self._handle_update_install_failure(str(exc), manual)
            return

        message = (
            f"Nova versao {info.latest_version} encontrada. O app sera fechado para remover a versao atual e instalar a nova automaticamente."
        )
        self._set_update_status(message)
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "VexNuvem",
                "Atualizacao automatica iniciada. A versao instalada sera aberta automaticamente ao final.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        self._force_close = True
        self.tray_icon.hide()
        QTimer.singleShot(400, QApplication.quit)

    def _handle_update_install_failure(self, message: str, manual: bool) -> None:
        failure_message = f"Falha ao preparar a atualizacao automatica: {message}"
        self.logger.warning(failure_message)
        self._close_update_progress_dialog()
        self._set_update_status(failure_message)
        if manual:
            QMessageBox.warning(self, "VexNuvem", failure_message)

    def _handle_update_install_finished(self) -> None:
        self.update_install_worker = None
        if not self._force_close:
            self._close_update_progress_dialog()

    def _set_update_status(self, message: str) -> None:
        if hasattr(self, "sidebar_update_label"):
            self.sidebar_update_label.setText(self._compact_status_message(message, 58))
        if hasattr(self, "dashboard_update_card"):
            self.dashboard_update_card.set_status(message)
        if hasattr(self, "settings_update_status_label"):
            self.settings_update_status_label.setText(message)

    def _resolve_update_repository(self, config: AppConfig) -> str:
        return (config.update.repository or self.default_update_repository).strip()

    def _schedule_startup_actions(self) -> None:
        should_run_backup = self.started_from_windows_startup and self.scheduler_service.should_run_startup_backup(self.config)
        if should_run_backup:
            self.pending_update_check_after_startup_backup = True
            self._set_update_status("Inicializado com o Windows. Verificando backup automatico pendente...")
            QTimer.singleShot(1200, self._run_startup_backup_if_due)
            return
        QTimer.singleShot(1800, self.check_for_updates_on_startup)

    def _run_startup_backup_if_due(self) -> None:
        self.config = self.config_manager.load()
        if not self.scheduler_service.should_run_startup_backup(self.config):
            self.pending_update_check_after_startup_backup = False
            QTimer.singleShot(1200, self.check_for_updates_on_startup)
            return
        self.logger.info("Disparando backup automatico pendente ao iniciar com o Windows")
        self.start_backup("automatic-startup")

    def _schedule_post_update_notice(self) -> None:
        QTimer.singleShot(900, self._show_pending_update_notice)

    def _show_pending_update_notice(self) -> None:
        pending_notice = load_pending_update_notice()
        if pending_notice is None:
            return

        comparison = self.update_service._compare_versions(self.app_version, pending_notice.version)
        if comparison < 0:
            return
        if comparison > 0:
            clear_pending_update_notice()
            return
        if not self.isVisible() and self.started_from_windows_startup and self.config.run_in_background:
            return

        clear_pending_update_notice()
        WhatsNewDialog(pending_notice, self).exec()

    def _ensure_update_progress_dialog(self, info: UpdateInfo) -> None:
        if self.update_progress_dialog is None:
            self.update_progress_dialog = UpdateProgressDialog(info.latest_version, self)
        self.update_progress_dialog.show()
        self.update_progress_dialog.raise_()
        self.update_progress_dialog.activateWindow()

    def _close_update_progress_dialog(self) -> None:
        if self.update_progress_dialog is None:
            return
        self.update_progress_dialog.close()
        self.update_progress_dialog.deleteLater()
        self.update_progress_dialog = None

    @staticmethod
    def _resolve_restart_executable() -> str:
        if not getattr(sys, "frozen", False):
            return ""
        executable = Path(sys.executable)
        if executable.suffix.lower() != ".exe":
            return ""
        return str(INSTALLED_APP_EXE)

    @staticmethod
    def _sync_windows_startup_setting(config: AppConfig) -> None:
        apply_start_with_windows(config.start_with_windows)

    @staticmethod
    def _can_self_update() -> bool:
        if not getattr(sys, "frozen", False):
            return False
        executable = Path(sys.executable)
        return executable.exists() and executable.suffix.lower() == ".exe"

    def _default_update_status_message(self) -> str:
        if self.default_update_repository:
            return f"Atualizacoes automaticas prontas para consultar {self.default_update_repository}."
        return "Configure o repositorio GitHub para ativar as atualizacoes automaticas."

    def _restore_from_tray(self) -> None:
        if not self._ensure_session_authenticated():
            return
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _quit_from_tray(self) -> None:
        self._force_close = True
        QApplication.quit()

    def _trigger_manual_protection_scan(self) -> None:
        success, message = self.protection_service.trigger_manual_defender_scan()
        self._handle_protection_status_changed(message)
        if success:
            QMessageBox.information(self, "VexNuvem", message)
            return
        QMessageBox.warning(self, "VexNuvem", message)

    def _handle_protection_status_changed(self, message: str) -> None:
        if hasattr(self, "sidebar_protection_label"):
            self.sidebar_protection_label.setText(self._compact_status_message(message, 58))
        if hasattr(self, "dashboard_protection_card"):
            self.dashboard_protection_card.set_status(message)
        if hasattr(self, "protection_status_label"):
            self.protection_status_label.setText(message)

    def _handle_protection_threat_detected(self, payload: dict) -> None:
        message = str(payload.get("message", "Atividade suspeita detectada."))
        self._handle_protection_status_changed(message)
        if self.tray_icon.isVisible() and not self.isVisible():
            self.tray_icon.showMessage(
                "VexNuvem",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                4500,
            )
            return
        QMessageBox.warning(self, "VexNuvem", message)

    def _ensure_session_authenticated(self) -> bool:
        if self.session_authenticated:
            return True

        self.config = self.config_manager.load()
        dialog = AccessLoginDialog(
            auth_config=self.config.auth,
            parent=self,
            require_username=True,
            title="Entrar no VexNuvem Agent",
            description="Informe usuario e senha para abrir o painel do agente.",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        self.session_authenticated = True
        return True

    def _authorize_settings_access(self) -> bool:
        if not self._ensure_session_authenticated():
            return False

        auth_config = self.config_manager.load().auth
        dialog = AccessLoginDialog(
            auth_config=auth_config,
            parent=self,
            require_username=False,
            title="Senha das Configuracoes",
            description="Informe a senha para acessar e alterar as configuracoes do agente.",
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def _format_datetime(raw_value: str | None) -> str:
        if not raw_value:
            return "--"
        try:
            return raw_value.replace("T", " ")
        except Exception:
            return str(raw_value)

    @staticmethod
    def _compact_status_message(message: str, max_length: int) -> str:
        clean = " ".join(str(message or "").split())
        if len(clean) <= max_length:
            return clean
        return f"{clean[: max_length - 3].rstrip()}..."
