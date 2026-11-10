import re
import sys

import cv_tools

text = cv_tools.extract_text(sys.argv[1])
for line in text.splitlines():
    s = line.strip()
    if 0 < len(s) <= 40 and len(s.split()) <= 5 and not re.search(r"\d|@|http", s):
        print(repr(s))