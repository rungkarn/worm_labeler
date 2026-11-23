# worm_labeler

เว็บลาเบลหนอน (static, github.io) แยกจากโปรเจกต์ `worm` — อ่าน `README.md` ก่อน
- `docs/` = รากของ GitHub Pages (Source: main /docs): `index.html`, `config.json`, `packs/<pack>/`
- `tools/` = export_web_pack.py, collect_labels.py, apps_script.gs (ไม่ถูกเผยแพร่)
- ต้นแบบ: `worm/code/gui/worm_label_app_v2.py` (Lanta) — คลาส/คีย์ลัด/CSV `Class,Filename,file_hash` ต้องตรงกัน
- ตอบผู้ใช้เป็นภาษาไทย; แก้ไฟล์ไทยด้วย Edit/Write ไม่ใช้ PowerShell Get/Set-Content
