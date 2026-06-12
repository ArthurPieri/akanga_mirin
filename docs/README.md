# docs/ — Documentation Map

This directory holds everything published on the MkDocs site **plus** internal
planning material. **[index.md](index.md) is the site hub** — it has the phase
table, the foundation list, and the project terminology. Start there.

> Learners: start with [index.md](index.md) → Phase 0.
> Contributors: see `CONTRIBUTING.md` at the repo root; the planning docs below
> are for you.

---

## Directory tree

```
docs/
├── index.md                     ← site hub: phases, foundations, terminology
├── learning/                    10 phase docs (0, 1A, 1B, 2–8)
├── foundations/                 15 background explainers
│   ├── asyncio-primer.md          ├── mkdocs-basics.md
│   ├── design-patterns.md         ├── python-dataclasses.md
│   ├── direnv-basics.md           ├── python-threading.md
│   ├── git-basics.md              ├── python-type-annotations.md
│   ├── http-fundamentals.md       ├── relation-vocabulary.md
│   ├── json-rpc-basics.md         ├── sqlite-basics.md
│   ├── makefile-basics.md         ├── terminal-and-tmux-basics.md
│   │                              └── yaml-and-markdown-frontmatter.md
├── architecture-overview.md     derived reference (published)
├── architecture-detailed.md     derived reference (published)
├── deployment.md                tmux / launchd / systemd options (published)
│
├── observability-module.md      structured logging, @timed, /health patterns (published)
├── facilitator-guide.md         running Akanga Mirin as a 2–4 day workshop (published)
│
│   # Contributor-facing planning docs — excluded from the published site
│   # (see exclude_docs in mkdocs.yml)
├── status-remediation.md        the remediation handoff log — per-round finding
│                                status + adopted decisions (start here for state)
├── adversarial-analysis-v5.md   Round 5 risk analysis — readability/DRY (CURRENT)
├── adversarial-analysis-v4.md   Round 4 risk analysis (historical, resolved)
├── adversarial-analysis-v3.md   Round 3 risk analysis (historical, resolved)
├── adversarial-analysis-v2.md   Round 2 risk analysis (historical, resolved)
├── adversarial-analysis.md      Round 1 risk analysis (historical, resolved)
├── implementation-plan.md       historical sprint plan (stale; trust `make status`)
├── analysis-and-enhancements.md findings + agreed decisions
├── plan-*.md                    specialist plans (docs/tests, KG theory, Makefile, security)
├── roadmap.md                   MVP / V1 / V2 scope boundaries
├── user-stories.md              user journeys and requirements
├── future-ideas.md              parked features (cloud sync, embeddings, …)
└── archive/                     superseded documents
```

For phase time estimates and the full foundation descriptions, see
[index.md](index.md) — this file is only the map.
