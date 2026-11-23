#!/bin/bash
# Run ON LANTA (transfer node `lanta`, which can reach github.com). Images never touch the local PC.
#
#   bash tools/lanta_publish_pack.sh <src-dir with roi_mask/ roi_src/> <pack-id> [export_web_pack.py args...]
#   e.g. bash tools/lanta_publish_pack.sh /project/lt200264-saiwat/WormProject/data/relabel_class3 class3_c --part 1/2
#
# Two clones on Lanta (each with its own read-write deploy key, since GitHub allows one repo per key):
#   $WL_CODE  = worm_labeler        (code; ssh alias github-wl  -> ~/.ssh/worm_labeler_deploy)   - only pulled here
#   $WL_PACKS = worm_labeler_packs  (images; ssh alias github-wlp -> ~/.ssh/worm_labeler_packs_deploy) - pushed here
# The site (docs/config.json "packsBase") reads images from https://rungkarn.github.io/worm_labeler_packs/.
# When labelling is finished: delete the packs repo (history and images vanish with it), recreate it empty for the next round.
set -euo pipefail
CODE=${WL_CODE:-/project/lt200264-saiwat/WormProject/worm_labeler_repo}
PACKS=${WL_PACKS:-/project/lt200264-saiwat/WormProject/worm_labeler_packs_repo}
PY=${WL_PY:-/project/lt200264-saiwat/Env/segmentation/bin/python}
[ $# -ge 2 ] || { sed -n '2,5p' "$0"; exit 1; }
SRC=$1; PACK=$2; shift 2

git -C "$CODE" pull -q --ff-only
git -C "$PACKS" pull -q --ff-only
"$PY" -I "$CODE/tools/export_web_pack.py" --src-dir "$SRC" --site "$PACKS" --pack "$PACK" "$@"   # writes $PACKS/packs/<pack>/ + packs/index.json
cd "$PACKS"
git add packs
git commit -q -m "pack $PACK (exported on Lanta)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q origin main
git log -1 --oneline    # (not `git log | head -1`: SIGPIPE + pipefail made the script exit non-zero after a successful push)
echo "pushed. live in ~1 min: https://rungkarn.github.io/worm_labeler/?pack=$PACK"
