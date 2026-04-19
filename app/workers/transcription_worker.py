from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services import file_naming, markdown_writer, transcriber


class TranscriptionWorker(QThread):
    log_message = Signal(str, str)   # level, message
    status_update = Signal(str)
    finished = Signal(bool)          # had_errors

    def __init__(self, files: list[Path], language: str, model: str) -> None:
        super().__init__()
        self._files = files
        self._language = language
        self._model = model

    def run(self) -> None:
        total = len(self._files)
        had_errors = False
        for i, path in enumerate(self._files, 1):
            self.status_update.emit(f"{total}件中 {i}件目を処理中")
            self.log_message.emit("INFO", f"Start: {path}")
            try:
                result = transcriber.transcribe(path, self._model, self._language)
                output_path = file_naming.resolve_output_path(path)
                markdown_writer.write(result, output_path)
                self.log_message.emit("INFO", f"Saved: {output_path}")
            except Exception as e:
                had_errors = True
                self.log_message.emit("ERROR", f"Failed: {path} — {e}")
        self.finished.emit(had_errors)
