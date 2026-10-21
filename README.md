# rewrite-python lock fixtures

Recorded package-manager output used by the native Python lock regeneration tests in
[openrewrite/rewrite](https://github.com/openrewrite/rewrite) (`rewrite-python`). Each scenario is replayed offline,
and the engine must reproduce the package manager's lock byte for byte, or fail the way the scenario records.

The scenarios still live in `rewrite-python/src/test/resources` as well. Until the `rewrite-python` build reads them
from here, a scenario added in one place is added in the other, and the two copies are kept identical.

## Layout

```
lock/<manager>/<scenario>/      manager: uv, poetry, pdm, pipenv
  pyproject.toml   the manifest after the edit (Pipfile for pipenv)
  *.before         the lock before the edit
  *.after          the lock the package manager wrote (absent when it failed)
  http/            the index responses and metadata files the scenario needs
  recording/       for a scenario recorded against a local index, the inputs `record/` serves and edits
```

Each manager directory's README records which release wrote each scenario, against which index, and what the
scenario pins. `lock/uv/BEHAVIOR.md` and `lock/uv/FORMAT.md` record uv's behavior and lock format as observed.

## Recording

Record with the real package manager from an empty cache and never hand-edit a lock. Most uv scenarios are recorded
against a throwaway PEP 503 index of synthetic wheels, served locally and rewritten to `https://index.example`
afterwards. The scripts are in [`record/`](record/README.md).

## License

The test scenarios and their organization are licensed under the Apache License 2.0 (see LICENSE). Recorded index
responses and package metadata of published packages belong to their respective authors under their own licenses,
included as test data.
