"""Run the Akanga REST API against a vault.

Usage: python run_api.py <vault_path> <db_path>

The db path is required so the SQLite file never lands in the solution
directory by accident (e.g. ~/.local/share/akanga/akanga.db).
"""
import sys
from pathlib import Path

import uvicorn

# Make akanga_core importable when running from the solution directory.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from akanga_core.app import AkangaApp  # noqa: E402
from akanga_core.server import create_app  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_api.py <vault_path> <db_path>")
        sys.exit(1)

    akanga = AkangaApp(vault_path=sys.argv[1], db_path=sys.argv[2])
    akanga.start_all()

    app = create_app(akanga)
    # SEC-04: localhost only.
    uvicorn.run(app, host="127.0.0.1", port=8000)
