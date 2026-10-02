# GuideCut Studio 2.0

โปรแกรมตัดต่อวิดีโอแบบ **Guide-driven** สำหรับ Content Guide 1–2 นาที

แนวคิดหลัก:

**Guide Excel → Media → Auto Build → Human Review → Preview → Export**

## รองรับ Content Guide จากระบบปัจจุบัน

อ่าน Sheet:

- Overview
- Script Flow
- Visual Plan
- Checklist

ไม่ใช้ 16-Angle Library ในหน้าตัดต่อ เพราะเป็นข้อมูลคิดคอนเทนต์ ไม่ใช่ข้อมูล Render

## Master Timeline

เมื่อเปิด Guide โปรแกรมสร้าง Story Blocks อัตโนมัติ เช่น:

- Hook
- Context
- Core
- Payoff
- Bridge

แต่ละแถวมี:

- Timeline Start / End
- Video
- Source In / Out
- Visual / Proof
- Keyword
- Match

## Auto Build

เลือกโฟลเดอร์ Media แล้วกด **Auto Build**

โปรแกรมจะ:

1. Scan วิดีโอทุก subfolder
2. พยายามจับชนิดภาพจากชื่อไฟล์กับ Visual / Proof
3. ใส่วิดีโอให้ Story Blocks
4. สร้าง Rough Cut
5. Mark ทุกแถวให้ผู้ใช้ตรวจ Source In / Out ก่อน Export

Auto Build เป็น draft ไม่ใช่ final editorial decision

## Coverage

แสดงว่า Hook / Context / Core / Payoff / Bridge มี Media พร้อมแล้วหรือยัง

## Manual Review

- เปลี่ยนคลิปแถวที่เลือก
- เปิด Source ด้วย player ของ Windows
- แก้ Src In / Src Out
- แก้ Keyword
- ปิดบางแถวได้

## Render

- Preview
- Final MP4
- Auto GPU: NVIDIA / Intel / AMD / CPU fallback
- Keyword burn-in
- Subtitle ไม่ burn-in
- Export .srt แยก
- Final stage ใช้ stream-copy video + audio mux เพื่อลดเวลา export

## Output

ตัวอย่าง:

    GuideCut_Output.mp4
    GuideCut_Output.srt

## Legacy

ยังเปิด Master Edit Guide รุ่นเดิมได้ best-effort แต่หน้าหลักและ Auto Build ออกแบบมาสำหรับ Content Guide รุ่นใหม่เป็นหลัก
