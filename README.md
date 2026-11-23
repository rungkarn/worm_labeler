# worm_labeler — ลาเบลหนอนผ่าน browser (github.io)

เวอร์ชันเว็บของ `code/gui/worm_label_app_v2.py` ของโปรเจกต์ `worm` (อยู่บน Lanta) — ผู้ลาเบลเปิดลิงก์เดียว ไม่ต้องลงโปรแกรม ไม่ต้องรับไฟล์ภาพ
ผลลาเบลถูกส่งเข้า **Google Sheet** ของผู้ดูแลอัตโนมัติ แล้วดึงกลับมาเป็น CSV รูปแบบเดิม (`Class,Filename,file_hash`)

```
Lanta/เครื่องคุณ                 GitHub Pages (public)             ผู้ลาเบล              Google Sheet
roi_mask/*.npy + roi_src/*.npy ─► tools/export_web_pack.py ─► docs/packs/<pack>/ ─► เปิดลิงก์ ─► POST ─► tab "labels"
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

> `token` อยู่ใน config.json ซึ่งเป็น public — กันได้แค่คนสุ่มส่งข้อมูลมั่ว ไม่ใช่ความลับจริง. Script ตรวจ Class (−1…6), ชื่อ, ชื่อไฟล์ให้แล้ว และ**ต่อแถวเท่านั้น ไม่เขียนทับ** ถ้ามีคนส่งขยะก็ตัดแถวทิ้งได้

## 4. เอาผลกลับ

```powershell
& "D:\DEV\miniforge-pypy3\python.exe" -I tools\collect_labels.py --url https://script.google.com/macros/s/XXXX/exec --out labels_web
# หรือใช้ไฟล์ที่โหลดจาก Sheet (tab labels → File → Download → CSV)
& "D:\DEV\miniforge-pypy3\python.exe" -I tools\collect_labels.py --csv labels.csv --pack nb01 --out labels_web
```

ได้ `labels_web/ground_truth_worms_<pack>_<ชื่อ>.csv` ต่อคน — รูปแบบเดียวกับ CSV ของโปรแกรมเดิม (ส่งต่อ label merge ตามขั้นตอนเดิม)

## พฤติกรรมของแอป

- ปุ่ม/คีย์ลัดเหมือนโปรแกรมเดิม: `1–7` เลือกคลาส, `←/→` เลื่อนคลาส, `↑/↓` สลับแถว, `Space/d` ถัดไป, `Backspace/a` ย้อน, `s` บันทึก (เพิ่ม: `0` ล้างคำตอบ, `n` ไปรูปที่ยังไม่ลาเบล, ตัวเลือก "เลือกแล้วไปรูปถัดไปอัตโนมัติ")
- ส่งขึ้น Sheet อัตโนมัติทุก 10 ลาเบล / 15 วินาที / ตอนปิดแท็บ; ถ้าเน็ตหลุดจะเก็บคิวในเครื่องแล้วส่งซ้ำ (retry แบบ backoff)
- เปิดซ้ำ (หรือเปลี่ยนเครื่อง ใช้ชื่อเดิม) → ดึงสถานะจาก Sheet แล้วไปต่อที่รูปที่ยังไม่ลาเบล
- ปุ่ม **Download CSV** ใช้เป็นสำรองได้เสมอ (ไม่ต้องมี endpoint ก็ใช้งานได้)
- ภาพแสดงแบบยืดเป็นสี่เหลี่ยมจัตุรัสเหมือนโปรแกรมเดิม (`resize((450,450))`); crop ตัวอย่างเป็น 505×505 อยู่แล้ว

## ทดสอบแล้ว (2026-11-23)

pack 30 รูปจริงจาก `relabel_class3` + endpoint จำลอง: คีย์ลัด/ส่งเป็น batch/คืนสถานะหลังล้าง localStorage/collect_labels ผ่านหมด, หน้าจอมือถือ 375px ปุ่มคลาสเห็นโดยไม่ต้องเลื่อน.
**ยังไม่ได้ทดสอบกับ Apps Script จริง** (ต้อง deploy ด้วยบัญชี Google ของคุณ) และยังไม่ได้ push ขึ้น GitHub (repo ชื่อ `worm-label` หรือ `worm_labeler` ก็ได้ — ชื่อ repo คือส่วนหนึ่งของ URL)
