# Contributing

Run the complete theme, consumer, schema, converter, and JavaScript checks against a Zola binary:

```sh
uv --no-config run --locked python tests/check.py --zola /path/to/zola
```

The test suite builds the included demo, a base-path consumer with scoped recursive navigation, and
a consumer with optional features disabled. It also tests source adapters with local fixtures. Keep
the minimum supported Zola version and the current release passing.

Full external corpus runs are documented in `benchmarks/corpus/README.md`. Keep source acquisition
and generated output outside the repository, pin every source revision, and record both native and
Zola Docs results when changing an adapter or generator-facing behavior.
