"""Phase 02 tests — indexer: index_file, full_scan_and_index, edge cases."""
import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest

from tests.phase_02.conftest import _load_db, _load_indexer, _load_parser

# Bound by the autouse fixture below at fixture time -- not import time -- so
# a missing/broken learner module is reported through the AKANGA_SRC guard's
# diagnostics instead of a raw collection error (adversarial-analysis-v5 #2).
GraphDatabase = None
_indexer_mod = None


@pytest.fixture(scope="module", autouse=True)
def _bind_learner_modules():
    global GraphDatabase, _indexer_mod
    GraphDatabase = _load_db()
    _indexer_mod = _load_indexer()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_md(directory: Path, filename: str, node_id: str, title: str, body: str = "") -> Path:
    """Write a minimal .md file with YAML frontmatter to *directory*."""
    content = dedent(f"""\
        ---
        id: {node_id}
        title: {title}
        type: note
        tags: []
        edges: []
        ---

        {body}
        """)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. index_file
# ---------------------------------------------------------------------------

def test_index_single_file(tmp_db: str, tmp_vault: Path):
    """index_file() parses a .md file and upserts the node into the DB."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    path = _write_md(tmp_vault, "single.md", "aaaa0001-0000-0000-0000-000000000001", "Single Node")

    index_file(str(path), db, str(tmp_vault))

    node = db.get_node("aaaa0001-0000-0000-0000-000000000001")
    assert node is not None
    assert node.title == "Single Node"


# ---------------------------------------------------------------------------
# 2. full_scan_and_index
# ---------------------------------------------------------------------------

def test_full_scan_indexes_all_files(tmp_db: str, tmp_vault: Path):
    """full_scan_and_index() indexes every .md file in the vault."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    _write_md(tmp_vault, "node1.md", "bbbb0001-0000-0000-0000-000000000001", "Alpha")
    _write_md(tmp_vault, "node2.md", "bbbb0002-0000-0000-0000-000000000002", "Beta")
    _write_md(tmp_vault, "node3.md", "bbbb0003-0000-0000-0000-000000000003", "Gamma")

    full_scan_and_index(str(tmp_vault), db)

    ids = {"bbbb0001-0000-0000-0000-000000000001",
           "bbbb0002-0000-0000-0000-000000000002",
           "bbbb0003-0000-0000-0000-000000000003"}
    for node_id in ids:
        assert db.get_node(node_id) is not None


def test_full_scan_skips_hidden_dirs(tmp_db: str, tmp_vault: Path):
    """Files inside hidden directories (e.g. .git/) are not indexed."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    hidden_dir = tmp_vault / ".git"
    hidden_dir.mkdir()
    _write_md(hidden_dir, "secret.md", "cccc0001-0000-0000-0000-000000000001", "Hidden Node")

    full_scan_and_index(str(tmp_vault), db)

    assert db.get_node("cccc0001-0000-0000-0000-000000000001") is None


def test_full_scan_skips_non_md_files(tmp_db: str, tmp_vault: Path):
    """Non-.md files in the vault directory are silently skipped."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    txt_file = tmp_vault / "notes.txt"
    txt_file.write_text("this is plain text\n", encoding="utf-8")
    # Also add one valid node so the scan has something to process
    _write_md(tmp_vault, "valid.md", "dddd0001-0000-0000-0000-000000000001", "Valid Node")

    # Must not raise even though notes.txt is not a markdown file.
    full_scan_and_index(str(tmp_vault), db)

    assert db.get_node("dddd0001-0000-0000-0000-000000000001") is not None


def test_full_scan_returns_count(tmp_db: str, tmp_vault: Path):
    """full_scan_and_index() returns the number of nodes successfully indexed."""
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    for i in range(3):
        _write_md(tmp_vault, f"count_{i}.md", f"eeee000{i}-0000-0000-0000-00000000000{i}", f"Count Node {i}")

    count = full_scan_and_index(str(tmp_vault), db)
    assert count == 3


def test_reindex_updates_node(tmp_db: str, tmp_vault: Path):
    """Re-indexing a file whose title changed updates the DB record."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    path = _write_md(tmp_vault, "reindex.md", "ffff0001-0000-0000-0000-000000000001", "Old Title")
    index_file(str(path), db, str(tmp_vault))

    # Overwrite with a new title
    _write_md(tmp_vault, "reindex.md", "ffff0001-0000-0000-0000-000000000001", "New Title")
    index_file(str(path), db, str(tmp_vault))

    node = db.get_node("ffff0001-0000-0000-0000-000000000001")
    assert node.title == "New Title"


# ---------------------------------------------------------------------------
# 3. Two-pass edge resolution + DB expendability (the phase's core promises)
# ---------------------------------------------------------------------------

def test_two_pass_edge_resolution(tmp_db: str, tmp_vault: Path):
    """A wikilink [[Beta]] in alpha.md must become a resolved edge A→B in the DB.

    alpha.md sorts before beta.md, so a single-pass indexer would try to
    resolve the link before Beta exists. The two-pass design (index all nodes
    first, then extract edges) is what makes this resolve.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    id_alpha = "abab0001-0000-0000-0000-000000000001"
    id_beta  = "abab0002-0000-0000-0000-000000000002"
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="This links to [[Beta]].")
    _write_md(tmp_vault, "b-beta.md",  id_beta,  "Beta")

    full_scan_and_index(str(tmp_vault), db)

    neighbors = db.get_neighbors(id_alpha)
    assert any(n.id == id_beta for n in neighbors), (
        "After full_scan_and_index, the wikilink [[Beta]] in alpha.md must "
        "exist as an edge Alpha→Beta in the edges table.\n"
        f"get_neighbors(Alpha) returned: {[getattr(n, 'title', n) for n in neighbors]!r}\n"
        "Pass 2 must re-read each node's body from disk (parse_node_file), call "
        "extract_wikilinks, resolve_wikilink, then db.upsert_edge. An indexer "
        "that extracts zero edges silently breaks Phases 3, 5, and 8."
    )


def test_db_is_expendable(tmp_db: str, tmp_vault: Path):
    """Delete the DB file, re-index, and get back the identical graph (doc Deliverable).

    This is the core architectural promise of the phase: the DB is a derived
    index, the .md files are the source of truth.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    id_alpha = "cdcd0001-0000-0000-0000-000000000001"
    id_beta  = "cdcd0002-0000-0000-0000-000000000002"
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="This links to [[Beta]].")
    _write_md(tmp_vault, "b-beta.md",  id_beta,  "Beta")

    def _snapshot(db) -> tuple[set, set]:
        node_ids = {n.id for n in db.list_nodes(limit=10_000)}
        conn = sqlite3.connect(tmp_db)
        edges = set(
            conn.execute("SELECT source_id, target_id FROM edges").fetchall()
        )
        conn.close()
        return node_ids, edges

    db = GraphDatabase(tmp_db)
    full_scan_and_index(str(tmp_vault), db)
    nodes_before, edges_before = _snapshot(db)
    assert len(nodes_before) == 2, "Precondition: both nodes must be indexed."
    db.close()

    # Destroy the derived index (including WAL sidecar files).
    for suffix in ("", "-wal", "-shm"):
        sidecar = Path(tmp_db + suffix)
        if sidecar.exists():
            sidecar.unlink()
    assert not Path(tmp_db).exists(), "Precondition: DB file must be gone."

    db2 = GraphDatabase(tmp_db)
    full_scan_and_index(str(tmp_vault), db2)
    nodes_after, edges_after = _snapshot(db2)
    db2.close()

    assert nodes_after == nodes_before, (
        "After deleting the DB and re-indexing, the node set must be identical.\n"
        f"Before: {sorted(nodes_before)!r}\nAfter:  {sorted(nodes_after)!r}\n"
        "If this fails, some node state lives only in the DB — the DB must be "
        "fully derivable from the .md files."
    )
    assert edges_after == edges_before, (
        "After deleting the DB and re-indexing, the edge set must be identical.\n"
        f"Before: {sorted(edges_before)!r}\nAfter:  {sorted(edges_after)!r}\n"
        "Edges must be re-derived from wikilinks on every full scan — never "
        "stored only in the DB."
    )


# ---------------------------------------------------------------------------
# 4. Error path
# ---------------------------------------------------------------------------

def test_index_missing_file_raises(tmp_db: str, tmp_vault: Path):
    """index_file() on a non-existent path raises an exception (FileNotFoundError or similar)."""
    index_file = _indexer_mod.index_file

    db = GraphDatabase(tmp_db)
    missing = str(tmp_vault / "does-not-exist.md")

    with pytest.raises(Exception):
        index_file(missing, db, str(tmp_vault))


# ---------------------------------------------------------------------------
# 5. Re-index idempotency (adversarial-analysis-v3 finding #1)
#
# The indexer's own docstring promises idempotence; round 3 reproduced the
# opposite (2 → 4 → 6 edge rows across three identical scans). These tests
# make that promise falsifiable: scan twice, nothing changes; edit one file,
# only that node's edges change; delete a file, its node is tombstoned.
# ---------------------------------------------------------------------------

def _node_count(db_path: str) -> int:
    """Count node rows via a fresh read connection (WAL-safe, like _snapshot)."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    finally:
        conn.close()


def _edge_row_count(db_path: str) -> int:
    """Count RAW edge rows — duplicates that DISTINCT would mask still count."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    finally:
        conn.close()


def _edge_pairs(db_path: str) -> list[tuple[str, str]]:
    """All (source_id, target_id) edge rows, duplicates included."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT source_id, target_id FROM edges").fetchall()
    finally:
        conn.close()


def _three_node_vault(tmp_vault: Path) -> tuple[str, str, str]:
    """alpha → [[Beta]], beta → [[Gamma]], gamma plain. Returns the three ids."""
    id_alpha = "1d1d0001-0000-0000-0000-000000000001"
    id_beta  = "1d1d0002-0000-0000-0000-000000000002"
    id_gamma = "1d1d0003-0000-0000-0000-000000000003"
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="Links to [[Beta]].")
    _write_md(tmp_vault, "b-beta.md",  id_beta,  "Beta",  body="Links to [[Gamma]].")
    _write_md(tmp_vault, "c-gamma.md", id_gamma, "Gamma")
    return id_alpha, id_beta, id_gamma


def test_rescan_unchanged_vault_is_noop(tmp_db: str, tmp_vault: Path):
    """Scanning the SAME unchanged vault twice must not change node or edge counts.

    This is the missing test class round 3 exposed: the reference indexer
    duplicated every edge on every re-scan (2 → 4 → 6 rows, reproduced),
    while its docstring claimed idempotence.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    _three_node_vault(tmp_vault)

    full_scan_and_index(str(tmp_vault), db)
    nodes_first = _node_count(tmp_db)
    edges_first = _edge_row_count(tmp_db)
    assert nodes_first == 3, "Precondition: all 3 nodes must be indexed by the first scan."
    assert edges_first >= 2, "Precondition: both wikilink edges must exist after the first scan."

    # Nothing on disk changed — this scan must be a complete no-op.
    full_scan_and_index(str(tmp_vault), db)
    nodes_second = _node_count(tmp_db)
    edges_second = _edge_row_count(tmp_db)
    db.close()

    assert nodes_second == nodes_first, (
        f"Node count changed on a re-scan of an UNCHANGED vault: "
        f"{nodes_first} → {nodes_second}.\n"
        "every re-scan must be a no-op on an unchanged vault — add "
        "UNIQUE(source_id,target_id,relation) / INSERT OR IGNORE and skip "
        "unchanged files"
    )
    assert edges_second == edges_first, (
        f"Edge ROW count grew on a re-scan of an UNCHANGED vault: "
        f"{edges_first} → {edges_second}.\n"
        "every re-scan must be a no-op on an unchanged vault — add "
        "UNIQUE(source_id,target_id,relation) / INSERT OR IGNORE and skip "
        "unchanged files\n"
        "(A blind INSERT with a fresh uuid4 PK duplicates every edge on every "
        "scan: weekly refreshes for a year ≈ 243k duplicate rows. DISTINCT in "
        "get_neighbors only masks it — ego graphs and RAG triples surface it.)"
    )


def test_rescan_after_editing_one_file_changes_only_that_nodes_edges(
    tmp_db: str, tmp_vault: Path
):
    """Editing ONE file between scans must update only that node's outgoing edges.

    The fix contract (v3 #1): per-changed-node `DELETE FROM edges WHERE
    source_id = ?` then re-derive — stale edges from the edited node must
    disappear, and untouched nodes' edges must neither change nor duplicate.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    id_alpha, id_beta, id_gamma = _three_node_vault(tmp_vault)

    full_scan_and_index(str(tmp_vault), db)

    # Edit alpha only: its link now points at Gamma instead of Beta.
    _write_md(tmp_vault, "a-alpha.md", id_alpha, "Alpha", body="Links to [[Gamma]].")
    full_scan_and_index(str(tmp_vault), db)

    pairs = _edge_pairs(tmp_db)
    db.close()

    alpha_edges = [p for p in pairs if p[0] == id_alpha]
    beta_edges  = [p for p in pairs if p[0] == id_beta]

    assert alpha_edges == [(id_alpha, id_gamma)], (
        f"After editing alpha.md ([[Beta]] → [[Gamma]]) and re-scanning, "
        f"alpha's outgoing edges are {alpha_edges!r}; expected exactly "
        f"[(alpha, gamma)].\n"
        "Re-indexing a changed node must DELETE its old edge rows before "
        "re-deriving — otherwise the stale Alpha→Beta edge survives forever "
        "(or the new edge piles onto the old as a duplicate)."
    )
    assert beta_edges == [(id_beta, id_gamma)], (
        f"Beta was NOT edited, but its edges changed: {beta_edges!r}; "
        f"expected exactly [(beta, gamma)].\n"
        "An unchanged node's edges must survive a re-scan exactly once — "
        "neither dropped nor duplicated. Skip unchanged files (hash check "
        "BEFORE parse) and make edge inserts idempotent "
        "(UNIQUE(source_id,target_id,relation) / INSERT OR IGNORE)."
    )


def test_rescan_after_deleting_file_tombstones_node(tmp_db: str, tmp_vault: Path):
    """Deleting a .md file then re-scanning must remove its node (and its edges).

    The DB is a derived index of the files — a note deleted on disk must not
    live in the index (or FTS, or RAG context) forever.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    id_alpha, id_beta, _ = _three_node_vault(tmp_vault)

    full_scan_and_index(str(tmp_vault), db)
    assert db.get_node(id_beta) is not None, "Precondition: Beta indexed by first scan."

    (tmp_vault / "b-beta.md").unlink()
    full_scan_and_index(str(tmp_vault), db)

    ghost = db.get_node(id_beta)
    pairs = _edge_pairs(tmp_db)
    db.close()

    assert ghost is None, (
        "b-beta.md was deleted from disk, but its node is still in the DB "
        "after a full re-scan.\n"
        "full_scan_and_index needs a tombstone pass: any node whose path no "
        "longer exists under the vault must be deleted from nodes (and FTS). "
        "Without it, deleted notes haunt search results and RAG context "
        "forever — the DB is supposed to be derivable from the files."
    )
    referencing = [p for p in pairs if id_beta in p]
    assert referencing == [], (
        f"Edges still reference the deleted node Beta: {referencing!r}.\n"
        "Tombstoning a node must also remove its edges (ON DELETE CASCADE "
        "covers source_id; edges TARGETING the dead node must go too — "
        "alpha's [[Beta]] wikilink no longer resolves, so re-derivation must "
        "not keep the old row)."
    )


# ---------------------------------------------------------------------------
# 6. UUID write-back stability (adversarial-analysis-v3 finding #1e)
# ---------------------------------------------------------------------------

def test_minted_uuid_is_written_back_and_stable_across_rescans(
    tmp_db: str, tmp_vault: Path
):
    """A no-id file gets its minted UUID written back to disk — once, forever.

    Round 3 measured the failure mode: an Obsidian-style vault with no `id:`
    fields gets fresh UUIDs re-minted on EVERY scan, orphaning every edge
    that pointed at the previous id. The contract: mint once, persist the id
    into the file's frontmatter during indexing, never re-mint.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index

    db = GraphDatabase(tmp_db)
    no_id_file = tmp_vault / "no-id.md"
    no_id_file.write_text(
        "---\ntitle: No Id Note\ntype: note\ntags: []\n---\n\nBody text.\n",
        encoding="utf-8",
    )

    full_scan_and_index(str(tmp_vault), db)

    nodes = list(db.list_nodes(limit=100))
    assert len(nodes) == 1, f"Precondition: exactly one node indexed, got {len(nodes)}."
    minted_id = nodes[0].id

    on_disk = no_id_file.read_text(encoding="utf-8")
    assert minted_id in on_disk, (
        f"The indexer minted id {minted_id!r} for no-id.md but never wrote it "
        "back to the file's frontmatter.\n"
        "Mint once, persist immediately: write the minted UUID back into the "
        ".md file (write_node_file) during indexing. A UUID that lives only "
        "in the DB is re-minted on the next scan, orphaning every edge that "
        "pointed at the old id."
    )

    # Re-scan: the persisted id must be parsed back, not re-minted.
    full_scan_and_index(str(tmp_vault), db)
    nodes_after = list(db.list_nodes(limit=100))
    db.close()

    assert len(nodes_after) == 1, (
        f"Re-scanning the same vault produced {len(nodes_after)} node rows "
        "for a single file.\n"
        "If the minted UUID is written back to frontmatter, the second scan "
        "parses the SAME id — it must never mint a second one."
    )
    assert nodes_after[0].id == minted_id, (
        f"The node's id changed across re-scans: {minted_id!r} → "
        f"{nodes_after[0].id!r}.\n"
        "Identity must be stable: the first scan mints and writes back, every "
        "later scan reads the same id from the file."
    )
    assert minted_id in no_id_file.read_text(encoding="utf-8"), (
        "The on-disk id changed (or vanished) on the second scan — write-back "
        "must happen exactly once; an unchanged file must not be rewritten."
    )


# ---------------------------------------------------------------------------
# 7. Inline typed edges reach the graph (adversarial-analysis-v4 finding #7a)
#
# Round 4 ran the system end-to-end and found write_back — Phase 1A's
# flagship — was dead code: no indexer, watcher, REST, or MCP path ever
# called it, so `[[Target | relation]]` reached the graph as an untyped
# "wikilink" edge with the relation silently dropped. This test pins the
# fix contract: index_file's changed branch calls write_back to fold inline
# typed edges into frontmatter BEFORE parsing, and the ordinary frontmatter
# edge pass then derives the typed edge.
# ---------------------------------------------------------------------------

def _edge_triples(db_path: str) -> list[tuple[str, str, str]]:
    """All (source_id, target_id, relation) edge rows, duplicates included."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT source_id, target_id, relation FROM edges"
        ).fetchall()
    finally:
        conn.close()


def test_inline_typed_edge_folds_on_index(tmp_db: str, tmp_vault: Path):
    """`[[Target Note | supports]]` in prose must become a TYPED edge in the DB
    and a folded `edges:` entry in the source file's frontmatter — and stay
    idempotent on re-scan.
    """
    full_scan_and_index = _indexer_mod.full_scan_and_index
    parser_mod = _load_parser()

    db = GraphDatabase(tmp_db)
    id_source = "fade0001-0000-0000-0000-000000000001"
    id_target = "fade0002-0000-0000-0000-000000000002"
    source_path = _write_md(
        tmp_vault, "a-source.md", id_source, "Source Note",
        body="This claim [[Target Note | supports]] the target's argument.",
    )
    _write_md(tmp_vault, "b-target.md", id_target, "Target Note")

    full_scan_and_index(str(tmp_vault), db)

    # (a) The DB edge must carry the typed relation, not the untyped fallback.
    relations = {
        rel for src, tgt, rel in _edge_triples(tmp_db)
        if src == id_source and tgt == id_target
    }
    assert "supports" in relations, (
        f"No Source→Target edge with relation 'supports' in the DB after "
        f"indexing; found relations {sorted(relations)!r}.\n"
        "index_file must call write_back so the Phase-1A typed syntax "
        "actually reaches the graph: fold the inline `[[Target Note | "
        "supports]]` into the frontmatter `edges:` block BEFORE parsing, "
        "then let the frontmatter pass derive the typed edge. An indexer "
        "that only sees the wikilink half stores an untyped 'wikilink' row "
        "and silently drops the relation the learner wrote."
    )

    # (b) The fold must be persisted to the source file's frontmatter.
    parse_back = parser_mod.parse_node_file(str(source_path))
    folded = [
        e for e in (parse_back.frontmatter.get("edges") or [])
        if isinstance(e, dict)
        and e.get("relation") == "supports"
        and e.get("target") == "Target Note"
    ]
    assert folded, (
        f"a-source.md's frontmatter has no folded edges: entry for "
        f"(supports, Target Note); frontmatter edges: "
        f"{parse_back.frontmatter.get('edges')!r}.\n"
        "write_back must persist the fold to disk — the .md files are the "
        "source of truth, so a typed edge that exists only in the DB "
        "vanishes on the next `rm *.db && scan`."
    )

    # (c) Idempotence survives the fold: a second scan changes nothing.
    nodes_before = _node_count(tmp_db)
    edges_before = _edge_row_count(tmp_db)
    full_scan_and_index(str(tmp_vault), db)
    nodes_after = _node_count(tmp_db)
    edges_after = _edge_row_count(tmp_db)
    db.close()

    assert (nodes_after, edges_after) == (nodes_before, edges_before), (
        f"Re-scanning after the fold changed the DB: nodes "
        f"{nodes_before} → {nodes_after}, edge rows "
        f"{edges_before} → {edges_after}.\n"
        "The fold rewrites the file, so the stored content_hash must be "
        "taken from the FOLDED bytes (re-hash after write_back, exactly "
        "like the minted-id write-back) — otherwise every scan re-parses "
        "and re-folds the file forever, and the scan;scan no-op contract "
        "breaks."
    )
