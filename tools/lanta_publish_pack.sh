#!/bin/bash
# Run ON LANTA (transfer node `lanta`, which can reach github.com). Images never touch the local PC.
#
#   bash tools/lanta_publish_pack.sh <src-dir with roi_mask/ roi_src/> <pack-id> [export_web_pack.py args...]
#   e.g. bash tools/lanta_publish_pack.sh /project/lt200264-saiwat/WormProject/data/relabel_class3 class3_c --part 1/2
#
# Uses the clone in $WL_REPO and the deploy key (ssh alias github-wl -> ~/.ssh/worm_labeler_deploy).
set -euo pipefail
REPO=${WL_REPO:-/project/lt200264-saiwat/WormProject/worm_labeler_repo}
PY=${WL_PY:-/project/lt200264-saiwat/Env/segmentation/bin/python}
[ $# -ge 2 ] || { sed -n '2,8p' "$0"; exit 1; }
SRC=$1; PACK=$2; shift 2

cd "$REPO"
git pull -q --ff-only
"$PY" -I tools/export_web_pack.py --src-dir "$SRC" --site docs --pack "$PACK" "$@"
git add docs/packs
git commit -q -m "pack $PACK (exported on Lanta)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q origin main
git log --oneline | head -1
echo "pushed. live in ~1 min: https://rungkarn.github.io/worm_labeler/?pack=$PACK"
