"""vulture has no JSON output -> use its API. usage: tm_vulture.py --out F --min-confidence 60 PATH..."""
import argparse
import os

import vulture

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--min-confidence", type=int, default=60)
ap.add_argument("paths", nargs="+")
a = ap.parse_args()
v = vulture.Vulture()
v.scavenge(a.paths)
items = v.get_unused_code(min_confidence=a.min_confidence)
dump(a.out, [{"name": i.name, "type": i.typ, "file": os.path.relpath(str(i.filename)), "line": i.first_lineno,
              "end_line": i.last_lineno, "confidence": i.confidence, "size": i.size} for i in items])
