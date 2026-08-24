# Zola Docs

Zola Docs is a small documentation theme with responsive navigation, breadcrumbs, previous and next
page links, a page table of contents, local search, system-aware light/dark appearance, code-copy
controls, optional Mermaid rendering, and optional documentation version selection. It requires
[Zola](https://www.getzola.org/) but has no client-side framework or package-manager runtime
dependency.

## Install

Install the repository as `themes/zola-docs` and enable it in `config.toml`:

```toml
theme = "zola-docs"
build_search_index = true

[search]
index_format = "fuse_json"
include_title = true
include_content = true
include_path = true
```

Provide `data/navigation.json` as an array of groups:

```json
[
  {
    "id": "guides",
    "title": "Guides",
    "items": [
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
```

## Configuration

Override values under `[extra.zola_docs]`:

| Key | Default | Purpose |
| --- | --- | --- |
| `site_name` | `Documentation` | Header label |
| `home_url` | `/` | Header destination |
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
| `version_preserve_path` | `true` | Use route manifests to preserve paths across versions |
| `favicon` | empty | Optional static favicon path |
| `extra_styles` | empty | Additional static stylesheets |

Mermaid is loaded in the browser only when rendered content contains `class="mermaid"`. The theme
does not require Chromium. Set `mermaid = false` when diagrams are rendered to SVG during another
build step. Mermaid is disabled by default because its default module URL is a third-party request.

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

Zola resolves this scope while rendering each static page. Unrelated links never enter that page's
HTML, so the browser has less markup to download and parse than a complete tree hidden with CSS or
collapsed by JavaScript. The full navigation data remains available at build time for breadcrumbs,
previous and next links, validation, and generated reference indexes.

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

A version entry can provide a `manifest` URL containing a JSON array of published paths. When
`version_preserve_path` is enabled, the selector keeps the current path if it appears in the target
manifest and otherwise opens that version's root. A failed manifest request also falls back to the
version root.

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
uv run python tests/check.py --zola /path/to/zola
```
