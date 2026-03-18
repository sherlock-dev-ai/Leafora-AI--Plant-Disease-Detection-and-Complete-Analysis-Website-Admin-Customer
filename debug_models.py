
import os
from pathlib import Path
import logging

# Set up logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_script_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = _script_dir
DETECTION_MODELS_DIR = os.path.join(PROJECT_ROOT, "detection")
DETECTION_ONLY_MODE = os.getenv("DETECTION_ONLY_MODE", "1").strip() != "0"

print(f"PROJECT_ROOT: {PROJECT_ROOT}")
print(f"DETECTION_MODELS_DIR: {DETECTION_MODELS_DIR}")
print(f"DETECTION_ONLY_MODE: {DETECTION_ONLY_MODE}")

search_dirs = []
if DETECTION_ONLY_MODE:
    search_dirs.append(Path(DETECTION_MODELS_DIR))
else:
    search_dirs.append(Path(PROJECT_ROOT) / "m_models")
    search_dirs.append(Path(PROJECT_ROOT) / "main_models")

print(f"Search dirs: {search_dirs}")

models = []
seen_paths = set()

for d in search_dirs:
    if not d.is_absolute():
        d = Path(PROJECT_ROOT) / d
    
    try:
        d = d.resolve()
    except OSError:
        print(f"Failed to resolve {d}")
        continue
        
    if not d.exists():
        print(f"Directory does not exist: {d}")
        continue
    
    print(f"Searching in: {d}")
    keras_files = list(d.glob("*.keras"))
    print(f"Found {len(keras_files)} keras files")
    for f in keras_files:
        print(f"  - {f.name}")
