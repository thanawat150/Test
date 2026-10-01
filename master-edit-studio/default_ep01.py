from __future__ import annotations

MASTER_HEADERS = [
    "Timeline", "Part", "Video / Footage", "ช่วงที่ใช้ใน Select", "VO",
    "Original Audio", "Music", "Text / Subtitle", "Edit / Transition", "หมายเหตุ",
]

MASTER_TIMELINE = [
    ["00:00.00–00:02.00","Cold Open","04_FIELD_WALK_ROOTS_IMG1309.mp4","00:00 → 00:02","ไม่มี VO","Hero: ปล่อยเสียงจริงเด่น (-4 ถึง -2 dB)","ยังไม่เข้าเพลง","1 POINT","Hard Cut","เปิดด้วยภาพที่รู้สึกถึงพื้นที่จริงทันที"],
    ["00:02.00–00:06.00","Hook / Map","EP01_MAP_SCREEN_RECORD.mp4","เลือก 4 วิที่เห็นจุด/ซูมเข้าได้ชัดที่สุด","VO1 เริ่ม","Mute เสียง Map","Fade in เบา ๆ ~ -28 dB","1 POINT","Cut จาก Field → Map; Thin Swoosh optional","ช่วง Map ยังไม่ได้ล็อกเฟรมแบบเป๊ะ ให้เลือกช่วงดีที่สุดจาก Screen Recording"],
    ["00:06.00–00:10.12","Hook / Field","03_JOURNEY_BOAT_MANGROVE_IMG1303.mp4","00:00 → 00:04.12","VO1 ต่อ","ใต้ VO ~ -22 dB","~ -28 dB","พื้นที่จริง","Cut จาก Map → ของจริง","ให้เสียงน้ำ/เรือยังได้ยินเบา ๆ"],
    ["00:10.12–00:14.12","Hook / Reality","04_FIELD_WALK_ROOTS_IMG1309.mp4","00:02 → 00:06","VO1 จบ","ใต้ VO ~ -22 dB","~ -28 dB","ของจริง","Hard Cut","เน้นความต่างระหว่างจุดบนแผนที่กับสภาพจริง"],
    ["00:14.12–00:18.12","Journey / Road","01_JOURNEY_ROAD_IMG1301.mp4","00:00 → 00:04","VO2 เริ่ม","ใต้ VO ~ -20 dB","~ -27 dB","—","Straight Cut","ภาพเดินทางก่อนเข้าไซต์"],
    ["00:18.12–00:22.12","Journey / Boat","02_JOURNEY_BOAT_IMG1302.mp4","00:00 → 00:04","VO2 ต่อ","ใต้ VO ~ -20 dB","~ -27 dB","นั่งเรือ","Straight Cut","ปล่อยภาพเรือเดินทางต่อเนื่อง"],
    ["00:22.12–00:26.50","Journey / Mangrove","03_JOURNEY_BOAT_MANGROVE_IMG1303.mp4","00:04.12 → 00:08.50","VO2 จบ","ใต้ VO ~ -20 dB","~ -27 dB","เข้าป่า","Straight Cut","ให้เห็นว่าต้องนั่งเรือเข้าไปจริง"],
    ["00:26.50–00:28.50","Breathing Shot","03_JOURNEY_BOAT_MANGROVE_IMG1303.mp4","00:08.50 → 00:10.50","ไม่มี VO","ดันเสียงจริงขึ้น ~ -6 ถึง -3 dB","~ -24 dB","—","ไม่ต้องใส่ Transition","ปล่อย 2 วิให้เสียงเรือ/น้ำหายใจ"],
    ["00:28.50–00:37.50","Field / Roots","04_FIELD_WALK_ROOTS_IMG1309.mp4","00:06 → 00:15","VO3 เริ่ม","ใต้ VO ~ -20 dB","~ -28 dB","โคลน / รากไม้","Straight Cut","ช็อตหลักของช่วงอธิบายความยากหน้างาน"],
    ["00:37.50–00:45.59","Field / Environment","05_FIELD_ENVIRONMENT_IMG1380.mp4","ใช้ทั้งคลิป ~ 8 วิ","VO3 จบ","ใต้ VO ~ -20 dB","~ -28 dB","ของจริง","Gentle Cut","ใช้เป็นภาพบรรยากาศ ไม่ต้องตัดเร็ว"],
    ["00:45.59–00:49.09","Purpose / Start Work","06_NEXT_MEASURE_01_IMG1331.mp4","ใช้ทั้งคลิป ~ 3.5 วิ","VO4 เริ่ม","ใต้ VO ~ -20 dB","~ -27 dB","FIELD DATA","Straight Cut","เริ่มเปิดให้เห็นว่าวันนี้มาทำงานอะไร"],
    ["00:49.09–00:52.09","Purpose / Insert","07_NEXT_MEASURE_02_IMG1332.mp4","00:00 → 00:03","VO4 ต่อ","ใต้ VO ~ -22 dB","~ -27 dB","เริ่มงาน","Cut on Action","ใช้เป็น Insert สั้น ๆ ไม่ต้องอธิบายรายละเอียด"],
    ["00:52.09–00:56.68","Purpose / Measure","08_NEXT_MEASURE_03_IMG1333.mp4","00:00 → 00:04.59","VO4 จบ","ใต้ VO ~ -20 dB","~ -27 dB","—","Straight Cut","ให้ภาพงานจริงเล่าเอง"],
    ["00:56.68–00:58.00","Breathing / Measure","08_NEXT_MEASURE_03_IMG1333.mp4","00:04.59 → 00:05.91","ไม่มี VO","ดันเสียงจริงขึ้น ~ -6 dB","~ -24 dB","—","ไม่ต้องใส่ Transition","พักก่อนเข้าคำถามท้ายคลิป"],
    ["00:58.00–01:02.00","Next EP / Question","08_NEXT_MEASURE_03_IMG1333.mp4","00:05.91 → 00:09.91","VO5 เริ่ม","ใต้ VO ~ -22 dB","~ -28 dB","เก็บอะไรบ้าง?","Straight Cut","เริ่มค้างคำถามเพื่อส่ง EP.2"],
    ["01:02.00–01:04.00","Detail Insert","09_NEXT_MEASURE_04_IMG1334.mp4","00:00 → 00:02","VO5 ต่อ","ใต้ VO ~ -22 dB","~ -28 dB","เก็บอะไรบ้าง?","Cut on Detail","ช็อต Detail แทรก ไม่ต้องอยู่นาน"],
    ["01:04.00–01:06.16","Tease EP.2","10_NEXT_MEASURE_05_IMG1335.mp4","00:00 → 00:02.16","VO5 จบ","ใต้ VO ~ -20 dB","เริ่ม Fade ลง","เก็บอะไรบ้าง?","Straight Cut","จบคำพูดบนภาพวัดต้นไม้"],
    ["01:06.16–01:08.00","End Hold","10_NEXT_MEASURE_05_IMG1335.mp4","00:02.16 → 00:04.00 โดยประมาณ","ไม่มี VO","Hero: -4 ถึง -2 dB","Fade out จนจบ","คลิปหน้าผมพาไปดู","Hold / Fade out","ปล่อยเสียงหน้างานจริง 1–2 วิแล้วจบ"],
]

ASSET_HEADERS = ["ประเภท","ไฟล์ / Asset","อยู่ที่ไหน","ใช้ตรงไหน","วิธีใช้","Priority / สถานะ","Link"]

ASSET_MAP = [
    ["Footage Select","01_JOURNEY_ROAD_IMG1301.mp4","SELECTS_READY","Journey / Road","ใช้ช่วงต้น ~4 วิ เป็นภาพเดินทางก่อนเข้าไซต์","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","02_JOURNEY_BOAT_IMG1302.mp4","SELECTS_READY","Journey / Boat","ใช้ช่วงต้น ~4 วิ ภาพเริ่มนั่งเรือ","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","03_JOURNEY_BOAT_MANGROVE_IMG1303.mp4","SELECTS_READY","Hook + Journey + Breathing","ใช้ 3 ช่วงต่อกัน: 0–4.12 / 4.12–8.50 / 8.50–10.50","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","04_FIELD_WALK_ROOTS_IMG1309.mp4","SELECTS_READY","Cold Open + Hook + Field","ใช้ 0–2 / 2–6 / 6–15 วิ โดยประมาณ","PRIMARY สำคัญมาก / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","05_FIELD_ENVIRONMENT_IMG1380.mp4","SELECTS_READY","Field / Environment","ใช้เกือบทั้งคลิปเป็น breathing / atmosphere","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","06_NEXT_MEASURE_01_IMG1331.mp4","SELECTS_READY","Purpose","ใช้ทั้งคลิป ~3.5 วิ เปิดช่วงเริ่มทำงาน","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","07_NEXT_MEASURE_02_IMG1332.mp4","SELECTS_READY","Purpose / Insert","ใช้ ~3 วิเป็นภาพเสริม","BACKUP แต่ใช้ได้ / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","08_NEXT_MEASURE_03_IMG1333.mp4","SELECTS_READY","Purpose + Next EP","ใช้ต่อเนื่องหลายช่วง เป็นแกนภาพงานวัด","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","09_NEXT_MEASURE_04_IMG1334.mp4","SELECTS_READY","Detail Insert","ใช้ ~2 วิ แทรกช่วงคำถามท้าย","BACKUP แต่ใช้ได้ / พร้อมใช้","เปิดไฟล์"],
    ["Footage Select","10_NEXT_MEASURE_05_IMG1335.mp4","SELECTS_READY","Tease + End Hold","ใช้ ~4 วิสุดท้ายของคลิป","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Map / GIS","EP01_MAP_SCREEN_RECORD.mp4","04_MAP_GIS","00:02–00:06","เลือก 4 วิที่เห็นจุดหรือการซูมเข้าได้ชัดที่สุด; Mute เสียง Map","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Voice Over","01_VO_HOOK.mp3","01_VOICE_OVER","00:02–00:14.12","ปกติเวลาดูแผนที่ มันก็เหมือนเป็นแค่จุดหนึ่งจุด / แต่พอมาลงพื้นที่จริง... โห มันไม่ได้ง่ายแบบนั้นเลย","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Voice Over","02_VO_JOURNEY.mp3","01_VOICE_OVER","00:14.12–00:26.50","อย่างจุดที่ผมไปเจอมา / ต้องนั่งเรือเข้าไปก่อน แล้วก็เดินต่อเข้าไปอีก / กว่าจะถึงจุดที่เราจะทำงานจริง ๆ เหนื่อยสุด ๆ","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Voice Over","03_VO_FIELD.mp3","01_VOICE_OVER","00:28.50–00:45.59","พอเข้ามาถึงพื้นที่... มีทั้งโคลน ทั้งรากไม้... ดูในแผนที่ เราไม่เห็นอะไรพวกนี้เลย","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Voice Over","04_VO_PURPOSE.mp3","01_VOICE_OVER","00:45.59–00:56.68","แล้ววันนี้ที่ผมเข้ามา หลัก ๆ คือเรามาเก็บข้อมูลต้นไม้ในพื้นที่ / พอมาถึงแล้ว ถึงจะเริ่มทำงานกันจริง ๆ","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Voice Over","05_VO_NEXT_EP.mp3","01_VOICE_OVER","00:58.00–01:06.16","แต่จริง ๆ คำว่าเก็บข้อมูลต้นไม้เนี่ย... เขาเก็บอะไรกันบ้าง? เดี๋ยวคลิปหน้าผมพาไปดู","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["Music","EP01_MUSIC_MAIN.mp3","03_MUSIC","ประมาณ 00:02–01:08","เข้าเบา ๆ หลัง Cold Open; ใต้ VO ~ -28 ถึง -27 dB; ช่วงไม่มี VO ~ -24 dB; Fade out ท้าย","PRIMARY / พร้อมใช้","เปิดไฟล์"],
    ["SFX","Interface Click","SFX กลางของ Satun","Map / Point","ใช้ได้ตอน Pin/Point ปรากฏ 1 ครั้ง","OPTIONAL","286"],
    ["SFX","Thin Swoosh","SFX กลางของ Satun","Map → Field","ใช้ได้ 1 ครั้งตอนตัดจาก Map ไปภาพจริง","OPTIONAL","286"],
    ["SFX","Cinematic Low Hit","SFX กลางของ Satun","Hook","ถ้าต้องการเน้นคำว่า 'ของจริง' ใช้เบามาก","OPTIONAL","286"],
    ["SFX","Swoosh Riser Reverb","SFX กลางของ Satun","Purpose","ไม่จำเป็น; ใช้ได้เฉพาะถ้าจังหวะเข้า FIELD DATA ยังแบน","OPTIONAL","286"],
    ["SFX","River Motor Boat Jungle Cruise","SFX กลางของ Satun","—","ไม่ใช้ เพราะ Original Audio ของเรือดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["SFX","Small Boat Engine","SFX กลางของ Satun","—","ไม่ใช้ เพราะ Original Audio ของเรือดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["SFX","Boat on River","SFX กลางของ Satun","—","ไม่ใช้ เพราะ Original Audio ของเรือดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["SFX","Leaves Rustling","SFX กลางของ Satun","—","ไม่ใช้เป็นหลัก เพราะเสียงป่าจริงดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["SFX","Forest Ambience","SFX กลางของ Satun","—","ไม่ใช้เป็นหลัก เพราะเสียงป่าจริงดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["SFX","Footsteps on Mud","SFX กลางของ Satun","—","ไม่ใช้เป็นหลัก เพราะเสียงเดินจริงดีอยู่แล้ว","ไม่ใช้ EP1","286"],
    ["Working File","MP4_WORKING","02_FOOTAGE_SELECTS/MP4_WORKING","—","ไม่ต้องลากเข้า Timeline ถ้ามี SELECTS_READY แล้ว; เก็บไว้เป็น working copy","สำรอง","เปิดโฟลเดอร์"],
    ["Final Select Folder","SELECTS_READY","02_FOOTAGE_SELECTS/SELECTS_READY","ทุกช่วง Footage","ใช้โฟลเดอร์นี้เป็นแหล่ง Footage หลักตอนตัดต่อ","ใช้จริง","เปิดโฟลเดอร์"],
]

TRACK_HEADERS = ["Layer / Track","ใส่อะไร","ตำแหน่ง / ช่วง","ระดับเริ่มต้น","กฎหลัก","สิ่งที่ต้องทำ","หมายเหตุ"]

TRACK_SETUP = [
    ["V1 – Main Video","Footage Select 01–10","ตาม Master Timeline","เต็มเฟรม 9:16","ใช้ภาพจริงเป็นแกน","Crop จาก 16:9 → 9:16 โดยให้ Subject อยู่กลาง; ถ้า Subject เคลื่อน ให้ Keyframe Pan","อย่าเร่งตัดมากเกินไป"],
    ["V2 – Map / Overlay","EP01_MAP_SCREEN_RECORD.mp4","00:02–00:06","เต็มเฟรมหรือ Fit แบบไม่ให้ข้อมูลสำคัญหาย","Map ใช้สั้น ๆ เพื่อเล่า 'จุดบนแผนที่'","Mute เสียง Map; ถ้าแนวนอนไม่พอดี 9:16 ใช้ Crop หรือ Blur Background แบบพอดี","ไม่ต้องใส่กราฟิกเยอะ"],
    ["V3 – Text On Screen","1 POINT / พื้นที่จริง / ของจริง / นั่งเรือ / เข้าป่า / โคลน / รากไม้ / FIELD DATA / เริ่มงาน / เก็บอะไรบ้าง?","ตาม Timeline","2–5 คำต่อครั้ง","Text เป็น Keyword ไม่ใช่ Subtitle ซ้ำทั้งประโยค","วางใน Safe Zone ไม่ชน UI TikTok/Reels","ใช้ฟอนต์ไทยอ่านง่าย"],
    ["V4 – Subtitle","Subtitle จาก VO ทั้ง 5 ไฟล์","ช่วงที่มี VO","2 บรรทัดสูงสุด","อ่านง่ายและตรงเสียงพูด","วางล่างกลางแต่ยกขึ้นจากขอบล่างประมาณ 15–20%","ไม่ต้องใส่ Subtitle ช่วงเสียงธรรมชาติอย่างเดียว"],
    ["A1 – Original Audio","เสียงจาก Footage","ตลอดคลิป","ใต้ VO: -22 ถึง -20 dB / ไม่มี VO: -6 ถึง -2 dB","Original Audio เป็น Hero","อย่าปิดเสียงเรือ น้ำ ป่า กิ่งไม้ เท้า และงานภาคสนาม","ปรับตามหูจริง ไม่ต้องยึด dB ตายตัว"],
    ["A2 – Voice Over","VO1–VO5","ตาม Master Timeline","ให้ชัดที่สุด; Peak ประมาณ -6 ถึง -3 dB","VO เป็นแกนเนื้อเรื่อง","ใช้ Fade สั้น 2–4 frames ถ้ามี click","ห้าม Music กลบคำพูด"],
    ["A3 – Music","EP01_MUSIC_MAIN.mp3","00:02–01:08","ใต้ VO: -30 ถึง -27 dB / ไม่มี VO: -25 ถึง -22 dB","Music เป็นพื้น ไม่ใช่พระเอก","Fade in หลัง Cold Open และ Fade out ท้าย","ถ้าเพลงรบกวนเสียงธรรมชาติ ให้ลดลงอีก"],
    ["A4 – SFX Optional","Interface Click / Thin Swoosh / Low Hit","เฉพาะ Map/Transition","ประมาณ -20 ถึง -14 dB แล้วแต่ไฟล์","ใช้ให้น้อย","ใช้ 0–3 จุดทั้งคลิปพอ","ถ้า Original Audio ดีแล้ว ไม่ต้องใส่"],
    ["Project","Canvas / Sequence","ทั้งโปรเจกต์","1080 × 1920 (9:16)","Vertical Short-form","ตั้ง Sequence เป็น 9:16 ก่อนวาง Footage","Source Footage เดิมเป็น 1920×1080 landscape"],
    ["Project","Frame Rate","ทั้งโปรเจกต์","คงตาม Source; ถ้าต้องเลือก fixed ให้ใช้ 30 fps","อย่าเปลี่ยน FPS ไปมา","ตรวจ Project Settings ก่อนเริ่ม Export","ถ้า Source เป็น 60fps และต้อง Slow motion ค่อยใช้เฉพาะจุด"],
    ["Export","Video Codec","Final","H.264 / MP4","เน้น compatibility","1080×1920, High Quality, bitrate ประมาณ 12–20 Mbps","ไม่ต้องอัปสเกลเกิน 1080×1920"],
    ["Export","Audio","Final","AAC 48 kHz / 192–320 kbps","เสียงต้องชัดบนมือถือ","ตรวจ Peak ไม่ Clip","ฟังด้วยหูฟังและลำโพงมือถือก่อนโพสต์"],
    ["Final Check","ก่อน Export","ทั้งคลิป","—","Story > Effect","ดู 1 รอบแบบปิดเสียงเพื่อตรวจภาพ และ 1 รอบแบบไม่มองจอเพื่อตรวจเสียง","ความยาวเป้าหมายประมาณ 68 วิ; ยืด/หด 1–3 วิได้ตามจังหวะจริง"],
]


LATEST_SFX_BY_TIMELINE_ROW = [
    "—",
    "Interface Click.mp3 @ 00:02.00 | -18 ถึง -14 dB | 1 ครั้งตอน Point/Pin ปรากฏ",
    "Thin Swoosh.mp3 @ 00:06.00 | -18 ถึง -14 dB | คร่อมรอยตัด Map → Field",
    "Cinematic Low Hit.mp3 @ 00:10.12 | -22 ถึง -18 dB | เบามาก เน้นคำว่า “ของจริง”",
    "—", "—", "—", "—", "—", "—",
    "Swoosh Riser Reverb.mp3 @ ~00:45.5 | -20 ถึง -16 dB | OPTIONAL ถ้าจังหวะเข้า FIELD DATA ยังแบน",
    "—", "—", "—", "—", "—", "—", "—",
]

LATEST_SFX_ASSET_OVERRIDES = {
    "Interface Click": [
        "SFX", "Interface Click", "EP1/05_EDIT_ASSETS/05_SFX", "00:02.00",
        "ใส่ 1 ครั้งตอน Point/Pin บน Map ปรากฏ; ประมาณ -18 ถึง -14 dB",
        "RECOMMENDED", "เปิดไฟล์",
    ],
    "Thin Swoosh": [
        "SFX", "Thin Swoosh", "EP1/05_EDIT_ASSETS/05_SFX", "00:06.00",
        "วางคร่อมรอยตัด Map → Field เล็กน้อย; ประมาณ -18 ถึง -14 dB",
        "RECOMMENDED", "เปิดไฟล์",
    ],
    "Cinematic Low Hit": [
        "SFX", "Cinematic Low Hit", "EP1/05_EDIT_ASSETS/05_SFX", "00:10.12",
        "ใช้เบามากตอนเข้า 'ของจริง'; ประมาณ -22 ถึง -18 dB",
        "RECOMMENDED เบา ๆ", "เปิดไฟล์",
    ],
    "Swoosh Riser Reverb": [
        "SFX", "Swoosh Riser Reverb", "EP1/05_EDIT_ASSETS/05_SFX", "~00:45.5",
        "ก่อนเข้า FIELD DATA; ใช้เฉพาะถ้าจังหวะยังแบน; ประมาณ -20 ถึง -16 dB",
        "OPTIONAL", "เปิดไฟล์",
    ],
}

LATEST_A4_TRACK = [
    "A4 – SFX",
    "Interface Click / Thin Swoosh / Cinematic Low Hit / Swoosh Riser Reverb",
    "00:02 / 00:06 / 00:10.12 / ~00:45.5",
    "Click,Swoosh: -18 ถึง -14 dB | Low Hit: -22 ถึง -18 dB | Riser: -20 ถึง -16 dB",
    "ใช้เป็น Accent เท่านั้น; Original Audio ยังเป็นหลัก",
    "Click ตอน Point/Pin → Swoosh คร่อม Map→Field → Low Hit เบามากตอน “ของจริง” → Riser ใช้เฉพาะถ้าเข้า FIELD DATA ยังแบน",
    "3 ตัวแรกแนะนำ; Riser เป็น OPTIONAL และถ้าเสียงจริงพอดีแล้วไม่ต้องใส่",
]


def default_project() -> dict:
    # Keep the embedded default synchronized with the latest Drive Guide.
    # The original constants remain readable, while this patch adds the latest
    # SFX column and the updated SFX/track instructions.
    master_headers = list(MASTER_HEADERS)
    if "SFX" not in master_headers:
        master_headers.insert(7, "SFX")

    master_timeline = []
    for index, source_row in enumerate(MASTER_TIMELINE):
        row = list(source_row)
        if len(row) == 10:
            row.insert(7, LATEST_SFX_BY_TIMELINE_ROW[index])
        master_timeline.append(row)

    asset_map = []
    for source_row in ASSET_MAP:
        row = list(source_row)
        if len(row) > 1 and row[0] == "SFX" and row[1] in LATEST_SFX_ASSET_OVERRIDES:
            row = list(LATEST_SFX_ASSET_OVERRIDES[row[1]])
        asset_map.append(row)

    track_setup = []
    for source_row in TRACK_SETUP:
        row = list(source_row)
        if row and str(row[0]).startswith("A4"):
            row = list(LATEST_A4_TRACK)
        track_setup.append(row)

    return {
        "master_headers": master_headers,
        "master_timeline": master_timeline,
        "asset_headers": list(ASSET_HEADERS),
        "asset_map": asset_map,
        "track_headers": list(TRACK_HEADERS),
        "track_setup": track_setup,
    }
