# Video Segment Cutter

Windows .exe สำหรับอ่านแผนตัดวิดีโอจาก Excel ให้ผู้ใช้ตรวจสอบก่อน แล้วจึงตัดเฉพาะช่วงที่ต้องการเป็น MP4 สำหรับ AI / โปรแกรมตัดต่อ

## Workflow

1. เปิด Excel
2. เลือก Sheet
3. โปรแกรมแสดงข้อมูล Excel ดิบทั้งหมดก่อน
4. โปรแกรมเดาแถว Header และคอลัมน์ RAW / ช่วงเวลา / Start / End / Purpose / Priority
5. ผู้ใช้ตรวจหรือเปลี่ยนการจับคู่คอลัมน์
6. กดนำข้อมูลไป Cut Plan
7. แก้ RAW / Start / End / Purpose / Priority ได้ใน Cut Plan
8. เลือกโฟลเดอร์วิดีโอ RAW
9. โปรแกรมจับคู่ตามชื่อไฟล์และแสดง พบ/ไม่พบ/ซ้ำ
10. กดตรวจสอบก่อนตัด
11. กดยืนยันอีกครั้งก่อนเริ่ม FFmpeg

โปรแกรมจะไม่ตัดวิดีโอทันทีที่เปิด Excel

## Excel formats

รองรับ:

- .xlsx
- .xls
- .xlsb
- .ods

อ่านด้วย python-calamine

รองรับโครงสร้างเวลา 2 แบบ:

- คอลัมน์เดียว: 00:01.5 → 00:08.5
- แยก Start / End

## Cut Plan

คอลัมน์หลัก:

- ใช้
- RAW
- Start
- End
- ความยาว
- เก็บไว้เพื่อ
- Priority
- ไฟล์วิดีโอจริง
- Match
- Output
- สถานะ
- Progress

สามารถแก้ RAW / Start / End / Purpose / Priority ก่อนตัดได้

## Source matching

จับคู่ตามชื่อไฟล์จริงแบบ case-insensitive ก่อน เช่น:

    01_JOURNEY_ROAD_IMG1301.MOV

ถ้า extension ต่างกัน จะลองจับคู่จากชื่อฐานไฟล์อีกครั้ง

## Output

ชื่อ Output ยึดตามชื่อไฟล์นำเข้า แต่เปลี่ยนเป็น .mp4:

    01_JOURNEY_ROAD_IMG1301.MOV
    -> 01_JOURNEY_ROAD_IMG1301.mp4

Default output folder:

    <RAW folder>\CUT_MP4

Preset แนะนำ:

- H.264 / AVC
- AAC
- yuv420p
- CFR 30fps
- 1080p maximum
- MP4 faststart

## Safety

- มี Preview Excel ก่อน
- มี Preflight validation
- Start ต้องน้อยกว่า End
- RAW ต้องจับคู่กับไฟล์จริง
- มี confirmation ก่อนเริ่ม
- ถ้า Output ชื่อซ้ำ จะถามก่อนเขียนทับ
- ไฟล์ RAW ต้นฉบับไม่ถูกแก้ไข

## Build Windows EXE

    pip install -r requirements-dev.txt
    pyinstaller --noconfirm --clean --onefile --windowed --name VideoSegmentCutter --collect-all imageio_ffmpeg --collect-all python_calamine video_segment_cutter.py
