import sys
from datetime import time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import video_segment_cutter as app


def test_parse_timecodes():
    assert app.parse_timecode("00:01.5") == 1.5
    assert app.parse_timecode("01:02.5") == 62.5
    assert app.parse_timecode("00:01:02.5") == 62.5
    assert app.parse_timecode(time(0, 0, 3, 500000)) == 3.5
    assert app.parse_timecode(timedelta(seconds=4.2)) == 4.2


def test_parse_range_cell():
    assert app.parse_range_cell("00:01.5 → 00:08.5") == ("00:01.5", "00:08.5")
    assert app.parse_range_cell("00:02 -> 00:17") == ("00:02", "00:17")


def test_header_detection():
    data = [
        ["โครงการสำรวจ"],
        ["RAW", "ตัดช่วงประมาณ", "เก็บไว้เพื่อ", "Priority"],
        ["a.MOV", "00:01 → 00:03", "test", "PRIMARY"],
    ]
    assert app.find_best_header_row(data) == 1
    headers = data[1]
    assert app.detect_column(headers, "raw") == 0
    assert app.detect_column(headers, "range") == 1
    assert app.detect_column(headers, "purpose") == 2
    assert app.detect_column(headers, "priority") == 3


def test_header_detection_for_split_start_end_columns():
    headers = ["RAW", "Start", "End", "Purpose", "Priority"]
    assert app.detect_column(headers, "raw") == 0
    assert app.detect_column(headers, "start") == 1
    assert app.detect_column(headers, "end") == 2


def test_output_name_keeps_imported_basename():
    assert app.sanitize_output_name("01_JOURNEY_ROAD_IMG1301.MOV") == "01_JOURNEY_ROAD_IMG1301.mp4"


def test_seconds_to_timecode():
    assert app.seconds_to_timecode(7.0) == "00:07.0"
    assert app.seconds_to_timecode(62.5) == "01:02.5"


def test_cut_plan_column_layout_has_auto_range_and_duration():
    assert app.COL_START == 2
    assert app.COL_END == 3
    assert app.COL_RANGE == 4
    assert app.COL_LENGTH == 5
    assert app.COL_PURPOSE == 6
    assert app.COL_PRIORITY == 7


def test_ffmpeg_command_is_ai_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(app.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "ffmpeg")
    job = app.CutJob(
        row=0,
        source=tmp_path / "a.MOV",
        output=tmp_path / "a.mp4",
        start_seconds=1.5,
        duration_seconds=7.0,
    )
    cmd = app.build_ffmpeg_command(job, "AI Ready • 1080p • แนะนำ")
    joined = " ".join(cmd)
    assert "libx264" in cmd
    assert "aac" in cmd
    assert "yuv420p" in cmd
    assert "-ss 1.500" in joined
    assert "-t 7.000" in joined
    assert "-fps_mode cfr" in joined
    assert "+faststart" in cmd



def test_short_in_to_aliases_do_not_match_filename():
    headers = ["Filename", "Start", "End"]
    assert app.detect_column(headers, "raw") == 0
    assert app.detect_column(headers, "start") == 1
    assert app.detect_column(headers, "end") == 2
