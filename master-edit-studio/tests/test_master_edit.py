import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from default_ep01 import default_project
from project_model import (
    blank_project,
    load_default_project,
    parse_db_instruction,
    parse_range,
    parse_single_time,
)
from render_engine import (
    ass_time,
    generate_ass,
    generate_srt,
    generate_keyword_ass,
    build_final_command,
    preflight,
    readable_file,
    select_video_encoder,
    video_encode_args,
)


def test_latest_embedded_guide_has_sfx_column():
    guide = default_project()
    assert "SFX" in guide["master_headers"]
    assert len(guide["master_timeline"]) == 18

    sfx_index = guide["master_headers"].index("SFX")
    assert "Interface Click.mp3" in guide["master_timeline"][1][sfx_index]
    assert "Thin Swoosh.mp3" in guide["master_timeline"][2][sfx_index]
    assert "Cinematic Low Hit.mp3" in guide["master_timeline"][3][sfx_index]
    assert "Swoosh Riser Reverb.mp3" in guide["master_timeline"][10][sfx_index]


def test_latest_sfx_defaults_are_parsed_from_guide():
    project = load_default_project()
    sfx = {item["name"]: item for item in project["sfx"]}

    assert sfx["Interface Click"]["enabled"] is True
    assert sfx["Interface Click"]["file"] == "Interface Click.mp3"
    assert sfx["Interface Click"]["start"] == 2.0
    assert sfx["Interface Click"]["gain_db"] == -16.0

    assert sfx["Thin Swoosh"]["enabled"] is True
    assert sfx["Cinematic Low Hit"]["enabled"] is True
    assert sfx["Swoosh Riser Reverb"]["enabled"] is False
    assert sfx["Swoosh Riser Reverb"]["start"] == 45.5


def test_timeline_contains_sfx_guide_text():
    project = load_default_project()
    assert "Interface Click.mp3" in project["timeline"][1]["sfx_instruction"]
    assert "Cinematic Low Hit.mp3" in project["timeline"][3]["sfx_instruction"]


def test_time_and_db_parsing():
    assert parse_range("00:02.00–00:06.00") == (2.0, 6.0)
    assert parse_single_time("~00:45.5") == 45.5
    assert parse_db_instruction("Hero: -4 ถึง -2 dB") == -3.0
    assert parse_db_instruction("Mute เสียง Map") == -96.0


def test_ass_time():
    assert ass_time(68.0) == "0:01:08.00"


def test_ass_generation_keeps_keyword_but_not_subtitle_burn_in(tmp_path):
    project = load_default_project()
    out = tmp_path / "overlay.ass"
    generate_ass(project, out, 1080, 1920)
    text = out.read_text(encoding="utf-8-sig")

    assert "Style: Keyword" in text
    assert "1 POINT" in text
    assert "ปกติเวลาดูแผนที่" not in text



def test_empty_asset_path_is_not_treated_as_current_directory(tmp_path):
    ok, reason = readable_file("")
    assert ok is False
    assert "ยังไม่ได้จับคู่" in reason

    ok, reason = readable_file(tmp_path)
    assert ok is False
    assert "โฟลเดอร์" in reason

    actual = tmp_path / "clip.mp4"
    actual.write_bytes(b"test")
    ok, reason = readable_file(actual)
    assert ok is True
    assert reason == ""


def test_preflight_blocks_default_project_before_asset_matching():
    project = load_default_project()
    issues = preflight(project)
    assert issues
    assert any("ยังไม่ได้จับคู่" in issue for issue in issues)


def test_blank_project_is_really_empty():
    project = blank_project()
    assert project["timeline"] == []
    assert project["voices"] == []
    assert project["music"] == []
    assert project["sfx"] == []
    assert project["asset_root"] == ""
    assert project["output_path"] == ""



def test_default_project_uses_auto_gpu():
    project = load_default_project()
    assert project["settings"]["encoder_mode"] == "Auto GPU"


def test_cpu_encoder_selection_is_stable():
    assert select_video_encoder("CPU x264") == ("libx264", "CPU x264")


def test_gpu_encode_args_use_expected_encoder():
    args = video_encode_args("h264_nvenc", preview=False, bitrate="16M")
    assert args[0:2] == ["-c:v", "h264_nvenc"]
    assert "16M" in args
    assert "yuv420p" in args

    cpu = video_encode_args("libx264", preview=False, bitrate="16M")
    assert cpu[0:2] == ["-c:v", "libx264"]
    assert "-crf" in cpu



def test_master_timeline_is_the_only_visible_work_page():
    from PySide6.QtWidgets import QApplication
    from master_edit_studio import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.timeline_table.columnCount() == 12
    assert window.timeline_table.rowCount() == 18
    assert window.voice_table.columnCount() == 7
    assert window.music_table.columnCount() == 7
    assert window.sfx_table.columnCount() == 5
    assert window.tabs.count() == 0

    window.close()



def test_srt_export_is_separate_from_video(tmp_path):
    project = load_default_project()
    out = tmp_path / "episode.srt"
    generate_srt(project, out)
    text = out.read_text(encoding="utf-8-sig")
    assert "-->" in text
    assert "ปกติเวลาดูแผนที่" in text


def test_keyword_ass_contains_only_keyword_layer(tmp_path):
    project = load_default_project()
    item = next(x for x in project["timeline"] if x.get("text"))
    out = tmp_path / "keyword.ass"
    ok = generate_keyword_ass(item, out, 1080, 1920, 4.0)
    assert ok is True
    text = out.read_text(encoding="utf-8-sig")
    assert "Style: Keyword" in text
    assert "Style: Subtitle" not in text


def test_final_mux_copies_video_without_reencoding(tmp_path):
    project = load_default_project()
    base = tmp_path / "base.mp4"
    output = tmp_path / "final.mp4"
    cmd, _ = build_final_command(project, base, output, preview=False)
    joined = " ".join(cmd)
    assert "-c:v copy" in joined
    assert "subtitles=" not in joined
    assert "libx264" not in joined
    assert "h264_amf" not in joined
