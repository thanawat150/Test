from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from PySide6.QtCore import QObject, QStandardPaths, QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "iPhone Video Converter"
SUPPORTED_INPUTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".webm"}

PRESETS = {
    "AI Compatible • 1080p • แนะนำ": {
        "max_height": 1080,
        "crf": 20,
        "preset": "medium",
        "fps": 30,
    },
    "AI Compatible • ความละเอียดเดิม": {
        "max_height": None,
        "crf": 20,
        "preset": "medium",
        "fps": 30,
    },
    "ไฟล์เล็ก • 1080p": {
        "max_height": 1080,
        "crf": 24,
        "preset": "medium",
        "fps": 30,
    },
    "เร็ว • 1080p": {
        "max_height": 1080,
        "crf": 22,
        "preset": "veryfast",
        "fps": 30,
    },
}


@dataclass
class Job:
    row: int
    source: Path
    output: Path


def unique_output_path(source: Path, output_dir: Path) -> Path:
    base = source.stem
    candidate = output_dir / f"{base}_AI.mp4"
    counter = 2
    while candidate.exists():
        candidate = output_dir / f"{base}_AI_{counter}.mp4"
        counter += 1
    return candidate


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def parse_duration_seconds(line: str) -> float | None:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_time_seconds(line: str) -> float | None:
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def build_ffmpeg_command(
    source: Path,
    output: Path,
    preset_name: str,
    keep_60fps: bool = False,
) -> list[str]:
    preset = PRESETS[preset_name]
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    vf_parts: list[str] = []
    max_height = preset["max_height"]
    if max_height:
        vf_parts.append(
            f"scale='if(gt(ih,{max_height}),-2,iw)':'if(gt(ih,{max_height}),{max_height},ih)'"
        )

    # yuv420p gives broad compatibility with browsers, NLEs and AI pipelines.
    vf_parts.append("format=yuv420p")

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        str(preset["preset"]),
        "-crf",
        str(preset["crf"]),
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-pix_fmt",
        "yuv420p",
    ]

    if vf_parts:
        cmd += ["-vf", ",".join(vf_parts)]

    if not keep_60fps:
        cmd += ["-r", str(preset["fps"]), "-fps_mode", "cfr"]

    cmd += [
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "0",
        str(output),
    ]
    return cmd


class ConvertWorker(QObject):
    row_status = Signal(int, str)
    row_progress = Signal(int, int)
    overall_progress = Signal(int, int)
    finished = Signal()
    error = Signal(int, str)

    def __init__(self, jobs: list[Job], preset_name: str, keep_60fps: bool) -> None:
        super().__init__()
        self.jobs = jobs
        self.preset_name = preset_name
        self.keep_60fps = keep_60fps
        self.current_process: subprocess.Popen[str] | None = None
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass

    def run(self) -> None:
        total = len(self.jobs)
        for index, job in enumerate(self.jobs, start=1):
            if self.stop_requested:
                break

            self.row_status.emit(job.row, "กำลังแปลง...")
            self.row_progress.emit(job.row, 0)

            try:
                self._convert_one(job)
                if self.stop_requested:
                    self.row_status.emit(job.row, "หยุดแล้ว")
                    break
                self.row_status.emit(job.row, "สำเร็จ")
                self.row_progress.emit(job.row, 100)
            except Exception as exc:
                if self.stop_requested:
                    self.row_status.emit(job.row, "หยุดแล้ว")
                    break
                self.row_status.emit(job.row, "ผิดพลาด")
                self.error.emit(job.row, str(exc))

            self.overall_progress.emit(index, total)

        self.finished.emit()

    def _convert_one(self, job: Job) -> None:
        job.output.parent.mkdir(parents=True, exist_ok=True)
        cmd = build_ffmpeg_command(
            job.source,
            job.output,
            self.preset_name,
            keep_60fps=self.keep_60fps,
        )

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        duration: float | None = None
        tail: list[str] = []

        assert self.current_process.stderr is not None
        for raw_line in self.current_process.stderr:
            line = raw_line.strip()
            if line:
                tail.append(line)
                if len(tail) > 30:
                    tail.pop(0)

            if duration is None:
                parsed = parse_duration_seconds(line)
                if parsed and parsed > 0:
                    duration = parsed

            current = parse_time_seconds(line)
            if duration and current is not None:
                percent = max(0, min(99, int((current / duration) * 100)))
                self.row_progress.emit(job.row, percent)

            if self.stop_requested:
                try:
                    self.current_process.terminate()
                except OSError:
                    pass
                break

        code = self.current_process.wait()
        self.current_process = None

        if self.stop_requested:
            try:
                job.output.unlink(missing_ok=True)
            except OSError:
                pass
            return

        if code != 0 or not job.output.exists() or job.output.stat().st_size < 1024:
            try:
                job.output.unlink(missing_ok=True)
            except OSError:
                pass
            detail = "\n".join(tail[-12:]) or f"FFmpeg exited with code {code}"
            raise RuntimeError(detail)


class DropTable(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ConvertWorker | None = None
        self.output_dir: Path | None = None

        self.setWindowTitle(f"{APP_NAME} 1.0")
        self.resize(1120, 720)
        self.setAcceptDrops(True)

        self.table = DropTable()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ไฟล์ต้นฉบับ", "ขนาด", "สถานะ", "Progress", "ไฟล์ปลายทาง"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.files_dropped.connect(self.add_paths)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS.keys())

        self.keep_60fps_check = QCheckBox("รักษา FPS เดิม/60fps (ไฟล์จะใหญ่ขึ้น)")
        self.keep_60fps_check.setChecked(False)

        self.output_label = QLabel("บันทึกในโฟลเดอร์เดียวกับต้นฉบับ")
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.add_btn = QPushButton("เพิ่มไฟล์")
        self.add_btn.clicked.connect(self.choose_files)

        self.remove_btn = QPushButton("ลบรายการที่เลือก")
        self.remove_btn.clicked.connect(self.remove_selected)

        self.clear_btn = QPushButton("ล้างรายการ")
        self.clear_btn.clicked.connect(lambda: self.table.setRowCount(0))

        self.output_btn = QPushButton("เลือกโฟลเดอร์ปลายทาง")
        self.output_btn.clicked.connect(self.choose_output_dir)

        self.convert_btn = QPushButton("แปลงเป็น MP4 สำหรับ AI")
        self.convert_btn.setObjectName("primaryButton")
        self.convert_btn.clicked.connect(self.start_conversion)

        self.stop_btn = QPushButton("หยุด")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_conversion)

        self.overall = QProgressBar()
        self.overall.setValue(0)
        self.status = QLabel(
            "ลากไฟล์ .MOV จาก iPhone มาวางได้เลย • ค่าแนะนำ: AI Compatible 1080p"
        )

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel(APP_NAME)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)

        subtitle = QLabel(
            "แปลง .MOV / HEVC จาก iPhone → .MP4 H.264 + AAC ที่ AI และโปรแกรมตัดต่ออ่านได้ง่าย"
        )
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)

        file_group = QGroupBox("1) ไฟล์วิดีโอ — ลากมาวางในตารางได้")
        file_layout = QVBoxLayout(file_group)
        file_layout.addWidget(self.table)

        file_buttons = QHBoxLayout()
        file_buttons.addWidget(self.add_btn)
        file_buttons.addWidget(self.remove_btn)
        file_buttons.addWidget(self.clear_btn)
        file_buttons.addStretch()
        file_layout.addLayout(file_buttons)

        settings_group = QGroupBox("2) ตั้งค่าการแปลง")
        settings_layout = QVBoxLayout(settings_group)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.keep_60fps_check)
        settings_layout.addLayout(preset_row)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("บันทึกที่:"))
        output_row.addWidget(self.output_label, 1)
        output_row.addWidget(self.output_btn)
        settings_layout.addLayout(output_row)

        note = QLabel(
            "AI Compatible จะเข้ารหัสใหม่เป็น H.264/AVC + AAC, yuv420p, CFR 30fps และ faststart "
            "เพื่อเลี่ยงปัญหา HEVC / Variable Frame Rate / codec จาก iPhone ที่ระบบ AI บางตัวอ่านยาก"
        )
        note.setWordWrap(True)
        settings_layout.addWidget(note)

        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(self.stop_btn)
        action_row.addWidget(self.convert_btn)

        root.addWidget(file_group, 1)
        root.addWidget(settings_group)
        root.addLayout(action_row)
        root.addWidget(self.overall)
        root.addWidget(self.status)

        self.setCentralWidget(central)

    def _apply_style(self) -> None:
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
            QTableWidget, QComboBox {
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
                padding: 10px 18px;
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

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "เลือกไฟล์วิดีโอ",
            QStandardPaths.writableLocation(QStandardPaths.MoviesLocation),
            "Video Files (*.mov *.MOV *.mp4 *.MP4 *.m4v *.avi *.mkv *.mts *.m2ts *.webm);;All Files (*.*)",
        )
        self.add_paths(files)

    def add_paths(self, paths: list[str]) -> None:
        existing = {
            self.table.item(row, 0).data(Qt.UserRole)
            for row in range(self.table.rowCount())
            if self.table.item(row, 0)
        }

        added = 0
        for raw in paths:
            path = Path(raw)
            if (
                not path.is_file()
                or path.suffix.lower() not in SUPPORTED_INPUTS
                or str(path) in existing
            ):
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            source_item = QTableWidgetItem(path.name)
            source_item.setData(Qt.UserRole, str(path))
            source_item.setToolTip(str(path))

            try:
                size = human_size(path.stat().st_size)
            except OSError:
                size = "-"

            output_dir = self.output_dir or path.parent
            output = unique_output_path(path, output_dir)

            self.table.setItem(row, 0, source_item)
            self.table.setItem(row, 1, QTableWidgetItem(size))
            self.table.setItem(row, 2, QTableWidgetItem("รอ"))
            self.table.setCellWidget(row, 3, self._progress_widget())
            out_item = QTableWidgetItem(output.name)
            out_item.setToolTip(str(output))
            self.table.setItem(row, 4, out_item)
            added += 1

        if added:
            self.refresh_output_names()
            self.status.setText(f"เพิ่มแล้ว {added} ไฟล์ • พร้อมแปลง")
        elif paths:
            self.status.setText("ไม่มีไฟล์วิดีโอใหม่ที่รองรับในรายการที่เลือก")

    @staticmethod
    def _progress_widget() -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedWidth(150)
        return bar

    def remove_selected(self) -> None:
        rows = sorted(
            {index.row() for index in self.table.selectionModel().selectedRows()},
            reverse=True,
        )
        for row in rows:
            self.table.removeRow(row)

    def choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ปลายทาง")
        if folder:
            self.output_dir = Path(folder)
            self.output_label.setText(str(self.output_dir))
            self.refresh_output_names()

    def refresh_output_names(self) -> None:
        reserved: set[Path] = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item:
                continue
            source = Path(item.data(Qt.UserRole))
            output_dir = self.output_dir or source.parent

            candidate = output_dir / f"{source.stem}_AI.mp4"
            counter = 2
            while candidate.exists() or candidate in reserved:
                candidate = output_dir / f"{source.stem}_AI_{counter}.mp4"
                counter += 1

            reserved.add(candidate)
            out_item = QTableWidgetItem(candidate.name)
            out_item.setData(Qt.UserRole, str(candidate))
            out_item.setToolTip(str(candidate))
            self.table.setItem(row, 4, out_item)

    def start_conversion(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        if self.table.rowCount() == 0:
            QMessageBox.information(self, APP_NAME, "กรุณาเพิ่มไฟล์วิดีโอก่อน")
            return

        self.refresh_output_names()

        jobs: list[Job] = []
        for row in range(self.table.rowCount()):
            source_item = self.table.item(row, 0)
            out_item = self.table.item(row, 4)
            if not source_item or not out_item:
                continue
            source = Path(source_item.data(Qt.UserRole))
            output = Path(out_item.data(Qt.UserRole))
            jobs.append(Job(row, source, output))
            self.table.item(row, 2).setText("รอ")
            bar = self.table.cellWidget(row, 3)
            if isinstance(bar, QProgressBar):
                bar.setValue(0)

        if not jobs:
            return

        self.overall.setRange(0, len(jobs))
        self.overall.setValue(0)

        self.thread = QThread(self)
        self.worker = ConvertWorker(
            jobs,
            self.preset_combo.currentText(),
            self.keep_60fps_check.isChecked(),
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.row_status.connect(self.on_row_status)
        self.worker.row_progress.connect(self.on_row_progress)
        self.worker.overall_progress.connect(self.on_overall_progress)
        self.worker.error.connect(self.on_job_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.status.setText("กำลังแปลงวิดีโอ...")
        self.thread.start()

    def stop_conversion(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.status.setText("กำลังหยุด...")

    def set_busy(self, busy: bool) -> None:
        self.convert_btn.setEnabled(not busy)
        self.add_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.output_btn.setEnabled(not busy)
        self.preset_combo.setEnabled(not busy)
        self.keep_60fps_check.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def on_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, 2)
        if item:
            item.setText(status)

    def on_row_progress(self, row: int, value: int) -> None:
        bar = self.table.cellWidget(row, 3)
        if isinstance(bar, QProgressBar):
            bar.setValue(value)

    def on_overall_progress(self, current: int, total: int) -> None:
        self.overall.setMaximum(total)
        self.overall.setValue(current)
        self.status.setText(f"กำลังแปลง {current} / {total}")

    def on_job_error(self, row: int, message: str) -> None:
        source = self.table.item(row, 0).text() if self.table.item(row, 0) else "ไฟล์"
        QMessageBox.warning(
            self,
            f"แปลง {source} ไม่สำเร็จ",
            "FFmpeg ไม่สามารถแปลงไฟล์นี้ได้\n\n" + message[-1600:],
        )

    def on_finished(self) -> None:
        self.set_busy(False)
        self.status.setText("เสร็จแล้ว • ไฟล์ MP4 พร้อมสำหรับนำไปใช้กับ AI / โปรแกรมตัดต่อ")
        self.worker = None
        self.thread = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.thread and self.thread.isRunning():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "กำลังแปลงวิดีโออยู่ ต้องการปิดโปรแกรมหรือไม่?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.No:
                event.ignore()
                return
            self.worker.request_stop()
            self.thread.quit()
            self.thread.wait(2000)
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
