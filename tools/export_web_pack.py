#!/usr/bin/env python
"""Export a labelling set (roi_mask/*.npy + roi_src/*.npy) to a static web pack.

--src-dir is either
    a folder with roi_mask/ and roi_src/                         (e.g. data/relabel_class3)
    a pack_reseg zip  reseg_<tag>[_a].zip  (<prefix>/roi_mask, <prefix>/roi_src, optional roi_mask/list.txt)
Files under undecidable/ in a zip are NOT exported (warned) — pass them as their own pack if needed.

Output (under --site):
    packs/<pack>/manifest.json      {"pack", "n", "source", "created", "relabel": [...], "items": [[Filename, file_hash], ...]}
    packs/<pack>/src/<stem>.jpg     source crop (RGB)
    packs/<pack>/mask/<stem>.png    RGBA overlay, blue [52,152,219,130] where mask>0 (same as worm_label_app_v2)
    packs/index.json                list of packs for the picker page

file_hash = md5 of the roi_mask .npy bytes, same as worm_label_app_v2.py, so the CSV
coming back is drop-in compatible with the desktop labeller's CSV.
"relabel" = names from the zip's roi_mask/list.txt (masks re-sent / force relabel) — informational:
the web labels every item of a pack fresh anyway.

An existing pack id is refused unless --replace (which deletes the old pack folder first).

Example:
    python export_web_pack.py --src-dir /project/.../data/relabel_class3 --site ./site --pack nb01 --limit 3000
    python export_web_pack.py --src-dir /project/.../reseg/v2/reseg_20261120_134720.zip --site ./site --pack C
"""
import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

OVERLAY = (52, 152, 219, 130)


def md5_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def to_rgb(arr: np.ndarray) -> Image.Image:
    if arr.dtype == bool:
        arr = arr.astype(np.uint8) * 255
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    return Image.fromarray(arr.astype(np.uint8)).convert("RGB")


# ── sources: name -> (read mask bytes, read src bytes) ─────────────────────────

class DirSource:
    def __init__(self, root: Path):
        self.root, self.desc = root, str(root)
        self.names = sorted(p.name for p in (root / "roi_mask").glob("*.npy"))
        self.relabel = []
        lt = root / "roi_mask" / "list.txt"
        if lt.exists():
            self.relabel = sorted({Path(l.strip()).name for l in lt.read_text(encoding="utf-8").splitlines() if l.strip()})
        self.skipped_undecidable = 0

    def has_src(self, n):
        return (self.root / "roi_src" / n).exists()

    def mask(self, n):
        return (self.root / "roi_mask" / n).read_bytes()

    def src(self, n):
        return (self.root / "roi_src" / n).read_bytes()


class ZipSource:
    """pack_reseg zip: <prefix>/roi_mask/*.npy, <prefix>/roi_src/*.npy (+ <prefix>/undecidable/...)"""

    def __init__(self, path: Path):
        self.zf = zipfile.ZipFile(path)
        self.desc = path.name
        self.mask_m, self.src_m = {}, {}
        self.relabel, self.skipped_undecidable = [], 0
        for m in self.zf.namelist():
            p = PurePosixPath(m)
            if "undecidable" in p.parts:
                if p.suffix == ".npy" and p.parent.name == "roi_mask":
                    self.skipped_undecidable += 1
                continue
            if p.parent.name == "roi_mask" and p.suffix == ".npy":
                self.mask_m[p.name] = m
            elif p.parent.name == "roi_src" and p.suffix == ".npy":
                self.src_m[p.name] = m
            elif p.parent.name == "roi_mask" and p.name == "list.txt":
                txt = self.zf.read(m).decode("utf-8")
                self.relabel = sorted({PurePosixPath(l.strip()).name for l in txt.splitlines() if l.strip()})
        self.names = sorted(self.mask_m)

    def has_src(self, n):
        return n in self.src_m

    def mask(self, n):
        return self.zf.read(self.mask_m[n])     # ZipFile.read is thread-safe (own handle per call)

    def src(self, n):
        return self.zf.read(self.src_m[n])


def open_source(path: str):
    p = Path(path)
    if p.suffix.lower() == ".zip":
        return ZipSource(p)
    if not (p / "roi_mask").is_dir():
        sys.exit(f"{p}: not a .zip and has no roi_mask/ folder")
    return DirSource(p)


def export_one(source, name: str, out_src: Path, out_mask: Path, max_side: int, quality: int):
    mb = source.mask(name)
    src = to_rgb(np.load(io.BytesIO(source.src(name))))
    m = np.load(io.BytesIO(mb))
    if m.ndim == 3:
        m = m[:, :, 0]
    overlay = np.zeros((*m.shape, 4), dtype=np.uint8)
    overlay[m > 0] = OVERLAY
    ov = Image.fromarray(overlay)
    if ov.size != src.size:                       # keep both layers pixel-aligned
        ov = ov.resize(src.size, Image.NEAREST)
    if max_side and max(src.size) > max_side:     # shrink both by the same factor
        s = max_side / max(src.size)
        size = (max(1, round(src.width * s)), max(1, round(src.height * s)))
        src = src.resize(size, Image.LANCZOS)
        ov = ov.resize(size, Image.NEAREST)
    stem = Path(name).stem
    src.save(out_src / f"{stem}.jpg", quality=quality, optimize=True)
    ov.save(out_mask / f"{stem}.png", optimize=True)
    return name, md5_bytes(mb)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", required=True, help="folder with roi_mask/ + roi_src/, or a pack_reseg .zip")
    ap.add_argument("--site", required=True, help="site root that holds packs/ (the packs repo)")
    ap.add_argument("--pack", required=True, help="pack id, ASCII letters/digits/_/- only")
    ap.add_argument("--replace", action="store_true", help="overwrite an existing pack with this id")
    ap.add_argument("--limit", type=int, default=0, help="export at most N masks (0 = all)")
    ap.add_argument("--list", help="txt file, one mask filename/stem per line: export only these")
    ap.add_argument("--skip-labelled", help="existing label CSV (Class,Filename,file_hash): skip rows whose hash already matches")
    ap.add_argument("--part", help="i/n: export only the i-th of n contiguous chunks (split work between labellers), e.g. 1/2")
    ap.add_argument("--max-side", type=int, default=450, help="downscale so the longest side <= this (0 = keep). default 450 = desktop display size")
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    if not (a.pack.isascii() and a.pack.replace("_", "").replace("-", "").isalnum()):
        sys.exit("--pack: use ASCII letters, digits, _ and - only (the labeller's name goes in ?u=, not here)")

    site = Path(a.site)
    pdir = site / "packs" / a.pack
    if pdir.exists() and not a.replace:
        sys.exit(f"pack '{a.pack}' already exists ({pdir}) — choose another id, or --replace to overwrite it")

    source = open_source(a.src_dir)
    names = source.names
    if not names:
        sys.exit(f"no roi_mask/*.npy in {source.desc}")
    if source.skipped_undecidable:
        print(f"warning: {source.skipped_undecidable} masks under undecidable/ not exported")

    if a.list:
        want = {Path(l.strip()).stem for l in open(a.list, encoding="utf-8") if l.strip()}
        names = [n for n in names if Path(n).stem in want]

    if a.skip_labelled:
        import csv
        done = {}
        with open(a.skip_labelled, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done[r["Filename"]] = r.get("file_hash", "")
        before = len(names)
        names = [n for n in names if not (n in done and done[n] == md5_bytes(source.mask(n)))]
        print(f"skip-labelled: {before - len(names)} already labelled, {len(names)} remain")

    if a.limit:
        names = names[: a.limit]
    if a.part:
        i, n = (int(x) for x in a.part.split("/"))
        if not 1 <= i <= n:
            sys.exit("--part: use i/n with 1 <= i <= n, e.g. 1/2")
        k = -(-len(names) // n)                  # ceil: contiguous chunks keep crops of one photo together
        names = names[(i - 1) * k: i * k]
        print(f"part {i}/{n}: {len(names)} masks")
    missing = [n for n in names if not source.has_src(n)]
    if missing:
        print(f"warning: {len(missing)} masks have no roi_src, skipped (e.g. {missing[:3]})")
        names = [n for n in names if n not in set(missing)]
    if not names:
        sys.exit("nothing to export")

    if pdir.exists():                             # --replace: no stale images from the old pack
        shutil.rmtree(pdir)
    out_src, out_mask = pdir / "src", pdir / "mask"
    out_src.mkdir(parents=True, exist_ok=True)
    out_mask.mkdir(parents=True, exist_ok=True)

    items = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(export_one, source, nm, out_src, out_mask, a.max_side, a.quality) for nm in names]
        for i, fu in enumerate(futs, 1):
            items.append(list(fu.result()))
            if i % 500 == 0:
                print(f"  {i}/{len(futs)}")

    exported = {it[0] for it in items}
    manifest = {"pack": a.pack, "n": len(items), "source": source.desc,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "relabel": [r for r in source.relabel if r in exported], "items": items}
    (pdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    idx_path = site / "packs" / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    idx = [p for p in idx if p["id"] != a.pack] + [{"id": a.pack, "n": len(items)}]
    idx_path.write_text(json.dumps(sorted(idx, key=lambda p: p["id"]), ensure_ascii=False, indent=1), encoding="utf-8")

    size = sum(f.stat().st_size for f in pdir.rglob("*") if f.is_file())
    rel = f", relabel (list.txt) {len(manifest['relabel'])}" if manifest["relabel"] else ""
    print(f"pack '{a.pack}': {len(items)} items{rel}, {size / 1e6:.1f} MB -> {pdir}")


if __name__ == "__main__":
    main()
