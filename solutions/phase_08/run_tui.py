"""Run the Akanga terminal UI against a vault.

Usage: python run_tui.py <vault_path> <db_path>

The db path is required so the SQLite file never lands in the solution
directory by accident (e.g. ~/.local/share/akanga/akanga.db).

Wiring (the part that makes live refresh real): AkangaApp is the
composition root — it owns the database, the EventBus, the VaultWatcher,
and the GitManager, and its start_all() indexes the vault and starts the
watcher. The TUI receives that same AkangaApp, so the ``node_updated``
events published by the indexing pipeline reach the screen. Constructing
the TUI with a bare EventBus that nothing publishes on (the old bug)
renders a UI that never updates.
"""
import sys
from pathlib import Path

# Make akanga_core / akanga_tui importable when running from the solution directory.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from akanga_core.app import AkangaApp  # noqa: E402
from akanga_tui.app import AkangaTUI  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_tui.py <vault_path> <db_path>")
        sys.exit(1)

    vault_path = Path(sys.argv[1]).absolute()
    core = AkangaApp(vault_path=str(vault_path), db_path=sys.argv[2])
    core.start_all()  # index the vault + start watcher and commit batcher
    try:
        AkangaTUI(core).run()
    finally:
        core.stop_all()  # stop watcher first, flush the final batched commit
