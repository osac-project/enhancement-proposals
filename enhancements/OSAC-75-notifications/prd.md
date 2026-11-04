# Notifications

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | ovishlit@redhat.com  |
| Jira        | [OSAC-75](https://redhat.atlassian.net/browse/OSAC-75) |
| Date        | 2026-10-18           |

## Glossary

| Term | Definition |
|------|-----------|
| **Notification** | A message telling a Tenant User/Admin what happened, delivered in-app and/or via a subscription provider. |
| **Notification event** | The durable record of something worth telling. One event can feed in-app messages and/or match several subscriptions. |
| **Condition** | A state that stays true over time, such as "still over the quota warning threshold". A condition raises one notification and triggers reminders at a bounded rate (TBD). |
| **Producer** | A component that creates notification events such as quota, billing health, announcements, and resource lifecycle state. |
| **Subscription** | A stored filter over the tenant's events with a destination. A subscription is created and managed by tenant admins. |
| **Filter** | A CEL expression that decides whether a given notification event is delivered to that subscription's destination. Validated at creation time. This is the same language `Watch` uses. |
| **Provider** | A delivery implementation for subscriptions. The webhook is the first provider. Email, Slack and others follow later. |
| **Severity** | How urgent an event is: info, warning, or critical. Subscriptions may filter by it while in-app messages may display it. |
| **Delivery** | For an org subscription, one notification is sent to one matched subscription (including retries). For in-app (the default), a message is stored until the user reads or dismisses it. |

## 1. Problem Statement

Tenants learn about their own resources by polling. A tenant user refreshes the console to find out whether their VM
finished provisioning or failed. A tenant admin discovers that usage stopped being reported when the invoice is wrong.
The Events API offers `Watch`, but holding a stream open is for machines. A person should not need a long-lived client
to know
their resource (e.g. cluster) is ready, and an organization's automation should not have to poll either.

Features wait on this. Quota warning thresholds (OSAC-4500) are blocked by the missing notifications capability.

A delivery failure never fails the flow that caused the notification. A recorded notification event is
delivered to matching subscriptions' destinations (for example webhooks) or reported as failed.
By default, users receive a stored message they can read or dismiss. Recorded events are never silently
lost on either path.

## 2. In Scope

- Tenant-facing notification: resource lifecycle, quota rejection, quota warning
  exceeded, billing health for the tenant, and platform announcements.
- Condition behavior: When a persistent problem starts (for example usage crosses and stays at a quota warning),
  send one notification. If it is still true later, send reminders at a bounded rate (TBD). Stop when the problem ends.
- In-app notifications (default): Tenant Users and Tenant Admins receive stored messages for events
  that concern them, and can view them in a notification UI.
- Subscriptions with CEL filters, the same filter language `Watch` uses, shaped to share the subscription
  concept with explicit event subscriptions. Subscriptions are managed by Tenant Admins.
- Severity on every notification event. Subscriptions may filter by it.
- Webhook delivery for Tenant Admin–managed subscription endpoints, including retries, failure reporting, delivery
  history, and pause after exhausted retries.
- Tenant isolation: a tenant cannot see another tenant's in-app notifications or subscriptions.

## 3. Out of Scope

- Platform pipeline health: For a non-empty dead-letter queue, a component that refused to start, a quarantined
  change, clock skew; the operator causes these and the operator fixes them. They are alerts on the monitoring stack,
  where the person who can act already watches. Telling a tenant about a fault they cannot fix helps nobody. The one
  exception is billing health. When a tenant's usage has gone unreported for hours, the tenant admin is told, because
  their invoice is what ends up wrong.
- Tenant User subscriptions: Tenant Users do not create CEL filters or webhook endpoints. Personal
  opt-in preference surfaces may come later.
- Email, SMS, and chat channels for persons or org managed subscription providers. Email, PagerDuty, and
  similar may become providers later. Per-severity provider routing may follow.
- Custom templates, and digest or batched email.
- Real-time alerting on audit events (OSAC-63).
- Forwarding to SIEM or external collectors. The audit design owns export.

## 4. User Stories

### Tenant User

- As a Tenant User, I want to be notified when a resource I created is ready or has failed, with the failure
  reason, so that I stop polling the console.
- As a Tenant User, I want to be notified when my request is rejected by quota, with the dimension, the limit,
  and the current usage, so that I know what to change.
- As a Tenant User, I want my notifications limited to resources and actions I am allowed to see, so that
  notifications respect my visibility.
- As a Tenant User, I want to see unread notifications in the UI and open them, so that I can act without a
  custom client or webhook.

### Tenant Admin

- As a Tenant Admin, I want to create, list, and delete my organization's subscriptions, each with a filter and a
  webhook endpoint, so that our systems hear about what matters to us.
- As a Tenant Admin, I want to filter subscriptions by severity, so that urgent events and routine events reach the
  right destination.
- As a Tenant Admin, I want to be notified when usage my organization is billed for has gone unreported, with
  reminders at a bounded rate (TBD). So that I can raise it before the invoice is wrong without
  being flooded.
- As a Tenant Admin, I want to be notified when usage crosses a quota warning threshold, with reminders at a bounded
  rate (TBD), so that I can act before hard failures without being flooded.
- As a Tenant Admin, I want to see which org subscription deliveries failed and why, so that I can fix my endpoint or
  my filter.
- As a Tenant Admin, I want receivers to tell a genuine webhook notification from a forged one, so that our automation
  can trust what it acts on.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to send an announcement to affected tenants, so that planned maintenance or
  degradation reaches everyone it concerns.
- As a Cloud Provider Admin, I want to see org webhook delivery health per tenant, so that I can tell a tenant their
  endpoint has been failing.

## 5. Acceptance Criteria

- [ ] A Tenant Admin creates, lists, and deletes an org subscription with a filter and a webhook endpoint. An invalid
  filter is rejected at subscribe time
- [ ] A Tenant User cannot create, update, or delete org subscriptions
- [ ] When a resource fails provisioning, a notification is available to the appropriate person (s) in the
  console with the failure reason
- [ ] When a request is rejected by quota, a notification is available to the requesting user with the
  dimension, the limit, and the current usage
- [ ] Usage crossing a quota warning threshold produces a notification for the Tenant Admin. This unblocks
  OSAC-4500
- [ ] When a tenant's usage has been unreported for the configured window, the Tenant Admin receives a
  notification
- [ ] A Tenant User opens the notification UI and sees unread notifications, then can open them
- [ ] A Tenant User does not receive notifications for resources they are not allowed to see
- [ ] An org subscription filtered by severity receives only matching events
- [ ] A receiver can verify that a notification came from the platform
- [ ] A failing webhook retries with backoff. After the bounded number of attempts (TBD), the failure appears in the
  delivery history and the subscription is paused. Pausing the subscription does not drop undelivered events.
- [ ] After the endpoint recovers or the Tenant Admin unpauses the subscription, retained events are delivered (or
  reported failed per retry rules)
- [ ] While the quota-warning-exceeded condition remains true, the tenant gets one opening notification plus
  reminders at the bounded rate (TBD) and not one notification per duplicate threshold or usage sample
- [ ] While the billing-health (usage unreported) condition remains true, the Tenant Admin gets one opening
  notification plus reminders at the bounded rate (TBD) until reporting resumes
- [ ] Unsubscribing an org subscription stops deliveries for it
- [ ] A tenant cannot see another tenant's notifications or org subscriptions
- [ ] With the webhook endpoint down for an hour, provisioning flows succeed, and every notification event that matched
  org subscriptions in that hour is delivered after recovery or unpause (or reported failed per retry rules), even if
  retries were exhausted and the subscription was paused during the outage
- [ ] Delivery to internal cluster and service addresses is refused

## 6. Assumptions

- Webhook endpoints come from tenants or the provider and are reachable from the platform.
- Org subscription management reuses the tenant's existing identity and RBAC.
- In-app notification visibility reuses the tenant's existing identity and resource RBAC.
- The console hosts the notification UI for in-app messages.
- How retained webhook backlog is stored and replayed after pause or recovery is left to design.

## 7. Dependencies

- **Durable event pipeline** (OSAC-983, OSAC-1161). Provides durable, ordered per-tenant event delivery for matching
  and fan-out.
- **Quota** (OSAC-4500). Emits the threshold and rejection events that notifications deliver.
- **Metering** (OSAC-5753). Exposes per-tenant usage reporting freshness used for billing-health evaluation.
- **Billing-health evaluation** (design follows). Reads metering's delivery state and writes a notification event
  when a tenant's usage has been unreported for the configured window.
- **Event subscriptions** (OSAC-5659). Use the same CEL filter and subscription shape.
  OSAC-5659 delivers matches on a stream; OSAC-75 delivers matches to a webhook.
- **Console/UX.** Hosts the notification UI for in-app messages.

## 8. Risks

### 8.1 Webhook endpoints

- **Owner:** notifications design.
- **Risk:** The platform delivers by making HTTP requests to URLs that Tenant Admins choose. A tenant admin can aim
  the platform at addresses it should never request, such as the Kubernetes API or a database reachable from the
  cluster.
- **Mitigation:** The design must refuse delivery to internal addresses, validate an endpoint before delivery
  starts, and let receivers verify a notification's origin.

### 8.2 Payload sensitivity on webhooks

- **Owner:** notifications design.
- **Risk:** Webhook destinations are tenant-chosen URLs. Notification payloads may include details about resources,
  quota, or failures. If a payload ever carried secrets or other sensitive material, it would be sent to whatever
  endpoint the Tenant Admin configured, with no channel-confidentiality guarantee in this release.
- **Mitigation:** The design must define what notification payloads may contain, keep secrets and credentials out of
  webhook bodies, and document that tenants treat webhook endpoints as trusted receivers of tenant data.

## 9. Decisions

### D-1. Tenant-facing only

Notifications tell tenants about their resources, their quota, their billing, and the platform as it affects them.
Platform pipeline health rides the monitoring stack, where the operator who can act already watches.

### D-2. Two paths: in-app for people, webhooks for org automation

Persons (Tenant Users and Tenant Admins acting as themselves) receive **in-app notifications** in the console.
Organizations receive automation callbacks through Tenant Admin–managed subscriptions (CEL filter + webhook).
Email and other personal or alternate org providers are deferred. Severity remains in the event contract so
subscription routing can use it when more providers arrive.

### D-3. Org subscriptions are not the personal inbox

A subscription is an org-scoped filter plus a webhook destination, managed only by Tenant Admins. Explicit event
subscriptions (OSAC-5659) share that filter language for stream consumption. In-app inbox delivery is identity-bound
and is not modeled as a Tenant User–created subscription in the first iteration.

### D-4. Same events, two consumers

A single notification event may both create in-app messages for the relevant people and match org webhook
subscriptions. How matching and fan-out are implemented is left to design.
