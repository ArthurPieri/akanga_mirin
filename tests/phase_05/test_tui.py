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
from tests._helpers import load_attr


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

    return load_attr(
        ("akanga_tui.app", "AkangaTUI"),
        ("akanga_tui.app", "AkangaApp"),
        ("tui", "AkangaTUI"),
        ("tui", "AkangaApp"),
        hint="a TUI App class (akanga_tui/app.py or tui.py, class AkangaTUI or AkangaApp)",
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


def _collect_rendered_text(app) -> str:
    """Collect all visible text across every screen of the app.

    Walks the full screen stack (so modal/overlay content counts) and knows
    how to extract text from DataTable cells and OptionList prompts in
    addition to plain renderable/label widgets — a node list built on
    DataTable or OptionList is just as valid as one built on ListView.
    """
    parts: list[str] = []

    try:
        from textual.widgets import DataTable, OptionList
    except ImportError:  # pragma: no cover — textual is importorskip'd upstream
        DataTable = OptionList = ()  # type: ignore[assignment]

    screens = list(getattr(app, "screen_stack", None) or [app.screen])
    for screen in screens:
        for w in screen.query("*"):
            parts.append(str(getattr(w, "renderable", "") or ""))
            parts.append(str(getattr(w, "label", "") or ""))
            if DataTable and isinstance(w, DataTable):
                try:
                    for row_key in list(w.rows):
                        parts.extend(str(cell) for cell in w.get_row(row_key))
                except Exception:
                    pass
            if OptionList and isinstance(w, OptionList):
                try:
                    for i in range(w.option_count):
                        parts.append(str(w.get_option_at_index(i).prompt))
                except Exception:
                    pass
            # Last resort: whatever the widget itself renders.
            try:
                parts.append(str(w.render()))
            except Exception:
                pass

    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tui_app_starts_without_crash(vault_with_nodes, indexed_db, tmp_path):
    """The TUI must mount and exit cleanly with no exceptions."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    async with app.run_test() as pilot:
        # Just mounting without crashing satisfies this test.
        # We press 'q' to quit gracefully so the app lifecycle completes.
        await pilot.press("q")


async def test_tui_shows_node_titles(vault_with_nodes, indexed_db, tmp_path):
    """After mounting, node titles from the db must appear somewhere in the widget tree."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    expected_titles = {"Alpha Node", "Beta Node", "Gamma Node"}

    async with app.run_test() as pilot:
        # Allow the app to finish mounting and loading data.
        await pilot.pause()

        # Collect all text rendered by the application — including DataTable
        # rows and OptionList options, so any list-widget choice passes.
        all_text = _collect_rendered_text(pilot.app)

        found = {title for title in expected_titles if title in all_text}
        assert found, (
            f"None of the expected node titles {expected_titles!r} were found in the "
            f"TUI widget tree (ListView, DataTable, and OptionList were all checked).\n"
            f"Collected text sample (first 400 chars): {all_text[:400]!r}\n"
            "Make sure your node list widget populates with titles from the database "
            "during on_mount()."
        )

        await pilot.press("q")


async def test_tui_quit_on_q(vault_with_nodes, indexed_db, tmp_path):
    """Pressing 'q' must exit the application."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")

    # After the context manager exits the app must no longer be running.
    assert not app.is_running, (
        "App is still running after pressing 'q'.\n"
        "Bind 'q' to the quit action: BINDINGS = [Binding('q', 'quit', 'Quit')]"
    )


async def test_tui_search_mode_on_slash(vault_with_nodes, indexed_db, tmp_path):
    """Pressing '/' must activate a search input widget (visible or focused)."""
    pytest.importorskip("textual", reason="textual not installed — skipping TUI tests")
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

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


async def test_tui_node_count_matches_db(vault_with_nodes, indexed_db, tmp_path):
    """The node list must contain exactly as many items as there are nodes in the db."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    # The db fixture indexed 3 nodes (alpha, beta, gamma).
    expected_count = len(indexed_db.list_nodes())
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


async def test_delete_requires_confirmation(vault_with_nodes, indexed_db, tmp_path):
    """Pressing 'd' ONCE must not delete the selected node — confirmation required.

    The keybinding spec: 'd' = Delete selected node (+ confirm). A single
    keypress that immediately destroys a file is the lazygit anti-pattern this
    phase explicitly avoids — push a confirmation screen (or modal) first.
    """
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    count_before = len(indexed_db.list_nodes())
    assert count_before == 3, f"Precondition: expected 3 nodes in db, got {count_before}"

    async with app.run_test() as pilot:
        await pilot.pause()
        # Move selection onto a node, then press 'd' exactly once.
        await pilot.press("j")
        await pilot.press("d")
        await pilot.pause()

        count_after = len(indexed_db.list_nodes())
        assert count_after == count_before, (
            f"A single 'd' keypress deleted a node ({count_before} → {count_after}).\n"
            "Delete must require confirmation: push a confirmation ModalScreen "
            "(or two-step keypress) and only call db.delete_node / os.remove "
            "after the user confirms."
        )

        # Dismiss any confirmation modal so shutdown is clean, then quit.
        await pilot.press("escape")
        await pilot.press("q")

    # The vault files must also be untouched.
    md_files = list(vault_with_nodes.glob("*.md"))
    assert len(md_files) == 3, (
        f"A single 'd' keypress removed a vault file (expected 3 .md files, "
        f"found {len(md_files)}). Never touch the filesystem before the user confirms."
    )


async def test_help_overlay(vault_with_nodes, indexed_db, tmp_path):
    """Pressing '?' must show the keybinding cheatsheet — a pushed screen or new content."""
    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    async with app.run_test() as pilot:
        await pilot.pause()

        stack_before = len(pilot.app.screen_stack)
        text_before = _collect_rendered_text(pilot.app)

        await pilot.press("question_mark")
        await pilot.pause()

        stack_after = len(pilot.app.screen_stack)
        text_after = _collect_rendered_text(pilot.app)

        pushed_screen = stack_after > stack_before
        new_content = text_after != text_before

        assert pushed_screen or new_content, (
            "Pressing '?' changed nothing — no screen was pushed and no new "
            "content appeared.\n"
            "Implement action_help_cheatsheet: build a table from self.BINDINGS "
            "and push a ModalScreen showing it "
            "(Binding('question_mark', 'help_cheatsheet', 'Help', key_display='?'))."
        )

        await pilot.press("escape")
        await pilot.press("q")


async def test_modal_double_dismiss_is_safe(vault_with_nodes, indexed_db, tmp_path):
    """Closing a modal twice must leave the base screen intact (dismiss-once guard).

    Key auto-repeat — or a second close event queued behind the first — can
    deliver another dismissal after the modal has already been popped.  An
    unguarded second ``dismiss()`` / ``pop_screen()`` then pops the BASE
    screen and the app crashes with ScreenStackError.  Route every modal
    exit through a dismiss-once guard so the duplicate is a no-op.
    """
    import inspect

    TUI = _load_tui_class()
    db_path = str(tmp_path / "test.db")
    app = _make_app(TUI, vault=str(vault_with_nodes), db_path=db_path)

    async with app.run_test() as pilot:
        await pilot.pause()

        base_screen = pilot.app.screen
        await pilot.press("question_mark")
        await pilot.pause()

        modal = pilot.app.screen
        if modal is base_screen:
            # An app that shows help without pushing a screen has no modal
            # stack to corrupt — the double-dismiss bug class cannot occur.
            pytest.skip("'?' did not push a screen — nothing to double-dismiss")

        async def _close_once() -> None:
            """Invoke the modal's own close path, exactly as a queued event would.

            Probes only learner-defined exits (action_close / action_cancel /
            on_key) — never Textual's built-in ``action_dismiss``, which is raw
            ``dismiss()`` and sits outside any screen-level guard.
            """
            for name in ("action_close", "action_cancel"):
                method = getattr(modal, name, None)
                if callable(method):
                    result = method()
                    if inspect.isawaitable(result):
                        await result
                    return
            handler = getattr(modal, "on_key", None)
            if callable(handler):
                from textual import events

                result = handler(events.Key("escape", None))
                if inspect.isawaitable(result):
                    await result
                return
            pytest.skip(
                "modal exposes no close action or on_key handler — "
                "cannot exercise its dismissal path"
            )

        await _close_once()
        await pilot.pause()
        try:
            await _close_once()  # the auto-repeat duplicate — must be a no-op
            await pilot.pause()
        except Exception as exc:  # noqa: BLE001 — ANY escape here is the bug
            pytest.fail(
                f"Dismissing the modal a second time raised {type(exc).__name__}: {exc}\n"
                "A duplicate close event (key auto-repeat, or escape queued behind q) "
                "must be a no-op.  Route every modal exit through a dismiss-once "
                "guard — a _DismissOnce mixin whose _finish() sets a flag and calls "
                "self.dismiss(result) only the first time — instead of calling "
                "dismiss()/pop_screen() unguarded."
            )

        assert pilot.app.screen is base_screen, (
            "After closing the help modal twice, the app is no longer on its base "
            f"screen (now on {pilot.app.screen!r}).\n"
            "The second dismiss() popped the screen BELOW the modal.  Make modal "
            "dismissal idempotent with a dismiss-once guard (_finish sets a flag, "
            "then dismisses exactly once)."
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
