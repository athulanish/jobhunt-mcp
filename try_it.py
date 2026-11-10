import json
import sys

import cv_tools

cv_path, jd_path = sys.argv[1], sys.argv[2]

print(json.dumps(cv_tools.inspect_cv(cv_path), indent=2))

with open(jd_path, encoding="utf-8", errors="ignore") as f:
    jd = f.read()
print(json.dumps(cv_tools.keyword_gap(cv_tools.extract_text(cv_path), jd), indent=2))