# Pure FlashArray Storage Provider for OSAC

| Field       | Value   |
|-------------|---------|
| Author(s)   | Chen Yosef |
| Jira        | TBD — no ticket created yet |
| Date        | 2026-06-09 |

## 1. Problem Statement

OSAC currently supports only VAST Data as a storage provider for tenant VM boot disks. CSPs using Pure Storage FlashArrays cannot offer OSAC-managed storage to their tenants without manual, out-of-band provisioning that bypasses OSAC's tenant isolation, tiering, and credential management. This forces CSPs to either adopt VAST infrastructure or manage Pure storage entirely outside OSAC, losing the automation, multi-tenancy, and QoS guarantees that the storage provider framework delivers. Adding Pure FlashArray as a pluggable storage provider enables OSAC to serve CSPs with Pure infrastructure using the same tenant isolation and tiering model already proven with VAST.

## 2. Goals and Non-Goals

### 2.1 Goals

- CSPs with Pure FlashArray infrastructure can onboard tenants with isolated, tiered block storage through the same `storage_provider` workflow used for VAST, with no manual storage provisioning required after initial FlashArray setup.
- Each OSAC tenant receives an isolated FlashArray Realm with per-tier Pods, QoS enforcement, and scoped credentials — preventing cross-tenant data access or performance interference.
- Tenant VM boot disks provisioned via KubeVirt use Pure FlashArray block storage with per-tier QoS limits and optional encryption, managed entirely through OSAC's existing StorageClass and Tenant CR machinery.
- The implementation reuses the existing `storage_provider` dispatcher, EP #26 StorageClass labeling, and Tenant CR credential flow — no changes to `osac-operator` or `fulfillment-service` are required.

### 2.3 Non-Goals

- **NVMe-TCP transport.** PX-CSI QoS limits (`max_iops`, `max_bandwidth`) are not supported with NVMe volumes. iSCSI is the only supported transport for MVP. NVMe-TCP can be added when QoS support is available or when QoS is not required for a deployment. `[Clarify: R2.Q1]`
- **VolumeSnapshotClass creation.** FlashArray supports native snapshots, but VolumeSnapshotClass provisioning is deferred. `[Clarify: R1.Q5]`
- **Multi-array support.** MVP targets a single FlashArray per deployment. Routing volumes across multiple arrays is deferred. `[Clarify: R1.Q5]`
- **FlashBlade (NFS/S3).** Only FlashArray block storage is in scope. `[User]`
- **Changes to osac-operator or fulfillment-service.** The Tenant controller already handles multi-tier StorageClasses via EP #26. No upstream changes are needed.

## 3. Requirements

### 3.1 Functional Requirements

#### Tenant Setup

- **FR-1:** The `pure_storage` role must create a FlashArray Realm for each OSAC tenant using `purestorage.flasharray.purefa_realm`, providing SMT-based isolation. `[Clarify: R1.Q3]`
- **FR-2:** For each configured storage tier, the role must create a FlashArray Pod within the tenant's Realm (e.g., `pod-<tenant>-<tier>`), enabling per-tier volume and QoS isolation. `[Clarify: R2.Q3]`
- **FR-3:** The role must create a per-tenant FlashArray user with a Role scoped to the tenant's Realm, granting CSI-level access without admin privileges. `[User]`
- **FR-4:** The role must persist tenant configuration (Realm ID, Pod names, per-tenant credentials, FlashArray endpoint) to a K8s Secret on the hub cluster, following the same pattern as VAST's `vast-tenant-config-*` Secrets. `[User]`
- **FR-5:** If any step in tenant setup fails, the role must roll back all partially-created FlashArray resources (Realm, Pods, user, Role) and the hub Secret before reporting the error. `[User]`

#### StorageClass Provisioning

- **FR-6:** The role must create one Kubernetes StorageClass per configured tier, with `provisioner: pxd.portworx.com`, `backend: pure_block`, and `pure_fa_pod_name` set to the tier's FlashArray Pod name. `[Clarify: R2.Q2, R2.Q3]`
- **FR-7:** Each StorageClass must carry `osac.openshift.io/tenant` and `osac.openshift.io/storage-tier` labels, conforming to EP #26 (tenant-storage-tiers). `[User]`
- **FR-8:** When a tier definition includes QoS limits, the StorageClass must include `max_iops` and/or `max_bandwidth` parameters. `[Clarify: R1.Q5]`
- **FR-9:** When block encryption is enabled (passphrase provided via Tenant CR spec), the StorageClass must set `secure: "true"` and the CSI Secret must include the encryption key. `[Clarify: R1.Q5]`
- **FR-10:** The role must create a CSI Secret in the tenant's namespace containing per-tenant FlashArray credentials (API token, endpoint). Admin credentials must never appear in tenant-namespace resources. `[User]`
- **FR-11:** If all expected StorageClasses for a tenant already exist, the role must short-circuit and skip provisioning (idempotent). `[User]`

#### CSI Operator Installation

- **FR-12:** The role must install the Portworx Enterprise Operator via OLM from the `certified-operators` catalog source, following the same OLM pattern as VAST's CSI operator installation. `[Clarify: R1.Q1]`
- **FR-13:** The role must wait for the PX-CSI driver to register before proceeding with StorageClass creation. `[User]`

#### Teardown

- **FR-14:** The role must delete all K8s resources (StorageClasses, CSI Secret, hub Secret) and FlashArray resources (Pods, user/Role, Realm) for a tenant, using best-effort cleanup with `ignore_errors` to prevent one failure from blocking others. `[User]`

#### Dispatcher Integration

- **FR-15:** The role must integrate with the existing `osac.service.storage_provider` dispatcher, accepting `_provider_tiers` and `_provisioning_target` inputs and producing `storage_provider_tenant_config` and `storage_provider_storage_class_names` output facts. `[User]`
- **FR-16:** The role's `meta/osac.yaml` must declare `implementation_strategy: pure`, `template_type: storage_provider`, `supported_protocols: [block]`, and `provisioning_targets: [vmaas]`. `[User]`

### 3.2 Non-Functional Requirements

- **NFR-1:** Admin credentials (FlashArray API token with full privileges) must be sourced from environment variables on the AAP pod and cleared from Ansible facts after each run. They must never be written to K8s Secrets in tenant namespaces. `[User]`
- **NFR-2:** Per-tenant credentials stored in the CSI Secret must use the scoped user created in FR-3, not the admin API token. `[User]`
- **NFR-3:** All FlashArray API calls must use TLS with configurable certificate validation (analogous to VAST's `vast_storage_validate_certs`). `[User]`
- **NFR-4:** The role must be transport-agnostic. It creates StorageClasses with `backend: pure_block` without specifying iSCSI or NVMe-TCP. Transport is a deployment-time decision configured at the StorageCluster CR level by the CSP. `[Clarify: R2.Q2]`
- **NFR-5:** The `purestorage.flasharray` certified Ansible collection must be added to `collections/requirements.yml` with a pinned version. `[Clarify: R1.Q4]`

## 4. Acceptance Criteria

- [ ] A CSP can run `playbook_osac_configure_tenant_storage.yml` with `STORAGE_TIERS` containing `provider: pure` entries, and the playbook creates a FlashArray Realm, per-tier Pods, a scoped user, and a hub Secret for the tenant.
- [ ] StorageClasses created by the role have `provisioner: pxd.portworx.com`, `backend: pure_block`, correct `pure_fa_pod_name`, and EP #26 labels (`osac.openshift.io/tenant`, `osac.openshift.io/storage-tier`).
- [ ] A KubeVirt VM provisioned using a Pure-backed StorageClass gets a boot disk on the correct FlashArray Pod within the tenant's Realm.
- [ ] QoS parameters (`max_iops`, `max_bandwidth`) appear in the StorageClass when the tier definition includes QoS limits.
- [ ] Block encryption is enabled (`secure: "true"` in StorageClass, encryption key in CSI Secret) when a passphrase is provided via the Tenant CR spec.
- [ ] Teardown removes all FlashArray resources (Realm, Pods, user) and K8s resources (StorageClasses, Secrets) for the tenant.
- [ ] A setup failure mid-way through (e.g., Pod creation fails) triggers rollback that cleans up the partially-created Realm and hub Secret.
- [ ] The Portworx Enterprise Operator is installed via OLM and the PX-CSI driver registers before StorageClass creation proceeds.
- [ ] `ansible-lint` passes on all new task files.
- [ ] Admin FlashArray credentials never appear in tenant-namespace K8s Secrets.

## 5. Assumptions

- The CSP has a FlashArray running Purity//FA with Secure Multi-Tenancy (SMT) support (Purity 6.4+). If SMT is not available, the Realm and Pod creation steps will fail.
- The Portworx Enterprise Operator is available in the `certified-operators` catalog on the target OpenShift cluster. Air-gapped environments may require mirroring the catalog.
- The `purestorage.flasharray` Ansible collection includes `purefa_realm`, `purefa_pod`, `purefa_host`, and user/role management modules. If any module is missing, the corresponding step will need to use direct REST API calls as a fallback.
- iSCSI connectivity between OpenShift worker nodes and the FlashArray is pre-configured by the CSP (multipath, iSCSI initiators). The role does not provision network-level connectivity.

## 6. Dependencies

- **Portworx Enterprise Operator** — must be available in the OpenShift OperatorHub (`certified-operators` catalog).
- **`purestorage.flasharray` Ansible collection** — must be added to `collections/requirements.yml` and vendored.
- **EP #26 (tenant-storage-tiers)** — the Tenant controller in `osac-operator` must support `status.storageClasses` (list) for the tier-labeled StorageClasses to be resolved. This EP is already implemented.
- **`osac.service.storage_provider` dispatcher** — the existing dispatcher already supports multi-provider dispatch. No changes are expected, but the new provider name (`pure`) must route correctly to `osac.templates.pure_storage`.

## 7. Risks

### 7.1 SMT module availability in the Ansible collection

The `purefa_realm` module is documented but relatively new. If the certified collection version on the Red Hat catalog lags behind upstream, the Realm module may not be available.

- **Owner:** OSAC team
- **Mitigation:** Pin a collection version that includes the Realm module. If unavailable in the certified version, fall back to direct FlashArray REST API calls for Realm operations.

### 7.2 QoS enforcement gap with future NVMe-TCP adoption

QoS parameters (`max_iops`, `max_bandwidth`) are not supported with NVMe volumes in PX-CSI. If a CSP later switches to NVMe-TCP, existing QoS-configured tiers will silently lose enforcement.

- **Owner:** OSAC team
- **Mitigation:** Document the limitation in deployment guides. When NVMe-TCP support is added, validate whether PX-CSI has added QoS support for NVMe volumes.

## 8. Open Questions

### 8.1 What FlashArray API token scope is needed for the admin credential?

The admin token must have permissions to create Realms, Pods, and users. The minimum required role (array_admin, storage_admin, or a custom role) needs to be determined during the design phase.

- **Owner:** OSAC team / Pure Storage SME
- **Impact:** Affects NFR-1 (credential requirements) and deployment documentation.
