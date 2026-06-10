"""Run the Akanga terminal UI against a vault.

Usage: python run_tui.py <vault_path> <db_path>

The db path is required so the SQLite file never lands in the solution
directory by accident (e.g. ~/.local/share/akanga/akanga.db).
"""
import sys
from pathlib import Path

# Make akanga_core / akanga_tui importable when running from the solution directory.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from akanga_core.eventbus import EventBus  # noqa: E402
from akanga_tui.app import AkangaTUI  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_tui.py <vault_path> <db_path>")
        sys.exit(1)

    vault_path = Path(sys.argv[1]).absolute()
    app = AkangaTUI(db_path=sys.argv[2], vault_path=vault_path, event_bus=EventBus())
    app.run()
