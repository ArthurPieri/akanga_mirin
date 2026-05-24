"""Phase 05 test suite — Terminal UI (Textual).

Tests the learner's Textual TUI application.  The TUI class must be importable
as one of:
    - AkangaTUI   from akanga_tui.app
    - AkangaApp   from akanga_tui.app  (alternate name)
    - AkangaTUI   from tui  (flat layout)

The TUI must accept ``vault`` and ``db_path`` constructor arguments so that
tests can point it at a temporary vault and database.

All tests are async and driven by Textual's ``Pilot`` headless driver.
``pytest-asyncio`` must be installed.

Textual itself is an optional dependency — every test skips gracefully when it
is not installed.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_tui_class():
    """
    Locate and return the learner's TUI App class.

    Search order:
      1. akanga_tui.app.AkangaTUI
      2. akanga_tui.app.AkangaApp
      3. tui.AkangaTUI
      4. tui.AkangaApp
    """
    textual = pytest.importorskip("textual", reason="textual not installed — skipping TUI tests")  # noqa: F841

    candidates = [
        ("akanga_tui.app", "AkangaTUI"),
        ("akanga_tui.app", "AkangaApp"),
        ("tui", "AkangaTUI"),
        ("tui", "AkangaApp"),
    ]
    for module_name, class_name in candidates:
        try:
            import importlib
            mod = importlib.import_module(module_name)
            cls = getattr(mod, class_name, None)
            if cls is not None:
                return cls
        except ImportError:
            continue

    pytest.fail(
        "Could not import a TUI App class from AKANGA_SRC.\n"
        "Expected one of:\n"
        "  akanga_tui/app.py  →  class AkangaTUI(App) or AkangaApp(App)\n"
        "  tui.py             →  class AkangaTUI(App) or AkangaApp(App)\n"
        "Make sure your file exists and has no syntax errors."
    )


def _make_app(tui_cls, vault: str, db_path: str):
    """Construct a TUI app instance using the most permissive signature."""
    try:
        return tui_cls(vault=vault, db_path=db_path)
    except TypeError:
        try:
            return tui_cls(vault=vault)
        except TypeError:
            return tui_cls()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tui_app_starts_without_crash(tmp_vault, tmp_db, tmp_path):
    """The TUI must mount and exit cleanly with no exceptions."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(tmp_vault), db_path=db_path)

    async with app.run_test() as pilot:
        # Just mounting without crashing satisfies this test.
        # We press 'q' to quit gracefully so the app lifecycle completes.
        await pilot.press("q")


async def test_tui_shows_node_titles(tmp_vault, tmp_db, tmp_path):
    """After mounting, node titles from the db must appear somewhere in the widget tree."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(tmp_vault), db_path=db_path)

    expected_titles = {"Alpha Node", "Beta Node", "Gamma Node"}

    async with app.run_test() as pilot:
        # Allow the app to finish mounting and loading data.
        await pilot.pause()

        # Collect all text rendered by the application.
        all_text = " ".join(
            str(getattr(w, "renderable", "") or getattr(w, "label", "") or "")
            for w in pilot.app.query("*")
        )

        found = {title for title in expected_titles if title in all_text}
        assert found, (
            f"None of the expected node titles {expected_titles!r} were found in the "
            f"TUI widget tree.\n"
            f"Collected text sample (first 400 chars): {all_text[:400]!r}\n"
            "Make sure your node list widget populates with titles from the database "
            "during on_mount()."
        )

        await pilot.press("q")


async def test_tui_quit_on_q(tmp_vault, tmp_db, tmp_path):
    """Pressing 'q' must exit the application."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(tmp_vault), db_path=db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")

    # After the context manager exits the app must no longer be running.
    assert not app.is_running, (
        "App is still running after pressing 'q'.\n"
        "Bind 'q' to the quit action: BINDINGS = [Binding('q', 'quit', 'Quit')]"
    )


async def test_tui_search_mode_on_slash(tmp_vault, tmp_db, tmp_path):
    """Pressing '/' must activate a search input widget (visible or focused)."""
    pytest.importorskip("textual", reason="textual not installed — skipping TUI tests")
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(tmp_vault), db_path=db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()

        # A search input should now be visible somewhere in the tree.
        # Accept any of: Input, SearchInput, or a widget whose id/classes suggest search.
        from textual.widgets import Input

        inputs = list(pilot.app.query(Input))
        visible_inputs = [w for w in inputs if w.display]

        assert visible_inputs, (
            "After pressing '/', no visible Input widget was found in the widget tree.\n"
            "Implement a search input that is shown or focused when the user presses '/'.\n"
            "Example: bind '/' to an action that shows a SearchInput or Input widget."
        )

        await pilot.press("escape")
        await pilot.press("q")


async def test_tui_node_count_matches_db(tmp_vault, tmp_db, tmp_path):
    """The node list must contain exactly as many items as there are nodes in the db."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(tmp_vault), db_path=db_path)

    # The db fixture indexed 3 nodes (alpha, beta, gamma).
    expected_count = len(tmp_db.list_nodes())
    assert expected_count == 3, f"Precondition: expected 3 nodes in db, got {expected_count}"

    async with app.run_test() as pilot:
        await pilot.pause()

        # Count list items.  Accept ListView / ListItem or any widget whose
        # CSS class or id suggests it is an item in the node list.
        try:
            from textual.widgets import ListItem, ListView
            list_views = list(pilot.app.query(ListView))
            if list_views:
                items = list(list_views[0].query(ListItem))
                item_count = len(items)
            else:
                # Fallback: count any widget whose id or classes mention "node"
                item_count = len([
                    w for w in pilot.app.query("*")
                    if "node" in (w.id or "") or "node" in " ".join(w.classes)
                ])
        except Exception:
            item_count = 0

        assert item_count == expected_count, (
            f"Expected {expected_count} node list items but found {item_count}.\n"
            "Your node list widget must render one item per node returned by the db."
        )

        await pilot.press("q")


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


async def test_tui_empty_vault_starts_without_crash(empty_vault, empty_db, tmp_path):
    """The TUI must start cleanly even when the vault / db contain zero nodes."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "empty.db")
    app = _make_app(TUI, vault=str(empty_vault), db_path=db_path)

    try:
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
    except (IndexError, KeyError, AttributeError) as exc:
        pytest.fail(
            f"TUI crashed with {type(exc).__name__}: {exc} when starting with an empty vault.\n"
            "Guard your on_mount() / compose() against an empty node list."
        )
