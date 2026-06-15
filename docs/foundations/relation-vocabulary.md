# Relation Vocabulary — The 72 Built-in Relation Types

**Audience:** anyone choosing a relation type for an edge · **Read time:** ~10 min skim; reference, don't memorize

**This file is THE relation registry.** Every relation ID used anywhere in the
repository — phase docs, skeletons, tests, solutions, examples — is defined here
and only here.

Akanga ships 72 relation types organized into 11 semantic categories. This is the
vocabulary you build in Phase 1 and query by ID in Phase 8 (`list_relation_types()`).

> **Note:** `HT-005 instance_of` was added after the initial release; older
> documents that say "71 types" are counting the pre-`instance_of` vocabulary.

Custom types are always allowed — assigned a UUID at creation, no pre-registration
required. The built-in types exist so common relations are named consistently across
vaults and can be compared, filtered, and inferred programmatically.

**How to browse this file:**
- `make foundations TOPIC=relation-vocabulary` — opens this doc in glow
- Phase 1 uses this to implement the relation registry
- Phase 8's `list_relation_types()` MCP tool returns rows from this vocabulary

**ID format:** category prefix + 3-digit number (e.g. `EP-001`). IDs are stable forever —
the relation name is a human-readable display cache and can be renamed without breaking edges.

> **Conformance rule:** because IDs are stable forever, every `XX-NNN` literal that
> appears anywhere else in this repository (phase docs, `SERVER_INSTRUCTIONS`,
> skeleton comments, test fixtures, examples) MUST match this table exactly.
> If another document disagrees with this file, the other document is wrong —
> fix it there, never here. This rule is CI-checkable: grep for `[A-Z]{2}-[0-9]{3}`
> and verify each hit against this registry.

**Flags:** `⇄` = symmetric (A→B implies B→A with the same label);
`↔ XX-NNN` = has a natural inverse in this vocabulary;
`★` = core tier (see below).

---

## The Core Tier — Start Here

72 types is a menu, not a syllabus. Empirical audits of real vaults (including this
curriculum's own exercise vaults) show that roughly **15 types do almost all of the
work**. Start with the core tier below — marked `★` in the tables — and reach for
the extended tier only when none of the core types fits. A vault written entirely in
core-tier relations is a perfectly good vault.

| Core type | ID | One-line use |
|---|---|---|
| `supports` | `EP-001` | A is evidence for B |
| `contradicts` | `EP-002` | A and B can't both be true |
| `qualifies` | `EP-003` | A adds a caveat to B |
| `is_part_of` | `HT-002` | A is a component of B |
| `subtype_of` | `HT-003` | A is a kind of B |
| `instance_of` | `HT-005` | A is a concrete example of class B |
| `implements` | `SC-002` | A realizes spec/pattern B |
| `uses` | `SC-003` | A employs B as a tool |
| `enables` | `CT-002` | A makes B possible |
| `solves` | `CT-005` | A resolves problem B |
| `motivated_by` | `CT-006` | A arose in response to B |
| `has_prerequisite` | `CT-009` | understand B before A |
| `is_analogous_to` | `CC-002` | A mirrors B across domains |
| `contrasts_with` | `CC-006` | A is set against B deliberately |
| `is_applied_in` | `PA-002` | concept A is used in project B |
| `has_context` | `TC-004` | A lives inside cultural/domain context B |

(That is 15 starters plus `contradicts`, which travels as a pair with `supports`.)
Everything not marked `★` is the **extended tier** — valid, stable, and there when
you need precision, but not where you begin.

---

## Epistemic / Reasoning (10)
*How ideas relate in terms of knowledge, truth, and argument.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `EP-001` | `supports` | A provides evidence, reasoning, or data that strengthens B | ★ |
| `EP-002` | `contradicts` | A conflicts with or undermines B — they can't both be fully true | ⇄ ★ |
| `EP-003` | `qualifies` | A adds nuance, conditions, or caveats to B without contradicting it | ★ |
| `EP-004` | `confirms` | A independently corroborates findings or conclusions in B | |
| `EP-005` | `implies` | A logically entails or strongly suggests B | |
| `EP-006` | `questions` | A raises unresolved doubts about B without firm counter-evidence | |
| `EP-007` | `corrects` | A corrects errors in B | |
| `EP-008` | `updates` | A provides updated or revised information that supersedes parts of B | |
| `EP-009` | `extends` | A builds upon and adds to facts or ideas in B | |
| `EP-010` | `synthesizes` | A combines ideas from multiple sources including B into a unified view | |

---

## Hierarchical / Taxonomic (5)
*Classification, containment, and hierarchy.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `HT-001` | `contains` | A is a collection or container that includes B | ↔ HT-002 |
| `HT-002` | `is_part_of` | A is a component, section, or member of B | ↔ HT-001 ★ |
| `HT-003` | `subtype_of` | A is a more specific *class* or *kind* of B (subclass → class) | ★ |
| `HT-004` | `sibling_of` | A and B are at the same level of a hierarchy, sharing a common parent | ⇄ |
| `HT-005` | `instance_of` | A is one concrete *individual* of the class B (instance → class) | ★ |

**`instance_of` vs `subtype_of`:** `instance_of` links an individual to its class
("Nhamandu `instance_of` Guaraní Deity" — Nhamandu is one specific deity), while
`subtype_of` links a class to a broader class ("Guaraní Deity `subtype_of` Deity" —
every Guaraní deity is also a deity). In plain language: use `instance_of` for "this
is *an example of*", `subtype_of` for "this is *a kind of*". (For readers who know
RDF: `instance_of` is `rdf:type`, `subtype_of` is `rdfs:subClassOf`.)

---

## Structural / Compositional (7)
*How things depend on, implement, or build from each other.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `SC-001` | `depends_on` | A requires B to function, exist, or be understood | |
| `SC-002` | `implements` | A is a concrete realization of the abstract specification or pattern B | ★ |
| `SC-003` | `uses` | A employs B as a component, library, or tool | ★ |
| `SC-004` | `overrides` | A replaces inherited behavior from B | |
| `SC-005` | `satisfies` | A (design/implementation) satisfies the requirement B | |
| `SC-006` | `verifies` | A (test/analysis) verifies that a design satisfies requirement B | |
| `SC-007` | `aggregates` | A loosely groups B (B can exist independently of A) | |

> **Note:** `satisfies` and `verifies` are complementary (both point at the requirement), not inverses.

---

## Causal / Temporal (12)
*How things produce, enable, follow, or precede each other.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `CT-001` | `causes` | A directly and reliably produces B | |
| `CT-002` | `enables` | A makes B possible without directly causing it | ★ |
| `CT-003` | `blocks` | A prevents, impedes, or is fundamentally incompatible with B | |
| `CT-004` | `led_to` | A historically contributed to or resulted in B | |
| `CT-005` | `solves` | A addresses and resolves problem B | ★ |
| `CT-006` | `motivated_by` | A was motivated by or arose in response to B | ★ |
| `CT-007` | `precedes` | A comes before B in time or logical order | ↔ CT-008 |
| `CT-008` | `follows` | A comes after B in time or logical order | ↔ CT-007 |
| `CT-009` | `has_prerequisite` | B must exist or be understood before A | ★ |
| `CT-010` | `triggers` | A initiates or activates B | |
| `CT-011` | `produces` | A generates B as an output or result | ↔ CT-012 |
| `CT-012` | `consumes` | A takes B as an input or resource | ↔ CT-011 |

---

## Attribution / Provenance (7)
*Who made it, where it came from, what it's based on.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `AP-001` | `derived_from` | A was created by transforming or adapting B | |
| `AP-002` | `based_on` | A was built upon or inspired by B as a foundation | |
| `AP-003` | `replaces` | A supersedes or is the successor to B | |
| `AP-004` | `was_generated_by` | A (entity) was produced by activity B | |
| `AP-005` | `was_quoted_from` | A repeats content from B as a quotation | |
| `AP-006` | `is_adaptation_of` | A is adapted from B (film from novel, concept from paper, etc.) | |
| `AP-007` | `is_summary_of` | A is an abstract or summary of B | |

---

## Documentary / Reference (6)
*How one thing describes, discusses, or points to another.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `DR-001` | `references` | A cites or points to B — neutral, no strong epistemic claim | |
| `DR-002` | `discusses` | A examines, analyzes, or writes about B at length | |
| `DR-003` | `documents` | A describes or explains how B works | |
| `DR-004` | `reviews` | A provides a critical evaluation of B | |
| `DR-005` | `recommended_reading` | A recommends B as further reading on this topic | |
| `DR-006` | `mentions` | A references B in passing without being primarily about it | |

---

## Comparative / Contrastive (8)
*How things compare, contrast, or substitute for each other.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `CC-001` | `is_similar_to` | A resembles B structurally or conceptually without being the same | ⇄ |
| `CC-002` | `is_analogous_to` | A is structurally similar to B in a different domain (cross-domain analogy) | ⇄ ★ |
| `CC-003` | `is_alternative_to` | A can substitute for B in a given context | ⇄ |
| `CC-004` | `is_opposite_of` | A is the conceptual inverse or antithesis of B | ⇄ |
| `CC-005` | `is_better_than` | A is preferable to B in a specific, stated context | |
| `CC-006` | `contrasts_with` | A is deliberately set in contrast to B to highlight differences | ⇄ ★ |
| `CC-007` | `is_related_to` | A is associatively related to B (non-hierarchical, non-specific) | ⇄ |
| `CC-008` | `see_also` | Cross-reference to B without a stronger semantic claim | ⇄ |

---

## Evolutionary / Versioning (2)
*How things evolve or get partially modified over time.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `EV-001` | `amends` | A modifies specific parts of B without fully replacing it | |
| `EV-002` | `revises` | A is a revised or updated version of B | |

---

## Personal / Associative (3)
*Your personal relationship to the knowledge.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `PA-001` | `inspired_by` | A was created under the intellectual influence of B | |
| `PA-002` | `is_applied_in` | Concept or idea A is practically used in project or context B | ★ |
| `PA-003` | `learned_from` | A is a lesson or insight derived from experience or source B | |

---

## Social / Organizational (8)
*Relations between people, roles, and organizations.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `SO-001` | `knows` | A has some acquaintance with person B | ⇄ |
| `SO-002` | `works_with` | A collaborates with B professionally | ⇄ |
| `SO-003` | `works_for` | A is employed by or works within organization B | |
| `SO-004` | `founded` | A founded or created organization B | |
| `SO-005` | `member_of` | A is a member of organization or group B | |
| `SO-006` | `affiliated_with` | A has a formal affiliation with organization B | ⇄ |
| `SO-007` | `reports_to` | A reports to person or role B in a hierarchy | ↔ SO-008 |
| `SO-008` | `manages` | A manages or is responsible for person or unit B | ↔ SO-007 |

---

## Topical / Classification (4)
*Soft relations for categorization and context.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `TC-001` | `has_topic` | A is about or relevant to the topic or field B | |
| `TC-002` | `tagged_as` | A is loosely categorized as B | |
| `TC-003` | `belongs_to` | A belongs to category, project, or domain B | |
| `TC-004` | `has_context` | A is understood within the cultural or domain context of B | ★ |

---

## Choosing Between Overlapping Types

Two clusters of the vocabulary overlap heavily in practice. Use these discriminators.

### The "supersedes" cluster — `EP-007`, `EP-008`, `AP-003`, `EV-001`, `EV-002`

All five say "A is somehow newer or more right than B." Pick by asking *what was
wrong with B and how much of it survives*:

- `EP-007 corrects` — **B contains an error.** A fixes a claim that was wrong from
  the start. ("Errata note `corrects` Chapter 3.")
- `EP-008 updates` — **B was right at the time.** A carries newer information; most
  of B remains valid. ("2025 benchmark `updates` 2023 benchmark.")
- `AP-003 replaces` — **B is obsolete as a whole.** A is the successor artifact;
  readers should stop using B entirely. ("v2 design doc `replaces` v1 design doc.")
- `EV-001 amends` — **B stays primary.** A patches specific parts of B without
  superseding it. ("Addendum `amends` the contract.")
- `EV-002 revises` — **same work, new edition.** A is a revised version of the same
  document or idea — B's identity continues in A. ("Draft 2 `revises` Draft 1.")

Rule of thumb: error → `corrects`; new info → `updates`; new artifact → `replaces`;
partial patch → `amends`; new edition → `revises`.

### The "weak link" cluster — `DR-001`, `DR-006`, `CC-007`, `CC-008`

All four say "A and B are connected, somehow." Pick by asking *how explicit the
connection is in A's body*:

- `DR-001 references` — **A explicitly cites B** (a quotation, footnote, or named
  citation appears in A's text). Directed: the citation lives in A.
- `DR-006 mentions` — **B appears in passing** in A's text, but A is not about B
  and makes no citation-level claim. Directed, weaker than `references`.
- `CC-007 is_related_to` — **conceptual association, no textual citation** in either
  body. Symmetric. Use when you sense a connection you cannot yet name — and
  consider upgrading it to a more specific type later.
- `CC-008 see_also` — **pure navigation aid.** Symmetric, the weakest of all: "a
  reader of A may also enjoy B." No semantic claim whatsoever.

Rule of thumb: cited in the text → `references`; named in passing → `mentions`;
felt connection → `is_related_to`; browsing hint → `see_also`.

---

## Summary

| Category | Prefix | Count |
|---|---|---|
| Epistemic / Reasoning | `EP` | 10 |
| Hierarchical / Taxonomic | `HT` | 5 |
| Structural / Compositional | `SC` | 7 |
| Causal / Temporal | `CT` | 12 |
| Attribution / Provenance | `AP` | 7 |
| Documentary / Reference | `DR` | 6 |
| Comparative / Contrastive | `CC` | 8 |
| Evolutionary / Versioning | `EV` | 2 |
| Personal / Associative | `PA` | 3 |
| Social / Organizational | `SO` | 8 |
| Topical / Classification | `TC` | 4 |
| **Total** | | **72** |

---

## Symmetric Relations (12)

These relations are their own inverse — declaring A→B implies B→A with the same label.
The ego-graph traversal handles display; no double-entry needed in frontmatter.

`EP-002` contradicts · `HT-004` sibling_of · `CC-001` is_similar_to · `CC-002` is_analogous_to ·
`CC-003` is_alternative_to · `CC-004` is_opposite_of · `CC-006` contrasts_with · `CC-007` is_related_to ·
`CC-008` see_also · `SO-001` knows · `SO-002` works_with · `SO-006` affiliated_with

---

## Natural Inverse Pairs (4) — and the Canonicalization Rule

Declaring A→B in one relation logically implies B→A in the paired relation.
Automatic inference of the inverse is a v2 query-layer feature — not stored in files at MVP.

**Canonicalization rule:** for each pair, one member is **canonical** — store edges
using the canonical member; the other member is **derived** for display only. This
keeps queries simple (one ID to filter on) and prevents the same logical edge from
existing twice under two names.

| Canonical (store this) | ID | Derived (display only) | ID |
|---|---|---|---|
| `is_part_of` | `HT-002` | `contains` | `HT-001` |
| `precedes` | `CT-007` | `follows` | `CT-008` |
| `produces` | `CT-011` | `consumes` | `CT-012` |
| `reports_to` | `SO-007` | `manages` | `SO-008` |

If you catch yourself writing `contains`, flip it: write `B is_part_of A` in B's
frontmatter instead. The derived names stay in the registry (their IDs are stable
forever) so old edges still resolve, but new edges should use the canonical member.

**Everything else renders in natural direction only.** Directed types *without* a
listed inverse (the other 52 directed types) have no sanctioned inverse label. A
triple is always serialized in its stored, natural direction —
`Source --[relation]--> Target` — regardless of which endpoint you are looking from.
Do **not** invent inverse names like `is_supported_by` or `is_X_by`: mechanical
inverse-name generation is explicitly deferred to V2. An incoming edge is simply the
same triple seen from the target's side; render it unchanged and mark the direction
(e.g. `EgoEdge.direction = INCOMING`) if the UI needs to distinguish it.
