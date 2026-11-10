import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Point the tool at a throwaway folder BEFORE any project module is imported.
TEST_DIR = Path(tempfile.mkdtemp(prefix="jobhunt-test-")).resolve()
os.environ["JOBHUNT_DIR"] = str(TEST_DIR)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def clean_data_dir():
    """Start every test with an empty jobhunt folder (no CVs, database or cache left over)."""
    for item in TEST_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    yield
