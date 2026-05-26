import sys
import os
from pathlib import Path

# Add src to path so akanga_core is discoverable
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from akanga_tui.app import AkangaTUI
from akanga_core.eventbus import EventBus

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_tui.py <vault_path> [db_path]")
        sys.exit(1)
    
    vault_path = Path(sys.argv[1]).absolute()
    db_path = sys.argv[2] if len(sys.argv) > 2 else "akanga.db"
    
    # We need an event bus for the TUI
    events = EventBus()
    
    app = AkangaTUI(db_path=db_path, vault_path=vault_path, event_bus=events)
    app.run()
