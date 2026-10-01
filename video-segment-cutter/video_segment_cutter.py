from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

import imageio_ffmpeg
from python_calamine import CalamineWorkbook
from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Video Segment Cutter"
SUPPORTED_VIDEO = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".webm"}
SUPPORTED_EXCEL = {".xlsx", ".xls", ".xlsb", ".ods"}

COL_USE = 0
COL_RAW = 1
COL_START = 2
COL_END = 3
COL_RANGE = 4
COL_LENGTH = 5
COL_PURPOSE = 6
COL_PRIORITY = 7
COL_SOURCE = 8
COL_MATCH = 9
COL_OUTPUT = 10
COL_STATUS = 11
COL_PROGRESS = 12

PRESETS = {
    "AI Ready • 1080p • แนะนำ": {"max_height": 1080, "crf": 20, "preset": "medium", "fps": 30},
    "AI Ready • ความละเอียดเดิม": {"max_height": None, "crf": 20, "preset": "medium", "fps": 30},
    "ไฟล์เล็ก • 1080p": {"max_height": 1080, "crf": 24, "preset": "medium", "fps": 30},
    "เร็ว • 1080p": {"max_height": 1080, "crf": 22, "preset": "veryfast", "fps": 30},
}

HEADER_KEYWORDS = {
    "raw": ("raw", "filename", "file name", "file", "ชื่อไฟล์", "ไฟล์", "video", "clip", "ต้นฉบับ"),
    "range": ("ตัดช่วง", "ช่วง", "time range", "range", "in-out", "in / out", "ช่วงเวลา"),
    "start": ("start", "เวลาเริ่ม", "เริ่ม", "in", "from", "จาก"),
    "end": ("end", "เวลาจบ", "จบ", "out", "to", "ถึง"),
    "purpose": ("เก็บไว้เพื่อ", "purpose", "ใช้เพื่อ", "หมายเหตุ", "note", "description", "รายละเอียด"),
    "priority": ("priority", "ความสำคัญ", "ระดับ", "สำคัญ"),
}


@dataclass
class PlanRow:
    raw_name: str
    start: str
    end: str
    purpose: str
    priority: str


@dataclass
class CutJob:
    row: int
    source: Path
    output: Path
    start_seconds: float
    duration_seconds: float


def value_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, time):
        total = value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000
        return seconds_to_timecode(total)
    if isinstance(value, timedelta):
        return seconds_to_timecode(value.total_seconds())
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip()


def normalize_header(value: str) -> str:
    value = value_to_text(value).lower().strip()
    value = re.sub(r"[\s_\-/]+", " ", value)
    return value


def find_best_header_row(data: list[list], max_rows: int = 20) -> int:
    best_index = 0
    best_score = -1

    for row_index, row in enumerate(data[:max_rows]):
        score = 0
        seen_groups: set[str] = set()
        for cell in row:
            header = normalize_header(cell)
            if not header:
                continue
            for group, keywords in HEADER_KEYWORDS.items():
                if group in seen_groups:
                    continue
                if any(keyword in header for keyword in keywords):
                    score += 3 if group == "raw" else 2
                    seen_groups.add(group)
        if score > best_score:
            best_score = score
            best_index = row_index

    return best_index


def detect_column(headers: list[str], kind: str) -> int | None:
    keywords = HEADER_KEYWORDS[kind]
    normalized = [normalize_header(x) for x in headers]

    # Exact/strong substring matches first.
    for idx, header in enumerate(normalized):
        if not header:
            continue
        if any(header == key or key in header for key in keywords):
            return idx
    return None


def parse_timecode(value) -> float:
    if value is None:
        raise ValueError("เวลาเป็นค่าว่าง")
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, time):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000

    text = value_to_text(value).strip().replace(",", ".")
    if not text:
        raise ValueError("เวลาเป็นค่าว่าง")

    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)

    parts = text.split(":")
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        if seconds >= 60:
            raise ValueError(f"เวลาไม่ถูกต้อง: {text}")
        return minutes * 60 + seconds

    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        if minutes >= 60 or seconds >= 60:
            raise ValueError(f"เวลาไม่ถูกต้อง: {text}")
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"เวลาไม่ถูกต้อง: {text}")


def parse_range_cell(value) -> tuple[str, str]:
    text = value_to_text(value)
    # Prefer explicit arrows / words; allow hyphen surrounded by spaces.
    parts = re.split(r"\s*(?:→|->|–|—|\bto\b|\bถึง\b)\s*", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        parts = re.split(r"\s+-\s+", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"อ่านช่วงเวลาไม่ได้: {text}")
    parse_timecode(parts[0])
    parse_timecode(parts[1])
    return parts[0].strip(), parts[1].strip()


def seconds_to_timecode(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:04.1f}"
    return f"{minutes:02d}:{secs:04.1f}"


def normalize_priority(value) -> str:
    text = value_to_text(value).upper().replace("*", "").strip()
    if "BACKUP" in text:
        return "BACKUP"
    if "PRIMARY" in text:
        return "PRIMARY"
    return text or "PRIMARY"


def sanitize_output_name(raw_name: str) -> str:
    stem = Path(raw_name).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", stem).strip(" .")
    return (stem or "clip") + ".mp4"


def build_ffmpeg_command(job: CutJob, preset_name: str) -> list[str]:
    cfg = PRESETS[preset_name]
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    filters: list[str] = []
    max_height = cfg["max_height"]
    if max_height:
        filters.append(
            f"scale='if(gt(ih,{max_height}),-2,iw)':'if(gt(ih,{max_height}),{max_height},ih)'"
        )
    filters.append("format=yuv420p")

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{job.start_seconds:.3f}",
        "-i",
        str(job.source),
        "-t",
        f"{job.duration_seconds:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        str(cfg["preset"]),
        "-crf",
        str(cfg["crf"]),
        "-pix_fmt",
        "yuv420p",
        "-vf",
        ",".join(filters),
        "-r",
        str(cfg["fps"]),
        "-fps_mode",
        "cfr",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(job.output),
    ]
    return cmd


class VideoDropTable(QTableWidget):
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
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class CutWorker(QObject):
    row_status = Signal(int, str)
    row_progress = Signal(int, int)
    overall = Signal(int, int)
    error = Signal(int, str)
    finished = Signal()

    def __init__(self, jobs: list[CutJob], preset_name: str) -> None:
        super().__init__()
        self.jobs = jobs
        self.preset_name = preset_name
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
            self.row_status.emit(job.row, "กำลังตัด...")
            self.row_progress.emit(job.row, 0)
            try:
                self._cut_one(job)
                if self.stop_requested:
                    self.row_status.emit(job.row, "หยุดแล้ว")
                    break
                self.row_progress.emit(job.row, 100)
                self.row_status.emit(job.row, "สำเร็จ")
            except Exception as exc:
                try:
                    job.output.unlink(missing_ok=True)
                except OSError:
                    pass
                self.row_status.emit(job.row, "ผิดพลาด")
                self.error.emit(job.row, str(exc))
            self.overall.emit(index, total)
        self.finished.emit()

    def _cut_one(self, job: CutJob) -> None:
        job.output.parent.mkdir(parents=True, exist_ok=True)
        cmd = build_ffmpeg_command(job, self.preset_name)

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        errors: list[str] = []
        assert self.current_process.stdout is not None
        for raw_line in self.current_process.stdout:
            line = raw_line.strip()
            if line.startswith("out_time_us="):
                try:
                    current = int(line.split("=", 1)[1]) / 1_000_000
                    percent = int(min(99, max(0, current / job.duration_seconds * 100)))
                    self.row_progress.emit(job.row, percent)
                except (ValueError, ZeroDivisionError):
                    pass
            elif line and "=" not in line:
                errors.append(line)
                if len(errors) > 20:
                    errors.pop(0)

            if self.stop_requested:
                try:
                    self.current_process.terminate()
                except OSError:
                    pass
                break

        code = self.current_process.wait()
        self.current_process = None

        if self.stop_requested:
            job.output.unlink(missing_ok=True)
            return

        if code != 0 or not job.output.exists() or job.output.stat().st_size < 1024:
            detail = "\n".join(errors[-10:]) or f"FFmpeg exited with code {code}"
            raise RuntimeError(detail)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.workbook_path: Path | None = None
        self.workbook: CalamineWorkbook | None = None
        self.sheet_data: list[list] = []
        self.header_row_index = 0
        self.video_index: dict[str, list[Path]] = {}
        self.video_root: Path | None = None
        self.output_dir: Path | None = None
        self.thread: QThread | None = None
        self.worker: CutWorker | None = None

        self.setWindowTitle(f"{APP_NAME} 1.1")
        self.resize(1440, 900)

        self.tabs = QTabWidget()

        self.open_excel_btn = QPushButton("เปิด Excel")
        self.open_excel_btn.setObjectName("primaryButton")
        self.open_excel_btn.clicked.connect(self.open_excel)

        self.excel_label = QLabel("ยังไม่ได้เลือกไฟล์ Excel")
        self.excel_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.sheet_combo = QComboBox()
        self.sheet_combo.currentTextChanged.connect(self.load_selected_sheet)
        self.sheet_combo.setEnabled(False)

        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, 9999)
        self.header_spin.setValue(1)
        self.header_spin.valueChanged.connect(self.refresh_mapping)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.raw_combo = QComboBox()
        self.range_combo = QComboBox()
        self.start_combo = QComboBox()
        self.end_combo = QComboBox()
        self.purpose_combo = QComboBox()
        self.priority_combo = QComboBox()

        self.auto_map_btn = QPushButton("เดาคอลัมน์อัตโนมัติ")
        self.auto_map_btn.clicked.connect(self.auto_map_columns)

        self.load_plan_btn = QPushButton("นำข้อมูลไปหน้า Cut Plan")
        self.load_plan_btn.setObjectName("primaryButton")
        self.load_plan_btn.clicked.connect(self.build_plan_from_excel)

        self.plan_table = VideoDropTable()
        self.plan_table.setColumnCount(13)
        self.plan_table.setHorizontalHeaderLabels([
            "ใช้", "RAW", "Start", "End", "ช่วงตัด (Auto)", "Duration (Auto)",
            "เก็บไว้เพื่อ", "Priority", "ไฟล์วิดีโอจริง", "Match",
            "Output", "สถานะ", "Progress",
        ])
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.plan_table.horizontalHeader().setSectionResizeMode(COL_PURPOSE, QHeaderView.Stretch)
        self.plan_table.horizontalHeader().setSectionResizeMode(COL_SOURCE, QHeaderView.Stretch)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.plan_table.files_dropped.connect(self.add_video_paths)
        self.plan_table.itemChanged.connect(self.on_plan_item_changed)

        self.video_folder_btn = QPushButton("เลือกโฟลเดอร์วิดีโอ RAW")
        self.video_folder_btn.clicked.connect(self.choose_video_folder)

        self.add_video_btn = QPushButton("เพิ่มไฟล์วิดีโอ")
        self.add_video_btn.clicked.connect(self.choose_video_files)

        self.rematch_btn = QPushButton("จับคู่ชื่อไฟล์ใหม่")
        self.rematch_btn.clicked.connect(self.match_all_sources)

        self.primary_only_btn = QPushButton("เลือกเฉพาะ PRIMARY")
        self.primary_only_btn.clicked.connect(self.select_primary_only)

        self.select_all_btn = QPushButton("เลือกทั้งหมด")
        self.select_all_btn.clicked.connect(lambda: self.set_all_checks(True))

        self.output_btn = QPushButton("เลือกโฟลเดอร์ Output")
        self.output_btn.clicked.connect(self.choose_output_dir)

        self.output_label = QLabel("Output: จะสร้างโฟลเดอร์ CUT_MP4 ภายใต้โฟลเดอร์ RAW")
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS.keys())

        self.preflight_btn = QPushButton("ตรวจสอบก่อนตัด")
        self.preflight_btn.clicked.connect(self.run_preflight)

        self.cut_btn = QPushButton("ยืนยันแผนตัดและเริ่ม")
        self.cut_btn.setObjectName("primaryButton")
        self.cut_btn.clicked.connect(self.start_cutting)

        self.stop_btn = QPushButton("หยุด")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_cutting)

        self.open_output_btn = QPushButton("เปิดโฟลเดอร์ Output")
        self.open_output_btn.clicked.connect(self.open_output_dir)

        self.overall = QProgressBar()
        self.overall.setValue(0)
        self.status = QLabel("1) เปิด Excel → 2) ตรวจข้อมูล → 3) จับคู่ RAW → 4) ตรวจสอบ → 5) ตัด")

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel(APP_NAME)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)

        subtitle = QLabel(
            "อ่านแผนตัดจาก Excel ให้ตรวจสอบก่อน แล้วตัดเฉพาะช่วงที่ต้องการเป็น MP4 สำหรับ AI"
        )
        root.addWidget(title)
        root.addWidget(subtitle)

        # Excel Preview tab
        excel_tab = QWidget()
        excel_layout = QVBoxLayout(excel_tab)

        excel_top = QHBoxLayout()
        excel_top.addWidget(self.open_excel_btn)
        excel_top.addWidget(self.excel_label, 1)
        excel_top.addWidget(QLabel("Sheet:"))
        excel_top.addWidget(self.sheet_combo)
        excel_top.addWidget(QLabel("แถวหัวตาราง:"))
        excel_top.addWidget(self.header_spin)
        excel_layout.addLayout(excel_top)

        preview_group = QGroupBox("Excel Preview — ดูข้อมูลดิบก่อน โปรแกรมยังไม่ตัดวิดีโอ")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.addWidget(self.preview_table)
        excel_layout.addWidget(preview_group, 1)

        map_group = QGroupBox("จับคู่คอลัมน์")
        map_layout = QHBoxLayout(map_group)
        for label, combo in [
            ("RAW", self.raw_combo),
            ("ช่วงเวลา", self.range_combo),
            ("Start", self.start_combo),
            ("End", self.end_combo),
            ("เก็บไว้เพื่อ", self.purpose_combo),
            ("Priority", self.priority_combo),
        ]:
            box = QVBoxLayout()
            box.addWidget(QLabel(label))
            box.addWidget(combo)
            map_layout.addLayout(box)
        excel_layout.addWidget(map_group)

        map_actions = QHBoxLayout()
        map_actions.addWidget(self.auto_map_btn)
        map_actions.addStretch()
        map_actions.addWidget(self.load_plan_btn)
        excel_layout.addLayout(map_actions)

        # Cut Plan tab
        plan_tab = QWidget()
        plan_layout = QVBoxLayout(plan_tab)

        plan_hint = QLabel(
            "แก้ RAW / Start / End / Purpose / Priority ได้โดยตรง • "
            "ช่วงตัดและ Duration คำนวณอัตโนมัติ • ลากไฟล์วิดีโอมาวางในตารางได้"
        )
        plan_layout.addWidget(plan_hint)
        plan_layout.addWidget(self.plan_table, 1)

        video_actions = QHBoxLayout()
        video_actions.addWidget(self.video_folder_btn)
        video_actions.addWidget(self.add_video_btn)
        video_actions.addWidget(self.rematch_btn)
        video_actions.addWidget(self.primary_only_btn)
        video_actions.addWidget(self.select_all_btn)
        video_actions.addStretch()
        plan_layout.addLayout(video_actions)

        settings = QGroupBox("Output")
        settings_layout = QHBoxLayout(settings)
        settings_layout.addWidget(QLabel("Preset:"))
        settings_layout.addWidget(self.preset_combo)
        settings_layout.addWidget(self.output_btn)
        settings_layout.addWidget(self.output_label, 1)
        settings_layout.addWidget(self.open_output_btn)
        plan_layout.addWidget(settings)

        actions = QHBoxLayout()
        actions.addWidget(self.preflight_btn)
        actions.addStretch()
        actions.addWidget(self.stop_btn)
        actions.addWidget(self.cut_btn)
        plan_layout.addLayout(actions)
        plan_layout.addWidget(self.overall)

        self.tabs.addTab(excel_tab, "1. Excel Preview")
        self.tabs.addTab(plan_tab, "2. Cut Plan")

        root.addWidget(self.tabs, 1)
        root.addWidget(self.status)
        self.setCentralWidget(central)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
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
            QTableWidget, QComboBox, QSpinBox {
                background: white;
                border: 1px solid #d7dce5;
                border-radius: 6px;
            }
            QPushButton {
                background: white;
                border: 1px solid #cfd5df;
                border-radius: 7px;
                padding: 8px 12px;
            }
            QPushButton:hover { background: #eef2f8; }
            QPushButton#primaryButton {
                background: #2563eb;
                color: white;
                border: none;
                font-weight: 700;
                padding: 9px 16px;
            }
            QPushButton#primaryButton:hover { background: #1d4ed8; }
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
        """)

    def open_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "เลือก Excel แผนตัดวิดีโอ",
            "",
            "Spreadsheet (*.xlsx *.xls *.xlsb *.ods);;All Files (*.*)",
        )
        if not path:
            return

        try:
            if self.workbook:
                self.workbook.close()
            self.workbook_path = Path(path)
            self.workbook = CalamineWorkbook.from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"เปิด Excel ไม่สำเร็จ\n\n{exc}")
            return

        self.excel_label.setText(str(self.workbook_path))
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(self.workbook.sheet_names)
        self.sheet_combo.blockSignals(False)
        self.sheet_combo.setEnabled(True)

        if self.workbook.sheet_names:
            self.sheet_combo.setCurrentIndex(0)
            self.load_selected_sheet(self.sheet_combo.currentText())

    def load_selected_sheet(self, name: str) -> None:
        if not self.workbook or not name:
            return
        try:
            self.sheet_data = self.workbook.get_sheet_by_name(name).to_python(skip_empty_area=False)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"อ่าน Sheet ไม่สำเร็จ\n\n{exc}")
            return

        self.header_row_index = find_best_header_row(self.sheet_data)
        self.header_spin.blockSignals(True)
        self.header_spin.setMaximum(max(1, len(self.sheet_data)))
        self.header_spin.setValue(self.header_row_index + 1)
        self.header_spin.blockSignals(False)
        self.render_excel_preview()
        self.refresh_mapping()
        self.auto_map_columns()
        self.status.setText(
            f"อ่าน Excel แล้ว • Sheet {name} • เดาหัวตารางที่แถว {self.header_row_index + 1} — ตรวจสอบก่อนนำไป Cut Plan"
        )

    def render_excel_preview(self) -> None:
        rows = self.sheet_data
        max_cols = max((len(row) for row in rows), default=0)
        self.preview_table.clear()
        self.preview_table.setRowCount(len(rows))
        self.preview_table.setColumnCount(max_cols)
        self.preview_table.setHorizontalHeaderLabels([f"Col {i+1}" for i in range(max_cols)])

        for r, row in enumerate(rows):
            for c in range(max_cols):
                value = row[c] if c < len(row) else ""
                item = QTableWidgetItem(value_to_text(value))
                if r == self.header_row_index:
                    item.setBackground(QColor("#dbeafe"))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.preview_table.setItem(r, c, item)

        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def current_headers(self) -> list[str]:
        if not self.sheet_data:
            return []
        idx = max(0, min(self.header_spin.value() - 1, len(self.sheet_data) - 1))
        row = self.sheet_data[idx]
        max_cols = max((len(r) for r in self.sheet_data), default=len(row))
        return [value_to_text(row[c] if c < len(row) else "") or f"Column {c+1}" for c in range(max_cols)]

    def refresh_mapping(self) -> None:
        if not self.sheet_data:
            return
        self.header_row_index = max(0, self.header_spin.value() - 1)
        self.render_excel_preview()
        headers = self.current_headers()

        combos = [
            self.raw_combo, self.range_combo, self.start_combo,
            self.end_combo, self.purpose_combo, self.priority_combo,
        ]
        for combo in combos:
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— ไม่ใช้ —", None)
            for idx, header in enumerate(headers):
                combo.addItem(f"{idx+1}: {header}", idx)
            if current is not None:
                pos = combo.findData(current)
                if pos >= 0:
                    combo.setCurrentIndex(pos)
            combo.blockSignals(False)

    def auto_map_columns(self) -> None:
        headers = self.current_headers()
        if not headers:
            return

        mapping = {
            self.raw_combo: detect_column(headers, "raw"),
            self.range_combo: detect_column(headers, "range"),
            self.start_combo: detect_column(headers, "start"),
            self.end_combo: detect_column(headers, "end"),
            self.purpose_combo: detect_column(headers, "purpose"),
            self.priority_combo: detect_column(headers, "priority"),
        }

        for combo, col in mapping.items():
            combo.setCurrentIndex(0 if col is None else combo.findData(col))

        self.status.setText("เดาคอลัมน์แล้ว • กรุณาตรวจ RAW และช่วงเวลาก่อนสร้าง Cut Plan")

    @staticmethod
    def _row_value(row: list, index: int | None):
        if index is None or index < 0 or index >= len(row):
            return ""
        return row[index]

    def build_plan_from_excel(self) -> None:
        raw_col = self.raw_combo.currentData()
        range_col = self.range_combo.currentData()
        start_col = self.start_combo.currentData()
        end_col = self.end_combo.currentData()
        purpose_col = self.purpose_combo.currentData()
        priority_col = self.priority_combo.currentData()

        if raw_col is None:
            QMessageBox.information(self, APP_NAME, "กรุณาเลือกคอลัมน์ RAW/ชื่อไฟล์")
            return
        if range_col is None and (start_col is None or end_col is None):
            QMessageBox.information(
                self, APP_NAME, "กรุณาเลือกคอลัมน์ช่วงเวลา หรือเลือก Start และ End"
            )
            return

        plan: list[PlanRow] = []
        errors: list[str] = []
        for excel_row_index, row in enumerate(self.sheet_data[self.header_row_index + 1:], start=self.header_row_index + 2):
            raw_name = value_to_text(self._row_value(row, raw_col)).strip()
            if not raw_name:
                continue

            try:
                if range_col is not None:
                    start, end = parse_range_cell(self._row_value(row, range_col))
                else:
                    start = value_to_text(self._row_value(row, start_col))
                    end = value_to_text(self._row_value(row, end_col))
                    parse_timecode(start)
                    parse_timecode(end)
            except Exception as exc:
                start = value_to_text(self._row_value(row, start_col)) if start_col is not None else ""
                end = value_to_text(self._row_value(row, end_col)) if end_col is not None else ""
                errors.append(f"Excel แถว {excel_row_index}: {raw_name} — {exc}")

            purpose = value_to_text(self._row_value(row, purpose_col))
            priority = normalize_priority(self._row_value(row, priority_col))
            plan.append(PlanRow(raw_name, start, end, purpose, priority))

        self.populate_plan(plan)
        self.tabs.setCurrentIndex(1)

        if errors:
            QMessageBox.warning(
                self,
                "มีข้อมูลเวลาที่ควรตรวจ",
                "นำข้อมูลเข้า Cut Plan แล้ว แต่มีบางแถวอ่านเวลาไม่ได้\n"
                "โปรแกรมยังไม่ตัดวิดีโอ กรุณาแก้ในตารางก่อน\n\n"
                + "\n".join(errors[:12]),
            )
        else:
            self.status.setText(f"สร้าง Cut Plan แล้ว {len(plan)} รายการ • ยังไม่มีการตัดไฟล์")

    def populate_plan(self, plan: list[PlanRow]) -> None:
        self.plan_table.blockSignals(True)
        self.plan_table.setRowCount(0)

        for item in plan:
            row = self.plan_table.rowCount()
            self.plan_table.insertRow(row)

            use_item = QTableWidgetItem()
            use_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            use_item.setCheckState(Qt.Checked)
            self.plan_table.setItem(row, COL_USE, use_item)

            self.plan_table.setItem(row, COL_RAW, QTableWidgetItem(item.raw_name))
            self.plan_table.setItem(row, COL_START, QTableWidgetItem(item.start))
            self.plan_table.setItem(row, COL_END, QTableWidgetItem(item.end))
            self.plan_table.setItem(row, COL_RANGE, QTableWidgetItem(""))
            self.plan_table.setItem(row, COL_LENGTH, QTableWidgetItem(""))
            self.plan_table.setItem(row, COL_PURPOSE, QTableWidgetItem(item.purpose))
            self.plan_table.setItem(row, COL_PRIORITY, QTableWidgetItem(item.priority))
            self.plan_table.setItem(row, COL_SOURCE, QTableWidgetItem(""))
            self.plan_table.setItem(row, COL_MATCH, QTableWidgetItem("ยังไม่จับคู่"))
            self.plan_table.setItem(row, COL_OUTPUT, QTableWidgetItem(sanitize_output_name(item.raw_name)))
            self.plan_table.setItem(row, COL_STATUS, QTableWidgetItem("รอตรวจสอบ"))

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedWidth(120)
            self.plan_table.setCellWidget(row, COL_PROGRESS, bar)

            for col in (COL_RANGE, COL_LENGTH, COL_SOURCE, COL_MATCH, COL_OUTPUT, COL_STATUS):
                table_item = self.plan_table.item(row, col)
                if table_item:
                    table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)

            self.validate_plan_row(row)

        self.plan_table.blockSignals(False)
        if self.video_index:
            self.match_all_sources()

    def choose_video_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ไฟล์วิดีโอ RAW")
        if not folder:
            return
        self.video_root = Path(folder)
        paths = [p for p in self.video_root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO]
        self.index_video_paths(paths)
        if self.output_dir is None:
            self.output_dir = self.video_root / "CUT_MP4"
            self.output_label.setText(str(self.output_dir))
        self.match_all_sources()
        self.status.setText(f"พบไฟล์วิดีโอ {len(paths)} ไฟล์ • จับคู่กับ Cut Plan แล้ว")

    def choose_video_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "เพิ่มไฟล์วิดีโอ",
            "",
            "Video (*.mov *.MOV *.mp4 *.MP4 *.m4v *.avi *.mkv *.mts *.m2ts *.webm);;All Files (*.*)",
        )
        self.add_video_paths(files)

    def add_video_paths(self, raw_paths: list[str]) -> None:
        paths = [Path(x) for x in raw_paths if Path(x).is_file() and Path(x).suffix.lower() in SUPPORTED_VIDEO]
        if not paths:
            return
        if self.video_root is None:
            self.video_root = paths[0].parent
        self.index_video_paths(paths, append=True)
        if self.output_dir is None:
            self.output_dir = self.video_root / "CUT_MP4"
            self.output_label.setText(str(self.output_dir))
        self.match_all_sources()

    def index_video_paths(self, paths: list[Path], append: bool = False) -> None:
        if not append:
            self.video_index.clear()
        for path in paths:
            key = path.name.casefold()
            bucket = self.video_index.setdefault(key, [])
            if path not in bucket:
                bucket.append(path)

    def match_source(self, raw_name: str) -> tuple[Path | None, str]:
        raw = Path(raw_name).name
        exact = self.video_index.get(raw.casefold(), [])
        if len(exact) == 1:
            return exact[0], "ตรงชื่อ"
        if len(exact) > 1:
            return None, f"ซ้ำ {len(exact)} ไฟล์"

        raw_stem = Path(raw).stem.casefold()
        stem_matches: list[Path] = []
        for paths in self.video_index.values():
            for path in paths:
                if path.stem.casefold() == raw_stem:
                    stem_matches.append(path)

        if len(stem_matches) == 1:
            return stem_matches[0], "ตรงชื่อฐาน"
        if len(stem_matches) > 1:
            return None, f"ชื่อฐานซ้ำ {len(stem_matches)} ไฟล์"
        return None, "ไม่พบ"

    def match_all_sources(self) -> None:
        self.plan_table.blockSignals(True)
        for row in range(self.plan_table.rowCount()):
            raw_item = self.plan_table.item(row, COL_RAW)
            if not raw_item:
                continue
            source, match_text = self.match_source(raw_item.text())
            source_item = self.plan_table.item(row, COL_SOURCE)
            match_item = self.plan_table.item(row, COL_MATCH)
            if source_item:
                source_item.setText(str(source) if source else "")
                source_item.setData(Qt.UserRole, str(source) if source else None)
            if match_item:
                match_item.setText(match_text)
                match_item.setBackground(QColor("#dcfce7") if source else QColor("#fee2e2"))
            if source:
                self.plan_table.item(row, COL_OUTPUT).setText(sanitize_output_name(source.name))
            self.validate_plan_row(row)
        self.plan_table.blockSignals(False)

    def validate_plan_row(self, row: int) -> bool:
        valid = True
        messages: list[str] = []

        range_item = self.plan_table.item(row, COL_RANGE)
        length_item = self.plan_table.item(row, COL_LENGTH)

        try:
            start_text = self.plan_table.item(row, COL_START).text().strip()
            end_text = self.plan_table.item(row, COL_END).text().strip()
            start = parse_timecode(start_text)
            end = parse_timecode(end_text)
            if end <= start:
                raise ValueError("End ต้องมากกว่า Start")

            # Keep Start/End as the editable source of truth.
            # Range and Duration are display-only and always regenerated.
            if range_item:
                range_item.setText(f"{start_text} → {end_text}")
                range_item.setBackground(QColor("#eff6ff"))
            if length_item:
                length_item.setText(seconds_to_timecode(end - start))
                length_item.setBackground(QColor("#eff6ff"))
        except Exception as exc:
            valid = False
            messages.append(str(exc))
            if range_item:
                range_item.setText("ตรวจเวลา")
                range_item.setBackground(QColor("#fee2e2"))
            if length_item:
                length_item.setText("ผิด")
                length_item.setBackground(QColor("#fee2e2"))

        source_item = self.plan_table.item(row, COL_SOURCE)
        source_path = Path(source_item.text()) if source_item and source_item.text() else None
        if not source_path or not source_path.exists():
            valid = False
            messages.append("ยังไม่พบไฟล์ RAW")

        status_item = self.plan_table.item(row, COL_STATUS)
        if status_item:
            if valid:
                status_item.setText("พร้อม")
                status_item.setBackground(QColor("#dcfce7"))
            else:
                status_item.setText("ตรวจสอบ: " + " / ".join(messages))
                status_item.setBackground(QColor("#fee2e2"))
        return valid

    def on_plan_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() in (COL_RAW, COL_START, COL_END, COL_PRIORITY):
            row = item.row()
            if item.column() == COL_RAW:
                source, match_text = self.match_source(item.text())
                self.plan_table.blockSignals(True)
                self.plan_table.item(row, COL_SOURCE).setText(str(source) if source else "")
                self.plan_table.item(row, COL_MATCH).setText(match_text)
                self.plan_table.item(row, COL_OUTPUT).setText(
                    sanitize_output_name(source.name if source else item.text())
                )
                self.plan_table.blockSignals(False)
            self.validate_plan_row(row)

    def set_all_checks(self, checked: bool) -> None:
        for row in range(self.plan_table.rowCount()):
            item = self.plan_table.item(row, COL_USE)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def select_primary_only(self) -> None:
        for row in range(self.plan_table.rowCount()):
            priority = self.plan_table.item(row, COL_PRIORITY)
            use = self.plan_table.item(row, COL_USE)
            if use:
                is_primary = priority and "PRIMARY" in priority.text().upper()
                use.setCheckState(Qt.Checked if is_primary else Qt.Unchecked)

    def choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ Output")
        if folder:
            self.output_dir = Path(folder)
            self.output_label.setText(str(self.output_dir))

    def open_output_dir(self) -> None:
        if not self.output_dir:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def selected_rows(self) -> list[int]:
        result = []
        for row in range(self.plan_table.rowCount()):
            item = self.plan_table.item(row, COL_USE)
            if item and item.checkState() == Qt.Checked:
                result.append(row)
        return result

    def run_preflight(self, show_success: bool = True) -> bool:
        rows = self.selected_rows()
        if not rows:
            QMessageBox.information(self, APP_NAME, "ยังไม่ได้เลือกคลิปที่จะตัด")
            return False

        invalid: list[str] = []
        for row in rows:
            if not self.validate_plan_row(row):
                raw = self.plan_table.item(row, COL_RAW).text()
                status = self.plan_table.item(row, COL_STATUS).text()
                invalid.append(f"{row + 1}. {raw}: {status}")

        if invalid:
            QMessageBox.warning(
                self,
                "ยังไม่พร้อมตัด",
                "พบข้อมูลที่ต้องแก้ก่อน โปรแกรมยังไม่ตัดไฟล์:\n\n" + "\n".join(invalid[:20]),
            )
            return False

        if self.output_dir is None:
            if self.video_root:
                self.output_dir = self.video_root / "CUT_MP4"
            else:
                QMessageBox.information(self, APP_NAME, "กรุณาเลือกโฟลเดอร์ Output")
                return False
            self.output_label.setText(str(self.output_dir))

        if show_success:
            QMessageBox.information(
                self,
                "ตรวจสอบผ่าน",
                f"พร้อมตัด {len(rows)} คลิป\n\nOutput: {self.output_dir}\n"
                "ยังไม่มีไฟล์ถูกแก้ไขจนกว่าจะกด “ยืนยันแผนตัดและเริ่ม”",
            )
        return True

    def start_cutting(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        if not self.run_preflight(show_success=False):
            return

        rows = self.selected_rows()
        assert self.output_dir is not None

        existing: list[str] = []
        jobs: list[CutJob] = []
        for row in rows:
            source = Path(self.plan_table.item(row, COL_SOURCE).text())
            start = parse_timecode(self.plan_table.item(row, COL_START).text())
            end = parse_timecode(self.plan_table.item(row, COL_END).text())
            output = self.output_dir / self.plan_table.item(row, COL_OUTPUT).text()
            if output.exists():
                existing.append(output.name)
            jobs.append(CutJob(row, source, output, start, end - start))

        if existing:
            answer = QMessageBox.question(
                self,
                "มีไฟล์ Output อยู่แล้ว",
                f"มี {len(existing)} ไฟล์ชื่อซ้ำใน Output\nโปรแกรมจะเขียนทับไฟล์เหล่านี้\n\n"
                + "\n".join(existing[:10])
                + "\n\nดำเนินการต่อหรือไม่?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        answer = QMessageBox.question(
            self,
            "ยืนยันเริ่มตัด",
            f"จะตัด {len(jobs)} คลิปตาม Start/End ที่แสดงอยู่ใน Cut Plan\n"
            f"Output: {self.output_dir}\n\nเริ่มตัดหรือไม่?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.overall.setRange(0, len(jobs))
        self.overall.setValue(0)
        self.thread = QThread(self)
        self.worker = CutWorker(jobs, self.preset_combo.currentText())
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.row_status.connect(self.on_row_status)
        self.worker.row_progress.connect(self.on_row_progress)
        self.worker.overall.connect(self.on_overall)
        self.worker.error.connect(self.on_cut_error)
        self.worker.finished.connect(self.on_cut_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.status.setText(f"กำลังตัด {len(jobs)} คลิป...")
        self.thread.start()

    def stop_cutting(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.status.setText("กำลังหยุด...")

    def set_busy(self, busy: bool) -> None:
        self.cut_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.open_excel_btn.setEnabled(not busy)
        self.video_folder_btn.setEnabled(not busy)
        self.add_video_btn.setEnabled(not busy)
        self.preset_combo.setEnabled(not busy)

    def on_row_status(self, row: int, text: str) -> None:
        item = self.plan_table.item(row, COL_STATUS)
        if item:
            item.setText(text)
            if text == "สำเร็จ":
                item.setBackground(QColor("#dcfce7"))

    def on_row_progress(self, row: int, value: int) -> None:
        bar = self.plan_table.cellWidget(row, COL_PROGRESS)
        if isinstance(bar, QProgressBar):
            bar.setValue(value)

    def on_overall(self, current: int, total: int) -> None:
        self.overall.setMaximum(total)
        self.overall.setValue(current)
        self.status.setText(f"กำลังตัด {current} / {total}")

    def on_cut_error(self, row: int, message: str) -> None:
        raw = self.plan_table.item(row, COL_RAW).text()
        QMessageBox.warning(
            self,
            f"ตัด {raw} ไม่สำเร็จ",
            "FFmpeg ไม่สามารถสร้างคลิปนี้ได้\n\n" + message[-1400:],
        )

    def on_cut_finished(self) -> None:
        self.set_busy(False)
        self.status.setText("ตัดเสร็จแล้ว • เปิดโฟลเดอร์ Output เพื่อตรวจคลิปได้")
        self.worker = None
        self.thread = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.thread and self.thread.isRunning():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "กำลังตัดวิดีโออยู่ ต้องการปิดโปรแกรมหรือไม่?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.No:
                event.ignore()
                return
            self.worker.request_stop()
            self.thread.quit()
            self.thread.wait(2000)
        if self.workbook:
            try:
                self.workbook.close()
            except Exception:
                pass
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
