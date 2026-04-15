# graphite

Topological metering ontology for AZ Södertälje — Brick Schema over flat tables,
DuckDB for calculations, Streamlit for browsing and curation.

See [`plan.md`](plan.md) for sequencing and [`ontology_proposal.md`](ontology_proposal.md) for the data model.

## Layout

Monorepo, uv workspace.

- `packages/ontology` — table schemas, CSV/DuckDB I/O
- `packages/validation` — write-time rule checks
- `packages/calc` — SQL views for meter nets and aggregations
- `packages/refsite` — deterministic fake-site generator
- `packages/app` — Streamlit app
- `data/` — generated and real-slice CSVs (gitignored)
- `reference/` — raw investigation artifacts (Excels, XMLs, logs)

## Setup

```
uv sync
```

## Common tasks

```
make test       # pytest across all packages
make lint       # ruff
make typecheck  # mypy
make app        # streamlit run
```
