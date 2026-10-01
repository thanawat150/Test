import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import advanced_tts


def test_edge_retry_recovers_from_transient_no_audio(monkeypatch, tmp_path):
    calls = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate, pitch, volume):
            calls.append((rate, pitch, volume))

        async def save(self, path):
            if len(calls) < 2:
                raise RuntimeError("No audio was received. Please verify that your parameters are correct.")
            Path(path).write_bytes(b"x" * 1024)

    monkeypatch.setattr(advanced_tts.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(advanced_tts, "EDGE_RETRY_DELAYS", (0, 0))

    output = tmp_path / "voice.mp3"
    asyncio.run(
        advanced_tts._edge_save_with_retry(
            text="สวัสดีครับ",
            output_path=output,
            voice="th-TH-PremwadeeNeural",
            rate=-5,
            pitch=2,
            volume=1,
        )
    )

    assert output.exists()
    assert output.stat().st_size == 1024
    assert len(calls) == 2
    assert calls[1] == ("-5%", "+2Hz", "+1%")


def test_edge_retry_final_attempt_uses_neutral_prosody(monkeypatch, tmp_path):
    calls = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate, pitch, volume):
            calls.append((rate, pitch, volume))

        async def save(self, path):
            if len(calls) < 3:
                raise RuntimeError("No audio was received.")
            Path(path).write_bytes(b"y" * 1024)

    monkeypatch.setattr(advanced_tts.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(advanced_tts, "EDGE_RETRY_DELAYS", (0, 0))

    output = tmp_path / "voice.mp3"
    asyncio.run(
        advanced_tts._edge_save_with_retry(
            text="ทดสอบ",
            output_path=output,
            voice="th-TH-NiwatNeural",
            rate=-12,
            pitch=-4,
            volume=3,
        )
    )

    assert len(calls) == 3
    assert calls[-1] == ("+0%", "+0Hz", "+0%")
    assert output.exists()
