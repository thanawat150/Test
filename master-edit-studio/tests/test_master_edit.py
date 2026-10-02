import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from content_guide import (
    auto_build,
    build_content_project,
    coverage,
    parse_time_range,
)
from project_model import blank_project, load_default_project
from render_engine import (
    build_final_command,
    generate_srt,
    readable_file,
    select_video_encoder,
    video_encode_args,
)


OVERVIEW = [
    ["Field", "Value"],
    ["Topic", "ทำ AI ตัดต่อวิดีโอเองได้ไหม"],
    ["Target Length", "1–2 นาที"],
    ["Recommended Hook", "ถ้า AI เขียนโค้ดได้ มันก็น่าจะตัดคลิปได้"],
    ["Payoff", "AI ทำ rough cut ได้ แต่มนุษย์ยังคุม taste"],
]

FLOW = [
    ["Time", "Beat", "Goal", "Narration / Talking Point", "Visual / Proof", "On-screen Text"],
    ["0–8s", "Hook", "หยุดคนดู", "ประโยค Hook", "Talking Head", "AI CUT?"],
    ["8–25s", "Context", "ทำให้คนอยากรู้ต่อ", "Context", "Screen / B-roll", "PROBLEM"],
    ["25–65s", "Core", "อธิบาย", "Core", "Demo / Screen", "ROUGH CUT"],
    ["65–95s", "Payoff", "สรุป", "Payoff", "Talking Head / Result", "HUMAN TASTE"],
    ["95–120s", "Bridge", "ตอนต่อ", "Bridge", "Screen / Tease", "NEXT EP"],
]

VISUALS = [
    ["Asset / Shot", "Type", "Purpose", "What to Prepare", "Status", "Notes"],
    ["Opening", "Talking Head / Hero Shot", "Hook", "Hero", "Need", ""],
    ["Context", "Screen / B-roll", "Context", "Screen", "Need", ""],
    ["Core Proof", "Demo / Screen", "Core", "Demo", "Need", ""],
    ["Payoff", "Talking Head / Result", "Payoff", "Result", "Need", ""],
    ["Bridge", "Screen / Tease", "Bridge", "Tease", "Need", ""],
]

CHECKLIST = [
    ["Category", "Check", "Status"],
    ["Hook", "เข้าใจได้", "Todo"],
    ["Proof", "มี Demo", "Todo"],
]


def make_content_project():
    return build_content_project(
        OVERVIEW,
        FLOW,
        VISUALS,
        CHECKLIST,
        guide_name="Test Guide",
    )


def test_parse_content_guide_time_range():
    assert parse_time_range("0–8s") == (0.0, 8.0)
    assert parse_time_range("8-25s") == (8.0, 25.0)
    assert parse_time_range("95 → 120s") == (95.0, 120.0)


def test_content_guide_becomes_five_story_blocks():
    project = make_content_project()
    assert project["guide_type"] == "content-guide"
    assert len(project["timeline"]) == 5
    assert [x["beat"] for x in project["timeline"]] == [
        "Hook", "Context", "Core", "Payoff", "Bridge"
    ]
    assert project["timeline"][0]["text"] == "AI CUT?"
    assert project["timeline"][2]["crop_mode"] == "Fit + Blur"


def test_auto_build_assigns_media(tmp_path):
    project = make_content_project()

    for name in [
        "01_talk_hero.mov",
        "02_screen_context.mp4",
        "03_demo_workflow.mp4",
        "04_result_face.mp4",
        "05_screen_tease.mp4",
    ]:
        (tmp_path / name).write_bytes(b"video")

    auto_build(project, tmp_path)

    assert all(row["asset_path"] for row in project["timeline"])
    assert all(row["match_status"] == "AUTO" for row in project["timeline"])
    assert project["timeline"][0]["file"] == "01_talk_hero.mov"
    assert "demo" in project["timeline"][2]["file"].lower()


def test_coverage_reports_story_blocks(tmp_path):
    project = make_content_project()
    before = coverage(project)
    assert before["ready"] == 0
    assert before["total"] == 5

    for index in range(5):
        (tmp_path / f"{index:02d}.mp4").write_bytes(b"x")
    auto_build(project, tmp_path)

    after = coverage(project)
    assert after["ready"] == 5
    assert all(after["beats"].values())


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


def test_srt_export_is_separate(tmp_path):
    project = load_default_project()
    out = tmp_path / "episode.srt"
    generate_srt(project, out)
    text = out.read_text(encoding="utf-8-sig")
    assert "-->" in text


def test_guidecut_ui_starts_blank():
    from PySide6.QtWidgets import QApplication
    from master_edit_studio import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle().startswith("GuideCut Studio 2.0.0")
    assert window.table.columnCount() == 10
    assert window.table.rowCount() == 0
    assert window.auto_btn.text() == "Auto Build"
    window.close()
