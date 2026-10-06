# Benchmarks

[pytest-benchmark](https://pytest-benchmark.readthedocs.io) benchmarks against a fixed synthetic dataset (`dataset.py`), so results are comparable between runs and commits.

They need the Postgres and Elasticsearch from `docker compose`. They use their own test database (`test_isic_benchmark`) and `benchmark-*` indices, so the development and test databases and indices are never touched.

```sh
uv run tox -e benchmark                             # everything
uv run tox -e benchmark -- -k image_search          # a subset
uv run tox -e benchmark -- --benchmark-save=before  # save the run to .benchmarks/
uv run tox -e benchmark -- --benchmark-compare      # compare with the last saved run
uv run tox -e benchmark -- --benchmark-disable      # run each benchmark once, without timing
```

- Each session starts from a fresh copy of the dataset. The first run for a schema generates about 100k images, which takes about 2 minutes, and keeps them in a `test_isic_benchmark_<hash>` database that later runs copy. Drop old ones with `DROP DATABASE test_isic_benchmark_<hash>`.
- Caching is disabled (`DummyCache`, cachalot off), so every request does its full work.
- Benchmarks that write data roll back each round.
- Benchmarks that use the `benchmark_with_memory` fixture also record the peak memory Python allocates, measured in a separate call. Memory allocated outside Python, such as by psycopg, isn't counted.
- CI (`.github/workflows/benchmarks.yml`) runs on each push to master. `history.py record` adds each benchmark's fastest round and peak memory to `benchmarks/data.js` on the `gh-pages` branch, and the job copies `index.html` next to it. Then `history.py check` fails the job when either is more than 50% higher than in the run before it.
- `index.html` charts `data.js`, grouped by module and test, at https://imagemarkup.github.io/isic/benchmarks/. To chart local runs:

  ```sh
  uv run tox -e benchmark -- --benchmark-json=.benchmarks/run.json
  uv run python benchmarks/history.py record .benchmarks/run.json .benchmarks/site/data.js
  cp benchmarks/index.html .benchmarks/site/ && python -m http.server -d .benchmarks/site
  ```
