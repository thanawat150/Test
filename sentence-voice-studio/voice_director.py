from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectorCue:
    name: str
    eleven_tag: str
    azure_style: str | None
    rate_delta: int = 0
    pitch_delta: int = 0
    volume_delta: int = 0


CUES: dict[str, DirectorCue] = {
    "ปกติ": DirectorCue("ปกติ", "neutral", None),
    "ธรรมชาติ": DirectorCue("ธรรมชาติ", "conversational", None, -3, 0, 0),
    "อุทาน": DirectorCue("อุทาน", "excited", "excited", 8, 10, 3),
    "ตื่นเต้น": DirectorCue("ตื่นเต้น", "excited", "excited", 7, 8, 3),
    "ดีใจ": DirectorCue("ดีใจ", "cheerfully", "friendlycheerful", 4, 6, 2),
    "เป็นกันเอง": DirectorCue("เป็นกันเอง", "warm, conversational", "friendlycheerful", -2, 1, 0),
    "อบอุ่น": DirectorCue("อบอุ่น", "warmly", "caringempathy", -7, -3, 0),
    "ให้กำลังใจ": DirectorCue("ให้กำลังใจ", "encouraging", "encouraging", -2, 2, 2),
    "สงสัย": DirectorCue("สงสัย", "curious", "curious", -2, 5, 0),
    "ครุ่นคิด": DirectorCue("ครุ่นคิด", "thoughtful, reflective", "reflective", -10, -3, -1),
    "คิด": DirectorCue("คิด", "thoughtful", "reflective", -8, -2, -1),
    "คิดถึง": DirectorCue("คิดถึง", "nostalgic", "nostalgic", -10, -4, -1),
    "จริงจัง": DirectorCue("จริงจัง", "serious", "serious", -7, -7, 2),
    "เศร้า": DirectorCue("เศร้า", "sad", "saddisappointed", -12, -6, -2),
    "ผิดหวัง": DirectorCue("ผิดหวัง", "disappointed", "saddisappointed", -11, -5, -2),
    "ผจญภัย": DirectorCue("ผจญภัย", "adventurous", "adventurous", 3, 5, 2),
    "กระซิบ": DirectorCue("กระซิบ", "whispers", None, -16, -8, -14),
    "เบา": DirectorCue("เบา", "softly", None, -12, -5, -10),
    "ตะโกน": DirectorCue("ตะโกน", "shouts", "excited", 10, 12, 12),
    "หัวเราะ": DirectorCue("หัวเราะ", "laughs", "friendlycheerful", 1, 4, 1),
    "ขำ": DirectorCue("ขำ", "giggling", "friendlycheerful", 1, 4, 1),
    "ถอนหายใจ": DirectorCue("ถอนหายใจ", "sighs", "reflective", -8, -5, -4),
    "กระแอม": DirectorCue("กระแอม", "clears throat", None, -2, -2, 0),
    "ลังเล": DirectorCue("ลังเล", "hesitant", "reflective", -13, -2, -2),
    "กลัว": DirectorCue("กลัว", "with controlled fear", "saddisappointed", -8, 5, -3),
    "มั่นใจ": DirectorCue("มั่นใจ", "confidently", "encouraging", 0, -1, 3),
    "เน้น": DirectorCue("เน้น", "with emphasis", "serious", -1, 2, 3),
    "เร็ว": DirectorCue("เร็ว", "quickly", None, 16, 0, 0),
    "ช้า": DirectorCue("ช้า", "slowly", None, -18, 0, 0),
}

ALIASES = {
    "ตื่นเต้นมาก": "ตื่นเต้น",
    "แฮปปี้": "ดีใจ",
    "ดีใจมาก": "ดีใจ",
    "เป็นมิตร": "เป็นกันเอง",
    "ซึ้ง": "อบอุ่น",
    "เศร้ามาก": "เศร้า",
    "เสียใจ": "เศร้า",
    "ตกใจ": "อุทาน",
    "แปลกใจ": "อุทาน",
    "พูดเบา": "เบา",
    "พูดช้า": "ช้า",
    "พูดเร็ว": "เร็ว",
}

TAG_PATTERN = re.compile(r"\[([^\[\]]+)\]")


@dataclass
class DirectedSegment:
    cue: DirectorCue
    text: str


def normalize_tag(raw: str) -> str:
    tag = raw.strip().lower()
    return ALIASES.get(tag, tag)


def get_cue(raw: str) -> DirectorCue | None:
    return CUES.get(normalize_tag(raw))


def parse_director_script(text: str) -> list[DirectedSegment]:
    current = CUES["ธรรมชาติ"]
    segments: list[DirectedSegment] = []
    cursor = 0

    for match in TAG_PATTERN.finditer(text):
        before = text[cursor:match.start()]
        if before.strip():
            segments.append(DirectedSegment(current, before.strip()))

        cue = get_cue(match.group(1))
        if cue is not None:
            # Reaction tags should be emitted as their own cue when there is no
            # following text dependency; Eleven v4 can vocalize these directly.
            if cue.name in {"หัวเราะ", "ขำ", "ถอนหายใจ", "กระแอม"}:
                segments.append(DirectedSegment(cue, ""))
            else:
                current = cue
        else:
            # Unknown tags are preserved as spoken text rather than silently lost.
            segments.append(DirectedSegment(current, match.group(0)))

        cursor = match.end()

    tail = text[cursor:]
    if tail.strip():
        segments.append(DirectedSegment(current, tail.strip()))

    return segments


def prepare_plain_text(text: str) -> str:
    text = re.sub(r"\s*\|\|\s*", ". ", text)
    text = re.sub(r"\s*\|\s*", ", ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text.strip()


def to_eleven_v4_text(text: str) -> str:
    segments = parse_director_script(text)
    out: list[str] = []

    reaction_only = {"หัวเราะ", "ขำ", "ถอนหายใจ", "กระแอม"}
    for segment in segments:
        tag = f"[{segment.cue.eleven_tag}]"
        if segment.cue.name in reaction_only and not segment.text:
            out.append(tag)
            continue
        if segment.cue.name in {"ปกติ", "ธรรมชาติ"}:
            if segment.text:
                out.append(prepare_plain_text(segment.text))
        else:
            out.append(tag)
            if segment.text:
                out.append(prepare_plain_text(segment.text))

    return " ".join(part for part in out if part).strip()


def _azure_text_with_breaks(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\s*\|\|\s*", '<break time="700ms"/>', escaped)
    escaped = re.sub(r"\s*\|\s*", '<break time="280ms"/>', escaped)
    return escaped


def to_azure_ssml(text: str, voice: str) -> str:
    segments = parse_director_script(text)
    body: list[str] = []

    for segment in segments:
        if not segment.text:
            # MAI Thai styles do not expose paralinguistic laugh/sigh/whisper
            # events. Keep the style transition without inventing spoken words.
            continue

        content = _azure_text_with_breaks(segment.text)
        style = segment.cue.azure_style

        if segment.cue.name == "อุทาน" and not re.search(r"[!?！？]\s*$", segment.text):
            content += "!"

        if style:
            body.append(
                f'<mstts:express-as style="{style}">{content}</mstts:express-as>'
            )
        else:
            body.append(content)

    joined = " ".join(body)
    return (
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" '
        'xml:lang="th-TH">'
        f'<voice name="{html.escape(voice, quote=True)}">{joined}</voice>'
        "</speak>"
    )


DIRECTOR_HELP = """Voice Director — ใส่คำกำกับไว้หน้าช่วงที่ต้องการเปลี่ยนอารมณ์

อารมณ์/น้ำเสียง:
[ธรรมชาติ] [อุทาน] [ตื่นเต้น] [ดีใจ] [เป็นกันเอง] [อบอุ่น]
[ให้กำลังใจ] [สงสัย] [ครุ่นคิด] [คิดถึง] [จริงจัง]
[เศร้า] [ผิดหวัง] [กลัว] [มั่นใจ] [เน้น]

ปฏิกิริยามนุษย์ (ทำได้ดีที่สุดใน ElevenLabs v4):
[หัวเราะ] [ขำ] [ถอนหายใจ] [กระแอม] [กระซิบ] [ตะโกน] [ลังเล]

จังหวะ:
| = พักสั้น
|| = พักยาว
[เร็ว] [ช้า]
[ปกติ] = กลับเสียงปกติ

ตัวอย่าง:
[เป็นกันเอง] หลายคนคิดว่า AI ต้องพูดแข็ง ๆ || [อุทาน] แต่จริง ๆ ไม่ใช่!
[ครุ่นคิด] ถ้าเราจัดจังหวะดีขึ้น... | เสียงจะฟังเป็นมนุษย์ขึ้นมาก
[หัวเราะ] [เป็นกันเอง] และบางครั้ง การมีปฏิกิริยาเล็ก ๆ ก็ช่วยได้
"""
