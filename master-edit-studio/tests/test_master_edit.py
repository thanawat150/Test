import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from autocut_engine import broll_windows, speech_segments
from project_model import blank_project, load_default_project
from render_engine import (
    build_final_command,
    readable_file,
    select_video_encoder,
    video_encode_args,
)


def test_speech_segments_remove_silence_with_padding():
    ranges = speech_segments(
        10.0,
        [(2.0, 3.0), (6.0, 7.0)],
        padding=0.1,
        min_keep=0.5,
    )
    assert ranges == [
        (0.0, 2.1),
        (2.9, 6.1),
        (6.9, 10.0),
    ]


def test_speech_segments_without_silence_keeps_clip():
    assert speech_segments(5.0, []) == [(0.0, 5.0)]


def test_broll_windows_take_short_middle_segments():
    windows = broll_windows(12.0, window=3.0, max_windows=3)
    assert len(windows) == 3
    assert all(2.9 <= end - start <= 3.01 for start, end in windows)
    assert windows[0][0] > 0


def test_broll_short_clip_uses_whole_clip():
    assert broll_windows(2.0, window=3.0) == [(0.0, 2.0)]


def test_blank_project_is_empty():
    project = blank_project()
    assert project["timeline"] == []
    assert project["asset_root"] == ""
    assert project["output_path"] == ""


def test_empty_path_is_not_a_file(tmp_path):
    ok, reason = readable_file("")
    assert ok is False
    assert "ยังไม่ได้จับคู่" in reason

    ok, reason = readable_file(tmp_path)
    assert ok is False
    assert "โฟลเดอร์" in reason


def test_cpu_encoder_selection():
    assert select_video_encoder("CPU x264") == ("libx264", "CPU x264")


def test_gpu_encoder_args():
    args = video_encode_args("h264_nvenc", preview=False, bitrate="16M")
    assert args[:2] == ["-c:v", "h264_nvenc"]
    assert "16M" in args


def test_final_mux_copies_video_without_reencoding(tmp_path):
    project = load_default_project()
    base = tmp_path / "base.mp4"
    output = tmp_path / "final.mp4"
    cmd, _ = build_final_command(project, base, output, preview=False)
    joined = " ".join(cmd)
    assert "-c:v copy" in joined
    assert "libx264" not in joined
    assert "h264_amf" not in joined


def test_autocut_ui_starts_without_guide():
    from PySide6.QtWidgets import QApplication
    from master_edit_studio import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.windowTitle().startswith("AutoCut Studio 3.0.0")
    assert window.table.rowCount() == 0
    assert window.table.columnCount() == 10
    assert window.auto_btn.text() == "AUTO CUT"
    assert "Guide" not in window.status.text()
    assert window.project["project_type"] == "autocut"

    window.close()
