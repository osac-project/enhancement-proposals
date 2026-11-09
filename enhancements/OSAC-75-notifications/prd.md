# Notifications

| Field     | Value                                                  |
|-----------|--------------------------------------------------------|
| Author(s) | ovishlit@redhat.com, jubah@redhat.com                  |
| Jira      | [OSAC-75](https://redhat.atlassian.net/browse/OSAC-75) |
| Date      | 2026-10-18                                             |

## Glossary

| Term             | Definition                                                                                                                       |
|------------------|----------------------------------------------------------------------------------------------------------------------------------|
| **Event**        | A point-in-time record of something worth telling.                                                                               |
| **Notification** | A message telling a user what happened, delivered via a channel.                                                                 |
| **Producer**     | A component that submits events into the notification system.                                                                    |
| **Subscription** | A stored filter over the tenant's events with a destination. Created and managed by Tenant Admins.                               |
| **Filter**       | A CEL expression that decides whether a given event is delivered to that subscription's destination. Validated at creation time. |
| **Channel**      | How a notification is delivered (for example inbox, webhook, email, Slack).                                                      |
| **Severity**     | How urgent an event is: info, warning, or critical.                                                                              |

## 1. Problem Statement

People and automation learn about changes by polling or by holding an Events `Watch` stream open. A person should not
need a long-lived client to learn that something they care about changed. Organization automation should not have to
poll either.

This PRD defines the notification mechanism. Producers (such as Fulfillment API) submit events. The system delivers
notifications on channels
such as inbox and webhook. Other Producers (for example Billing service) can adopt this mechanism.

A delivery failure never fails the flow that caused the event. A recorded event is delivered to matching subscription
destinations or reported as failed. By default, people receive a stored inbox message they can read or dismiss.
Recorded events are never silently lost on either path.

## 2. In Scope

- An API for producers to submit events into the notification system.
- Inbox channel (default for persons): Tenant Users and Tenant Admins receive stored messages and view them in a
  notification UI. Producers identify inbox recipients. Notification access follows RBAC. Inbox
  is in scope for first iteration and separate from subscription channels.
- Tenant's subscriptions managed by Tenant Admins: Each subscription has a CEL filter and a destination. Tenant scope
  and authorization are enforced server-side, independently of the CEL filter. A filter cannot select another tenant's
  events or bypass RBAC.
- Webhook as the only subscription channel in first iteration: Tenant Admins use webhooks. Email, SMS, Slack, and
  similar
  subscription destinations are deferred. Includes retries, failure reporting, delivery history, and pause after
  retries. Delivery is at-least-once. Duplicates are possible. Events carry a stable ID for receiver idempotency.
- Webhook endpoint safety: Delivery to unsafe or internal destinations is refused. Endpoints are also validated at
  delivery
  time. Address classes, DNS rebinding, and redirect handling are left to design.
- Severity on every event: Subscriptions may filter by it.
- Tenant isolation: A tenant cannot see another tenant's notifications or subscriptions.
- Producer authentication and authorization during event submission.

## 3. Out of Scope

- Alarms and alerts: Configurable alarm rules and stateful alerts (firing, reminders, silence, or disable) are not
  part of the first iteration.
- Platform pipeline health: Operator-facing faults such as dead-letter queues or failed components stay on the
  monitoring stack.
- Tenant User–managed subscriptions: Tenant Users do not create filters or webhook endpoints. Personal preference
  surfaces may come later.
- Email, SMS, Slack, and other subscription channels beyond webhook are deferred for the first iteration. Inbox remains
  in scope.
- Custom templates, digest or batched email.
- Real-time alerting on audit events (OSAC-63).
- Forwarding to SIEM or external collectors. The audit design owns export.

## 4. User Stories

### Tenant User

- As a Tenant User, I want to receive inbox notifications when I am an intended recipient, so that I
  do not need a custom client or webhook.
- As a Tenant User, I want to see unread notifications in the UI and open them, so that I can act on them.

### Tenant Admin

- As a Tenant Admin, I want to create, list, update, and delete my tenant's subscriptions, each with a filter and a
  webhook destination, so that our systems receive the events that matter to us.
- As a Tenant Admin, I want to filter subscriptions by severity, so that urgent and routine events reach the right
  destination.
- As a Tenant Admin, I want to see which subscription deliveries failed and why, so that I can fix my endpoint or my
  filter.
- As a Tenant Admin, I want to pause or unpause a subscription, so that I can stop or resume webhook delivery after
  fixing my endpoint.
- As a Tenant Admin, I want receivers to tell a genuine webhook notification from a forged one, so that our automation
  can trust what it acts on.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to see tenant's webhook delivery health per tenant, so that I can tell a tenant
  their endpoint has been failing.

## 5. Acceptance Criteria

- [ ] A producer can submit an event to the notification system
- [ ] When producers submit events, the system authenticates the producer and authorizes the target tenant and event
  type. Unauthenticated or unauthorized submits are rejected
- [ ] A Tenant Admin creates, lists, and deletes a tenant's subscription with a filter and a webhook destination. An
  invalid filter is rejected at time of creation
- [ ] A Tenant User cannot create, update, or delete a tenant's subscriptions
- [ ] When a producer submits an event with one or more recipient IDs, each recipient receives an inbox notification.
  Recipient identity comes from the event
- [ ] A Tenant User opens the notification UI and sees unread notifications, then can open them
- [ ] When a Tenant User opens the inbox, only notifications they are still allowed to see (per current RBAC) are shown.
  If their access to a resource was revoked after the event was stored, that notification is not shown.
- [ ] A tenant's subscription filtered by severity receives only matching events on its webhook
- [ ] Tenant scope and authorization are enforced server-side for subscriptions, independently of the CEL filter. A
  filter cannot select another tenant's events or bypass RBAC
- [ ] Webhook delivery is at-least-once. Duplicates may occur. Each event has a stable ID so receivers can be
  idempotent. Ordering across subscriptions is not guaranteed
- [ ] A webhook receiver can verify that a notification came from the platform
- [ ] A failing webhook can be retried and the failure should appear in the delivery history
- [ ] After the endpoint recovers or the Tenant Admin unpauses the subscription, retained events are delivered or
  reported failed per retry rules (TBD in design)
- [ ] Unsubscribing a tenant's subscription stops deliveries for it
- [ ] A tenant cannot see another tenant's notifications or subscriptions
- [ ] Delivery to unsafe or internal webhook destinations is refused. Endpoints are validated at delivery time
- [ ] With the webhook endpoint down for a certain period (TBD in design), producer submit and other business flows
  succeed. Every event that matched a tenant's subscriptions in that period is delivered after recovery or unpause, or
  reported failed per retry rules (TBD in design), even if retries were exhausted and the subscription was paused
  during the outage

## 6. Assumptions

- Webhook endpoints come from tenants or the provider and are reachable from the platform.
- Tenant's subscription management reuses the tenant's existing identity and RBAC.
- Inbox notification visibility reuses the tenant's existing identity and resource RBAC when the user reads the inbox.
- The console hosts the notification UI for inbox messages.
- How retained webhook backlog is stored and replayed after pause or recovery is left to design.
- Outage retention window, retry count, and backoff are TBD and will be defined in the design.
- Exact unsafe-address classes, DNS rebinding, and redirect policy for webhooks are left to design.

## 7. Dependencies

- **Console/UX.** Hosts the notification UI for inbox messages.
- **Producer event-submission contract.** Producers (for example fulfillment, quota, billing) submit
  events into the notification system. They authenticate as producers and may only target tenants and event types they
  are authorized for. Matching inbox recipients and tenant subscriptions receive the event without each producer
  implementing delivery.

## 8. Risks

### 8.1 Webhook endpoints

- **Owner:** notifications design.
- **Risk:** The platform delivers by making HTTP requests to URLs that Tenant Admins choose. A tenant admin can aim
  the platform at addresses it should never request, such as the Kubernetes API or a database reachable from the
  cluster.
- **Mitigation:** The design must refuse delivery to internal addresses. It must validate an endpoint before delivery
  starts. Receivers must be able to verify a notification's origin.

### 8.2 Payload sensitivity on webhooks

- **Owner:** notifications design.
- **Risk:** Webhook destinations are tenant-chosen URLs. Notification payloads may include details about resources or
  failures. Sensitive material sent to a tenant endpoint has no channel-confidentiality guarantee in this release.
- **Mitigation:** The design must define what payloads may contain. Secrets and credentials must stay out of webhook
  bodies. Tenants must treat webhook endpoints as trusted receivers of tenant data.
