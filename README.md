# Multi-Tenant App Base — Demo

A starter for enterprise apps where each organization gets its own
isolated data, rebuilt from scratch with synthetic data. One schema per
organization, durable background work through a queue, and a per-organization
entity that handles its messages one at a time.

This is a personal demo project. It captures the pattern — schema-per-tenant
isolation, a Postgres-backed queue, and per-tenant entities — without any
client code, client data, or proprietary material.

## The problem

Multi-tenancy done with a `tenant_id` column on every table is one missed
`WHERE` clause away from leaking one customer's data to another. Giving
each organization its own schema makes the leak structurally impossible:
a query bound to one schema cannot read another's tables. The background
work gets the same treatment — events live in the database, so a crash
loses nothing.

## How it works

```
Sign up, create an organization
  -> a schema named tenant_<org id> is created with its tables
  -> the shared schema keeps only users, sessions, organizations,
     and the registry mapping each org to its schema
  -> code reaches tenant data through for_organization(id), which
     hands back tables bound to that one schema

Add a project
  -> written to tenant_<org>.projects
  -> an event goes on the queue (stored in the database)
  -> a worker takes the event and hands it to that org's entity —
     a long-lived object, one per org, handling messages one at a time
  -> the entity writes a numbered activity row back into the tenant schema
```

## Run it

```bash
python -m src.run_demo
```

Pure standard library, no dependencies (SQLite via `sqlite3`; schemas are
simulated with prefixed tables, the same shape as real per-schema tables).
It creates two organizations, adds a project to one, runs the worker, and
shows the activity feed — and that the other org sees nothing.

Run the checks:

```bash
python -m unittest discover -s tests -v
```

## What this proves

- **Isolation is structural.** A query bound to `tenant_<org>` tables
  cannot read another org's tables. The test suite proves org A's project
  never appears in org B's list, even when the code asks for it.
- **No lost work.** Events live in the database. A worker crash leaves
  the event queued; the next worker run processes it.
- **Ordered per-org processing.** Each org's entity handles its messages
  one at a time, in order, so the activity feed is numbered and never
  interleaves.
- **Immediate reads, eventual activity.** The project shows up in the list
  right away; the activity row lands once the worker has handled the event.

## Layout

- `src/tenancy.py` — organizations, schema creation, and
  `for_organization` table binding.
- `src/worker.py` — the event queue and the per-organization entity.
- `src/run_demo.py` — the demo walkthrough.
- `docs/design.md` — the full design: schemas, queue, entities, auth.
- `tests/` — checks for isolation, ordering, and crash safety.

## What production adds

Real Postgres schemas (not prefixed tables), a web framework, SSO
sign-up/sign-in with organizations, secret management, and a worker
cluster. None of those are claimed here — the demo is the isolation and
queue mechanism, local only.
