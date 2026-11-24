# BMaaS UEFI Secure Boot Enforcement — Design

| Field | Value |
|---|---|
| Author(s) | Matthieu Bernardin |
| Jira | [OSAC-3035](https://redhat.atlassian.net/browse/OSAC-3035) |
| PRD | [prd.md](prd.md) |
| Date | 2026-11-23 |

## 1. Overview

This design adds Secure Boot declarations to `BareMetalInstanceType` and
`DiskImage`, an immutable `required`/`preferred`/`disabled` intention to
`BareMetalInstance` (BMI), and an effective behavior resolved at creation.
Fulfillment stores that decision and projects either disabled best effort or
enabled fail closed to the bare-metal fulfillment operator (BMFO).

Current delivery adds declarations, create-time resolution, projection, and
fail-closed admission. No current backend advertises enabled support; provider-
owned confirmation remains a future qualification boundary. [Research]

## 2. Goals and Non-Goals

### 2.1 Goals

- Resolve and persist intention and effective behavior at BMI create.
- Reject every declaration blocker for `required` before host allocation.
- Project a typed, immutable, server-controlled execution mode to BMFO.
- Keep provider mapping and future fail-closed qualification behind BMFO's
  inventory boundary.

### 2.2 Non-Goals

- Add CaaS resource fields, service-level overrides, or CaaS-specific status.
- Implement OSAC-owned Redfish/IPMI confirmation, BMH detachment, or a
  validation-image workflow.
- Expose observed firmware state or confirmation status, or implement an
  OSAC-owned force-off operation.
- Verify declarations, image signatures, or keys; add attestation, quarantine,
  automatic failure attribution, or Secure Boot-specific notifications.
- Support VM Secure Boot, tracked by
  [OSAC-7205](https://redhat.atlassian.net/browse/OSAC-7205).

## 3. Background

Metal3 requests `BareMetalHost.spec.bootMode: UEFISecureBoot`; direct
OpenStack/Ironic sets `instance_info.capabilities.secure_boot: "true"`.
Neither proves fail-closed enforcement: sampled Ironic versions may warn and
continue when the Redfish `SecureBoot` resource is absent, while BMH status,
`HostFirmwareSettings`, and cached Ironic state are not fresh confirmation.
Ordinary UEFI or an absent capability is likewise not a portable force-off.
[Research]

## 4. Design

### 4.1 Resolution and Data Flow

Fulfillment resolves the declarations after locking the selected type and
image, then stores the canonical intention and effective behavior in the BMI
create transaction.

| Intention | Hardware and image declarations | Effective behavior | BMFO mode |
|---|---|---|---|
| `REQUIRED` | Both true | `ENABLED` | Enabled, fail closed |
| `REQUIRED` | Either false or absent | Create rejected | No projection |
| `PREFERRED` or omitted | Both true | `ENABLED` | Enabled, fail closed |
| `PREFERRED` or omitted | Either false or absent | `DISABLED` | Disabled, best effort |
| `DISABLED` | Any | `DISABLED` | Disabled, best effort |

The flow is BMI create → resolution → BMFO projection → backend admission →
AAP provider mapping. The caller's origin is irrelevant. Existing CaaS worker
creates omit the intention and therefore take the `PREFERRED` rows through the
same BMI path. [User]

### 4.2 API and BMFO Projection

| Message and field | Type | Contract |
|---|---|---|
| `BareMetalHardwareSpec.uefi_secure_boot_supported` | `optional bool` | Informative, mutable provider declaration; absence means unsupported. |
| `DiskImageSpec.uefi_secure_boot_compatible` | `optional bool` | Optional; mutable by authorized image owners; absence means incompatible. |
| `BareMetalInstanceSpec.secure_boot` | `BareMetalInstanceSecureBootIntention` | `REQUIRED`, `PREFERRED`, or `DISABLED`; `UNSPECIFIED` becomes `PREFERRED`; immutable. |
| `BareMetalInstanceStatus.secure_boot_effective` | `BareMetalInstanceSecureBootEffective` | Server-set once to `ENABLED` or `DISABLED`; output-only. |

Both enums live in `baremetal_instance_type.proto` with the BMI spec and status,
accept only defined values, and use constant (intention) and fixed-once-set
(effective behavior) metering.

BMFO receives an optional, typed, immutable, server-controlled representation
of the two modes in §4.1. Field names and nesting are implementation choices;
the representation need not duplicate intention. Absence means disabled best
effort for legacy CRs. Every new BMI projects a complete mode.

The mode joins BMFO's provisioning desired-config hash. Legacy absence retains
the exact pre-feature hash; network-attachment and IP-discovery hashes do not
change. Proto, public API, Go, BMFO CRD, and Helm outputs are regenerated from
their sources; generic persistence needs no migration.

### 4.3 Validation and Lifecycle

`PrivateBareMetalInstancesServer.prepareCreate` canonicalizes omission to
`PREFERRED`, reads both declarations with absence treated as false, applies
§4.1, and persists the result. A blocked `REQUIRED` request returns
`InvalidArgument` with `INCOMPATIBLE_SECURE_BOOT_DECLARATIONS`, listing every
blocker in hardware-then-image order with resource identity and corrector role.
It does not search for alternatives. No BMI or allocation is created.
[Locked: D11, D12]

New DiskImages may omit the declaration, which is treated as incompatible.
Authorized image owners may add or change the declaration through
DiskImage Update. Existing BMI or catalog-item references do not block these
updates; unlike architecture removal, no reverse-dependency guard applies.
Legacy absence survives unrelated updates and remains incompatible until an
owner adds a declaration. Hardware and image declaration updates affect only
later BMIs because each existing BMI retains its creation-time effective
behavior. [Locked: D18]

BMI intention and BMFO mode are immutable. Effective behavior is never
recomputed, and BMFO status synchronization excludes
`status.secure_boot_effective` from its update mask. Delete behavior is
unchanged.

CLI changes are limited to:

- BMI create: `--secure-boot required|preferred|disabled` (default `preferred`).
- DiskImage create: optional
  `--uefi-secure-boot-compatible=<true|false>`; omission creates no declaration
  and is interpreted as incompatible.
- DiskImage update: explicit `true` or `false` sets the declaration; omission
  preserves the stored declaration.
- BareMetalInstanceType create/update:
  `--uefi-secure-boot-supported=<true|false>`.
- Get/describe: declarations, intention, and effective behavior.

### 4.4 Backend Admission and Mapping

Before host allocation, BMFO consults the selected provider path's capability to
perform Secure Boot enforcement. An effective-enabled request is admitted only
when that path indicates support for provider-owned final enablement and fresh
confirmation before tenant-image power-on. If the capability is absent, false,
or cannot be evaluated, BMFO sets phase `Failed` and `Allocated=False` with
reason `SecureBootEnforcementUnsupported`; it creates no allocation, external
host ID, or AAP job and never retries as disabled.

The implementation task decides whether this capability is represented by one
shared contract or separate inventory and management capability contracts. One
possible implementation shape is illustrative only:

```go
type ServerCapabilities struct {
    SecureBootEnforcementSupported bool
}
```

The example does not prescribe ownership, naming, or composition. Every current
native Metal3, BCM, NetBox, and OpenStack provider path reports unsupported.

| Mode | Native Metal3 / BCM / NetBox | Direct OpenStack/Ironic |
|---|---|---|
| Either enabled mode | Set BMH `spec.bootMode: UEFISecureBoot`. | Add `capabilities: {secure_boot: "true"}` to fresh `instance_info`. |
| Disabled or legacy absence | Set BMH `spec.bootMode: UEFI`. | Omit `secure_boot` after undeploy clears prior `instance_info`. |

For effective `disabled`, this UEFI/no-option mapping is the complete contract;
the effective value does not claim independently observed firmware state.

A future provider path may advertise support only when it performs bounded,
provider-owned final enablement and fresh confirmation before tenant-image
power-on, fails closed for unsupported, absent, stale, contradictory, error, or
timeout results, and passes the E9/E10 real-boundary gate.

### 4.5 Failures, Security, and Operations

| Failure | Result |
|---|---|
| Declaration blocker for `required` | Create fails before persistence or allocation with every blocker. |
| Current backend receives an enabled mode | Terminal `SecureBootEnforcementUnsupported`; curated fulfillment error; no provider call. |
| Enabled provider request fails | Existing provisioning failure; no ordinary-UEFI fallback. |
| Declaration changes or reconcile retries | Existing BMIs retain their stored effective behavior and projected mode; later creates use the updated declaration. |

No roles, permissions, credentials, BMC access, metrics, alerts, or tracing are
added. Existing resource visibility and tenant isolation apply. Resolution adds
no query and constant storage; admission is one in-memory capability check.

## 5. Interface Changes

| ID | Contract |
|---|---|
| IC-1 | API/admin CLI expose mutable hardware support; absence is unsupported. |
| IC-2 | API/CLI expose optional image declarations; DiskImage Update lets authorized owners add or change the declaration without a BMI/catalog reference guard. |
| IC-3 | API/BMI create CLI expose immutable intention; omission stores `PREFERRED`. |
| IC-4 | API/CLI expose immutable declaration-derived effective behavior. |
| IC-5 | Blocked create returns the exact actionable declaration error before allocation. |
| IC-7 | BMFO receives the optional immutable enabled/disabled projection; absence preserves legacy behavior and hash. |
| IC-8 | Inventory capability gates fail-closed before allocation with terminal unsupported behavior. |
| IC-9 | AAP maps enabled and disabled modes to provider-native requests. |

IC-6, the former CaaS-specific interface, remains retired. CaaS uses IC-3,
IC-4, and IC-7–IC-9 through the shared BMI contract.

## 6. Compatibility, Risks, and Alternatives

- Existing types, images, BMIs, and CRs are not backfilled or reprovisioned.
  Authorized owners may add declarations to existing types and images; existing
  BMIs retain their stored effective behavior.
- Old clients may omit the DiskImage declaration; omission remains incompatible.
- All current backends reject enabled requests; the default-on success journey
  is deferred until a backend supports enabled requests. The OpenStack/Ironic
  fail-closed dependency is tracked by
  [RFE-10199](https://redhat.atlassian.net/browse/RFE-10199); other provider
  paths require provider-specific qualification.
- OSAC does not support in-place upgrades. Mixed versions are unsupported;
  generated BMFO CRDs, BMFO, and the AAP role must roll out before Fulfillment
  accepts the new fields.
- No installer setting or UI surface is added. API/CLI and BMaaS documentation
  must explain declaration ownership, defaulting, and current backend limits.
- OSAC-owned Redfish confirmation was rejected because it duplicates provider
  credentials, locking, and power ownership and retains time-of-check gaps.
- `templateParameters` were rejected because users can override them.
- Explicit force-off was rejected because absent/false Ironic capability is not
  a portable disable operation.

## 7. Test Plan

The companion [test plan](testplan.md) covers all ten PRD requirements and all
eight active interfaces. FR-5 and the CaaS branch of FR-7
map to the shared BMI defaulting, visibility, projection, and enforcement cases;
there is no separate CaaS behavior or changed CaaS boundary to duplicate.

E1–E7 cover the current implementation. E8 is the current deployed fail-closed
admission journey using an adapter that reports unsupported. E9 and E10 are
conditional provider qualification gates; one must pass before its provider
path may advertise Secure Boot enforcement support. E11 is the subsequent
deployed provider-confirmation and success validation and remains deferred
until a qualified path exists.
Planning approval is not execution evidence.

---

## Provenance

Authored: draft @ design 0.15.0 - cd88680, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf (169 behind origin/main)
Final: respond @ design 0.15.0 - ceab343, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf (253 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"ceab343","source_repo":"a3ec34fbf","source_repo_branch":"feat/OSAC-3035-UEFI-Secure-Boot","commits_behind_main":253,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
