from __future__ import annotations

import asyncio
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import edge_tts

from voice_director import (
    CUES,
    parse_director_script,
    prepare_plain_text,
    to_azure_ssml,
    to_eleven_v4_text,
)


AZURE_THAI_VOICES = [
    ("Krit • MAI Voice 2 • อารมณ์ไทย", "th-TH-Krit:MAI-Voice-2"),
    ("Nattapong • MAI Voice 2 • อารมณ์ไทย", "th-TH-Nattapong:MAI-Voice-2"),
    ("Krit • MAI Voice 2 Flash • เร็ว", "th-TH-Krit:MAI-Voice-2-Flash"),
    ("Nattapong • MAI Voice 2 Flash • เร็ว", "th-TH-Nattapong:MAI-Voice-2-Flash"),
]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _signed_percent(value: int) -> str:
    return f"{value:+d}%"


def _signed_hz(value: int) -> str:
    return f"{value:+d}Hz"


async def synthesize_edge(
    text: str,
    output_path: Path,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    director_mode: bool,
    natural_pause: bool,
) -> None:
    if not director_mode:
        prepared = prepare_plain_text(text) if natural_pause else text
        communicate = edge_tts.Communicate(
            prepared,
            voice,
            rate=_signed_percent(rate),
            pitch=_signed_hz(pitch),
            volume=_signed_percent(volume),
        )
        await communicate.save(str(output_path))
        return

    segments = parse_director_script(text)
    if not segments:
        segments = []

    temp_paths: list[Path] = []
    try:
        for index, segment in enumerate(segments):
            cue = segment.cue

            # Free Edge mode cannot make true non-verbal reactions.
            # We keep those cues as a short natural pause instead of reading the tag.
            if not segment.text:
                continue

            segment_text = prepare_plain_text(segment.text) if natural_pause else segment.text
            if cue.name == "อุทาน" and segment_text and segment_text[-1] not in "!?！？":
                segment_text += "!"

            seg_rate = _clamp(rate + cue.rate_delta, -50, 50)
            seg_pitch = _clamp(pitch + cue.pitch_delta, -50, 50)
            seg_volume = _clamp(volume + cue.volume_delta, -50, 50)

            temp_path = Path(tempfile.gettempdir()) / (
                f"sentence_voice_segment_{os.getpid()}_{index}.mp3"
            )
            communicate = edge_tts.Communicate(
                segment_text,
                voice,
                rate=_signed_percent(seg_rate),
                pitch=_signed_hz(seg_pitch),
                volume=_signed_percent(seg_volume),
            )
            await communicate.save(str(temp_path))
            temp_paths.append(temp_path)

        if not temp_paths:
            prepared = prepare_plain_text(text) if natural_pause else text
            communicate = edge_tts.Communicate(
                prepared,
                voice,
                rate=_signed_percent(rate),
                pitch=_signed_hz(pitch),
                volume=_signed_percent(volume),
            )
            await communicate.save(str(output_path))
            return

        # MPEG audio frames are concatenable; Edge outputs plain MP3 frame streams.
        # This allows per-segment prosody without bundling ffmpeg.
        with output_path.open("wb") as target:
            for temp_path in temp_paths:
                target.write(temp_path.read_bytes())
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _http_post(url: str, headers: dict[str, str], data: bytes, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:700]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"เชื่อมต่อบริการเสียงไม่สำเร็จ: {exc.reason}") from exc


def synthesize_azure(
    text: str,
    output_path: Path,
    key: str,
    region: str,
    voice: str,
    director_mode: bool,
) -> None:
    key = key.strip()
    region = region.strip()
    if not key or not region:
        raise RuntimeError("Azure Expressive ต้องใส่ Speech Key และ Region")

    if director_mode:
        ssml = to_azure_ssml(text, voice)
    else:
        safe = prepare_plain_text(text)
        ssml = to_azure_ssml(f"[ปกติ]{safe}", voice)

    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    audio = _http_post(
        url,
        {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml; charset=utf-8",
            "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
            "User-Agent": "SentenceVoiceStudio",
        },
        ssml.encode("utf-8"),
    )
    output_path.write_bytes(audio)


def synthesize_eleven(
    text: str,
    output_path: Path,
    api_key: str,
    voice_id: str,
    director_mode: bool,
) -> None:
    api_key = api_key.strip()
    voice_id = voice_id.strip()
    if not api_key or not voice_id:
        raise RuntimeError("ElevenLabs v4 ต้องใส่ API Key และเลือก Voice")

    directed = to_eleven_v4_text(text) if director_mode else prepare_plain_text(text)
    if len(directed) > 4500:
        raise RuntimeError(
            "ข้อความยาวเกินไปสำหรับ Preview ที่ควบคุมอารมณ์ได้ละเอียด "
            "แนะนำให้ใช้โหมดแยกบรรทัดหรือแยกประโยค"
        )

    payload = json.dumps(
        {
            "text": directed,
            "model_id": "eleven_v4",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    safe_voice_id = urllib.parse.quote(voice_id, safe="")
    audio = _http_post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{safe_voice_id}"
        "?output_format=mp3_44100_128",
        {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        payload,
    )
    output_path.write_bytes(audio)


def fetch_eleven_voices(api_key: str) -> list[dict]:
    api_key = api_key.strip()
    if not api_key:
        raise RuntimeError("กรุณาใส่ ElevenLabs API Key ก่อน")

    request = urllib.request.Request(
        "https://api.elevenlabs.io/v2/voices?page_size=100&include_total_count=false",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"โหลด Voice ไม่สำเร็จ HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"เชื่อมต่อ ElevenLabs ไม่สำเร็จ: {exc.reason}") from exc

    voices = []
    for voice in data.get("voices", []):
        voice_id = voice.get("voice_id")
        if not voice_id:
            continue
        labels = voice.get("labels") or {}
        details = " • ".join(
            x for x in [
                labels.get("language"),
                labels.get("accent"),
                labels.get("gender"),
                labels.get("use_case"),
            ] if x
        )
        voices.append(
            {
                "voice_id": voice_id,
                "name": voice.get("name") or voice_id,
                "details": details,
            }
        )
    return voices


async def synthesize_audio(
    *,
    engine: str,
    text: str,
    output_path: Path,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    natural_pause: bool,
    director_mode: bool,
    azure_key: str = "",
    azure_region: str = "",
    eleven_key: str = "",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if engine == "edge":
        await synthesize_edge(
            text,
            output_path,
            voice,
            rate,
            pitch,
            volume,
            director_mode,
            natural_pause,
        )
        return

    if engine == "azure":
        synthesize_azure(
            text,
            output_path,
            azure_key,
            azure_region,
            voice,
            director_mode,
        )
        return

    if engine == "eleven":
        synthesize_eleven(
            text,
            output_path,
            eleven_key,
            voice,
            director_mode,
        )
        return

    raise RuntimeError(f"ไม่รู้จัก TTS engine: {engine}")
