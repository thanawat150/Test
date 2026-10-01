# Sentence Voice Studio

โปรแกรม Windows สำหรับแปลงข้อความเป็นเสียง (Text-to-Speech) และบันทึกเป็น MP3 แบบทีละประโยคหรือหลายประโยคพร้อมกัน

## Version 0.2.0

เวอร์ชันนี้เน้นภาษาไทย การฟัง Preview ที่ง่ายขึ้น และการปรับเสียงให้ฟังเป็นธรรมชาติมากกว่าเดิม

### เสียงและบุคคล

- ไทยแท้: Premwadee (หญิง), Niwat (ชาย), Achara (หญิง)
- Multilingual ที่แนะนำสำหรับภาษาไทย: Ava, Andrew, Emma, Brian
- มีปุ่มโหลด Voice Catalog ออนไลน์เพื่อเลือกเสียงเพิ่มเติม
- ค้นหาเสียงจากชื่อ, เพศ, locale หรือ voice id ได้
- กรองเฉพาะเสียงไทยแท้ / Multilingual / เสียงทั้งหมดได้

### โทนเสียง

Preset ที่มีให้:

- ธรรมชาติ
- อบอุ่น
- เล่าเรื่อง
- สดใส
- จริงจัง
- ชัดเจน / อ่านง่าย
- กำหนดเอง

Preset จะปรับ Rate, Pitch และ Volume ให้อัตโนมัติ และผู้ใช้ปรับต่อเองได้

> หมายเหตุ: edge-tts ไม่รองรับ custom SSML style/emotion แบบเต็มรูปแบบ ดังนั้น preset เหล่านี้เป็นการปรับ prosody เพื่อให้ได้โทนที่เป็นธรรมชาติมากขึ้น ไม่ใช่ emotion model โดยตรง

### จังหวะพูดแบบคน

ใช้สัญลักษณ์ในข้อความ:

- `|` = พักสั้น
- `||` = พักยาว

ตัวอย่าง:

    วันนี้ | เราจะมาพูดเรื่อง AI || เริ่มกันเลย

โปรแกรมจะแปลงเครื่องหมายเหล่านี้เป็นจังหวะ punctuation ก่อนส่งให้ TTS

### ฟังเสียงง่ายขึ้น

- Preview แล้วเล่นในโปรแกรมทันที
- เล่นไฟล์ที่เลือก
- Pause / Resume
- Stop
- Seek bar และเวลาเสียง
- ดับเบิลคลิกรายการที่สร้างแล้วเพื่อเล่นได้

### ตั้งชื่อไฟล์เอง

คอลัมน์ "ชื่อไฟล์ (แก้ได้)" สามารถแก้ได้โดยตรงก่อนสร้างเสียง

ตัวอย่าง:

    เปิดคลิป_AI.mp3
    hook_01.mp3
    scene_03.mp3

ถ้าไม่ใส่ .mp3 โปรแกรมจะเติมให้อัตโนมัติ และจะตัดอักขระที่ Windows ไม่อนุญาตออกให้

ถ้าตั้งชื่อซ้ำใน Batch โปรแกรมจะเติมเลขท้ายเพื่อไม่ให้ไฟล์เดิมถูกเขียนทับ

## โหมดแบ่งข้อความ

- รวมเป็นไฟล์เดียว
- แยกตามบรรทัด
- แยกตามประโยค

แนะนำโหมด "แยกตามบรรทัด" สำหรับงานตัดต่อวิดีโอ เพราะ 1 บรรทัด = 1 ไฟล์เสียง

## หมายเหตุเรื่องอินเทอร์เน็ต

โปรแกรมใช้ edge-tts เพื่อเรียกเสียง Microsoft online TTS จึงต้องมีอินเทอร์เน็ตขณะสร้างเสียง และไม่ต้องใส่ API Key

## รันจาก Source

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python sentence_voice_studio.py

## สร้าง .exe บน Windows

    pip install -r requirements-dev.txt
    pyinstaller --noconfirm --clean --onefile --windowed --name SentenceVoiceStudio --collect-all edge_tts sentence_voice_studio.py

ไฟล์จะอยู่ที่ dist/SentenceVoiceStudio.exe

## GitHub Actions

Workflow จะทดสอบและ build Windows .exe อัตโนมัติ และอัปโหลด Artifact ชื่อ SentenceVoiceStudio-Windows
