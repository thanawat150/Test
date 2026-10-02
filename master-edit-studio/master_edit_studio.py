from __future__ import annotations

import copy
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
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
    QComboBox,
)

from content_guide import (
    auto_build,
    coverage,
    is_content_guide,
    load_content_guide,
)
from project_model import (
    blank_project,
    load_default_project,
    load_project_from_excel,
    load_project_json,
    save_project_json,
)
from render_engine import preflight, render_project

APP_NAME = "GuideCut Studio"
APP_VERSION = "2.0.0"

COL_USE = 0
COL_BEAT = 1
COL_TSTART = 2
COL_TEND = 3
COL_VIDEO = 4
COL_SIN = 5
COL_SOUT = 6
COL_VISUAL = 7
COL_KEYWORD = 8
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

        self.project = self._starter_project()
        self.thread: QThread | None = None
        self.worker: RenderWorker | None = None
        self.last_render: Path | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1540, 900)

        self.guide_label = QLabel("ยังไม่ได้เปิด Content Guide")
        self.asset_label = QLabel("ยังไม่ได้เลือก Media")
        self.topic_label = QLabel("-")
        self.hook_label = QLabel("-")
        self.coverage_label = QLabel("Coverage: 0/0")

        self.open_guide_btn = QPushButton("เปิด Guide Excel")
        self.open_guide_btn.setObjectName("primaryButton")
        self.open_guide_btn.clicked.connect(self.open_guide)

        self.media_btn = QPushButton("เลือกโฟลเดอร์ Media")
        self.media_btn.clicked.connect(self.choose_media_folder)

        self.auto_btn = QPushButton("Auto Build")
        self.auto_btn.setObjectName("successButton")
        self.auto_btn.clicked.connect(self.auto_build_project)

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
                "Beat",
                "T.Start",
                "T.End",
                "Video",
                "Src In",
                "Src Out",
                "Visual / Proof",
                "Keyword",
                "Match",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_VIDEO, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_VISUAL, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_KEYWORD, QHeaderView.Stretch)

        self.replace_btn = QPushButton("เปลี่ยนคลิปแถวที่เลือก")
        self.replace_btn.clicked.connect(self.replace_selected_clip)

        self.open_source_btn = QPushButton("เปิดคลิปแถวที่เลือก")
        self.open_source_btn.clicked.connect(self.open_selected_source)

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

        self.render_btn = QPushButton("Export MP4")
        self.render_btn.setObjectName("primaryButton")
        self.render_btn.clicked.connect(lambda: self.start_render(False))

        self.stop_btn = QPushButton("หยุด")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_render)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status = QLabel(
            "เปิด Content Guide → เลือก Media → Auto Build → ปรับ Timeline → Preview / Export"
        )

        self._build_ui()
        self._style()
        self.populate()

    @staticmethod
    def _starter_project() -> dict:
        project = blank_project()
        project["version"] = "2.0"
        project["guide_type"] = "content-guide"
        project["guide_name"] = "Blank"
        project["overview"] = {}
        project["visual_plan"] = []
        project["checklist"] = []
        project["settings"]["encoder_mode"] = "Auto GPU"
        project["settings"]["subtitle_enabled"] = False
        return project

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)

        top = QHBoxLayout()
        title = QLabel("GuideCut Studio")
        font = QFont()
        font.setPointSize(21)
        font.setBold(True)
        title.setFont(font)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.open_guide_btn)
        top.addWidget(self.media_btn)
        top.addWidget(self.auto_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.load_btn)
        root.addLayout(top)

        guide_group = QGroupBox("Guide")
        guide_layout = QVBoxLayout(guide_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Guide:"))
        row1.addWidget(self.guide_label, 2)
        row1.addWidget(QLabel("Media:"))
        row1.addWidget(self.asset_label, 2)
        guide_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Topic:"))
        row2.addWidget(self.topic_label, 2)
        row2.addWidget(QLabel("Hook:"))
        row2.addWidget(self.hook_label, 4)
        row2.addWidget(self.coverage_label, 1)
        guide_layout.addLayout(row2)

        root.addWidget(guide_group)

        timeline_group = QGroupBox("Master Timeline")
        timeline_layout = QVBoxLayout(timeline_group)

        hint = QLabel(
            "Auto Build เป็น Rough Cut เท่านั้น • ปรับ Src In / Src Out และเปลี่ยน Video ได้ก่อน Export"
        )
        hint.setWordWrap(True)
        timeline_layout.addWidget(hint)
        timeline_layout.addWidget(self.table, 1)

        timeline_actions = QHBoxLayout()
        timeline_actions.addWidget(self.replace_btn)
        timeline_actions.addWidget(self.open_source_btn)
        timeline_actions.addStretch()
        timeline_layout.addLayout(timeline_actions)
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
        action_row.addWidget(self.render_btn)
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
                font-weight: 700;
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

    def populate(self) -> None:
        self.table.setRowCount(0)
        for item in self.project.get("timeline", []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, COL_USE, _check_item(bool(item.get("enabled", True))))
            self.table.setItem(
                row,
                COL_BEAT,
                _item(item.get("beat") or item.get("part") or f"Beat {row + 1}", False),
            )
            self.table.setItem(
                row, COL_TSTART, _item(f"{float(item.get('timeline_start', 0)):.2f}")
            )
            self.table.setItem(
                row, COL_TEND, _item(f"{float(item.get('timeline_end', 0)):.2f}")
            )
            self.table.setItem(row, COL_VIDEO, _item(item.get("file", ""), False))
            self.table.setItem(
                row, COL_SIN, _item(f"{float(item.get('source_in', 0)):.2f}")
            )
            self.table.setItem(
                row, COL_SOUT, _item(f"{float(item.get('source_out', 0)):.2f}")
            )
            self.table.setItem(
                row, COL_VISUAL, _item(item.get("visual", item.get("goal", "")), False)
            )
            self.table.setItem(row, COL_KEYWORD, _item(item.get("text", "")))
            self.table.setItem(
                row, COL_MATCH, _item(item.get("match_status", "รอ"), False)
            )

            if item.get("review", False):
                for col in range(self.table.columnCount()):
                    cell = self.table.item(row, col)
                    if cell:
                        cell.setBackground(QColor("#fff7d6"))

            match = self.table.item(row, COL_MATCH)
            if item.get("asset_path"):
                match.setBackground(QColor("#dcfce7"))
            elif match:
                match.setBackground(QColor("#fee2e2"))

        overview = self.project.get("overview", {})
        self.topic_label.setText(overview.get("Topic", self.project.get("guide_name", "-")))
        self.hook_label.setText(overview.get("Recommended Hook", "-"))
        self.guide_label.setText(self.project.get("guide_name", "-"))
        self.asset_label.setText(self.project.get("asset_root", "") or "ยังไม่ได้เลือก")

        settings = self.project.get("settings", {})
        self.encoder_combo.setCurrentText(settings.get("encoder_mode", "Auto GPU"))
        self.output_edit.setText(self.project.get("output_path", ""))
        self.update_coverage()

    def update_coverage(self) -> None:
        data = coverage(self.project)
        beats = []
        for name, ok in data["beats"].items():
            beats.append(f"{'✓' if ok else '○'} {name}")
        self.coverage_label.setText(
            f"Coverage {data['ready']}/{data['total']}  |  " + "  ".join(beats)
        )

    def sync_project(self) -> None:
        timeline = self.project.get("timeline", [])
        if len(timeline) != self.table.rowCount():
            raise ValueError("Timeline ในหน้าจอไม่ตรงกับ Project")

        for row, item in enumerate(timeline):
            item["enabled"] = self.table.item(row, COL_USE).checkState() == Qt.Checked
            item["timeline_start"] = _float(
                self.table.item(row, COL_TSTART).text(), f"แถว {row+1} T.Start"
            )
            item["timeline_end"] = _float(
                self.table.item(row, COL_TEND).text(), f"แถว {row+1} T.End"
            )
            item["source_in"] = _float(
                self.table.item(row, COL_SIN).text(), f"แถว {row+1} Src In"
            )
            item["source_out"] = _float(
                self.table.item(row, COL_SOUT).text(), f"แถว {row+1} Src Out"
            )
            item["text"] = self.table.item(row, COL_KEYWORD).text().strip()

        settings = self.project.setdefault("settings", {})
        settings["encoder_mode"] = self.encoder_combo.currentText()
        self.project["output_path"] = self.output_edit.text().strip()

    def open_guide(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "เปิด Content Guide",
            "",
            "Excel (*.xlsx *.xls *.xlsb *.ods);;All Files (*.*)",
        )
        if not path:
            return

        try:
            if is_content_guide(path):
                project = load_content_guide(path)
            else:
                project = load_project_from_excel(path)
            old_root = self.project.get("asset_root", "")
            self.project = project
            if old_root and self.project.get("guide_type") == "content-guide":
                auto_build(self.project, old_root)
            self.populate()
            self.status.setText("โหลด Guide แล้ว • เลือก Media แล้วกด Auto Build")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"อ่าน Guide ไม่สำเร็จ\n\n{exc}")

    def choose_media_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ Media")
        if not folder:
            return

        self.project["asset_root"] = folder
        self.asset_label.setText(folder)

        if not self.output_edit.text().strip():
            topic = self.project.get("overview", {}).get("Topic", "GuideCut")
            safe = "".join(ch for ch in topic if ch not in '<>:"/\\|?*').strip()
            if not safe or "{{" in safe:
                safe = "GuideCut_Output"
            output = Path(folder) / "EXPORT" / f"{safe}.mp4"
            self.output_edit.setText(str(output))
            self.project["output_path"] = str(output)

        self.status.setText("เลือก Media แล้ว • กด Auto Build เพื่อสร้าง Rough Cut")

    def auto_build_project(self) -> None:
        root = self.project.get("asset_root", "")
        if not root:
            self.choose_media_folder()
            root = self.project.get("asset_root", "")
            if not root:
                return

        if not self.project.get("timeline"):
            QMessageBox.information(self, APP_NAME, "กรุณาเปิด Guide Excel ก่อน")
            return

        try:
            self.sync_project()
            if self.project.get("guide_type") == "content-guide":
                auto_build(self.project, root)
            else:
                from project_model import match_project_assets
                match_project_assets(self.project, root)
            self.populate()
            self.status.setText("Auto Build เสร็จแล้ว • ตรวจ Src In / Src Out และ Preview")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

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
        self.status.setText(f"เปลี่ยนคลิป: {Path(path).name}")

    def open_selected_source(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "เลือกแถวใน Timeline ก่อน")
            return
        path = Path(self.project["timeline"][row].get("asset_path", ""))
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, APP_NAME, "แถวนี้ยังไม่มีไฟล์วิดีโอ")

    def choose_output(self) -> None:
        current = self.output_edit.text().strip() or "GuideCut_Output.mp4"
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
                "Timeline และ Media พร้อมแล้ว\n\nแนะนำให้ Preview ก่อน Export Final",
            )
        return True

    def start_render(self, preview: bool) -> None:
        if self.thread and self.thread.isRunning():
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
        self.worker = RenderWorker(self.project, str(target), preview)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.progress.setValue(0)
        self.thread.start()

    def stop_render(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.status.setText("กำลังหยุด...")

    def set_busy(self, busy: bool) -> None:
        for button in (
            self.open_guide_btn,
            self.media_btn,
            self.auto_btn,
            self.clear_btn,
            self.preview_btn,
            self.render_btn,
        ):
            button.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.encoder_combo.setEnabled(not busy)

    def on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, value)))
        self.status.setText(message)

    def on_finished(self, path: str) -> None:
        self.last_render = Path(path)
        self.progress.setValue(100)
        self.status.setText(f"เสร็จแล้ว: {Path(path).name}")
        self.set_busy(False)
        QMessageBox.information(
            self,
            APP_NAME,
            f"เสร็จแล้ว\n\nVideo: {path}\nSubtitle: {Path(path).with_suffix('.srt')}",
        )
        self.worker = None
        self.thread = None

    def on_error(self, message: str) -> None:
        self.set_busy(False)
        self.status.setText("Render ไม่สำเร็จ")
        QMessageBox.critical(self, APP_NAME, message)
        self.worker = None
        self.thread = None

    def clear_workspace(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        answer = QMessageBox.question(
            self,
            "เคลียร์หน้า",
            "ล้าง Guide / Timeline / Media / Output จากหน้าจอหรือไม่?\n"
            "ไฟล์ต้นฉบับจะไม่ถูกลบ",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.project = self._starter_project()
            self.last_render = None
            self.progress.setValue(0)
            self.populate()
            self.status.setText("หน้าโล่งแล้ว • เปิด Guide เพื่อเริ่มใหม่")

    def save_project(self) -> None:
        try:
            self.sync_project()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "GuideCut_Project.json", "JSON (*.json)"
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
