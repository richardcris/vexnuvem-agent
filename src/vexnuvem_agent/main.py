from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import __github_repository__, __version__
from .api_client import MonitoringApiClient
from .backup_service import BackupEngine
from .config import ConfigManager
from .ftp_service import FTPFailoverUploader
from .logging_utils import configure_logging
from .protection_service import RansomwareProtectionService
from .scheduler_service import SchedulerService
from .startup_service import STARTUP_ARGUMENT, was_started_from_windows
from .storage import BackupHistoryStore
from .ui.auth_dialog import AccessLoginDialog
from .ui.main_window import MainWindow
from .ui.theme import apply_theme
from .update_service import GitHubUpdateService


def main() -> int:
    raw_args = list(sys.argv)
    started_from_windows_startup = was_started_from_windows(raw_args[1:])
    qt_args = [raw_args[0], *[arg for arg in raw_args[1:] if arg != STARTUP_ARGUMENT]]

    logger = configure_logging()
    app = QApplication(qt_args)
    app.setApplicationDisplayName("VexNuvem Agent")
    app.setApplicationVersion(__version__)
    apply_theme(app)

    config_manager = ConfigManager()
    config = config_manager.load()
    history_store = BackupHistoryStore()
    ftp_uploader = FTPFailoverUploader(logger)
    api_client = MonitoringApiClient(logger)
    update_service = GitHubUpdateService(logger)
    protection_service = RansomwareProtectionService(logger)
    scheduler = SchedulerService(logger)
    backup_engine = BackupEngine(
        config_manager=config_manager,
        history_store=history_store,
        ftp_uploader=ftp_uploader,
        api_client=api_client,
        logger=logger,
    )

    authenticated_session = False
    if not (started_from_windows_startup and config.run_in_background):
        login_dialog = AccessLoginDialog(
            auth_config=config.auth,
            require_username=True,
            title="Entrar no VexNuvem Agent",
            description="Informe usuario e senha para abrir o agente.",
        )
        if login_dialog.exec() != login_dialog.DialogCode.Accepted:
            scheduler.shutdown()
            return 0
        authenticated_session = True

    window = MainWindow(
        config_manager=config_manager,
        history_store=history_store,
        backup_engine=backup_engine,
        scheduler_service=scheduler,
        update_service=update_service,
        protection_service=protection_service,
        app_version=__version__,
        default_update_repository=__github_repository__,
        started_from_windows_startup=started_from_windows_startup,
        authenticated_session=authenticated_session,
        logger=logger,
    )
    if started_from_windows_startup and window.config.run_in_background:
        window.hide()
    else:
        window.show()

    exit_code = app.exec()
    protection_service.shutdown()
    scheduler.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
