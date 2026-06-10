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
│   # Contributor-facing planning docs — excluded from the published site
│   # (see exclude_docs in mkdocs.yml)
├── implementation-plan.md       historical sprint plan (stale; trust `make status`)
├── adversarial-analysis.md      original risk analysis
├── adversarial-analysis-v2.md   current risk analysis (authoritative)
├── analysis-and-enhancements.md findings + agreed decisions
├── plan-*.md                    specialist plans (docs/tests, KG theory, Makefile, security)
├── roadmap.md                   MVP / V1 / V2 scope boundaries
├── user-stories.md              user journeys and requirements
├── future-ideas.md              parked features (cloud sync, embeddings, …)
├── observability-module.md      parked observability design
└── archive/                     superseded documents
```

For phase time estimates and the full foundation descriptions, see
[index.md](index.md) — this file is only the map.
