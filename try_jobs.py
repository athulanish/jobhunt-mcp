import json
import sys

import job_tools

entries = [e for e in sys.argv[1].split(",") if e]
keywords = sys.argv[2] if len(sys.argv) > 2 else ""
location = sys.argv[3] if len(sys.argv) > 3 else ""
print(json.dumps(job_tools.search_boards(entries, keywords, location, limit=10), indent=2))