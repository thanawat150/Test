from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import imageio_ffmpeg


ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class RenderError(RuntimeError):
    pass


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def readable_file(value: str | Path) -> tuple[bool, str]:
    raw = str(value or "").strip()
    if not raw:
        return False, "ยังไม่ได้จับคู่ไฟล์"

    path = Path(raw)
    try:
        if not path.exists():
            return False, "ไม่พบไฟล์"
        if not path.is_file():
            return False, "Path นี้เป็นโฟลเดอร์ ไม่ใช่ไฟล์"
        with path.open("rb") as stream:
            stream.read(1)
        return True, ""
    except PermissionError:
        return False, "เปิดอ่านไม่ได้: Permission denied"
    except OSError as exc:
        return False, f"เปิดอ่านไม่ได้: {exc}"


def db_to_linear(db: float) -> float:
    if db <= -90:
        return 0.0
    return 10 ** (float(db) / 20.0)


def ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def ass_escape(text: str) -> str:
    value = str(text or "")
    # Preserve ASS line-break control (\\N) produced by wrap_thai_text.
    value = value.replace("{", r"\{").replace("}", r"\}")
    value = value.replace("\n", r"\N")
    return value


def wrap_thai_text(text: str, max_chars: int = 34, max_lines: int = 2) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""

    words = text.split(" ")
    if len(words) == 1:
        # Thai often has no spaces. Break conservatively by character count.
        lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
        return r"\N".join(lines[:max_lines])

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    return r"\N".join(lines[:max_lines])


def split_transcript(transcript: str) -> list[str]:
    text = str(transcript or "").strip()
    if not text:
        return []

    parts = [x.strip() for x in re.split(r"\s*/\s*", text) if x.strip()]
    if len(parts) > 1:
        return parts

    parts = [
        x.strip()
        for x in re.split(r"(?<=[.!?…])\s+", text)
        if x.strip()
    ]
    return parts or [text]


def generate_ass(project: dict, path: Path, width: int, height: int) -> None:
    settings = project.get("settings", {})
    subtitle_enabled = bool(settings.get("subtitle_enabled", True))
    keyword_enabled = bool(settings.get("keyword_enabled", True))

    font_size_keyword = max(30, int(height * 0.045))
    font_size_subtitle = max(28, int(height * 0.032))
    margin_keyword = max(100, int(height * 0.13))
    margin_subtitle = max(180, int(height * 0.17))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        (
            f"Style: Keyword,Tahoma,{font_size_keyword},&H00FFFFFF,&H000000FF,"
            f"&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,8,80,80,{margin_keyword},1"
        ),
        (
            f"Style: Subtitle,Tahoma,{font_size_subtitle},&H00FFFFFF,&H000000FF,"
            f"&H00101010,&H96000000,0,0,0,0,100,100,0,0,1,3,1,2,70,70,{margin_subtitle},1"
        ),
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]

    if keyword_enabled:
        previous = None
        for item in project.get("timeline", []):
            if not item.get("enabled", True):
                continue
            text = str(item.get("text", "")).strip()
            if not text or text in {"—", "-", "–"}:
                continue
            # Keep repeated keywords across adjacent cuts, but avoid exact
            # duplicate rows that begin at the same time.
            key = (round(float(item.get("timeline_start", 0)), 2), text)
            if key == previous:
                continue
            previous = key
            start = float(item.get("timeline_start", 0))
            end = float(item.get("timeline_end", start + 1))
            wrapped = wrap_thai_text(text, max_chars=20, max_lines=2)
            lines.append(
                f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Keyword,,0,0,0,,{ass_escape(wrapped)}"
            )

    if subtitle_enabled:
        for voice in project.get("voices", []):
            if not voice.get("enabled", True):
                continue
            start = float(voice.get("start", 0))
            end = float(voice.get("end", start))
            phrases = split_transcript(voice.get("transcript", ""))
            if not phrases or end <= start:
                continue

            duration = end - start
            weights = [max(1, len(re.sub(r"\s+", "", p))) for p in phrases]
            total_weight = sum(weights)
            cursor = start

            for i, (phrase, weight) in enumerate(zip(phrases, weights)):
                if i == len(phrases) - 1:
                    phrase_end = end
                else:
                    phrase_end = cursor + duration * (weight / total_weight)
                wrapped = wrap_thai_text(phrase, max_chars=38, max_lines=2)
                lines.append(
                    f"Dialogue: 2,{ass_time(cursor)},{ass_time(phrase_end)},Subtitle,,0,0,0,,{ass_escape(wrapped)}"
                )
                cursor = phrase_end

    path.write_text("\n".join(lines), encoding="utf-8-sig")


def escape_subtitle_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def probe_has_audio(path: Path) -> bool:
    ok, _ = readable_file(path)
    if not ok:
        return False

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    return "Audio:" in proc.stderr


def _run_process(
    cmd: list[str],
    duration: float | None,
    progress: ProgressCallback | None,
    progress_base: int,
    progress_span: int,
    message: str,
    cancelled: CancelCallback | None,
) -> None:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    tail: list[str] = []
    assert proc.stdout is not None

    for raw in proc.stdout:
        line = raw.strip()
        if line:
            tail.append(line)
            if len(tail) > 60:
                tail.pop(0)

        if progress and duration and line.startswith("out_time_us="):
            try:
                current = int(line.split("=", 1)[1]) / 1_000_000
                fraction = max(0.0, min(1.0, current / duration))
                progress(progress_base + int(progress_span * fraction), message)
            except (ValueError, ZeroDivisionError):
                pass

        if cancelled and cancelled():
            proc.terminate()
            proc.wait(timeout=5)
            raise RenderError("ยกเลิกการ Render แล้ว")

    code = proc.wait()
    if code != 0:
        detail = "\n".join(tail[-20:])
        raise RenderError(f"FFmpeg ทำงานไม่สำเร็จ\n\n{detail}")


def _fill_filter(width: int, height: int, pan_x: float, fps: int, source_duration: float, target_duration: float, transition: str) -> str:
    ratio = max(0.0, min(1.0, pan_x / 100.0))
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}:x='(iw-ow)*{ratio:.4f}':y='(ih-oh)/2'",
        f"fps={fps}",
        "format=yuv420p",
        f"trim=duration={source_duration:.3f}",
        "setpts=PTS-STARTPTS",
        f"tpad=stop_mode=clone:stop_duration={max(0.0, target_duration-source_duration+0.2):.3f}",
        f"trim=duration={target_duration:.3f}",
    ]
    lower = transition.lower()
    if "gentle" in lower and target_duration > 0.3:
        filters.append("fade=t=in:st=0:d=0.12")
    if ("fade out" in lower or "hold" in lower) and target_duration > 0.6:
        filters.append(f"fade=t=out:st={max(0.0,target_duration-0.55):.3f}:d=0.55")
    return ",".join(filters)


def _fit_blur_complex(width: int, height: int, fps: int, source_duration: float, target_duration: float, transition: str) -> str:
    post = [
        f"fps={fps}",
        "format=yuv420p",
        f"trim=duration={source_duration:.3f}",
        "setpts=PTS-STARTPTS",
        f"tpad=stop_mode=clone:stop_duration={max(0.0, target_duration-source_duration+0.2):.3f}",
        f"trim=duration={target_duration:.3f}",
    ]
    lower = transition.lower()
    if "gentle" in lower and target_duration > 0.3:
        post.append("fade=t=in:st=0:d=0.12")
    if ("fade out" in lower or "hold" in lower) and target_duration > 0.6:
        post.append(f"fade=t=out:st={max(0.0,target_duration-0.55):.3f}:d=0.55")

    return (
        "[0:v]split=2[bg0][fg0];"
        f"[bg0]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=24:2[bg];"
        f"[fg0]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        + ",".join(post)
        + "[v]"
    )


def render_video_segments(
    project: dict,
    temp_dir: Path,
    preview: bool,
    progress: ProgressCallback | None,
    cancelled: CancelCallback | None,
) -> list[tuple[dict, Path]]:
    settings = project.get("settings", {})
    scale = 0.5 if preview else 1.0
    width = int(int(settings.get("width", 1080)) * scale)
    height = int(int(settings.get("height", 1920)) * scale)
    width -= width % 2
    height -= height % 2
    fps = int(settings.get("fps", 30))

    enabled = [x for x in project.get("timeline", []) if x.get("enabled", True)]
    if not enabled:
        raise RenderError("ไม่มี Timeline ที่เปิดใช้งาน")

    outputs: list[tuple[dict, Path]] = []
    total = len(enabled)

    for index, item in enumerate(enabled):
        if cancelled and cancelled():
            raise RenderError("ยกเลิกการ Render แล้ว")

        source = Path(item.get("asset_path", ""))
        ok, reason = readable_file(source)
        if not ok:
            raise RenderError(
                f"เปิดไฟล์ Video ไม่ได้: {item.get('file','')}\n"
                f"Path: {item.get('asset_path','') or '(ยังไม่ได้จับคู่)'}\n"
                f"สาเหตุ: {reason}"
            )

        target_duration = max(
            0.05,
            float(item.get("timeline_end", 0)) - float(item.get("timeline_start", 0)),
        )
        source_in = max(0.0, float(item.get("source_in", 0)))
        source_out = max(source_in + 0.05, float(item.get("source_out", source_in + target_duration)))
        source_duration = max(0.05, source_out - source_in)
        output = temp_dir / f"segment_{index:03d}.mp4"

        cmd = [
            ffmpeg_exe(),
            "-hide_banner",
            "-y",
            "-ss",
            f"{source_in:.3f}",
            "-i",
            str(source),
        ]

        crop_mode = str(item.get("crop_mode", "Fill 9:16"))
        if crop_mode.lower().startswith("fit"):
            cmd += [
                "-filter_complex",
                _fit_blur_complex(
                    width,
                    height,
                    fps,
                    source_duration,
                    target_duration,
                    str(item.get("transition", "")),
                ),
                "-map",
                "[v]",
            ]
        else:
            cmd += [
                "-vf",
                _fill_filter(
                    width,
                    height,
                    float(item.get("pan_x", 50)),
                    fps,
                    source_duration,
                    target_duration,
                    str(item.get("transition", "")),
                ),
            ]

        cmd += [
            "-an",
            "-t",
            f"{target_duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if preview else "medium",
            "-crf",
            "24" if preview else "18",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output),
        ]

        base = int(5 + 50 * (index / total))
        span = max(1, int(50 / total))
        _run_process(
            cmd,
            target_duration,
            progress,
            base,
            span,
            f"สร้างภาพ {index + 1}/{total}: {item.get('part','')}",
            cancelled,
        )
        outputs.append((item, output))

    return outputs


def concat_segments(
    segments: list[tuple[dict, Path]],
    temp_dir: Path,
    progress: ProgressCallback | None,
    cancelled: CancelCallback | None,
) -> Path:
    concat_file = temp_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(
            "file '" + str(path.resolve()).replace("\\", "/").replace("'", "'\\''") + "'"
            for _, path in segments
        ),
        encoding="utf-8",
    )
    output = temp_dir / "base_video.mp4"

    cmd = [
        ffmpeg_exe(),
        "-hide_banner",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output),
    ]
    _run_process(cmd, None, progress, 55, 5, "รวม Timeline Video", cancelled)
    if progress:
        progress(60, "รวม Timeline Video เสร็จแล้ว")
    return output


def _audio_filter_for_source(label: str, duration: float, gain_db: float, delay_ms: int) -> str:
    linear = db_to_linear(gain_db)
    return (
        f"{label}aresample=48000,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
        f"apad=pad_dur={duration:.3f},atrim=0:{duration:.3f},"
        f"volume={linear:.8f},adelay={delay_ms}|{delay_ms}"
    )


def build_final_command(
    project: dict,
    base_video: Path,
    ass_path: Path,
    output: Path,
    preview: bool,
) -> tuple[list[str], float]:
    settings = project.get("settings", {})
    total_duration = max(
        [float(x.get("timeline_end", 0)) for x in project.get("timeline", []) if x.get("enabled", True)]
        or [1.0]
    )

    cmd = [ffmpeg_exe(), "-hide_banner", "-y", "-i", str(base_video)]
    audio_filters: list[str] = []
    audio_labels: list[str] = []
    input_index = 1

    # Original location audio from each timeline segment.
    for idx, item in enumerate(project.get("timeline", [])):
        if not item.get("enabled", True):
            continue
        gain = float(item.get("original_db", -20.0))
        source = Path(item.get("asset_path", ""))
        ok, _ = readable_file(source)
        if gain <= -90 or not ok or not probe_has_audio(source):
            continue

        start = float(item.get("timeline_start", 0))
        target_duration = max(0.05, float(item.get("timeline_end", 0)) - start)
        source_in = max(0.0, float(item.get("source_in", 0)))
        source_out = max(source_in + 0.05, float(item.get("source_out", source_in + target_duration)))
        source_duration = min(target_duration, max(0.05, source_out - source_in))

        cmd += ["-ss", f"{source_in:.3f}", "-t", f"{source_duration:.3f}", "-i", str(source)]
        label = f"[{input_index}:a]"
        out_label = f"[orig{idx}]"
        audio_filters.append(
            _audio_filter_for_source(label, target_duration, gain, int(round(start * 1000)))
            + out_label
        )
        audio_labels.append(out_label)
        input_index += 1

    # Voice over.
    for idx, item in enumerate(project.get("voices", [])):
        if not item.get("enabled", True):
            continue
        source = Path(item.get("asset_path", ""))
        ok, _ = readable_file(source)
        if not ok:
            continue

        start = float(item.get("start", 0))
        end = float(item.get("end", start))
        duration = max(0.05, end - start)
        cmd += ["-i", str(source)]
        label = f"[{input_index}:a]"
        out_label = f"[vo{idx}]"
        audio_filters.append(
            _audio_filter_for_source(
                label,
                duration,
                float(item.get("gain_db", 0.0)),
                int(round(start * 1000)),
            )
            + out_label
        )
        audio_labels.append(out_label)
        input_index += 1

    # Music bed. Ducking is approximated conservatively by lowering another 3 dB.
    for idx, item in enumerate(project.get("music", [])):
        if not item.get("enabled", True):
            continue
        source = Path(item.get("asset_path", ""))
        if not source.exists():
            continue

        start = float(item.get("start", 0))
        end = float(item.get("end", total_duration))
        duration = max(0.05, end - start)
        gain = float(item.get("gain_db", -24.0))
        duck_enabled = bool(
            item.get("duck_under_vo", True)
            and settings.get("music_ducking", True)
        )

        cmd += ["-stream_loop", "-1", "-i", str(source)]
        label = f"[{input_index}:a]"
        out_label = f"[music{idx}]"
        fade_out_start = max(0.0, duration - 1.2)

        base_linear = db_to_linear(gain)
        volume_filter = f"volume={base_linear:.8f}"

        if duck_enabled:
            # Guide target: Music ~ -30..-27 dB under VO and ~ -25..-22 dB
            # during breathing/natural-audio moments. Use the editable base gain
            # for no-VO sections and duck another 4 dB only inside VO intervals.
            intervals: list[tuple[float, float]] = []
            for voice in project.get("voices", []):
                if not voice.get("enabled", True):
                    continue
                v_start = max(start, float(voice.get("start", 0)))
                v_end = min(end, float(voice.get("end", 0)))
                if v_end > v_start:
                    intervals.append((v_start - start, v_end - start))

            if intervals:
                checks = "+".join(
                    f"between(t\\,{a:.3f}\\,{b:.3f})"
                    for a, b in intervals
                )
                duck_linear = db_to_linear(gain - 4.0)
                expr = (
                    f"if(gt({checks}\\,0)\\,"
                    f"{duck_linear:.8f}\\,{base_linear:.8f})"
                )
                volume_filter = f"volume='{expr}':eval=frame"

        audio_filters.append(
            f"{label}aresample=48000,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
            f"{volume_filter},afade=t=in:st=0:d=0.6,"
            f"afade=t=out:st={fade_out_start:.3f}:d=1.2,"
            f"adelay={int(round(start*1000))}|{int(round(start*1000))}{out_label}"
        )
        audio_labels.append(out_label)
        input_index += 1

    # Sound effects.
    for idx, item in enumerate(project.get("sfx", [])):
        if not item.get("enabled", False):
            continue
        source = Path(item.get("asset_path", ""))
        if not source.exists():
            continue

        start = float(item.get("start", 0))
        gain = float(item.get("gain_db", -18.0))
        cmd += ["-i", str(source)]
        label = f"[{input_index}:a]"
        out_label = f"[sfx{idx}]"
        linear = db_to_linear(gain)
        audio_filters.append(
            f"{label}aresample=48000,asetpts=PTS-STARTPTS,"
            f"volume={linear:.8f},adelay={int(round(start*1000))}|{int(round(start*1000))}{out_label}"
        )
        audio_labels.append(out_label)
        input_index += 1

    if not audio_labels:
        cmd += ["-f", "lavfi", "-t", f"{total_duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        label = f"[{input_index}:a]"
        audio_filters.append(
            f"{label}atrim=0:{total_duration:.3f},asetpts=PTS-STARTPTS[silent]"
        )
        audio_labels.append("[silent]")

    audio_filters.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=0:normalize=0,"
        f"atrim=0:{total_duration:.3f},alimiter=limit=0.95[aout]"
    )

    subtitles_on = bool(settings.get("subtitle_enabled", True) or settings.get("keyword_enabled", True))
    if subtitles_on:
        subtitle_path = escape_subtitle_path(ass_path)
        video_filter = f"[0:v]subtitles='{subtitle_path}'[vout]"
        filter_complex = ";".join([video_filter] + audio_filters)
        map_video = ["-map", "[vout]"]
    else:
        filter_complex = ";".join(audio_filters)
        map_video = ["-map", "0:v:0"]

    cmd += [
        "-filter_complex",
        filter_complex,
        *map_video,
        "-map",
        "[aout]",
        "-t",
        f"{total_duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast" if preview else "medium",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
    ]

    if preview:
        cmd += ["-b:v", "4M", "-maxrate", "6M", "-bufsize", "8M", "-c:a", "aac", "-b:a", "160k"]
    else:
        bitrate = str(settings.get("video_bitrate", "16M"))
        audio_bitrate = str(settings.get("audio_bitrate", "256k"))
        cmd += [
            "-b:v",
            bitrate,
            "-maxrate",
            "20M",
            "-bufsize",
            "32M",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
        ]

    cmd += [
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    return cmd, total_duration


def preflight(project: dict) -> list[str]:
    problems: list[str] = []
    enabled_timeline = [x for x in project.get("timeline", []) if x.get("enabled", True)]
    if not enabled_timeline:
        problems.append("ไม่มี Timeline ที่เปิดใช้งาน")
        return problems

    previous_end = None
    for i, item in enumerate(enabled_timeline, start=1):
        start = float(item.get("timeline_start", 0))
        end = float(item.get("timeline_end", 0))
        source_in = float(item.get("source_in", 0))
        source_out = float(item.get("source_out", 0))

        if end <= start:
            problems.append(f"Timeline {i}: End ต้องมากกว่า Start")
        if source_out <= source_in:
            problems.append(f"Timeline {i}: Source Out ต้องมากกว่า Source In")
        ok, reason = readable_file(item.get("asset_path", ""))
        if not ok:
            problems.append(
                f"Timeline {i}: {item.get('file','')} — {reason}"
            )
        if previous_end is not None and abs(start - previous_end) > 0.08:
            problems.append(
                f"Timeline {i}: มี Gap/Overlap จากแถวก่อน {start - previous_end:+.2f} วินาที"
            )
        previous_end = end

    for group_name, label in (("voices", "VO"), ("music", "Music"), ("sfx", "SFX")):
        for item in project.get(group_name, []):
            if item.get("enabled", group_name != "sfx"):
                ok, reason = readable_file(item.get("asset_path", ""))
                if not ok:
                    problems.append(
                        f"{label}: {item.get('file','')} — {reason}"
                    )

    return problems


def render_project(
    project: dict,
    output_path: str | Path,
    preview: bool = False,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> Path:
    output = Path(output_path)
    if output.exists() and output.is_dir():
        raise RenderError(
            "Output ที่เลือกเป็นโฟลเดอร์ กรุณาเลือกชื่อไฟล์ .mp4"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    issues = preflight(project)
    if issues:
        raise RenderError("Preflight ไม่ผ่าน:\n- " + "\n- ".join(issues[:30]))

    if progress:
        progress(1, "เริ่ม Render")

    with tempfile.TemporaryDirectory(prefix="MasterEditStudio_") as temp:
        temp_dir = Path(temp)
        segments = render_video_segments(project, temp_dir, preview, progress, cancelled)
        base_video = concat_segments(segments, temp_dir, progress, cancelled)

        settings = project.get("settings", {})
        scale = 0.5 if preview else 1.0
        width = int(int(settings.get("width", 1080)) * scale)
        height = int(int(settings.get("height", 1920)) * scale)
        width -= width % 2
        height -= height % 2

        ass_path = temp_dir / "overlay.ass"
        generate_ass(project, ass_path, width, height)

        cmd, total_duration = build_final_command(
            project,
            base_video,
            ass_path,
            output,
            preview,
        )

        _run_process(
            cmd,
            total_duration,
            progress,
            60,
            39,
            "Mix เสียง + Text + Subtitle + Export",
            cancelled,
        )

    if not output.exists() or output.stat().st_size < 1024:
        raise RenderError("Render เสร็จแต่ไม่พบไฟล์ Output")

    if progress:
        progress(100, f"เสร็จแล้ว: {output.name}")
    return output
