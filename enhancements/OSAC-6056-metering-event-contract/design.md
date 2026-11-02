---
title: metering-event-contract
authors:
  - ovishlit@redhat.com
creation-date: 2026-10-28
last-updated: 2026-10-28
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-6056
prd:
  - "prd.md"
see-also:
  - "../core-architecture/design.md"
  - "/enhancements/OSAC-5753-event-log-driven-metering"
  - "/enhancements/OSAC-6060-customer-developed-adapters"
  - "/enhancements/OSAC-985-metering-and-usage-tracking"
---

# The metering event contract

## Summary

Metering writes each tenant's usage to Kafka as usage events, and their shape lives only in
OSAC code. This design publishes the contract:

- **A generated reference.** A generator walks the metering code and writes a document a
  person reads plus a schema file a tool checks. A stale copy fails the build.
- **A published schema never changes.** A new field is a new schema with a version and an effective date.
- **Reading access.** Each reader gets credentials that can only read its tenant's topic,
  granted and revoked as configuration.

See [PRD](prd.md) for detailed requirements.

## Motivation

- The usage events are described by code alone. A reader outside couples to types that change in any release.
- A Cloud Provider Admin whose billing system has no OSAC adapter has no path to the usage data.
- The only credentials that can read the usage topics are OSAC's own; the platform cannot share them.
- OSAC-6060, customer-developed adapters, needs this contract first.

## Behavior changes

- The usage event schemas become immutable files in the metering code, each with a version
  and an effective date. CI fails the build on any change to a published file.
- A generator writes the reference and the schema check into `osac-metering`; CI fails a stale copy.
- The metering chart gains a reader list. Each entry names one reader and one tenant, and the
  chart renders one `KafkaUser` with a read ACL on that tenant's usage topic and a read ACL on a
  consumer group named after the reader.
- The installer's Kafka resource gains Strimzi's Kafka exporter. It reports consumer-group lag
  per reader. The usage pipeline itself does not change, no new service runs, and the contract
  documents what runs on main.

## Goals and Non-Goals

### Goals

- One contract over the usage pipeline: payload, reading rule, lifecycle, transport, access.
- A reference generated from the code, so it cannot drift.
- Grant and revoke a reader as configuration, with no OSAC credential shared and no restart.
- A worked example a team runs against a dev deployment in an afternoon.
- A grant covers a single metered tenant.

### Non-Goals

- The raw event log, `osac.events.<tenant>`. It carries internal resource snapshots.
- The adapter extension point, SDKs, and conformance kits. That is OSAC-6060.
- Pricing, rating, invoicing. The reader prices; OSAC meters.
- Provider adapters. M360 is OSAC-3784; Red Hat Cost Management is OSAC-4284.
- User identity on usage events. They carry none today; OSAC-6154 may add one.

## Proposal

### Big picture

```mermaid
flowchart LR
  met["Metering"] --> ue(["Usage topic per tenant"])
  ue --> rd["billing-reader, a reader"]
  reg[("Registry, schema files, rules")] --> gen["Generator"] -. CI checks .-> ref[("Reference")]
  admin["Cloud Infrastructure Admin"] --> cred["Reader credentials"] --> ue
```

| Who | When | What it does |
|---|---|---|
| Metering | Every minute | Writes usage events and corrections to the tenant's usage topic. |
| Generator and CI | Every pull request | Regenerates the reference from the code and fails a stale or changed copy. |
| Cloud Infrastructure Admin | Onboarding, offboarding | Adds or removes the reader in the chart values. |
| Reader | Always | Keeps its own place, drops repeats by event id, sums. |

### Key ideas

1. **The contract covers metering's output.** Usage events, corrections, transport, and the reading rule.
2. **A published schema never changes.** A new field is a new schema with a version and an effective date.
3. **Access copies the adapter pattern.** One read-only credential set per reader, granted as chart values.

### Running example

Tenant `acme`, VM `vm-7` of instance type `small`, project `web`. Dana is the Cloud
Infrastructure Admin. `billing-reader` is a reader an outside team owns.

| Time | What happens |
|---|---|
| 09:00 | Dana adds `billing-reader` for tenant `acme` to the chart values; Strimzi issues its password. |
| 10:01 | Metering sends 20 s of compute for `vm-7`, then 60 s at 10:02 and 60 s at 10:03. |
| 10:04 | `vm-7` stopped at 10:02:30; metering sends a correction of -30 s for the span past the stop. |
| 10:04 | `billing-reader` sums the four usage events: 110 s of compute, dimension `small`. |
| 11:00 | A restart resends the 10:04 event; `billing-reader` drops it by event id. |

## Design Details

### What the contract covers

The contract covers the usage topics and the events on them. The event log, the failed-record
topics, and the usage database stay internal. OSAC meters six resource types with seven meters, as
revision 0001 defines. The reference lists each meter with its unit and billable states.

A usage event is one CloudEvent in JSON, type `osac.resource.heartbeat.v1`. A CloudEvent is a
common envelope for events on Kafka. The payload carries three groups of fields:

- Identity: the tenant, the resource, the meter, its component, and the billing dimensions.
- Quantity: one interval, `from` inclusive and `to` exclusive, an amount, and a unit.
- Provenance: the sending minute, metering's place in the log, and the rules revision.

The generated reference lists every field, its unit, and whether it is required. Timestamps
are UTC with whole seconds. The amount is text with six digits after the point, so reading
it never yields an approximate binary number.

**The reading rule is one sentence.** Add every usage event; a correction is a negative one.
The billable quantity for one resource, meter, component, and set of billing dimensions is the
total.

**The event id drops repeats.** The id is a hash of the tenant, resource type, resource id,
meter, component, billing dimensions, interval start, interval end, and sending minute. It
leaves out the amount and the external billing account id, so a resend keeps its id and the
reader drops the copy. A correction is sent in a later round, so its sending minute differs and
its id never matches the event it corrects. A reader can tell a correction from a repeat.

**Every usage event names its schema version.** It is the type-name suffix, `.v1`. A new
contract version is a new type, `.v2`, with its own effective date, published in the reference.
A reader that meets a type it does not know treats it as a version it has not adopted. The
reference asks the reader to alert, keep the event, and add support before the effective date.
The contract states this rule; it cannot enforce it. OSAC's own adapters dead-letter an event
they cannot translate and increment a failure counter.

Metering derives usage from resource states, which the reader never sees. A resource starts
billing when a rule revision says its state is billable, and each minute metering sends the
difference since the last. A state or dimension change re-keys the usage. A stop sends a
final correction for the span billed past it.

| Transport fact | The rule |
|---|---|
| Topic naming | One usage topic per tenant, named `osac.metering.heartbeat.<tenant>` |
| Ordering | Each topic has one partition, so events arrive in the order metering sent them |
| Delivery | At least once; repeats carry the same event id |
| Retention | Set per installation, indefinite by default; it is metering's recovery window |
| Compaction | None. Metering checks `cleanup.policy=delete` and refuses a compacted topic |

Metering creates a tenant's topic on first use. A reader knows its topic from its grant. The contract publishes
the per-tenant usage pipeline of OSAC-5753, which replaced the shared-topic layout of the older OSAC-985
metering design.

### Schemas never change

The usage event schema lives as a file in the metering code, with a version and the date it
takes effect, the way billing rule revisions carry theirs.

A published schema never changes. A new field is a new schema: a new file with the next version and its effective
date. The old file stays, so its records stay readable. Deleting one fails the build. CI hashes the published files
and fails the build on a changed bit, a rename, a version number used again, or a changed effective date.

Replay uses the versions. Metering rebuilds usage by reading each record with the schema in
effect when it was written, so a rebuild always produces the same usage.

**A published version retires only when its records are gone.** The contract supports every
published version for as long as its records are retained. Retention is indefinite by default,
so no version has been retired. Deleting or cold-storing records is what makes a version
retirable, and that work is outside this contract. The reference announces each version's
effective date, so a reader knows when to adopt it.

A new resource type changes no schema. Its name travels as data, so new offerings need no new version.

The resource events metering reads are protos that follow the add-only rule, and drift tests
already enforce it. The usage event schemas metering writes use the immutable files above.

### Reading access

**Each reader gets credentials that can only read its tenant's usage events.** The metering
chart holds a list of readers as values in the platform repository. Each entry names one reader
and one tenant, and renders one `KafkaUser`, the object Strimzi uses for a Kafka account.
Strimzi issues the password into a Secret. A reader serves one tenant, so the chart rejects two
entries with the same reader name. A billing system that bills many tenants runs one reader
per tenant, each with its own credentials. The connection needs TLS and the password, and the
reader must trust the shared OSAC CA. The admin hands over the password, the CA certificate,
and the address, out of band.

**A grant covers the tenant's usage events and nothing else.** The credentials read that one
topic alone: not the raw event log, not the tenant's dead-letter topic, and not another
tenant's topic. The reader also gets a consumer group named after itself, with a read ACL on
that group, so it can commit offsets and its lag is reported under its name. Metering does not
serve the built-in `system` and `shared` tenants, so their usage topics are never created.

**Revocation restarts nothing.** The admin removes the entry and applies the change with a helm
upgrade, which re-renders the `KafkaUser` alone. The metering deployment carries no checksum of
these values, so no OSAC service restarts. Strimzi's user operator deletes the user, its
password, and its ACLs. The broker authorizes every request, so a reader that is still running
fails on its next fetch, within 60 seconds of the upgrade. Each grant and revocation is a
commit in the platform repository, naming who, when, and which reader.

**Offboarding a tenant removes its reader grants.** The tenant's reader entries go with it, and
after the final invoice the tenant's topics and metering rows are deleted. The reader decides how
long to keep the usage it copied.

**A reader cannot write, and its failures cannot disturb the billing pipeline.** The broker
denies every operation the grant does not allow. Each reader keeps its place in the stream, and
OSAC's adapters keep theirs. A slow reader delays only itself, and owns its retries and failed
records.

**The provider can see how far behind each reader is, and who each reader is.** A reader reads
under its own name, and its consumer group carries the same name, so the lag Strimzi's Kafka
exporter reports maps to the reader. This design adds the exporter to the installer's Kafka
resource, with an alert when a reader falls behind. Kafka's ACL listings show who holds access.

### The generated reference

A generator walks three inputs that already exist as data:

1. the metering registry, which lists every resource type and its tracked fields;
2. the schema files, which carry the JSON field names and shapes, including the billing account id;
3. the default rule revisions shipped with the chart, which name each meter, unit, dimension, and billable state.

It writes two files into `osac-metering/docs/contract/`: a document a person reads and a schema
file a tool checks. CI regenerates both and fails the check on any diff.

A new resource type appears in the reference with no code change. The reference uses the values
that events carry, so a cluster appears as `cluster_order`. Dimension names are still a Go map
(`rules/dimensions.go`), so a new dimension needs that one code edit.

### The billing account id

A usage event carries `external_billing_account_id` when the tenant has one. A tenant without
one omits it. The field is an external label from the provider's billing system, and metering
never uses it to correlate events. The tenant, resource, meter, interval, and dimensions do
that. One tenant maps to one billing account, and one account can bill many tenants (OSAC-3784).

The id can change while a tenant has usage in flight. Metering stamps each heartbeat with the id
current when the round builds it and does not rewrite published heartbeats. A correction is
correlated by tenant, resource, meter, and dimensions, so it reverses the right usage. It
carries the id current when its round builds it. A reader uses the id to route each event and
never uses it to match a correction with the event it corrects.

### The worked example

The example is a small Go program beside the echo adapter. It reads the usage topics under
its own name, drops repeats by event id, sums the amount per resource, meter, and
dimensions, and prints the billable total. Its README documents the run against a dev
deployment: grant the example's user, deploy, run it, and read `vm-7`'s 110 seconds. The
password, the CA certificate, and the bootstrap address arrive as environment variables
from a mounted Secret. The repository carries none.

## What happens when

| Situation | What happens |
|---|---|
| A published schema file changes | CI fails the build on any change. |
| Usage is rebuilt from Kafka | Each record is read with the schema in effect then; the total is the same. |
| A usage event is delivered twice | The copy carries the same event id; the reader drops it. |
| A tenant's billing account changes | Later heartbeats carry the new id; published heartbeats keep theirs. A correction carries the id current when its round builds it. |
| A revoked reader reconnects | The broker refuses the connection at once. |
| A revoked reader keeps running | Its next fetch fails within 60 seconds; OSAC services keep running. |
| A tenant is offboarded | Its reader grants go with it; after the final invoice its topics and metering rows are deleted. |
| A reader writes, or joins OSAC's consumer group | The broker denies it; the credentials can only read. |
| The reader meets an unknown event type | It alerts and does not drop the event silently. OSAC's own adapters dead-letter it and increment a failure counter. |

## Risks and Mitigations

- **Schema versions multiply over time.** Only a new field needs a version; new resource types cost nothing.
- **A slow reader falls behind, and old records expire with retention.** Lag is visible, and retention is
  metering's recovery window, set per installation.
- **The file check flags a change that turns out harmless.** The check compares published files as
  written, so the author sees every difference before it merges.

## Drawbacks

Readers must handle more than one schema version over time. A provider that bills many tenants
runs one reader per tenant, so the number of credentials grows with the number of tenants. Every
new field costs a new schema file and its publication.

## Alternatives

- **A pull API over Kafka.** It needs a new service and new login work; a `KafkaUser` already grants the same access.
- **A hand-written reference.** Prose drifts from the code as coverage grows.
- **Sharing OSAC's adapter credentials.** Revoking one reader would break the billing pipeline.
- **Publishing the raw event log.** It exposes internal snapshots; usage events already carry the usage.
- **New fields inside a published schema.** Replay could read an old record with a newer shape and bill it wrong.

## Open Questions

- How a published version is retired once its records are deleted or moved to cold storage.
- Whether readers get short-lived credentials, which would need OAuth on the Kafka listener.
- Whether the worked example stays in the adapters module or moves into OSAC-6060's SDK work.

## Test Plan

Behaviors to check, one per PRD criterion:

1. The reference lists every resource type that emits usage events, with its meters, units, billable
   states, field meanings, and required fields.
2. The reference states the reading rule: sum every usage event for a resource, meter, component, and set
   of billing dimensions; a correction is a negative one.
3. The reference documents start, change, stop, and corrections, and rebuilds a billable quantity by summing.
4. The reference states topic naming, ordering, delivery, the deduplication key, and how long records stay
   readable. The key leaves out the amount and the billing account id.
5. Every usage event names its schema version; the reference says where to read it.
6. A new field arrives as a new schema file with a version and an effective date.
7. A change to a published schema file fails the build.
8. A rebuild from Kafka, reading each record with the schema in effect then, produces the same usage.
9. The billing account id is present for a tenant with one, omitted for one without. It labels where each
   event is reported and never correlates usage.
10. Every event carries its meter's billing dimensions plus the deployment, tenant, project, catalog,
    template, and meter type.
11. An admin grants a reader by chart values; the reader sees the usage events of the tenant its grant
    names, with its own credentials, no other topic, and a read ACL on its consumer group.
12. Removing the entry stops the reader's access; a running reader's next fetch fails within 60 seconds;
    no OSAC pod restarts.
13. Each grant and revocation is a commit naming who, when, and which reader.
14. The reader's credentials cannot write, and its failures cannot disturb OSAC's billing pipeline; the
    broker denies the write.
15. The provider sees how far behind each reader is, and who each reader is, keyed by consumer group name.
16. The contract states the reader owns its retries and failed records.
17. The contract states the raw event log stays internal.
18. The example runs against a dev deployment, reads usage events, derives a billable total, and stores no credentials.
19. A schema change that leaves the reference or the schema check stale fails the check.
20. Offboarding a tenant removes its reader grants; its topics and rows are deleted after the final invoice.
21. A published version stays readable for as long as its records are retained; no version has been retired.

---

## Provenance

Committed: commit @ design 0.11.3 - 9b25062, workspace main @ e526ec64b

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"e526ec64b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
