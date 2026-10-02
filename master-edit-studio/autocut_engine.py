from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".webm"}


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


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


def probe_media(path: str | Path) -> dict:
    source = Path(path)
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(source)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = proc.stderr

    duration = 0.0
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        duration = hours * 3600 + minutes * 60 + seconds

    return {
        "path": str(source),
        "file": source.name,
        "duration": duration,
        "has_audio": "Audio:" in text,
    }


def detect_silences(
    path: str | Path,
    *,
    noise_db: float = -35.0,
    min_silence: float = 0.45,
) -> list[tuple[float, float]]:
    source = Path(path)
    cmd = [
        ffmpeg_exe(),
        "-hide_banner",
        "-nostats",
        "-i", str(source),
        "-vn",
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = proc.stderr.splitlines()

    result: list[tuple[float, float]] = []
    current: float | None = None
    for line in lines:
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            current = float(start_match.group(1))
            continue

        end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
        if end_match and current is not None:
            result.append((current, float(end_match.group(1))))
            current = None

    return result


def speech_segments(
    duration: float,
    silences: list[tuple[float, float]],
    *,
    padding: float = 0.12,
    min_keep: float = 0.70,
) -> list[tuple[float, float]]:
    duration = max(0.0, float(duration))
    if duration <= 0:
        return []

    if not silences:
        return [(0.0, duration)] if duration >= min_keep else []

    clean: list[tuple[float, float]] = []
    cursor = 0.0
    for silence_start, silence_end in sorted(silences):
        keep_start = cursor
        keep_end = max(cursor, silence_start + padding)
        if keep_end - keep_start >= min_keep:
            clean.append((keep_start, min(duration, keep_end)))
        cursor = max(cursor, silence_end - padding)

    if duration - cursor >= min_keep:
        clean.append((max(0.0, cursor), duration))

    return [
        (max(0.0, start), min(duration, end))
        for start, end in clean
        if end - start >= min_keep
    ]


def broll_windows(
    duration: float,
    *,
    window: float = 3.0,
    max_windows: int = 3,
) -> list[tuple[float, float]]:
    duration = max(0.0, float(duration))
    if duration <= 0.25:
        return []

    if duration <= window:
        return [(0.0, duration)]

    count = min(max_windows, max(1, int(duration // max(window, 1.0))))
    windows: list[tuple[float, float]] = []

    for index in range(count):
        ratio = (index + 1) / (count + 1)
        center = duration * ratio
        start = max(0.0, center - window / 2)
        end = min(duration, start + window)
        start = max(0.0, end - window)
        if end - start >= 0.6:
            windows.append((start, end))

    return windows


def _limit_segments(
    segments: list[dict],
    target_seconds: float | None,
) -> list[dict]:
    if not target_seconds or target_seconds <= 0:
        return segments

    result: list[dict] = []
    used = 0.0

    for segment in segments:
        remaining = target_seconds - used
        if remaining <= 0.05:
            break

        duration = float(segment["source_out"]) - float(segment["source_in"])
        if duration <= remaining + 0.02:
            result.append(segment)
            used += duration
            continue

        if remaining >= 0.7:
            clipped = dict(segment)
            clipped["source_out"] = float(clipped["source_in"]) + remaining
            result.append(clipped)
            used += remaining
        break

    return result


def _interleave(talking: list[dict], broll: list[dict]) -> list[dict]:
    if not talking:
        return broll
    if not broll:
        return talking

    result: list[dict] = []
    b_index = 0

    for index, talk in enumerate(talking):
        result.append(talk)
        if (index + 1) % 2 == 0 and b_index < len(broll):
            result.append(broll[b_index])
            b_index += 1

    result.extend(broll[b_index:])
    return result


def build_autocut_project(
    root: str | Path,
    *,
    mode: str = "ผสม",
    target_seconds: float | None = 60.0,
    remove_silence: bool = True,
    progress=None,
) -> dict:
    videos = scan_videos(root)
    if not videos:
        raise ValueError("ไม่พบไฟล์วิดีโอในโฟลเดอร์ที่เลือก")

    media: list[dict] = []
    total = len(videos)

    for index, path in enumerate(videos):
        if progress:
            progress(
                int(5 + 35 * (index / max(1, total))),
                f"วิเคราะห์ไฟล์ {index + 1}/{total}: {path.name}",
            )
        info = probe_media(path)
        media.append(info)

    talking: list[dict] = []
    broll: list[dict] = []

    for index, info in enumerate(media):
        path = Path(info["path"])
        duration = float(info["duration"])
        has_audio = bool(info["has_audio"])

        if progress:
            progress(
                int(40 + 35 * (index / max(1, total))),
                f"หา Cut {index + 1}/{total}: {path.name}",
            )

        if has_audio and mode != "B-roll":
            if remove_silence:
                silences = detect_silences(path)
                ranges = speech_segments(duration, silences)
            else:
                ranges = [(0.0, duration)] if duration > 0 else []

            for start, end in ranges:
                talking.append(
                    {
                        "file": path.name,
                        "asset_path": str(path),
                        "source_in": start,
                        "source_out": end,
                        "kind": "TALK",
                        "original_db": 0.0,
                    }
                )

        if mode != "พูดหน้ากล้อง":
            for start, end in broll_windows(duration):
                broll.append(
                    {
                        "file": path.name,
                        "asset_path": str(path),
                        "source_in": start,
                        "source_out": end,
                        "kind": "B-ROLL",
                        "original_db": -14.0 if has_audio else -96.0,
                    }
                )

    if mode == "พูดหน้ากล้อง":
        chosen = talking
    elif mode == "B-roll":
        chosen = broll
    else:
        chosen = _interleave(talking, broll)

    if not chosen:
        # Fallback to a simple montage if speech analysis produced no usable cuts.
        for info in media:
            path = Path(info["path"])
            for start, end in broll_windows(float(info["duration"])):
                chosen.append(
                    {
                        "file": path.name,
                        "asset_path": str(path),
                        "source_in": start,
                        "source_out": end,
                        "kind": "AUTO",
                        "original_db": -14.0 if info["has_audio"] else -96.0,
                    }
                )

    chosen = _limit_segments(chosen, target_seconds)
    if not chosen:
        raise ValueError("วิเคราะห์แล้วไม่พบช่วงวิดีโอที่ใช้งานได้")

    timeline: list[dict] = []
    cursor = 0.0

    for order, segment in enumerate(chosen, start=1):
        duration = max(
            0.05,
            float(segment["source_out"]) - float(segment["source_in"]),
        )
        timeline.append(
            {
                "enabled": True,
                "order": order,
                "timeline_start": cursor,
                "timeline_end": cursor + duration,
                "part": segment["kind"],
                "beat": segment["kind"],
                "file": segment["file"],
                "asset_path": segment["asset_path"],
                "source_in": float(segment["source_in"]),
                "source_out": float(segment["source_out"]),
                "original_db": float(segment["original_db"]),
                "text": "",
                "transition": "Straight Cut",
                "crop_mode": "Fill 9:16",
                "pan_x": 50,
                "review": True,
                "match_status": "AUTO",
            }
        )
        cursor += duration

    if progress:
        progress(80, f"สร้าง Timeline {len(timeline)} ช่วง • {cursor:.1f} วินาที")

    return {
        "version": "3.0",
        "project_type": "autocut",
        "settings": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "video_bitrate": "16M",
            "audio_bitrate": "256k",
            "subtitle_enabled": False,
            "keyword_enabled": False,
            "music_ducking": False,
            "encoder_mode": "Auto GPU",
        },
        "timeline": timeline,
        "voices": [],
        "music": [],
        "sfx": [],
        "media": media,
        "asset_root": str(root),
        "output_path": "",
        "autocut": {
            "mode": mode,
            "target_seconds": target_seconds,
            "remove_silence": remove_silence,
        },
    }
