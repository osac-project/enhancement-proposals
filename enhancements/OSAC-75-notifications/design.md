---
title: notifications
authors:
  - jubah@redhat.com
creation-date: 2026-11-06
last-updated: 2026-11-07
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-75
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-983-reliable-event-distribution"
  - "/enhancements/OSAC-4500-quota-foundation"
---

# Notifications

## Summary

A **notification** is a durable notice that something of interest happened for a Tenant User or for tenant
automation. Examples include a resource becoming ready, a quota warning, a billing notice, or a platform
announcement. It is meant to be read/consumed by users through various channels such as console inbox, email or a webhook.

This design adds a dedicated notification service (**osac-notifications**). Producers such as fulfillment-service,
metering, and billing can publish **CloudEvents** to per-tenant Kafka topics. Notification service consumes these events,
persists them, and asynchronously fans out to the per-user inbox and to matching Tenant Admin webhook subscriptions.
Tenant announcements are created by Tenant Admins, shown as a UI banner and only the Tenant Admin removes them.

## Motivation

People and tenant automation need to learn about important changes without polling the Fulfillment Events API or keeping a long-lived
client open. Today the closest option is `Events.Watch`. `Watch` streams resource lifecycle changes to clients that stay
connected, so it suits controllers and tools that can hold a stream. It does not automatically notify tenants or users
when a resource is ready, so teams poll, run custom Watch clients, or miss important changes when nobody is
listening.

Even with durable `Watch` delivery, streaming resource change is not the same as notifying a Tenant User or an
admin. Also, tenant care about notifications such as quota warnings and billing alerts, and not only resource lifecycle
changes. Those need a delivery path that reaches people and automation even when no client is watching, and
that does not block the producing business flow when an endpoint is down.

### Goals

- Ship notifications service as a separate binary and Helm chart so multiple producers publish a stable CloudEvents
  contract to Kafka.
- Consume from `osac.notifications.<tenant>` topic, persist accepted events, and fan out to inbox and webhooks.
- Expose CRUD endpoint for Tenant Admins to create and manage subscriptions.
- Expose Create, List, Get, Update, Delete on `Notifications` for event-driven notices and Admin announcements.
- Persist per-user inbox messages and Tenant Admin webhook subscriptions with CEL validation at time of creation and
  tenant isolation on every read path.
- Deliver webhooks with Standard Webhooks signatures, a published exponential retry schedule, delivery-attempt history,
  and auto-pause after sustained failure.
- Validate each webhook URL when the subscription is created and again when a delivery is attempted, and reject
  non-HTTPS or non-public destinations.

### Non-Goals

- Stateful alarms and alert management such as silence and inhibition.
- Additional channels such as email, SMS, and Slack.
- Digests (batched or summarized notices) and custom message templates.
- Tenant User managed subscriptions. Only Tenant Admins create and manage webhook subscriptions in this iteration.
- Turning Watch or `osac.events.<tenant>` object change streams into notifications automatically. Producers publish
  notification CloudEvents only when they want a notice.

## Proposal

Producers publish CloudEvents to per tenant Kafka topics. The notifications service (osac-notifications) consumes each
event, validates and stores it. It then processes the event payload along two paths. For Tenant Users, it creates inbox
rows from the event’s `recipient_ids`. Announcements skip inbox fan-out. One stored event is enough for a tenant-wide
UI banner. The Tenant Admin removes that announcement. For Tenant Admins, a subscription pattern is used. When
subscription matching is enabled, it evaluates active subscriptions against the event, and for each match it sends to
the webhook channel on that subscription. For the first iteration, the fulfillment service is the only producer and
webhook is the only supported channel for subscription.

```mermaid
flowchart LR
    FS[fulfillment-service]
    M[osac-metering]
    B[billing]
    Admin[Tenant Admin]
    K[Kafka<br/>osac.notifications.tenant]
    N[osac-notifications]
    I[UI Inbox]
    Banner[UI Banner]
    W[Webhook]
    FS --> K
    M -.-> K
    B -.-> K
    K --> N
    Admin --> N
    N --> I
    N --> Banner
    N --> W
```

Solid arrows mark the first iteration path. Dotted arrows show other producers that can publish on the same topics
later.

### Workflow Description

Kafka is the producer ingest path for event-driven notices. A successful Kafka write is enough for the producer.
The notification service consumes the CloudEvent, validates and dedupes it, then commits a `NotificationEvent` plus
outbox intents in one database transaction. That database commit is the durable acceptance for fan-out. The consumer
commits the Kafka offset only after that transaction succeeds. If the process crashes before the offset commit, the
message may be consumed again and must stay idempotent under `(tenant, source, id)`. The service then creates inbox
rows for the intended users. When subscription matching is enabled, it evaluates Tenant Admin subscriptions and posts
signed HTTPS deliveries to matching webhook channels. Retries and attempt history are stored in the notifications
database.

Notification for announcements use the Admin API ingress. The `create` endpoint accepts the same CloudEvent contract,
stores one tenant-scoped event, and does not create inbox rows.

#### **Tenant User notifications**

```mermaid
sequenceDiagram
    participant Prod as Producer <br>(fulfillment / metering / billing)
    participant Kafka as Kafka <br>osac.notifications.tenant
    participant N as osac-notifications
    participant DB as Notifications DB
    Prod ->> Kafka: publish CloudEvent
    Kafka -->> Prod: ack
    Note over Prod: Producer continues (no inbox wait)
    Kafka -->> N: CloudEvent
    N ->> N: validate + dedupe (tenant, source, id)
    N ->> DB: store NotificationEvent + outbox
    DB -->> N: event and outbox stored
    N ->> DB: create inbox rows
    DB -->> N: inbox rows created
```

**Producer → Kafka**
- Producer writes a CloudEvent to `osac.notifications.<tenant>`
- Kafka sends acknowledgement
- Producer continues without waiting for inbox delivery

**Kafka → osac-notifications**
- Service consumes the CloudEvent
- Validates schema, tenant match, `source` → allowed `osacnotificationkind` grant map, and `type` pattern
- Rejects `osacnotificationkind` of `announcement` on Kafka (Admin API only)
- Dedupes on `(tenant, source, id)`

**osac-notifications → Notifications DB**
- Stores `NotificationEvent` and outbox intents in one transaction
- Commits the Kafka offset only after that transaction succeeds
- Creates inbox rows from `data.recipient_ids`

##### Notifications

**Event-driven notifications**
- Ingress is Kafka.
- Producers publish a CloudEvent when something happens (resource ready, quota warning, billing, or meter).
- The notification kind is one of `event`, `quota`, `meter`, or `billing`.
- The producer sets `data.recipient_ids`. Those subject ids become inbox recipients. Notifications does not discover
  recipients with RBAC.
- Stored as one `notification_events` row plus one `inbox_notifications` row per recipient.
- Managed with the `Notifications` endpoints (`List`, `Get`, `Update`, `Delete`).
- Optional webhook fan-out when `osacmatchsubscriptions` is true.
- If `data.resource` is set, List and Get call fulfillment with the caller’s identity. The notification is hidden or
  omitted when the caller can no longer see the resource. See **RBAC / Tenancy**.

**Announcements**
- Ingress is the Admin API only. Kafka consumers reject `announcement`.
- Tenant Admin calls `Notifications.Create` with the same CloudEvent contract.
- The notification kind is `announcement`. The notice is for everyone in the tenant.
- The server sets `osactenant` from auth and `source` as `osac-notifications`.
- Stored as one `notification_events` row and zero inbox rows.
- The UI shows it as a banner via `Notifications` List or Get (filter `kind=announcement`).
- Only the Tenant Admin may remove it with `Notifications.Delete`. That removes the shared event for everyone.
- Per-user dismissal is an alternative, not v1. See **Alt E**.

#### **Tenant Admin webhook**

```mermaid
sequenceDiagram
    participant Prod as Producer <br>(fulfillment / metering / billing)
    participant Kafka as Kafka <br>osac.notifications.tenant
    participant N as osac-notifications
    participant DB as Notifications DB
    participant Hook as Tenant webhook
    Prod ->> Kafka: publish CloudEvent
    Kafka -->> Prod: ack
    Note over Prod: Producer continues (no webhook wait)
    Kafka -->> N: CloudEvent
    N ->> N: validate + dedupe (tenant, source, id)
    N ->> DB: store NotificationEvent + outbox
    DB -->> N: event and outbox stored
    N ->> DB: match CEL subscriptions if osacmatchsubscriptions
    DB -->> N: matching subscriptions
    N ->> Hook: signed HTTPS POST
    Hook -->> N: HTTP response
```

**Producer → Kafka**
- Producer writes a CloudEvent to `osac.notifications.<tenant>`
- Kafka sends acknowledgement
- Producer continues without waiting for webhook delivery

**Kafka → osac-notifications**
- Service consumes the CloudEvent
- Validates schema, tenant match, `source` → allowed `osacnotificationkind` grant map, and `type` pattern
- Rejects `osacnotificationkind` of `announcement` on Kafka
- Dedupes on `(tenant, source, id)`

**osac-notifications → Notifications DB**
- Stores `NotificationEvent` and outbox intents in one transaction
- Commits the Kafka offset only after that transaction succeeds
- When `osacmatchsubscriptions` is enabled, loads active subscriptions for that tenant
- Evaluates each CEL filter against the event

**osac-notifications → Tenant webhook**
- Creates a delivery row for each match
- POSTs immediately when the subscription is not paused
- If subscription is pause, store the notification for later delivery when the subscription is unpaused
- Retries and auto-pause follow the webhook delivery rules

##### Tenant Admin subscription

A Tenant Admin creates a subscription with a CEL filter and an HTTPS webhook URL. Creation returns a one-time signing
secret. The Admin can list, get, update (including pause and unpause), and delete subscriptions in their tenant. Tenant
Users cannot create or manage subscriptions.

**Example subscription** (illustrative quota warnings for tenant `acme`):

```json
{
  "id": "sub-acme-quota-warn",
  "tenant": "acme",
  "display_name": "Quota warnings",
  "webhook_url": "https://hooks.acme.example/osac/quota",
  "filter": "osacnotificationkind == \"quota\" && severity in [\"warning\", \"critical\"]",
  "paused": false
}
```

The subscription `Create` endpoint also returns `signing_secret` once. It is not returned from `List` or `Get`. Full
delivery history is listed through `NotificationSubscriptionDeliveries` (filter by subscription id).

**Matching an incoming event.** After osac-notifications accepts a CloudEvent for tenant `acme`:

1. If `osacmatchsubscriptions` is false, skip webhook matching. Inbox fan-out may still run.
2. Load all non-deleted subscriptions for that tenant, including paused ones.
3. Build a CEL input from the event: `event_type` (CE `type`), `severity`, `osacnotificationkind`, `summary`,
   `resource.kind`, `resource.id`, and tenant metadata.
4. Evaluate each subscription’s `filter` against that input. A true result is a match.
5. For each match, create a `notification_deliveries` row linked to the subscription and event.
6. If the subscription is not paused, send under **Webhook delivery**. If it is paused, keep the delivery in a retained
   state and do not POST until unpause or recovery handling runs.

Example: the illustrative quota CloudEvent in the schema section has `osacnotificationkind: "quota"` and
`severity: "warning"`. It matches `sub-acme-quota-warn` (subscription above). An `info` quota event or an
`event` kind notice does not match.

#### Webhook delivery

Deliveries use a 30s timeout, a published exponential retry schedule, and per-attempt history. After sustained
failure for five days the subscription auto-pauses. Kafka is not the webhook retry ledger.

**Pause and retain.** A match against a paused subscription still creates a delivery record. The service does not drop
the match. While paused, it does not POST new attempts for that subscription. When the Tenant Admin unpauses it, or when
the endpoint recovers after an outage, the service resumes retained deliveries. Each retained delivery is either
delivered successfully or reported failed under the same retry rules. Auto-pause from sustained failure uses the same
retain behavior so matches during the pause are not lost.

It requires HTTPS destinations. The hostname is resolved and connected only to an address that passes policy checks at
subscription creation time and again at each delivery attempt. Does not follow redirects.
Always block loopback and cloud metadata ranges.

Authenticity uses the [Standard Webhooks](https://www.standardwebhooks.com/) HMAC scheme. Each subscription gets its
own signing secret (`whsec_…`), returned once on create and on rotate. Every delivery attempt sends:

- `webhook-id`: stable id for the delivery (receivers dedupe retries)
- `webhook-timestamp`: unix time of this attempt
- `webhook-signature`: HMAC-SHA256 over `webhook-id.timestamp.body`, versioned as `v1,…`

Receivers recompute the HMAC with the shared secret and reject bad signatures. Reject timestamps outside a skew
window (libraries default to about five minutes). Treat `webhook-id` as an idempotency key. During rotate, sign with
both old and new secrets for an overlap window so either signature verifies. Then drop the old secret. Payload bodies
must not contain credentials or other secrets.

#### Error paths

**Bad or unauthorized CloudEvent**
- Schema is invalid, tenant does not match the topic, `source` or `osacnotificationkind` is outside the grant map,
  `announcement` arrived on Kafka, or `type` fails the pattern.
- Create no inbox rows and no webhooks.
- Emit a metric. Optionally send the record to a dead-letter topic outside the consumer subscription.

**Duplicate CloudEvent**
- The same `(tenant, source, id)` was already accepted.
- Ignore the duplicate (idempotent consume).
- Do not create a second inbox or webhook fan-out.

**Unsafe webhook URL (subscription creation)**
- URL fails SSRF checks (non-HTTPS, blocked address ranges, and so on)
- Reject the creation with `InvalidArgument`
- No subscription is stored

**Cross-tenant API access**
- Caller asks for another tenant’s inbox, subscription, or delivery
- Return empty results or `NotFound`
- Do not leak that the other tenant’s objects exist

**Fulfillment unavailable on inbox RBAC**
- Inbox item has `data.resource` and fulfillment cannot be reached for the visibility check
- Fail closed: omit or hide that item for this List/Get
- Items without `data.resource` are unaffected

### API Extensions

**Tenant-facing gRPC** on osac-notifications:

|Service|Method|Purpose|
|---|---|---|
|`NotificationSubscriptions`|`Create`|Create a webhook subscription.|
|`NotificationSubscriptions`|`List`|List subscriptions in the caller’s tenant. Supports pagination and filtering.|
|`NotificationSubscriptions`|`Get`|Get a subscription by id.|
|`NotificationSubscriptions`|`Update`|Update subscription filter, webhook URL, or pause and unpause a subscription.|
|`NotificationSubscriptions`|`Delete`|Delete a subscription and stop further deliveries.|
|`NotificationSubscriptionDeliveries`|`List`|List delivery history (paginated). Filter by subscription id and related fields (status, time).|
|`NotificationSubscriptionDeliveries`|`Get`|Get one delivery or attempt record.|
|`Notifications`|`Create`|Tenant Admin creates an announcement (same CloudEvent contract).|
|`Notifications`|`List`|List the caller’s event-driven notifications and active tenant announcements (filter by kind).|
|`Notifications`|`Get`|Get an event-driven notification or tenant announcement by id.|
|`Notifications`|`Update`|Mark an event-driven message as read, dismiss, or other state. Not used for announcements.|
|`Notifications`|`Delete`|Delete the caller’s event-driven notification, or (Tenant Admin) remove a tenant announcement for everyone.|

### UX Alignment

New `@temp-api` shapes against the **notifications** public API. Console proxy routes to osac-notifications.

### Implementation Details/Notes/Constraints

#### Component layout

```text
osac/
  osac-notifications/     # binary, Kafka consumer, chart
  fulfillment-service/    # CE publisher + RBAC authority for resource
  osac-metering/          # CE publisher
  osac-installer/         # notifications chart + topic lifecycle
```

#### CloudEvents contract

CloudEvents 1.0, JSON `data`, aligned with metering extension style (`osactenant`).

|Attribute|Required|Meaning|
|---|---|---|
|`id`|yes|Idempotency key that is stable for this producer. Uniqueness is enforced as `(tenant, source, id)`.|
|`source`|yes|Producing service identity (for example `fulfillment-service`, `osac-metering`, or `osac-billing`).|
|`type`|yes|`osac.notification.<kind>.<name>` (see validation below)|
|`time`|yes|Time of the event|
|`specversion`|yes|`1.0`|
|`osactenant`|yes|Tenant id. Must match the topic suffix.|
|`osacnotificationkind`|yes|`event` \| `meter` \| `billing` \| `quota` on Kafka. `announcement` only on Admin `Notifications.Create`.|
|`severity`|yes|`info` \| `warning` \| `critical`|
|`osacmatchsubscriptions`|no|Whether to evaluate webhook subscriptions. Defaults to `true`.|
|`data`|yes|See below|

**Validation (Kafka ingest):** Reject the event if any check fails.

- A consumed Kafka record does not carry the producer’s authenticated principal. The consumer authorizes using a
  configured grant map: each `source` is set to its allowed `osacnotificationkind` values. Reject the event when
  `source` or `osacnotificationkind` is outside that map.
- Each producer KafkaUser is assigned one `source` value in that map. The owning service must set that `source` on
  every event. Kafka ACLs still control which principals may write tenant topics.
- Reject `osacnotificationkind` of `announcement`. Announcements use Admin `Notifications.Create` only.
- `type` must be `osac.notification.<kind>.<name>` where `<kind>` equals `osacnotificationkind`.
- `<name>` is free within a pattern: nonempty, lowercase letters, digits, and underscores only (for example
  `warning`, `resource_created`, or `maintenance`).
- `osactenant` must match the topic suffix.

**Validation (Admin `Notifications.Create`):** Reject non-announcement kinds. Set `osactenant` and `source` on the
server. Do not allow client-supplied tenant or source.

**`data` (v1):**

|Field|Required|Meaning|
|---|---|---|
|`summary`|yes|Short text that summarizes a notification message|
|`body`|no|Longer text that contains details of the message|
|`recipient_ids`|no|Targeted inbox recipients (subject/user ids). Required for non-announcement inbox fan-out. Omit for announcements (no inbox expand).|
|`resource`|no|`{ "kind", "id" }` OSAC objects that points to user's RBAC.|
|`details`|no|Kind-specific map (e.g. used/limit). Optional; empty for many announcements.|
|`links`|no|Optional deep links; UI may derive from `resource` + kind if omitted.|

**Example of quota warning** → topic `osac.notifications.acme`:

This example is illustrative only. Quota producer behavior and Admin recipient selection are out of scope for this
design.

```json
{
  "specversion": "1.0",
  "id": "quota-warn-acme-compute-2026-11-07T18:00:00Z",
  "source": "osac-billing",
  "type": "osac.notification.quota.warning",
  "time": "2026-11-07T18:00:00Z",
  "datacontenttype": "application/json",
  "osactenant": "acme",
  "osacnotificationkind": "quota",
  "severity": "warning",
  "osacmatchsubscriptions": true,
  "data": {
    "summary": "Compute vCPU quota at 90%",
    "body": "You have used 90 of 100 vCPUs.",
    "resource": {
      "kind": "quota",
      "id": "quota-compute"
    },
    "details": {
      "meter": "compute.vcpu",
      "used": "90",
      "limit": "100",
      "threshold_percent": 90
    }
  }
}
```

**Example of fulfillment resource notice** → topic `osac.notifications.acme`:

Explicit producer publish (not Watch). Fulfillment puts the **requesting user’s subject id** in `data.recipient_ids`
(information it already has on the creation path). `resource` identifies the object for later visibility checks.

```json
{
  "specversion": "1.0",
  "id": "fulfillment-ci-created-vm-42-2026-11-07T18:05:00Z",
  "source": "osac-tenant",
  "type": "osac.notification.event.resource_created",
  "time": "2026-11-07T18:05:00Z",
  "datacontenttype": "application/json",
  "osactenant": "acme",
  "osacnotificationkind": "event",
  "severity": "info",
  "osacmatchsubscriptions": false,
  "data": {
    "summary": "Compute instance vm-42 created",
    "body": "Your compute instance vm-42 is ready.",
    "recipient_ids": [
      "user-123"
    ],
    "resource": {
      "kind": "compute_instance",
      "id": "vm-42"
    },
    "details": {
      "lifecycle": "created",
      "project_id": "proj-9",
      "name": "vm-42"
    }
  }
}
```

**Example of announcement** → `Notifications.Create` request body (same CloudEvent contract for client-supplied
fields). The server sets `osactenant` from auth and `source` to `osac-notifications`. Clients must not send those
fields.

```json
{
  "specversion": "1.0",
  "id": "announce-acme-maintenance-2026-11-10",
  "type": "osac.notification.announcement.maintenance",
  "time": "2026-11-07T18:10:00Z",
  "datacontenttype": "application/json",
  "osacnotificationkind": "announcement",
  "severity": "warning",
  "osacmatchsubscriptions": false,
  "data": {
    "summary": "Scheduled maintenance window",
    "body": "Control-plane maintenance is planned for 2026-11-10 02:00–04:00 UTC. API calls may fail during that window."
  }
}
```

#### Persistence

osac-notifications owns its Postgres tables.

- `notification_events`: accepted event (id, source, type, kind, severity, payload, tenant). Unique on
  `(tenant, source, id)` for dedupe.
- `inbox_notifications`: one row per recipient user (owner subject id plus link to `notification_events`).
- `notification_subscriptions`: Tenant Admin webhook subscriptions
- `notification_deliveries` and `notification_delivery_attempts`: webhook delivery history under a subscription,
  including retained matches created while a subscription was paused
- `notification_outbox`: create inbox rows or send webhooks for an accepted event. Saved with the event so
  the work is not lost if the service restarts.

#### Installer

- Chart for osac-notifications
- On tenant create, provision `osac.notifications.<tenant>` (one partition) and optional
  `osac.notifications.dlq.<tenant>`
- Consumer group `osac-notifications` subscribes only to ingest topics. Use a regex that matches exactly one tenant
  segment and therefore excludes DLQ topics such as `osac.notifications.dlq.<tenant>` (for example
  `^osac\.notifications\.[^.]+$`).
- Do not put DLQ topics in the same consumer subscription as ingest topics.
- Reuse the existing Strimzi `KafkaUser` pattern (same approach as fulfillment’s `osac.events.*` ACLs). Extend
  producer users with publish rights on `osac.notifications.` topics and wire bootstrap plus credentials into producer
  charts. The Kafka broker enforces those ACLs on write.
- Configure the notifications consumer grant map so each `source` is set to its allowed `osacnotificationkind`
  values. Assign each producer KafkaUser one `source` value that its service must set on every event.
- Worker and retry knobs as needed

### Security Considerations

- **Who may publish.** Kafka ACLs (provisioned by the installer, enforced by the broker on write) limit each
  producer principal to the tenant topics it may write. Producers authenticate with those credentials and publish.
  The notifications consumer authorizes each event using a configured grant map where each `source` is set to its
  allowed `osacnotificationkind` values (see validation below). An event is rejected when `source` or
  `osacnotificationkind` is outside that grant, even if the topic ACL allowed the write. Kafka ingest rejects
  `announcement`. `osactenant` must match the topic name.
- **Who may call the public API.** OPA (or equivalent) enforces Keycloak roles on
  `NotificationSubscriptions`, `NotificationSubscriptionDeliveries`, and `Notifications`.
- **Webhook destinations.** Validate URLs at create and at each delivery so the service does not call unsafe or
  internal addresses. Sign each delivery with the subscription secret. Do not put credentials in payload bodies.
- **Calls to fulfillment.** The notifications service account may call fulfillment only to check `data.resource`
  visibility for inbox List and Get.

### RBAC / Tenancy

**API roles**
- Tenant User: Can perform List/Get/Update/Delete on their own `Notifications`.
- Tenant Admin: can create and manage subscriptions and subscription delivery history in the tenant. `Notifications.Create` and
  `Notifications.Delete` for tenant announcements (handler enforces admin for `announcement` kind).
- Cloud Provider Admin: cross-tenant webhook health.
- Kafka: tenant isolation by topic name and ACL. Consumer grant map sets each `source` to allowed
  `osacnotificationkind` values.

**Recipient resolution vs resource visibility**

These are different jobs. Fulfillment RBAC (Get or SelfSubjectAccessReview) answers whether **this** recipient may see
**this** object. It does not efficiently answer who should receive an inbox row.

|Concern|Who decides|Mechanism|
|---|---|---|
|**Who gets an inbox row** (targeted)|**Producer**|`data.recipient_ids` (subject ids already known on the write path).|
|**Who sees an announcement**|**Tenant scope**|Tenant Admin `Notifications.Create` stores one `notification_events` row. Admin Delete removes it.|
|**May this caller see this inbox item**|**osac-notifications** at List/Get|If `data.resource` is set, call fulfillment with the caller’s identity. Deny or omit if not allowed.|
|**Webhook subscribers**|Tenant Admin subscriptions + CEL|Only when `osacmatchsubscriptions` is true. Independent of inbox recipients.|

When `data.resource` is set, List/Get (and optional write-time filter) call fulfillment for per-subject visibility.
Announcements without `resource` skip that check. Recipient discovery is never done by enumerating RBAC in v1.
Notifications SA calls fulfillment only for these `resource` checks.

### Risks and Mitigations

|Risk|Mitigation|
|---|---|
|A producer is granted the wrong Kafka ACL and can publish into another tenant’s topic.|Deny publish by default. Grant ACLs per producer and tenant. Cover ACL boundaries in integration tests.|
|A producer forges another service’s `source` or publishes an `osacnotificationkind` it is not authorized for.|Authorize with a grant map where each `source` is set to allowed `osacnotificationkind` values. Assign each producer one `source`. Reject events outside the map.|
|A producer publishes `announcement` on Kafka and bypasses Admin Create authorization.|Reject `announcement` on Kafka ingest. Create announcements only through Admin `Notifications.Create`.|
|Two producers reuse the same CloudEvent `id` for one tenant and one event is dropped.|Dedupe on `(tenant, source, id)`, not `(tenant, id)` alone.|
|The consumer also reads DLQ topics and republishes invalid records.|Use a distinct DLQ name pattern and a consumer regex that excludes DLQ topics.|
|A match during pause is lost because no delivery row was created.|Create a retained delivery for paused matches. Resume or fail those deliveries on unpause under retry rules.|
|A webhook URL points at an internal or non-public address (SSRF).|Validate URLs when the subscription is created and again on each delivery. Reject non-HTTPS and non-public destinations. Restrict egress at the platform layer.|
|Producers drift from the CloudEvent contract and send incompatible payloads.|Enforce the `type` pattern and the grant map of `source` to allowed `osacnotificationkind` values. Reject events that are missing required fields. Prefer additive optional `data` fields.|
|Operators confuse notification topics with Watch or metering topics.|Use the distinct `osac.notifications.` prefix. Document the topic contract next to producer setup.|
|A caller forges `osactenant` or `source` on `Notifications.Create`.|Set tenant and `source` on the server from auth and service identity. Do not trust those fields from the client.|
|A Tenant User creates or deletes a tenant-wide announcement.|Authorize Create and Delete for announcements to Tenant Admin only. Cover allow and deny cases in tests.|
|Fulfillment is unavailable during inbox List or Get for a `data.resource` item.|Fail closed for resource-scoped items. Leave items without `resource` unaffected.|

### Drawbacks

- Kafka + topic lifecycle is mandatory for producers (more moving parts than gRPC Submit).
- Inbox RBAC still depends on fulfillment for `resource`.
- In-house webhook sender vs buy Svix tradeoff remains.

## Alternatives

### Alt A — Embed notification plane in fulfillment-service binary

Rejected for multi-producer peer shape.

### Alt B — gRPC Submit as producer ingest (no Kafka)

- **Pros:** Simpler authz at RPC; no topic ops.
- **Cons:** Every producer depends on notifications availability/endpoint; weaker shared ingest log; unlike metering’s
  Kafka CE style.
- **Rejected:** Kafka-only producer path locked.

### Alt C — One Kafka topic per notification kind/type

Rejected — topic explosion; kinds via CE attributes.

### Alt D — mTLS or SNS style cert URLs for webhook authenticity

- **Pros:** Strong peer auth (mTLS). Familiar if receivers already require client certs.
- **Cons:** Cert lifecycle on every tenant receiver. Breaks behind TLS terminating load balancers. SNS cert
  URLs add download and trust chain work. OSAC mTLS today is for fixed platform peers (BCM, Kafka, DB), not
  arbitrary customer callback URLs.
- **Rejected:** Standard Webhooks HMAC covers authenticity, replay, and rotation for tenant HTTPS URLs. Defer
  mTLS until product needs private receivers that already require client certificates.

### Alt E — Per-user announcement expand and dismiss

Expand each announcement to every Tenant User (fulfillment `Users.List`), create one inbox row per user, and let each
user dismiss independently.

- **Pros:** Same dismiss UX as targeted inbox items. No separate banner semantics.
- **Cons:** `Users.List` dependency, N inbox rows per announcement, fan-out cost and failure modes.
- **Rejected for v1:** One tenant-scoped `notification_events` row and a UI banner are enough. Tenant Admin removes
  the announcement for everyone via `Notifications.Delete`. If product later needs per-user dismiss, add lazy
  inbox rows or a dismissals table without rewriting the shared event row.

## Open Questions

### OQ-1: Inbox retention and dismiss TTL

- **Owner:** To be determined (product / UX)
- **Impact:** purge job, storage, dismiss vs delete.

### OQ-2: Database topology for osac-notifications

- **Owner:** To be determined (platform)
- **Impact:** dedicated Postgres vs shared DB.

## Test Plan

### Unit Tests (osac-notifications)

- Reject CloudEvents that are missing required attributes, fail the `type` pattern, or fall outside the configured
  grant map of `source` to allowed `osacnotificationkind` values.
- Reject Kafka events with `osacnotificationkind` of `announcement`.
- Reject events whose `osactenant` does not match the Kafka topic.
- Treat a duplicate `(tenant, source, id)` as a no-op, and accept the same `id` from a different trusted `source`.
- Compile subscription CEL filters and match or miss events by severity and kind.
- Create a retained delivery when a filter matches a paused subscription, and resume or fail it on unpause.
- Reject non-public and non-HTTPS webhook URLs, and verify Standard Webhooks signature and timestamp handling.
- Enforce OPA (or equivalent) on public RPCs, including Tenant Admin–only Create and Delete for announcements.
- Cover webhook retry scheduling and auto-pause after sustained failure.

### Integration Tests

- Publish a valid event-driven CloudEvent to `osac.notifications.<tenant>` and assert inbox rows for `recipient_ids`,
  with webhook delivery when matching is enabled.
- Confirm a second producer can publish with its assigned `source` and `osacnotificationkind` values, and that an
  unknown `source` or unauthorized `osacnotificationkind` is rejected or sent to the DLQ.
- Confirm the Kafka offset is not committed when the accept transaction fails, and that a redelivered event with the
  same `(tenant, source, id)` is a no-op.
- Reject a Kafka-published announcement, and accept the same shape through Admin `Notifications.Create`.
- With `osacmatchsubscriptions` set to false, create inbox rows and do not create webhook deliveries.
- Pause a matching subscription, publish an event, assert a retained delivery with no POST, then unpause and assert
  delivery or failure reporting under retry rules.
- Confirm the consumer does not subscribe to DLQ topics.
- Let a Tenant Admin create an announcement through `Notifications.Create`, then assert one `notification_events` row,
  zero inbox rows, and visibility on List for users in the tenant.
- Deny announcement Create and Delete for a Tenant User, and clear the announcement for everyone when a Tenant Admin
  deletes it.
- Exercise subscription severity filters, subscription delete, private URL rejection, and a shortened webhook retry
  ladder.
- With a fulfillment mock, hide or return resource-scoped inbox items according to the caller’s RBAC result.

### E2E Tests

- From the console, create a subscription, publish an event-driven notice through the producer Kafka harness, and mark the Tenant User inbox item as read.
- Verify cross-tenant isolation for the public API and for Kafka topics.

## Infrastructure Needed

- `osac/osac-notifications` component (binary, image, chart, CI).
- Kafka topic lifecycle for `osac.notifications.<tenant>` (+ optional DLQ).
- PostgreSQL for notifications.
