"""Read automatically generated notes without a network request at startup."""
import json
import sys
from pathlib import Path


def load_notes(version, data_dir):
    from desktop_widgets.version import CHANGELOG
    bundle = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    for path in (Path(data_dir) / 'release_notes.json', bundle / 'release_notes.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('version') == version and isinstance(data.get('body'), str) and data['body'].strip():
                return data['body'].splitlines()
        except (OSError, ValueError, AttributeError):
            continue
    return CHANGELOG.get(version, [])
