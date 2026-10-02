# AutoCut Studio 3.0

โปรแกรมตัดต่อวิดีโออัตโนมัติแบบ **ไม่ต้องใช้ Excel Guide**

Workflow:

**เลือกโฟลเดอร์วิดีโอ → AUTO CUT → ตรวจ Rough Cut → Preview → Export**

## Auto Cut Modes

- **ผสม** — ใช้ช่วงพูดเป็นแกนและแทรก B-roll
- **พูดหน้ากล้อง** — เน้นคลิปที่มีเสียงพูดและตัด silence
- **B-roll** — สร้าง montage จากช่วงสั้น ๆ ของแต่ละคลิป

## Target Length

- Auto
- 30 วินาที
- 60 วินาที
- 90 วินาที

## Silence Detection

ใช้ FFmpeg silencedetect ตรวจช่วงเงียบจากคลิปที่มี audio แล้วสร้าง speech segments อัตโนมัติ

## Auto Timeline

หลัง AUTO CUT โปรแกรมสร้าง Timeline ต่อเนื่องให้อัตโนมัติ พร้อม:

- Type: TALK / B-ROLL / AUTO
- Timeline Start / End
- Source Video
- Source In / Out
- Length
- Original Audio dB
- Status

ผู้ใช้สามารถ:

- เปิด Source
- เปลี่ยนคลิป
- แก้ Src In / Src Out
- ปิดบางช่วง
- ปรับเสียง Original dB

## Render

- Preview
- Final MP4
- Auto GPU: NVIDIA / Intel / AMD / CPU fallback
- Final mux ใช้ stream copy เพื่อลด re-encode รอบสุดท้าย

## Scope

AutoCut 3.0 เป็น rough-cut engine แบบ local-first และไม่เรียก cloud AI ภายนอก

ตอนนี้การเลือกช่วงอัตโนมัติใช้:
- audio presence
- silence detection
- clip duration
- B-roll windows
- target duration

ยังไม่ได้ใช้ computer vision วิเคราะห์ว่าเฟรมไหนสวย/สั่น/เบลอ หรือ speech-to-text เพื่อเข้าใจเนื้อหาคำพูด
