# Notifications

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | ovishlit@redhat.com  |
| Jira        | [OSAC-75](https://redhat.atlassian.net/browse/OSAC-75) |
| Date        | 2026-10-18           |

## Glossary

| Term | Definition |
|------|-----------|
| **Notification** | A message telling a tenant what happened, delivered once the request that caused it finishes. |
| **Notification event** | The durable record of something worth telling. One event can match several subscriptions. |
| **Condition** | A state that persists, such as a threshold staying exceeded. One condition raises one notification. |
| **Producer** | A component that writes notification events: quota, billing health, announcements. |
| **Subscription** | A stored filter over the tenant's events, plus where matching notifications go. |
| **Filter** | A CEL expression over an event's fields, validated at subscribe time. The same language Watch uses. |
| **Provider** | A delivery implementation. The webhook is the first provider; email and others follow. |
| **Severity** | How urgent an event is: info, warning, or critical. Subscriptions may filter by it. |
| **Delivery** | Handing one notification to one matched subscription, including its retries. |

## 1. Problem Statement

Tenants learn about their own resources by polling. A tenant user refreshes the console to find out whether their VM
finished provisioning or failed. A tenant admin discovers that usage stopped being reported when the invoice is wrong.
The API offers Watch, but holding a stream open is for machines. A person should not need a client to know their
cluster is ready.

Features wait on this. Quota warning thresholds (OSAC-4500) are blocked by the missing notifications API.

Emission must be cheap for the producer. A VM creation succeeds regardless of whether any notification has been
delivered. Recording a notification costs the producer almost nothing, and delivery happens later, in the
background. A delivery failure never fails the flow that caused the notification, and a recorded notification is
delivered or reported as failed, never silently lost.

## 2. In Scope

- The machinery is built once. Adding a new event type is a documentation change plus a topic write permission,
  with no code change.
- Tenant-facing notifications: resource lifecycle, quota conditions, billing health for the tenant, platform
  announcements.
- Subscriptions with CEL filters, the same filter language Watch uses, shaped to share the subscription concept with
  explicit event subscriptions (OSAC-5659).
- Webhook delivery, with endpoints managed by Tenant Admins.
- Severity on every notification event. Subscriptions may filter by it.
- Delivery retries, failure reporting, and a delivery history.

## 3. Out of Scope

- **Platform pipeline health.** A non-empty dead-letter queue, a component that refused to start, a quarantined
  change, clock skew: the operator causes these and the operator fixes them. They are alerts on the monitoring stack,
  where the person who can act already watches. Telling a tenant about a fault they cannot fix helps nobody. The one
  exception is billing health. When a tenant's usage has gone unreported for hours, the tenant admin is told, because
  their invoice is what ends up wrong.
- Email, SMS, and chat channels. The webhook is the only provider in the first release, and it is the generic escape
  hatch: a customer's own app is a webhook endpoint. Email, PagerDuty, and similar become built-in providers later,
  and per-severity provider routing follows.
- Custom templates, and digest or batched email.
- Real-time alerting on audit events (OSAC-63).
- Forwarding to SIEM or external collectors. The audit design owns export.
- A notification center UI. The API comes first.

## 4. User Stories

### Tenant User

- As a Tenant User, I want to be notified when a resource I created is ready or has failed, with the failure reason,
  so that I stop polling the console.
- As a Tenant User, I want a quota rejection to notify me with the dimension, the limit, and the current usage,
  so that I know what to change.
- As a Tenant User, I want to subscribe only to resources I can see, so that notifications respect my visibility.

### Tenant Admin

- As a Tenant Admin, I want to manage my organization's subscriptions, each with a filter and a webhook endpoint,
  so that our systems hear about what matters to us.
- As a Tenant Admin, I want to filter subscriptions by severity, so that urgent events and routine events reach the
  right place.
- As a Tenant Admin, I want to be notified when usage my organization is billed for has gone unreported, so that I
  can raise it before the invoice is wrong.
- As a Tenant Admin, I want to see which notifications failed to deliver and why, so that I can fix my endpoint or
  my filter.
- As a Tenant Admin, I want to be able to tell a genuine notification from a forged one, so that our automation can
  trust what it acts on.
- As a Tenant Admin, I want a condition that persists to raise one notification with reminders at a bounded rate,
  so that an ongoing problem does not flood our endpoint.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to send an announcement to affected tenants, so that planned maintenance or
  degradation reaches everyone it concerns.
- As a Cloud Provider Admin, I want to see delivery health per tenant, so that I can tell a tenant their endpoint
  has been failing.

## 5. Acceptance Criteria

- [ ] A Tenant Admin creates, lists, and deletes a subscription with a filter and a webhook endpoint. An invalid
  filter is rejected at subscribe time
- [ ] A resource that fails provisioning notifies subscribed users with the failure reason
- [ ] A request rejected by quota notifies the requesting user with the dimension, the limit, and the current usage
- [ ] Usage crossing a quota warning threshold notifies the subscribed Tenant Admin. This unblocks OSAC-4500
- [ ] When a tenant's usage has been unreported for the configured window, the Tenant Admin is notified
- [ ] A subscription filtered by severity receives only matching events
- [ ] A receiver can verify that a notification came from the platform
- [ ] A failing webhook retries with backoff. After the bounded number of attempts, the failure appears in the
  delivery history and the subscription is paused
- [ ] A condition that persists raises one notification plus reminders at the bounded rate, however many events
  trigger it
- [ ] Unsubscribing stops deliveries
- [ ] A tenant cannot see another tenant's notifications or subscriptions
- [ ] With the webhook endpoint down for an hour, provisioning flows succeed, and every notification written in that
  hour is delivered after recovery
- [ ] Delivery to internal cluster and service addresses is refused
- [ ] Adding an event type for a new producer is a documentation change plus a topic write permission, with no
  code change

## 6. Assumptions

- Webhook endpoints come from tenants or the provider and are reachable from the platform.
- Subscription management reuses the tenant's existing identity and RBAC.

## 7. Dependencies

- **Durable event pipeline** (OSAC-983, OSAC-1161). Provides the topics: the tenant's event topic the matcher
  reads, and the notification topics producers write.
- **Quota** (OSAC-4500). Emits the threshold and rejection events that notifications delivers.
- **Metering** (OSAC-5753). Exposes per-tenant delivery state: dead-letter depth, age of the oldest unhandled
  record, heartbeat lag. The billing-health condition is evaluated from it.
- **Billing-health evaluation** (design follows). Reads metering's delivery state and writes a notification event
  when a tenant's usage has been unreported for the configured window.
- **Event subscriptions** (OSAC-5659). Shares the subscription concept: a stored CEL filter, consumed either as a
  stream or as a delivery. The filter language and subscription shape stay aligned.

## 8. Risks

### 8.1 Webhook endpoints

- **Owner:** notifications design.
- **Risk:** The platform delivers by making HTTP requests to URLs that Tenant Admins choose. A tenant admin can aim
  the platform at addresses it should never request, such as the Kubernetes API or a database reachable from the
  cluster.
- **Mitigation:** The design must refuse delivery to internal addresses, validate an endpoint before delivery
  starts, and let receivers verify a notification's origin.

## 9. Decisions

### D-1. Tenant-facing only

Notifications tell tenants about their resources, their quota, their billing, and the platform as it affects them.
Platform pipeline health rides the monitoring stack, where the operator who can act already watches.

### D-2. Webhook first, providers later

The webhook is the first provider and the generic escape hatch. A customer's own app is a webhook endpoint. Email,
PagerDuty, and similar become built-in providers without changing producers, and per-severity provider routing
follows. Severity is in the contract from day one, so subscriptions can be interpreted per severity when routing
arrives.

### D-3. One subscription concept

A subscription is a stored filter plus a destination. Explicit event subscriptions (OSAC-5659) consume the same
filters as streams. One filter language, one subscription shape, several ways to consume the matches.
