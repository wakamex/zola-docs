# Version tombstone benchmarks

The benchmark compares route snapshots from independently built documentation versions. It reports
how many marked HTML tombstones would fill the gaps in each version's route set.

Create route snapshots from any local static build:

```sh
python tools/snapshot_routes.py directory /path/to/public -o routes.txt
```

The snapshot tool also reads deployed mdBook search indexes and XML sitemaps. These commands recreate
the checked benchmark inputs under the ignored `benchmarks/.work` directory:

```sh
mkdir -p benchmarks/.work

for document in book cargo reference; do
  for version in 1.70.0 1.90.0 1.98.0; do
    python tools/snapshot_routes.py mdbook \
      "https://doc.rust-lang.org/$version/$document/" \
      -o "benchmarks/.work/$document-$version.routes"
  done
done

curl -fsSL https://docs.djangoproject.com/sitemap-en.xml \
  -o benchmarks/.work/django-sitemap-en.xml
for version in 2.2 3.0 3.1 3.2 4.0 4.1 4.2 5.0 5.1 5.2; do
  python tools/snapshot_routes.py sitemap benchmarks/.work/django-sitemap-en.xml \
    --root "https://docs.djangoproject.com/en/$version/" \
    -o "benchmarks/.work/django-$version.routes"
done
```

Run the comparisons:

```sh
python tools/benchmark_version_routes.py benchmarks/rust-docs.toml
python tools/benchmark_version_routes.py benchmarks/django.toml
```

`shell_bytes` estimates raw overlay size by multiplying the tombstone count by a representative
rendered Zola Docs 404 page. File-count amplification is independent of that estimate.

These are route snapshot estimates. The [`corpus`](corpus/README.md) runner performs full-source
conversion and compares complete native and Zola Docs builds.
