#!/usr/bin/env python
"""Pull web-labelled results into the desktop labeller's CSV format (Class,Filename,file_hash).

Source (pick one):
    --url  https://script.google.com/macros/s/.../exec     (reads ?action=dump)
    --csv  sheet.csv                                       (the "labels" tab exported from Google Sheets)

One output file per (pack, labeler): <out>/ground_truth_worms_<pack>_<labeler>.csv
Latest timestamp per (pack, labeler, Filename) wins; Class -1 (cleared) is dropped.

Example:
    python collect_labels.py --url https://script.google.com/macros/s/XXXX/exec --token T --out labels_web
"""
import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path


def from_url(url, pack, token):
    q = {"action": "dump"}
    if pack:
        q["pack"] = pack
    if token:
        q["token"] = token
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(q), timeout=120) as r:
        j = json.loads(r.read().decode("utf-8"))
    if not j.get("ok"):
        raise SystemExit(f"server error: {j}")
    return dedupe(j["rows"])


def _ts(v):
    from datetime import datetime
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return 0.0


def dedupe(rows):
    """latest ts wins per (pack, labeler, Filename); input order breaks ties (later = newer)"""
    best = {}
    for r in rows:
        k = (r["pack"], r["labeler"], r["Filename"])
        t = _ts(r.get("ts", 0))
        if k not in best or t >= best[k][0]:
            best[k] = (t, r)
    return [r for _, r in best.values()]


def from_csv(path, pack):
    from datetime import datetime
    latest = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if pack and r["pack"] != pack:
                continue
            try:
                ts = datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).timestamp()
            except Exception:
                ts = 0
            k = (r["pack"], r["labeler"], r["Filename"])
            if k not in latest or ts >= latest[k][0]:
                latest[k] = (ts, r)
    return [{"pack": r["pack"], "labeler": r["labeler"], "Class": int(r["Class"]),
             "Filename": r["Filename"], "file_hash": r["file_hash"]} for _, r in latest.values()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--csv")
    ap.add_argument("--token", default="")
    ap.add_argument("--pack", default="")
    ap.add_argument("--out", default="labels_web")
    a = ap.parse_args()

    rows = from_url(a.url, a.pack, a.token) if a.url else from_csv(a.csv, a.pack)
    groups = {}
    for r in rows:
        if int(r["Class"]) < 0:
            continue
        groups.setdefault((r["pack"], r["labeler"]), []).append(r)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for (pack, who), rs in sorted(groups.items()):
        rs.sort(key=lambda r: r["Filename"])
        p = out / f"ground_truth_worms_{pack}_{who}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Class", "Filename", "file_hash"])
            for r in rs:
                w.writerow([int(r["Class"]), r["Filename"], r["file_hash"]])
        print(f"{p}  {len(rs)} labels")
    if not groups:
        print("no labels found")


if __name__ == "__main__":
    main()
