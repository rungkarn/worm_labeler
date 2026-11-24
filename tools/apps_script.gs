/**
 * Worm web labeler — receiver (Google Apps Script bound to a Google Sheet).
 *
 * Setup: see README.md section 3.
 *  - Sheet tab "labels", columns: ts | pack | labeler | Class | Filename | file_hash
 *  - Deploy > New deployment > Web app > Execute as: Me, Who has access: Anyone
 *  - Put the /exec URL (and TOKEN, if you set one) into site/config.json
 *
 * After editing this script: Deploy > Manage deployments > pencil (edit) the EXISTING deployment >
 * Version: New version > Deploy. That keeps the /exec URL; "New deployment" would create a new URL.
 *
 * Every label event is APPENDED (never overwritten). The latest ts per
 * (pack, labeler, Filename) wins; Class = -1 means "cleared".
 */
const SHEET_NAME = "labels";
const TOKEN = "";          // optional shared secret; if set, must equal "token" in site/config.json
const MAX_ROWS_PER_POST = 500;

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(["ts", "pack", "labeler", "Class", "Filename", "file_hash"]);
    sh.setFrozenRows(1);
  }
  return sh;
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

const NAME_RE = /^[\w฀-๿\-]{1,30}$/;
const FILE_RE = /^[\w.\-]{1,120}$/;

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (TOKEN && body.token !== TOKEN) return json_({ ok: false, error: "bad token" });
    if (body.action !== "labels") return json_({ ok: false, error: "bad action" });

    const out = [];
    for (const r of (body.rows || []).slice(0, MAX_ROWS_PER_POST)) {
      const c = Number(r.Class);
      if (!(c >= -1 && c <= 7)) continue;   // 7 = border, age packs only
      if (!/^[\w\-]{1,40}$/.test(String(r.pack))) continue;
      if (!NAME_RE.test(String(r.labeler))) continue;
      if (!FILE_RE.test(String(r.Filename))) continue;
      out.push([String(r.ts), String(r.pack), String(r.labeler), c,
                String(r.Filename), String(r.file_hash || "").slice(0, 64)]);
    }
    if (out.length) {
      const lock = LockService.getScriptLock();
      lock.waitLock(20000);
      try {
        const sh = sheet_();
        sh.getRange(sh.getLastRow() + 1, 1, out.length, 6).setValues(out);
      } finally {
        lock.releaseLock();
      }
    }
    return json_({ ok: true, n: out.length });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

/** GET ?action=get&pack=P&user=U  -> {ok, labels:{Filename:[class, tsMillis]}}  (resume on another device)
 *  GET ?action=dump&pack=P        -> {ok, rows:[{pack,labeler,Class,Filename,file_hash,ts}]}  (latest per labeler+file) */
function doGet(e) {
  try {
    const p = e.parameter || {};
    if (TOKEN && p.token !== TOKEN) return json_({ ok: false, error: "bad token" });
    const sh = sheet_();
    const n = sh.getLastRow();
    const vals = n > 1 ? sh.getRange(2, 1, n - 1, 6).getValues() : [];
    const latest = {};   // key -> {ts, row}
    for (const v of vals) {
      const ts = new Date(v[0]).getTime() || 0;
      if (p.pack && String(v[1]) !== p.pack) continue;
      if (p.action === "get" && String(v[2]) !== p.user) continue;
      const key = v[1] + "|" + v[2] + "|" + v[4];
      if (!latest[key] || ts >= latest[key].ts) latest[key] = { ts: ts, v: v };
    }
    if (p.action === "get") {
      const labels = {};
      for (const k in latest) {
        const v = latest[k].v;
        if (Number(v[3]) >= 0) labels[v[4]] = [Number(v[3]), latest[k].ts];
      }
      return json_({ ok: true, labels: labels });
    }
    if (p.action === "dump") {
      const rows = Object.keys(latest).map(k => {
        const v = latest[k].v;
        return { pack: v[1], labeler: v[2], Class: Number(v[3]), Filename: v[4], file_hash: v[5], ts: latest[k].ts };
      });
      return json_({ ok: true, rows: rows });
    }
    return json_({ ok: true, service: "worm-labeler" });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}
