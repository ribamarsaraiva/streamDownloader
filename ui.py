"""
ui.py — Interface desktop (PySide6).

Fluxo:
  1. Colar link + "Analisar"  -> lista opcoes simplificadas
  2. Escolher opcao na lista
  3. "Escolher pasta" (dialogo nativo)
  4. "Baixar" + barra de progresso

Trabalho pesado (analise e download) roda em QThread para nao travar a UI.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import downloader
from downloader import SimpleOption, VideoInfo


class AnalyzeWorker(QThread):
    """Extrai formatos numa thread separada."""
    done = Signal(object)      # VideoInfo
    failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            info = downloader.list_formats(self.url)
            self.done.emit(info)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class DownloadWorker(QThread):
    """Baixa numa thread separada."""
    progress = Signal(dict)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, option: SimpleOption, dest: str, ffmpeg: Optional[str]):
        super().__init__()
        self.url = url
        self.option = option
        self.dest = dest
        self.ffmpeg = ffmpeg

    def run(self) -> None:
        try:
            path = downloader.download(
                self.url,
                self.option,
                self.dest,
                ffmpeg_path=self.ffmpeg,
                progress_cb=self.progress.emit,
            )
            self.done.emit(path or "")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QWidget):
    def __init__(self, ffmpeg_path: Optional[str] = None):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.current_info: Optional[VideoInfo] = None
        self.dest_dir: str = os.path.join(os.path.expanduser("~"), "Downloads")
        self._analyze_worker: Optional[AnalyzeWorker] = None
        self._download_worker: Optional[DownloadWorker] = None

        self.setWindowTitle("Stream Downloader")
        self.setMinimumWidth(560)
        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Linha do link
        link_row = QHBoxLayout()
        self.link_edit = QLineEdit()
        self.link_edit.setPlaceholderText("Cole o link do video (YouTube, X, Instagram, Facebook...)")
        self.link_edit.returnPressed.connect(self.on_analyze)
        self.analyze_btn = QPushButton("Analisar")
        self.analyze_btn.clicked.connect(self.on_analyze)
        link_row.addWidget(self.link_edit)
        link_row.addWidget(self.analyze_btn)
        layout.addLayout(link_row)

        # Titulo do video
        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Combo de formatos
        self.format_combo = QComboBox()
        self.format_combo.setEnabled(False)
        layout.addWidget(QLabel("Formato:"))
        layout.addWidget(self.format_combo)

        # Linha da pasta
        dest_row = QHBoxLayout()
        self.dest_label = QLineEdit(self.dest_dir)
        self.dest_label.setReadOnly(True)
        self.choose_dir_btn = QPushButton("Escolher pasta")
        self.choose_dir_btn.clicked.connect(self.on_choose_dir)
        dest_row.addWidget(self.dest_label)
        dest_row.addWidget(self.choose_dir_btn)
        layout.addLayout(dest_row)

        # Botao baixar
        self.download_btn = QPushButton("Baixar")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.on_download)
        layout.addWidget(self.download_btn)

        # Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)
        layout.addWidget(self.log)

    # ------------------------------------------------------------------ #
    def _log(self, msg: str) -> None:
        self.log.append(msg)

    def _set_busy(self, busy: bool) -> None:
        self.analyze_btn.setEnabled(not busy)
        self.download_btn.setEnabled(not busy and self.current_info is not None)
        self.link_edit.setEnabled(not busy)

    # ------------------------------------------------------------------ #
    def on_analyze(self) -> None:
        url = self.link_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Atencao", "Cole um link primeiro.")
            return
        self._set_busy(True)
        self.format_combo.clear()
        self.format_combo.setEnabled(False)
        self.title_label.setText("Analisando...")
        self._log(f"Analisando: {url}")

        self._analyze_worker = AnalyzeWorker(url)
        self._analyze_worker.done.connect(self._on_analyze_done)
        self._analyze_worker.failed.connect(self._on_analyze_failed)
        self._analyze_worker.start()

    def _on_analyze_done(self, info: VideoInfo) -> None:
        self.current_info = info
        self.title_label.setText(f"<b>{info.title}</b>")
        self.format_combo.clear()
        for opt in info.options:
            self.format_combo.addItem(opt.label)
        self.format_combo.setEnabled(True)
        self._set_busy(False)
        self.download_btn.setEnabled(True)
        self._log(f"Encontradas {len(info.options)} opcoes.")
        if info.is_playlist:
            self._log("AVISO: o link e uma playlist. Apenas o PRIMEIRO video sera baixado.")

    def _on_analyze_failed(self, err: str) -> None:
        self.title_label.setText("")
        self._set_busy(False)
        self._log(f"ERRO: {err}")
        QMessageBox.critical(self, "Erro ao analisar", err)

    # ------------------------------------------------------------------ #
    def on_choose_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Escolher pasta de destino", self.dest_dir)
        if chosen:
            self.dest_dir = chosen
            self.dest_label.setText(chosen)

    # ------------------------------------------------------------------ #
    def on_download(self) -> None:
        if not self.current_info:
            return
        idx = self.format_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Atencao", "Escolha um formato.")
            return
        option = self.current_info.options[idx]
        url = self.current_info.webpage_url

        self._set_busy(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._log(f"Baixando '{option.label}' para {self.dest_dir} ...")

        self._download_worker = DownloadWorker(url, option, self.dest_dir, self.ffmpeg_path)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.done.connect(self._on_download_done)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.start()

    def _on_progress(self, d: dict) -> None:
        percent = d.get("percent")
        if percent is not None:
            # Modo determinado: mostra a porcentagem real.
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(percent))
        else:
            # Sem tamanho total conhecido: barra indeterminada (animada).
            self.progress_bar.setRange(0, 0)
        status = d.get("status")
        if status == "processing":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self._log("Processando (juntando audio/video)...")

    def _on_download_done(self, path: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._set_busy(False)
        self._log(f"Concluido: {path}")
        QMessageBox.information(self, "Pronto", f"Download concluido:\n{path}")

    def _on_download_failed(self, err: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(False)
        self._log(f"ERRO: {err}")
        QMessageBox.critical(self, "Erro ao baixar", err)


def run(ffmpeg_path: Optional[str] = None) -> int:
    app = QApplication.instance() or QApplication([])
    win = MainWindow(ffmpeg_path=ffmpeg_path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    run()
