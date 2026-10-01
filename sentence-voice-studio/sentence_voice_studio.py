from __future__ import annotations

import asyncio
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from PySide6.QtCore import QObject, QStandardPaths, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

MODE_FULL = "รวมเป็นไฟล์เดียว"
MODE_LINES = "แยกตามบรรทัด"
MODE_SENTENCES = "แยกตามประโยค"

THAI_CAPABLE_MULTILINGUAL = {
    "en-US-AvaMultilingualNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-BrianMultilingualNeural",
}

CURATED_VOICES = [
    ("ไทยแท้ • ผู้หญิง • Premwadee", "th-TH-PremwadeeNeural", "Female", "th-TH", True),
    ("ไทยแท้ • ผู้ชาย • Niwat", "th-TH-NiwatNeural", "Male", "th-TH", True),
    ("ไทยแท้ • ผู้หญิง • Achara", "th-TH-AcharaNeural", "Female", "th-TH", True),
    ("Multilingual • ผู้หญิง • Ava • พูดไทยได้", "en-US-AvaMultilingualNeural", "Female", "en-US", True),
    ("Multilingual • ผู้ชาย • Andrew • พูดไทยได้", "en-US-AndrewMultilingualNeural", "Male", "en-US", True),
    ("Multilingual • ผู้หญิง • Emma • พูดไทยได้", "en-US-EmmaMultilingualNeural", "Female", "en-US", True),
    ("Multilingual • ผู้ชาย • Brian • พูดไทยได้", "en-US-BrianMultilingualNeural", "Male", "en-US", True),
    ("English (US) • ผู้หญิง • Jenny", "en-US-JennyNeural", "Female", "en-US", False),
    ("English (US) • ผู้ชาย • Guy", "en-US-GuyNeural", "Male", "en-US", False),
]

TONE_PRESETS = {
    "ธรรมชาติ": (-4, 0, 0),
    "อบอุ่น": (-8, -4, 0),
    "เล่าเรื่อง": (-10, -2, 2),
    "สดใส": (2, 8, 2),
    "จริงจัง": (-6, -8, 2),
    "ชัดเจน / อ่านง่าย": (-15, 0, 3),
}


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

    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def safe_filename(text: str, index: int, full_mode: bool = False) -> str:
    if full_mode:
        return "voice_full.mp3"

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    cleaned = cleaned[:48] or "voice"
    return f"{index:03d}_{cleaned}.mp3"


def sanitize_custom_filename(name: str, fallback_text: str, index: int) -> str:
    name = (name or "").strip()
    if not name:
        return safe_filename(fallback_text, index)

    if name.lower().endswith(".mp3"):
        stem = name[:-4]
    else:
        stem = name

    stem = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    stem = stem[:100] or f"voice_{index:03d}"
    return f"{stem}.mp3"


def prepare_speech_text(text: str, natural_pause: bool = True) -> str:
    text = text.strip()
    if not natural_pause:
        return text

    # User-controlled natural pauses:
    # |  = short pause, || = longer pause.
    text = re.sub(r"\s*\|\|\s*", ". ", text)
    text = re.sub(r"\s*\|\s*", ", ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text.strip()


def signed_percent(value: int) -> str:
    return f"{value:+d}%"


def signed_hz(value: int) -> str:
    return f"{value:+d}Hz"


def format_ms(value: int) -> str:
    seconds = max(0, value // 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class VoiceCatalogWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def run(self) -> None:
        try:
            voices = asyncio.run(edge_tts.list_voices())
            self.finished.emit(voices)
        except Exception as exc:
            self.error.emit(str(exc))
            self.finished.emit([])


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
        natural_pause: bool,
    ) -> None:
        super().__init__()
        self.items = items
        self.output_dir = output_dir
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.natural_pause = natural_pause

    def run(self) -> None:
        try:
            paths = asyncio.run(self._run_async())
            self.finished.emit(paths)
        except Exception as exc:
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
                    prepare_speech_text(item.text, self.natural_pause),
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
        self.voice_thread: QThread | None = None
        self.voice_worker: VoiceCatalogWorker | None = None
        self.preview_mode = False
        self._applying_preset = False

        self.voice_catalog = [
            {
                "label": label,
                "short_name": short_name,
                "gender": gender,
                "locale": locale,
                "thai_capable": thai_capable,
            }
            for label, short_name, gender, locale, thai_capable in CURATED_VOICES
        ]

        self.setWindowTitle(f"{APP_NAME} 0.2")
        self.resize(1280, 860)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.9)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_playback_position)
        self.player.durationChanged.connect(self.on_playback_duration)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "วางข้อความที่นี่...\n\n"
            "ใช้ | สำหรับพักสั้น และ || สำหรับพักยาว เช่น:\n"
            "วันนี้ | เราจะมาพูดเรื่อง AI || แบบที่ฟังเป็นธรรมชาติมากขึ้น"
        )
        self.text_edit.setMinimumHeight(250)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([MODE_LINES, MODE_SENTENCES, MODE_FULL])

        self.voice_filter_combo = QComboBox()
        self.voice_filter_combo.addItems(
            ["แนะนำสำหรับภาษาไทย", "ไทยแท้ (th-TH)", "Multilingual", "ทั้งหมด"]
        )
        self.voice_filter_combo.currentTextChanged.connect(self.filter_voice_catalog)

        self.voice_search = QLineEdit()
        self.voice_search.setPlaceholderText("ค้นหาชื่อเสียง เช่น Ava, Niwat, Female...")
        self.voice_search.textChanged.connect(self.filter_voice_catalog)

        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumContentsLength(34)

        self.refresh_voices_btn = QPushButton("โหลดรายชื่อเสียงออนไลน์")
        self.refresh_voices_btn.clicked.connect(self.refresh_voice_catalog)

        self.tone_combo = QComboBox()
        self.tone_combo.addItems(list(TONE_PRESETS.keys()) + ["กำหนดเอง"])
        self.tone_combo.currentTextChanged.connect(self.apply_tone_preset)

        self.natural_pause_check = QCheckBox("เปิดจังหวะพูดธรรมชาติจาก | และ ||")
        self.natural_pause_check.setChecked(True)

        self.rate_slider = self._slider(-50, 50, 0)
        self.pitch_slider = self._slider(-50, 50, 0)
        self.volume_slider = self._slider(-50, 50, 0)

        self.rate_value = QLabel("+0%")
        self.pitch_value = QLabel("+0Hz")
        self.volume_value = QLabel("+0%")

        self.rate_slider.valueChanged.connect(self.on_rate_changed)
        self.pitch_slider.valueChanged.connect(self.on_pitch_changed)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)

        music_dir = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
        base_dir = Path(music_dir) if music_dir else Path.home()
        self.output_dir = base_dir / "SentenceVoiceStudio"

        self.output_label = QLabel(str(self.output_dir))
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.choose_output_btn = QPushButton("เลือกโฟลเดอร์")
        self.choose_output_btn.clicked.connect(self.choose_output_folder)

        self.build_queue_btn = QPushButton("สร้างคิวจากข้อความ")
        self.build_queue_btn.clicked.connect(self.build_queue)

        self.preview_btn = QPushButton("สร้าง Preview และเล่น")
        self.preview_btn.clicked.connect(self.preview_selected)

        self.play_btn = QPushButton("▶ เล่นไฟล์ที่เลือก")
        self.play_btn.clicked.connect(self.play_selected_audio)

        self.pause_btn = QPushButton("⏸ พัก / เล่นต่อ")
        self.pause_btn.clicked.connect(self.pause_resume_audio)

        self.audio_stop_btn = QPushButton("■ หยุดฟัง")
        self.audio_stop_btn.clicked.connect(self.player.stop)

        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setRange(0, 0)
        self.playback_slider.sliderMoved.connect(self.player.setPosition)

        self.playback_time = QLabel("00:00 / 00:00")

        self.generate_selected_btn = QPushButton("สร้างใหม่เฉพาะที่เลือก")
        self.generate_selected_btn.clicked.connect(self.generate_selected)

        self.generate_all_btn = QPushButton("สร้างเสียงทั้งหมด")
        self.generate_all_btn.setObjectName("primaryButton")
        self.generate_all_btn.clicked.connect(self.generate_all)

        self.stop_btn = QPushButton("หยุดสร้าง")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)

        self.open_folder_btn = QPushButton("เปิดโฟลเดอร์")
        self.open_folder_btn.clicked.connect(self.open_output_folder)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "ข้อความ", "สถานะ", "ชื่อไฟล์ (แก้ได้)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 560)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 350)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellDoubleClicked.connect(self.on_table_double_click)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.status_label = QLabel("พร้อมใช้งาน")

        self._build_layout()
        self._apply_styles()
        self.filter_voice_catalog()
        self.apply_tone_preset("ธรรมชาติ")
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
        root.setSpacing(10)

        title = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Text-to-Speech สำหรับ Windows • เสียงไทย/Multilingual • ปรับโทน • ฟังในโปรแกรม • ตั้งชื่อไฟล์เอง"
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
        pause_hint = QLabel("เคล็ดลับ: | = พักสั้น   •   || = พักยาว")
        text_layout.addWidget(pause_hint)
        text_layout.addWidget(self.build_queue_btn)

        settings_group = QGroupBox("2) เสียงและความเป็นธรรมชาติ")
        grid = QGridLayout(settings_group)

        grid.addWidget(QLabel("วิธีแบ่ง"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1, 1, 3)

        grid.addWidget(QLabel("กลุ่มเสียง"), 1, 0)
        grid.addWidget(self.voice_filter_combo, 1, 1, 1, 3)

        grid.addWidget(QLabel("ค้นหาเสียง"), 2, 0)
        grid.addWidget(self.voice_search, 2, 1, 1, 2)
        grid.addWidget(self.refresh_voices_btn, 2, 3)

        grid.addWidget(QLabel("บุคคล / Voice"), 3, 0)
        grid.addWidget(self.voice_combo, 3, 1, 1, 3)

        grid.addWidget(QLabel("โทน"), 4, 0)
        grid.addWidget(self.tone_combo, 4, 1, 1, 3)

        grid.addWidget(QLabel("ความเร็ว"), 5, 0)
        grid.addWidget(self.rate_slider, 5, 1, 1, 2)
        grid.addWidget(self.rate_value, 5, 3)

        grid.addWidget(QLabel("Pitch"), 6, 0)
        grid.addWidget(self.pitch_slider, 6, 1, 1, 2)
        grid.addWidget(self.pitch_value, 6, 3)

        grid.addWidget(QLabel("Volume"), 7, 0)
        grid.addWidget(self.volume_slider, 7, 1, 1, 2)
        grid.addWidget(self.volume_value, 7, 3)

        grid.addWidget(self.natural_pause_check, 8, 1, 1, 3)

        grid.addWidget(QLabel("บันทึกที่"), 9, 0)
        grid.addWidget(self.output_label, 9, 1, 1, 2)
        grid.addWidget(self.choose_output_btn, 9, 3)

        top_layout.addWidget(text_group, 3)
        top_layout.addWidget(settings_group, 3)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        queue_group = QGroupBox(
            "3) คิวเสียง — แก้ข้อความและชื่อไฟล์ได้โดยตรงในตาราง"
        )
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.addWidget(self.table)

        playback_row = QHBoxLayout()
        playback_row.addWidget(self.preview_btn)
        playback_row.addWidget(self.play_btn)
        playback_row.addWidget(self.pause_btn)
        playback_row.addWidget(self.audio_stop_btn)
        playback_row.addWidget(self.playback_slider, 1)
        playback_row.addWidget(self.playback_time)
        queue_layout.addLayout(playback_row)

        button_row = QHBoxLayout()
        button_row.addWidget(self.generate_selected_btn)
        button_row.addStretch()
        button_row.addWidget(self.open_folder_btn)
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.generate_all_btn)
        queue_layout.addLayout(button_row)

        bottom_layout.addWidget(queue_group)

        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setSizes([390, 470])

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
            QTextEdit, QTableWidget, QComboBox, QLineEdit {
                background: white;
                border: 1px solid #d7dce5;
                border-radius: 7px;
            }
            QLineEdit, QComboBox {
                min-height: 29px;
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

    def on_rate_changed(self, value: int) -> None:
        self.rate_value.setText(signed_percent(value))
        self._mark_custom_tone()

    def on_pitch_changed(self, value: int) -> None:
        self.pitch_value.setText(signed_hz(value))
        self._mark_custom_tone()

    def on_volume_changed(self, value: int) -> None:
        self.volume_value.setText(signed_percent(value))
        self._mark_custom_tone()

    def _mark_custom_tone(self) -> None:
        if not self._applying_preset and self.tone_combo.currentText() != "กำหนดเอง":
            self.tone_combo.blockSignals(True)
            self.tone_combo.setCurrentText("กำหนดเอง")
            self.tone_combo.blockSignals(False)

    def apply_tone_preset(self, name: str) -> None:
        if name not in TONE_PRESETS:
            return

        rate, pitch, volume = TONE_PRESETS[name]
        self._applying_preset = True
        self.rate_slider.setValue(rate)
        self.pitch_slider.setValue(pitch)
        self.volume_slider.setValue(volume)
        self._applying_preset = False

    def filter_voice_catalog(self, *_args) -> None:
        group = self.voice_filter_combo.currentText() if hasattr(self, "voice_filter_combo") else "แนะนำสำหรับภาษาไทย"
        query = self.voice_search.text().strip().lower() if hasattr(self, "voice_search") else ""
        selected = self.voice_combo.currentData() if hasattr(self, "voice_combo") else None

        filtered = []
        for voice in self.voice_catalog:
            short_name = voice["short_name"]
            locale = voice["locale"]
            thai_capable = voice["thai_capable"]

            if group == "แนะนำสำหรับภาษาไทย" and not thai_capable:
                continue
            if group == "ไทยแท้ (th-TH)" and locale != "th-TH":
                continue
            if group == "Multilingual" and "Multilingual" not in short_name:
                continue

            searchable = (
                f'{voice["label"]} {short_name} {voice["gender"]} {locale}'
            ).lower()
            if query and query not in searchable:
                continue

            filtered.append(voice)

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        for voice in filtered:
            self.voice_combo.addItem(voice["label"], voice["short_name"])

        if selected:
            index = self.voice_combo.findData(selected)
            if index >= 0:
                self.voice_combo.setCurrentIndex(index)

        self.voice_combo.blockSignals(False)

    def refresh_voice_catalog(self) -> None:
        if self.voice_thread and self.voice_thread.isRunning():
            return

        self.refresh_voices_btn.setEnabled(False)
        self.refresh_voices_btn.setText("กำลังโหลด...")
        self.status_label.setText("กำลังโหลดรายชื่อเสียงจากบริการออนไลน์...")

        self.voice_thread = QThread(self)
        self.voice_worker = VoiceCatalogWorker()
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.finished.connect(self.on_voice_catalog_loaded)
        self.voice_worker.error.connect(self.on_voice_catalog_error)
        self.voice_worker.finished.connect(self.voice_thread.quit)
        self.voice_worker.finished.connect(self.voice_worker.deleteLater)
        self.voice_thread.finished.connect(self.voice_thread.deleteLater)
        self.voice_thread.start()

    def on_voice_catalog_loaded(self, voices: list) -> None:
        by_name = {voice["short_name"]: voice for voice in self.voice_catalog}

        for voice in voices:
            short_name = voice.get("ShortName", "")
            if not short_name:
                continue

            locale = voice.get("Locale", "")
            gender = voice.get("Gender", "")
            thai_capable = locale == "th-TH" or short_name in THAI_CAPABLE_MULTILINGUAL
            thai_tag = " • พูดไทยได้" if thai_capable and locale != "th-TH" else ""
            label = f"{locale} • {gender} • {short_name}{thai_tag}"

            if short_name in by_name:
                by_name[short_name]["gender"] = gender or by_name[short_name]["gender"]
                by_name[short_name]["locale"] = locale or by_name[short_name]["locale"]
                by_name[short_name]["thai_capable"] = thai_capable or by_name[short_name]["thai_capable"]
            else:
                by_name[short_name] = {
                    "label": label,
                    "short_name": short_name,
                    "gender": gender,
                    "locale": locale,
                    "thai_capable": thai_capable,
                }

        curated_names = {item[1] for item in CURATED_VOICES}
        curated = [v for v in by_name.values() if v["short_name"] in curated_names]
        others = sorted(
            [v for v in by_name.values() if v["short_name"] not in curated_names],
            key=lambda v: (v["locale"], v["short_name"]),
        )
        self.voice_catalog = curated + others
        self.filter_voice_catalog()

        self.refresh_voices_btn.setEnabled(True)
        self.refresh_voices_btn.setText("โหลดรายชื่อเสียงออนไลน์")
        self.status_label.setText(f"โหลดรายชื่อเสียงแล้ว {len(self.voice_catalog)} เสียง")
        self.voice_thread = None
        self.voice_worker = None

    def on_voice_catalog_error(self, message: str) -> None:
        self.status_label.setText(f"โหลดรายชื่อเสียงไม่สำเร็จ: {message}")

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
            file_item.setToolTip("ดับเบิลคลิกเพื่อแก้ชื่อไฟล์ก่อนบันทึก")

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
        text_item = self.table.item(row, 1)
        filename_item = self.table.item(row, 3)
        text = (text_item.text() if text_item else "").strip()

        if preview:
            filename = "preview.mp3"
        else:
            requested = filename_item.text() if filename_item else ""
            filename = sanitize_custom_filename(requested, text, row + 1)
            if filename_item:
                filename_item.setText(filename)

        return QueueItem(row=row, text=text, filename=filename)

    def _all_queue_items(self) -> list[QueueItem]:
        items = []
        seen: dict[str, int] = {}

        for row in range(self.table.rowCount()):
            text_item = self.table.item(row, 1)
            if not text_item or not text_item.text().strip():
                continue

            item = self._queue_item_for_row(row)
            stem = Path(item.filename).stem
            suffix = Path(item.filename).suffix or ".mp3"
            key = item.filename.lower()

            if key in seen:
                seen[key] += 1
                item.filename = f"{stem}_{seen[key]}{suffix}"
                self.table.item(row, 3).setText(item.filename)
            else:
                seen[key] = 1

            items.append(item)

        return items

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

        items = self._all_queue_items()
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

        voice = self.voice_combo.currentData()
        if not voice:
            QMessageBox.information(self, APP_NAME, "กรุณาเลือกเสียงก่อน")
            return

        self.preview_mode = preview
        self.progress.setRange(0, len(items))
        self.progress.setValue(0)
        self.status_label.setText("กำลังเชื่อมต่อบริการเสียง...")

        self.thread = QThread(self)
        self.worker = TTSWorker(
            items=items,
            output_dir=output_dir,
            voice=voice,
            rate=self.rate_slider.value(),
            pitch=self.pitch_slider.value(),
            volume=self.volume_slider.value(),
            natural_pause=self.natural_pause_check.isChecked(),
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
            self.status_label.setText("กำลังหยุดหลังจากไฟล์ปัจจุบันเสร็จ...")

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
            self.status_label.setText("Preview พร้อมแล้ว")
            if paths:
                self.play_audio_path(Path(paths[0]))
        else:
            self.status_label.setText(
                f"เสร็จแล้ว {len(paths)} ไฟล์ • {self.output_dir}"
            )

        self.preview_mode = False
        self.thread = None
        self.worker = None

    def play_audio_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.information(self, APP_NAME, "ยังไม่พบไฟล์เสียงนี้")
            return
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self.status_label.setText(f"กำลังเล่น: {path.name}")

    def play_selected_audio(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, APP_NAME, "กรุณาเลือกไฟล์ในตารางก่อน")
            return

        item = self._queue_item_for_row(row)
        self.play_audio_path(self.output_dir / item.filename)

    def pause_resume_audio(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_playback_position(self, position: int) -> None:
        self.playback_slider.setValue(position)
        self.playback_time.setText(
            f"{format_ms(position)} / {format_ms(self.player.duration())}"
        )

    def on_playback_duration(self, duration: int) -> None:
        self.playback_slider.setRange(0, max(duration, 0))
        self.playback_time.setText(
            f"{format_ms(self.player.position())} / {format_ms(duration)}"
        )

    def on_table_double_click(self, row: int, column: int) -> None:
        if column == 3:
            self.table.editItem(self.table.item(row, column))
            return

        filename_item = self.table.item(row, 3)
        if not filename_item:
            return

        path = self.output_dir / sanitize_custom_filename(
            filename_item.text(),
            self.table.item(row, 1).text() if self.table.item(row, 1) else "",
            row + 1,
        )
        if path.exists():
            self.play_audio_path(path)

    def open_output_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.player.stop()

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
