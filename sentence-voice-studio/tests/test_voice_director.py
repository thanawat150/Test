import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from voice_director import (
    auto_direct_script,
    get_cue,
    infer_cue_for_text,
    parse_director_script,
    to_azure_ssml,
    to_eleven_v4_text,
)


def test_director_changes_emotion_mid_sentence():
    segments = parse_director_script(
        "[เป็นกันเอง] สวัสดีครับ [อุทาน] โห! [ครุ่นคิด] จริงเหรอ..."
    )
    spoken = [(segment.cue.name, segment.text) for segment in segments if segment.text]
    assert spoken == [
        ("เป็นกันเอง", "สวัสดีครับ"),
        ("อุทาน", "โห!"),
        ("ครุ่นคิด", "จริงเหรอ..."),
    ]


def test_flexible_custom_thai_direction_maps_to_supported_cue():
    assert get_cue("พูดช้าและจริงจัง").name in {"ช้า", "จริงจัง"}
    assert get_cue("ถามแบบสงสัย").name == "สงสัย"
    assert get_cue("พูดเบาเหมือนกระซิบ").name in {"กระซิบ", "เบา"}


def test_unknown_bracket_instruction_is_not_spoken():
    segments = parse_director_script("[พูดเหมือนเล่าเรื่องสารคดี] สวัสดีครับ")
    assert all("พูดเหมือนเล่าเรื่องสารคดี" not in segment.text for segment in segments)


def test_human_reactions_become_eleven_audio_tags():
    result = to_eleven_v4_text(
        "[สงสัย] จริงเหรอ? [หัวเราะ] [กระซิบ] อย่าบอกใครนะ [ถอนหายใจ]"
    )
    assert "[curious]" in result
    assert "[laughs]" in result
    assert "[whispers]" in result
    assert "[sighs]" in result


def test_azure_uses_supported_thai_mai_styles():
    ssml = to_azure_ssml(
        "[ตื่นเต้น] เยี่ยมมาก [ครุ่นคิด] แต่ลองคิดดูอีกที",
        "th-TH-Krit:MAI-Voice-2",
    )
    assert 'style="excited"' in ssml
    assert 'style="reflective"' in ssml
    assert "th-TH-Krit:MAI-Voice-2" in ssml


def test_auto_analysis_is_editable_visible_markup():
    result = auto_direct_script("จริงเหรอ? โห! ทำได้ขนาดนี้เลย")
    assert "[สงสัย]" in result
    assert "[อุทาน]" in result or "[ตื่นเต้น]" in result


def test_auto_analysis_preserves_user_directed_lines():
    source = "[จริงจัง] เรื่องนี้สำคัญมาก"
    assert auto_direct_script(source) == source


def test_inference_basics():
    assert infer_cue_for_text("ทำไมมันถึงเป็นแบบนี้?") == "สงสัย"
    assert infer_cue_for_text("โห ไม่น่าเชื่อเลย") == "อุทาน"
    assert infer_cue_for_text("ประเด็นนี้สำคัญ ต้องระวัง") == "จริงจัง"
