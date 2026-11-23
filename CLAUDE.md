# worm_labeler

เว็บลาเบลหนอน (static, github.io) แยกจากโปรเจกต์ `worm` — อ่าน `README.md` ก่อน
- `docs/` = รากของ GitHub Pages (Source: main /docs): `index.html`, `config.json` (ภาพไม่อยู่ใน repo นี้แล้ว — ดูข้อล่างสุด)
- `tools/` = export_web_pack.py, collect_labels.py, apps_script.gs (ไม่ถูกเผยแพร่)
- ต้นแบบ: `worm/code/gui/worm_label_app_v2.py` (Lanta) — คลาส/คีย์ลัด/CSV `Class,Filename,file_hash` ต้องตรงกัน
- ตอบผู้ใช้เป็นภาษาไทย; แก้ไฟล์ไทยด้วย Edit/Write ไม่ใช้ PowerShell Get/Set-Content
- **ภาพ pack ห้ามเก็บบนเครื่อง Windows นี้** (ผู้ใช้สั่ง 2026-11-23) — export + push จาก Lanta เท่านั้น: `bash tools/lanta_publish_pack.sh` บน Lanta (clone อยู่ `/project/lt200264-saiwat/WormProject/worm_labeler_repo`, deploy key alias `github-wl`). อย่า export_web_pack.py ในเครื่องนี้ และอย่าดึงภาพกลับมา
- **ภาพอยู่ repo แยก `rungkarn/worm_labeler_packs`** (2026-11-23; `docs/config.json` → `packsBase`; clone บน Lanta `…/worm_labeler_packs_repo`, deploy key alias `github-wlp`) — เมื่อลาเบลจบให้ลบ repo นั้นทิ้งแล้วสร้างใหม่ (ประวัติภาพหายหมด) ดู README หัวข้อ "ทำ pack จาก Lanta เท่านั้น"
