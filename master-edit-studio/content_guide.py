from __future__ import annotations

import re
from pathlib import Path

from python_calamine import CalamineWorkbook

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".webm"}

CONTENT_SHEETS = {
    "Overview",
    "Script Flow",
    "Visual Plan",
    "Checklist",
}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _rows(workbook: CalamineWorkbook, name: str) -> list[list[str]]:
    raw = workbook.get_sheet_by_name(name).to_python(skip_empty_area=False)
    cleaned: list[list[str]] = []
    for row in raw:
        values = [_text(value) for value in row]
        while values and not values[-1]:
            values.pop()
        if any(values):
            cleaned.append(values)
    return cleaned


def is_content_guide(path: str | Path) -> bool:
    workbook = CalamineWorkbook.from_path(str(path))
    try:
        names = set(workbook.sheet_names)
        return CONTENT_SHEETS.issubset(names)
    finally:
        workbook.close()


def parse_time_range(value: str) -> tuple[float, float]:
    text = _text(value).lower().replace("seconds", "s").replace("sec", "s")
    text = text.replace("วินาที", "s").replace("วิ", "s")
    text = re.sub(r"\s+", "", text)

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|–|—|→|to)\s*(\d+(?:\.\d+)?)s?",
        text,
    )
    if not match:
        raise ValueError(f"อ่านช่วงเวลาไม่ได้: {value}")

    start = float(match.group(1))
    end = float(match.group(2))
    if end <= start:
        raise ValueError(f"ช่วงเวลาต้อง End > Start: {value}")
    return start, end


def _table_to_dict(rows: list[list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) >= 2 and row[0]:
            result[row[0]] = row[1]
    return result


def _table_records(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    headers = rows[0]
    result: list[dict[str, str]] = []
    for row in rows[1:]:
        record = {
            headers[i]: row[i] if i < len(row) else ""
            for i in range(len(headers))
        }
        if any(record.values()):
            result.append(record)
    return result


def build_content_project(
    overview_rows: list[list[str]],
    flow_rows: list[list[str]],
    visual_rows: list[list[str]],
    checklist_rows: list[list[str]],
    guide_name: str = "Content Guide",
) -> dict:
    overview = _table_to_dict(overview_rows)
    flow = _table_records(flow_rows)
    visuals = _table_records(visual_rows)
    checklist = _table_records(checklist_rows)

    visual_by_purpose: dict[str, dict[str, str]] = {}
    for item in visuals:
        purpose = item.get("Purpose", "").strip().casefold()
        if purpose:
            visual_by_purpose[purpose] = item

    timeline: list[dict] = []
    for order, beat in enumerate(flow, start=1):
        start, end = parse_time_range(beat.get("Time", ""))
        beat_name = beat.get("Beat", "") or f"Beat {order}"
        purpose = beat_name.strip().casefold()
        visual_plan = visual_by_purpose.get(purpose, {})

        visual = beat.get("Visual / Proof", "")
        if not visual:
            visual = visual_plan.get("What to Prepare", "")

        type_text = visual_plan.get("Type", "")
        combined = f"{type_text} {visual}".casefold()
        crop_mode = "Fit + Blur" if any(
            key in combined for key in ("screen", "diagram", "graphic", "workflow", "map")
        ) else "Fill 9:16"

        target_duration = end - start
        original_db = 0.0 if "talking head" in combined or "hero" in combined else -18.0

        timeline.append(
            {
                "enabled": True,
                "order": order,
                "timeline_start": start,
                "timeline_end": end,
                "beat": beat_name,
                "goal": beat.get("Goal", ""),
                "narration": beat.get("Narration / Talking Point", ""),
                "visual": visual,
                "text": beat.get("On-screen Text", ""),
                "file": "",
                "asset_path": "",
                "source_in": 0.0,
                "source_out": target_duration,
                "crop_mode": crop_mode,
                "pan_x": 50,
                "original_db": original_db,
                "transition": "Straight Cut",
                "review": True,
                "match_status": "รอ Auto Build",
            }
        )

    return {
        "version": "2.0",
        "guide_type": "content-guide",
        "guide_name": guide_name,
        "overview": overview,
        "visual_plan": visuals,
        "checklist": checklist,
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
        "voices": [],
        "music": [],
        "sfx": [],
        "raw_guide": {
            "overview": overview_rows,
            "script_flow": flow_rows,
            "visual_plan": visual_rows,
            "checklist": checklist_rows,
        },
        "asset_root": "",
        "output_path": "",
    }


def load_content_guide(path: str | Path) -> dict:
    workbook = CalamineWorkbook.from_path(str(path))
    try:
        names = set(workbook.sheet_names)
        missing = sorted(CONTENT_SHEETS - names)
        if missing:
            raise ValueError("Excel ขาด Sheet: " + ", ".join(missing))

        overview = _rows(workbook, "Overview")
        flow = _rows(workbook, "Script Flow")
        visuals = _rows(workbook, "Visual Plan")
        checklist = _rows(workbook, "Checklist")
    finally:
        workbook.close()

    return build_content_project(
        overview,
        flow,
        visuals,
        checklist,
        guide_name=Path(path).stem,
    )


def scan_videos(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(
        (
            path for path in root_path.rglob("*")
            if path.is_file() and path.suffix.lower() in VIDEO_EXTS
        ),
        key=lambda path: path.name.casefold(),
    )


def _score_video(path: Path, item: dict) -> int:
    name = path.stem.casefold()
    haystack = " ".join(
        [
            item.get("beat", ""),
            item.get("visual", ""),
            item.get("goal", ""),
        ]
    ).casefold()

    score = 0
    rules = [
        (("screen", "record", "capture", "workflow", "demo", "ui"), ("screen", "workflow", "demo")),
        (("map", "gis"), ("map", "gis")),
        (("talk", "face", "hero", "self", "cam"), ("talking head", "hero")),
        (("broll", "b-roll", "footage", "img", "mov"), ("b-roll", "context")),
        (("result", "after", "final"), ("payoff", "result")),
    ]
    for filename_words, guide_words in rules:
        if any(word in haystack for word in guide_words):
            if any(word in name for word in filename_words):
                score += 10
    return score


def auto_build(project: dict, root: str | Path) -> dict:
    videos = scan_videos(root)
    project["asset_root"] = str(root)

    if not videos:
        for item in project.get("timeline", []):
            item["asset_path"] = ""
            item["file"] = ""
            item["match_status"] = "ไม่พบวิดีโอ"
        return project

    unused = list(videos)
    used_count: dict[Path, int] = {}

    for item in project.get("timeline", []):
        if not item.get("enabled", True):
            continue

        candidates = unused or videos
        ranked = sorted(
            candidates,
            key=lambda p: (-_score_video(p, item), used_count.get(p, 0), p.name.casefold()),
        )
        chosen = ranked[0]

        if chosen in unused:
            unused.remove(chosen)
        used_count[chosen] = used_count.get(chosen, 0) + 1

        duration = max(
            0.1,
            float(item.get("timeline_end", 0)) - float(item.get("timeline_start", 0)),
        )
        item["file"] = chosen.name
        item["asset_path"] = str(chosen)
        item["source_in"] = 0.0
        item["source_out"] = duration
        item["match_status"] = "AUTO"
        item["review"] = True

    return project


def coverage(project: dict) -> dict:
    rows = [x for x in project.get("timeline", []) if x.get("enabled", True)]
    ready = sum(1 for row in rows if row.get("asset_path"))
    with_text = sum(1 for row in rows if str(row.get("text", "")).strip())

    beats: dict[str, bool] = {}
    for row in rows:
        name = str(row.get("beat", "")).strip() or f"Beat {row.get('order','')}"
        beats[name] = bool(row.get("asset_path"))

    required_visuals = [
        x for x in project.get("visual_plan", [])
        if str(x.get("Status", "")).strip().casefold() == "need"
    ]

    return {
        "beats": beats,
        "ready": ready,
        "total": len(rows),
        "with_text": with_text,
        "required_visuals": len(required_visuals),
    }
