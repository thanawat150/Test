from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

st.set_page_config(page_title="AutoCut AI Studio", page_icon="🎬", layout="wide")
st.title("🎬 AutoCut AI Studio")
st.caption("MVP: ตัดช่วงเงียบ + สร้างซับภาษาไทย โดยไม่แก้ไขไฟล์ต้นฉบับ")


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "FFmpeg processing failed")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ไม่พบ FFmpeg กรุณาติดตั้ง FFmpeg และเพิ่มไว้ใน PATH")


def remove_silence(source: Path, output: Path, threshold_db: int, duration: float) -> None:
    # Conservative two-sided silence removal. Natural short pauses remain.
    audio_filter = (
        f"silenceremove=start_periods=1:start_duration={duration}:"
        f"start_threshold={threshold_db}dB:stop_periods=-1:"
        f"stop_duration={duration}:stop_threshold={threshold_db}dB"
    )
    run_command([
        "ffmpeg", "-y", "-i", str(source),
        "-af", audio_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ])


def extract_audio(source: Path, output: Path) -> None:
    run_command([
        "ffmpeg", "-y", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "mp3", "-b:a", "64k",
        str(output),
    ])


def transcribe_to_srt(audio_path: Path) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า OPENAI_API_KEY ในไฟล์ .env")

    client = OpenAI(api_key=api_key)
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
            language="th",
            response_format="srt",
        )
    return result if isinstance(result, str) else str(result)


with st.sidebar:
    st.header("ตั้งค่าการตัด")
    preset = st.selectbox("ระดับการตัด", ["ธรรมชาติ", "สมดุล", "รวดเร็ว"])
    presets = {
        "ธรรมชาติ": (-42, 1.0),
        "สมดุล": (-38, 0.7),
        "รวดเร็ว": (-34, 0.45),
    }
    threshold_db, silence_duration = presets[preset]
    st.write(f"เกณฑ์เสียง: {threshold_db} dB")
    st.write(f"ตัดเมื่อเงียบเกิน: {silence_duration} วินาที")
    make_subtitles = st.checkbox("สร้างซับภาษาไทย", value=True)

uploaded = st.file_uploader("อัปโหลดวิดีโอ", type=["mp4", "mov", "mkv", "avi", "webm"])

if uploaded:
    st.video(uploaded)
    st.info("ไฟล์ต้นฉบับจะไม่ถูกเขียนทับ")

    if st.button("เริ่มตัดต่ออัตโนมัติ", type="primary", use_container_width=True):
        try:
            require_ffmpeg()
            with tempfile.TemporaryDirectory(prefix="autocut_") as temp_dir:
                workdir = Path(temp_dir)
                suffix = Path(uploaded.name).suffix or ".mp4"
                source = workdir / f"source{suffix}"
                edited = workdir / "autocut_output.mp4"
                audio = workdir / "speech.mp3"
                source.write_bytes(uploaded.getbuffer())

                progress = st.progress(0, text="กำลังตรวจสอบวิดีโอ")
                remove_silence(source, edited, threshold_db, silence_duration)
                progress.progress(55, text="ตัดช่วงเงียบเสร็จแล้ว")

                srt_text = ""
                if make_subtitles:
                    extract_audio(edited, audio)
                    progress.progress(75, text="กำลังถอดเสียงภาษาไทย")
                    srt_text = transcribe_to_srt(audio)

                progress.progress(100, text="เสร็จแล้ว")
                edited_bytes = edited.read_bytes()
                st.success("สร้างวิดีโอฉบับตัดต่อสำเร็จ")
                st.video(edited_bytes)
                st.download_button(
                    "ดาวน์โหลดวิดีโอ MP4",
                    edited_bytes,
                    file_name="autocut_output.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )

                if srt_text:
                    st.subheader("ตัวอย่าง Subtitle")
                    st.text_area("แก้ไขข้อความก่อนดาวน์โหลดได้", srt_text, height=280)
                    st.download_button(
                        "ดาวน์โหลด Subtitle SRT",
                        srt_text.encode("utf-8"),
                        file_name="autocut_subtitles_th.srt",
                        mime="application/x-subrip",
                        use_container_width=True,
                    )
        except Exception as exc:
            st.error(str(exc))

st.divider()
st.markdown(
    "**ขั้นถัดไป:** Hook Generator → Story Restructuring → Retention Risk Map → "
    "B-roll Planner → Sound Effects → AI Image/Video Generation"
)
