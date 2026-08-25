# Zola Docs

Zola Docs is a small documentation theme with responsive navigation, breadcrumbs, previous and next
page links, a page table of contents, local search, system-aware light/dark appearance, code-copy
controls, optional Mermaid rendering, and optional documentation version selection. It requires
[Zola](https://www.getzola.org/) but has no client-side framework or package-manager runtime
dependency.

## Install

Add the theme under `themes/zola-docs` and enable it in `config.toml`:

```sh
git submodule add https://github.com/wakamex/zola-docs.git themes/zola-docs
```

Pin the submodule to a release tag or commit for production sites. The `main` branch is the next
theme revision.

```toml
theme = "zola-docs"
build_search_index = true

[search]
index_format = "fuse_json"
include_title = true
include_content = true
include_path = true
```

Provide `data/navigation.json`. The preferred root object works in both JSON and TOML:

```json
{
  "groups": [
    {
      "id": "guides",
      "title": "Guides",
      "items": [
        { "title": "Overview", "path": "" },
        {
          "title": "Getting started",
          "path": "guides/getting-started/",
          "children": [
            { "title": "Installation", "path": "guides/installation/" }
          ]
        }
      ]
    }
  ]
}
```

The legacy root array remains supported.

## Configuration

Override values under `[extra.zola_docs]`:

| Key | Default | Purpose |
| --- | --- | --- |
| `site_name` | `Documentation` | Header label |
| `home_url` | empty | Header destination; the default resolves to the site's base URL |
| `navigation_path` | `data/navigation.json` | Navigation data file |
| `navigation_label` | `Documentation` | Navigation accessible label |
| `search_enabled` | `true` | Load the local search interface |
| `search_label` | `Search documentation` | Search accessible label |
| `search_placeholder` | `Search` | Search input hint |
| `search_index` | `search_index.en.json` | Fuse JSON index path |
| `search_results_limit` | `10` | Maximum visible results |
| `copy_code` | `true` | Add copy buttons to code blocks |
| `page_navigation` | `true` | Show previous and next page links when page data provides them |
| `breadcrumbs` | `true` | Show page breadcrumbs when page data provides them |
| `toc` | `true` | Show page tables of contents |
| `content_max_width` | `78rem` | CSS maximum width for page and section content; use `none` for full width |
| `backlinks` | `false` | Show pages and sections that link to the current content |
| `backlinks_label` | `Referenced by` | Backlink list heading |
| `edit_url` | empty | Repository edit URL prefix |
| `edit_branch` | `main` | Source branch or tag used by edit links |
| `last_updated` | `true` | Show `page.updated` when available |
| `appearance_selector` | `true` | Show a system-aware, persisted light/dark toggle |
| `metadata` | `true` | Emit canonical and Open Graph page metadata |
| `social_image` | empty | Optional default Open Graph image |
| `mermaid` | `false` | Load Mermaid on pages containing diagrams |
| `mermaid_url` | jsDelivr Mermaid ESM URL | Mermaid module source |
| `versions_enabled` | `false` | Show the documentation version selector |
| `versions_path` | `data/versions.json` | Version selector data file |
| `version_label` | `Documentation version` | Version selector accessible label |
| `current_version` | empty | ID of the version represented by this build |
| `version_banner` | empty | Optional plain-text notice shown above every page |
| `version_preserve_path` | `true` | Preserve the current relative route when switching versions |
| `favicon` | empty | Optional static favicon path |
| `extra_styles` | empty | Additional static stylesheets |

Mermaid is loaded in the browser only when rendered content contains `class="mermaid"`. The theme
does not require Chromium. Set `mermaid = false` when diagrams are rendered to SVG during another
build step. Mermaid is disabled by default because its default module URL is a third-party request.

## Navigation data

Navigation contains groups, and each group contains recursive nodes under `items`. A node requires a
title and one of these destinations:

- `path` is an internal Zola path without a leading slash. Use an empty path for the site root.
- `url` is emitted unchanged and is intended for external or deliberately absolute links.
- `children` makes a label-only branch possible when the node has no destination.

Nodes may also provide a stable `id`, recursive `children`, and `sidebar_children = false` to prune
their descendants from page sidebars. The same node shape works at every depth. The validator caps
navigation at 20 levels because Tera rejects a 21st recursive component call.

The machine-readable contract is in `schemas/navigation.schema.json`. Validate JSON or TOML with:

```sh
uv --no-config run --locked python tools/validate_navigation.py data/navigation.json
```

For hand-edited TOML, point `navigation_path` at a TOML file and use the same `groups` structure:

```toml
[[groups]]
id = "guides"
title = "Guides"

[[groups.items]]
title = "Overview"
path = ""

[[groups.items]]
title = "Project"
url = "https://example.com/"
```

The checked-in validator and Zola both load JSON or TOML through `navigation_path`.

### Migration converters

The converter creates normalized navigation JSON from a MkDocs `nav` list or an mdBook
`SUMMARY.md`:

```sh
uv --no-config run --locked python tools/convert_navigation.py mkdocs mkdocs.yml \
  --output data/navigation.json
uv --no-config run --locked python tools/convert_navigation.py mdbook src/SUMMARY.md \
  --output data/navigation.json
```

These are one-shot navigation converters. They do not move content, rewrite Markdown, or inspect
custom route configuration. They map ordinary Markdown filenames to directory-style routes, retain
external URLs, validate the result, and leave the generated JSON for review.

For a complete mdBook migration, use the site adapter:

```sh
uv --no-config run --locked python tools/convert_mdbook_site.py /path/to/book \
  --output /path/to/converted-site
```

The adapter runs mdBook's Markdown renderer after the book's own preprocessors. It converts the
result into a ready Zola Docs consumer with front matter, recursive navigation, previous and next
links, edit metadata, redirect aliases, rewritten internal links, and copied assets. Running the
source preprocessors avoids maintaining a partial implementation of mdBook includes or private
extensions in this repository.

Pinned full-site corpus tests compare converted sites with their native generators through one
manifest and measurement contract. The Rust Book fixture and instructions for adding other source
formats or generators are in [`benchmarks/corpus`](benchmarks/corpus/README.md).

## Page data

The theme reads optional page controls and navigation from front matter:

```toml
[extra]
source_path = "docs/guides/getting-started.md"
breadcrumbs = [{ title = "Guides", path = "guides/" }]
previous = { title = "Overview", path = "" }
next = { title = "Configuration", path = "guides/configuration/" }
page_navigation = true
toc = true
backlinks = false
edit_link = true
metadata = true
```

Internal navigation entries use paths without a leading slash. The theme resolves them through
Zola's `get_url`, so the same build works at the domain root and under a base path. A consumer can
set any per-page boolean to `false`, and `page_navigation`, `breadcrumbs`, and `toc` also have global
defaults.

Set `navigation_group` and `navigation_branch` in page or section extras to use build-time scoped
navigation:

```toml
[extra]
navigation_group = "guides"
navigation_branch = "guides/getting-started/"
```

The theme always emits the major group headings, emits items only for the current group, and emits
children only for the current branch. Set `sidebar_children` to `false` on a navigation item when
its exhaustive leaves already live on an index page and in search. Pages without these extras keep
the complete navigation for compatibility.

Parent links use route-driven SVG chevrons. A right-facing chevron leads into a section, while a
down-facing chevron marks the generated branch whose children are visible. Chevrons are navigation
state, not client-side toggle controls. A muted count on a pruned parent reports how many immediate
sub-pages are omitted from the current page.

Recursive nodes whose internal paths contain the current page route expand automatically. For
scoped navigation, `navigation_branch` selects a top-level node by its `id`, `path`, or `url`.

Zola resolves this scope while rendering each static page. Unrelated links never enter that page's
HTML, so the browser has less markup to download and parse than a complete tree hidden with CSS or
collapsed by JavaScript. The full navigation data remains available at build time for breadcrumbs,
previous and next links, validation, and generated reference indexes.

### Measured Wakterm output

Wakterm's 655-document site previously emitted the same 646-link sidebar on every page. With the
same content and scoped navigation, a guide emits 21 sidebar links and a generated config field
emits 38:

| Page | Complete HTML, raw | Complete HTML, gzip-compressed | Sidebar HTML, raw | Sidebar links |
| --- | ---: | ---: | ---: | ---: |
| Guide, full tree | 164,421 B | 16,528 B | 138,539 B | 646 |
| Guide, scoped | 30,159 B | 8,712 B | 3,922 B | 21 |
| Config field, full tree | 143,726 B | 10,106 B | 138,539 B | 646 |
| Config field, scoped | 12,774 B | 2,444 B | 7,548 B | 38 |

The raw complete page fell by 82% for the guide and 91% for the config field. After compressing the
complete page with gzip, its size fell by 47% for the guide and 76% for the config field. The gzip
numbers use Python's default settings over generated HTML, not a browser transfer trace.

Backlinks use Zola's native `page.backlinks` and `section.backlinks` data. The theme does not parse
wikilinks or require them: ordinary internal links and wikilinks both contribute when the Zola build
records an internal content link. Enable backlink presentation with `backlinks = true` globally or
on individual content through `[extra]`.

Set `[markdown] insert_anchor_links = "right"` in the site configuration to use the theme's
keyboard-focusable heading permalinks.

## Documentation versions

The theme displays versions but does not decide how releases are named, built, retained, or
deployed. Enable the selector and provide `data/versions.json`:

```toml
[extra.zola_docs]
versions_enabled = true
current_version = "1.4"
```

```json
[
  { "id": "1.4", "label": "1.4", "url": "https://docs.example.com/1.4/" },
  { "id": "stable", "label": "Stable", "url": "https://docs.example.com/stable/" }
]
```

Each deployed build should set `current_version` to an ID in that file. Exact release URLs can stay
immutable while entries such as `stable`, `latest`, or `nightly` can point to moving deployments.
Channels have no built-in meaning. Omit a nightly entry when the project has no nightly docs, or
leave `versions_enabled = false` for a single unversioned site.

When `version_preserve_path` is enabled, each version link combines the target version root with the
current Zola `current_path`. The generated link works without JavaScript and preserves ordinary
browser behavior such as opening in a new tab. Disable it when version roots should always open their
landing pages.

### Version tombstones

A missing route can become a marked informational page instead of a generic dead end. After building
all retained versions, describe their output directories in a deployment-only TOML file:

```toml
[[versions]]
id = "1.3"
label = "1.3"
url = "https://docs.example.com/1.3/"
directory = "build/1.3"
release_order = 13

[[versions]]
id = "1.4"
label = "1.4"
url = "https://docs.example.com/1.4/"
directory = "build/1.4"
release_order = 14

[[versions]]
id = "stable"
label = "Stable"
url = "https://docs.example.com/stable/"
directory = "build/stable"
```

Generate a separate overlay:

```sh
uv --no-config run --locked python tools/generate_version_tombstones.py \
  versions.toml --output tombstones
```

The output contains one directory per version. Merge each directory into the corresponding deployed
static tree. Existing documentation builds are never modified by the generator.

Each generated page:

- is created only for a route found in at least one other configured version;
- uses that version's rendered `404.html` as its visual shell;
- carries `zola-docs-route-state=unavailable` and `noindex,follow` metadata;
- links to every configured version containing the route;
- reports the first documented release when `release_order` is available;
- links to the deepest ancestor that exists in the selected version.

These portable tombstones are intentional HTTP 200 informational pages. Unknown routes still use the
host's ordinary `404.html`. Marker-aware availability and link checks should treat tombstones as
unavailable documentation. A host-specific deployment adapter may serve the same files with 404 or
410 later without changing their HTML contract.

Route growth can be measured before generating HTML. Snapshot any static output directory, deployed
mdBook, or sitemap with `tools/snapshot_routes.py`, then compare two or more snapshots with
`tools/benchmark_version_routes.py`. The reproducible Rust and Django cases and current results are
in [`benchmarks`](benchmarks/README.md).

Set `version_banner` on a build that needs a site-wide warning, such as unreleased or unsupported
documentation. Each versioned build naturally uses its own Zola search index, so search stays within
the selected documentation set.

Compatibility floors, deprecations, and API availability remain source or consumer data. Generated
reference templates can render them through the `page_metadata` block without adding handwritten
version markers to prose.

## Overrides

Site templates can extend a theme template and replace a focused block:

```jinja
{% extends "zola-docs/templates/page.html" %}
{% block page_footer %}<p>Site-owned footer</p>{% endblock page_footer %}
```

The public extension blocks include `head`, `header`, `header_brand`, `sidebar`, `page_header`,
`page_metadata`, `page_before_content`, `page_after_content`, `page_footer`, `section_header`,
`section_before_content`, `section_after_content`, `section_footer`, `footer`, and `scripts`.

Content transformations, generated references, release data, navigation generation, and custom
components belong to the consuming site.

## Validate

Build the included demo and exercise a separate consumer override:

```sh
uv --no-config run --locked python tests/check.py --zola /path/to/zola
```

CI runs this suite against Zola 0.23.0, the minimum declared in `theme.toml`, and the current 0.23.3
release. Full-site corpus builds are reproducible but remain outside CI because they clone external
repositories and run their native toolchains. The generated `public` directory and local `.venv`
are not release artifacts.
