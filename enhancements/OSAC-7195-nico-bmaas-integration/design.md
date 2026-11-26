---
title: nico-backend-for-usable-bare-metal-instances
authors:
  - vromanso@redhat.com
creation-date: 2026-11-06
last-updated: 2026-11-06
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-7195
prd: "prd.md"
see-also:
  - https://redhat.atlassian.net/browse/OSAC-7351
  - /enhancements/OSAC-1437-bmaas-networking
replaces:
  - N/A
superseded-by:
  - N/A
---

# NICo backend for usable bare-metal instances

> **Draft status:** The [PRD is in draft PR #475](https://github.com/osac-project/enhancement-proposals/pull/475), so its requirements may change. This design is submitted for parallel review as an engineering proposal, not a claim that the GB300 pilot installed an operating system or enforced a SecurityGroup. Resolve the open questions and reconcile the final PRD before merging this EP.

## Summary

Add a provider-owned binding from an OSAC tenant, Subnet, Instance Type and DiskImage to approved NICo resources; use the existing BMI controller and AAP dispatch to allocate from a NICo Instance Type, boot an approved ARM64 OS, report verified guest readiness and IPv4 attachment, and retain ownership through safe cleanup. See [PRD](prd.md) for the product requirements.

## Motivation

The GB300 pilot proves that an OSAC BMI can allocate a NICo Instance from a two-tray pool, report the selected Machine and IPv4 address, and eventually release that Machine. Its `fedora` DiskImage was a KubeVirt containerDisk while NICo booted an Assisted Installer discovery environment. The pilot also set `phoneHomeEnabled: false`, treated NICo `Ready` as OSAC `RUNNING`, and accepted an OSAC SecurityGroup without programming policy into NICo. Therefore its `RUNNING` state did not establish the guest OS or access contract in the PRD.

The pilot's binding is a mounted ConfigMap of OSAC Tenant/Subnet IDs and numeric AWX credential IDs. Boot, network, pool, and tenant identifiers are embedded in the AWX credential. This is adequate for one controlled test, but does not provide a stable, inspectable administrative contract or safe credential rotation. The pilot code is on a development branch, not upstream `main`.

### Goals

- Preserve the tenant-facing BMI, catalog, InstanceType, Subnet, and single-attachment API shapes. Extend DiskImage only to represent a real, pinned installable disk artifact; NICo identifiers and credentials stay provider-only.
- Make the binding exact, durable, reviewable, and independent of AWX database IDs. Snapshot the nonsecret identity needed to clean up a BMI even after onboarding changes.
- Let NICo select an eligible Machine from a provider-approved Instance Type; do not race NICo with OSAC's generic host allocation or fabric port operations.
- Distinguish NICo allocation/network convergence from installed-guest readiness before setting the BMF condition that Fulfillment maps to `RUNNING`.
- Make creation at most once under an uncertain response, and deletion ownership-checked and finalizer-protected.

### Non-Goals

- OSAC creation/deletion of NICo VPCs, Prefixes, or NSGs; a NICo fabric manager is [OSAC-7351](https://redhat.atlassian.net/browse/OSAC-7351).
- Automatic conversion of OCI containerDisks or arbitrary user iPXE scripts into NICo Operating Systems. The first offering uses a provider-published disk artifact and a registered installer.
- Flat/ETV networking, multiple BMI attachments, IPv6, ExternalIP/NAT, HostedCluster workers, and tenant selection of a specific Machine.
- NICo power-off/restart and arbitrary post-create network/OS mutation. The NICo BMI path rejects these requests until their semantics are designed.

## Proposal

The first boot implementation uses a provider-published, immutable ARM64 QCOW2 disk artifact and a NICo templated iPXE Operating System that installs that artifact to local storage and boots the installed guest. The provider tests the Site's `qcow-image` template on a GB300 before publishing the offering; if that template cannot install and boot the image, this design returns for review rather than substituting a discovery script. The Cloud Infrastructure Admin creates an OSAC DiskImage describing the same pinned artifact, registers and synchronizes the NICo Operating System, then creates a provider-only `NicoBareMetalBinding` through Fulfillment's private API. The binding names the OSAC tenant, Subnet, BMI InstanceType, exact DiskImage-to-NICo-OS mappings, NICo tenant/site/VPC/Prefix/Instance Type, and stable AWX credential names. Its spec contains only nonsecret IDs and stable names; tokens, client secrets, and CA material remain outside the binding. A Fulfillment reconciler validates it and exposes `Ready` only when the image, installer, and other remote resources agree. An installer hook or admin CLI can submit this API object; admins are not required to post a Kubernetes CR.

Fulfillment keeps its tenant API. On BMI creation it selects exactly one Ready provider binding and passes its ID/version, stable OSAC resource IDs, selected DiskImage ID, SSH public key and user-data reference to BMF as internal template parameters. BMF rechecks the binding through the private API, persists a nonsecret snapshot on the BMI before any NICo create call, and launches the NICo AAP role with resolved credentials. A short allocation job creates or adopts an Instance with the BMI UID as ownership label, approved NICo OS, phone-home, and validated cloud-init user data that installs the tenant SSH public key. It returns provider IDs before the guest boot wait. Separate read-only observation jobs track network assignment and guest callback, allowing BMF to persist provider IDs even when boot fails. BMF reports the host as `RUNNING` only after the agreed guest-readiness gate. On deletion it uses the saved Instance/Machine IDs and binding snapshot to remove only the owned Instance and wait for the original Machine to become unassigned and Ready.

This is an explicit exception to the accepted generic [BMaaS networking flow](/enhancements/OSAC-1437-bmaas-networking/design.md): NICo and its DPU own FNN attachment and address assignment, so OSAC does not move a switch port or discover a fabric DHCP lease. The exception does not redefine VirtualNetwork/Subnet/SecurityGroup semantics for other managers.

### Workflow Description

**Starting state:** NICo Site and DPU Machines are onboarded; at least one Machine in the approved NICo Instance Type is unassigned Ready. A NICo tenant account has compute/IP allocations and a Ready FNN VPC with a Ready VPC Prefix. The provider has published a versioned, checksum-verified ARM64 QCOW2 artifact at an HTTPS URL reachable during boot; registered a NICo templated iPXE OS that installs that URL; confirmed Site `Synced`, local-disk reboot, metadata phone-home and authorized FNN reachability on the target hardware; and provisioned separate AWX tenant/provider credentials. The OSAC tenant, catalog item, InstanceType, VirtualNetwork/Subnet, and matching DiskImage exist.

1. **Cloud Infrastructure Admin:** publish the pinned artifact, create its OSAC DiskImage, register the NICo installer OS, and create the binding through Fulfillment's private API, either directly or with repeatable onboarding automation. Validation reads the DiskImage URL/checksum/architecture and NICo OS template parameters and Site association, as well as the OSAC Subnet/VNet and InstanceType identities, NICo tenant account/allocation, Instance Type Site/Ready pool, FNN VPC/Prefix association and exact IPv4 CIDR, credential availability, and the network-policy contract below. Binding updates are staged; an invalid new version does not become usable.
2. **Cloud Provider Admin:** publish the BMI catalog item for the authorized OSAC tenant. A tenant does not see the binding's NICo IDs or AWX credentials.
3. **Tenant Admin/User:** create a BMI through the existing API/CLI with catalog item, InstanceType, approved DiskImage, SSH public key, and the one approved Subnet. Fulfillment resolves references, validates tenant ownership, selects one Ready private binding, and passes its ID/version to BMF. A mismatch or unsupported SecurityGroup policy fails before any NICo Instance POST.
4. **BMF and AAP:** BMF installs its finalizer, reads the selected validated binding through the private API, and persists create intent plus a nonsecret binding snapshot on the BMI before launching one AAP allocation job. AAP rechecks tenant/site/VPC/Prefix/pool/OS bindings, including the NICo OS definition fingerprint and Site `Synced` association, then POSTs a NICo Instance with `instanceTypeId`, one FNN physical interface using `vpcPrefixId`, `operatingSystemId`, `userData`, `phoneHomeEnabled: true`, and ownership labels. NICo chooses the Machine. The allocation job returns the NICo Instance ID without waiting for OS boot; the initial REST response is not proof of boot.
5. **BMF and AAP:** BMF persists the NICo Instance ID, then launches bounded read-only observation jobs. Persist the original Machine ID once assigned, including when the guest is still booting. Validate the NICo Instance's tenant, UID label, pool, VPC, OS, Machine, interface, and single IPv4 address within the exact approved Prefix. Report provisioning progress without `PowerSynced=True` until the guest gate succeeds. Fulfillment then projects the BMF result and IP to the tenant's BMI status.
6. **Tenant Admin/User:** read BMI state and address. After `RUNNING`, connect from an authorized network endpoint using the key whose public half was supplied. The real-hardware E2E test must prove this with its own private half; routine OSAC reconciliation cannot authenticate with a tenant private key it never receives.
7. **Tenant Admin/User:** delete the BMI. BMF keeps the finalizer and saved IDs, AAP rechecks ownership and requests deletion, then polls NICo until the Instance is absent and the **same** Machine reports `Ready`, `instanceId: null`, and no allocation-blocking aggregate alert. Only then does BMF remove its finalizer. Fulfillment removes the public BMI after BMF disappears.

NICo `Ready` before guest callback, `BootCompleted` after callback, a timed-out AAP job, and a transient NICo outage are distinct states. The implementation must verify the deployed NICo version's exact `Ready`/`BootCompleted` transition; with phone-home enabled it must not mark the BMI running from `Ready` alone.

### API Extensions

**Public DiskImage source extension ([OSAC-7383](https://redhat.atlassian.net/browse/OSAC-7383)).** Add a source type for an HTTPS QCOW2 disk artifact (illustrative enum name `SOURCE_TYPE_HTTPS_QCOW2`) and an immutable SHA-256 field in `DiskImageSpec`. For this source type, require an HTTPS `source_ref`, a valid digest, and a provider-published immutable artifact URL. The first GB300 offering additionally requires Linux/ARM64 compatibility. Keep existing `SOURCE_TYPE_REGISTRY` behavior unchanged; compute and other backends that cannot consume the new source type reject it explicitly. The source describes the installed disk bytes, not the NICo OS UUID or an Assisted Installer ISO. A new image version gets a new DiskImage rather than changing its immutable source. Exact proto names and whether a URL-specific type should be generalized are subject to API review; the URL, digest, and backend compatibility requirements are not optional.

The first implementation deliberately avoids an OCI-to-NICo conversion service. Such a service would need to extract a disk artifact, publish it on the boot network, verify its digest, create and synchronize a NICo OS, and maintain that relationship through versioning and deletion. It is a separate future capability, not an implied conversion of the pilot's `quay.io/containerdisks/fedora:latest` reference.

**Provider-only Fulfillment object: `NicoBareMetalBinding` (working name).** Add a private gRPC service and persisted object in Fulfillment, following the administrative API pattern used for NetworkClass. A single binding is keyed by `(OSAC tenant ID, OSAC Subnet ID, OSAC BMI InstanceType ID, NICo Site ID)`, with exactly one active binding per key. The service is absent from the generated public API. The installer or an admin tool creates/updates it idempotently through the private API; tenants never post a Kubernetes CR. Example object shape, with exact proto names subject to API review:

```yaml
metadata:
  name: tenant1-gb300-fnn
  tenant: tenant1
  annotations:
    osac.openshift.io/tenant: tenant1
    osac.openshift.io/owner-reference: Tenant/<OSAC-tenant-ID>
spec:
  osacTenantID: <OSAC-tenant-ID>
  osacSubnetID: <OSAC-subnet-ID>
  osacInstanceTypeID: <OSAC-instance-type-ID>
  nicoTenantID: <NICo-tenant-ID>
  nicoSiteID: <NICo-site-ID>
  nicoVPCID: <NICo-vpc-ID>
  nicoVPCPrefixID: <NICo-prefix-ID>
  nicoInstanceTypeID: <NICo-instance-type-ID>
  awxOrganization: <provider-AWX-organization>
  tenantCredentialName: <AWX-credential-name>
  providerCredentialName: <AWX-credential-name>
  operatingSystems:
    - diskImageID: <OSAC-disk-image-ID>
      nicoOperatingSystemID: <NICo-operating-system-ID>
      sshLoginUser: <installed-guest-user>
status:
  validatedSpecFingerprint: <fingerprint>
  conditions:
    - type: Ready
      status: "True"
      reason: Validated
```

The binding is managed by private-API authorization. `spec` contains only nonsecret IDs and stable names, never tokens, client secrets, or CA material. The Fulfillment server rejects duplicate active four-part keys and mismatched tenant metadata; its reconciler validates OSAC and remote NICo/AWX resources and enforces unique DiskImage mappings. Status records the fingerprint of a successfully validated spec and remote definitions; a mismatch sets `Ready=False` without exposing credentials. For each mapping it resolves the OSAC DiskImage ID and its immutable URL/digest, reads the NICo OS UUID and Site association, requires the approved `qcow-image` template and an exact `image_url` match, and records a fingerprint of the OS definition and boot policy. The provider verifies the published artifact's SHA-256 and that the URL cannot be overwritten; because the template's `image_url` parameter is not itself a digest proof, a matching URL alone does not establish byte identity. A changed NICo OS definition or unsynced Site association makes the binding unready for new BMIs, and AAP rechecks the fingerprint before create. Binding deletion is blocked while any BMI references it; credential names may rotate only after new credentials validate, while old BMI snapshots retain the identities needed for cleanup. `Ready` is a prerequisite for **new** BMI creation, not a reason to lose cleanup authorization for existing BMIs.

**Existing BMI APIs:** no new public NICo-specific fields or methods. Internal BMF BMI status adds an operation record (create intent, AAP job reference, binding ID/version, chosen OS ID, NICo Instance ID/Machine ID, assigned address, and observed readiness stage) and conditions for provider binding, guest boot, and cleanup. Fulfillment passes the selected binding ID/version and OSAC DiskImage/InstanceType IDs in internal template parameters and maps BMF `PowerSynced=True/PowerOn` to public `RUNNING` only after the NICo guest gate. Internal status must not print OAuth material, user data, or SSH keys.

**SecurityGroup API behavior:** The current public create path requires a SecurityGroup for a nondefault Subnet and can default one on the default Subnet. This design cannot silently ignore such a group. The initial proposed contract is to allow a NICo catalog item to request an explicit Subnet **without** SecurityGroups, with a narrow NICo-specific validation exception; any supplied or defaulted group is rejected before allocation. The provider-prepared FNN VPC still provides tenant network isolation, but OSAC makes no SG firewall claim on that attachment. This is a deliberate exception requiring networking-owner review. If reviewers require an SG on every BMI attachment, the alternative is a pre-created NICo NSG whose effective rules are verified equivalent and whose propagation is checked before reporting ready; OSAC-7351 would later own NSG lifecycle. See Open Question 1.

## UX Alignment

No new tenant UI workflow or BMI public field is proposed. The public DiskImage source extension is exposed through the existing image catalog path; the UI must display its source/architecture correctly if it shows image details. The current `osac-ui` BMI API adapter consumes generated proto types rather than maintaining a matching `@temp-api` field model. The existing CLI/API displays the BMI lifecycle and assigned address; other UI work is limited to any generic status rendering affected by the stricter `RUNNING` gate.

### Implementation Details/Notes/Constraints

**Binding and validation.** Persist the administrative binding in Fulfillment and expose it only through its private API. A Fulfillment reconciler checks OSAC references and delegates NICo checks to a provider preflight AAP job using the AWX tenant/provider credential pair; BMF must never read client secrets. AWX credential names are resolved within the named AWX organization to numeric IDs at job launch by a scoped service client, with duplicate/missing-name failure. This requires extending the AAP provisioner; simply storing names in the existing pilot ConfigMap will not work because it currently accepts only IDs. NICo REST/token endpoints and the CA bundle are provider deployment configuration; OAuth material remains in AWX. Preflight records the validated binding version/fingerprint and nonsecret remote resource versions/IDs; it must recheck immediately before the create POST to close staleness between validation and allocation. Sensitive validation diagnostics stay in provider-only logs/status.

**Placement.** The binding contains `nicoInstanceTypeID`, not a target Machine. NICo selects from the Ready Machines eligible for that Instance Type and tenant allocation. The AAP role checks that the selected `machineId` belongs to the same Site and type before publishing it. Placement is constrained by NICo pool/allocation policy, not OSAC inventory labels alone. The two-tray pilot selected different Machines on separate runs, which is expected.

**DiskImage and OS.** A provider prepares one tested, immutable ARM64 QCOW2 and records its HTTPS URL and SHA-256 in a new OSAC DiskImage. It registers a NICo templated iPXE Operating System using the Site's `qcow-image` template with `image_url` set to that exact URL and waits for the Site association to become `Synced`. It then creates the binding entry `(OSAC DiskImage ID, Site ID) -> NICo Operating System UUID`, with an expected guest login user. These are explicit onboarding operations; OSAC does not infer a NICo OS from the image name or scan NICo for a match. At binding validation and again before Instance POST, compare the DiskImage source, NICo template/parameters, Site status, and stored OS definition fingerprint. The selected image must install the named ARM64 OS to local storage and boot it, not leave the host in a discovery environment. The first offering is unavailable until this path is proven on its Site. [NICo's templated iPXE Operating System](https://docs.nvidia.com/infra-controller/documentation/configuration-day-1/templated-i-pxe-operating-systems) provides the OS UUID selected by the Instance. The pilot's existing `fedora` OCI containerDisk is rejected on this NICo path; architecture compatibility alone does not convert it into an installable disk artifact. If the Site cannot use the template on GB300, evaluate a Site-enabled [image-based NICo OS](https://docs.nvidia.com/infra-controller/documentation/configuration-day-1/image-based-operating-systems) and return to API/design review before changing the install contract.

**Guest configuration and readiness.** Validate SSH public-key syntax; resolve optional user data from the existing OSAC secret reference; accept only a bounded, supported cloud-init format. Merge tenant key installation into the binding's approved guest login user and enable [NICo phone-home](https://docs.nvidia.com/infra-controller/documentation/configuration-day-1/tenant-management) without allowing user data to remove or redirect the callback. Require NICo OS `allowOverride` when passing per-Instance `userData`; reject before POST if unsupported. Do not use NICo `sshKeyGroupIds` for guest SSH: those grant serial-console access. Phone-home must originate from the installed guest after cloud-init, not the installer environment, and be tied to the NICo Instance; use NICo's `BootCompleted` (or the target release's documented final callback signal) as the automated readiness gate. The BMF `PowerSynced=True/PowerOn` condition is set only after that signal, preserving Fulfillment's existing `RUNNING` mapping. A real-hardware acceptance test uses the corresponding private key to authenticate over the reported address. Per-Instance cryptographic SSH proof by the control plane is an open decision because OSAC does not have the tenant's private key.

**FNN attachment.** AAP GETs the VPC and Prefix and verifies tenant ID, Site ID, `networkVirtualizationType=FNN`, Prefix `Ready`, VPC association, and exact normalized IPv4 CIDR equality with the OSAC Subnet; check the IP Block allocation as required by NICo. [NICo FNN](https://docs.nvidia.com/infra-controller/documentation/operations-day-2/managing-vp-cs/vpc-network-virtualization) creation includes one `interfaces` entry with `isPhysical: true` and the bound `vpcPrefixId`. On observation, reject absent/multiple matching interfaces or addresses outside the Prefix. Report the NICo-assigned IPv4 through BMF `networkAttachmentStatuses`. Packet reachability from the provider-approved endpoint and cross-tenant isolation are hardware E2E gates; an assigned address alone is insufficient.

**Create durability.** Use a stable NICo name/label derived from the BMF BMI UID and tenant ID. Persist create intent before launching AAP, then persist the AWX allocation job ID and its returned Instance ID before beginning read-only boot observation. The allocation job must exit with that ID promptly rather than waiting up to the full boot timeout; otherwise a boot failure can hide the provider ID in AWX artifacts. A second reconcile first reads the saved job and searches NICo by exact name/UID; it does not POST again after a lost or ambiguous response. A REST `404`/empty list alone does not prove Site/Core never allocated. Provide an admin recovery action that compares NICo REST and Core allocation for the UID, records the discovered Instance/Machine IDs, or attests that no allocation exists before resetting the one-attempt gate. This action is provider-only and audited; it cannot be a tenant retry button.

**Delete durability.** Before the first NICo create call, snapshot the NICo tenant/org, provider org, Site, binding ID/version, credential names, VPC, Instance Type, and OS ID in nonsecret BMI status. Add the original Machine ID when NICo assigns it. For delete, use the snapshot rather than the latest binding spec; resolve the named credentials at run time. If credentials have rotated, the admin must retain or replace a credential authorized for the snapshotted tenant/site until cleanup finishes. AAP must verify NICo Instance ownership label, tenant, Machine, and Site before DELETE. After DELETE, Instance absence and original Machine `Ready`/unassigned/no allocation-blocking aggregate alert are required. Failed/expired jobs retain the finalizer and retry with backoff; do not repeatedly POST a create. Do not use a separate health-report endpoint as the only cleanup gate: the pilot received a nested 403 from that endpoint while Machine GET supplied aggregate health.

**Installer and documentation.** Ship the private API and database migration, scoped API authorization, binding reconciliation, normal Helm values/schema, AWX custom credential type, versioned AAP project/Execution Environment, provider setup/preflight, and operator recovery runbook. The dev-only `redeploy-nico-pilot` target is not the product deployment interface. If installer values change, update the Enclave Wizard plugin/schema chain and test generated install artifacts. No tenant-visible NICo token is stored in Helm values, ConfigMaps, BMIs, AAP artifacts, or logs.

### Security Considerations

- Tenant create/list/get/delete remains subject to the existing Fulfillment auth boundary. Resolve the tenant from authenticated metadata, not a caller-provided NICo ID. Validate referenced catalog, DiskImage, InstanceType, Subnet and any SG against the same OSAC tenant before binding lookup.
- Bindings, credential names, raw NICo IDs, operation snapshots and admin recovery are provider-only. RBAC prohibits tenant writes/reads of the binding and AWX credentials. BMF and AAP use the minimum tenant/provider NICo roles needed for create/delete and Machine read; broadened dev `ncx-service` credentials are not a production pattern.
- Verify ownership before adopt/delete by exact BMI UID label, NICo tenant, Site, VPC, selected Instance Type and saved Machine ID. Do not delete by name alone. The label is an idempotency hint, not a trusted authorization decision by itself.
- Reject unsupported SG policy before allocation and document the temporary no-SG capability if approved. FNN VPC isolation and site deny prefixes are not a substitute for an arbitrary OSAC SG. Verify cross-tenant packet isolation on real hardware.
- Never log OAuth tokens, client secrets, user data, private keys or complete cloud-init. The tenant SSH public key may appear in a protected create request; persist only where existing BMI/user-data access controls permit.

### Failure Handling and Recovery

| Failure | System action | Tenant-visible result / recovery |
|---|---|---|
| Missing/duplicate/unready binding, unapproved DiskImage or SG, mismatched Subnet/Prefix/tenant/site | Reject before Instance POST; condition includes safe reason | Create fails or stays provisioning with actionable reference; admin fixes binding, tenant may create a new BMI. |
| AWX credential missing or token service unavailable before POST | No NICo POST; retain any persisted intent and inspect a launch whose outcome is uncertain before retrying | Provisioning/error; no false `RUNNING`. |
| Lost AAP launch response or NICo POST result | Keep create intent, inspect saved job and exact UID/name; no automatic second POST | `CreateOutcomeUnknown`; provider reconciles Site/Core before any retry. |
| NICo Instance allocated but OS install/phone-home fails | Persist Instance/Machine IDs and remain provisioning or failed; keep finalizer | Tenant sees boot timeout/failure and may delete safely; admin inspects boot/metadata. |
| NICo Instance returns unexpected Machine/VPC/OS/interface/IP | Fail closed with saved IDs; do not publish an address as usable | Failed BMI; admin investigates provider state and deletes owned Instance. |
| NICo/Keycloak/PostgreSQL outage during deletion | Retain finalizer, retry bounded AAP jobs with backoff and same snapshot | BMI remains `DELETING`; after provider recovery it completes. Pilot observed this after PostgreSQL storage filled. |
| Instance already absent but original Machine still cleaning/alerting | Continue polling original Machine; no finalizer removal | `DELETING` until Machine unassigned Ready and healthy. |
| Binding edited/deleted or credentials rotated while BMI exists | Old snapshot remains authoritative; binding deletion blocked; old or replacement credential remains available | Existing BMI can still delete; new creates use only a validated binding version. |

Every external operation has a bounded per-job timeout and an overall provider-visible age alert. Timeout does not mean cleanup succeeded. AAP returns structured, nonsecret artifacts; BMF verifies them against stored IDs before progressing.

### RBAC / Tenancy

`NicoBareMetalBinding` is a provider-managed Fulfillment object, stored in its database and accessible only through the private API. Its metadata identifies the OSAC tenant and carries `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` annotations. The private API rejects missing or mismatched tenant metadata; Fulfillment and BMF compare the selected binding with the BMI tenant and Subnet. Only provider administrators can create, update, or delete bindings; explicitly scoped service identities can read them for reconciliation. Tenant credentials cannot enumerate them. AAP credentials are scoped by AWX organization/job-template RBAC and selected only through the validated binding. The BMI CR retains its existing tenant and owner-reference annotations; the binding snapshot never crosses into tenant-controlled spec fields.

### Observability and Monitoring

- BMF conditions/events: `BindingReady`, `NICoCreateOutcomeUnknown`, `NICoAllocated`, `NICoGuestBootPending`, `NICoGuestBootFailed`, `NICoCleanupPending`, and `NICoCleanupBlocked`, with safe reason codes and no credential contents. Public BMI status projects meaningful progress via existing state/conditions.
- Metrics: `osac_nico_bmi_operations_total{operation,result}` counter, `osac_nico_bmi_operation_duration_seconds{operation}` histogram, and `osac_nico_bmi_pending{stage}` gauge. Exclude tenant, BMI UID, Instance ID and Machine ID from metric labels to avoid cardinality and data exposure. Alert on a create outcome unknown, deletion pending beyond the documented NICo cleanup window, and an unready binding serving an active offering; thresholds come from real Site timings, not the pilot's single run.
- Structured logs correlate OSAC BMI UID, binding ID/version, AWX job ID and NICo Instance/Machine IDs in provider-only logs. Tenant-facing messages omit raw provider IDs unless the public BMI contract already exposes the Machine reference. Record Site/OS version and validation evidence in the hardware E2E report.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| NICo `Ready` means control-plane convergence, not the installed OS | Enable phone-home, wait for verified final callback state, and run real-hardware installed-OS/SSH acceptance. |
| OSAC image choice may misrepresent NICo boot or mutable artifact bytes | Require the new URL-plus-digest source, a provider-verified immutable artifact, exact Site/OS/template/`image_url` binding, and a definition fingerprint recheck before create; reject the pilot containerDisk. |
| FNN Subnet and SG semantics diverge from accepted networking designs | Compare exact CIDR, make the NICo networking exception explicit, reject SG policy until enforceable, and request networking-owner review. |
| REST/Core eventual consistency after POST leads to duplicate allocation | Durable one-attempt intent plus provider recovery check; never equate empty REST list with safe retry. |
| Slow or failed NICo cleanup keeps a Machine reserved | Finalizer and backoff are intentional; publish age alert and Site runbook, including provider DB/storage checks. |
| Credential rotation or AWX DB ID churn strands deletion | Stable credential names, launch-time lookup, and cleanup snapshot; block retirement of credentials while dependent BMIs exist. |
| Admin binding can reference another tenant's resources | Private API authorization, exact OSAC/NICo ID verification, annotation checks, and adversarial cross-tenant tests. |

Security and networking owners should review binding authorization, guest user-data handling, and the proposed no-SG exception before implementation.

### Drawbacks

The initial offering requires provider prework for NICo tenant capacity, VPC/Prefix, OS artifacts, AWX credentials, and validation; it is not self-service network creation. A provider-only binding adds a new lifecycle and operational contract. Phone-home depends on a functioning guest cloud-init/metadata route, so an otherwise booted Machine can remain provisioning when that route fails. The strict create/delete gates can leave BMIs visibly stuck until an administrator resolves uncertain provider state; this is preferable to duplicate allocation or releasing the wrong Machine.

## Alternatives (Not Implemented)

| Alternative | Benefit | Why not selected for this increment |
|---|---|---|
| Keep the pilot ConfigMap and numeric AWX credential IDs | Smallest code delta | Binding is not a durable, validated resource and AWX ID churn can strand cleanup. |
| Put NICo tenant/VPC/pool/OS IDs in tenant BMI fields | Flexible per request | Cross-tenant resource selection and credential leakage risk; conflicts with the catalog/provider policy boundary. |
| Target the one known Machine | Deterministic demonstration | Bypasses the approved pool and requires targeted-creation entitlement; the real pilot proved pool selection across two trays. |
| Reuse Assisted Installer discovery iPXE and mark `Ready` as `RUNNING` | Already demonstrated control-plane allocation | Does not install the selected DiskImage or prove tenant SSH, violating the PRD. |
| Convert every OCI containerDisk automatically into a NICo boot source | Keeps current DiskImage source type | Requires extraction, artifact hosting, digest verification, NICo OS registration, Site sync, lifecycle and cleanup; defer until a separate image pipeline is designed. |
| Use NICo image-based OS instead of the templated `qcow-image` path | Native disk imaging with `imageSha` | Requires the Site capability and a tenant-admin-owned definition; use only if the preferred template fails GB300 validation, with an explicit design/API revision. |
| Automatically retry POST when NICo REST list is empty | Faster recovery | Site/Core may have allocated before REST became consistent; can allocate twice. |
| Use `sshKeyGroupIds` to satisfy the BMI SSH key | Uses NICo field without cloud-init merge | NICo uses this for serial-console access, not guest `authorized_keys`. |
| Fully translate OSAC SG rules into NICo NSGs now | Matches the long-term networking API | Requires NSG lifecycle, semantic parity, update propagation and default-network integration; belongs in OSAC-7351 unless reviewers reject the temporary no-SG contract. |
| Store the binding as an admin-posted BMF Kubernetes CR | BMF can watch it directly | Introduces a separate provider configuration surface; NetworkClass and StorageTier use Fulfillment's private API, and the binding needs tenant/API reference validation there. |
| Put NICo IDs in NetworkClass or catalog item | Reuses existing objects | NetworkClass chooses one deployment-wide network manager; a catalog item publishes an offering. Neither represents the per-tenant, per-Subnet, per-InstanceType and per-Site binding. |

## Open Questions

### 1. Network policy contract

Will networking owners accept an explicit NICo-only attachment with no OSAC SecurityGroup, with all supplied/defaulted groups rejected and FNN tenant isolation validated? If not, this Feature must consume a pre-created equivalent NICo NSG with verified readback/propagation, or defer BMI create until OSAC-7351. The current pilot's silent SG acceptance is not an option. **Owner:** networking design reviewers. **Impact:** determines whether a supported FNN BMI can be created before NICo NSG integration.

### 2. Per-instance SSH evidence

Is NICo's post-cloud-init phone-home sufficient for the automated `RUNNING` gate, with E2E proving SSH using a test private key, or must the control plane authenticate to every instance? The latter needs a separately generated probe key, a trusted network probe location, and a private-key lifecycle; the tenant key alone cannot be used because OSAC receives only its public half. **Owner:** BMaaS and product reviewers. **Impact:** determines the readiness state machine and whether a new probe service is required.

### 3. First supported OS and DiskImage identity

Which pinned ARM64 QCOW2, guest login user, cloud-init form, and site metadata endpoint will the provider approve, and does the Site's `qcow-image` template install and reboot it correctly on GB300? The design chooses a new URL-plus-digest DiskImage source and provider-created NICo templated iPXE OS. Confirm the template's disk selection and whether its artifact integrity can be checked by NICo itself; otherwise document and enforce immutable provider hosting. If this boot path fails, return to review before selecting the Site-gated image-based alternative. The pilot `fedora` containerDisk remains unsupported. **Owner:** NICo Site, BMaaS image, and API reviewers. **Impact:** blocks publication of the first truthful offering and fixes the exact proto source type and checksum contract.

### 4. Binding placement and credential lookup

Which provider service identity may read the private Fulfillment binding API from BMF and resolve AWX credential names, and how are credential retirements blocked while dependent BMIs exist? **Owner:** Fulfillment, BMF and AAP maintainers. **Impact:** fixes API authorization, secret access boundaries and installer wiring.

## Test Plan

### Unit Tests

- New DiskImage source type validation and immutability; explicit rejection by VM/OCI-only consumers; binding four-part key uniqueness; missing/mismatched tenant and owner-reference annotations; OSAC/NICo resource ID and CIDR normalization; duplicate/unknown OS mapping, wrong template or `image_url`, unsynced Site and changed OS fingerprint; credential-name resolution failure.
- NICo create-body table tests for FNN `instanceTypeId`, Prefix, approved OS ID, cloud-init/user-data, `phoneHomeEnabled: true`, and no tenant-supplied Machine/credentials. Reject unsupported user-data formats, `allowOverride=false`, absent Prefix, CIDR mismatch and any SG under the temporary contract.
- State transitions: BMF persists a nonsecret binding snapshot before create; allocation job returns and persists its Instance ID before boot observation; `Pending`/`Ready` do not set BMF `PowerSynced=True`; only final guest callback state does. Error, timeout, ambiguous launch, and unknown artifacts retain IDs/finalizer. Verify Fulfillment never maps pre-boot BMF state to public `RUNNING`.
- Delete checks exact tenant/UID/Machine ownership, idempotent Instance 404 handling with saved IDs, Machine `Initializing`/`Error`/blocking alert retention, and finalizer removal only on released original Machine.

### Integration Tests

- Use a fake NICo REST/Core model and AWX job API in the Kind BMF/Fulfillment stack. Verify provider image publication/binding validation, tenant BMI creation, selected pool Machine/IP projection, guest-ready gate, deletion, credential rotation, and cleanup after BMF restart. An absent mapping, OCI containerDisk, changed NICo OS definition, and mismatched artifact URL must fail before Instance POST.
- Inject lost NICo POST response, REST lag with Core allocation, duplicate UID matches, AAP launch timeout, missing artifact, Keycloak/REST 403/500, and Machine validation delay. Assert no second POST and no wrong-tenant delete.
- Exercise public API/CLI tenant isolation: tenant B cannot list/create using tenant A's catalog, Subnet, DiskImage, or binding; a nondefault NICo Subnet with unsupported SG fails before NICo allocation.
- Validate private proto generation, database migration, API authorization, Helm schema and template rendering, and (if Helm values change) the Enclave Wizard generated schema/plugin flow. Test upgrade/skew behavior with old and new Fulfillment/BMF/AAP versions.

### E2E Tests

- On a supported FNN site with at least two eligible GB300 Machines, first verify the pinned artifact's digest, boot-network reachability, NICo `qcow-image` template, OS definition and Site `Synced` association. Create one BMI without target Machine and record the OSAC DiskImage ID/digest, NICo Instance Type, allocation, selected Machine, OS ID, assigned IP, OSAC status sequence, and NICo final phone-home state.
- Prove the installed OS identity on the selected tray, successful SSH authentication with the test private key from an authorized endpoint, IP reachability and cross-tenant isolation. Include a negative test for a mismatched DiskImage, Prefix CIDR and unsupported SG that creates no NICo Instance.
- Delete the BMI, observe `DELETING` while NICo cleans up, then verify public BMI absence, NICo Instance absence and the exact original Machine `Ready`/unassigned/no blocking health alerts. Repeat after an injected transient NICo service outage, with no leaked Instance.

## Graduation Criteria

Graduation criteria will be fixed when a release target is assigned. Dev Preview requires the above hardware create/boot/SSH/network/delete evidence and recovery runbook; later maturity requires repeated multi-tenant, upgrade, and failure-injection runs rather than reliance on the two pilot allocations.

## Upgrade / Downgrade Strategy

The provider opts into NICo offerings only after installing the private API/database migration, scoped authorization, BMF/AAP code, AWX credential type, and validated bindings. Existing non-NICo BMIs continue through their current path. The development ConfigMap is not silently migrated: an admin exports each pilot tuple, creates an equivalent binding with stable credential names and explicit OS mapping, verifies `Ready`, then retires the ConfigMap after pilot BMIs are gone. On rollback, stop new NICo creates first. Running NICo BMIs retain their BMF finalizer and deletion snapshot; do not downgrade to a version that cannot clean them up until they are deleted or a compatible cleanup controller remains. No automatic forced finalizer removal is part of rollback.

## Version Skew Strategy

Fulfillment must pass the added internal DiskImage/InstanceType IDs before a new BMF NICo path accepts create; missing values fail before NICo POST. BMF must recognize both old pilot statuses and new operation records for safe deletion but must not infer guest boot from an old `Ready` condition. The AAP role/module version in AWX must match the BMF artifact/extra-var contract; a binding is `Ready=False` if the installed AAP project/Execution Environment lacks it. Rolling upgrades may leave an active BMI in provisioning or deletion, with finalizer and IDs preserved; reconciliation resumes when compatible components are available. Tests cover skipping patch releases within the same minor stream and a one-minor rollback.

## Support Procedures

Inspect the public BMI state/conditions, BMF BMI phase/operation record and finalizer, binding `Ready` condition/version, AWX job result and nonsecret artifacts, and NICo Instance/Machine status/history. Diagnose `BootPending` with the selected OS template, boot artifact URL, guest cloud-init and Site metadata phone-home route. Diagnose long `Deleting` with NICo Instance presence, Machine validation/aggregate health, Keycloak and NICo REST health, and PostgreSQL/WAL/archive capacity; the pilot's full repository and WAL volumes interrupted OAuth and deletion. After provider recovery, let the controller retry; use the audited create-outcome recovery procedure only when REST and Core agree on the ownership result. Disabling the offering stops new creates but keeps binding/credentials and BMF deletion reconciliation active until all existing BMIs are released.

## Infrastructure Needed

A maintained NICo FNN test Site with two eligible ARM64 Machines, a provider-approved installable OS template and artifacts, a reachable metadata phone-home endpoint, an authorized SSH/reachability test host, a second NICo tenant for isolation checks, and an AWX project/Execution Environment containing the NICo role. These are test prerequisites, not resources that OSAC creates in this Feature.

---

## Provenance

Authored: draft @ design 0.8.0 - 7efcedb, workspace no-issue/nico-bmaas-integration-audit @ e71f63765
Final: revise @ design 0.11.5 - d1824b1, workspace no-issue/nico-bmaas-integration-audit @ e71f63765

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"d1824b1","source_repo":"e71f63765","source_repo_branch":"no-issue/nico-bmaas-integration-audit","commits_behind_main":0,"commits_ahead_main":13,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
