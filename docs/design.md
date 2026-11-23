# Design: one schema per organization

Status: demo of the schema-per-tenant pattern, with synthetic data. It does
not claim real Postgres schemas, a web framework, SSO, or a worker cluster.
SQLite tables with a `tenant_<org>_` prefix stand in for real schemas; the
shape — and the isolation guarantee — is the same.

## 1. One schema per organization

Creating an organization creates a schema named `tenant_<organization id>`
with its tables. The shared (`public`) schema keeps only shared tables:
users, sessions, organizations, and a `tenant` registry mapping each
organization to its schema. One customer's data never sits in another
customer's tables.

Code reaches tenant data through `for_organization(id)`, which hands back
tables bound to that one schema. There is no code path that reads tenant
data without going through it.

## 2. Why schemas, not a tenant_id column

A `tenant_id` column is a convention: every query must remember the
filter, and one forgotten `WHERE` leaks data. A schema is a boundary:
a query bound to one schema physically cannot read another's tables.
The isolation is structural, not conventional — it survives a careless
query, a new developer, and a late-night fix.

The cost is real: migrations must run against every schema, and
cross-tenant reporting needs a separate read path. For customer data, the
trade is worth it.

## 3. Durable background work

Adding a project writes it to the tenant schema, then puts an event on a
queue stored in the database. The worker takes events off the queue and
passes each one to that organization's entity: a long-lived object, one
per organization, that handles its messages one at a time — like a
durable object. The entity writes a numbered activity row back into the
tenant schema.

Queue items and entity messages live in the database, so a crash or
restart loses nothing. The worker is stateless; the state is the queue.

## 4. The activity feed

The entity's activity rows are numbered per organization, in the order
the entity handled them. The feed is therefore ordered and complete by
construction — no interleaving, no gaps, no duplicates. If the worker
crashes mid-event, the event stays queued and is processed once by the
next run.

## 5. Auth and organizations

Sign-up creates a user; creating an organization runs a hook that creates
its schema and tables. A user can belong to several organizations. The
shared schema holds the membership; the tenant schemas hold the data.

## 6. What production adds

- **Real Postgres schemas** with a migration runner that applies schema
  changes to `public` and then to every tenant schema.
- **Web app:** the pages people use, with server actions that write
  through `for_organization`.
- **Auth:** sign-up, sign-in, and organizations with an auth library.
- **Secrets:** local secrets from a secret manager, never from `.env`
  files.
- **Workers:** a worker process that runs the queue and the entities,
  alongside the web app.
