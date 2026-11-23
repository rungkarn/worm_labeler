#!/usr/bin/env python
"""Pull web-labelled results into the desktop labeller's CSV format (Class,Filename,file_hash).

Run ON LANTA (transfer node, `ssh lanta`) so the CSVs land straight in the labels folder:
    cd /project/lt200264-saiwat/WormProject/worm_labeler_repo
    python tools/collect_labels.py                 # every pack that is on the site now
    python tools/collect_labels.py --pack C        # one pack
    python tools/collect_labels.py --dry-run       # show what would be written

Output: <out>/<prefix>_<pack>_<labeler>_<YYYYMMDD>.csv
    default out    = /project/lt200264-saiwat/WormProject/data/worm-24022026/labels
    default prefix = worm-24022026-labels      e.g. worm-24022026-labels_C_somchai_20261124.csv
Same day again = the file is rewritten with the newer, complete result (the Sheet keeps everything).

Rules: latest timestamp per (pack, labeler, Filename) wins; Class -1 (cleared) is dropped;
only Filenames that are in the pack's manifest count; packs no longer on the site (deleted/renamed,
test packs) are skipped unless named with --pack. Endpoint/token/packsBase come from docs/config.json.

Other source: --csv <labels tab exported from Google Sheets> instead of the endpoint.
"""
import argparse
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_CFG = Path(__file__).resolve().parent.parent / "docs" / "config.json"
LANTA_LABELS = "/project/lt200264-saiwat/WormProject/data/worm-24022026/labels"


def get_json(url, timeout=180):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ts_ms(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return 0.0


def rows_from_url(endpoint, token, pack):
    q = {"action": "dump"}
    if pack:
        q["pack"] = pack
    if token:
        q["token"] = token
    j = get_json(endpoint + "?" + urllib.parse.urlencode(q))
    if not j.get("ok"):
        raise SystemExit(f"server error: {j}")
    return j["rows"]


def rows_from_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest(rows):
    best = {}
    for r in rows:
        k = (r["pack"], r["labeler"], r["Filename"])
        t = ts_ms(r.get("ts", 0))
        if k not in best or t >= best[k][0]:
            best[k] = (t, r)
    return [r for _, r in best.values()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CFG))
    ap.add_argument("--url", help="Apps Script /exec URL (default: docs/config.json endpoint)")
    ap.add_argument("--csv", help="use an exported Sheet CSV instead of the endpoint")
    ap.add_argument("--token")
    ap.add_argument("--packs-base", help="default: docs/config.json packsBase")
    ap.add_argument("--pack", help="only this pack (also works for a pack no longer on the site)")
    ap.add_argument("--out", default=LANTA_LABELS if os.path.isdir(LANTA_LABELS) else "labels_web")
    ap.add_argument("--prefix", default="worm-24022026-labels")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="date part of the file name (default today)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8")) if Path(a.config).exists() else {}
    endpoint = a.url or cfg.get("endpoint")
    token = a.token if a.token is not None else cfg.get("token", "")
    base = (a.packs_base or cfg.get("packsBase") or "").rstrip("/")

    # which packs, and which Filenames belong to each (from the live manifests)
    manifests = {}
    if base:
        index = get_json(f"{base}/packs/index.json")
        for p in index:
            if a.pack and p["id"] != a.pack:
                continue
            m = get_json(f"{base}/packs/{urllib.parse.quote(p['id'])}/manifest.json")
            manifests[p["id"]] = {it[0] for it in m["items"]}
    if a.pack and a.pack not in manifests:
        print(f"note: pack '{a.pack}' is not on the site now — writing its labels without a manifest check")

    if a.csv:
        rows = rows_from_csv(a.csv)
    elif endpoint:
        rows = rows_from_url(endpoint, token, a.pack)
    else:
        raise SystemExit("no endpoint (docs/config.json) and no --csv")

    groups, skipped = {}, {}
    for r in latest(rows):
        pack, who = r["pack"], r["labeler"]
        if a.pack and pack != a.pack:
            continue
        if not a.pack and pack not in manifests:
            skipped[pack] = skipped.get(pack, 0) + 1
            continue
        if int(r["Class"]) < 0:
            continue
        if pack in manifests and r["Filename"] not in manifests[pack]:
            continue
        groups.setdefault((pack, who), []).append(r)

    out = Path(a.out)
    if not a.dry_run:
        out.mkdir(parents=True, exist_ok=True)
    for (pack, who), rs in sorted(groups.items()):
        rs.sort(key=lambda r: r["Filename"])
        p = out / f"{a.prefix}_{pack}_{who}_{a.date}.csv"
        note = " (rewrite)" if p.exists() else ""
        if a.dry_run:
            print(f"[dry-run] {p}  {len(rs)} labels{note}")
            continue
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Class", "Filename", "file_hash"])
            for r in rs:
                w.writerow([int(r["Class"]), r["Filename"], r["file_hash"]])
        print(f"{p}  {len(rs)} labels{note}")
    if not groups:
        print("no labels found")
    if skipped:
        print(f"skipped packs not on the site (old/test): {sorted(skipped)} — name one with --pack to export it")


if __name__ == "__main__":
    main()
