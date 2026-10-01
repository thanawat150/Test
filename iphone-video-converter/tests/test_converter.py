import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import iphone_video_converter as app


def test_duration_parser():
    assert app.parse_duration_seconds("Duration: 00:01:30.50, start: 0") == 90.5


def test_time_parser():
    assert app.parse_time_seconds("frame=10 time=00:00:12.25 bitrate=1") == 12.25


def test_unique_output_has_mp4(tmp_path):
    src = tmp_path / "IMG_0001.MOV"
    src.write_bytes(b"x")
    result = app.unique_output_path(src, tmp_path)
    assert result.name == "IMG_0001_AI.mp4"


def test_ffmpeg_ai_command_uses_h264_aac_yuv420p(tmp_path, monkeypatch):
    monkeypatch.setattr(app.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "ffmpeg")
    source = tmp_path / "a.MOV"
    output = tmp_path / "a_AI.mp4"

    cmd = app.build_ffmpeg_command(
        source,
        output,
        "AI Compatible • 1080p • แนะนำ",
        keep_60fps=False,
    )

    joined = " ".join(cmd)
    assert "libx264" in cmd
    assert "aac" in cmd
    assert "yuv420p" in cmd
    assert "-fps_mode cfr" in joined
    assert "+faststart" in cmd
    assert str(output) == cmd[-1]
