from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from PySide6.QtCore import QObject, QStandardPaths, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Sentence Voice Studio"

VOICE_OPTIONS = [
    ("ไทย • ผู้หญิง • Premwadee", "th-TH-PremwadeeNeural"),
    ("ไทย • ผู้ชาย • Niwat", "th-TH-NiwatNeural"),
    ("English (US) • ผู้หญิง • Jenny", "en-US-JennyNeural"),
    ("English (US) • ผู้ชาย • Guy", "en-US-GuyNeural"),
]

MODE_FULL = "รวมเป็นไฟล์เดียว"
MODE_LINES = "แยกตามบรรทัด"
MODE_SENTENCES = "แยกตามประโยค"


@dataclass
class QueueItem:
    row: int
    text: str
    filename: str


def split_text(text: str, mode: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    if mode == MODE_FULL:
        return [text]

    if mode == MODE_LINES:
        return [line.strip() for line in text.split("\n") if line.strip()]

    # Sentence mode: split on common sentence-ending punctuation and new lines.
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def safe_filename(text: str, index: int, full_mode: bool = False) -> str:
    if full_mode:
        return "voice_full.mp3"

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    cleaned = cleaned[:48] or "voice"
    return f"{index:03d}_{cleaned}.mp3"


def signed_percent(value: int) -> str:
    return f"{value:+d}%"


def signed_hz(value: int) -> str:
    return f"{value:+d}Hz"


class TTSWorker(QObject):
    row_status = Signal(int, str, str)
    progress = Signal(int, int)
    finished = Signal(list)
    fatal_error = Signal(str)

    def __init__(
        self,
        items: list[QueueItem],
        output_dir: Path,
        voice: str,
        rate: int,
        pitch: int,
        volume: int,
    ) -> None:
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def run(self) -> None:
        try:
            paths = asyncio.run(self._run_async())
            self.finished.emit(paths)
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.fatal_error.emit(str(exc))
            self.finished.emit([])

    async def _run_async(self) -> list[str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        success_paths: list[str] = []
        total = len(self.items)

        for number, item in enumerate(self.items, start=1):
            if QThread.currentThread().isInterruptionRequested():
                break

            path = self.output_dir / item.filename
            self.row_status.emit(item.row, "กำลังสร้าง...", str(path))

            try:
                communicate = edge_tts.Communicate(
                    item.text,
                    self.voice,
                    rate=signed_percent(self.rate),
                    pitch=signed_hz(self.pitch),
                    volume=signed_percent(self.volume),
                )
                await communicate.save(str(path))
                success_paths.append(str(path))
                self.row_status.emit(item.row, "สำเร็จ", str(path))
            except Exception as exc:
                self.row_status.emit(item.row, f"ผิดพลาด: {exc}", str(path))

            self.progress.emit(number, total)

        return success_paths


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: TTSWorker | None = None
        self.preview_mode = False

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 780)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "วางข้อความที่นี่...\n\n"
            "แนะนำ: ถ้าต้องการ 1 บรรทัด = 1 ไฟล์เสียง ให้ขึ้นบรรทัดใหม่ทุกประโยค"
        )
        self.text_edit.setMinimumHeight(240)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([MODE_LINES, MODE_SENTENCES, MODE_FULL])

        self.voice_combo = QComboBox()
        for label, voice_id in VOICE_OPTIONS:
            self.voice_combo.addItem(label, voice_id)

        self.rate_slider = self._slider(-50, 50, 0)
        self.pitch_slider = self._slider(-50, 50, 0)
        self.volume_slider = self._slider(-50, 50, 0)

        self.rate_value = QLabel("+0%")
        self.pitch_value = QLabel("+0Hz")
        self.volume_value = QLabel("+0%")

        self.rate_slider.valueChanged.connect(
            lambda v: self.rate_value.setText(signed_percent(v))
        )
        self.pitch_slider.valueChanged.connect(
            lambda v: self.pitch_value.setText(signed_hz(v))
        )
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_value.setText(signed_percent(v))
        )

        music_dir = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
        base_dir = Path(music_dir) if music_dir else Path.home()
        self.output_dir = base_dir / "SentenceVoiceStudio"

        self.output_label = QLabel(str(self.output_dir))
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.choose_output_btn = QPushButton("เลือกโฟลเดอร์")
        self.choose_output_btn.clicked.connect(self.choose_output_folder)

        self.build_queue_btn = QPushButton("สร้างคิวจากข้อความ")
        self.build_queue_btn.clicked.connect(self.build_queue)

        self.preview_btn = QPushButton("ทดลองฟังรายการที่เลือก")
        self.preview_btn.clicked.connect(self.preview_selected)

        self.generate_selected_btn = QPushButton("สร้างใหม่เฉพาะที่เลือก")
        self.generate_selected_btn.clicked.connect(self.generate_selected)

        self.generate_all_btn = QPushButton("สร้างเสียงทั้งหมด")
        self.generate_all_btn.setObjectName("primaryButton")
        self.generate_all_btn.clicked.connect(self.generate_all)

        self.stop_btn = QPushButton("หยุด")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)

        self.open_folder_btn = QPushButton("เปิดโฟลเดอร์")
        self.open_folder_btn.clicked.connect(self.open_output_folder)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "ข้อความ", "สถานะ", "ไฟล์"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 520)
        self.table.setColumnWidth(2, 180)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellDoubleClicked.connect(self.open_generated_file)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status_label = QLabel("พร้อมใช้งาน")

        self._build_layout()
        self._apply_styles()
        self.build_queue()

    @staticmethod
    def _slider(minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        return slider

    def _build_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Text-to-Speech สำหรับ Windows • แยกเสียงเป็นรายบรรทัดหรือหลายประโยคได้"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        splitter = QSplitter(Qt.Vertical)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        text_group = QGroupBox("1) ข้อความ")
        text_layout = QVBoxLayout(text_group)
        text_layout.addWidget(self.text_edit)
        text_layout.addWidget(self.build_queue_btn)

        settings_group = QGroupBox("2) ตั้งค่าเสียง")
        grid = QGridLayout(settings_group)

        grid.addWidget(QLabel("วิธีแบ่ง"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel("เสียง"), 1, 0)
        grid.addWidget(self.voice_combo, 1, 1, 1, 2)

        grid.addWidget(QLabel("ความเร็ว"), 2, 0)
        grid.addWidget(self.rate_slider, 2, 1)
        grid.addWidget(self.rate_value, 2, 2)

        grid.addWidget(QLabel("Pitch"), 3, 0)
        grid.addWidget(self.pitch_slider, 3, 1)
        grid.addWidget(self.pitch_value, 3, 2)

        grid.addWidget(QLabel("Volume"), 4, 0)
        grid.addWidget(self.volume_slider, 4, 1)
        grid.addWidget(self.volume_value, 4, 2)

        grid.addWidget(QLabel("บันทึกที่"), 5, 0)
        grid.addWidget(self.output_label, 5, 1)
        grid.addWidget(self.choose_output_btn, 5, 2)

        top_layout.addWidget(text_group, 3)
        top_layout.addWidget(settings_group, 2)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        queue_group = QGroupBox("3) คิวเสียง — แก้ข้อความในตารางได้ก่อนสร้าง")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.addWidget(self.table)

        button_row = QHBoxLayout()
        button_row.addWidget(self.preview_btn)
        button_row.addWidget(self.generate_selected_btn)
        button_row.addStretch()
        button_row.addWidget(self.open_folder_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.generate_all_btn)
        queue_layout.addLayout(button_row)

        bottom_layout.addWidget(queue_group)

        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setSizes([340, 420])

        root.addWidget(splitter, 1)
        root.addWidget(self.progress)
        root.addWidget(self.status_label)

        self.setCentralWidget(central)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7fb;
                color: #18202b;
                font-size: 13px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #dfe3ea;
                border-radius: 10px;
                margin-top: 12px;
                padding: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QTextEdit, QTableWidget, QComboBox {
                background: white;
                border: 1px solid #d7dce5;
                border-radius: 7px;
            }
            QPushButton {
                background: white;
                border: 1px solid #cfd5df;
                border-radius: 7px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #eef2f8;
            }
            QPushButton#primaryButton {
                background: #2563eb;
                color: white;
                border: none;
                font-weight: 700;
                padding: 9px 18px;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                color: #9aa3b2;
                background: #eef0f4;
            }
            QProgressBar {
                border: 1px solid #d5d9e2;
                border-radius: 6px;
                text-align: center;
                background: white;
                min-height: 18px;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 5px;
            }
            """
        )

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "เลือกโฟลเดอร์บันทึกเสียง", str(self.output_dir)
        )
        if folder:
            self.output_dir = Path(folder)
            self.output_label.setText(str(self.output_dir))

    def build_queue(self) -> None:
        mode = self.mode_combo.currentText()
        pieces = split_text(self.text_edit.toPlainText(), mode)

        self.table.setRowCount(0)
        full_mode = mode == MODE_FULL

        for index, piece in enumerate(pieces, start=1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            index_item = QTableWidgetItem(str(index))
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)

            text_item = QTableWidgetItem(piece)
            status_item = QTableWidgetItem("รอ")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)

            filename = safe_filename(piece, index, full_mode=full_mode)
            file_item = QTableWidgetItem(filename)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, index_item)
            self.table.setItem(row, 1, text_item)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, file_item)

        self.status_label.setText(f"สร้างคิวแล้ว {len(pieces)} รายการ")

    def _selected_row(self) -> int | None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return None
        return selection[0].row()

    def _queue_item_for_row(self, row: int, preview: bool = False) -> QueueItem:
        text = (self.table.item(row, 1).text() if self.table.item(row, 1) else "").strip()
        if preview:
            filename = "preview.mp3"
        else:
            filename = self.table.item(row, 3).text()
        return QueueItem(row=row, text=text, filename=filename)

    def preview_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "กรุณาเลือกรายการในตารางก่อน")
            return

        item = self._queue_item_for_row(row, preview=True)
        if not item.text:
            return

        preview_dir = Path(tempfile.gettempdir()) / "SentenceVoiceStudio"
        self._start_generation([item], preview_dir, preview=True)

    def generate_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "กรุณาเลือกรายการในตารางก่อน")
            return

        item = self._queue_item_for_row(row)
        if item.text:
            self._start_generation([item], self.output_dir)

    def generate_all(self) -> None:
        if self.table.rowCount() == 0:
            self.build_queue()

        items = [
            self._queue_item_for_row(row)
            for row in range(self.table.rowCount())
            if self.table.item(row, 1) and self.table.item(row, 1).text().strip()
        ]

        if not items:
            QMessageBox.information(self, APP_NAME, "ยังไม่มีข้อความสำหรับสร้างเสียง")
            return

        self._start_generation(items, self.output_dir)

    def _start_generation(
        self,
        items: list[QueueItem],
        output_dir: Path,
        preview: bool = False,
    ) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, APP_NAME, "กำลังสร้างเสียงอยู่ กรุณารอให้จบก่อน")
            return

        self.preview_mode = preview
        self.progress.setRange(0, len(items))
        self.progress.setValue(0)
        self.status_label.setText("กำลังเชื่อมต่อบริการเสียง...")

        self.thread = QThread(self)
        self.worker = TTSWorker(
            items=items,
            output_dir=output_dir,
            voice=self.voice_combo.currentData(),
            rate=self.rate_slider.value(),
            pitch=self.pitch_slider.value(),
            volume=self.volume_slider.value(),
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.row_status.connect(self.on_row_status)
        self.worker.progress.connect(self.on_progress)
        self.worker.fatal_error.connect(self.on_fatal_error)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self._set_busy(True)
        self.thread.start()

    def stop_generation(self) -> None:
        if self.thread and self.thread.isRunning():
            self.thread.requestInterruption()
            self.status_label.setText(
                "กำลังหยุดหลังจากไฟล์ปัจจุบันเสร็จ..."
            )

    def _set_busy(self, busy: bool) -> None:
        self.generate_all_btn.setEnabled(not busy)
        self.generate_selected_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)
        self.build_queue_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def on_row_status(self, row: int, status: str, path: str) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.item(row, 2).setText(status)
            if not self.preview_mode and self.table.item(row, 3):
                self.table.item(row, 3).setToolTip(path)

    def on_progress(self, current: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(current)
        self.status_label.setText(f"กำลังสร้าง {current} / {total}")

    def on_fatal_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            APP_NAME,
            "เกิดข้อผิดพลาดในการสร้างเสียง\n\n"
            f"{message}\n\n"
            "ตรวจสอบการเชื่อมต่ออินเทอร์เน็ตแล้วลองใหม่อีกครั้ง",
        )

    def on_generation_finished(self, paths: list[str]) -> None:
        self._set_busy(False)

        if self.preview_mode:
            self.status_label.setText("ทดลองฟังเสร็จแล้ว")
            if paths:
                QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0]))
        else:
            self.status_label.setText(
                f"เสร็จแล้ว {len(paths)} ไฟล์ • {self.output_dir}"
            )

        self.preview_mode = False
        self.thread = None
        self.worker = None

    def open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def open_generated_file(self, row: int, _column: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        filename_item = self.table.item(row, 3)
        if not filename_item:
            return
        path = self.output_dir / filename_item.text()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(
                self,
                APP_NAME,
                "กำลังสร้างเสียงอยู่ ต้องการปิดโปรแกรมหรือไม่?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.thread.requestInterruption()
            self.thread.quit()
            self.thread.wait(1500)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
