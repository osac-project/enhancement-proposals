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
`BareMetalInstance` (BMI), and a three-state requested behavior resolved at
creation. Fulfillment stores `DISABLED`, `ENABLED_PREFERRED`, or
`ENABLED_REQUIRED` and projects the same value to the bare-metal fulfillment
operator (BMFO). BMFO admits each enabled mode according to a provider-owned
capability and maps `DISABLED` to UEFI without the Secure Boot option.

Current providers hardcode request-only support: preferred-enabled requests
proceed, while required-enabled requests fail before allocation. A provider may
claim fail-closed support only after provider-specific qualification.

## 2. Goals and Non-Goals

### 2.1 Goals

- Resolve and persist intention and requested behavior at BMI create.
- Reject every declaration blocker for `required` before host allocation.
- Project the typed, immutable requested behavior directly to BMFO.
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

## 4. Design

### 4.1 Resolution and Data Flow

Fulfillment resolves the declarations after locking the selected type and
image, then stores the canonical intention and requested behavior in the BMI
create transaction.

| Intention | Hardware and image declarations | `secure_boot_requested` |
|---|---|---|
| `REQUIRED` | Both true | `ENABLED_REQUIRED` |
| `REQUIRED` | Either false or absent | Create rejected |
| `PREFERRED` or omitted | Both true | `ENABLED_PREFERRED` |
| `PREFERRED` or omitted | Either false or absent | `DISABLED` |
| `DISABLED` | Any | `DISABLED` |

The flow is BMI create → resolution → BMFO projection → backend admission →
AAP provider mapping. The caller's origin is irrelevant. Existing CaaS worker
creates omit the intention and therefore take the `PREFERRED` rows through the
same BMI path.

### 4.2 API and BMFO Projection

| Message and field | Type | Contract |
|---|---|---|
| `BareMetalHardwareSpec.uefi_secure_boot_supported` | `optional bool` | Informative, mutable declaration on the selected `BareMetalInstanceType`; absence means unsupported. |
| `DiskImageSpec.uefi_secure_boot_compatible` | `optional bool` | Optional; mutable by authorized image owners; absence means incompatible. |
| `BareMetalInstanceSpec.secure_boot` | `BareMetalInstanceSecureBootIntention` | `REQUIRED`, `PREFERRED`, or `DISABLED`; `UNSPECIFIED` becomes `PREFERRED`; immutable. |
| `BareMetalInstanceStatus.secure_boot_requested` | `BareMetalInstanceSecureBootRequested` | Server-set once to `DISABLED`, `ENABLED_PREFERRED`, or `ENABLED_REQUIRED`; output-only and not observed firmware state. |

Both enums live in `baremetal_instance_type.proto` with the BMI spec and status,
accept only defined values, and use constant (intention) and fixed-once-set
(requested behavior) metering.

BMFO receives the same three values in optional immutable
`spec.secureBootRequested`. The Fulfillment reconciler reads only
`status.secure_boot_requested` and converts it directly; it does not resolve
the intention again. Absence preserves legacy CR behavior.

Legacy CRs retain their existing projected configuration; no persistence
migration is required. Proto, public API, Go, BMFO CRD, and Helm outputs are
regenerated from their sources.

### 4.3 Validation and Lifecycle

`PrivateBareMetalInstancesServer.prepareCreate` canonicalizes omission to
`PREFERRED`, reads both declarations with absence treated as false, applies
§4.1, and persists the result. A blocked `REQUIRED` request returns
`InvalidArgument` with `INCOMPATIBLE_SECURE_BOOT_DECLARATIONS`, listing every
blocker in hardware-then-image order with resource identity and corrector role.
It does not search for alternatives. No BMI or allocation is created.

New DiskImages may omit the declaration, which is treated as incompatible.
Authorized image owners may add or change the declaration through
DiskImage Update. Existing BMI or catalog-item references do not block these
updates; unlike architecture removal, no reverse-dependency guard applies.
Legacy absence survives unrelated updates and remains incompatible until an
owner adds a declaration. Hardware and image declaration updates affect only
later BMIs because each existing BMI retains its creation-time requested
behavior.

BMI intention and requested behavior are immutable. The value is never
recomputed, and BMFO status synchronization excludes
`status.secure_boot_requested` from its update mask. Delete behavior is
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
- Get/describe: declarations, intention, and requested behavior.

### 4.4 Backend Admission and Mapping

Each provider implementation hardcodes one capability; no user or installer
configuration is added. The capability is one internal enum with a conservative
zero value; exact Go types and names are implementation choices. One possible
shape:

```go
type ProviderCapabilities struct {
    SecureBoot SecureBootSupport
}

type SecureBootSupport uint8

const (
    SecureBootSupportUnsupported SecureBootSupport = iota
    SecureBootSupportRequestOnly
    SecureBootSupportFailClosed
)
```

Current Metal3, BCM, NetBox, and OpenStack paths return `RequestOnly`.

| Requested behavior | `Unsupported` | `RequestOnly` | `FailClosed` |
|---|---|---|---|
| `DISABLED` | Request UEFI without Secure Boot | Same | Same |
| `ENABLED_PREFERRED` | Fail before allocation with an unsupported-Secure-Boot error | Issue the Secure Boot request | Issue the Secure Boot request |
| `ENABLED_REQUIRED` | Fail before allocation with an unsupported-Secure-Boot error | Fail before allocation | Issue the Secure Boot request and require fail-closed provider behavior |

An explicit provider error fails either enabled request without a disabled
retry. A request-only provider may silently continue without Secure Boot for
`ENABLED_PREFERRED`; `secure_boot_requested` remains a request, not a firmware
observation. BMFO uses an exhaustive capability switch, not ordinal comparison.
The exact error message is implementation-defined — including reusing the
provider's own unsupported error — as long as the failure is terminal,
requester-visible, and identifies Secure Boot as the reason.

Both enabled values map to BMH `spec.bootMode: UEFISecureBoot` or fresh Ironic
`instance_info.capabilities.secure_boot: "true"`. `DISABLED` and legacy absence
map to BMH `UEFI` or omit the Ironic capability after undeploy clears prior
instance information.

A provider path, including NICo, may return `FailClosed` only after it confirms
Secure Boot before tenant-image power-on, fails closed on every non-success
outcome, and passes the E9/E10 real-boundary gate.

### 4.5 Failures, Security, and Operations

| Failure | Result |
|---|---|
| Declaration blocker for `required` | Create fails before persistence or allocation with every blocker. |
| Provider is `Unsupported` for an enabled request | Terminal failure before allocation with an unsupported-Secure-Boot error; no provider call. |
| `RequestOnly` provider receives `ENABLED_REQUIRED` | Terminal `SecureBootEnforcementUnsupported` before allocation; no provider call. |
| Enabled provider request returns an error | Existing provisioning failure; no ordinary-UEFI fallback. |
| Declaration changes or reconcile retries | Existing BMIs retain their stored requested behavior; later creates use the updated declaration. |

No roles, permissions, credentials, BMC access, metrics, alerts, or tracing are
added. Existing resource visibility and tenant isolation apply. Resolution adds
no query and constant storage; admission is one in-memory capability check.

## 5. Interface Changes

| ID | Contract |
|---|---|
| IC-1 | API/admin CLI expose mutable hardware support; absence is unsupported. |
| IC-2 | API/CLI expose optional image declarations; DiskImage Update lets authorized owners add or change the declaration without a BMI/catalog reference guard. |
| IC-3 | API/BMI create CLI expose immutable intention; omission stores `PREFERRED`. |
| IC-4 | API/CLI expose immutable three-state `secure_boot_requested`; it is not observed firmware state. |
| IC-5 | Blocked create returns the exact actionable declaration error before allocation. |
| IC-7 | BMFO receives the same optional immutable three-state request; absence preserves legacy behavior. |
| IC-8 | A hardcoded provider capability enum gates preferred and required admission. |
| IC-9 | AAP maps the three requested values to provider-native requests. |

IC-6, the former CaaS-specific interface, remains retired. CaaS uses IC-3,
IC-4, and IC-7–IC-9 through the shared BMI contract.

## 6. Compatibility, Risks, and Alternatives

- Existing types, images, BMIs, and CRs are not backfilled or reprovisioned.
  Authorized owners may add declarations to existing types and images; existing
  BMIs retain their stored requested behavior.
- Old clients may omit the DiskImage declaration; omission remains incompatible.
- Current backends accept preferred-enabled requests but reject required-enabled
  requests. The OpenStack/Ironic fail-closed dependency is tracked by
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

E1–E8 cover the current implementation, including required admission on a
request-only adapter. E9 and E10 qualify providers that claim fail-closed
support. E11 validates the current deployed preferred-enabled success path;
E12 is the deferred deployed required-failure journey on a qualified provider.
Planning approval is not execution evidence.

---

## Provenance

Authored: draft @ design 0.15.0 - cd88680, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf (169 behind origin/main)
Final: respond @ design 0.15.0 - 760cf64, workspace feat/OSAC-3035-UEFI-Secure-Boot @ a3ec34fbf (306 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"760cf64","source_repo":"a3ec34fbf","source_repo_branch":"feat/OSAC-3035-UEFI-Secure-Boot","commits_behind_main":306,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
