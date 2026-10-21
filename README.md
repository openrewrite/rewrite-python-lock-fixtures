# rewrite-python lock fixtures

Recorded package-manager output used by the native Python lock regeneration tests in
[openrewrite/rewrite](https://github.com/openrewrite/rewrite) (`rewrite-python`). Each scenario is replayed offline,
and the engine must reproduce the package manager's lock byte for byte, or fail the way the scenario records.

The `rewrite-python` build downloads the latest `main` of this repository and puts `lock/` on the test classpath.
There is no published artifact and no version pinning: fixture changes here track the tests in lockstep, and older
revisions of rewrite are not kept building against newer fixtures.

## Layout

```
lock/<manager>/<scenario>/      manager: uv, poetry, pdm, pipenv
  pyproject.before.toml   the manifest before the edit, where the scenario was recorded from one
  pyproject.toml          the manifest after the edit (Pipfile for pipenv)
  *.before                the lock before the edit
  *.after                 the lock the package manager wrote (absent when it failed)
  expect                  the outcome when it is not byte-exact (below)
  http/                   the index responses and metadata files the scenario needs
  recording/              for a scenario recorded against a local index, the inputs `record/` serves and edits
```

A scenario recorded from a public repository's lock is a whole repository, edited as the corpus tools edit it:

```
lock/repository/uv/<repository>__<edit>/
  tree-before/    the repository's manifest as committed
  tree/           the manifest after the edit
  before, after   the lock as committed, and the lock uv wrote after the edit
  about           the lock's source at its commit, and the edit
  recorded-with   the uv release that wrote after
  recorded-at     the moment uv locked, which a relative exclude-newer counts back from
  http/           every index response the engine asked for, and a 404 list of the URLs that answered not found
```

An `expect` line is `<outcome> <reason> [<package>]`. `uv-rejects` means the package manager refused the edit, and
the engine must fail too. `engine-refuses` means the package manager wrote a lock the engine does not reproduce, so
the engine must fail rather than write a different one; such a scenario may keep the package manager's lock as
`*.after` for the record. The reason is the engine's `LockFileRegeneration.Reason`.

Each manager directory's README records which release wrote each scenario, against which index, and what the
scenario pins. `lock/uv/BEHAVIOR.md` and `lock/uv/FORMAT.md` record uv's behavior and lock format as observed.

## Recording

Record with the real package manager from an empty cache and never hand-edit a lock. Most uv scenarios are recorded
against a throwaway PEP 503 index of synthetic wheels, served locally and rewritten to `https://index.example`
afterwards. The scripts are in [`record/`](record/README.md), with `pipenv-oracle.py`, which computes the
Pipfile.lock hashes and JSON layout the pipenv tests expect.

## License

The test scenarios and their organization are licensed under the Apache License 2.0 (see LICENSE). Recorded index
responses and package metadata of published packages belong to their respective authors under their own licenses,
included as test data.
