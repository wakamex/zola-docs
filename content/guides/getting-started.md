+++
title = "Getting started"
updated = 2026-08-24

[extra]
navigation_group = "theme"
navigation_branch = "guides/getting-started/"
breadcrumbs = [{ title = "Guides", path = "guides/" }]
previous = { title = "Zola Docs", path = "" }
+++

# Getting started

Install the theme under `themes/zola-docs`, set `theme = "zola-docs"`, and provide navigation data.

## Search

The theme reads Zola's Fuse JSON index and ranks title, path, and body matches locally.

## Diagrams

<pre class="mermaid"><code>flowchart LR
  Content --> Zola
  Zola --> Documentation</code></pre>
