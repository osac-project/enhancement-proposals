---
title: tenant-external-billing-id-ux
authors:
  - ekim@redhat.com
creation-date: 2026-11-23
last-updated: 2026-11-23
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-6161
prd: "prd.md"
prototype: "https://heyethankim.github.io/osac-design-lab/provider/workspace?nav=administration-organizations&hub=1&topic=external-billing-id&design=2&action=register-tenant"
see-also:
  - "/enhancements/OSAC-6161-tenant-external-billing-id/prd.md"
  - "/enhancements/OSAC-6161-tenant-external-billing-id/design.md"
  - "/enhancements/OSAC-6161-tenant-external-billing-id/clarifications.md"
replaces:
superseded-by:
---

# Tenant external billing identity — UX Design (Design 2)

Conceptual UX for **associating an OSAC tenant with its identity in an
external billing system**
([OSAC-6161](https://redhat.atlassian.net/browse/OSAC-6161)), captured from
**Design Lab → External billing ID → Design 2**.

Design 2 is the **no integrated billing system** path (Option B): when the
cluster has no configured billing integration such as M360, Provider Admin
does not see Link now / Set up later account-linking cards. The Billing step
is a single optional **External billing ID** field (for example a Zuora-style
account ID). After registration, the ID is **mutable** and edited **inline
on tenant Overview** — not by reopening the onboarding wizard.

**Prototype (developers):**

- [Register tenant → Billing (Design 2)](https://heyethankim.github.io/osac-design-lab/provider/workspace?nav=administration-organizations&hub=1&topic=external-billing-id&design=2&action=register-tenant)
- [Tenants list (Design 2)](https://heyethankim.github.io/osac-design-lab/provider/workspace?nav=administration-organizations&hub=1&topic=external-billing-id&design=2)
- [Tenant detail — harborline-capital](https://heyethankim.github.io/osac-design-lab/provider/workspace?nav=administration-organizations&hub=1&topic=external-billing-id&design=2&tenant=org-harborline-capital)

Requirements: [prd.md](prd.md). Backend / API design: [design.md](design.md).
Clarifications: [clarifications.md](clarifications.md).

> **Scope note.** The locked Feature MVP stores and reads
> `external_billing_id` on the **private** Tenant API and stamps it into
> metering heartbeats ([design.md](design.md)). Console UI is a future
> increment in the PRD. This document records the **Design 2** console
> concept so Provider Admin association and observability stay aligned with
> that field when UI ships.

## Product decisions (this release / Design 2)

- **No integrated billing → external ID only.** When no integrated billing
  system is configured, Design 2 hides Link now / Set up later and shows only
  an optional **External billing ID** on the Billing step. Lede: *Enter an
  optional external billing ID for this tenant. You can leave it blank and add
  or update it later from the tenant overview.*
- **Opaque, optional identifier.** Placeholder example `A00078421`. The value
  is not validated against the external system at onboarding
  ([prd.md](prd.md) Out of Scope). Max length matches the private API (256).
- **Provider-only.** Capture and display under Provider Admin →
  **Administration → Tenants**. Tenant Admins and Tenant Users never see the
  field ([prd.md](prd.md)).
- **Simplified post-create flow.** Register uses **General → Billing →
  Review**. After create, Provider Admin does **not** return to the wizard to
  set or change the ID.
- **Inline edit on Overview (mutable).** Tenant detail Overview is the only
  place to add or update the ID after registration: empty → **Add external
  billing ID**; set → value + pencil. Save/cancel stay on the page. The field
  remains editable at any time (no read-only / immutable lock). Changes apply
  going forward in metering (FR-4).
- **List and cards are read-only.** Tenants list (table and cards) show the
  value or **—** for scanability. They do not offer Add / Edit controls that
  open the wizard or inline edit.
- **Review shows the ID.** Review lists **External billing ID** with the
  entered value (or empty / — when blank). No separate billing-mode label.
- **Tenant setup checklist.** Tenant setup tracks **External billing ID** as
  a checklist step and updates when the Overview inline edit saves.

---

## Journey overview

```text
Cloud Provider Admin opens Administration → Tenants
        │
        ▼
Register tenant (Design 2) — General → Billing → Review
        │
        ▼
Billing: optional External billing ID only
  (no Link now / Set up later / M360 picker)
  Lede points to tenant overview for later add/update
        │
        ▼
Review → Register tenant
        │
        ▼
Tenants list / cards: read-only External billing ID (value or —)
        │
        ▼
Tenant Overview: mutable inline edit
  • unset → Add external billing ID
  • set → value + pencil → save / cancel in place
  (no wizard round-trip)
```

---

## 1. Register tenant — Billing (Design 2)

**What this screen is for.** Let a Cloud Provider Admin record an optional
external billing account identifier at tenant registration when the
deployment has no integrated billing platform to link against
([prd.md](prd.md) Cloud Provider Admin stories).

**Explanation.** On **Register tenant → Billing**, Design 2 leads with *Enter
an optional external billing ID for this tenant. You can leave it blank and
add or update it later from the tenant overview.* A single **External billing
ID** text field (placeholder `e.g. A00078421`) accepts the opaque ID. There
are no timing cards and no M360 account picker. **Next** advances to Review;
leaving the field empty is valid. Post-registration changes happen on
Overview, not by reopening this step.

<img src="assets/01-register-tenant-billing-design-2.png" alt="Register tenant Billing step — Design 2 external billing ID only" width="720" />

---

## 2. Register tenant — Review

**What this screen is for.** Confirm tenant identity and the external billing
association before the tenant is created.

**Explanation.** **Review** summarizes tenant name, primary email domain,
company logo, and **External billing ID** (for example `A00078421`). Primary
action is **Register tenant**.

<img src="assets/02-register-tenant-review-design-2.png" alt="Register tenant Review with external billing ID" width="720" />

---

## 3. Tenants list — External billing ID column (read-only)

**What this screen is for.** Let Provider Admin scan which tenants already
carry an external billing identifier and spot gaps before or after
onboarding.

**Explanation.** **Administration → Tenants** lede: *Register tenants and map
billing accounts.* List view columns include **External billing ID**. Rows
show the stored value (for example `HLC-ENT-55108`) or **—** when unset.
Cards mirror the same read-only display. There is no Add / Edit link on the
list; open the tenant and use Overview inline edit to change the ID. Search
and filters stay on the Tenants page; list view remains the canonical scan
surface for Design 2 observability.

<img src="assets/03-tenants-list-external-billing-id-design-2.png" alt="Tenants list with read-only External billing ID column" width="720" />

---

## 4. Tenant detail — Overview (inline edit)

**What this screen is for.** Confirm the stored external billing identity on
an existing tenant and add or update it without leaving the page.

**Explanation.** Tenant Overview includes **External billing ID**. When the
value is set, it appears in `<code>` with a pencil control that opens
field-specific inline edit (text input, save, cancel; Escape cancels, Enter
saves). When unset, **Add external billing ID** starts the same inline
editor. Saving updates the Overview, Tenant setup checklist, and list/card
displays. Header **Actions** / **Edit** are not required for this field —
Design 2 does not send the admin back into the Billing wizard to mutate the
ID. The identifier stays mutable for the life of the tenant.

<img src="assets/04-tenant-detail-external-billing-id-design-2.png" alt="Tenant detail Overview with mutable inline External billing ID" width="720" />

<img src="assets/05-tenant-detail-external-billing-id-inline-edit-design-2.png" alt="Tenant detail Overview — External billing ID inline edit active" width="720" />

---

## Notes vs Design 1 and the API design

| Topic | Design 2 (this UX) | Design 1 / other |
| --- | --- | --- |
| Integrated billing present? | Assumed **no** — hide Link now / Set up later | Design 1 keeps timing cards; External billing ID hidden when M360 / integrated platform is linked |
| Post-create edit | **Inline on Overview only** (mutable anytime) | Design 1 uses integrated Billing configuration; no Design 2-style inline ID when integrated |
| List / cards | Read-only value or **—** | Scan + Billing account column when integrated |
| Field semantics | Optional opaque `external_billing_id` | Same field; [design.md](design.md) private API + heartbeat stamp |
| Console in Feature MVP | Conceptual / future UI | Locked MVP is private API (+ `osac create -f` via schema) per D2 |
| Tenant-facing UI | None | None |

Align shipping console copy with **External billing ID**, keep the ID
provider-only, preserve optional empty as a first-class state, and treat
Overview inline edit as the supported path for later association or
correction so tenants are not blocked at registration.
