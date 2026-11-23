#!/usr/bin/env python
"""Export a labelling folder (roi_mask/*.npy + roi_src/*.npy) to a static web pack.

Output (under --site):
    packs/<pack>/manifest.json      {"pack", "n", "items": [[Filename, file_hash], ...]}
    packs/<pack>/src/<stem>.jpg     source crop (RGB)
    packs/<pack>/mask/<stem>.png    RGBA overlay, blue [52,152,219,130] where mask>0 (same as worm_label_app_v2)
    packs/index.json                list of packs for the picker page

file_hash = md5 of the roi_mask .npy bytes, same as worm_label_app_v2.py, so the CSV
coming back is drop-in compatible with the desktop labeller's CSV.

Example:
    python export_web_pack.py --src-dir /project/.../data/relabel_class3 --site ./site --pack nb01 --limit 3000
    python export_web_pack.py --src-dir D:\\data\\batch --site .\\site --pack pc02 --skip-labelled labels.csv
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OVERLAY = (52, 152, 219, 130)


def md5_file(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_rgb(arr: np.ndarray) -> Image.Image:
    if arr.dtype == bool:
        arr = arr.astype(np.uint8) * 255
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    return Image.fromarray(arr.astype(np.uint8)).convert("RGB")


def export_one(mask_path: Path, src_path: Path, out_src: Path, out_mask: Path, max_side: int, quality: int):
    src = to_rgb(np.load(str(src_path)))
    m = np.load(str(mask_path))
    if m.ndim == 3:
        m = m[:, :, 0]
    overlay = np.zeros((*m.shape, 4), dtype=np.uint8)
    overlay[m > 0] = OVERLAY
    ov = Image.fromarray(overlay)
    if ov.size != src.size:                       # keep both layers pixel-aligned
        ov = ov.resize(src.size, Image.NEAREST)
    # shrink both by the same factor
    if max_side and max(src.size) > max_side:
        s = max_side / max(src.size)
        size = (max(1, round(src.width * s)), max(1, round(src.height * s)))
        src = src.resize(size, Image.LANCZOS)
        ov = ov.resize(size, Image.NEAREST)
    stem = mask_path.stem
    src.save(out_src / f"{stem}.jpg", quality=quality, optimize=True)
    ov.save(out_mask / f"{stem}.png", optimize=True)
    return mask_path.name, md5_file(mask_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", required=True, help="folder that contains roi_mask/ and roi_src/")
    ap.add_argument("--site", required=True, help="site root (the folder that holds index.html)")
    ap.add_argument("--pack", required=True, help="pack id, letters/digits/_/- only")
    ap.add_argument("--limit", type=int, default=0, help="export at most N masks (0 = all)")
    ap.add_argument("--list", help="txt file, one mask filename/stem per line: export only these")
    ap.add_argument("--skip-labelled", help="existing label CSV (Class,Filename,file_hash): skip rows whose hash already matches")
    ap.add_argument("--part", help="i/n: export only the i-th of n contiguous chunks (split work between labellers), e.g. 1/2")
    ap.add_argument("--max-side", type=int, default=450, help="downscale so the longest side <= this (0 = keep). default 450 = desktop display size")
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    if not a.pack.replace("_", "").replace("-", "").isalnum():
        sys.exit("--pack: use letters, digits, _ and - only")

    root = Path(a.src_dir)
    masks = sorted((root / "roi_mask").glob("*.npy"))
    if not masks:
        sys.exit(f"no roi_mask/*.npy under {root}")

    if a.list:
        want = {Path(l.strip()).stem for l in open(a.list, encoding="utf-8") if l.strip()}
        masks = [m for m in masks if m.stem in want]

    done = {}
    if a.skip_labelled:
        import csv
        with open(a.skip_labelled, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done[r["Filename"]] = r.get("file_hash", "")
        before = len(masks)
        masks = [m for m in masks if not (m.name in done and done[m.name] == md5_file(m))]
        print(f"skip-labelled: {before - len(masks)} already labelled, {len(masks)} remain")

    if a.limit:
        masks = masks[: a.limit]
    if a.part:
        i, n = (int(x) for x in a.part.split("/"))
        if not 1 <= i <= n:
            sys.exit("--part: use i/n with 1 <= i <= n, e.g. 1/2")
        k = -(-len(masks) // n)                  # ceil: contiguous chunks keep crops of one photo together
        masks = masks[(i - 1) * k : i * k]
        print(f"part {i}/{n}: {len(masks)} masks")
    missing = [m.name for m in masks if not (root / "roi_src" / m.name).exists()]
    if missing:
        print(f"warning: {len(missing)} masks have no roi_src, skipped (e.g. {missing[:3]})")
        masks = [m for m in masks if m.name not in set(missing)]

    site = Path(a.site)
    pdir = site / "packs" / a.pack
    out_src, out_mask = pdir / "src", pdir / "mask"
    out_src.mkdir(parents=True, exist_ok=True)
    out_mask.mkdir(parents=True, exist_ok=True)

    items = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(export_one, m, root / "roi_src" / m.name, out_src, out_mask, a.max_side, a.quality) for m in masks]
        for i, fu in enumerate(futs, 1):
            items.append(list(fu.result()))
            if i % 500 == 0:
                print(f"  {i}/{len(futs)}")

    (pdir / "manifest.json").write_text(
        json.dumps({"pack": a.pack, "n": len(items), "items": items}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    idx_path = site / "packs" / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    idx = [p for p in idx if p["id"] != a.pack] + [{"id": a.pack, "n": len(items)}]
    idx_path.write_text(json.dumps(sorted(idx, key=lambda p: p["id"]), ensure_ascii=False, indent=1), encoding="utf-8")

    size = sum(f.stat().st_size for f in pdir.rglob("*") if f.is_file())
    print(f"pack '{a.pack}': {len(items)} items, {size / 1e6:.1f} MB -> {pdir}")


if __name__ == "__main__":
    main()
