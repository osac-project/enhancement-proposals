# Tenant Onboarding and Offboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-08 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS integration) |
| Status | Revised draft — dedicated pre-created SVM model; team agreement pending |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but lack equivalent NetApp ONTAP onboarding/offboarding over Fibre Channel
(FC). Providers need to connect administrator-prepared storage virtual machines
(SVMs) to OSAC tenants, expose their tiers and see whether that connection is
usable. The Developer Preview needs this configuration for its shared VMaaS
workflow without making OSAC responsible for array networking or driver installation.

## In Scope

- Register one ONTAP backend and one or more FC block tiers through the existing
  UI, CLI, and API.
- Bind each tenant to its dedicated, pre-created SVM and enable its assigned tiers.
- Offboard OSAC-managed tenant storage using the established lifecycle safeguards.

Infrastructure administrators prepare SVMs, management/FC LIFs, credentials,
native tier policies and the vendor driver using documented manual steps.
OSAC validates and adopts this configuration. Tenants receive no ONTAP
management credentials.
Offboarding follows
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md),
[OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and their data/dependency guards; completion confirms removal of OSAC-managed
configuration and the departing tenant's OSAC access, while preserving
administrator-created SVMs, LIFs and credential sources.

### Required verification

Onboard two tenants and verify distinct SVMs and management LIFs, correct tier
bindings/native policies, and FC access limited to authorized consumers. FC
requires no separate tenant IP data LIF; its target LIFs follow ONTAP's FC
model. Failed onboarding remains not ready and retries avoid duplicate resources.
Offboarding respects data/dependency guards, removes OSAC-owned configuration and
access, preserves prepared infrastructure and the other tenant's storage, and
rejects unsafe reassignment. QE validates the resulting configuration
through the shared VMaaS-over-FC flow; VM disk lifecycle implementation is a
separate dependency below. Setup and acceptance may be performed manually.

## Workflows

### 1. Installation and management prerequisites

Before OSAC deployment, the Cloud Infrastructure Admin prepares the connected
OpenShift Virtualization cluster, worker FC connectivity, zoning and multipath.
Every worker eligible to run a VM or disk-import workload must have supported FC
access; guest VMs consume virtual disks. The administrator installs complete
native Trident, including its required Kubernetes resources/OpenShift permissions,
and supplies the bootstrap storage needed to start OSAC. Bootstrap storage is
independent of tenant classes created later. The tested driver version, namespace
and configuration are documented.

Before backend registration, the administrator supplies reachable, trusted ONTAP
cluster-management HTTPS access and a service account permitted to discover the
intended SVMs, management/FC interfaces and native policies. This account needs
no SVM/LIF creation or deletion privileges. Management access does not prove FC I/O.

### 2. Backend and tier registration

The Cloud Provider Admin:

1. Stores the management password through the existing protected Secret workflow
   and registers the ONTAP provider, cluster endpoint and credentials through
   UI/CLI/API. No aggregate, IPspace, subnet, node or port inputs are required.
2. Receives a read-only access-validation result. An unreachable endpoint,
   untrusted certificate, invalid credentials or insufficient discovery
   permissions returns an actionable error; the backend is not accepted as ready.
   Success stores the backend and returns its identifier. Registration creates
   no tenant SVM, LIF, native backend or StorageClass.
3. Registers BLOCK tiers referencing the backend, with an optional native
   per-volume IOPS ceiling and the existing encryption setting. Unsupported
   protocol/performance inputs are rejected rather than silently translated.

Registration is independent of tenant onboarding. A ready backend or active tier
is catalog configuration, not a claim that a tenant can use FC.

### 3. Manual preparation for a named tenant

Before creating the OSAC tenant, the Cloud Provider Admin chooses its name and
shares that name, the returned backend identifier and tier requirements with the
Cloud Infrastructure Admin. The infrastructure administrator:

1. Prepares exactly one dedicated SVM using the assignment convention below,
   with usable ONTAP capacity and no previous tenant's workload data/active assignment.
2. Prepares its distinct management LIF, FCP service, SVM-scoped FC target LIFs
   and zoning. Physical FC ports may serve several SVMs; each logical target LIF
   belongs to its SVM. FC needs no separate tenant IP data LIF.
3. Creates an SVM-scoped account with Trident's required volume-management
   permissions and supplies its protected credential Secret. Discovering the
   SVM or its endpoint cannot recover its password.
4. For each capped tier, creates an SVM-owned, non-shared native QoS policy
   matching the tier ceiling. Enables the required array encryption capability
   when requested. An uncapped tier needs no additional cap. Policy creation
   requires the appropriate cluster-administrator privileges;
   [native Trident settings](https://docs.netapp.com/us-en/trident-2510/trident-use/ontap-san-examples.html)
   and [ONTAP policy creation](https://docs.netapp.com/us-en/ontap-cli-9171/qos-policy-group-create.html)
   define the provider prerequisites.

Preparation is deterministic for a known tenant. OSAC does not choose an arbitrary
free SVM; administrators prepare another dedicated SVM for another tenant.

### 4. Tenant onboarding

The Cloud Provider Admin creates the tenant through the normal OSAC workflow.
OSAC resolves its backend/tiers, discovers the assigned SVM and validates its
identity, management endpoint, FCP configuration, native policies and SVM account.
A missing SVM, conflicting assignment, previous-tenant data or missing/unusable
credentials leaves NetApp storage unavailable with an actionable reason.

OSAC records the assignment against the current immutable tenant identity and
configures a tenant-specific native Trident backend and tier bindings. Storage
is ready only after that configuration succeeds. Failed onboarding identifies
the affected stage; correcting preparation and retrying reuses the assignment
and completed work. Matching names alone do not authorize adoption.

Ready bindings are supplied to the shared VMaaS workflow. Users select tiers
without array settings or credentials; VM disk provisioning/lifecycle remains
OSAC-6037's responsibility. OSAC creates no SVM/LIF or zoning during onboarding.

### 5. Offboarding and manual release

After the established data/dependency guards permit cleanup, OSAC removes its
tenant tier bindings and native backend configuration and invalidates the
departing tenant's OSAC access. Failure remains visible and does not report
completion. Administrator-created SVMs, LIFs, policies and account/credential
sources are preserved and reported as retained.

Retained infrastructure is not automatically returned to a pool or rebound when
the same tenant name is reused. Before a new tenant identity can adopt it, the
infrastructure administrator verifies data cleanup, revokes/replaces old account
access and supplies newly authorized credentials. OSAC validates the new
preparation and rejects stale ownership/credential generations. Manual release
does not bypass active-data guards; its protected handoff is proposed in OQ-3.

## Configuration and API Contract

The proposed preview contract makes administrator input explicit; existing
VAST/Pure contracts remain compatible.

| Surface | Proposed contract / schema change |
|---|---|
| StorageBackend | Reuse `spec.provider="ontap"`, `spec.endpoint` and `spec.credentials`, including existing password Secret references; description remains optional. No new `spec.ontap` provisioning recipe or physical-topology fields. Add read-only ONTAP access validation during registration. |
| StorageTier | Reuse `spec.protocol=BLOCK`, backend references and `encryption_enabled`. Add optional typed `BackendAssociation.provider_qos` oneof with `OntapAssociationConfig ontap = 5`; that config's `int64 max_iops = 1` is nonnegative and permitted only for an ONTAP backend. API JSON is `spec.backends[].ontap.maxIops`. Positive values are per-volume ceilings; zero/unset adds no cap. Existing read/write bandwidth fields must be zero for ONTAP. Public tier shape is unchanged. |
| Tenant input | Existing tenant creation input is unchanged. Backend identifier plus planned tenant name selects prepared storage; no SVM/LIF/account parameters are exposed to tenant users. |
| Prepared credentials | Administrator creates a protected credential Secret in the configured native-driver namespace, with SVM username/password and assignment metadata. No new Secret type or API resource is required. This is separate from the backend registration password Secret. |
| Status | Extend private `TenantConditionType` with `TENANT_CONDITION_TYPE_STORAGE_BACKEND_READY = 3` and `TENANT_CONDITION_TYPE_CLUSTER_STORAGE_READY = 4`, reflecting existing operator storage stages through the existing `TenantStatus.conditions` field. Cloud Provider Admins receive readiness/reasons through UI/CLI/API; IDP synchronization alone does not mean storage is ready. |
| Operator → AAP | Preserve backend-ID-keyed `storage_backend_connections` with discovery endpoint/credentials and the existing tenant name/immutable identity. Extend tier definitions with `encryption_enabled` and `qos_limits.provider_config.max_iops` as a numeric value. The dispatcher passes these generic containers to the ONTAP role; it does not interpret provider-specific fields. |
| Output | Ready tenant/tier bindings use the existing `{name, tier}` contract, identifying native StorageClass and tier names. Array endpoints/credentials and physical topology are excluded from tenant-facing output. |

The ONTAP AAP role discovers/claims the prepared SVM and reads its protected
credential Secret through the existing privileged cluster connection. It then
configures native Trident to reference those SVM credentials; the cluster
discovery account is never substituted for them. Backend adoption and native
backend/class configuration retain the existing two onboarding stages. Their
success and failure feed the storage conditions above; passwords stay out of
logs and tenant-facing status. No backend `provider_config` input is needed
when physical preparation is supplied entirely through this convention.

### Assignment and credential handoff

For this proposal, `assignment_key` is the first 16 lowercase SHA-256 hex
characters of `backend_id + "|" + tenant_name`; `tier_key` uses the tier name.
`tier_key` is likewise the first 16 lowercase SHA-256 hex characters. Both can
be calculated before tenant creation. Documentation provides the
calculation and resulting names:

- SVM: `osac-<assignment_key>-svm`.
- Credential Secret: `osac-<assignment_key>-credentials`, in the configured native
  Trident namespace, with `username` and `password` entries.
- Capped-tier policy: `osac-<assignment_key>-<tier_key>-qos`.

The administrator records `osac.openshift.io/storage-backend` (full backend ID),
`osac.openshift.io/tenant` (planned tenant name),
`osac.openshift.io/storage-resource-id` (SVM UUID) and
`osac.openshift.io/storage-assignment-state=available` annotations on the Secret.
OSAC validates these values before adoption, records
`osac.openshift.io/storage-tenant-uid` and marks the assignment `claimed`.
After successful offboarding, state becomes `retained` and the previous identity
remains recorded. Retry accepts the same claimed identity; another identity is
rejected. The short naming key is not ownership proof.

Manual release requires administrator-verified data cleanup and account-access
replacement, then a newly prepared credential Secret generation marked
`available` without the old claim. OSAC keeps the previous retained assignment
until the replacement preparation is verified; deleting a Secret alone is not
release. The administrator-created Secret is preserved during offboarding.
This concrete handoff remains proposed for review (OQ-3/OQ-4).

### Example: one array, two tenants

An administrator registers `backend-id` and BLOCK tier `fast` with a 5,000 IOPS
ceiling. Before creating `tenant-a`, administrators prepare its conventionally
named SVM, management/FC LIFs, matching non-shared policy and credential Secret.
Onboarding validates that preparation and makes `fast` available for VM disks.
For `tenant-b`, administrators prepare another SVM, management LIF, policy and
credential Secret. Both tenants share the registered cluster endpoint but use
separate SVM endpoints/accounts. Offboarding A removes A's OSAC bindings and
retains its prepared SVM for manual release while B remains usable.

## Out of Scope

- Shared VM/Volume lifecycle implementation, independent VaaS volumes and dynamic attach/detach.
- OSAC CSI integration changes or removal, and vendor-driver installation automation.
- CaaS and BMaaS storage integration, and Enclave.
- Multi-cluster or multi-backend preview deployment profiles.
- FC switch configuration, zoning, host/HBA preparation, and dedicated fabric diagnostics.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers; supported in-place OSAC upgrades.
- Performance benchmarking or custom QoS beyond native provider capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.
- Automatic SVM/LIF creation/deletion, arbitrary free-SVM allocation and automatic
  sanitization/recycling; accounts and native policies are administrator-prepared.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want multiple NetApp block tiers with native
  performance policies on the registered backend, so that tenants can select
  my storage offerings.
- As a Cloud Provider Admin, I want OSAC to bind each tenant to its prepared
  dedicated SVM, so that I can enable storage without automating array networking.
- As a Cloud Provider Admin, I want missing preparation and failed onboarding to
  identify the required correction, so that I can retry for the same tenant safely.
- As a Cloud Provider Admin, I want tenant offboarding to report completion or
  safe, actionable failures under existing dependency guards, so that I can
  coordinate cleanup and safe release of preserved administrator-owned resources.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want documented SVM, credential, policy and
  driver prerequisites, so that I can prepare tenant storage before OSAC adoption.
- As a Cloud Infrastructure Admin, I want unsafe SVM reassignment to be rejected,
  so that I can finish data/access cleanup before preparing it for a new tenant.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my assigned NetApp tiers to become
  available after onboarding, so that I can use the existing VMaaS workflow
  without handling ONTAP management credentials.

## Assumptions

- One existing, connected OpenShift cluster with OpenShift Virtualization hosts
  OSAC and tenant VMs. The preview profile operates without the OSAC CSI driver;
  existing CSI integrations remain intact.
- Infrastructure administrators supply workers with supported FC access, prepared
  zoning, management connectivity, and the required vendor storage deployment.
  These prerequisites use documented setup steps.
- The team accepts dedicated pre-created SVM adoption for this draft. Deterministic
  assignment, administrator-supplied SVM credentials and native policies are the
  proposed baseline; exact handoff/release validation needs agreement (OQ-3/OQ-4).
- Native policies and requested encryption capabilities can be validated with
  the supplied service-account permissions on the tested ONTAP platform (OQ-2/OQ-4).
- Management access does not prove FC connectivity; infrastructure owners prepare
  tenant targets and zoning before onboarding.
- Existing central credential handling and lifecycle safeguards apply.

## Dependencies

- Existing Core/secrets support, tenant storage status feedback and protected
  configuration/onboarding handoffs.
- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) owns the shared
  VM/Volume lifecycle, including disk creation, ownership and cleanup. This
  feature supplies tenant/tier storage configuration; the consumption handoff
  needs agreement with that workstream (OQ-1).
- QE and infrastructure owners supply an FC-capable array and connected workers.
  Access details have been handed to the E2E team; successful FC consumption
  remains to be verified (OQ-2). Relevant findings from
  [OSAC-5807](https://redhat.atlassian.net/browse/OSAC-5807) may inform FC setup.
- Independent VaaS/attachment remains a platform stretch goal under separate
  work, including [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884).

## Risks

- Management-only array access or workers without FC connectivity cannot establish
  VM consumption acceptance (OQ-2).
- Incomplete prepared SVMs, missing credentials or native policies block tenant
  storage until corrected; preserve the assignment and report the correction.
- Manual release without verified data/access cleanup could expose previous
  tenant state; preserved assignments require explicit reauthorization (OQ-3).
- A mismatch with the shared consumption configuration can block VM acceptance
  despite successful tenant resource creation (OQ-1).

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | Which tenant/tier configuration does the shared VM consumption path require, and who owns any NetApp-specific adaptation? | Open — Feature owner / OSAC-6037 workstream | Defines the onboarding output without duplicating shared VM lifecycle implementation. |
| OQ-2 | Has the intended NetApp environment demonstrated working FC consumption from its OpenShift workers? | Access handed to E2E team; validation pending — QE / infrastructure owners | Establishes readiness for joint VM acceptance. |
| OQ-3 | Is the proposed retained-assignment/credential-generation handoff sufficient for manual release and safe retry? | Proposed — Storage Working Group / Core-secrets workstream | Prevents stale-name adoption, unsafe reuse and false cleanup completion. |
| OQ-4 | Do administrators supply per-SVM credentials and matching native policies through the proposed protected convention? | Proposed baseline — Feature owner / infrastructure owners | Keeps registration to endpoint/credentials and removes SVM/LIF/account-creation privileges; another credential model changes this contract. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c8d0d8890

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c8d0d8890","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
