import importlib.util
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / "sentence_voice_studio.py"
spec = importlib.util.spec_from_file_location("sentence_voice_studio", APP_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


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
