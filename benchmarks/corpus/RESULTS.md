# Rust Book full-site result

Source revision: `917544888a55e4da7109bdba8c88c893c0da70f4`

The adapter converted 111 chapters and 28 assets. Conversion took 2.31 seconds. It uses mdBook's
preprocessed Markdown output and is a one-shot migration cost, so it is separate from generator
timing.

| Generator | Median of 5 warm builds | Range | Peak RSS | Files | HTML files | Output bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mdBook 0.5.1 | 1.304 s | 1.294-1.323 s | 199,312 KiB | 202 | 137 | 13,013,751 B |
| Zola 0.23.3 and Zola Docs | 0.113 s | 0.111-0.120 s | 69,044 KiB | 168 | 135 | 5,460,884 B |

The Zola build preserved all chapter and redirect routes. mdBook additionally generates `/print/`
and `/toc/`; the corpus manifest classifies those two utility pages as expected native-only routes.

The native cold build took 9.13 seconds and 427,840 KiB peak RSS because it compiled the Rust
Book's custom preprocessors. Warm measurements clean generator output between runs but retain tool
and filesystem caches. The outputs are not byte-equivalent: mdBook bundles its own theme, scripts,
search implementation, combined print page, and standalone table of contents.
