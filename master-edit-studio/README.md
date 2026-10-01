# Master Edit Studio

## Version 1.0.1

- แก้ `Permission denied` จาก Asset Path ว่างที่เดิมถูกตีความเป็นโฟลเดอร์ปัจจุบัน
- Preflight ตรวจว่า Asset ต้องเป็นไฟล์จริงและเปิดอ่านได้ ก่อนส่งเข้า FFmpeg
- รองรับกรณี Google Drive/OneDrive placeholder หรือไฟล์ที่ยังไม่มีสิทธิ์อ่าน โดยแจ้งชื่อ Asset ก่อน Render
- เพิ่มปุ่ม **เคลียร์หน้า** สำหรับล้าง Timeline / VO / Music / SFX / Asset Root / Output โดยไม่ลบไฟล์ต้นฉบับ


Windows `.exe` สำหรับประกอบวิดีโอตาม **EP01 Master Edit Guide** โดยอ่าน Excel เป็น Edit Blueprint แล้วให้แก้ค่าทั้งหมดก่อน Render

## Source of truth

โปรแกรม sync ค่า Default กับ Guide ล่าสุดที่อยู่ในโฟลเดอร์ Drive ของ EP01

Guide ล่าสุดมี:

- Master Timeline 18 ช่วง ประมาณ 68 วินาที
- Video / Map
- Original Audio
- Voice Over 5 ไฟล์
- Music
- SFX
- Keyword Text
- Transition
- Asset Map
- Track Setup
- Vertical 1080×1920 / 30 fps
- H.264 MP4 + AAC

## SFX จาก Guide ล่าสุด

Default:

- Interface Click.mp3 @ 00:02.00 — Recommended
- Thin Swoosh.mp3 @ 00:06.00 — Recommended
- Cinematic Low Hit.mp3 @ 00:10.12 — Recommended
- Swoosh Riser Reverb.mp3 @ ~00:45.5 — Optional

ผู้ใช้เปิด/ปิด เปลี่ยนเวลา และ Gain dB ได้ในโปรแกรม

## Workflow

1. เปิดโปรแกรม — ได้ EP01 Guide ล่าสุดเป็น Default
2. หรือกด **เปิด Excel Guide** เพื่อโหลดไฟล์ Excel เวอร์ชันใหม่
3. เลือกโฟลเดอร์ Assets ที่มี Video / VO / Map / Music / SFX
4. โปรแกรม Scan แบบ Recursive และจับคู่ตามชื่อไฟล์
5. ตรวจ Timeline
6. แก้ Timeline Start/End, Source In/Out, Crop, Pan X, Original Audio, Text, Transition
7. ตรวจ VO / Music / SFX
8. กด Preflight
9. Render Preview 540×960
10. ปรับจังหวะ
11. Render Final 1080×1920

## Editable Timeline

แก้ได้:

- เปิด/ปิดแต่ละช่วง
- Timeline Start / End
- Part
- Video filename
- Source In / Out
- Crop mode
  - Fill 9:16
  - Fit + Blur
- Pan X 0–100%
- Original Audio dB
- Keyword Text
- Transition
- SFX Guide instruction

ช่วงที่ Excel เขียนแบบไม่ล็อกเฟรม เช่น “เลือก 4 วิที่เห็นจุด/ซูมเข้าได้ชัดที่สุด” จะถูก Mark ว่า **Review**

## Audio

### Original Audio

ดึงจาก Footage ตามแต่ละช่วงและใช้ dB จาก Guide

### Voice Over

ใช้เวลาและ Transcript จาก Asset Map

Transcript ถูกใช้สร้าง Subtitle อัตโนมัติ โดยแบ่ง phrase จากเครื่องหมาย `/` ใน Guide

### Music

วางตามเวลาใน Guide, Fade in/out และลด Gain เพิ่มเมื่อเปิด Duck Under VO

### SFX

เปิด/ปิดและแก้เวลา/Gain ได้ทีละตัว

## Text / Subtitle

ใช้ ASS/libass ของ FFmpeg

- Keyword อยู่ Safe Zone ด้านบน
- Subtitle อยู่ด้านล่างและยกขึ้นจาก UI zone
- ใช้ Tahoma บน Windows เพื่อรองรับภาษาไทย
- สามารถปิด Keyword หรือ Subtitle ก่อน Render ได้

## Asset matching

โปรแกรมไม่บังคับชื่อโฟลเดอร์ แต่จะ Scan ทุก subfolder

ตัวอย่างโครงสร้างที่รองรับ:

    EP01/
      01_VIDEO/
      02_VOICE_OVER/
      03_MAP/
      04_MUSIC/
      05_SFX/
      06_GUIDE/

จับคู่ตามชื่อเต็มก่อน และลองจับคู่ด้วยชื่อไฟล์ไม่รวมนามสกุลอีกครั้ง

## Render

Final:

- 1080 × 1920
- 30 fps
- H.264 High Profile
- yuv420p
- AAC 48 kHz
- Bitrate Default 16 Mbps
- MP4 faststart

Preview:

- 540 × 960
- Veryfast encode
- Bitrate ต่ำลงเพื่อดูจังหวะเร็วขึ้น

## Safety / QA

ก่อน Render โปรแกรมตรวจ:

- Asset ที่เปิดใช้งานครบหรือไม่
- Timeline End > Start
- Source Out > Source In
- Timeline มี Gap/Overlap หรือไม่
- VO / Music / SFX ที่เปิดอยู่มีไฟล์จริงหรือไม่

ไฟล์ต้นฉบับไม่ถูกแก้ไข

## Build Windows

    pip install -r requirements-dev.txt

    pyinstaller --noconfirm --clean --onefile --windowed ^
      --name MasterEditStudio ^
      --collect-all imageio_ffmpeg ^
      --collect-all python_calamine ^
      master_edit_studio.py
