# Full-site corpus tests

Corpus tests clone a pinned public documentation source, convert it through a source adapter, and
build the same content with its native generator and Zola Docs. Route snapshots remain useful for
testing many versions cheaply, but corpus tests exercise preprocessing, navigation, assets, Markdown
conversion, templates, search indexing, redirects, and complete static output.

Each site manifest contains acquisition metadata, one adapter name, and generator commands. The
runner owns source verification, isolated output directories, warmups, timing, peak process memory,
file and byte counts, and normalized route comparison. A future source format needs one preparation
adapter. Native and alternative generators remain declarative command entries and reuse the same
measurement path.

The source checkout and generated work stay outside this repository. Fetching verifies the pinned
revision:

```sh
python tools/docs_corpus.py fetch benchmarks/corpus/rust-book.toml \
  --destination /code/docs-corpus/rust-book

python tools/docs_corpus.py prepare benchmarks/corpus/rust-book.toml \
  --source /code/docs-corpus/rust-book \
  --work /code/docs-corpus/work/rust-book \
  --theme /code/zola-docs

python tools/docs_corpus.py benchmark benchmarks/corpus/rust-book.toml \
  --source /code/docs-corpus/rust-book \
  --work /code/docs-corpus/work/rust-book \
  --zola /path/to/zola \
  --runs 5 --warmups 1 \
  --output /code/docs-corpus/work/rust-book/results.json
```

The mdBook adapter asks mdBook for its built-in Markdown renderer output after preprocessors run.
It then adds Zola front matter, normalized navigation, previous and next links, edit metadata,
redirect aliases, internal-link rewrites, and static assets. This preserves custom preprocessors
without teaching the converter their private syntax.
