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
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autocut_engine import build_autocut_project, scan_videos
from project_model import blank_project, load_project_json, save_project_json
from render_engine import preflight, render_project

APP_NAME = "AutoCut Studio"
APP_VERSION = "3.0.0"

COL_USE = 0
COL_KIND = 1
COL_TSTART = 2
COL_TEND = 3
COL_VIDEO = 4
COL_SIN = 5
COL_SOUT = 6
COL_DURATION = 7
COL_AUDIO = 8
COL_MATCH = 9


def _item(value: object, editable: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(str(value))
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def _check_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    return item


def _float(text: str, label: str) -> float:
    try:
        return float(str(text).strip())
    except ValueError as exc:
        raise ValueError(f"{label} ต้องเป็นตัวเลข") from exc


class AutoCutWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        root: str,
        mode: str,
        target_seconds: float | None,
        remove_silence: bool,
    ) -> None:
        super().__init__()
        self.root = root
        self.mode = mode
        self.target_seconds = target_seconds
        self.remove_silence = remove_silence

    def run(self) -> None:
        try:
            project = build_autocut_project(
                self.root,
                mode=self.mode,
                target_seconds=self.target_seconds,
                remove_silence=self.remove_silence,
                progress=lambda value, message: self.progress.emit(value, message),
            )
            self.finished.emit(project)
        except Exception as exc:
            self.error.emit(str(exc))


class RenderWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, project: dict, output: str, preview: bool) -> None:
        super().__init__()
        self.project = copy.deepcopy(project)
        self.output = output
        self.preview = preview
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(self) -> None:
        try:
            result = render_project(
                self.project,
                self.output,
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

        self.project = self._blank_project()
        self.thread: QThread | None = None
        self.worker: QObject | None = None
        self.last_render: Path | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1480, 880)

        self.media_label = QLabel("ยังไม่ได้เลือกโฟลเดอร์วิดีโอ")
        self.media_count_label = QLabel("0 คลิป")
        self.duration_label = QLabel("Timeline 0.0 วินาที")

        self.media_btn = QPushButton("เลือกโฟลเดอร์วิดีโอ")
        self.media_btn.setObjectName("primaryButton")
        self.media_btn.clicked.connect(self.choose_media_folder)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["ผสม", "พูดหน้ากล้อง", "B-roll"])

        self.target_combo = QComboBox()
        self.target_combo.addItems(["Auto", "30 วินาที", "60 วินาที", "90 วินาที"])
        self.target_combo.setCurrentText("60 วินาที")

        self.silence_check = QCheckBox("ตัดช่วงเงียบ")
        self.silence_check.setChecked(True)

        self.auto_btn = QPushButton("AUTO CUT")
        self.auto_btn.setObjectName("successButton")
        self.auto_btn.clicked.connect(self.start_auto_cut)

        self.clear_btn = QPushButton("เคลียร์หน้า")
        self.clear_btn.clicked.connect(self.clear_workspace)

        self.save_btn = QPushButton("Save Project")
        self.save_btn.clicked.connect(self.save_project)

        self.load_btn = QPushButton("Load Project")
        self.load_btn.clicked.connect(self.load_project)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "ใช้",
                "Type",
                "T.Start",
                "T.End",
                "Video",
                "Src In",
                "Src Out",
                "Length",
                "Original dB",
                "Status",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_VIDEO, QHeaderView.Stretch)

        self.open_source_btn = QPushButton("เปิดคลิป")
        self.open_source_btn.clicked.connect(self.open_selected_source)

        self.replace_btn = QPushButton("เปลี่ยนคลิป")
        self.replace_btn.clicked.connect(self.replace_selected_clip)

        self.delete_btn = QPushButton("เอาแถวนี้ออก")
        self.delete_btn.clicked.connect(self.disable_selected_row)

        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(
            ["Auto GPU", "NVIDIA NVENC", "Intel Quick Sync", "AMD AMF", "CPU x264"]
        )

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output .mp4")
        self.output_btn = QPushButton("เลือก Output")
        self.output_btn.clicked.connect(self.choose_output)

        self.check_btn = QPushButton("ตรวจสอบ")
        self.check_btn.clicked.connect(self.run_preflight)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(lambda: self.start_render(True))

        self.export_btn = QPushButton("Export MP4")
        self.export_btn.setObjectName("primaryButton")
        self.export_btn.clicked.connect(lambda: self.start_render(False))

        self.stop_btn = QPushButton("หยุด")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_work)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel(
            "เลือกโฟลเดอร์วิดีโอ → เลือกโหมด → AUTO CUT → Preview → Export"
        )

        self._build_ui()
        self._style()
        self.populate()

    @staticmethod
    def _blank_project() -> dict:
        project = blank_project()
        project["version"] = "3.0"
        project["project_type"] = "autocut"
        project["media"] = []
        project["autocut"] = {}
        project["settings"]["subtitle_enabled"] = False
        project["settings"]["keyword_enabled"] = False
        project["settings"]["music_ducking"] = False
        return project

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)

        top = QHBoxLayout()
        title = QLabel("AutoCut Studio")
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.media_btn)
        top.addWidget(self.auto_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.load_btn)
        root.addLayout(top)

        auto_group = QGroupBox("Auto Cut")
        auto_layout = QVBoxLayout(auto_group)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Media:"))
        source_row.addWidget(self.media_label, 1)
        source_row.addWidget(self.media_count_label)
        source_row.addSpacing(12)
        source_row.addWidget(self.duration_label)
        auto_layout.addLayout(source_row)

        option_row = QHBoxLayout()
        option_row.addWidget(QLabel("โหมด:"))
        option_row.addWidget(self.mode_combo)
        option_row.addSpacing(10)
        option_row.addWidget(QLabel("ความยาวเป้าหมาย:"))
        option_row.addWidget(self.target_combo)
        option_row.addSpacing(10)
        option_row.addWidget(self.silence_check)
        option_row.addStretch()
        option_row.addWidget(self.auto_btn)
        auto_layout.addLayout(option_row)

        root.addWidget(auto_group)

        timeline_group = QGroupBox("Auto Timeline")
        timeline_layout = QVBoxLayout(timeline_group)

        hint = QLabel(
            "AUTO CUT เป็น Rough Cut อัตโนมัติ • ถ้ายังไม่ถูกใจ แก้ Src In / Src Out หรือเปลี่ยนคลิปได้ก่อน Export"
        )
        hint.setWordWrap(True)
        timeline_layout.addWidget(hint)
        timeline_layout.addWidget(self.table, 1)

        edit_row = QHBoxLayout()
        edit_row.addWidget(self.open_source_btn)
        edit_row.addWidget(self.replace_btn)
        edit_row.addWidget(self.delete_btn)
        edit_row.addStretch()
        timeline_layout.addLayout(edit_row)

        root.addWidget(timeline_group, 1)

        export_group = QGroupBox("Preview / Export")
        export_layout = QVBoxLayout(export_group)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Encoder:"))
        output_row.addWidget(self.encoder_combo)
        output_row.addSpacing(12)
        output_row.addWidget(QLabel("Output:"))
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_btn)
        export_layout.addLayout(output_row)

        action_row = QHBoxLayout()
        action_row.addWidget(self.check_btn)
        action_row.addStretch()
        action_row.addWidget(self.stop_btn)
        action_row.addWidget(self.preview_btn)
        action_row.addWidget(self.export_btn)
        export_layout.addLayout(action_row)

        root.addWidget(export_group)
        root.addWidget(self.progress)
        root.addWidget(self.status)

        self.setCentralWidget(central)

    def _style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7fb;
                color: #172033;
                font-size: 13px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #dfe3ea;
                border-radius: 10px;
                margin-top: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTableWidget, QLineEdit, QComboBox {
                background: white;
                border: 1px solid #d6dce7;
                border-radius: 6px;
            }
            QPushButton {
                background: white;
                border: 1px solid #cdd4df;
                border-radius: 7px;
                padding: 8px 11px;
            }
            QPushButton:hover { background: #eef2f8; }
            QPushButton#primaryButton {
                background: #2563eb;
                color: white;
                border: none;
                font-weight: 700;
            }
            QPushButton#successButton {
                background: #16a34a;
                color: white;
                border: none;
                font-weight: 800;
                padding: 10px 18px;
            }
            QPushButton:disabled {
                background: #eef0f4;
                color: #98a1b2;
            }
            QProgressBar {
                background: white;
                border: 1px solid #d5d9e2;
                border-radius: 6px;
                text-align: center;
                min-height: 18px;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 5px;
            }
            """
        )

    def choose_media_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์วิดีโอ")
        if not folder:
            return

        videos = scan_videos(folder)
        self.project["asset_root"] = folder
        self.project["timeline"] = []
        self.project["media"] = []
        self.media_label.setText(folder)
        self.media_count_label.setText(f"{len(videos)} คลิป")
        self.progress.setValue(0)
        self.populate()

        if not videos:
            QMessageBox.warning(self, APP_NAME, "ไม่พบไฟล์วิดีโอในโฟลเดอร์นี้")
            self.status.setText("ไม่พบวิดีโอ")
            return

        if not self.output_edit.text().strip():
            output = Path(folder) / "EXPORT" / "AUTO_CUT.mp4"
            self.output_edit.setText(str(output))
            self.project["output_path"] = str(output)

        self.status.setText("พร้อมวิเคราะห์ • กด AUTO CUT")

    def target_seconds(self) -> float | None:
        value = self.target_combo.currentText()
        if value == "Auto":
            return None
        return float(value.split()[0])

    def start_auto_cut(self) -> None:
        if self.thread and self.thread.isRunning():
            return

        root = self.project.get("asset_root", "")
        if not root:
            self.choose_media_folder()
            root = self.project.get("asset_root", "")
            if not root:
                return

        self.thread = QThread(self)
        worker = AutoCutWorker(
            root,
            self.mode_combo.currentText(),
            self.target_seconds(),
            self.silence_check.isChecked(),
        )
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(self.on_autocut_finished)
        worker.error.connect(self.on_error)
        worker.finished.connect(self.thread.quit)
        worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.progress.setValue(0)
        self.status.setText("กำลังวิเคราะห์วิดีโอ...")
        self.thread.start()

    def on_autocut_finished(self, project: dict) -> None:
        old_output = self.output_edit.text().strip()
        project["settings"]["encoder_mode"] = self.encoder_combo.currentText()
        project["output_path"] = old_output
        self.project = project
        self.populate()
        self.progress.setValue(100)
        self.status.setText(
            f"AUTO CUT เสร็จแล้ว • {len(project.get('timeline', []))} ช่วง • Preview เพื่อตรวจ"
        )
        self.set_busy(False)
        self.worker = None
        self.thread = None

    def populate(self) -> None:
        self.table.setRowCount(0)

        for item in self.project.get("timeline", []):
            row = self.table.rowCount()
            self.table.insertRow(row)

            start = float(item.get("timeline_start", 0))
            end = float(item.get("timeline_end", 0))
            src_in = float(item.get("source_in", 0))
            src_out = float(item.get("source_out", 0))

            self.table.setItem(row, COL_USE, _check_item(bool(item.get("enabled", True))))
            self.table.setItem(
                row, COL_KIND, _item(item.get("part", item.get("beat", "AUTO")), False)
            )
            self.table.setItem(row, COL_TSTART, _item(f"{start:.2f}", False))
            self.table.setItem(row, COL_TEND, _item(f"{end:.2f}", False))
            self.table.setItem(row, COL_VIDEO, _item(item.get("file", ""), False))
            self.table.setItem(row, COL_SIN, _item(f"{src_in:.2f}"))
            self.table.setItem(row, COL_SOUT, _item(f"{src_out:.2f}"))
            self.table.setItem(
                row, COL_DURATION, _item(f"{max(0.0, src_out-src_in):.2f}s", False)
            )
            self.table.setItem(
                row, COL_AUDIO, _item(f"{float(item.get('original_db', 0)):.1f}")
            )
            self.table.setItem(
                row, COL_MATCH, _item(item.get("match_status", "AUTO"), False)
            )

            if item.get("review", False):
                for col in range(self.table.columnCount()):
                    cell = self.table.item(row, col)
                    if cell:
                        cell.setBackground(QColor("#fff7d6"))

            status_item = self.table.item(row, COL_MATCH)
            if item.get("asset_path"):
                status_item.setBackground(QColor("#dcfce7"))

        root = self.project.get("asset_root", "")
        if root:
            self.media_label.setText(root)
            self.media_count_label.setText(f"{len(scan_videos(root))} คลิป")
        else:
            self.media_label.setText("ยังไม่ได้เลือกโฟลเดอร์วิดีโอ")
            self.media_count_label.setText("0 คลิป")

        timeline = [
            item for item in self.project.get("timeline", [])
            if item.get("enabled", True)
        ]
        duration = max(
            [float(x.get("timeline_end", 0)) for x in timeline] or [0.0]
        )
        self.duration_label.setText(f"Timeline {duration:.1f} วินาที")

        settings = self.project.get("settings", {})
        self.encoder_combo.setCurrentText(settings.get("encoder_mode", "Auto GPU"))
        self.output_edit.setText(self.project.get("output_path", ""))

        autocut = self.project.get("autocut", {})
        if autocut.get("mode") in {"ผสม", "พูดหน้ากล้อง", "B-roll"}:
            self.mode_combo.setCurrentText(autocut["mode"])
        target = autocut.get("target_seconds")
        if target in {30.0, 60.0, 90.0}:
            self.target_combo.setCurrentText(f"{int(target)} วินาที")
        elif target is None and autocut:
            self.target_combo.setCurrentText("Auto")
        if "remove_silence" in autocut:
            self.silence_check.setChecked(bool(autocut["remove_silence"]))

    def sync_project(self) -> None:
        timeline = self.project.get("timeline", [])
        if len(timeline) != self.table.rowCount():
            raise ValueError("Timeline ในหน้าจอไม่ตรงกับ Project")

        cursor = 0.0
        for row, item in enumerate(timeline):
            item["enabled"] = self.table.item(row, COL_USE).checkState() == Qt.Checked
            item["source_in"] = _float(
                self.table.item(row, COL_SIN).text(), f"แถว {row+1} Src In"
            )
            item["source_out"] = _float(
                self.table.item(row, COL_SOUT).text(), f"แถว {row+1} Src Out"
            )
            item["original_db"] = _float(
                self.table.item(row, COL_AUDIO).text(), f"แถว {row+1} Original dB"
            )
            duration = max(0.05, item["source_out"] - item["source_in"])
            item["timeline_start"] = cursor
            item["timeline_end"] = cursor + duration
            cursor += duration

        settings = self.project.setdefault("settings", {})
        settings["encoder_mode"] = self.encoder_combo.currentText()
        self.project["output_path"] = self.output_edit.text().strip()
        self.project["autocut"] = {
            "mode": self.mode_combo.currentText(),
            "target_seconds": self.target_seconds(),
            "remove_silence": self.silence_check.isChecked(),
        }

    def selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def open_selected_source(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "เลือกแถวใน Timeline ก่อน")
            return

        path = Path(self.project["timeline"][row].get("asset_path", ""))
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, APP_NAME, "ไม่พบไฟล์ต้นฉบับ")

    def replace_selected_clip(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "เลือกแถวใน Timeline ก่อน")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกวิดีโอแทน",
            self.project.get("asset_root", ""),
            "Video (*.mov *.MOV *.mp4 *.MP4 *.m4v *.avi *.mkv *.mts *.m2ts *.webm)",
        )
        if not path:
            return

        item = self.project["timeline"][row]
        item["file"] = Path(path).name
        item["asset_path"] = path
        item["match_status"] = "MANUAL"
        item["review"] = True
        self.populate()
        self.table.selectRow(row)

    def disable_selected_row(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "เลือกแถวก่อน")
            return
        self.project["timeline"][row]["enabled"] = False
        self.populate()
        self.table.selectRow(row)
        self.status.setText("ปิดแถวแล้ว • ตอน Export จะข้ามช่วงนี้")

    def choose_output(self) -> None:
        current = self.output_edit.text().strip() or "AUTO_CUT.mp4"
        path, _ = QFileDialog.getSaveFileName(
            self, "เลือก Output", current, "MP4 Video (*.mp4)"
        )
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_edit.setText(path)

    def run_preflight(self, notify: bool = True) -> bool:
        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return False

        issues = preflight(self.project)
        if issues:
            QMessageBox.warning(
                self,
                "ยังไม่พร้อม Export",
                "\n".join(f"• {issue}" for issue in issues[:30]),
            )
            return False

        if notify:
            QMessageBox.information(
                self,
                "พร้อม",
                "Timeline พร้อมแล้ว\n\nแนะนำให้ Preview ก่อน Export Final",
            )
        return True

    def start_render(self, preview: bool) -> None:
        if self.thread and self.thread.isRunning():
            return
        if not self.project.get("timeline"):
            QMessageBox.information(self, APP_NAME, "กด AUTO CUT ก่อน")
            return
        if not self.run_preflight(False):
            return

        output = self.output_edit.text().strip()
        if not output:
            self.choose_output()
            output = self.output_edit.text().strip()
            if not output:
                return

        target = Path(output)
        if preview:
            target = target.with_name(target.stem + "_PREVIEW.mp4")

        self.thread = QThread(self)
        worker = RenderWorker(self.project, str(target), preview)
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(self.on_render_finished)
        worker.error.connect(self.on_error)
        worker.finished.connect(self.thread.quit)
        worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.progress.setValue(0)
        self.thread.start()

    def stop_work(self) -> None:
        if isinstance(self.worker, RenderWorker):
            self.worker.cancel()
            self.status.setText("กำลังหยุด Render...")
        else:
            self.status.setText("Auto Cut กำลังวิเคราะห์ • กรุณารอให้ขั้นนี้จบ")

    def set_busy(self, busy: bool) -> None:
        for button in (
            self.media_btn,
            self.auto_btn,
            self.clear_btn,
            self.preview_btn,
            self.export_btn,
            self.load_btn,
        ):
            button.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.encoder_combo.setEnabled(not busy)
        self.mode_combo.setEnabled(not busy)
        self.target_combo.setEnabled(not busy)
        self.silence_check.setEnabled(not busy)

    def on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, value)))
        self.status.setText(message)

    def on_render_finished(self, path: str) -> None:
        self.last_render = Path(path)
        self.progress.setValue(100)
        self.status.setText(f"เสร็จแล้ว: {Path(path).name}")
        self.set_busy(False)
        QMessageBox.information(self, APP_NAME, f"Render เสร็จแล้ว\n\n{path}")
        self.worker = None
        self.thread = None

    def on_error(self, message: str) -> None:
        self.set_busy(False)
        self.status.setText("ทำงานไม่สำเร็จ")
        QMessageBox.critical(self, APP_NAME, message)
        self.worker = None
        self.thread = None

    def clear_workspace(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        answer = QMessageBox.question(
            self,
            "เคลียร์หน้า",
            "ล้าง Media / Auto Timeline / Output จากหน้าจอหรือไม่?\n"
            "ไฟล์ต้นฉบับจะไม่ถูกลบ",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.project = self._blank_project()
            self.last_render = None
            self.progress.setValue(0)
            self.output_edit.clear()
            self.populate()
            self.status.setText("หน้าโล่งแล้ว • เลือกโฟลเดอร์วิดีโอเพื่อเริ่ม")

    def save_project(self) -> None:
        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "AutoCut_Project.json", "JSON (*.json)"
        )
        if path:
            save_project_json(self.project, path)
            self.status.setText(f"บันทึก Project แล้ว: {path}")

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Project", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            self.project = load_project_json(path)
            self.populate()
            self.status.setText("โหลด Project แล้ว")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.thread and self.thread.isRunning():
            if isinstance(self.worker, RenderWorker):
                answer = QMessageBox.question(
                    self,
                    APP_NAME,
                    "กำลัง Render อยู่ ต้องการปิดหรือไม่?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer == QMessageBox.No:
                    event.ignore()
                    return
                self.worker.cancel()
            else:
                QMessageBox.information(
                    self,
                    APP_NAME,
                    "กำลังวิเคราะห์ Auto Cut อยู่ กรุณารอให้จบก่อนปิดโปรแกรม",
                )
                event.ignore()
                return
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
