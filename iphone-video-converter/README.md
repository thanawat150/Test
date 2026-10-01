# iPhone Video Converter

Windows app สำหรับแปลงวิดีโอจาก iPhone เช่น `.MOV` / HEVC ให้เป็น `.MP4` ที่ระบบ AI และโปรแกรมตัดต่ออ่านได้ง่าย

## Default: AI Compatible MP4

Preset แนะนำจะเข้ารหัสเป็น:

- Container: MP4
- Video: H.264 / AVC (libx264)
- Audio: AAC 192 kbps / 48 kHz
- Pixel format: yuv420p
- Frame rate: Constant 30 fps
- Max height: 1080p
- MP4 faststart

เหตุผลคือไฟล์จาก iPhone อาจเป็น HEVC/H.265, HDR หรือ Variable Frame Rate ซึ่งบาง AI/NLE รองรับไม่สม่ำเสมอ

## Features

- Drag & Drop ไฟล์
- Batch หลายไฟล์
- MOV / MP4 / M4V / AVI / MKV / MTS / M2TS / WebM
- Preset AI Compatible 1080p
- Preset AI Compatible ความละเอียดเดิม
- Presetไฟล์เล็ก
- Presetแปลงเร็ว
- เลือกโฟลเดอร์ปลายทาง
- Progress ต่อไฟล์
- Stop งานที่กำลังแปลง
- FFmpeg ฝังมากับโปรแกรมผ่าน imageio-ffmpeg ไม่ต้องติดตั้ง FFmpeg เอง

## Output naming

เช่น:

    IMG_1234.MOV
    -> IMG_1234_AI.mp4

ถ้ามีไฟล์ชื่อเดิมอยู่แล้ว:

    IMG_1234_AI_2.mp4

## Run source

    py -3.11 -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python iphone_video_converter.py

## Build Windows EXE

    pip install -r requirements-dev.txt
    pyinstaller --noconfirm --clean --onefile --windowed --name iPhoneVideoConverter --collect-all imageio_ffmpeg iphone_video_converter.py

## Note

ถ้าวิดีโอ iPhone เป็นต้นฉบับ HDR และต้องการรักษาสี HDR/แปลงเป็น SDR แบบ tone-map คุณภาพสูง ควรเพิ่ม HDR workflow แยกต่างหากในรุ่นถัดไป เพราะเป้าหมายของ preset ปัจจุบันคือ compatibility สำหรับ AI/editing เป็นหลัก
