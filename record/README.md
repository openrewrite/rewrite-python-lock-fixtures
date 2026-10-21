# Recording

All scripts run under zsh and need `uvx` and Python 3.11+.

## A uv scenario against a local index

1. Create `<dir>/index.json` listing the synthetic packages (`name`, `version`, `requires_dist`, `requires_python`,
   `provides_extra`, optional `wheel_tags`), and `<dir>/pyproject.before.toml` and `<dir>/pyproject.after.toml`
   declaring `http://127.0.0.1:__PORT__/simple/` as the default index.
2. `UV_RELEASE=0.13.4 record/record-uv-scenario.sh <dir>` builds the index (`mkindex.py`), serves it, and locks
   before and after the edit from an empty cache. Copy `work/pyproject.toml` to `work/pyproject.after.toml`.
3. `record/mkfixture.py <dir> lock/uv/<scenario> <scenario>` rewrites the host to `https://index.example` and copies
   the manifest, both locks and the listings and metadata files into the fixture. Copy `index.json` and the two
   manifests into `lock/uv/<scenario>/recording/`.

## How uv renders markers

`uv-marker-renderings.py <markers.txt> <out.tsv> [uv-release]` records how a uv release writes each marker, as
`lock/uv/marker/` holds for uv 0.13.4. It declares every marker on a dependency group of one probe project, locks it
against a one-package local index, and reads the rendering back from `[package.metadata.requires-dev]`.

## Replaying the engine outside the tests

`src/Harness.java` drives one engine from the command line against a `rewrite-python` build. Write the build's test
runtime classpath to `record/classpath.txt` with `classpath.gradle` (an init script registering
`printTestRuntimeClasspath`), compile the harness into `record/out`, then:

- `replay-engine-scenario.sh <dir>` runs the engine over a recorded local-index scenario and diffs it against uv.
- `corpus-noop.sh <cases> <results>` runs each case's engine with an unchanged manifest.
- `corpus-uv-edits.sh <cases>/uv <results> <uv-release>` applies the edits of `edit_pyproject.py` (upgrade, removal,
  add-leaf, add-closure, transitive; `EDIT_KINDS` picks them) and compares the engine with real uv. `NOOP_TSV` names
  the no-op result that selects the cases. `PYLOCK_UV_VERSION` is passed to the engine as the uv release.
- `snapshot-classpath.sh` copies the build directories so a long corpus run survives a rebuild
  (`PYLOCK_CP_FILE=record/classpath.snapshot.txt`).

`record-uv-repository.sh <edit-dir> <case-dir> <scenario-dir> [uv-release]` turns one `corpus-uv-edits.sh` edit
into a `lock/repository/uv` scenario. uv locks the edit again from an empty cache, then the engine replays it with
`PYLOCK_RECORD_HTTP` set, which saves every index response it receives into `http/`. It prints `exact` when the engine
wrote uv's lock and the engine's outcome otherwise. An edit uv fails on is not recorded. Responses to range requests (a wheel read for its metadata where the index
offers no sidecar) are not recorded either, so such a scenario cannot replay and is left out. uv gets the lock's `[options]` as
flags (`uv-lock-options.py`), and uv and the engine share one pinned "now" (`UV_INTERNAL__TEST_CURRENT_TIMESTAMP`,
`PYLOCK_CURRENT_TIME`), written to `recorded-at`. `corpus-uv-edits.sh` runs uv the same way.

`fetch_corpus.py <candidates> <corpus> [limit]` downloads manifest and lock pairs from GitHub, one per line of
`<owner>/<repo>\t<path-to-lock>`, recording the commit in each case's `META.json`.
