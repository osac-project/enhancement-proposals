# Clarification Log — OSAC-55

## Status

- Rounds completed — 6
- Open gaps — 0
- Exit criteria met — Yes

## Round 1 — Tenant web UI

### R1.Q1 — Web UI scope for 0.6

Should tenants be able to create, list, and delete VM snapshots and restore a VM from a snapshot in the OSAC web UI in 0.6? The merged proposal describes the API and illustrates the tenant workflow with CLI commands. [Merged VM Snapshots proposal](https://github.com/osac-project/enhancement-proposals/blob/f4fedae27e65893bfb77c95293d3d53a42a1736d/enhancements/OSAC-55-vm-snapshots/README.md#workflow-description)

#### Answer

Yes. The OSAC web UI is in scope for the tenant snapshot workflow in 0.6.

#### Impact

Include all four actions in the PRD's web UI requirements and acceptance criteria.

#### Decision (D1)

In 0.6, tenants can use the OSAC web UI to create, list, and delete their VM snapshots and restore their VMs from a snapshot.

## Round 2 — VMaaS storage prerequisite

### R2.Q1 — VMaaS storage path

Does the OSAC CSI driver provision the VMaaS disks in scope for this Feature?

#### Answer

The supported VMaaS provisioning path uses the workload cluster's storage provisioner for each disk. The OpenShift Virtualization role creates DataVolumes with the resolved StorageClasses for boot and data disks. The OSAC CSI storage role targets CaaS tenant clusters and requires a guest-cluster kubeconfig. [VM disk provisioning](https://github.com/osac-project/osac/blob/main/osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/create_resources.yaml#L60-L117) · [OSAC CSI deployment guard](https://github.com/osac-project/osac/blob/main/osac-aap/collections/ansible_collections/osac/templates/roles/osac_csi_storage/tasks/ensure_storage_class.yaml#L23-L30)

#### Impact

Under the merged design, KubeVirt needs snapshot and restore support from the CSI driver behind each VMaaS storage class in scope, with a matching VolumeSnapshotClass on the workload cluster. KubeVirt can use this storage capability directly. See D4 for the release sequencing decision. [KubeVirt snapshot prerequisites](https://kubevirt.io/user-guide/storage/snapshot_restore_api/#volumesnapshotclass) · [OSAC-48](https://redhat.atlassian.net/browse/OSAC-48)

## Round 3 — Snapshot consistency

### R3.Q1 — Online snapshot behavior and tenant visibility

Which consistency levels should OSAC support for online snapshots, and what should tenants see when guest quiescing is unavailable or fails?

#### Answer

Use KubeVirt's native best-effort behavior. Let KubeVirt use QEMU Guest Agent quiescing when available, including Windows VSS. Allow the native crash-consistent fallback when the agent is unavailable. Show KubeVirt's snapshot indications, such as `GuestAgent`, `NoGuestAgent`, and any reported quiesce failure, in OSAC snapshot status and the web UI.

#### Impact

- Describe filesystem consistency when the target platform confirms successful guest quiescing. A connected agent establishes availability, and application consistency also depends on cooperating applications. [OpenShift Virtualization snapshot consistency](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/virtualization/backup-and-restore)
- Describe snapshots taken while the VM is stopped as offline snapshots. Reserve the crash-consistent fallback label for a successful online snapshot captured without guest quiescing. [OpenShift Virtualization snapshot indications](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/virtualization/backup-and-restore)
- Verify the indications, errors, and resulting readiness on the OpenShift Virtualization versions targeted for 0.6. The upstream controller can retry a freeze error before taking disk snapshots, and its indication values include `QuiesceTimeout`. [KubeVirt snapshot controller](https://github.com/kubevirt/kubevirt/blob/main/pkg/storage/snapshot/snapshot.go#L496-L513) · [KubeVirt indication values](https://pkg.go.dev/kubevirt.io/api/snapshot/v1beta1#Indication)

#### Decision (D2)

For 0.6, OSAC uses KubeVirt's native best-effort online snapshot behavior. A missing or disconnected guest agent still permits KubeVirt's native crash-consistent snapshot. OSAC exposes the native indications and reports the actual readiness or failure in snapshot status and the web UI. A stopped VM uses native offline snapshot behavior.

## Round 4 — Restore scope and storage dependency

### R4.Q1 — Disks, VM configuration, and eligible storage

Which disks and settings does restore cover, and which storage classes qualify?

#### Answer

Restore covers all persistent boot and data disks backed by CDI DataVolumes or PVCs on snapshot-capable StorageClasses. It also covers the full captured VM configuration, including CPU, memory, devices, and network interfaces. On completion, the OSAC ComputeInstance and Volume records reflect the restored settings and disks, including the original instance type. Any workload-cluster StorageClass qualifies if its CSI driver supports snapshot and restore and the cluster has a matching VolumeSnapshotClass. KubeVirt reports per-volume eligibility.

#### Impact

- Verify per-disk eligibility through the VM's `volumeSnapshotStatuses`, and verify which disks the completed snapshot actually contains through its included and excluded volume lists. [KubeVirt VM status reference](https://kubevirt.io/api-reference/main/definitions.html#_v1_virtualmachinestatus) · [KubeVirt snapshot guide](https://kubevirt.io/user-guide/storage/snapshot_restore_api/#snapshot-a-virtualmachine)
- Validate that the restored VM boots with the captured configuration and disk data and that OSAC reports the restored instance type and volumes. Align record reconciliation and cleanup with the proposed Volume controller ownership of VM disks. [PR #518](https://github.com/osac-project/enhancement-proposals/pull/518)
- The accepted VMaaS networking design fixes a VM's tenant attachment at creation and derives its network interface from that attachment. D6 defines how restore handles a mismatch. [VMaaS networking design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1435-vmaas-networking/design.md#network-attachment-and-validation)

#### Decision (D3)

Restore rolls the source VM back to the captured configuration, including its instance type at snapshot time, and restores all eligible persistent boot and data disks. A storage class is eligible when its CSI driver provides snapshot and restore support and a matching VolumeSnapshotClass is configured on the workload cluster. Once restore completes, the ComputeInstance and Volume records reflect the restored settings and disks.

---

### R4.Q2 — OSAC-48 release sequencing

Does OSAC-48 need to ship before OSAC-55?

#### Answer

OSAC-55 can ship independently. KubeVirt uses the CSI drivers behind the VM's workload-cluster StorageClasses for disk snapshots. OSAC-48 delivers the standalone volume snapshot API and UI.

#### Impact

The PRD should record snapshot-capable workload-cluster storage as the prerequisite for VM disk restore. Jira records a formal blocking link between the two Features. [OSAC-55](https://redhat.atlassian.net/browse/OSAC-55) · [OSAC-48](https://redhat.atlassian.net/browse/OSAC-48)

#### Decision (D4)

OSAC-55 can ship independently of OSAC-48. The storage prerequisite is native CSI snapshot and restore support for the VMaaS disks in scope.

## Round 5 — Provider monitoring, snapshot limits, and CLI

### R5.Q1 — Provider monitoring and per-VM snapshot limits

What monitoring and capacity controls are in scope for 0.6?

#### Answer

Use KubeVirt's native snapshot status and errors to surface storage failures. Providers can use standard Kubernetes ResourceQuotas on the workload cluster. Dedicated OSAC provider storage monitoring and OSAC per-VM snapshot limits are candidates for a later release.

#### Impact

Tenants can see a storage failure on the affected snapshot. Cluster administrators can configure a ResourceQuota to limit the number of snapshot objects in a namespace. This quota counts objects across VMs in that namespace. Physical snapshot storage consumption is a separate backend measurement. [Kubernetes object-count quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/#quota-on-object-count)

#### Decision (D5)

For 0.6, OSAC surfaces native KubeVirt snapshot status and errors and relies on standard Kubernetes quota controls. Dedicated OSAC provider storage monitoring and OSAC per-VM snapshot limits are out of scope.

---

### R5.Q2 — Tenant CLI workflows

Are the tenant snapshot workflows shown in the merged proposal in scope for the OSAC CLI in 0.6?

#### Answer

“I think yes.”

#### Impact

Include the CLI in the draft on that working assumption. Tenants can create a snapshot, list snapshots, inspect an individual snapshot's status or error, delete a snapshot, and restore the source VM from a selected snapshot. [Merged VM Snapshots CLI workflows](https://github.com/osac-project/enhancement-proposals/blob/f4fedae27e65893bfb77c95293d3d53a42a1736d/enhancements/OSAC-55-vm-snapshots/README.md#workflow-description)

## Round 6 — Network attachment conflict during restore

### R6.Q1 — Restore rejection before disk changes

What happens if a snapshot's captured interface configuration conflicts with the source VM's fixed tenant network attachment?

#### Answer

Reject the restore up front, before changing any disks, and tell the tenant which network attachment conflicts.

#### Impact

Include a restore acceptance scenario with a conflicting attachment and multiple disks. Verify that the rejection identifies the attachment and that every boot and data disk retains its pre-restore contents.

#### Decision (D6)

If the captured interface configuration conflicts with the VM's fixed tenant network attachment, OSAC must reject the restore before modifying any disk and return a clear tenant-facing error identifying the conflicting attachment.
