import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import sentence_voice_studio as module


def test_split_lines():
    text = "สวัสดีครับ\n\nวันนี้เราจะทดสอบ\nบรรทัดที่สาม"
    result = module.split_text(text, module.MODE_LINES)
    assert result == ["สวัสดีครับ", "วันนี้เราจะทดสอบ", "บรรทัดที่สาม"]


def test_split_sentences():
    text = "Hello world. How are you? ดีมาก!"
    result = module.split_text(text, module.MODE_SENTENCES)
    assert result == ["Hello world.", "How are you?", "ดีมาก!"]


def test_full_mode():
    text = "บรรทัดหนึ่ง\nบรรทัดสอง"
    result = module.split_text(text, module.MODE_FULL)
    assert result == ["บรรทัดหนึ่ง\nบรรทัดสอง"]


def test_safe_filename_removes_windows_invalid_chars():
    name = module.safe_filename('test: "hello" / world?', 2)
    assert name.startswith("002_")
    assert ":" not in name
    assert "/" not in name
    assert "?" not in name


def test_custom_filename_keeps_user_name_and_adds_mp3():
    name = module.sanitize_custom_filename("เสียงเปิดคลิป", "fallback", 1)
    assert name == "เสียงเปิดคลิป.mp3"


def test_custom_filename_removes_windows_invalid_chars():
    name = module.sanitize_custom_filename('intro:AI?.mp3', "fallback", 1)
    assert name == "introAI.mp3"


def test_pause_markers_become_natural_punctuation():
    text = "วันนี้ | เราจะมาพูดเรื่อง AI || เริ่มกันเลย"
    result = module.prepare_speech_text(text, True)
    assert result == "วันนี้, เราจะมาพูดเรื่อง AI. เริ่มกันเลย"


def test_pause_markers_can_be_disabled():
    text = "วันนี้ | ทดสอบ"
    assert module.prepare_speech_text(text, False) == text
