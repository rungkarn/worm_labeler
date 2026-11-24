#!/usr/bin/env python
"""Show labelling progress per (pack, labeler): done / total, finished or not, last activity.

Reads endpoint, token and packsBase from docs/config.json by default, so just:
    python tools/progress.py
    python tools/progress.py --pack A
    python tools/progress.py --url https://script.google.com/macros/s/.../exec --packs-base https://user.github.io/worm_labeler_packs/

Total per pack = number of items in that pack's manifest.json (fetched from the packs site).
Done = labels with Class >= 0 whose Filename is in the manifest (latest label per labeler+file wins).
Age packs (task "age", ids R1_xx) work the same; a DONE age pack is collected by code/tool/collect_age_labels.py, not collect_labels.py.
Needs only the standard library (no -I problems: self-contained).
"""
import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_CFG = Path(__file__).resolve().parent.parent / "docs" / "config.json"


def get_json(url, timeout=120):
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


def fmt_ts(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M") if ms else "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CFG), help="docs/config.json (default)")
    ap.add_argument("--url", help="Apps Script /exec URL (overrides config)")
    ap.add_argument("--token", help="overrides config")
    ap.add_argument("--packs-base", help="e.g. https://user.github.io/worm_labeler_packs/ (overrides config)")
    ap.add_argument("--pack", help="only this pack")
    a = ap.parse_args()

    cfg = {}
    if Path(a.config).exists():
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    endpoint = a.url or cfg.get("endpoint")
    token = a.token if a.token is not None else cfg.get("token", "")
    base = (a.packs_base or cfg.get("packsBase") or "").rstrip("/")
    if not endpoint:
        raise SystemExit("no endpoint (set docs/config.json or pass --url)")
    if not base:
        raise SystemExit("no packsBase (set docs/config.json or pass --packs-base)")

    # totals: manifests of every pack on the packs site
    index = get_json(f"{base}/packs/index.json")
    totals, names, tasks = {}, {}, {}
    for p in index:
        if a.pack and p["id"] != a.pack:
            continue
        m = get_json(f"{base}/packs/{urllib.parse.quote(p['id'])}/manifest.json")
        names[p["id"]] = {it[0] for it in m["items"]}
        tasks[p["id"]] = m.get("task") or p.get("task") or ""
        totals[p["id"]] = len(m["items"])
    if a.pack and a.pack not in totals:
        raise SystemExit(f"pack '{a.pack}' not found on the packs site (have: {[p['id'] for p in index]})")

    # labels: latest per (pack, labeler, file)
    q = {"action": "dump"}
    if a.pack:
        q["pack"] = a.pack
    if token:
        q["token"] = token
    j = get_json(endpoint + "?" + urllib.parse.urlencode(q))
    if not j.get("ok"):
        raise SystemExit(f"server error: {j}")

    best = {}
    for r in j["rows"]:
        k = (r["pack"], r["labeler"], r["Filename"])
        t = ts_ms(r.get("ts", 0))
        if k not in best or t >= best[k][0]:
            best[k] = (t, int(r["Class"]))

    done, last, stale = {}, {}, {}
    for (pack, who, fn), (t, c) in best.items():
        key = (pack, who)
        last[key] = max(last.get(key, 0), t)
        if pack not in names:
            stale[key] = stale.get(key, 0) + 1
        elif fn in names[pack] and c >= 0:
            done[key] = done.get(key, 0) + 1

    rows = []
    seen_packs = set()
    for (pack, who) in sorted(set(done) | set(last)):
        if pack not in totals:
            continue
        seen_packs.add(pack)
        d, n = done.get((pack, who), 0), totals[pack]
        state = "DONE" if d >= n else f"{n - d} left"
        rows.append((pack, who, f"{d}/{n}", f"{100 * d / n:5.1f}%", state, fmt_ts(last.get((pack, who), 0))))
    for pack in sorted(set(totals) - seen_packs):
        rows.append((pack, "-", f"0/{totals[pack]}", "  0.0%", "not started", "-"))

    head = ("pack", "labeler", "done/total", "pct", "status", "last activity")
    rows.sort(key=lambda r: (r[0], r[1]))
    w = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    for r in [head] + rows:
        print("  ".join(str(x).ljust(w[i]) for i, x in enumerate(r)))
    age_done = sorted({r[0] for r in rows if r[4] == "DONE" and tasks.get(r[0]) == "age"})
    if age_done:
        print(f"\nDONE age packs {age_done}: collect with code/tool/collect_age_labels.py (worm repo, on Lanta), NOT collect_labels.py")
    unknown = {p for (p, _w) in stale}
    if unknown:
        print(f"\nnote: labels for packs not on the packs site (deleted/renamed): {sorted(unknown)}")


if __name__ == "__main__":
    main()
