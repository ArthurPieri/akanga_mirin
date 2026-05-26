# MKDocs Basics

**Estimated read time:** 20 minutes
**Prerequisite:** None — this doc assumes you can open a terminal and edit a YAML file.

---

Most documentation starts as Markdown files in a directory. That is fine for reading
in a terminal with `glow` or in your editor. But at some point you want to share those
docs — with teammates, with future-you on a different machine, or with the internet.
That is where MKDocs comes in.

MKDocs turns a directory of Markdown files into a browsable website. You point it at
your `docs/` folder, run one command, and get a site with navigation, full-text search,
and a polished theme — all generated from the Markdown you already have.

This doc explains what MKDocs is, how it works, and how Akanga uses it alongside
`glow` for a two-mode documentation workflow.

---

## 1. What MKDocs is

MKDocs is a **static site generator** written in Python. "Static site generator" means
it reads your Markdown files at build time, converts them to HTML, and writes the
result to a directory. No server-side code runs when someone visits the site — the
output is plain HTML, CSS, and JavaScript that any web server (or GitHub Pages) can
host.

What MKDocs is **not**:

- **Not a CMS.** There is no admin panel, no database, no login system. Your content
  lives in `.md` files on disk, managed by git like any other code.
- **Not a wiki engine.** There is no edit-in-browser flow. You edit Markdown in your
  editor, commit, and rebuild.
- **Not a replacement for glow.** MKDocs produces a website; glow renders Markdown in
  the terminal. They serve different contexts.

The mental model: **MKDocs is a build tool.** Markdown in, website out.

---

## 2. Why MKDocs alongside glow

The Akanga learning path already uses `glow` for terminal-based reading during study
sessions. Running `make docs-phase PHASE=2` opens the phase doc right in your terminal,
which is fast and distraction-free. That workflow is not going away.

MKDocs adds a second mode:

- **Rich rendering.** Diagrams (Mermaid), callout boxes (admonitions), syntax
  highlighting with line numbers, and embedded search all work in a browser but not in
  a terminal.
- **Navigation.** A sidebar with all phases and foundation docs, clickable and
  searchable. Easier to browse than `ls docs/`.
- **Sharing.** Deploy the generated site to GitHub Pages, Netlify, or any static host.
  Send someone a URL instead of asking them to clone the repo.
- **Cross-referencing.** Internal links between docs become clickable hyperlinks. The
  build will warn you if a link target is missing.

The two tools complement each other: `glow` for focused terminal study sessions,
MKDocs for browsing, sharing, and rich rendering.

---

## 3. Installing MKDocs

Since Akanga uses `uv` as the Python package manager, installation is one command:

```shell
uv add mkdocs mkdocs-material
```

This installs two packages:

- **`mkdocs`** — the core static site generator.
- **`mkdocs-material`** — the Material for MKDocs theme, which is the de-facto standard
  theme used by most Python projects. It provides responsive design, dark mode, search,
  admonitions, code copy buttons, and dozens of other features out of the box.

If you are not using `uv`, the equivalent pip command is:

```shell
pip install mkdocs mkdocs-material
```

Verify the installation:

```shell
mkdocs --version
```

You should see output like `mkdocs, version 1.6.x`. If you installed via `uv`, you may
need to run `uv run mkdocs --version` instead — or activate your virtual environment
first.

---

## 4. Project structure

MKDocs needs exactly two things:

1. A **`mkdocs.yml`** configuration file in the project root.
2. A **`docs/`** directory containing your Markdown files.

Here is the minimal structure:

```
akanga_mirin/
  mkdocs.yml          # MKDocs configuration
  docs/
    index.md           # Home page (maps to /)
    learning/
      phase-00-*.md
      phase-01-*.md
      ...
    foundations/
      sqlite-basics.md
      makefile-basics.md
      mkdocs-basics.md
      ...
```

MKDocs reads the directory structure under `docs/` and generates navigation
automatically. Subdirectories become sections, filenames become page titles (derived
from the first `# heading` in each file). You can override this with an explicit `nav:`
block in `mkdocs.yml` — more on that in section 8.

The key insight: **you do not need to reorganize your docs.** If they are already in a
`docs/` directory (as they are in Akanga), MKDocs works with them as-is. You add a
config file and you are done.

---

## 5. mkdocs.yml anatomy

The `mkdocs.yml` file is the only configuration MKDocs needs. Here is a minimal
example:

```yaml
site_name: My Docs
theme:
  name: material
```

That is enough to get a working site. MKDocs will auto-discover every `.md` file under
`docs/` and build navigation from the directory structure.

Here is a more complete configuration suited to the Akanga learning path:

```yaml
site_name: Akanga Mirin — Knowledge Graph Learning Path
site_url: https://example.com/akanga-mirin/
repo_url: https://github.com/your-user/akanga_mirin

theme:
  name: material
  palette:
    - scheme: default
      primary: teal
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: teal
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.sections
    - navigation.expand
    - search.highlight
    - content.code.copy

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - toc:
      permalink: true

plugins:
  - search
```

Let's walk through the key sections:

- **`site_name`** — appears in the browser tab and the site header.
- **`site_url`** — the URL where the site will be deployed. Used for generating
  canonical URLs and sitemap entries.
- **`repo_url`** — adds a link to the repository in the site header.
- **`theme`** — configures Material. The `palette` block enables a light/dark mode
  toggle. The `features` list activates optional UI behaviors.
- **`markdown_extensions`** — enables extra Markdown syntax. `admonition` adds callout
  boxes, `pymdownx.superfences` enables fenced code blocks inside other elements,
  `toc` adds anchor links to headings.
- **`plugins`** — `search` is the built-in full-text search. MKDocs enables it by
  default, but listing it explicitly lets you configure options later.

---

## 6. `mkdocs serve` — the dev server

The command you will use most:

```shell
mkdocs serve
```

This starts a local development server (default: `http://127.0.0.1:8000`) and watches
your files for changes. Edit a Markdown file, save it, and the browser reloads
automatically.

If you need a different host or port (for example, when port 8000 is already in use):

```shell
mkdocs serve --dev-addr 0.0.0.0:8080
```

In the Akanga learning path, this is wrapped in a Makefile target:

```shell
make docs-serve
```

Which runs `mkdocs serve` with the project's settings. You do not need to remember
flags — just `make docs-serve` and open the URL it prints.

### What the dev server does

1. Reads `mkdocs.yml` and all Markdown files under `docs/`.
2. Converts every `.md` file to HTML using the configured theme and extensions.
3. Serves the result on `localhost:8000`.
4. Watches the filesystem. When any `.md` file or `mkdocs.yml` changes, it rebuilds
   the affected pages and triggers a browser reload.

The dev server is for local development only. It is not meant for production hosting.
For that, you use `mkdocs build` and deploy the output.

---

## 7. `mkdocs build` — generating the static site

When you are ready to publish:

```shell
mkdocs build
```

This generates a `site/` directory containing the full static website: HTML pages, CSS,
JavaScript, search index, and any images or assets referenced in your docs.

```
site/
  index.html
  learning/
    phase-00-.../index.html
    phase-01-.../index.html
    ...
  foundations/
    sqlite-basics/index.html
    makefile-basics/index.html
    ...
  search/
    search_index.json
  assets/
    stylesheets/...
    javascripts/...
```

You can open `site/index.html` directly in a browser, or deploy the entire `site/`
directory to any static hosting service (GitHub Pages, Netlify, Cloudflare Pages, or
a plain web server).

### Important: add `site/` to .gitignore

The `site/` directory is a build artifact — it is generated from your source files and
should not be committed to the repository. Add it to `.gitignore`:

```
# .gitignore
site/
```

This is the same principle as not committing compiled `.pyc` files or `node_modules/`.
The source of truth is your Markdown and `mkdocs.yml`, not the generated HTML.

---

## 8. Navigation configuration

MKDocs can generate navigation automatically from the directory structure, or you can
define it explicitly in `mkdocs.yml`.

### Automatic navigation

With no `nav:` block in `mkdocs.yml`, MKDocs scans the `docs/` directory and builds
the sidebar from the folder structure. Page titles come from the first `# heading` in
each file.

This works well for simple projects, but the ordering is alphabetical by filename,
which is not always what you want.

### Explicit navigation

For precise control, define a `nav:` block:

```yaml
nav:
  - Home: index.md
  - Learning Path:
    - "Phase 0 — Atomic Writer": learning/phase-00-atomic-markdown.md
    - "Phase 1A — Edge Schema": learning/phase-01a-edge-schema.md
    - "Phase 1B — Workspace Registry": learning/phase-01b-workspace-registry.md
    - "Phase 2 — SQLite Backbone": learning/phase-02-sqlite-backbone.md
    - "Phase 3 — Graph Queries": learning/phase-03-graph-queries.md
    - "Phase 4 — File Watcher": learning/phase-04-file-watcher.md
    - "Phase 5 — CLI Layer": learning/phase-05-cli-layer.md
    - "Phase 6 — Visualization": learning/phase-06-visualization.md
    - "Phase 7 — MCP Server": learning/phase-07-mcp-server.md
    - "Phase 8 — RAG Context": learning/phase-08-rag-context.md
  - Foundations:
    - "SQLite Basics": foundations/sqlite-basics.md
    - "Makefile Basics": foundations/makefile-basics.md
    - "MKDocs Basics": foundations/mkdocs-basics.md
    - "YAML and Frontmatter": foundations/yaml-and-markdown-frontmatter.md
```

Key points about explicit navigation:

- **Paths are relative to `docs/`.** Not relative to the project root, not absolute.
  `foundations/sqlite-basics.md` means `docs/foundations/sqlite-basics.md`.
- **Sections are created by nesting.** "Learning Path:" with indented items becomes a
  collapsible sidebar section.
- **Only listed pages appear in the nav.** Any `.md` file not listed still gets built
  (and is accessible by URL) but will not show up in the sidebar.
- **Ordering is manual.** Items appear in the order you list them, which is how you
  get phases in numerical order instead of alphabetical.

### When to use which

Use automatic navigation when your docs are small and alphabetical ordering is fine.
Switch to explicit navigation when you need a specific order (like phases 0 through 8)
or want to group docs into labeled sections.

---

## 9. Admonitions (power-user feature)

This section is **optional**. Admonitions are not required for basic MKDocs usage,
but they are one of the most useful features of Material for MKDocs and worth knowing
about.

Admonitions are callout boxes — colored, titled blocks that visually separate notes,
warnings, tips, and other supplementary content from the main text. They look like
this when rendered in a browser:

A blue "Note" box, a yellow "Warning" box, a green "Tip" box, and so on.

### Syntax

An admonition starts with `!!!` followed by the type and an optional title:

```markdown
!!! note "Important detail"
    Content goes here. It must be indented by exactly 4 spaces
    relative to the `!!!` marker. Blank lines are fine inside
    the block as long as indentation is maintained.

!!! warning
    When no title is given, the type name is used as the title.
    This box will be titled "Warning".

!!! tip "Pro tip"
    You can use any inline Markdown inside admonitions:
    **bold**, `code`, [links](https://example.com).
```

### Collapsible admonitions

Replace `!!!` with `???` to make the admonition collapsible (click to expand):

```markdown
??? example "Click to see the example"
    This content is hidden by default.
    The reader clicks the title bar to expand it.

???+ example "Expanded by default"
    The `+` after `???` means this starts open.
    The reader can still click to collapse it.
```

### Common admonition types

| Type       | Color  | Use for                                   |
|------------|--------|-------------------------------------------|
| `note`     | Blue   | General supplementary information          |
| `info`     | Blue   | Contextual details, background             |
| `tip`      | Green  | Helpful advice, best practices             |
| `warning`  | Yellow | Things that could cause confusion or errors|
| `danger`   | Red    | Things that could cause data loss or breaks|
| `example`  | Purple | Code examples, worked problems             |
| `quote`    | Gray   | Quotations, cited text                     |

### Requirements

Admonitions require two markdown extensions, both included with Material for MKDocs:

```yaml
# mkdocs.yml
markdown_extensions:
  - admonition          # enables !!! syntax
  - pymdownx.details    # enables ??? collapsible syntax
```

### A note on portability

Admonitions render beautifully in MKDocs-served sites, but they appear as plain text
in other Markdown viewers (GitHub, glow, VS Code preview). The `!!!` lines show up
literally, and the indented content looks like a code block.

This means admonitions are best suited for documentation that will primarily be read
through MKDocs. For knowledge graph notes that you also read in glow or on GitHub,
stick to standard Markdown formatting (bold text, blockquotes, horizontal rules) for
callouts.

---

## 10. Useful plugins

MKDocs has a plugin ecosystem. Most projects need only a few. Here are the ones most
relevant to Akanga:

**`search`** (built-in) — Full-text search across all pages. Enabled by default.
Material for MKDocs enhances it with search suggestions and highlighting.

**`tags`** — Lets you add `tags: [python, sqlite]` to a page's frontmatter and
generates a tags index page. Useful if your knowledge graph notes use tags.

```yaml
plugins:
  - search
  - tags
```

**`mermaid2`** — Renders Mermaid diagram syntax in fenced code blocks. Several Akanga
phase docs include Mermaid diagrams for architecture and data flow. Install with
`uv add mkdocs-mermaid2-plugin` and add to your config:

```yaml
plugins:
  - search
  - mermaid2

markdown_extensions:
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
```

This is not an exhaustive list — the MKDocs plugin catalog has hundreds of options.
Start with search only and add plugins as you need them. Each plugin is one more
dependency and one more thing to configure.

---

## 11. Common pitfalls

**YAML indentation in mkdocs.yml.** YAML uses spaces for indentation — never tabs.
Inconsistent indentation is the most common cause of `mkdocs serve` failing to start.
If you see a parse error, check that every nested key is indented with exactly 2 spaces
(the convention) and that you have not mixed tabs and spaces. See the
[YAML and Markdown Frontmatter](yaml-and-markdown-frontmatter.md) foundation doc for
a deeper YAML primer.

**Forgetting to add `site/` to .gitignore.** The generated `site/` directory can be
large (tens of megabytes for a project with many pages). Committing it bloats the
repository and creates merge conflicts. Add `site/` to `.gitignore` before your first
build.

**Nav paths are relative to `docs/`, not the project root.** A common mistake:

```yaml
# Wrong — this looks for docs/docs/foundations/sqlite-basics.md
nav:
  - "SQLite": docs/foundations/sqlite-basics.md

# Right — paths start inside docs/
nav:
  - "SQLite": foundations/sqlite-basics.md
```

**Admonition content must be indented exactly 4 spaces.** If the content under `!!!`
is indented by 2 spaces (or uses tabs), MKDocs will not recognize it as part of the
admonition. The block will break, and the content will render as a regular paragraph.

```markdown
# Wrong — 2-space indent
!!! note
  This will not render as an admonition.

# Right — 4-space indent
!!! note
    This will render correctly.
```

**Broken internal links.** MKDocs validates internal links at build time. If you
rename or move a file, update all links that point to it. Run `mkdocs build --strict`
to turn link warnings into errors — this catches broken references before deployment.

**The dev server is not production.** `mkdocs serve` is for local development. Do not
expose it to the internet. For production, run `mkdocs build` and serve the `site/`
directory with a proper web server or static hosting platform.

---

## 12. Next steps

- Run `make docs-serve` in the akanga_mirin repo. Open `http://127.0.0.1:8000` in
  your browser and explore the site.
- Edit any `.md` file under `docs/` — change a heading, add a paragraph — and watch
  the browser reload automatically.
- Open `mkdocs.yml` and try changing `site_name` or adding a new page to the `nav:`
  block. The dev server picks up config changes too.
- Try `mkdocs build` and look inside the generated `site/` directory to see what the
  output looks like.
- For deeper reference: the official MKDocs documentation at
  `https://www.mkdocs.org/` and the Material for MKDocs docs at
  `https://squidfundamentals.github.io/mkdocs-material/` (or search "Material for
  MKDocs" — the site moves occasionally).
