# Sentence Voice Studio

โปรแกรม Windows สำหรับแปลงข้อความเป็นเสียง (Text-to-Speech) และบันทึกเป็นไฟล์ MP3 แบบทีละประโยคหรือหลายประโยคพร้อมกัน

## ฟังก์ชันใน MVP

- รองรับเสียงไทย Neural: Premwadee (หญิง) และ Niwat (ชาย)
- รองรับเสียง English (US) เพิ่มเติม
- 3 โหมด: รวมเป็นไฟล์เดียว / แยกตามบรรทัด / แยกตามประโยค
- Batch Queue: สร้างหลายไฟล์ต่อเนื่อง
- แก้ข้อความในคิวก่อนสร้างได้
- Preview รายการที่เลือก
- สร้างใหม่เฉพาะรายการที่เลือก
- ปรับความเร็ว, Pitch และ Volume
- เปิดไฟล์และโฟลเดอร์ผลลัพธ์จากโปรแกรม
- สร้างไฟล์ Windows .exe อัตโนมัติด้วย GitHub Actions

## การใช้งาน

1. เปิด SentenceVoiceStudio.exe
2. วางข้อความ
3. เลือกวิธีแบ่งข้อความ
4. กด "สร้างคิวจากข้อความ"
5. เลือกเสียงและปรับค่าเสียง
6. กด "สร้างเสียงทั้งหมด"
7. ไฟล์ MP3 จะอยู่ในโฟลเดอร์ Music/SentenceVoiceStudio โดยค่าเริ่มต้น

แนะนำให้ใช้โหมด "แยกตามบรรทัด" สำหรับงานตัดต่อวิดีโอ เพราะ 1 บรรทัดจะกลายเป็น 1 ไฟล์เสียง

## หมายเหตุเรื่องอินเทอร์เน็ต

MVP ใช้ edge-tts เพื่อเรียกเสียง Neural ของ Microsoft จึงต้องมีอินเทอร์เน็ตขณะสร้างเสียง ไม่ต้องใส่ API Key

## รันจาก Source

เปิด Command Prompt ในโฟลเดอร์นี้แล้วใช้:

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python sentence_voice_studio.py

## สร้าง .exe บนเครื่อง Windows

    pip install -r requirements-dev.txt
    pyinstaller --noconfirm --clean --onefile --windowed --name SentenceVoiceStudio --collect-all edge_tts sentence_voice_studio.py

ไฟล์จะอยู่ที่ dist/SentenceVoiceStudio.exe

## GitHub Actions

Workflow ชื่อ Build Sentence Voice Studio จะทดสอบและ build บน Windows อัตโนมัติเมื่อมีการ push ไปที่ main หรือ feature/sentence-voice-studio

ดาวน์โหลดไฟล์จากหน้า Actions > workflow run > Artifacts > SentenceVoiceStudio-Windows
