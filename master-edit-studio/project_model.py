from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from default_ep01 import default_project
from excel_loader import load_guide_excel

DRIVE_ROOT_URL = "https://drive.google.com/drive/folders/1xJyQwetAP8xd8ehC86APVNyfobT9VcMX?usp=sharing"

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

SFX_DEFAULTS = {
    "Interface Click": {"file": "Interface Click.mp3", "start": 2.0, "gain_db": -16.0},
    "Thin Swoosh": {"file": "Thin Swoosh.mp3", "start": 6.0, "gain_db": -16.0},
    "Cinematic Low Hit": {"file": "Cinematic Low Hit.mp3", "start": 10.12, "gain_db": -20.0},
    "Swoosh Riser Reverb": {"file": "Swoosh Riser Reverb.mp3", "start": 45.5, "gain_db": -18.0},
}


def parse_timecode(value: str | float | int) -> float:
    if isinstance(value, (float, int)):
        return float(value)

    text = str(value).strip().replace(",", ".")
    if not text:
        raise ValueError("เวลาเป็นค่าว่าง")

    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)

    parts = text.split(":")
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        if seconds >= 60:
            raise ValueError(f"เวลาไม่ถูกต้อง: {text}")
        return minutes * 60 + seconds

    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        if minutes >= 60 or seconds >= 60:
            raise ValueError(f"เวลาไม่ถูกต้อง: {text}")
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"เวลาไม่ถูกต้อง: {text}")


def format_timecode(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    return f"{minutes:02d}:{secs:05.2f}"


def parse_range(text: str) -> tuple[float, float]:
    value = str(text or "").strip()
    if not value:
        raise ValueError("ช่วงเวลาเป็นค่าว่าง")

    pieces = re.split(
        r"\s*(?:→|->|–|—|\bto\b|\bถึง\b)\s*",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(pieces) != 2:
        raise ValueError(f"อ่านช่วงเวลาไม่ได้: {value}")

    left = re.search(r"\d+(?::\d+){1,2}(?:\.\d+)?", pieces[0])
    right = re.search(r"\d+(?::\d+){1,2}(?:\.\d+)?", pieces[1])
    if not left or not right:
        raise ValueError(f"อ่านช่วงเวลาไม่ได้: {value}")

    return parse_timecode(left.group(0)), parse_timecode(right.group(0))


def parse_source_select(text: str, target_duration: float) -> tuple[float, float, bool]:
    value = str(text or "").strip()

    try:
        start, end = parse_range(value)
        return start, end, False
    except ValueError:
        pass

    # Guide rows such as "ใช้ทั้งคลิป ~ 8 วิ" or map instructions
    # do not lock exact source frames. Start at zero and flag for review.
    return 0.0, max(0.1, target_duration), True


def parse_db_instruction(text: str, default: float = -20.0) -> float:
    value = str(text or "").strip()
    lower = value.lower()
    if not value:
        return default
    if "mute" in lower or "ไม่มีเสียง" in value or "ปิดเสียง" in value:
        return -96.0
    if "ยังไม่เข้าเพลง" in value:
        return -96.0

    nums = [float(x) for x in re.findall(r"-\d+(?:\.\d+)?", value)]
    if nums:
        return sum(nums) / len(nums)
    return default



def parse_single_time(text: str, default: float = 0.0) -> float:
    value = str(text or "").strip().replace("~", "")
    match = re.search(r"\d+(?::\d+){1,2}(?:\.\d+)?", value)
    if not match:
        return default
    try:
        return parse_timecode(match.group(0))
    except ValueError:
        return default


def parse_gain_range(text: str, default: float) -> float:
    nums = [float(x) for x in re.findall(r"-\d+(?:\.\d+)?", str(text or ""))]
    if nums:
        return sum(nums) / len(nums)
    return default


def _header_map(headers: list[str]) -> dict[str, int]:
    return {str(header).strip(): i for i, header in enumerate(headers)}


def _cell(row: list, index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    value = row[index]
    return "" if value is None else str(value).strip()


def normalize_guide(raw: dict) -> dict:
    master_headers = raw["master_headers"]
    master = raw["master_timeline"]
    asset_headers = raw["asset_headers"]
    assets = raw["asset_map"]

    mh = _header_map(master_headers)
    ah = _header_map(asset_headers)

    timeline: list[dict] = []
    for order, row in enumerate(master, start=1):
        timeline_text = _cell(row, mh.get("Timeline"))
        filename = _cell(row, mh.get("Video / Footage"))
        if not timeline_text or not filename:
            continue

        start, end = parse_range(timeline_text)
        duration = max(0.1, end - start)
        source_in, source_out, review = parse_source_select(
            _cell(row, mh.get("ช่วงที่ใช้ใน Select")),
            duration,
        )

        is_map = "MAP" in filename.upper()
        text = _cell(row, mh.get("Text / Subtitle"))
        if text in {"—", "-", "–"}:
            text = ""

        timeline.append(
            {
                "enabled": True,
                "order": order,
                "timeline_start": start,
                "timeline_end": end,
                "part": _cell(row, mh.get("Part")),
                "file": filename,
                "source_in": source_in,
                "source_out": source_out,
                "vo_note": _cell(row, mh.get("VO")),
                "original_db": parse_db_instruction(
                    _cell(row, mh.get("Original Audio")),
                    -20.0,
                ),
                "music_instruction": _cell(row, mh.get("Music")),
                "sfx_instruction": _cell(row, mh.get("SFX")),
                "text": text,
                "transition": _cell(row, mh.get("Edit / Transition")) or "Straight Cut",
                "note": _cell(row, mh.get("หมายเหตุ")),
                "crop_mode": "Fit + Blur" if is_map else "Fill 9:16",
                "pan_x": 50,
                "review": review,
                "asset_path": "",
            }
        )

    voices: list[dict] = []
    music: list[dict] = []
    sfx: list[dict] = []

    for row in assets:
        kind = _cell(row, ah.get("ประเภท"))
        filename = _cell(row, ah.get("ไฟล์ / Asset"))
        use_where = _cell(row, ah.get("ใช้ตรงไหน"))
        instruction = _cell(row, ah.get("วิธีใช้"))
        status = _cell(row, ah.get("Priority / สถานะ"))

        if kind == "Voice Over":
            try:
                start, end = parse_range(use_where)
            except ValueError:
                continue
            voices.append(
                {
                    "enabled": True,
                    "file": filename,
                    "start": start,
                    "end": end,
                    "gain_db": 0.0,
                    "transcript": instruction,
                    "status": status,
                    "asset_path": "",
                }
            )

        elif kind == "Music":
            try:
                start, end = parse_range(use_where.replace("ประมาณ", "").strip())
            except ValueError:
                start, end = 2.0, 68.0
            music.append(
                {
                    "enabled": True,
                    "file": filename,
                    "start": start,
                    "end": end,
                    "gain_db": -24.0,
                    "duck_under_vo": True,
                    "instruction": instruction,
                    "asset_path": "",
                }
            )

        elif kind == "SFX" and filename in SFX_DEFAULTS:
            d = SFX_DEFAULTS[filename]
            file_name = filename if Path(filename).suffix else d["file"]
            recommended = "RECOMMENDED" in status.upper()
            sfx.append(
                {
                    "enabled": recommended,
                    "name": filename,
                    "file": file_name,
                    "start": parse_single_time(use_where, d["start"]),
                    "gain_db": parse_gain_range(instruction, d["gain_db"]),
                    "instruction": instruction,
                    "status": status,
                    "asset_path": "",
                }
            )

    return {
        "version": "1.1",
        "guide_name": "EP01 Master Edit Guide",
        "drive_url": DRIVE_ROOT_URL,
        "settings": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "video_bitrate": "16M",
            "audio_bitrate": "256k",
            "subtitle_enabled": False,
            "keyword_enabled": True,
            "music_ducking": True,
            "encoder_mode": "Auto GPU",
        },
        "timeline": timeline,
        "voices": voices,
        "music": music,
        "sfx": sfx,
        "raw_guide": copy.deepcopy(raw),
        "asset_root": "",
        "output_path": "",
    }


def blank_project() -> dict:
    return {
        "version": "1.1",
        "guide_name": "Blank Project",
        "drive_url": "",
        "settings": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "video_bitrate": "16M",
            "audio_bitrate": "256k",
            "subtitle_enabled": False,
            "keyword_enabled": True,
            "music_ducking": True,
            "encoder_mode": "Auto GPU",
        },
        "timeline": [],
        "voices": [],
        "music": [],
        "sfx": [],
        "raw_guide": {
            "master_headers": [],
            "master_timeline": [],
            "asset_headers": [],
            "asset_map": [],
            "track_headers": [],
            "track_setup": [],
        },
        "asset_root": "",
        "output_path": "",
    }


def load_default_project() -> dict:
    return normalize_guide(default_project())


def load_project_from_excel(path: str | Path) -> dict:
    return normalize_guide(load_guide_excel(path))


def scan_asset_root(root: str | Path) -> dict[str, list[str]]:
    root_path = Path(root)
    index: dict[str, list[str]] = {}
    if not root_path.exists():
        return index

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTS | AUDIO_EXTS:
            continue
        index.setdefault(path.name.casefold(), []).append(str(path))
        index.setdefault(path.stem.casefold(), []).append(str(path))
    return index


def resolve_asset(index: dict[str, list[str]], filename: str) -> tuple[str, str]:
    name = Path(filename).name
    exact = list(dict.fromkeys(index.get(name.casefold(), [])))
    if len(exact) == 1:
        return exact[0], "ตรงชื่อ"
    if len(exact) > 1:
        return "", f"ชื่อซ้ำ {len(exact)} ไฟล์"

    stem = Path(name).stem.casefold()
    matches = list(dict.fromkeys(index.get(stem, [])))
    if len(matches) == 1:
        return matches[0], "ตรงชื่อฐาน"
    if len(matches) > 1:
        return "", f"ชื่อฐานซ้ำ {len(matches)} ไฟล์"
    return "", "ไม่พบ"


def match_project_assets(project: dict, root: str | Path) -> list[str]:
    index = scan_asset_root(root)
    problems: list[str] = []
    project["asset_root"] = str(root)

    for group_name in ("timeline", "voices", "music", "sfx"):
        for item in project.get(group_name, []):
            filename = item.get("file", "")
            path, status = resolve_asset(index, filename)
            item["asset_path"] = path
            item["match_status"] = status
            if item.get("enabled", True) and not path:
                problems.append(f"{group_name}: {filename} — {status}")

    return problems


def save_project_json(project: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(project, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_project_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
