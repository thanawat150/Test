from __future__ import annotations

import copy
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from project_model import (
    blank_project,
    format_timecode,
    load_default_project,
    load_project_from_excel,
    load_project_json,
    match_project_assets,
    save_project_json,
)
from render_engine import RenderError, preflight, render_project

APP_NAME = "Master Edit Studio"


def editable_item(value, center: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(str(value))
    if center:
        item.setTextAlignment(Qt.AlignCenter)
    return item


def readonly_item(value, center: bool = False) -> QTableWidgetItem:
    item = editable_item(value, center)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def check_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    return item


def as_float(text: str, field: str) -> float:
    try:
        return float(str(text).strip())
    except ValueError as exc:
        raise ValueError(f"{field}: ต้องเป็นตัวเลข") from exc


class RenderWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, project: dict, output_path: str, preview: bool) -> None:
        super().__init__()
        self.project = copy.deepcopy(project)
        self.output_path = output_path
        self.preview = preview
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(self) -> None:
        try:
            result = render_project(
                self.project,
                self.output_path,
                preview=self.preview,
                progress=lambda value, message: self.progress.emit(value, message),
                cancelled=lambda: self.cancelled,
            )
            self.finished.emit(str(result))
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = load_default_project()
        self.thread: QThread | None = None
        self.worker: RenderWorker | None = None
        self.last_render: Path | None = None

        self.setWindowTitle(f"{APP_NAME} 1.2.0")
        self.resize(1500, 860)

        self.guide_label = QLabel("Default: EP01 Master Edit Guide (Latest Synced)")
        self.guide_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.asset_label = QLabel("ยังไม่ได้เลือกโฟลเดอร์ Assets")
        self.asset_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.open_excel_btn = QPushButton("เปิด Excel Guide")
        self.open_excel_btn.clicked.connect(self.open_excel)

        self.reset_default_btn = QPushButton("กลับ Default Guide")
        self.reset_default_btn.clicked.connect(self.reset_default)

        self.clear_btn = QPushButton("เคลียร์หน้า")
        self.clear_btn.clicked.connect(self.clear_workspace)

        self.asset_btn = QPushButton("เลือกโฟลเดอร์ Assets")
        self.asset_btn.setObjectName("primaryButton")
        self.asset_btn.clicked.connect(self.choose_asset_root)

        self.rematch_btn = QPushButton("จับคู่ไฟล์ใหม่")
        self.rematch_btn.clicked.connect(self.rematch_assets)

        self.save_project_btn = QPushButton("Save Project")
        self.save_project_btn.clicked.connect(self.save_project)

        self.load_project_btn = QPushButton("Load Project")
        self.load_project_btn.clicked.connect(self.load_project)

        self.timeline_table = QTableWidget()
        self.voice_table = QTableWidget()
        self.music_table = QTableWidget()
        self.sfx_table = QTableWidget()
        self.track_table = QTableWidget()

        self.width_spin = QSpinBox()
        self.width_spin.setRange(360, 3840)
        self.width_spin.setSingleStep(2)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(640, 3840)
        self.height_spin.setSingleStep(2)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(15, 60)

        self.video_bitrate = QComboBox()
        self.video_bitrate.addItems(["8M", "12M", "16M", "20M"])

        self.audio_bitrate = QComboBox()
        self.audio_bitrate.addItems(["192k", "256k", "320k"])

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([
            "Auto GPU",
            "NVIDIA NVENC",
            "Intel Quick Sync",
            "AMD AMF",
            "CPU x264",
        ])

        self.subtitle_check = QCheckBox("Subtitle จาก VO")
        self.keyword_check = QCheckBox("Keyword Text ตาม Guide")
        self.music_duck_check = QCheckBox("ลด Music เพิ่มเมื่อมี VO")

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("เลือกไฟล์ Output .mp4")

        self.output_btn = QPushButton("เลือก Output")
        self.output_btn.clicked.connect(self.choose_output)

        self.open_output_btn = QPushButton("เปิด Output")
        self.open_output_btn.clicked.connect(self.open_last_output)

        self.preflight_btn = QPushButton("ตรวจสอบ Project")
        self.preflight_btn.clicked.connect(self.show_preflight)

        self.preview_btn = QPushButton("Render Preview 540×960")
        self.preview_btn.clicked.connect(lambda: self.start_render(preview=True))

        self.render_btn = QPushButton("Render Final 1080×1920")
        self.render_btn.setObjectName("primaryButton")
        self.render_btn.clicked.connect(lambda: self.start_render(preview=False))

        self.stop_btn = QPushButton("หยุด Render")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_render)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel("โหลด Default Guide แล้ว • เลือกโฟลเดอร์ Assets เพื่อเริ่ม")

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)

        self.tabs = QTabWidget()

        self._build_ui()
        self._style()
        self.populate_all()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        title_row = QHBoxLayout()

        title = QLabel("Master Timeline")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)

        title_row.addStretch()
        title_row.addWidget(self.open_excel_btn)
        title_row.addWidget(self.reset_default_btn)
        title_row.addWidget(self.clear_btn)
        title_row.addWidget(self.asset_btn)
        title_row.addWidget(self.rematch_btn)
        title_row.addWidget(self.save_project_btn)
        title_row.addWidget(self.load_project_btn)

        root.addLayout(title_row)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Guide:"))
        source_row.addWidget(self.guide_label, 1)
        source_row.addWidget(QLabel("Assets:"))
        source_row.addWidget(self.asset_label, 2)
        root.addLayout(source_row)

        hint = QLabel(
            "แก้เฉพาะค่าที่มีผลกับงานจริง • แถวสีเหลือง = Guide ระบุ Source โดยประมาณ ควร Preview แล้วตรวจ Src In / Src Out"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        headers = [
            "ใช้", "T.Start", "T.End", "Video",
            "Src In", "Src Out", "Crop", "Pan X%", "Original dB",
            "Keyword", "Transition", "Match",
        ]
        self.timeline_table.setColumnCount(len(headers))
        self.timeline_table.setHorizontalHeaderLabels(headers)
        self.timeline_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.timeline_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.timeline_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.timeline_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Stretch)
        root.addWidget(self.timeline_table, 1)

        render_group = QGroupBox("Render")
        render_layout = QVBoxLayout(render_group)

        render_top = QHBoxLayout()
        render_top.addWidget(QLabel("Encoder:"))
        render_top.addWidget(self.encoder_combo)
        render_top.addSpacing(12)
        render_top.addWidget(QLabel("Output:"))
        render_top.addWidget(self.output_edit, 1)
        render_top.addWidget(self.output_btn)
        render_top.addWidget(self.open_output_btn)
        render_layout.addLayout(render_top)

        render_actions = QHBoxLayout()
        render_actions.addWidget(self.preflight_btn)
        render_actions.addStretch()
        render_actions.addWidget(self.stop_btn)
        render_actions.addWidget(self.preview_btn)
        render_actions.addWidget(self.render_btn)
        render_layout.addLayout(render_actions)

        root.addWidget(render_group)
        root.addWidget(self.progress)
        root.addWidget(self.status)

        # Keep Guide audio/render defaults loaded in memory but out of the main UI.
        # These hidden tables are populated from Excel and used by sync_project/render.
        self.log.hide()

        self.setCentralWidget(central)

    def _timeline_tab(self) -> QWidget:
        # Kept only for backward compatibility with older saved code paths.
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.timeline_table)
        return page

    def _audio_tab(self) -> QWidget:
        return QWidget()

    def _track_tab(self) -> QWidget:
        return QWidget()

    def _render_tab(self) -> QWidget:
        return QWidget()

    def _style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #f6f7fb;
                color: #18202b;
                font-size: 13px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #dfe3ea;
                border-radius: 9px;
                margin-top: 12px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QTableWidget, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: white;
                border: 1px solid #d7dce5;
                border-radius: 6px;
            }
            QPushButton {
                background: white;
                border: 1px solid #cfd5df;
                border-radius: 7px;
                padding: 8px 11px;
            }
            QPushButton:hover { background: #eef2f8; }
            QPushButton#primaryButton {
                background: #2563eb;
                color: white;
                border: none;
                font-weight: 700;
                padding: 9px 14px;
            }
            QPushButton#primaryButton:hover { background: #1d4ed8; }
            QPushButton:disabled { color: #9aa3b2; background: #eef0f4; }
            QProgressBar {
                border: 1px solid #d5d9e2;
                border-radius: 6px;
                text-align: center;
                background: white;
                min-height: 18px;
            }
            QProgressBar::chunk { background: #2563eb; border-radius: 5px; }
        """)

    def populate_all(self) -> None:
        self.populate_timeline()
        self.populate_audio()
        self.populate_settings()
        self.asset_label.setText(self.project.get("asset_root") or "ยังไม่ได้เลือกโฟลเดอร์ Assets")

    def populate_timeline(self) -> None:
        self.timeline_table.setRowCount(0)
        for item in self.project.get("timeline", []):
            row = self.timeline_table.rowCount()
            self.timeline_table.insertRow(row)

            values = [
                None,
                f"{float(item.get('timeline_start',0)):.2f}",
                f"{float(item.get('timeline_end',0)):.2f}",
                item.get("file", ""),
                f"{float(item.get('source_in',0)):.2f}",
                f"{float(item.get('source_out',0)):.2f}",
                item.get("crop_mode", "Fill 9:16"),
                str(item.get("pan_x", 50)),
                f"{float(item.get('original_db',-20)):.1f}",
                item.get("text", ""),
                item.get("transition", ""),
                item.get("match_status", "ยังไม่จับคู่"),
            ]

            self.timeline_table.setItem(row, 0, check_item(bool(item.get("enabled", True))))
            for col in range(1, len(values)):
                qitem = readonly_item(values[col]) if col == 11 else editable_item(values[col])
                self.timeline_table.setItem(row, col, qitem)

            if item.get("review", False):
                for col in range(self.timeline_table.columnCount()):
                    cell = self.timeline_table.item(row, col)
                    if cell:
                        cell.setBackground(QColor("#fef3c7"))
                        cell.setToolTip(
                            "Guide ระบุช่วง Source แบบประมาณ กรุณา Preview และตรวจ Src In/Out"
                        )

            match = self.timeline_table.item(row, 11)
            if item.get("match_status") in {"ตรงชื่อ", "ตรงชื่อฐาน"}:
                match.setBackground(QColor("#dcfce7"))
            elif item.get("match_status"):
                match.setBackground(QColor("#fee2e2"))

    def populate_audio(self) -> None:
        self.voice_table.setRowCount(0)
        for item in self.project.get("voices", []):
            row = self.voice_table.rowCount()
            self.voice_table.insertRow(row)
            self.voice_table.setItem(row, 0, check_item(bool(item.get("enabled", True))))
            vals = [
                item.get("file", ""),
                f"{float(item.get('start',0)):.2f}",
                f"{float(item.get('end',0)):.2f}",
                f"{float(item.get('gain_db',0)):.1f}",
                item.get("transcript", ""),
                item.get("match_status", "ยังไม่จับคู่"),
            ]
            for col, value in enumerate(vals, start=1):
                self.voice_table.setItem(
                    row, col, readonly_item(value) if col == 6 else editable_item(value)
                )

        self.music_table.setRowCount(0)
        for item in self.project.get("music", []):
            row = self.music_table.rowCount()
            self.music_table.insertRow(row)
            self.music_table.setItem(row, 0, check_item(bool(item.get("enabled", True))))
            vals = [
                item.get("file", ""),
                f"{float(item.get('start',0)):.2f}",
                f"{float(item.get('end',0)):.2f}",
                f"{float(item.get('gain_db',-24)):.1f}",
                "Yes" if item.get("duck_under_vo", True) else "No",
                item.get("match_status", "ยังไม่จับคู่"),
            ]
            for col, value in enumerate(vals, start=1):
                self.music_table.setItem(
                    row, col, readonly_item(value) if col == 6 else editable_item(value)
                )

        self.sfx_table.setRowCount(0)
        for item in self.project.get("sfx", []):
            row = self.sfx_table.rowCount()
            self.sfx_table.insertRow(row)
            self.sfx_table.setItem(row, 0, check_item(bool(item.get("enabled", False))))
            vals = [
                item.get("file", ""),
                f"{float(item.get('start',0)):.2f}",
                f"{float(item.get('gain_db',-18)):.1f}",
                item.get("match_status", "ยังไม่จับคู่"),
            ]
            for col, value in enumerate(vals, start=1):
                self.sfx_table.setItem(
                    row, col, readonly_item(value) if col == 4 else editable_item(value)
                )

    def populate_tracks(self) -> None:
        raw = self.project.get("raw_guide", {})
        headers = raw.get("track_headers", [])
        rows = raw.get("track_setup", [])

        self.track_table.clear()
        self.track_table.setColumnCount(len(headers))
        self.track_table.setHorizontalHeaderLabels(headers)
        self.track_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c in range(len(headers)):
                value = row[c] if c < len(row) else ""
                self.track_table.setItem(r, c, readonly_item(value))
        self.track_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        if len(headers) > 5:
            self.track_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

    def populate_settings(self) -> None:
        settings = self.project.get("settings", {})
        self.width_spin.setValue(int(settings.get("width", 1080)))
        self.height_spin.setValue(int(settings.get("height", 1920)))
        self.fps_spin.setValue(int(settings.get("fps", 30)))
        self.video_bitrate.setCurrentText(str(settings.get("video_bitrate", "16M")))
        self.audio_bitrate.setCurrentText(str(settings.get("audio_bitrate", "256k")))
        self.encoder_combo.setCurrentText(str(settings.get("encoder_mode", "Auto GPU")))
        self.subtitle_check.setChecked(bool(settings.get("subtitle_enabled", True)))
        self.keyword_check.setChecked(bool(settings.get("keyword_enabled", True)))
        self.music_duck_check.setChecked(bool(settings.get("music_ducking", True)))
        self.output_edit.setText(self.project.get("output_path", ""))

    def sync_project(self) -> None:
        timeline = self.project.get("timeline", [])
        if self.timeline_table.rowCount() != len(timeline):
            raise ValueError("จำนวน Timeline row ไม่ตรงกับ Project")

        for row, item in enumerate(timeline):
            item["enabled"] = self.timeline_table.item(row, 0).checkState() == Qt.Checked
            item["timeline_start"] = as_float(self.timeline_table.item(row, 1).text(), f"Timeline {row+1} Start")
            item["timeline_end"] = as_float(self.timeline_table.item(row, 2).text(), f"Timeline {row+1} End")
            item["file"] = self.timeline_table.item(row, 3).text().strip()
            item["source_in"] = as_float(self.timeline_table.item(row, 4).text(), f"Timeline {row+1} Src In")
            item["source_out"] = as_float(self.timeline_table.item(row, 5).text(), f"Timeline {row+1} Src Out")
            item["crop_mode"] = self.timeline_table.item(row, 6).text().strip() or "Fill 9:16"
            item["pan_x"] = max(0, min(100, int(as_float(self.timeline_table.item(row, 7).text(), f"Timeline {row+1} Pan X"))))
            item["original_db"] = as_float(self.timeline_table.item(row, 8).text(), f"Timeline {row+1} Original dB")
            item["text"] = self.timeline_table.item(row, 9).text().strip()
            item["transition"] = self.timeline_table.item(row, 10).text().strip()

        voices = self.project.get("voices", [])
        for row, item in enumerate(voices):
            item["enabled"] = self.voice_table.item(row, 0).checkState() == Qt.Checked
            item["file"] = self.voice_table.item(row, 1).text().strip()
            item["start"] = as_float(self.voice_table.item(row, 2).text(), f"VO {row+1} Start")
            item["end"] = as_float(self.voice_table.item(row, 3).text(), f"VO {row+1} End")
            item["gain_db"] = as_float(self.voice_table.item(row, 4).text(), f"VO {row+1} Gain")
            item["transcript"] = self.voice_table.item(row, 5).text().strip()

        music = self.project.get("music", [])
        for row, item in enumerate(music):
            item["enabled"] = self.music_table.item(row, 0).checkState() == Qt.Checked
            item["file"] = self.music_table.item(row, 1).text().strip()
            item["start"] = as_float(self.music_table.item(row, 2).text(), "Music Start")
            item["end"] = as_float(self.music_table.item(row, 3).text(), "Music End")
            item["gain_db"] = as_float(self.music_table.item(row, 4).text(), "Music Gain")
            item["duck_under_vo"] = self.music_table.item(row, 5).text().strip().lower() not in {"no", "false", "0", "ไม่"}

        sfx = self.project.get("sfx", [])
        for row, item in enumerate(sfx):
            item["enabled"] = self.sfx_table.item(row, 0).checkState() == Qt.Checked
            item["file"] = self.sfx_table.item(row, 1).text().strip()
            item["start"] = as_float(self.sfx_table.item(row, 2).text(), f"SFX {row+1} Start")
            item["gain_db"] = as_float(self.sfx_table.item(row, 3).text(), f"SFX {row+1} Gain")

        settings = self.project.setdefault("settings", {})
        settings["width"] = self.width_spin.value()
        settings["height"] = self.height_spin.value()
        settings["fps"] = self.fps_spin.value()
        settings["video_bitrate"] = self.video_bitrate.currentText()
        settings["audio_bitrate"] = self.audio_bitrate.currentText()
        settings["encoder_mode"] = self.encoder_combo.currentText()
        settings["subtitle_enabled"] = self.subtitle_check.isChecked()
        settings["keyword_enabled"] = self.keyword_check.isChecked()
        settings["music_ducking"] = self.music_duck_check.isChecked()

        self.project["output_path"] = self.output_edit.text().strip()

    def open_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "เปิด Master Edit Guide Excel",
            "",
            "Excel (*.xlsx *.xls *.xlsb *.ods);;All Files (*.*)",
        )
        if not path:
            return
        try:
            old_root = self.project.get("asset_root", "")
            self.project = load_project_from_excel(path)
            self.guide_label.setText(path)
            if old_root:
                match_project_assets(self.project, old_root)
            self.populate_all()
            self.log_message(f"โหลด Excel: {path}")
            self.status.setText("โหลด Excel Guide แล้ว • ค่าในตารางแก้ได้ก่อน Render")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"อ่าน Excel ไม่สำเร็จ\n\n{exc}")

    def reset_default(self) -> None:
        old_root = self.project.get("asset_root", "")
        self.project = load_default_project()
        if old_root:
            match_project_assets(self.project, old_root)
        self.guide_label.setText("Default: EP01 Master Edit Guide (Latest Synced)")
        self.populate_all()
        self.status.setText("กลับ Default Guide ล่าสุดแล้ว")

    def clear_workspace(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self,
                APP_NAME,
                "กำลัง Render อยู่ กรุณาหยุดหรือรอให้เสร็จก่อนเคลียร์หน้า",
            )
            return

        answer = QMessageBox.question(
            self,
            "เคลียร์หน้า",
            "จะล้าง Timeline / VO / Music / SFX / Asset Root / Output ทั้งหมด\n"
            "ไฟล์ต้นฉบับในเครื่องจะไม่ถูกลบ\n\n"
            "ต้องการเคลียร์หน้าใช่หรือไม่?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.project = blank_project()
        self.last_render = None
        self.guide_label.setText("Blank Project")
        self.asset_label.setText("ยังไม่ได้เลือกโฟลเดอร์ Assets")
        self.progress.setValue(0)
        self.log.clear()
        self.populate_all()
        self.status.setText(
            "เคลียร์หน้าแล้ว • เปิด Excel Guide หรือกดกลับ Default Guide เพื่อเริ่มใหม่"
        )

    def choose_asset_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ที่มี 01_VIDEO / 02_VOICE_OVER / MUSIC / SFX")
        if not folder:
            return
        try:
            self.sync_project()
            problems = match_project_assets(self.project, folder)
            self.asset_label.setText(folder)
            if not self.output_edit.text().strip():
                default_output = Path(folder) / "EXPORT" / "EP01_MASTER_EDIT.mp4"
                self.output_edit.setText(str(default_output))
                self.project["output_path"] = str(default_output)
            self.populate_timeline()
            self.populate_audio()
            self.log_message(f"Scan Assets: {folder}")
            if problems:
                self.status.setText(f"จับคู่แล้ว แต่มี {len(problems)} รายการที่ต้องตรวจ")
                QMessageBox.warning(
                    self,
                    "พบ Asset ที่ต้องตรวจ",
                    "\n".join(problems[:30]),
                )
            else:
                self.status.setText("จับคู่ Assets ครบแล้ว • พร้อมตรวจ Project")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def rematch_assets(self) -> None:
        root = self.project.get("asset_root", "")
        if not root:
            self.choose_asset_root()
            return
        try:
            self.sync_project()
            problems = match_project_assets(self.project, root)
            self.populate_timeline()
            self.populate_audio()
            self.status.setText(
                "จับคู่ Assets ใหม่แล้ว" if not problems else f"ยังมี {len(problems)} รายการไม่พร้อม"
            )
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def save_project(self) -> None:
        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "EP01_Master_Edit_Project.json", "JSON (*.json)"
        )
        if path:
            save_project_json(self.project, path)
            self.status.setText(f"บันทึก Project แล้ว: {path}")

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.project = load_project_json(path)
            self.populate_all()
            self.guide_label.setText(f"Project: {path}")
            self.status.setText("โหลด Project แล้ว")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def choose_output(self) -> None:
        current = self.output_edit.text().strip() or "EP01_MASTER_EDIT.mp4"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "เลือก Output MP4",
            current,
            "MP4 Video (*.mp4)",
        )
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_edit.setText(path)

    def show_preflight(self) -> bool:
        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, "ข้อมูลไม่ถูกต้อง", str(exc))
            return False

        issues = preflight(self.project)
        if issues:
            QMessageBox.warning(
                self,
                "Preflight พบปัญหา",
                "\n".join(f"• {x}" for x in issues[:35]),
            )
            self.status.setText(f"Preflight: พบ {len(issues)} ปัญหา")
            return False

        QMessageBox.information(
            self,
            "Preflight ผ่าน",
            "Asset และ Timeline ที่เปิดใช้งานพร้อม Render\n\n"
            "หมายเหตุ: แถวที่ Guide ระบุว่า 'เลือกช่วงดีที่สุด' ยังควร Preview และปรับ Source In/Out ตามสายตา",
        )
        self.status.setText("Preflight ผ่าน")
        return True

    def start_render(self, preview: bool) -> None:
        if self.thread and self.thread.isRunning():
            return

        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, "ข้อมูลไม่ถูกต้อง", str(exc))
            return

        issues = preflight(self.project)
        if issues:
            QMessageBox.warning(
                self,
                "ยัง Render ไม่ได้",
                "\n".join(f"• {x}" for x in issues[:35]),
            )
            return

        output_text = self.output_edit.text().strip()
        if not output_text:
            self.choose_output()
            output_text = self.output_edit.text().strip()
            if not output_text:
                return

        output = Path(output_text)
        if preview:
            output = output.with_name(output.stem + "_PREVIEW.mp4")

        self.project["output_path"] = str(output if not preview else Path(output_text))
        self.progress.setValue(0)
        self.log.clear()

        self.thread = QThread(self)
        self.worker = RenderWorker(self.project, str(output), preview)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_render_progress)
        self.worker.finished.connect(self.on_render_finished)
        self.worker.error.connect(self.on_render_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_render_busy(True)
        self.status.setText("กำลัง Render Preview..." if preview else "กำลัง Render Final...")
        self.thread.start()

    def stop_render(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.status.setText("กำลังหยุด Render...")

    def set_render_busy(self, busy: bool) -> None:
        self.render_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)
        self.preflight_btn.setEnabled(not busy)
        self.open_excel_btn.setEnabled(not busy)
        self.asset_btn.setEnabled(not busy)
        self.encoder_combo.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def on_render_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, value)))
        self.status.setText(message)
        self.log_message(f"{value:3d}%  {message}")

    def on_render_finished(self, path: str) -> None:
        self.last_render = Path(path)
        self.set_render_busy(False)
        self.progress.setValue(100)
        self.status.setText(f"Render เสร็จแล้ว: {path}")
        self.log_message(f"DONE: {path}")
        QMessageBox.information(self, APP_NAME, f"Render เสร็จแล้ว\n\n{path}")
        self.worker = None
        self.thread = None

    def on_render_error(self, message: str) -> None:
        self.set_render_busy(False)
        self.status.setText("Render ไม่สำเร็จ")
        self.log_message("ERROR: " + message)
        QMessageBox.critical(self, APP_NAME, message)
        self.worker = None
        self.thread = None

    def open_last_output(self) -> None:
        path = self.last_render
        if not path:
            text = self.output_edit.text().strip()
            path = Path(text) if text else None
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif path:
            path.parent.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def log_message(self, text: str) -> None:
        self.log.append(text)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.thread and self.thread.isRunning():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "กำลัง Render อยู่ ต้องการปิดโปรแกรมหรือไม่?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.No:
                event.ignore()
                return
            self.worker.cancel()
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
