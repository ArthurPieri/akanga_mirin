# Relation Vocabulary — The 71 Built-in Relation Types

Akanga ships 71 relation types organized into 11 semantic categories. This is the
vocabulary you build in Phase 1 and query by ID in Phase 8 (`list_relation_types()`).

Custom types are always allowed — assigned a UUID at creation, no pre-registration
required. The built-in types exist so common relations are named consistently across
vaults and can be compared, filtered, and inferred programmatically.

**How to browse this file:**
- `make foundations TOPIC=relation-vocabulary` — opens this doc in glow
- Phase 1 uses this to implement the relation registry
- Phase 8's `list_relation_types()` MCP tool returns rows from this vocabulary

**ID format:** category prefix + 3-digit number (e.g. `EP-001`). IDs are stable forever —
the relation name is a human-readable display cache and can be renamed without breaking edges.

**Flags:** `⇄` = symmetric (A→B implies B→A with the same label);
`↔ XX-NNN` = has a natural inverse in this vocabulary.

---

## Epistemic / Reasoning (10)
*How ideas relate in terms of knowledge, truth, and argument.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `EP-001` | `supports` | A provides evidence, reasoning, or data that strengthens B | |
| `EP-002` | `contradicts` | A conflicts with or undermines B — they can't both be fully true | ⇄ |
| `EP-003` | `qualifies` | A adds nuance, conditions, or caveats to B without contradicting it | |
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
| `HT-002` | `is_part_of` | A is a component, section, or member of B | ↔ HT-001 |
| `HT-003` | `subtype_of` | A is a more specific version or subtype of B | |
| `HT-004` | `sibling_of` | A and B are at the same level of a hierarchy, sharing a common parent | ⇄ |
| `HT-005` | `member_of` | A is a member of group, organization, or collection B | |

---

## Structural / Compositional (7)
*How things depend on, implement, or build from each other.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `SC-001` | `depends_on` | A requires B to function, exist, or be understood | |
| `SC-002` | `implements` | A is a concrete realization of the abstract specification or pattern B | |
| `SC-003` | `uses` | A employs B as a component, library, or tool | |
| `SC-004` | `overrides` | A replaces inherited behavior from B | |
| `SC-005` | `satisfies` | A (design/implementation) satisfies the requirement B | ↔ SC-006 |
| `SC-006` | `verifies` | A (test/analysis) verifies that a design satisfies requirement B | ↔ SC-005 |
| `SC-007` | `aggregates` | A loosely groups B (B can exist independently of A) | |

---

## Causal / Temporal (12)
*How things produce, enable, follow, or precede each other.*

| ID | Relation | Meaning | Flags |
|---|---|---|---|
| `CT-001` | `causes` | A directly and reliably produces B | |
| `CT-002` | `enables` | A makes B possible without directly causing it | |
| `CT-003` | `blocks` | A prevents, impedes, or is fundamentally incompatible with B | |
| `CT-004` | `led_to` | A historically contributed to or resulted in B | |
| `CT-005` | `solves` | A addresses and resolves problem B | |
| `CT-006` | `motivated_by` | A was motivated by or arose in response to B | |
| `CT-007` | `precedes` | A comes before B in time or logical order | ↔ CT-008 |
| `CT-008` | `follows` | A comes after B in time or logical order | ↔ CT-007 |
| `CT-009` | `has_prerequisite` | B must exist or be understood before A | |
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
| `CC-002` | `is_analogous_to` | A is structurally similar to B in a different domain (cross-domain analogy) | ⇄ |
| `CC-003` | `is_alternative_to` | A can substitute for B in a given context | ⇄ |
| `CC-004` | `is_opposite_of` | A is the conceptual inverse or antithesis of B | ⇄ |
| `CC-005` | `is_better_than` | A is preferable to B in a specific, stated context | |
| `CC-006` | `contrasts_with` | A is deliberately set in contrast to B to highlight differences | ⇄ |
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
| `PA-002` | `is_applied_in` | Concept or idea A is practically used in project or context B | |
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
| `TC-004` | `has_context` | A is understood within the cultural or domain context of B | |

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
| **Total** | | **71** |

---

## Symmetric Relations (14)

These relations are their own inverse — declaring A→B implies B→A with the same label.
The ego-graph traversal handles display; no double-entry needed in frontmatter.

`EP-002` contradicts · `HT-004` sibling_of · `CC-001` is_similar_to · `CC-002` is_analogous_to ·
`CC-003` is_alternative_to · `CC-004` is_opposite_of · `CC-006` contrasts_with · `CC-007` is_related_to ·
`CC-008` see_also · `SO-001` knows · `SO-002` works_with · `SO-006` affiliated_with

---

## Natural Inverse Pairs (4)

Declaring A→B in one relation logically implies B→A in the paired relation.
Automatic inference of the inverse is a v2 query-layer feature — not stored in files at MVP.

| Relation | ID | Inverse | ID |
|---|---|---|---|
| `contains` | `HT-001` | `is_part_of` | `HT-002` |
| `precedes` | `CT-007` | `follows` | `CT-008` |
| `produces` | `CT-011` | `consumes` | `CT-012` |
| `reports_to` | `SO-007` | `manages` | `SO-008` |
