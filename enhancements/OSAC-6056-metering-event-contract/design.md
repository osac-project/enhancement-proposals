---
title: metering-event-contract
authors:
  - ovishlit@redhat.com
creation-date: 2026-10-28
last-updated: 2026-11-03
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
- **Reading access.** Each reader gets one credential that can read every tenant's heartbeat topics,
  `osac.metering.heartbeat.<tenant>`, granted and revoked as configuration.

See [PRD](prd.md) for detailed requirements.

## Motivation

- The usage events are described by code alone. A reader outside couples to types that change in any release.
- A Cloud Provider Admin whose billing system has no OSAC adapter has no path to the usage data.
- The only credentials that can read the heartbeat topics are OSAC's own; the platform cannot share them.
- A reader per tenant makes every new tenant an operator task. The reader is created once, before the
  first tenant, and reads every tenant after it, so onboarding a tenant needs no chart update.
- OSAC-6060, customer-developed adapters, needs this contract first.

## Behavior changes

- The usage event schemas become immutable files in the metering code, each with a version
  and an effective date. CI fails the build on any change to a published file.
- A generator writes the reference and the schema check into `osac-metering`; CI fails a stale copy.
- The metering chart gains a reader list. Each entry names one reader and no tenant, and the
  chart renders one `KafkaUser` with a read and describe ACL on the `osac.metering.heartbeat.` topic
  prefix and a read ACL on a consumer group named after the reader.
- The installer's Kafka resource gains Strimzi's Kafka exporter. It reports consumer-group lag
  per reader and per heartbeat topic. The usage pipeline itself does not change, no new service runs, and
  the contract documents what runs on main.

## Goals and Non-Goals

### Goals

- One contract over the usage pipeline: payload, reading rule, lifecycle, transport, access.
- A reference generated from the code, so it cannot drift.
- Grant and revoke a reader as configuration, with no OSAC credential shared and no restart.
- A worked example a team runs against a dev deployment in an afternoon.
- One grant covers the heartbeat topic prefix `osac.metering.heartbeat.` and the reader's consumer group.

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
  met["Metering"] --> ue(["Heartbeat topic per tenant"])
  ue --> rd["billing-reader, one reader for every tenant"]
  reg[("Registry, schema files, rules")] --> gen["Generator"] -. CI checks .-> ref[("Reference")]
  admin["Cloud Infrastructure Admin"] --> cred["One reader credential"] --> ue
```

| Who | When | What it does |
|---|---|---|
| Metering | Every minute | Writes usage events and corrections to each tenant's heartbeat topic, `osac.metering.heartbeat.<tenant>`. |
| Generator and CI | Every pull request | Regenerates the reference from the code and fails a stale or changed copy. |
| Cloud Infrastructure Admin | Onboarding, offboarding | Adds or removes the reader in the chart values. |
| Reader | Always | Discovers the heartbeat topics, keeps its own place, drops repeats by event id, sums per tenant. |

### Key ideas

1. **The contract covers metering's output.** Usage events, corrections, transport, and the reading rule.
2. **A published schema never changes.** A new field is a new schema with a version and an effective date.
3. **Access copies the adapter pattern.** One read-only credential set per reader, granted as chart values.
   A reader covers every tenant's heartbeat topics, so one reader means one credential and one consumer group.

### Running example

Tenants `acme` and `globex`, VM `vm-7` of instance type `small`, project `web`. Dana is the Cloud
Infrastructure Admin. `billing-reader` is a reader an outside team owns. It reads every tenant.

| Time | What happens |
|---|---|
| 09:00 | Dana adds `billing-reader` to the chart values with no tenant field; Strimzi issues its password. |
| 10:01 | Metering sends 20 s of compute for `vm-7`, then 60 s at 10:02 and 60 s at 10:03. |
| 10:04 | `vm-7` stopped at 10:02:30; metering sends a correction of -30 s for the span past the stop. |
| 10:04 | `billing-reader` sums the four usage events: 110 s of compute for `acme`, dimension `small`. |
| 10:05 | `billing-reader` meets `osac.metering.heartbeat.globex`, reads it, and sums that tenant separately by `tenant_id` and account id. |
| 11:00 | A restart resends the 10:04 event; `billing-reader` drops it by event id. |

## Design Details

### What the contract covers

The contract covers the heartbeat topics and the events on them. The event log, the failed-record
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
| Topic naming | One heartbeat topic per tenant, named `osac.metering.heartbeat.<tenant>` |
| Ordering | Each topic has one partition, so events arrive in the order metering sent them |
| Delivery | At least once; repeats carry the same event id |
| Retention | Set per installation, indefinite by default; it is metering's recovery window |
| Compaction | None. Metering checks `cleanup.policy=delete` and refuses a compacted topic |

Metering creates a tenant's heartbeat topic on first use. A reader finds the heartbeat topics by their
prefix. The contract publishes the per-tenant usage pipeline of OSAC-5753, which replaced the shared-topic
layout of the older OSAC-985 metering design.

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

**One reader gets one credential that reads every tenant's heartbeat topics,
`osac.metering.heartbeat.<tenant>`.** The metering chart holds a list of readers as values in the platform
repository. Each entry names the reader and no tenant, and renders one `KafkaUser`, the object Strimzi uses
for a Kafka account. Strimzi issues the password into a Secret. The chart rejects two entries with the same
reader name. The connection needs TLS and the password, and the reader must trust the shared OSAC CA. The
admin hands over the password, the CA certificate, and the address, out of band.

The model replaces one reader per tenant because creating and rotating a Kafka reader for each tenant is a
poor operator experience. Each tenant would add a secret to hand over and a place to look when usage
stalls. One reader means one secret and one lag figure.

The values entry names the reader alone:

```yaml
metering:
  readers:
    - name: billing-reader
```

**A grant covers the heartbeat topic prefix `osac.metering.heartbeat.` and the reader's group.** The
`KafkaUser` carries a read and describe ACL on names that start with `osac.metering.heartbeat.`, and a read
ACL on the consumer group named after the reader. It reads no raw event log and no dead-letter topic, and it
cannot write. Metering does not serve the built-in `system` and `shared` tenants, so their heartbeat topics
are never created.

**The reader discovers the tenants.** It lists heartbeat topics with the prefix, or subscribes to a regular
expression such as `^osac\.metering\.heartbeat\..*`, and meets a new tenant's heartbeat topic on first use.
It separates usage by `tenant_id` and by external billing account id, so one read covers every tenant and
each bill still gets only its own usage.

**One consumer group per reader.** The reader commits offsets under its own name, so the exporter
reports lag per heartbeat topic under one reader. A slow tenant does not hide behind a fast one.

**Revocation restarts nothing.** The admin removes the entry and applies the change with a helm
upgrade, which re-renders the `KafkaUser` alone. The metering deployment carries no checksum of
these values, so no OSAC service restarts. Strimzi's user operator deletes the user, its
password, and its ACLs. The broker authorizes every request, so a reader that is still running
fails on its next fetch, within 60 seconds of the upgrade. One removal stops access to every tenant's
heartbeat topics at once. Each grant and revocation is a commit in the platform repository, naming who,
when, and which reader.

**Offboarding a tenant deletes its heartbeat topics.** After the final invoice, the tenant's heartbeat
topics and metering rows are deleted. The reader loses that tenant when the topics are gone, and its
credential still covers the remaining tenants. The reader decides how long to keep the usage it copied.

**A reader cannot write, and its failures cannot disturb the billing pipeline.** The broker
denies every operation the grant does not allow. Each reader keeps its place in the stream, and
OSAC's adapters keep theirs. A slow reader delays only itself, and owns its retries and failed
records.

**The provider can see how far behind each reader is, and who each reader is.** A reader reads
under its own name, and its consumer group carries the same name, so the lag Strimzi's Kafka
exporter reports maps to the reader, per heartbeat topic. This design adds the exporter to the
installer's Kafka resource, with an alert when a reader falls behind. Kafka's ACL listings show who
holds access.

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

The example is a small Go program beside the echo adapter. It reads the heartbeat topics under
its own name, drops repeats by event id, sums the amount per tenant, resource, meter, and
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
| A tenant is offboarded | Its heartbeat topics and metering rows are deleted after the final invoice; the reader loses that tenant and keeps the rest. |
| A new tenant is onboarded | Metering creates its heartbeat topic, and the reader's prefix grant already covers it. |
| A reader writes, or joins OSAC's consumer group | The broker denies it; the credentials can only read. |
| The reader meets an unknown event type | It alerts and does not drop the event silently. OSAC's own adapters dead-letter it and increment a failure counter. |

## Risks and Mitigations

- **Schema versions multiply over time.** Only a new field needs a version; new resource types cost nothing.
- **A slow reader falls behind, and old records expire with retention.** Lag is visible per heartbeat
  topic, and retention is metering's recovery window, set per installation.
- **The file check flags a change that turns out harmless.** The check compares published files as
  written, so the author sees every difference before it merges.
- **One credential covers every tenant.** A leaked reader credential exposes every tenant's heartbeat
  topics, where the per-tenant model limited a leak to one tenant. The credential carries read-only ACLs on
  the heartbeat topic prefix and one group, OSAC rotates it, the network admits only the reader's systems,
  and the provider audits who holds it. Tenants stay separate by `tenant_id` and by external billing
  account id.
- **No per-tenant revocation.** To stop one tenant the provider stops the reader or deletes that tenant's
  heartbeat topics. Deleting the topics removes that tenant's usage from every reader at once.

## Drawbacks

Readers must handle more than one schema version over time. One reader reads every tenant's heartbeat
topics, so one leaked credential exposes all of them and a bug in the reader can misbill several tenants at
once. There is no way to revoke one tenant without stopping the reader or deleting that tenant's heartbeat
topics. Every new field costs a new schema file and its publication.

## Alternatives

- **A pull API over Kafka.** It needs a new service and new login work; a `KafkaUser` already grants the same access.
- **One reader per tenant, the earlier model.** It allowed revoking a single tenant, but every new tenant
  needed a chart change and a secret to hand over, and the operator watched one lag figure per tenant. This
  design replaced it.
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
11. An admin grants a reader with one chart entry that names no tenant; the reader reads every tenant's
    heartbeat topics with one credential, finds them by prefix, and holds a read ACL on its one consumer
    group. Creating a tenant creates its heartbeat topic, and the reader reads it with no chart change.
12. Removing the entry stops the reader's access to every tenant's heartbeat topics at once; a running
    reader's next fetch fails within 60 seconds; no OSAC pod restarts.
13. Each grant and revocation is a commit naming who, when, and which reader.
14. The reader's credentials cannot write, and its failures cannot disturb OSAC's billing pipeline; the
    broker denies the write.
15. The provider sees how far behind each reader is, per heartbeat topic, and who each reader is, keyed by
    consumer group name.
16. The contract states the reader owns its retries and failed records.
17. The contract states the raw event log stays internal.
18. The example runs against a dev deployment, reads usage events, derives a billable total, and stores no credentials.
19. A schema change that leaves the reference or the schema check stale fails the check.
20. Offboarding a tenant deletes its heartbeat topics after the final invoice; the reader loses that tenant
    and its credential still covers the remaining tenants.
21. A published version stays readable for as long as its records are retained; no version has been retired.

---

## Provenance

Committed: commit @ design 0.11.3 - 9b25062, workspace main @ e526ec64b

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"e526ec64b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
