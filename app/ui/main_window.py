from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import notifier, settings
from app.ui.drop_area import SUPPORTED_EXTENSIONS, DropArea
from app.workers.transcription_worker import TranscriptionWorker

_LANGUAGES = [("Japanese (ja)", "ja"), ("English (en)", "en")]
_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
_DEFAULT_MODEL = "medium"
_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "app_icon.svg"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audio Transcript Tool")
        if _APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(_APP_ICON_PATH)))
        self._worker: TranscriptionWorker | None = None
        self._processing = False
        self._settings = settings.load()
        self._setup_ui()
        self._apply_settings_to_ui()
        self._connect_settings_persistence()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        self._drop_area = DropArea()
        self._drop_area.setMinimumHeight(150)
        self._drop_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._drop_area.files_dropped.connect(self._on_files_dropped)
        root.addWidget(self._drop_area)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("言語:"))
        self._lang_combo = QComboBox()
        for label, code in _LANGUAGES:
            self._lang_combo.addItem(label, code)
        settings_row.addWidget(self._lang_combo)
        settings_row.addSpacing(20)
        settings_row.addWidget(QLabel("モデル:"))
        self._model_combo = QComboBox()
        for m in _MODELS:
            self._model_combo.addItem(m)
        self._model_combo.setCurrentText(_DEFAULT_MODEL)
        settings_row.addWidget(self._model_combo)
        settings_row.addSpacing(20)
        self._diarization_check = QCheckBox("話者識別")
        settings_row.addWidget(self._diarization_check)
        settings_row.addStretch()
        root.addLayout(settings_row)

        self._status_label = QLabel("待機中")
        root.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(200)
        root.addWidget(self._log_view)

        clear_btn = QPushButton("ログをクリア")
        clear_btn.clicked.connect(self._log_view.clear)
        root.addWidget(clear_btn, alignment=Qt.AlignRight)

        self.resize(640, 540)

    def _on_files_dropped(self, paths: list[Path]) -> None:
        if self._processing:
            self._append_log("WARN", "現在処理中のため新しいドロップは無視しました")
            return

        valid: list[Path] = []
        for path in paths:
            if not path.exists():
                self._append_log("WARN", f"File not found: {path}")
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                self._append_log("WARN", f"Unsupported file skipped: {path}")
                continue
            valid.append(path)

        if not valid:
            self._append_log("INFO", "有効なファイルがありませんでした")
            return

        self._append_log("INFO", f"{len(valid)} files dropped")
        language: str = self._lang_combo.currentData()
        model: str = self._model_combo.currentText()
        enable_diarization: bool = self._diarization_check.isChecked()
        self._start_processing(valid, language, model, enable_diarization)

    def _start_processing(
        self,
        files: list[Path],
        language: str,
        model: str,
        enable_diarization: bool,
    ) -> None:
        self._processing = True
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText(f"{len(files)}件中 1件目を処理中")
        self._worker = TranscriptionWorker(files, language, model, enable_diarization)
        self._worker.log_message.connect(self._append_log)
        self._worker.status_update.connect(self._status_label.setText)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, overall_percent: float) -> None:
        self._progress_bar.setValue(int(overall_percent * 10))

    def _on_finished(self, had_errors: bool, success: int, failure: int) -> None:
        self._processing = False
        self._progress_bar.setValue(1000)
        self._progress_bar.setVisible(False)
        self._status_label.setText("エラーあり" if had_errors else "完了")

        if failure == 0:
            body = f"{success}件 成功"
        elif success == 0:
            body = f"{failure}件 失敗"
        else:
            body = f"{success + failure}件中 {success}件 成功 / {failure}件 失敗"
        notifier.notify("文字起こし完了", body)

    def _append_log(self, level: str, message: str) -> None:
        self._log_view.append(f"[{level}] {message}")

    def _apply_settings_to_ui(self) -> None:
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == self._settings.language:
                self._lang_combo.setCurrentIndex(i)
                break
        if self._settings.model in _MODELS:
            self._model_combo.setCurrentText(self._settings.model)
        self._diarization_check.setChecked(self._settings.enable_diarization)

    def _connect_settings_persistence(self) -> None:
        self._lang_combo.currentIndexChanged.connect(self._persist_settings)
        self._model_combo.currentTextChanged.connect(self._persist_settings)
        self._diarization_check.toggled.connect(self._persist_settings)

    def _persist_settings(self, *_args: object) -> None:
        self._settings.language = self._lang_combo.currentData() or self._settings.language
        self._settings.model = self._model_combo.currentText()
        self._settings.enable_diarization = self._diarization_check.isChecked()
        try:
            settings.save(self._settings)
        except OSError as e:
            self._append_log("WARN", f"設定の保存に失敗: {e}")
