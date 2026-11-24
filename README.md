# worm_labeler — ลาเบลหนอนผ่าน browser (github.io)

เวอร์ชันเว็บของ `code/gui/worm_label_app_v2.py` ของโปรเจกต์ `worm` (อยู่บน Lanta) — ผู้ลาเบลเปิดลิงก์เดียว ไม่ต้องลงโปรแกรม ไม่ต้องรับไฟล์ภาพ
ผลลาเบลถูกส่งเข้า **Google Sheet** ของผู้ดูแลอัตโนมัติ แล้วดึงกลับมาเป็น CSV รูปแบบเดิม (`Class,Filename,file_hash`)

```
Lanta/เครื่องคุณ                 GitHub Pages (public)             ผู้ลาเบล              Google Sheet
roi_mask/*.npy + roi_src/*.npy ─► tools/export_web_pack.py ─► repo worm_labeler_packs: packs/<pack>/ ─► เปิดลิงก์ ─► POST ─► tab "labels"
                                                                                                    │
                          ground_truth_worms_<pack>_<ชื่อ>.csv ◄─ tools/collect_labels.py ◄───────────────┘
```

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `docs/index.html` | แอปลาเบล (ไฟล์เดียว ไม่มี dependency/CDN) |
| `docs/config.json` | `endpoint` (URL ของ Apps Script) + `token` — ว่าง = ปิดการส่ง ใช้ปุ่ม Download CSV แทน |
| `tools/export_web_pack.py` | แปลงโฟลเดอร์ `roi_mask`/`roi_src` (.npy) → JPG + PNG overlay + `manifest.json` |
| `tools/apps_script.gs` | ตัวรับข้อมูลใส่ Google Sheet |
| `tools/collect_labels.py` | ดึงผลจาก Sheet → CSV ต่อ (pack, ผู้ลาเบล) |

## 1. ทำ pack (รันบนเครื่องที่มี roi_mask/roi_src — Lanta env `segmentation` หรือ miniforge local มี numpy+Pillow)

```powershell
& "D:\DEV\miniforge-pypy3\python.exe" -I tools\export_web_pack.py --src-dir <โฟลเดอร์ที่มี roi_mask และ roi_src> --site .\docs --pack nb01 --limit 3000
```

- `--part 1/2` แบ่งงานให้หลายคน: ส่งออกเฉพาะชิ้นที่ 1 จาก 2 (แบ่งต่อเนื่องตามชื่อไฟล์) — รันซ้ำด้วย `--part 2/2 --pack <ชื่ออื่น>` (ใช้ `--site` เดียวกัน `index.json` จะรวมให้) แล้วแจกลิงก์คนละ pack
- `--skip-labelled labels.csv` ข้ามภาพที่ CSV เดิมลาเบลแล้ว (เทียบ hash เหมือนโปรแกรมเดิม), `--list list.txt` เลือกเฉพาะบางไฟล์
- ขนาดจริง ~50 KB/รูป (crop 505px → ลดเหลือ 450px เท่าที่โปรแกรมเดิมแสดง) → 3,000 รูป ≈ 150 MB
  **GitHub Pages จำกัดเว็บ ~1 GB** → แบ่ง pack ละ ≤ 3,000–5,000 รูป และลบ pack ที่ลาเบลเสร็จแล้วออกจาก repo (ประวัติ git ยังเก็บภาพเก่าอยู่ — ถ้า repo โตเกิน ให้ squash/สร้าง repo ใหม่)
- `file_hash` = md5 ของไฟล์ `roi_mask/*.npy` (เหมือน `worm_label_app_v2.py`) → CSV ที่ได้ merge เข้า pipeline เดิมได้เลย

## 2. ขึ้น GitHub Pages

```powershell
git init -b main
git add .
git commit -m "worm web labeler + pack nb01"
git remote add origin https://github.com/<user>/worm-label.git   # repo public ใหม่
git push -u origin main
```

GitHub → repo → Settings → Pages → Source = `main` / **`/docs`**. ลิงก์ที่ส่งให้ผู้ลาเบล:

```
https://<user>.github.io/worm-label/?pack=nb01&u=somchai
```

- `pack` = ชื่อชุด, `u` = ชื่อผู้ลาเบล (ถ้าไม่ใส่ จะถามตอนเปิดครั้งแรก) — **แต่ละคนใช้ชื่อไม่ซ้ำ** เพราะผลแยกตามชื่อ
- ไม่ใส่ `pack` → หน้าเลือกชุดจาก `packs/index.json`

## 3. ตั้งค่า Google Sheet (ครั้งเดียว)

1. สร้าง Google Sheet ใหม่ → Extensions → Apps Script → วางเนื้อหา `tools/apps_script.gs` (ตั้ง `TOKEN` ถ้าต้องการ) → Save
2. Deploy → New deployment → ชนิด **Web app** → Execute as **Me** → Who has access **Anyone** → Deploy → อนุญาตสิทธิ์
3. คัดลอก URL `https://script.google.com/macros/s/…/exec` ใส่ `docs/config.json`:
   ```json
   { "endpoint": "https://script.google.com/macros/s/XXXX/exec", "token": "" }
   ```
   แล้ว commit + push อีกครั้ง
4. ทดสอบ: เปิด URL `…/exec?action=dump` ต้องได้ `{"ok":true,"rows":[]}`

> `token` อยู่ใน config.json ซึ่งเป็น public — กันได้แค่คนสุ่มส่งข้อมูลมั่ว ไม่ใช่ความลับจริง. Script ตรวจ Class (−1…7; 7 = กำกึ่ง ใช้เฉพาะชุดอายุ), ชื่อ, ชื่อไฟล์ให้แล้ว และ**ต่อแถวเท่านั้น ไม่เขียนทับ** ถ้ามีคนส่งขยะก็ตัดแถวทิ้งได้

## 4. เอาผลกลับ

รันบน Lanta (transfer node) — ไฟล์ลงโฟลเดอร์ labels ของ worm ตรงๆ ไม่ผ่านเครื่อง Windows (2026-11-23):

```bash
ssh lanta
cd /project/lt200264-saiwat/WormProject/worm_labeler_repo && git pull -q --ff-only
/project/lt200264-saiwat/Env/segmentation/bin/python tools/collect_labels.py --dry-run   # ดูก่อนว่าจะเขียนไฟล์อะไร
/project/lt200264-saiwat/Env/segmentation/bin/python tools/collect_labels.py             # ทุก pack ที่อยู่บนเว็บตอนนี้
/project/lt200264-saiwat/Env/segmentation/bin/python tools/collect_labels.py --pack C    # pack เดียว (หรือ pack ที่ถูกลบ/เปลี่ยนชื่อไปแล้ว)
```

ได้ `/project/lt200264-saiwat/WormProject/data/worm-24022026/labels/worm-24022026-labels_<pack>_<ชื่อ>_<YYYYMMDD>.csv` ต่อคน
— คอลัมน์ `Class,Filename,file_hash` เหมือน CSV ของโปรแกรม desktop ส่งเข้า `python -m tool.label_merge --input …` ได้เลย ·
endpoint/packsBase อ่านจาก `docs/config.json` · รันซ้ำวันเดียวกัน = เขียนทับด้วยผลล่าสุด (ครบกว่าเดิม) ·
pack ที่ไม่อยู่บนเว็บแล้ว (เปลี่ยนชื่อ/ลบ/ทดสอบ) ถูกข้าม ต้องระบุ `--pack` เอง · ใช้ไฟล์ export จาก Sheet แทน: `--csv labels.csv`

**ส่งจาก pack_reseg ตรงๆ:** `python tool/pack_reseg.py --no-dry-run --web C` (ใน `WormProject/code`) = zip ตามปกติ + ขึ้นเว็บเป็น pack C — ดู `code/tool/PACK_RESEG.md`
`tools/lanta_publish_pack.sh` / `export_web_pack.py` รับ zip ของ pack_reseg เป็น `--src-dir` ได้ (ข้าม `undecidable/`, เก็บ `list.txt` ไว้ใน manifest `relabel`) และไม่ยอมเขียนทับ pack ชื่อเดิม เว้นแต่ `--replace`

## พฤติกรรมของแอป

- ตามโปรแกรมเดิม **v2.1** (`code/gui/worm_label_app_v2.1.py`, 2026-11-23): `1–7` หรือคลิกปุ่มคลาส = เลือก → ขึ้น "✅ ชื่อคลาส" ตัวใหญ่สีเขียว 600 ms แล้วไปรูปถัดไปอัตโนมัติ (เลือกซ้ำภายใน 600 ms = เริ่มนับใหม่); ย้อนกลับมารูปที่เคยเลือกจะขึ้น "📌 เลือก: ชื่อคลาส"; `Space/→/d` ถัดไป, `Backspace/←/a` ย้อน, `s` บันทึก. **v2.1 เลิกใช้ ←/→ เลื่อนคลาสและ ↑/↓ แล้ว** เว็บจึงเลิกด้วย
- ส่วนเพิ่มของเว็บ: `0` ล้างคำตอบ, `n` ไปรูปที่ยังไม่ลาเบล. ต่างจาก v2.1 จุดเดียว: ถ้ากดเลื่อนรูปเองระหว่าง 600 ms เว็บจะยกเลิกการเลื่อนอัตโนมัติ (v2.1 จะเลื่อนซ้ำจนข้ามรูปหนึ่ง)
- ส่งขึ้น Sheet อัตโนมัติทุก 10 ลาเบล / 15 วินาที / ตอนปิดแท็บ; ถ้าเน็ตหลุดจะเก็บคิวในเครื่องแล้วส่งซ้ำ (retry แบบ backoff)
- เปิดซ้ำ (หรือเปลี่ยนเครื่อง ใช้ชื่อเดิม) → ดึงสถานะจาก Sheet แล้วไปต่อที่รูปที่ยังไม่ลาเบล
- ปุ่ม **Download CSV** ใช้เป็นสำรองได้เสมอ (ไม่ต้องมี endpoint ก็ใช้งานได้)
- ภาพแสดงแบบยืดเป็นสี่เหลี่ยมจัตุรัสเหมือนโปรแกรมเดิม (`resize((450,450))`); crop ตัวอย่างเป็น 505×505 อยู่แล้ว

## ทดสอบแล้ว (2026-11-23)

pack 30 รูปจริงจาก `relabel_class3` + endpoint จำลอง: คีย์ลัด/ส่งเป็น batch/คืนสถานะหลังล้าง localStorage/collect_labels ผ่านหมด, หน้าจอมือถือ 375px ปุ่มคลาสเห็นโดยไม่ต้องเลื่อน.
ทดสอบกับ Apps Script จริงจาก github.io แล้ว (2026-11-23): ส่งผล → Sheet → กู้คืนหลังล้าง localStorage → collect_labels ผ่าน

## ทำ pack จาก Lanta เท่านั้น (ภาพไม่ผ่านเครื่อง Windows)

**ภาพอยู่คนละ repo กับโค้ด (ตั้งแต่ 2026-11-23):**

| repo | เก็บอะไร | เว็บ | clone บน Lanta (deploy key) |
|---|---|---|---|
| `rungkarn/worm_labeler` | โค้ดเท่านั้น (`docs/index.html`, `config.json`, `tools/`) | https://rungkarn.github.io/worm_labeler/ | `…/WormProject/worm_labeler_repo` (alias `github-wl`) |
| `rungkarn/worm_labeler_packs` | ภาพ `packs/<pack>/` เท่านั้น | https://rungkarn.github.io/worm_labeler_packs/ | `…/WormProject/worm_labeler_packs_repo` (alias `github-wlp`) |

`docs/config.json` → `packsBase` ชี้ไปที่เว็บของ repo ภาพ. Windows ไม่เคยมีภาพ (clone `worm_labeler` มาก็ไม่มีภาพ ไม่ต้องใช้ sparse-checkout)

```bash
ssh lanta
cd /project/lt200264-saiwat/WormProject/worm_labeler_repo
bash tools/lanta_publish_pack.sh <โฟลเดอร์ที่มี roi_mask+roi_src> <pack-id> [--part 1/2] [--limit N] [--skip-labelled labels.csv]
```

สคริปต์ทำครบ: pull ทั้งสอง repo → export → commit → push repo ภาพ แล้วเว็บอัปเดตใน ~1 นาที. แต่ละ repo ต้องมี deploy key ของตัวเอง (GitHub ไม่ให้ key เดียวใช้สอง repo)

**ลาเบลเสร็จแล้ว:** ลบ repo `worm_labeler_packs` ทิ้ง (ประวัติ+ภาพหายหมด) แล้วสร้างใหม่ว่างๆ + deploy key + เปิด Pages (main `/`) ก่อนรอบถัดไป — repo โค้ดไม่ต้องแตะ

## ดูความคืบหน้า (รู้ว่าใครลาเบลเสร็จหรือยัง)

```powershell
& "D:\DEV\miniforge-pypy3\python.exe" -I tools\progress.py            # ทุก pack
& "D:\DEV\miniforge-pypy3\python.exe" -I tools\progress.py --pack A
```

อ่าน endpoint/packsBase จาก `docs/config.json` เอง; จำนวนรวมต่อ pack = จำนวนรายการใน `manifest.json` บนเว็บภาพ, ที่ลาเบลแล้ว = ค่าล่าสุดต่อไฟล์ (Class ≥ 0). สถานะ `DONE` = ครบทุกรูป → ค่อยรัน `collect_labels.py` ดึง CSV

## ชุดอายุ (task age) — หน้า `age/`

งานถามอายุหนอนตามเกณฑ์ใหม่ (pack `R1_01`…`R1_10`) ใช้หน้าแยก ส่งเข้า Apps Script/Sheet ตัวเดิม (ไม่แก้ `apps_script.gs`)

- ลิงก์: `https://rungkarn.github.io/worm_labeler/age/?pack=R1_01&u=ชื่อ` — เปิด `/?pack=R1_01` ก็เด้งมาหน้า age เอง (อ่าน `manifest.task`); pack 7 คลาสไม่มี `task` อยู่หน้าเดิม
- สัญญา pack (repo ภาพ `worm_labeler_packs`): `packs/<ID>/manifest.json` (`task:"age"`, `classes[]`, `items[[instance_id,md5]]`), `ctx/<instance_id>.jpg` (เส้นเหลือง = ตัวที่ถาม), `close/<instance_id>.jpg` (ใกล้ ไว้ดูสี) 450×450, `packs/index.json` มี `{"id","n","task":"age"}`
- ปุ่มเหมือนโปรแกรมลาเบล 7 คลาส + 8 = กำกึ่ง (`Class` ที่ส่ง, −1 = ล้าง; คีย์ `1–8` ใช้ `e.code` เลยพิมพ์ไทยอยู่ก็ได้):

  | Class | คีย์ | ชื่อ |
  |---|---|---|
  | 0 | 1 | หนอนเด็ก |
  | 1 | 2 | หนอนพอดี (เขียวนวลอ่อน ยังไม่เห็นลาย) |
  | 2 | 3 | หนอนแก่ (ลายดำ / ท้อง-หลังสีต่าง) |
  | 3 | 4 | หนอนระบุรุ่นไม่ได้ |
  | 4 | 5 | ไม่ใช่หนอน |
  | 5 | 6 | รูปแหว่ง/พลาด |
  | 6 | 7 | หนอนไม่มีคุณภาพ |
  | **7** | **8** | **หนอนกำกึ่ง** (พอดี↔แก่ ลายจางๆ) |

  code 0–6 ความหมายเดียวกับ 7 คลาส, 7 = กำกึ่ง (ชุดอายุเท่านั้น); `0` ล้าง, `n`, `s`, Space/Backspace เหมือนเดิม
- **ต้อง redeploy Apps Script ก่อนใช้ปุ่ม 8** (ตัวเก่าตัด Class 7 ทิ้งเงียบๆ ตอบ `{ok:true,n:0}`): แก้ `tools/apps_script.gs` (รับ Class −1…7) แล้ว Deploy → Manage deployments → ✏️ แก้ deployment **เดิม** → Version: **New version** → Deploy (URL `/exec` เดิม; "New deployment" จะได้ URL ใหม่). หน้า age เช็ค `n` ที่ server ตอบ — ถ้าไม่เท่าจำนวนที่ส่งจะขึ้น sync สีแดงและเก็บคิวไว้ส่งซ้ำ ไม่ทิ้งคำตอบ
- localStorage: ชื่อใช้คีย์ร่วม `wl:name`; ผล `wla:<pack>:<user>`, คิว `wlaq:…`, ตำแหน่ง `wlapos:…`, เคยเห็นเกณฑ์ `wlaseen:…`
- Download CSV สำรอง: `age_<pack>_<user>.csv` (`instance_id,answer,code`)
- **เก็บผล:** `code/tool/collect_age_labels.py` ใน repo `worm` บน Lanta เท่านั้น → ได้ CSV แยก **ไม่รวมเข้า CSV 7 คลาส** (`worm-24022026-labels_*.csv`) เพราะ code 7 (กำกึ่ง) ไม่มีใน 7 คลาส และเกณฑ์อายุต่างจากเกณฑ์เดิม. `tools/collect_labels.py` ข้าม pack ที่มี `task` (และทิ้งแถว Class 7 กันไว้) และปฏิเสธ `--pack <age pack>`; `tools/progress.py` ใช้ดูความคืบหน้าได้ตามปกติ
