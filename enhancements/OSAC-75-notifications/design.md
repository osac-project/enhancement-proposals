---
title: notifications
authors:
  - jubah@redhat.com
creation-date: 2026-11-06
last-updated: 2026-11-16
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

A **notification** is a durable notice that something of interest happened for a Tenant User or for tenant automation.
Examples include a resource becoming ready, a quota warning, a billing notice, or a platform announcement. Users and
automation consume notifications through channels such as the console inbox and webhooks.

This design adds the Notification APIs and object tables in the fulfillment-service, and adds `osac-notifications` as a
dedicated controller. Producers such as fulfillment-service, metering, and billing can publish CloudEvents to
per-tenant Kafka topics. The `osac-notifications` consumes these events, creates inbox and delivery objects through
the private API, and asynchronously fans out to the per-user inbox and to matching Tenant Admin webhook subscriptions.
Announcements are created by Tenant Admins or Cloud Provider Admins (for the whole platform) through the public API.
They appear as a UI banner. The creating admin role deletes them.

## Motivation

People and tenant automation need to learn about important changes without polling or holding a long-lived
`Events.Watch` stream. `Watch` suits controllers that stay connected. It does not notify users when nobody is
listening, and it does not cover quota or billing notices. Those need a path that reaches people and automation
without blocking the producer when a webhook is down.

### Goals

- Define Notification APIs and object storage in fulfillment-service.
- Ship osac-notifications as a separate controller binary and Helm chart that consumes Kafka and delivers webhooks.
- Let multiple producers publish a stable CloudEvents contract to `osac.notifications.<tenant>`.
- Expose CRUD for Tenant Admin subscriptions and on `Notifications`.
- Deliver webhooks with Standard Webhooks signatures, retries, delivery history, and auto-pause after sustained
  failure.
- Reject non-HTTPS or non-public webhook URLs at subscription create and on each delivery attempt.

### Non-Goals

- Stateful alarms and alert management such as silence and inhibition.
- Additional channels such as email, SMS, and Slack.
- Digests and custom message templates.
- Tenant User managed subscriptions. Only Tenant Admins manage webhook subscriptions in this iteration.
- Turning Watch or `osac.events.<tenant>` streams into notifications automatically.
- Webhook signing-secret rotation. v1 returns a secret once on create. Admins may delete and recreate a subscription
  until rotation ships.

## Proposal

Producers publish CloudEvents to per tenant Kafka topics. The osac-notifications controller consumes each event,
validates it, and creates the accepted event through the Notifications API. It then processes the event payload along two paths.
For Tenant Users, it creates inbox rows from the event’s `recipient_ids`. Announcements skip inbox fan-out. For Tenant Admins,
a subscription pattern is used. When subscription matching is enabled, it evaluates active subscriptions against the event,
and for each match it sends to the webhook channel on that subscription. For the first iteration, the fulfillment
service is the only producer and webhook is the only supported channel for subscription.

```mermaid
flowchart LR
    FS[Fulfillment service<br/>Notification APIs]
    M[osac-metering]
    B[billing]
    K[Kafka<br/>osac.notifications.tenant]
    N[osac-notifications]
    I[Notification Inbox]
    W[Webhook]
    FS --> K
    M -.-> K
    B -.-> K
    K --> N
    N --> I
    N --> W
```

Solid arrows mark the first iteration path. Dotted arrows show other producers that can publish in future version.

### Workflow Description

#### Event-driven fan-out

```mermaid
sequenceDiagram
    participant Prod as Producer <br>(fulfillment / metering / billing)
    participant Kafka as Kafka <br>osac.notifications.tenant
    participant N as osac-notifications
    participant FS as fulfillment-service
    participant User as Tenant User
    participant Hook as Tenant webhook
    Prod ->> Kafka: publish CloudEvent
    Kafka -->> Prod: ack
    Note over Prod: Producer continues without waiting for fan-out
    Kafka -->> N: CloudEvent
    N ->> N: validate + store notification_intent
    N ->> FS: private API create inbox Notifications
    FS -->> N: inbox objects created
    N ->> FS: private API create deliveries
    FS -->> N: delivery objects created
    User ->> FS: List / Get / SetNotificationState / Delete Notifications
    FS -->> User: inbox items
    N ->> Hook: signed HTTPS POST for pending deliveries
    Hook -->> N: HTTP response
```

**Producer → Kafka**
- Producer writes a CloudEvent to `osac.notifications.<tenant>`
- Kafka sends acknowledgement
- Producer continues without waiting for inbox or webhook delivery

**Kafka → osac-notifications**
- Controller consumes the CloudEvent
- Validates schema, tenant match, `source` → allowed `kind` grant map, and `type` pattern
- Rejects Kafka events whose `kind` is `announcement` (Admin API only)

**osac-notifications (controller)**
- Accepts the event and stores the intent in its own `notification_intent` table
- Commits the Kafka offset only after storing in the DB succeeds
- Calls fulfillment-service private APIs to create one inbox `Notification` per `data.recipient_ids` entry
  and, when `osacmatchsubscriptions` is enabled, it creates a delivery per matching subscription

**Inbox and webhook**
- Tenant Users manage inbox items through the public `Notifications` methods on fulfillment-service
- Matching subscriptions create deliveries in `pending` or `retained` state. See **Webhook delivery**

##### Notifications

**Event-driven notifications**
- Ingress is Kafka. Kind is one of `event`, `quota`, `meter`, or `billing`.
- The producer sets `data.recipient_ids`. Recipients are not discovered with RBAC.
- Stored as one inbox `Notification` per recipient, with `spec.event` set to `{id, source}` and `spec.recipient_id`.
- Managed with public `Notifications` methods. Optional webhook fan-out when `osacmatchsubscriptions` is true.
- If `data.resource` is set, List and Get may hide the item. See **RBAC / Tenancy**.
- Notification `spec` field is immutable after creation.

**Announcements**
- Ingress is the Admin public API only. Kafka rejects `announcement`.
- `spec.kind` is `announcement`. `spec.scope` is `tenant` or `platform`.
- **Tenant Admin** creates and deletes when `scope` is `tenant`.
- **Cloud Provider Admin** creates and deletes when `scope` is `platform`.
  The server sets `metadata.tenant` to the fixed system tenant `osac-system`
  so name uniqueness stays per tenant.
- One announcement object is enough for a UI banner. Per-user inbox rows are out of scope for v1. See **Alt E**.

##### Tenant Admin subscription

A Tenant Admin creates a subscription with a CEL filter and an HTTPS webhook URL. During creation, a `signing_secret`
is returned once and not stored in `spec` field. It is not returned from `List` or `Get` endpoints.
The Admin can list, get, update (including pause and unpause), and delete subscriptions in their tenant.
Delivery history uses `NotificationSubscriptionDeliveries`. See **Types and contracts** for the object shape.

**Matching an incoming event**

1. If `osacmatchsubscriptions` is false, skip webhook matching. Inbox fan-out may still run.
2. Load all non-deleted subscriptions for that tenant, including paused ones.
3. Build a CEL input from the event: `event_type` (CE `type`), `severity`, `kind`, `title`,
   `resource.kind`, `resource.id`, and tenant metadata.
4. Evaluate each subscription’s `filter`. A true result is a match.
5. For each match, create a `NotificationSubscriptionDelivery`. See **Persistence** for the unique key and
   **Webhook delivery** for `pending` versus `retained` and send behavior.

#### Webhook delivery

Each attempt uses a **30s** HTTP timeout. Attempts are recorded in delivery
history.

**Retry schedule:** Delays after a failed attempt are: 5s, 30s, 2m, 10m, 30m, 1h, then every 1h. Retry on
timeouts, connection errors, and **5xx**. Sustained failure means no successful delivery for that delivery
within **5 days** of its first failed attempt. Then mark the delivery `failed` and set subscription
`status.auto_paused`.

**Pause and retain:** A match against a paused or auto-paused subscription still creates a `retained` delivery. No
POST is sent until a Tenant Admin clears pause or auto-pause. Retained deliveries then move to `pending` and follow the
same retry rules until `delivered` or `failed`.

**SSRF policy:** Validate the URL at subscription create and before each POST.

- HTTPS only. Do not follow redirects.
- Resolve DNS, then connect only to addresses that pass the check. Re-validate resolved addresses immediately before
  connect (DNS rebinding).
- Block loopback, link-local, private (RFC1918), CGNAT `100.64.0.0/10`, cloud metadata (`169.254.169.254` and IPv6
  equivalents), and non-public multicast.

**Signing:** Authenticity uses the [Standard Webhooks](https://www.standardwebhooks.com/) HMAC scheme. Store
`signing_secret` encrypted at rest (or in the platform secret store). Every delivery attempt sends:

- `webhook-id`: stable id for the delivery (receivers dedupe retries)
- `webhook-timestamp`: unix time of this attempt
- `webhook-signature`: HMAC-SHA256 over `webhook-id.timestamp.body`, versioned as `v1,…`

Receivers reject bad signatures and timestamps outside skew. Treat `webhook-id` as an idempotency key. Payload bodies
must not contain credentials.

#### Failure Handling and Recovery

**Bad or unauthorized CloudEvent**
- The event fails **Validation (Kafka ingest)**
- Create no inbox or webhook fan-out
- Optionally write to a DLQ outside the consumer subscription
- Commit the Kafka offset after the rejection is recorded, or after a successful DLQ write when that is the durable
  rejection record

**Duplicate CloudEvent**
- The same `(tenant, source, id)` already exists in `notification_intent`
- Ignore it. Create no additional fan-out
- Commit the Kafka offset after the duplicate is ignored

**Unsafe webhook URL (subscription creation)**
- URL fails the **SSRF policy** in **Webhook delivery**
- Reject create with `InvalidArgument`. Store no subscription

**Cross-tenant API access**
- Caller asks for another tenant’s inbox, subscription, or delivery
- Return empty results or `NotFound` without leaking that the objects exist

**Resource visibility check unavailable**
- Inbox item has `data.resource` and the visibility check cannot complete
- Fail closed: omit or hide that item. Items without `data.resource` are unaffected

### API Extensions

**Public and private gRPC** on fulfillment-service:

|Service|Method|Purpose|Surface|
|---|---|---|---|
|`NotificationSubscriptions`|`Create`|Create a webhook subscription.|Public|
|`NotificationSubscriptions`|`List`|List subscriptions in the caller’s tenant.|Public|
|`NotificationSubscriptions`|`Get`|Get a subscription by id.|Public|
|`NotificationSubscriptions`|`Update`|Update subscription filter, webhook URL, or pause and unpause a subscription.|Public|
|`NotificationSubscriptions`|`Delete`|Delete a subscription and stop further deliveries.|Public|
|`NotificationSubscriptionDeliveries`|`Create`|Controller creates a delivery for a subscription match.|Private|
|`NotificationSubscriptionDeliveries`|`List`|List delivery history.|Public|
|`NotificationSubscriptionDeliveries`|`Get`|Get one delivery or attempt record.|Public|
|`NotificationSubscriptionDeliveries`|`Update`|Controller updates delivery status after send attempts.|Private|
|`Notifications`|`Create`|Tenant Admin or Cloud Provider Admin creates an announcement.|Public|
|`Notifications`|`Create`|Controller creates event-driven inbox items from Kafka fan-out.|Private|
|`Notifications`|`List`|List the caller’s event-driven notifications and visible announcements (tenant and platform).|Public|
|`Notifications`|`Get`|Get an event-driven notification or announcement by id.|Public|
|`Notifications`|`SetNotificationState`|Mark an event-driven inbox item read or unread. Not used for announcements.|Public|
|`Notifications`|`Delete`|Delete the caller’s event-driven notification, or remove an announcement per role rules below.|Public|

Controllers use the private methods. Tenants, admins, and the console use the public methods.

**List requests** take `offset`, `limit`, an optional `filter`, and an optional `order`. The `filter` field is a CEL
expression evaluated against each candidate object. Examples:

- Announcements for the UI banner: `this.spec.kind == "announcement"`
- Unread event-driven inbox items: `this.spec.kind != "announcement" && this.status.state == "unread"`
- Deliveries for one subscription: `this.spec.subscription.id == "sub-acme-quota-warn"`

### UX Alignment

New `@temp-api` shapes against the Notification public API. Console proxy routes to fulfillment-service.

### Implementation Details/Notes/Constraints

#### Component layout

```text
osac/
  fulfillment-service/    # Notification APIs + object tables; CE publisher
  osac-notifications/     # Kafka consumer, webhook workers, chart
  osac-metering/          # CE publisher
  osac-installer/         # notifications chart + topic lifecycle
```

`osac-notifications` is separate because the API path answers synchronous List/Get/Create requests, while the
controller does long-running asynchronous processing such as Kafka consume, dedupe, fan-out, webhook send and retry.
Keeping these separate allows the consumer and webhook workers scale and fail without affecting API latency or availability.

#### Types and contracts

This section covers producer ingest payloads and the public API resource shapes.

**Kafka ingest** for notifications uses CloudEvents 1.0 with JSON `data` and the `osactenant` extension.

|Attribute|Required|Meaning|
|---|---|---|
|`id`|yes|Idempotency key that is stable for this producer. Fan-out unique keys are in **Persistence**.|
|`source`|yes|Producing service identity. v1 values: `osac-fulfillment`, `osac-metering`, or `osac-billing`.|
|`type`|yes|`osac.notification.<kind>.<name>` (see validation below)|
|`time`|yes|Time of the event|
|`specversion`|yes|`1.0`|
|`osactenant`|yes|Tenant id. Must match the topic suffix.|
|`kind`|yes|Enum. `event` \| `meter` \| `billing` \| `quota` on Kafka. `announcement` only on Admin `Notifications.Create`.|
|`severity`|yes|Enum. `info` \| `warning` \| `critical`.|
|`osacmatchsubscriptions`|no|Whether to evaluate webhook subscriptions. Defaults to `true`.|
|`data`|yes|See below|

**Validation (Kafka ingest):** Reject the event if any check fails.

- Authorize with a grant map of `source` to allowed `kind` values. Each producer KafkaUser is assigned one `source`.
  Kafka ACLs still control which principals may write tenant topics.
- Reject `announcement`. Announcements use Admin `Notifications.Create` only.
- `type` must be `osac.notification.<kind>.<name>` where the `<kind>` segment equals `kind`.
  `<name>` is nonempty lowercase letters, digits, and underscores only.
- `osactenant` must match the topic suffix.

**`data` (v1) for Kafka CloudEvents:**

|Field|Required|Meaning|
|---|---|---|
|`title`|yes|Short text that summarizes the notification message.|
|`description`|no|Longer text with details of the message.|
|`recipient_ids`|no|Targeted inbox recipients (subject or user ids). Required for non-announcement inbox fan-out. Omit for announcements.|
|`resource`|no|Optional `{ "kind", "id" }` reference used for later RBAC visibility checks.|
|`details`|no|Optional kind-specific map (for example used and limit). Often empty for announcements.|

**Example of quota warning** → topic `osac.notifications.acme` (illustrative):

```json
{
  "specversion": "1.0",
  "id": "quota-warn-acme-compute-2026-11-07T18:00:00Z",
  "source": "osac-billing",
  "type": "osac.notification.quota.warning",
  "time": "2026-11-07T18:00:00Z",
  "datacontenttype": "application/json",
  "osactenant": "acme",
  "kind": "quota",
  "severity": "warning",
  "osacmatchsubscriptions": true,
  "data": {
    "title": "Compute vCPU quota at 90%",
    "description": "You have used 90 of 100 vCPUs.",
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

**Example of fulfillment resource notice** → topic `osac.notifications.acme` (explicit publish, not Watch).
`data.recipient_ids` is the requesting user’s subject id. `resource` is for later visibility checks.

```json
{
  "specversion": "1.0",
  "id": "fulfillment-ci-created-vm-42-2026-11-07T18:05:00Z",
  "source": "osac-fulfillment",
  "type": "osac.notification.event.resource_created",
  "time": "2026-11-07T18:05:00Z",
  "datacontenttype": "application/json",
  "osactenant": "acme",
  "kind": "event",
  "severity": "info",
  "osacmatchsubscriptions": false,
  "data": {
    "title": "Compute instance vm-42 created",
    "description": "Your compute instance vm-42 is ready.",
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

**Public API resources** use `id`, `metadata`, `spec`, and `status`. The server assigns `id` and system metadata
such as tenant. For subscriptions and announcements, the caller supplies `metadata.name` and `spec`.

**`Notification` protobuf**:

```protobuf
message Notification {
  string id = 1;
  Metadata metadata = 2;
  NotificationSpec spec = 3;
  NotificationStatus status = 4; // OUTPUT_ONLY
}

enum NotificationKind {
  NOTIFICATION_KIND_UNSPECIFIED = 0;
  NOTIFICATION_KIND_EVENT = 1;
  NOTIFICATION_KIND_QUOTA = 2;
  NOTIFICATION_KIND_METER = 3;
  NOTIFICATION_KIND_BILLING = 4;
  NOTIFICATION_KIND_ANNOUNCEMENT = 5;
}

enum NotificationSeverity {
  NOTIFICATION_SEVERITY_UNSPECIFIED = 0;
  NOTIFICATION_SEVERITY_INFO = 1;
  NOTIFICATION_SEVERITY_WARNING = 2;
  NOTIFICATION_SEVERITY_CRITICAL = 3;
}

enum NotificationScope {
  NOTIFICATION_SCOPE_UNSPECIFIED = 0;
  NOTIFICATION_SCOPE_TENANT = 1;
  NOTIFICATION_SCOPE_PLATFORM = 2;
}

message NotificationEventReference {
  string id = 1;
  string source = 2;
}

message NotificationResourceReference {
  string kind = 1;
  string id = 2;
}

message NotificationSpec {
  NotificationKind kind = 1;
  NotificationSeverity severity = 2;
  string type = 3; // e.g. osac.notification.event.resource_created
  NotificationEventReference event = 4;
  string recipient_id = 5;             
  NotificationScope scope = 6;         
  string title = 7;
  string description = 8;
  NotificationResourceReference resource = 9;
  map<string, string> details = 10;
}

enum NotificationState {
  NOTIFICATION_STATE_UNSPECIFIED = 0;
  NOTIFICATION_STATE_UNREAD = 1;
  NOTIFICATION_STATE_READ = 2;
}

message NotificationStatus {
  NotificationState state = 1;
}
```

**Notification state:** Dedicated `Notifications.SetNotificationState` with `id` and `state`.

```protobuf
rpc SetNotificationState(NotificationsSetNotificationStateRequest)
    returns (NotificationsSetNotificationStateResponse);

message NotificationsSetNotificationStateRequest {
  string id = 1;
  NotificationState state = 2;  // READ or UNREAD
}

message NotificationsSetNotificationStateResponse {
  Notification object = 1;
}
```

Examples below are shapes returned by `Get` or `List`.

**Example `NotificationSubscription`:**

```json
{
  "id": "sub-acme-quota-warn",
  "metadata": {
    "name": "quota-warnings",
    "tenant": "acme"
  },
  "spec": {
    "webhook_url": "https://hooks.acme.example/osac/quota",
    "filter": "kind == \"quota\" && severity in [\"warning\", \"critical\"]",
    "paused": false
  },
  "status": {
    "last_delivery_status": "delivered"
  }
}
```

**Example `NotificationSubscriptionDelivery`:**

Deliveries are system-created on a subscription match. The server assigns a new `id` and a distinct
`metadata.name` for each delivery.

```json
{
  "id": "del-acme-quota-warn-1",
  "metadata": {
    "name": "quota-warn-acme-compute-2026-11-07t18-00-00z",
    "tenant": "acme"
  },
  "spec": {
    "subscription": {
      "id": "sub-acme-quota-warn",
      "name": "quota-warnings"
    },
    "event": {
      "id": "quota-warn-acme-compute-2026-11-07T18:00:00Z",
      "source": "osac-billing"
    }
  },
  "status": {
    "state": "retained",
    "attempt_count": 0,
    "last_http_status": 0,
    "last_error": ""
  }
}
```

`spec.event` is `{id, source}` for the CloudEvent that produced this delivery.

`status.state` is the enum `NotificationSubscriptionDeliveryState`:

|Value|Meaning|
|---|---|
|`pending`|The delivery needs a webhook POST (first attempt or a scheduled retry). The send worker selects these rows.|
|`retained`|The subscription matched while paused (or auto-paused). No POST is sent until a Tenant Admin unpauses it.|
|`delivered`|The webhook accepted the delivery.|
|`failed`|Retries are exhausted, or the delivery was reported failed.|

**Example of `Notification` (inbox item):**

```json
{
  "id": "inbox-acme-user-123-1",
  "metadata": {
    "name": "inbox-acme-user-123-1",
    "tenant": "acme"
  },
  "spec": {
    "kind": "event",
    "severity": "info",
    "type": "osac.notification.event.resource_created",
    "event": {
      "id": "fulfillment-ci-created-vm-42-2026-11-07T18:05:00Z",
      "source": "osac-fulfillment"
    },
    "recipient_id": "user-123",
    "title": "Compute instance vm-42 created",
    "description": "Your compute instance vm-42 is ready.",
    "resource": {
      "kind": "compute_instance",
      "id": "vm-42"
    },
    "details": {
      "lifecycle": "created"
    }
  },
  "status": {
    "state": "unread"
  }
}
```

`status.state` for inbox items is an enum with v1 values `unread` and `read`. Announcements do not use this field.

**Example announcement `Notification`** (tenant scope):

```json
{
  "id": "announce-acme-maintenance-2026-11-10",
  "metadata": {
    "name": "maintenance-2026-11-10",
    "tenant": "acme"
  },
  "spec": {
    "kind": "announcement",
    "scope": "tenant",
    "severity": "warning",
    "type": "osac.notification.announcement.maintenance",
    "title": "Scheduled maintenance window",
    "description": "Control-plane maintenance is planned for 2026-11-10 02:00–04:00 UTC. API calls may fail during that window."
  },
  "status": {}
}
```

A platform announcement (by CPA admin) uses `spec.scope` set to `platform` and `metadata.tenant` set to `osac-system`.

#### Persistence

Fulfillment-service stores the Notification API objects with the same object and tenancy patterns as other OSAC
resources. The tables are:

- `notifications`: inbox items and announcements (`Notification`). Event-driven inbox rows are unique on
  `(metadata.tenant, spec.event.source, spec.event.id, spec.recipient_id)`.
- `notification_subscriptions`: Tenant Admin webhook subscriptions (`NotificationSubscription`). Unique on
  `(tenant, id)`.
- `notification_subscription_deliveries` and delivery attempts: webhook history under a subscription
  (`NotificationSubscriptionDelivery`), including retained matches. Unique on
  `(metadata.tenant, spec.subscription.id, spec.event.source, spec.event.id)`.

**osac-notifications** owns its processing tables:

- `notification_intent`: durable accept/fan-out intents written after consuming from Kafka.
  Unique on `(tenant, source, id)` (CloudEvent `osactenant`, `source`, `id`). After the intent is stored,
  the controller creates notifications and delivery API objects through fulfillment private APIs.

#### Installer

- Chart for osac-notifications
- On tenant create, provision `osac.notifications.<tenant>` (one partition) and optional
  `osac.notifications.dlq.<tenant>`
- Consumer group `osac-notifications` subscribes only to ingest topics with a regex that excludes DLQ topics (for
  example `^osac\.notifications\.[^.]+$`)
- Extend Strimzi `KafkaUser` ACLs (same pattern as `osac.events.*`) so producers can publish to
  `osac.notifications.` topics
- Wire the consumer grant map from **Validation (Kafka ingest)**

### Security Considerations

See **RBAC / Tenancy** for publish and API access rules.
See **Webhook delivery** for URL validation, signing, and payload rules.

### RBAC / Tenancy

**API roles**
- Tenant User: List/Get/Update/Delete on their own event-driven `Notifications`.
- Tenant Admin: Manage subscriptions and delivery history. Create/Delete announcements with `scope` `tenant` only.
- Cloud Provider Admin: Create/Delete announcements with `scope` `platform`. They can List and Get subscription
  and deliveries across tenants.
- Kafka publish auth is in **Validation (Kafka ingest)** and **Installer**.

**Recipient resolution vs resource visibility**

These are different jobs. Fulfillment RBAC answers whether this caller may see this object. It does not efficiently
answer who should receive an inbox notification.

|Concern|Who decides|Mechanism|
|---|---|---|
|**Who gets an inbox notification**|**Producer**|`data.recipient_ids`|
|**Who sees an announcement**|**`spec.scope`**|Set to either `tenant` or `platform`|
|**May this caller see this inbox item**|**fulfillment-service**|If `data.resource` is set, evaluate with the caller’s identity|
|**Webhook subscribers**|Tenant Admin subscriptions + CEL|Only when `osacmatchsubscriptions` is true|

### Risks and Mitigations

|Risk|Mitigation|
|---|---|
|Unauthorized or invalid Kafka publish, including `announcement`.|ACLs and grant map per **Validation (Kafka ingest)** and **Installer**. Cover boundaries in tests.|
|Redelivery creates duplicate inbox or delivery objects.|Unique keys in **Persistence**.|
|The consumer also reads DLQ topics.|Distinct DLQ names and a consumer regex that excludes them. See **Installer**.|
|A match during pause is lost.|`retained` deliveries per **Webhook delivery**.|
|SSRF via webhook URL.|URL checks in **Webhook delivery**.|
|Wrong role or forged tenant or `scope` on announcement Create.|Server-set tenant. Reject client `spec.source`. Role rules in **RBAC / Tenancy**.|
|Resource visibility check unavailable.|Fail closed for `data.resource` items.|

## Drawbacks

- Inbox List and Get still depend on fulfillment resource visibility when `data.resource` is set.
- Webhook delivery is an in-house sender (retries, SSRF, signing) rather than a hosted provider such as Svix.

## Alternatives

### Alt A — Host Notification APIs in osac-notifications

Rejected because fulfillment-service owns the public and private Notification APIs and object tables.

### Alt B — gRPC Submit as producer ingest (no Kafka)

Rejected because producers use Kafka CloudEvents only, matching the metering-style ingest path.

### Alt C — One Kafka topic per notification kind/type

Rejected because that explodes the topic count and `kind` field is part of CloudEvent attributes instead.

### Alt D — mTLS or SNS-style cert URLs for webhook authenticity

Rejected because Standard Webhooks HMAC covers authenticity and replay for tenant HTTPS URLs.

### Alt E — Per-user announcement expand

Rejected for v1 because one announcement object and a UI banner are enough (`scope` `tenant` or `platform`).

## Infrastructure Needed

- `osac-notifications` binary, image, chart, and CI
- Kafka topics and ACLs per **Installer**
- Notification API object tables in fulfillment-service PostgreSQL
- `notification_intent` table in the same PostgreSQL database
