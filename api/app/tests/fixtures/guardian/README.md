# Guardian integration test fixtures

Shared fixture files for Guardian acceptance + contract tests.

## Convention (Constitution §Development Workflow #3)

These files are *the same* JSON events as `samples/gdst/*.json` and `samples/fsma/*.json`
at the repo root — one source of truth. `/speckit-implement` will populate both
locations (by symlink or by file-level equality) so there is no drift between the
GPS submission samples and the test fixtures.

Expected layout once implemented:

```
api/app/tests/fixtures/guardian/
├── gdst/                       # symlinked to /samples/gdst/
│   ├── fishing.json
│   ├── landing.json
│   ├── transshipment.json
│   ├── on_vessel.json
│   ├── processing.json
│   ├── shipping.json
│   └── aggregation.json
├── fsma/                       # symlinked to /samples/fsma/
│   ├── creating.json
│   ├── shipping.json
│   ├── receiving.json
│   ├── transforming.json
│   ├── packing.json
│   └── unpacking.json
└── mgs_responses/              # recorded MGS responses for respx replay
    ├── login.json
    ├── register.json
    ├── profile.json
    ├── schema_create.json
    ├── policy_create.json
    ├── external_submit.json
    ├── task_completed.json
    └── vc_query.json
```

Every file is referenced by at least one test in
[../../integration/guardian/](../../integration/guardian/). Adding a fixture that
no test references is a bootstrap-time check performed by
`/speckit-analyze` / CI.
