import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
data_dir = Path(os.environ.get("JOBHUNT_DIR", "~/jobhunt")).expanduser().resolve()
data_dir.mkdir(parents=True, exist_ok=True)

config = {
    "mcpServers": {
        "jobhunt": {
            "command": sys.executable,
            "args": [str(root / "server.py")],
            "env": {"JOBHUNT_DIR": str(data_dir)},
        }
    }
}

print(f"Your jobhunt folder (put your CV here): {data_dir}\n")
print("Merge this into claude_desktop_config.json (Settings, Developer, Edit Config):\n")
print(json.dumps(config, indent=2)) 