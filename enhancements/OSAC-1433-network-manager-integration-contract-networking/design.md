---
title: network-manager-integration-contract
authors:
  - dmanor@redhat.com
creation-date: 2026-10-04
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: prd.md
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking/design.md
  - Agentless VLAN Fabric Manager Design: /enhancements/OSAC-3664-agentless-vlan-fabric-manager/design.md
  - CUDN EVPN Kubernetes Manager: /enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Network Manager Integration Contract

| Field | Value |
|-------|-------|
| Author(s) | Dan Manor (dmanor@redhat.com) |
| Jira | https://redhat.atlassian.net/browse/OSAC-1433 |
| PRD | [Network Manager Integration Contract PRD](prd.md) |
| Date | 2026-10-22 |

## Contents

- [1. Overview](#1-overview)
- [2. Goals and Non-Goals](#2-goals-and-non-goals)
  - [2.1 Goals](#21-goals)
  - [2.2 Non-Goals](#22-non-goals)
- [3. Motivation and Background](#3-motivation-and-background)
- [4. Design](#4-design)
  - [4.1 Manager types](#41-manager-types)
  - [4.2 Registration and capabilities](#42-registration-and-capabilities)
  - [4.3 Invocation, settings, and secrets](#43-invocation-settings-and-secrets)
  - [4.4 Data channels](#44-data-channels)
  - [4.5 Task input](#45-task-input)
  - [4.6 Task result and errors](#46-task-result-and-errors)
  - [4.7 Ordering, concurrency, retries, and ownership](#47-ordering-concurrency-retries-and-ownership)
  - [4.8 Addressing](#48-addressing)
  - [4.9 Network types and the network segment](#49-network-types-and-the-network-segment)
  - [4.10 Task reference](#410-task-reference)
    - [Fabric `create_virtual_network` / `delete_virtual_network`](#fabric-create_virtual_network--delete_virtual_network)
    - [Fabric `create_subnet` / `delete_subnet`](#fabric-create_subnet--delete_subnet)
    - [Fabric `create_security_group` / `delete_security_group`](#fabric-create_security_group--delete_security_group)
    - [Fabric `apply_network_attachment` / `delete_network_attachment`](#fabric-apply_network_attachment--delete_network_attachment)
    - [Fabric `query_dhcp_lease`](#fabric-query_dhcp_lease)
    - [Fabric `create_external_ip_pool` / `delete_external_ip_pool`](#fabric-create_external_ip_pool--delete_external_ip_pool)
    - [Fabric `create_external_ip` / `delete_external_ip`](#fabric-create_external_ip--delete_external_ip)
    - [Fabric `attach_external_ip` / `detach_external_ip`](#fabric-attach_external_ip--detach_external_ip)
    - [Fabric `create_nat_gateway` / `delete_nat_gateway`](#fabric-create_nat_gateway--delete_nat_gateway)
    - [Fabric `reserve_cluster_ingress_ip` / `release_cluster_ingress_ip`](#fabric-reserve_cluster_ingress_ip--release_cluster_ingress_ip)
    - [Fabric `create_fabric_domain` / `delete_fabric_domain` (optional)](#fabric-create_fabric_domain--delete_fabric_domain-optional)
    - [OSAC Kubernetes Manager tasks (OSAC-internal)](#osac-kubernetes-manager-tasks-osac-internal)
  - [4.11 Conformance tests](#411-conformance-tests)
  - [4.12 Security, RBAC, and tenancy](#412-security-rbac-and-tenancy)
  - [4.13 Risks and drawbacks](#413-risks-and-drawbacks)
  - [Edge cases that need handling](#edge-cases-that-need-handling)
    - [Restarts and job tracking](#restarts-and-job-tracking)
    - [Updates while a job runs](#updates-while-a-job-runs)
    - [Network segment acceptance](#network-segment-acceptance)
    - [Registration and image](#registration-and-image)
    - [Kubernetes Manager hub network](#kubernetes-manager-hub-network)
- [5. Interface Changes](#5-interface-changes)
- [6. Alternatives Considered](#6-alternatives-considered)
- [7. Observability and Monitoring](#7-observability-and-monitoring)
- [8. Impact and Compatibility](#8-impact-and-compatibility)

## 1. Overview

OSAC networking has two manager types: the **Fabric Manager**, written by a provider (or OSAC), and the **Kubernetes Manager**, written by OSAC. A manager is an Ansible role with a fixed task set. OSAC picks each task, passes it a fixed input, checks its result, and orders the tasks of both managers, so a conforming Fabric Manager needs no OSAC code changes.

This is the complete contract for Fabric Manager authors; §4.10 also defines OSAC's internal Kubernetes Manager tasks. The [Unified Networking Design](/enhancements/OSAC-1433-unified-networking/design.md) defines what the resources mean to tenants; the VMaaS, BMaaS, and CaaS designs define when each workload attaches and detaches. §4.1 to §4.13 describe the normal flow; [Edge cases that need handling](#edge-cases-that-need-handling) lists restarts, races, and partial failures with their proposed handling.

## 2. Goals and Non-Goals

### 2.1 Goals

- A Fabric Manager author can implement a manager from this document alone.
- A provider supplies the Fabric Manager with no provider-specific OSAC code.
- Any conforming Fabric Manager works with any OSAC Kubernetes Manager whose network type it declares (§4.9).
- A conformance suite proves correct behavior; registration and successful results alone do not.

### 2.2 Non-Goals

- Provider-written Kubernetes Managers.
- Network types other than `evpn` in this release.
- Deployments outside Unified's [deployment](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary) support boundaries.
- More than one network attachment per workload.
- Network-behavior conformance tests; they are a [follow-up](testplan.md#follow-up-network-behavior-tests) to §4.11.

## 3. Motivation and Background

Providers run OSAC on networking they already own, and OSAC cannot implement every backend, so a fixed contract lets them plug in their fabric. OSAC writes every Kubernetes Manager, so it takes the Fabric's segment values as a typed task result that it validates, stores, and passes on.

## 4. Design

### 4.1 Manager types

| Manager type | Configures | Selected by |
|---|---|---|
| Fabric Manager (provider's) | The physical fabric: segments, routing, DHCP for physical interfaces, NAT, external addresses, bare-metal port moves, SecurityGroup policy objects bound to bare-metal ports and VM addresses. | `NetworkClass.fabric_manager` (required) |
| Kubernetes Manager (OSAC's) | Hub networking, where VMs run: the VMs' primary overlay network, overlay addressing, SecurityGroup policy objects bound to VM pods. | `NetworkClass.k8s_manager` (optional; required for VMs) |

- OSAC ships its Kubernetes Managers in its own `osac.*` collections in its base execution environment image (§4.3); this release has `cudn_evpn`, type `evpn` (§4.9).
- OSAC calls each manager separately. Managers never call each other and never write OSAC workload resources (ComputeInstances and their VMs, BareMetalInstances, ClusterOrders) or OSAC networking CRs.
- At create, OSAC records each selected manager as `{name, ansibleRole}` in the CR's `status.networkManagers.fabric` and `status.networkManagers.kubernetes`; a VirtualNetwork also records the NetworkClass's `network_type` (§4.2) in `status.networkType`. Every later task, including delete, uses these, so a delete reaches the backend that created the state even if a registration ConfigMap is later replaced.
- A deployment has exactly one NetworkClass. Its spec (`fabric_manager`, `k8s_manager`, `spec.defaults`, `spec.east_west_capabilities`, and `spec.address_plan`) is immutable after creation; only its status changes, written by OSAC. To change anything else, follow [Replacing the NetworkClass](/enhancements/OSAC-1433-default-networking/design.md#replacing-the-networkclass).
- The NetworkClass gates and guards networking resources: VirtualNetwork and ExternalIPPool creates are rejected with `FAILED_PRECONDITION` until the NetworkClass is READY, and its delete is rejected with `FAILED_PRECONDITION` while any VirtualNetwork or ExternalIPPool exists ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates), [Deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)); every other networking resource depends on one of these, so none can exist without a READY NetworkClass.
- A VirtualNetwork takes the managers from the NetworkClass at create; an ExternalIPPool takes only the Fabric Manager, because only Fabric tasks run on pools and their children. Every other resource is a **child** of a parent: a Subnet, SecurityGroup, NATGateway, or FabricDomain of its VirtualNetwork; a NetworkAttachment of its Subnet; an ExternalIP of its ExternalIPPool; an ExternalIPAttachment of its ExternalIP. A child copies its parent's managers (under a VirtualNetwork, also the network type), except a NATGateway, which records only the Fabric Manager, because only Fabric tasks run on it.
- A **NetworkAttachment** is OSAC's internal hub CR for one workload interface's attachment to one Subnet and its SecurityGroups, made from the workload's `network_attachment` field; its `id` is the target's API ID ([Unified — NetworkAttachment](/enhancements/OSAC-1433-unified-networking/design.md#networkattachment) defines it). §4.10 states when each workload service creates and deletes it.
- An **overlay** interface is a VM interface on the Subnet's hub network: the Kubernetes Manager attaches it, and both managers bind it to its SecurityGroups. A **physical** interface is a bare-metal host port, attached and bound by the Fabric Manager only. "Attachment" always means a NetworkAttachment; an ExternalIPAttachment is always named in full.
- A **workload service** is VMaaS (VMs), BMaaS (bare-metal servers), or CaaS (clusters).
- An **API ID** is the stable ID the fulfillment service (OSAC's API server) assigns to a resource, never the CR name or `metadata.uid`. API IDs are lowercase UUIDs (36 characters), and an API ID is never reused, so a manager can derive backend names from it.
- A **task** is one named operation from §4.10 (for example `create_subnet`): one task file in the manager's Ansible role, run as one AAP job (§4.3).
- A **manager design** is the document published with a manager's role for installers (OSAC never reads it). It lists the manager's environment variables (§4.3), network types (§4.9), documented no-ops, implementation limits (§4.7), installation prerequisites, and hub permissions (§4.12). OSAC publishes its own managers' designs as enhancements here (for example the [Agentless VLAN Fabric Manager](/enhancements/OSAC-3664-agentless-vlan-fabric-manager/design.md) and the [CUDN EVPN Kubernetes Manager](/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md)); other providers publish theirs where they choose.
- The **hub** is the one management cluster that runs the OSAC operator, the OSAC CRs, AAP, and the VMs. The **hub networking namespace** holds the networking CRs.
- A **documented no-op** is a task, or part of a task, that changes nothing and that its manager design describes as a no-op. A no-op task still returns a valid result.

### 4.2 Registration and capabilities

A manager registers with one ConfigMap in the OSAC operator's namespace (the namespace of the OSAC Helm release):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: network-manager-acme-fabric
  namespace: osac-operator
  labels:
    osac.openshift.io/network-fabric-manager: "true"   # Kubernetes Manager: osac.openshift.io/network-k8s-manager: "true"
immutable: true
data:
  name: acme_fabric            # the value NetworkClass selects
  ansible_role: acme.network.fabric
  network_types: evpn          # optional (§4.9); also optional: capabilities (table below)
  description: "optional free text"
```

- OSAC finds a manager by `data.name` and the manager-type label; `metadata.name` can be anything.
- `name` uses only lowercase letters, digits, and underscores, and starts with a letter.
- `ansible_role` is the role's fully qualified name (`<namespace>.<collection>.<role>`). A provider's role must not be in an `osac.*` collection: OSAC cannot check this, and OSAC's own `osac.*` collections shadow a provider collection of the same name (§4.3). Fabric Managers that OSAC ships are in `osac.*`.
- `capabilities` and `network_types` are comma-separated, without spaces. A key with an empty value counts as absent. Without `network_types` (§4.9), no Kubernetes Manager can pair with the Fabric Manager, so the deployment runs no VMs.
- The OSAC installer creates each OSAC Kubernetes Manager's registration in this format, with an `osac.*` `ansible_role` and a required `network_type` (exactly one type; `cudn_evpn`: `evpn`).
- `immutable: true` makes Kubernetes reject changes to `data`; to change it, delete the registration and create a new one.
- OSAC resolves a NetworkClass that is not READY when its CR is created and whenever a manager registration is added or removed. It never resolves a READY NetworkClass again, and resources use their recorded managers (§4.1), so adding or removing a registration affects only a NetworkClass that is not READY.

The OSAC operator sets the NetworkClass to FAILED, with the reason in `status.message`, when:
- the selected name matches no ConfigMap with the manager type's label, or more than one;
- a matched ConfigMap carries both manager-type labels;
- `name` or `ansible_role` is missing or malformed;
- the registration does not set `immutable: true`;
- `capabilities`, `network_types`, or `network_type` contains an unknown value;
- a registration has a `data` key its manager type does not define (both types: `name`, `ansible_role`, `description`; Fabric also `capabilities` and `network_types`; Kubernetes also `network_type`), so a typo such as `networkTypes` fails;
- a `capabilities` or `network_types` list has an empty or repeated value;
- the Kubernetes Manager has no `network_type`, an `ansible_role` whose collection namespace is not `osac`, or a `network_type` not in the Fabric Manager's `network_types` (the message names both);
- NetworkClass sets `spec.east_west_capabilities.supports_east_west_ethernet` and the Fabric Manager does not declare `eastWestEthernet`.

On success, the NetworkClass status records the selected `network_type` (empty without a Kubernetes Manager).

| Capability | Manager type | Meaning |
|---|---|---|
| `eastWestEthernet` | Fabric | The manager implements `create_fabric_domain` and `delete_fabric_domain` (§4.10). |

IPv4 is mandatory and is not a capability. The list is fixed because OSAC acts on each value.

### 4.3 Invocation, settings, and secrets

OSAC runs every task as an Ansible Automation Platform (AAP) job, through one generic playbook:

```yaml
- name: Run the selected network manager task
  ansible.builtin.include_role:
    name: "{{ osac_job_vars.manager.ansible_role }}"
    tasks_from: "{{ osac_job_vars.task }}"
```

Before `include_role`, the playbook checks that the role and its task file exist in the image. If not, it publishes `osac_error: {message: "role <ansible_role> or task file <task> not found in the execution environment", retryable: true}` and fails, so fixing the image recovers the resource.

- Jobs run in an execution environment image built on OSAC's image (which already holds OSAC's Kubernetes Managers), with the provider's collection installed in `/usr/share/ansible/collections`:

  ```dockerfile
  FROM ghcr.io/osac-project/osac-aap:<base tag>   # the release's Helm value aap.bootstrap.image
  USER root
  COPY acme-network-1.0.0.tar.gz /tmp/
  RUN ansible-galaxy collection install --no-deps -p /usr/share/ansible/collections /tmp/acme-network-1.0.0.tar.gz
  # also install the collection's Python and system dependencies
  USER 1000
  ```

  - The installer Helm value `aap.configAsCode.eeImage` names the image. AAP uses it as the execution environment and job pod image of every OSAC instance group and runs the generic playbook from OSAC's project (the OSAC repository) in it. The image is rebuilt for each OSAC release, so running jobs need no Galaxy server or network access.
  - AAP's `ANSIBLE_COLLECTIONS_PATH` always includes `/usr/share/ansible/collections`, searched after the collections next to OSAC's playbooks, so `include_role` finds the provider's role by its fully qualified name with no OSAC configuration change, and OSAC's own collections always win.
  - Provider tasks call modules by fully qualified name (for example `kubernetes.core.k8s`). OSAC's base image has ansible-core 2.19 or later, OSAC's collections and their dependencies (including `ansible.utils`, `community.general`, and `kubernetes.core`), and the Python package `netaddr`; the provider adds only what its collection needs.
- The role has the task files that [§4.10 Enabled services](#410-task-reference) requires.
- OSAC runs only tasks in the manager type's fixed set; any other task fails before a job starts and is never sent to the other manager.
- Providers add no AAP job templates; OSAC adds one only when the fixed task set grows. Every OSAC job template sets `ask_labels_on_launch: true`, so each job gets its own label (§4.7).
- Networking jobs run in the AAP instance group `<prefix>-networking-operations-ig`. Its job pods load, as environment variables, settings from the ConfigMap `network-fulfillment-ig` (optional) and credentials from the Secret `network-fulfillment-ig` (required, may be empty), both in the OSAC namespace (the namespace of the OSAC Helm release, where AAP runs). The installer writes both on every install and rollout from the Helm values `aap.instanceGroups.networkFulfillment.config` and `aap.instanceGroups.networkFulfillment.secret` (maps of keys to values), with `aap.instanceGroups.networkFulfillment.enabled: true`; nobody edits them with `kubectl`. Each manager prefixes the variable names it reads with its registration `name` in upper case (for example `ACME_FABRIC_API_URL`). There is no per-manager API field and no AAP Credential ID.
- Every role in the instance group can read all these values; the instance group is the trust boundary.
- A CA bundle can come through the ConfigMap; a task that needs it as a file writes the file inside the job. Tasks write private keys with mode `0600` and delete them after use.
- Tasks reach the hub with the job pod's in-cluster service account (networking CRs, VM networks). Task input has no cluster identifier.
- Every hub object a manager creates carries, where Kubernetes allows labels, `osac.openshift.io/owner-kind: <kind>` (lowercase kind, for example `subnet`) and `osac.openshift.io/owner-id: <api-id>` of its OSAC resource, so cleanup finds objects by owner, not by name. The resource's delete task removes them. A Fabric Manager creates hub objects only in the hub networking namespace, none cluster-scoped.
- Secrets never appear in `osac_job_vars`, `osac_result`, or task logs.

### 4.4 Data channels

Managers exchange no data directly. There are two channels:

| Channel | From → to | Carries |
|---|---|---|
| `osac_job_vars` (task input) | OSAC → manager | Everything OSAC owns, computes, or stores (§4.5): snapshots, target, SecurityGroup rules, address layout (§4.8), network type and segment (§4.9), task-specific inputs (§4.10). |
| `osac_result` and `osac_error` (task result) | Manager → OSAC | Only the typed outputs OSAC acts on (§4.10), or the error (§4.6). |

### 4.5 Task input

Each task receives one variable, `osac_job_vars`:

```yaml
osac_job_vars:
  manager: {name: acme_fabric, type: fabric, ansible_role: acme.network.fabric}   # type: fabric | kubernetes
  task: create_subnet
  tenant: <tenant API ID>               # from the CR's osac.openshift.io/tenant annotation; absent for ExternalIPPool tasks
  resource: <snapshot of the resource the task acts on>
  # plus the keys listed in the task's section of §4.10, for example
  # virtual_network, subnet, ipam, network_type, network_segment, target, network_attachment
```

A **snapshot** has this shape for every kind:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: Subnet
id: <stable fulfillment API ID>
metadata: {name: <CR name>, namespace: <hub namespace>, uid: <CR UID>, generation: 3}
spec: {...}
```

- `id` is the ownership key; `metadata.uid` and `metadata.generation` identify the CR version the input came from.
- OSAC captures the whole input once, when it starts the first job of a create, apply, attach, or reserve, and stores it in the CR's `status.taskInput`, one stored input per CR for all its managers. Every retry and the matching delete, detach, or release get that stored input, plus `manager`, `task`, and the keys OSAC adds at launch from recorded status (§4.9). Only one update stores a new input: a SecurityGroup rule update ([SecurityGroup](#fabric-create_security_group--delete_security_group)). One key is added to a stored input later: a VM's address, `network_attachment.interface.ipv4_address`, before the first [Fabric overlay apply](#fabric-apply_network_attachment--delete_network_attachment); the Kubernetes Manager ignores it.
- A snapshot's `spec` has only the fields its §4.10 section lists, in CRD camelCase (`spec: {}` when none are listed), so no CR secret (for example a pull secret or user data) reaches a manager. A key that §4.10 does not list for a task is absent from its input.
- `osac_job_vars` keys and typed outputs use snake_case.
- Canonical values: an IPv4 address is dotted decimal without leading zeros or a prefix length (for example `10.0.1.17`); a CIDR has zero host bits; a MAC address is lowercase and colon-separated.

### 4.6 Task result and errors

A task with a typed output (§4.10) publishes it with `set_stats` before it ends. A task without one publishes nothing; a successful play is its result.

```yaml
- name: Return manager result to OSAC
  ansible.builtin.set_stats:
    aggregate: false
    per_host: false
    data:
      osac_result:          # only the typed outputs defined for the task in §4.10
        dhcp_lease: {ip_address: 10.0.1.130, mac_address: aa:bb:cc:dd:ee:ff}
```

A task fails by failing the play (for example with `ansible.builtin.fail`), and may first publish `osac_error` the same way:

```yaml
osac_error: {message: "no free VLAN left in pool tenant-vlans", retryable: false}
```

- OSAC reads only the `osac_result` and `osac_error` keys from the job's `set_stats` artifacts, and only from the AAP job it launched for that task and input, so a result needs no identity fields.
- A task may leave out an optional output. When the play fails, OSAC ignores any `osac_result`.
- OSAC rejects a result with a missing required output, a key not defined for the task, or a malformed typed output. A rejected result fails the task, and OSAC changes nothing.
- An `osac_error` that is not exactly `{message, retryable}`, with a non-empty string and a boolean, counts as no `osac_error`, so the failure is final; OSAC adds "malformed osac_error" to the entry's message.
- `retryable` is the only field OSAC acts on. OSAC reruns a failed create, apply, attach, reserve, or `query_dhcp_lease` job when the job published `osac_error.retryable: true`, or when AAP ended the job before the play could report: AAP status `error` (for example the pod was evicted) or the AAP job timeout (§4.7). [Edge cases](#restarts-and-job-tracking) covers lost, unstarted, and hand-cancelled jobs.

  Every other failure is **final** (`retryable: false`, no `osac_error`, or a rejected result): OSAC stops, keeps the resource not Ready, and shows the message; the owner deletes the resource. OSAC never retries it, also not after a backend repair; only a new input starts a new attempt (a SecurityGroup rule update, §4.5). `query_dhcp_lease` never changes `Ready` ([`query_dhcp_lease`](#fabric-query_dhcp_lease)).
- A manager therefore wraps the task in `block`/`rescue`; `rescue` publishes `osac_error` with `retryable: true` for a transient failure (for example a backend API timeout), else `retryable: false`, then fails the play.
- A missing or malformed setting (§4.3) is `retryable: true`, with a message naming the setting, because an administrator can fix it and job pods read settings at start.
- On ansible-core, `no_log` does not hide `ansible_failed_result`, which holds the module arguments (for example an Authorization header). A task never puts it, or its `invocation`, into `osac_error`, a log, or a failure message.
- `message` says in plain words what failed and what to fix. OSAC shows it in the resource's status and logs, and never parses it.
- Delete, detach, and release tasks are the exception: OSAC retries them with backoff after every failure, whatever `osac_error` says, and the finalizer stays until one succeeds.

### 4.7 Ordering, concurrency, retries, and ownership

- **Order.** For a VirtualNetwork, Subnet, or SecurityGroup, create (and a SecurityGroup rule update) runs the Fabric task, then the Kubernetes task; delete runs in reverse. For a VirtualNetwork or Subnet this is required, because the Kubernetes Manager uses the Fabric's segment (§4.9). A VM's NetworkAttachment applies on the Kubernetes Manager first, because the Fabric binds the VM's address, which exists only once the VM runs; its delete runs Fabric, then Kubernetes. A child (§4.1) is created after its parent and deleted before it.
- **Readiness.** A VirtualNetwork, Subnet, or SecurityGroup is Ready once the create task of every manager in its `status.networkManagers` succeeds. A NetworkAttachment is Ready once the apply of every manager that handles its interface succeeds: overlay, the Kubernetes and then the Fabric apply; physical, the Fabric apply. Any other resource is Ready once its Fabric task (§4.10) succeeds.
- **Concurrency.** OSAC runs at most one job at a time per resource, task, and manager (a NetworkAttachment is one workload interface), and at most one Subnet task at a time per VirtualNetwork, because sibling Subnets can share backend objects. Jobs of distinct resources may run in parallel, and so may different tasks on one resource unless the order above applies. Managers take no locks. When two tasks of distinct resources can change one backend object (for example two `create_external_ip` in one pool, two `reserve_cluster_ingress_ip` on one Subnet, the NAT rules of one VirtualNetwork, one VNI range, or one host's ports), the manager allocates atomically in its backend, or fails with `retryable: true` on a conflict so OSAC retries with backoff. A backend that can neither allocate atomically nor detect the conflict is not supported in this release; TC-CONCURRENCY-01 fails it.
- **Job tracking.** OSAC tracks each job in the CR's `status.jobs`, a list of entries `{task, manager, attempt, state, jobID, message}`, for example `{task: apply_network_attachment, manager: kubernetes, attempt: 1, state: Succeeded, jobID: "1234", message: ""}`:
  - `manager` is the manager type, or `none` for a job that is not a manager task; `attempt` counts the task's launches. Only the latest entry per task and manager is kept.
  - `state` is `Running`, `Retrying` (failed, retry scheduled), `Succeeded`, `Failed` (final), or `Cancelled` (OSAC cancelled the job for a delete, or a retry never launched; never a failure reason).
  - `message` is the job's `osac_error` message, or the AAP failure text if it published none.

  Every networking hub CR, the ClusterOrder for its networking jobs, and the ComputeInstance for its provision and deprovision jobs use this shape (Go type `NetworkJobStatus`). OSAC never removes an entry. For each launch OSAC:
  1. increments the `attempt` of the task's entry and writes `state: Running` with an empty `jobID`;
  2. launches the job with the AAP label `osac-<task>-<manager>-<API ID>-<attempt>` (`<manager>`: `fabric`, `kubernetes`, or `none` for a job that is not a manager task), creating the label in OSAC's AAP organization if missing;
  3. writes `jobID` when AAP returns it.

  OSAC starts no create, apply, attach, reserve, or `query_dhcp_lease` job while the resource, NetworkAttachment, or target workload has a deletionTimestamp. [Edge cases](#restarts-and-job-tracking) covers restarts and failed launch calls.
- **Cancel on delete.** A delete cancels in AAP every running job of the resource that is not part of the delete (create, apply, attach, reserve, or `query_dhcp_lease`), and a pending retry. Once AAP reports the job ended, OSAC sets its entry to `Cancelled`, never uses its result, and starts the delete without waiting for the create's backend work to finish (Ownership). A delete also cancels a running workload provision or install job (VMaaS `provision`, a `manager: none` entry in `status.jobs`; CaaS core install, in the ClusterOrder `status.provisioningJobs`), also with provider networking disabled. Other `manager: none` jobs (the CaaS guest endpoint jobs) follow their service design.
- **Timeout.** Every OSAC networking job template sets an AAP job timeout of 60 minutes. A job that AAP ends at the timeout (OSAC reads this from the AAP job record: status `failed` with AAP's timeout job explanation) fails with the entry message 'job timed out after 60 minutes' and is retried (§4.6); a delete, detach, or release is retried like every failed delete.
- **Retries.** OSAC retries only as §4.6 allows, and only after the previous job has ended. The wait starts at two minutes and doubles after each failure, up to thirty minutes. There is no attempt limit: a resource whose create, apply, attach, or reserve keeps failing retryably stays `Ready=False`, reason `Progressing` (API state PENDING, with the message and the next retry time, [Unified — Status](/enhancements/OSAC-1433-unified-networking/design.md#status)), until a job succeeds or the resource is deleted. Exceptions: during a SecurityGroup rule update, a READY group stays `Ready=True`, reason `Updating` ([Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup)); a retryable `query_dhcp_lease` failure is retried after 30 seconds, and from the 20th attempt (about 10 minutes) after 5 minutes.
- **Idempotency.** Every task is idempotent by `resource.id` and its input: repeating a create or apply leaves the same backend state, with no duplicate objects, addresses, or policy. OSAC updates a resource by running its create or apply again with the same `resource.id` and a new input (such as a SecurityGroup rule update); the task makes the backend state match the new input, creating what is missing and changing what differs, and keeps what it allocated for the ID, so its typed output stays the same. A task can be stopped at any point (for example by a cancel), so its next run, or the delete, handles partial state. A delete finds its state by API ID, removes what it finds, and reports success only when cleanup is complete. It succeeds when the state is already absent, including when the create never ran, never succeeded, or was cancelled.
- **Finalizers and readiness.** A failed create or apply keeps the resource or NetworkAttachment not Ready, and the workload does not proceed. OSAC keeps the finalizer on a resource or NetworkAttachment until the delete task of every manager whose create started has succeeded. A manager whose create, apply, attach, or reserve never started (it has no `status.jobs` entry) gets no delete, detach, or release; with none started, OSAC removes the finalizer without a task. So after OSAC rejects a Subnet's segment (§4.9), the Subnet delete runs only the Fabric `delete_subnet`, and the segment rule never blocks a delete. A failed NetworkAttachment delete blocks ComputeInstance deletion and bare-metal deprovisioning.
- **Provider networking disabled.** OSAC runs no networking task, and a delete removes the finalizer without a task ([Unified — Provider networking control](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control)).
- **Ownership.** Managers key backend objects by stable API IDs (a NetworkAttachment's by `target.id`), never by a display name, CIDR, IP, MAC, AAP job ID, or Kubernetes UID. A missing hub CR is no reason to delete or reallocate backend state. A delete wins over every create, apply, attach, or reserve of the same API ID that a cancelled job may still have in flight (Cancel on delete): once the delete has succeeded, a late backend write for that API ID leaves no state. For example, the backend applies the requests of one API ID in order, or the delete records a tombstone for the API ID (never reused, §4.1) that turns a later write for it into a no-op.
- **Isolation.** Separate VirtualNetworks may have identical or overlapping CIDRs, even within one tenant ([Unified — VirtualNetwork](/enhancements/OSAC-1433-unified-networking/design.md#virtualnetwork) and [Subnet](/enhancements/OSAC-1433-unified-networking/design.md#subnet) define the CIDR rules, routing between sibling Subnets, and each Subnet's L2 domain). Managers key routing, policy, NAT, address lookup, and cleanup by VirtualNetwork and Subnet API ID, so deleting one resource's backend state never removes another's, even with equal addresses. A manager never relies on a workload service boundary, a namespace, or a separate backend API instance for isolation.
- **Implementation limits.** A Fabric Manager that cannot build a Subnet fails `create_subnet` with `retryable: false`. An OSAC Kubernetes Manager that cannot build a Subnet because of an implementation limit (for example [`cudn_evpn`'s](#osac-kubernetes-manager-tasks-osac-internal)) lets its Subnet tasks succeed without changes. It fails each attachment apply on that Subnet with `retryable: false` and a message naming the limit. The attachment delete succeeds, because nothing was created. OSAC does not reject such a Subnet, or a VM on it, at create: only the Kubernetes Manager knows which Subnets it can serve (for `cudn_evpn`, which Subnet owns the hub network), so no fulfillment check is possible; the attachment's final failure names the limit.

### 4.8 Addressing

OSAC computes each Subnet's address layout from the deployment's address plan and passes it to both managers as `osac_job_vars.ipam`. The plan gives the shares `overlay`, `fabric`, and `lbVip` of the Subnet's addresses; [Unified — Subnet address layout](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout) defines the setting, its validation, and its defaults. Each manager allocates only from its own range.

**Layout.** From the Subnet's network address, OSAC places the ranges in the fixed order overlay, fabric, lbVip; each range has its share of the addresses. Each list is the fewest aligned CIDRs that cover its range exactly, in ascending order; a share of 0 gives `[]`.

```yaml
ipam:                                    # Subnet 10.0.1.0/24, plan overlay 0.5, fabric 0.25, lbVip 0.25
  gateway_ipv4: 10.0.1.1
  overlay_ipv4_cidrs: [10.0.1.0/25]
  physical_ipv4_cidrs: [10.0.1.128/26]
  lb_vip_ipv4_cidrs: [10.0.1.192/26]
```

```yaml
ipam:                                    # Subnet 10.0.1.0/24, plan overlay 0.75, fabric 0.25, lbVip 0 (VMaaS only)
  gateway_ipv4: 10.0.1.1
  overlay_ipv4_cidrs: [10.0.1.0/25, 10.0.1.128/26]
  physical_ipv4_cidrs: [10.0.1.192/26]
  lb_vip_ipv4_cidrs: []
```

| Key | Rule | Used by |
|---|---|---|
| `gateway_ipv4` | The Subnet's network address plus one, in every plan. | Router for every workload on the Subnet, served only by the Fabric Manager (§4.9). |
| `overlay_ipv4_cidrs` | The `overlay` share. Not empty exactly when the Subnet has a Kubernetes Manager (§4.1), which is also exactly when the Fabric input has `network_type` (§4.9). | VM addresses from the Kubernetes Manager. |
| `physical_ipv4_cidrs` | The `fabric` share. | The Fabric Manager's range: Fabric DHCP for physical interfaces (bare-metal servers, CaaS workers) and the provider's own devices on the Subnet (router ports beyond the gateway, appliances, its DHCP server). With `[]`, the Subnet has no Fabric DHCP and no provider device besides the gateway. |
| `lb_vip_ipv4_cidrs` | The `lbVip` share. | LoadBalancer VIP reservations (the CaaS guest ingress address). Only the Fabric's `reserve_cluster_ingress_ip` (§4.10) allocates from it: no DHCP, VM allocator, or hub address pool. |

- OSAC computes the layout once, at Subnet create, and records it in `Subnet.status.ipam`. Every later task, including delete, gets the recorded layout, because addresses in use cannot move under running workloads.
- Any list may be `[]`; Fabric tasks accept `[]` for `physical_ipv4_cidrs` and `lb_vip_ipv4_cidrs`. OSAC never runs a task that allocates from an empty range: the address plan gives every Subnet the ranges of the services enabled at its create ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).
- The ranges are allocation pools on one L2 segment, not separate networks: for example, Fabric DHCP gives a bare-metal server an address from `physical_ipv4_cidrs` with the Subnet's mask and router `gateway_ipv4`.
- No allocator hands out the network address, the broadcast address, or `gateway_ipv4`, whatever range they fall in (the network address and the gateway fall in the first non-empty range, the broadcast address in the last).
- Every address a manager uses itself on the Subnet (router ports, node or management addresses, its DHCP server) is `gateway_ipv4` or comes from its own range. OVN-Kubernetes' infrastructure addresses (for example the management port `.2`) fall in the overlay range, so `cudn_evpn` only sets the network's `reservedSubnets` to every CIDR outside `overlay_ipv4_cidrs`.
- Each DHCP server answers only its own manager's interfaces (Fabric DHCP only the MACs of physical attachments, §4.10; the Kubernetes Manager's DHCP only the VM interfaces it attached), because VMs and hosts share one L2 segment.
- Every CIDR of a layout has at least 16 addresses, because the fulfillment service rejects a Subnet whose prefix length is too long for the plan ([Unified — Subnet address layout](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout)).
- Workloads get their address, the Subnet's prefix, `gateway_ipv4` as router, and DNS resolvers through DHCP from the manager that owns their interface; managers never write static addresses into guests or hosts. The provider chooses the Fabric DHCP resolvers; on a Subnet with CaaS workers they resolve the provider's management host names and the public zone `DNS_ZONE` ([CaaS — Infrastructure Needed](/enhancements/OSAC-1436-caas-networking/design.md#infrastructure-needed)); `cudn_evpn` gives VMs the resolvers of its setting `CUDN_EVPN_DNS_RESOLVERS` (§4.3; comma-separated IPv4 addresses), which the Cloud Infrastructure Admin sets at installation to the agreed DNS resolver addresses ([CUDN EVPN design](/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md)). The provider makes both reachable from the Subnet. VMaaS reads the VM address from the VirtualMachineInstance status; BMaaS calls `query_dhcp_lease`.

### 4.9 Network types and the network segment

A **network type** names the multi-tenancy technology that isolates each Subnet as its own segment (and each VirtualNetwork as its own routing domain). It must run on both sides, the provider fabric and the hub (OpenShift), so a Subnet stays one isolated segment end to end. The list is fixed per OSAC release; a new type (for example `vlan`) comes with the OSAC release that defines its schema and its OSAC Kubernetes Manager. This release has one: `evpn`, an EVPN control plane with a VXLAN data plane (OVN-Kubernetes `transport: EVPN`), served by `cudn_evpn`.

OSAC adds two keys at launch from recorded status, never stored in `status.taskInput` (§4.5); both never change once recorded, so every retry and delete gets the same input:
- `network_type`, from the resource's `status.networkType`, to Fabric VirtualNetwork and Subnet tasks when the resource records a Kubernetes Manager (§4.1); otherwise absent.
- `network_segment`, from the Subnet's `status.networkSegment`, to every Kubernetes task of the Subnet and its NetworkAttachments.

**Network segment.** Exactly when its input has `network_type`, Fabric `create_subnet` returns:

```yaml
network_segment: {type: evpn, l2_vni: "{{ l2_vni | int }}", l3_vni: "{{ l3_vni | int }}"}   # for example 10100 and 20001; Ansible renders "{{ x | int }}" as an integer
```

- OSAC accepts it only when it has exactly the keys `type`, `l2_vni`, and `l3_vni`; `type` equals `network_type`; and `l2_vni` and `l3_vni` are different YAML/JSON integers from 1 to 16777215 (a string is rejected). Without `network_type`, `network_segment` is an undefined key.
- OSAC compares it with the segments of every other Subnet CR whose Fabric `delete_subnet` has not succeeded. It rejects (§4.6) an `l2_vni` equal to any of their VNIs, an `l3_vni` equal to one of their `l2_vni` or to another VirtualNetwork's `l3_vni`, and an `l3_vni` that differs from a sibling Subnet's. When every conflict is with Subnets whose Fabric `delete_subnet` has started and not yet succeeded (it is running, waiting for a retry, or it has ended and OSAC has not processed it yet), OSAC rejects nothing yet: it waits until those deletes succeed, then checks again, because the Fabric frees a VNI inside its delete job (Fabric duties, below). While a Subnet waits, its Fabric `create_subnet` entry does not hold its VirtualNetwork's Subnet-task slot (§4.7 Concurrency), so a sibling's delete can still run. The tenant sees only the broken rule (for example "VNI already in use"), never VNIs or other resources' IDs; the details go to the operator log. [Edge cases](#network-segment-acceptance) covers parallel results.
- OSAC accepts a segment once per Subnet; a later result that differs is rejected and the stored value stays. It writes the accepted value to the Subnet's `status.networkSegment` (`{type, l2Vni, l3Vni}`) in the same status update that sets the Fabric `create_subnet` entry to `Succeeded`, and keeps it only there, never in the fulfillment database or the API. While it is absent, OSAC starts no Kubernetes create or apply of the Subnet or its NetworkAttachments.

**Fabric duties for `evpn`.** The Fabric Manager is the only gateway for every workload on the Subnet, VMs included. With `evpn`, it:
- in `create_virtual_network`, gives the routing domain an IP-VRF whose VNI is the VirtualNetwork's `l3_vni`, and extends it to the hub nodes;
- in `create_subnet`, gives the segment a MAC-VRF whose VNI is the Subnet's `l2_vni`, extends it to the hub nodes, and returns `l2_vni` and the VirtualNetwork's `l3_vni` (the same for every Subnet of one VirtualNetwork);
- extends a VRF to the hub nodes by importing and exporting its route target `<hub AS>:<VNI>` over the EVPN peering with the hub nodes (§4.12), where the hub AS is the one BGP AS of every hub node; OSAC passes no route target. When the hub AS is above 65535, every VNI is at most 65535;
- serves `gateway_ipv4` as an anycast gateway on every leaf that carries `l2_vni`, reachable from the hub nodes over the MAC-VRF: it answers ARP for it arriving over `l2_vni`, advertises the gateway's MAC/IP in an EVPN route as usual, and routes the Subnet's traffic in the IP-VRF. `cudn_evpn` serves no gateway: its network has no OVN router port, and its DHCP gives VMs `gateway_ipv4` as router;
- while a physical port is on the Subnet, advertises the MAC/IP of what is behind it (the host's addresses and a Cluster's guest ingress address, §4.10) like any EVPN host; the physical delete withdraws them;
- keeps VNIs unique: no two Subnets share an `l2_vni`, no two VirtualNetworks share an `l3_vni`, and no `l2_vni` equals an `l3_vni` (OVN-Kubernetes requires every VNI on the hub to be unique). It allocates only from a VNI range kept for OSAC in its settings (§4.3), fails the create with `retryable: false` and a message naming the range when the range has no free VNI, also while a delete is about to free one (an accepted limit, so the range is sized with headroom), reuses a VNI only after the Fabric delete of the Subnet or VirtualNetwork that held it succeeded, and frees it as the last step of that delete, so a delete that fails before that step never frees it;
- keeps VNIs fixed: a Subnet's `l2_vni` and its VirtualNetwork's `l3_vni` stay the same for the resource's whole life. Every re-run of `create_virtual_network` or `create_subnet` keeps them, `create_subnet` returns the same values, and the Fabric never changes them, also across controller restarts and backend upgrades, until the Fabric delete succeeds;
- uses VXLAN UDP port 4789, and floods broadcast, unknown-unicast, and multicast traffic by ingress replication (type-3 routes), with no multicast underlay;
- keeps every workload on the Subnet at MTU 1500: Fabric DHCP gives hosts 1500 (or no MTU option), `cudn_evpn` sets its network's MTU to 1500, and the fabric underlay and the hub node NICs carry frames of at least 1550 bytes (jumbo frames recommended).

The `evpn` schema and these duties are provisional until OSAC tests `cudn_evpn` in a lab against a real EVPN fabric (Netris); §4.13 has the risk. Open until that test: the route types the Fabric advertises toward the hub nodes (type-2 with the L3 VNI or type-5); the conformance `vm` profile decides.

### 4.10 Task reference

"Snapshot" means the §4.5 shape; the parentheses list the spec fields the task may use. Both tasks of a pair get the same stored input (§4.5); only `task` differs. The "Delete" row is the pair's second task (delete, detach, or release). Unless a section says otherwise, the result has no typed output.

**Task files.** Each task is the file `tasks/<task>.yaml` (or `.yml`) in the manager's Ansible role. The Fabric task set is the 21 tasks named in the Fabric headings below; the Kubernetes task set is the eight tasks of [OSAC Kubernetes Manager tasks](#osac-kubernetes-manager-tasks-osac-internal). One task file serves both interface types of `apply_network_attachment` and `delete_network_attachment`.

**Enabled services.** A deployment enables VMaaS, BMaaS, and CaaS separately ([OSAC-3046](/enhancements/OSAC-3046-per-service-enablement/design.md)), and every deployment needs the Fabric Manager. OSAC calls the same tasks on the same managers whatever services are enabled.
- A manager may implement a task, or part of one, as a documented no-op when it has nothing to do in its deployment. Examples with only VMaaS enabled: the Fabric DHCP scope of `create_subnet`, which has no physical client; the Fabric SecurityGroup and overlay attachment tasks of a fabric that does not enforce SecurityGroups. The gateway and network-type duties (§4.9) are never a no-op. The Fabric SecurityGroup tasks and the bind in the physical attachment may also be a documented no-op with BMaaS or CaaS enabled; the Fabric Manager is the only enforcement point of a physical port, so its SecurityGroups then filter no bare-metal traffic, and its manager design says so.
- The role has the task file of every task OSAC calls, also of a no-op. What OSAC never calls with the enabled services needs no implementation, and a task OSAC never calls needs no task file: without BMaaS and CaaS, `query_dhcp_lease` and the physical part of the attachment tasks (only for BareMetalInstances, also as CaaS workers); without VMaaS, the overlay part of the attachment tasks (only for ComputeInstances); without CaaS, `reserve_cluster_ingress_ip` / `release_cluster_ingress_ip` (only for Clusters); without `eastWestEthernet` or without BMaaS, the FabricDomain pair. While BMaaS and CaaS are disabled, the API rejects every BareMetalInstance and Cluster create with `UNAVAILABLE` (OSAC-3046).
- Enabling BMaaS or CaaS after networking resources exist is not supported ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).

**Attachment inputs.** `apply_network_attachment`, `delete_network_attachment`, and `query_dhcp_lease` share these inputs:

```yaml
resource:              # NetworkAttachment snapshot; id = target.id (one network attachment per workload)
  apiVersion: osac.openshift.io/v1alpha1
  kind: NetworkAttachment
  id: <target API ID>
  metadata: {name: <CR name>, namespace: <hub namespace>, uid: <CR UID>, generation: 1}
  spec: {target: {kind: ComputeInstance|BareMetalInstance, id: <API ID>}, subnet: <Subnet API ID>}
target: {kind: ComputeInstance, id: <API ID>}   # overlay
# physical: target: {kind: BareMetalInstance, id: <API ID>, host_name: <bare-metal inventory host name>}
network_attachment:
  subnet: <Subnet API ID>
  interface: {type: overlay}                    # Fabric overlay apply and later tasks: {type: overlay, ipv4_address: <VM address>}
                                                # physical: {type: physical, name: <host interface>, mac_address: <aa:bb:cc:dd:ee:ff>}
  security_group_ids: [<SecurityGroup API ID>, ...]   # the selected groups' API IDs: at least one, each once (Binding, below)
virtual_network: <snapshot>
subnet: <snapshot>
ipam: {...}
```

Parent snapshots (`virtual_network`, `subnet`, `external_ip_pool`) carry `spec.ipv4Cidr` (a pool: `spec.cidrs`) and no other spec field.

**Binding.** An apply binds the interface, at its manager's enforcement point, to the policy objects of `security_group_ids`; the interface then allows the union of their rules and follows each object's current rules. The delete unbinds. Every selected SecurityGroup was READY when the workload was created ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)), so its policy objects exist before any apply; a later rule update, or its failure, changes only the objects' rules, and the apply still binds.
- A VM attachment runs on both managers: the Kubernetes apply binds the VM pod before the VM exists; the Fabric apply binds the VM's address once it is known.
- A bare-metal (physical) attachment runs on the Fabric Manager only, because the Kubernetes Manager has no enforcement point on a physical port. The Fabric apply binds the port before it moves the port to the Subnet segment.

#### Fabric `create_virtual_network` / `delete_virtual_network`

| | |
|---|---|
| Called | When a VirtualNetwork is created. Delete: after all its children are gone. |
| Input | `resource`: VirtualNetwork snapshot (`spec.ipv4Cidr`); `network_type` (§4.9). |
| Must do | Create a routing domain for the VirtualNetwork (for example a virtual routing and forwarding (VRF) instance or a VPC), keyed by its API ID, that keeps its traffic apart from other VirtualNetworks, even when their CIDRs overlap. Give the routing domain a path to the DNS resolvers its workloads get through DHCP (§4.8; with `cudn_evpn`, also the addresses of `CUDN_EVPN_DNS_RESOLVERS`, which equal the agreed resolvers), with source NAT or a resolver per routing domain, because VirtualNetwork CIDRs overlap. A source-NAT address comes from a range in the manager's own settings (§4.3) that lies inside `excludedIpv4Cidrs` ([Unified — VirtualNetwork](/enhancements/OSAC-1433-unified-networking/design.md#virtualnetwork)); when none is free, fail with `retryable: false` and a message naming the range. With `network_type`, also do that type's duties (§4.9). |
| Result | Optional `backend_id` (string): the provider's network ID, shown in `status.backendNetworkId` (the VirtualNetwork's field name; a FabricDomain uses `status.backendId`). |
| Delete | Remove the routing domain and its resolver path (with `network_type`, also its IP-VRF, its hub extension, and its `l3_vni`), and free its source-NAT address as the last step. |

#### Fabric `create_subnet` / `delete_subnet`

| | |
|---|---|
| Called | When a Subnet is created; its VirtualNetwork is already Ready. Delete: after every attachment on the Subnet is deleted and after the Kubernetes `delete_subnet`. |
| Input | `resource`: Subnet snapshot (`spec.ipv4Cidr`); `virtual_network`; `ipam`; `network_type` (§4.9). |
| Must do | Create the Subnet's L2 segment in the VirtualNetwork's routing domain, with routes to the VirtualNetwork's other Subnets and `gateway_ipv4` as the segment's router address. When `physical_ipv4_cidrs` is not empty, run DHCP for physical interfaces that hands out addresses only from those ranges, with `gateway_ipv4` as router, and answers only MACs of physical attachments (§4.8); without BMaaS and CaaS, this DHCP part may be a documented no-op (Enabled services, §4.10). Accept `[]` for `physical_ipv4_cidrs` and `lb_vip_ipv4_cidrs`: with an empty `physical_ipv4_cidrs`, run no DHCP and use no Subnet address besides `gateway_ipv4`. With `network_type`, also do that type's duties (§4.9). |
| Result | With `network_type`: `network_segment` (§4.9). Without it: none. |
| Delete | Remove the segment, its extension to the hub, and the DHCP scope, and free its `l2_vni`. |

#### Fabric `create_security_group` / `delete_security_group`

**SecurityGroup rules.** [Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup) defines what the rules mean and how the API replaces them. Like a Subnet, every SecurityGroup records the Fabric Manager and, when its VirtualNetwork has one, the Kubernetes Manager (§4.1). Each manager enforces the group at its own enforcement point: the Kubernetes Manager with NetworkPolicy on the VM pod, the Fabric Manager with switch ACLs on bare-metal ports and on VM addresses, because some VM-to-VM traffic crosses the physical switches.
- Traffic must pass every enforcement point it crosses, so each manager enforces exactly the rules, or nothing as a documented no-op (§4.10 Enabled services), and never allows more. When the backend cannot enforce a rule exactly, or cannot hold the group's rule set (capacity), `create_security_group` fails with `retryable: false`.
- OSAC maps each API rule ([Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup)) to the task input:
  - `protocol` `PROTOCOL_TCP`, `PROTOCOL_UDP`, `PROTOCOL_ICMP`, `PROTOCOL_ALL` → `tcp`, `udp`, `icmp`, `all`; `icmp` means every ICMP type;
  - `ipv4_cidr` → `sourceCidr` in `ingressRules`, `destinationCidr` in `egressRules`: the remote addresses;
  - `port_from`, `port_to` → `portFrom`, `portTo`: the destination port range, present exactly for `tcp` and `udp`, both set, from 1 to 65535, with `portFrom` ≤ `portTo`;
  - a direction with no rules → `[]`.

  The API rejects every other rule, so a manager never gets one.
- Policy is stateful and allow-only and filters IPv4 only. ARP for any endpoint of the Subnet and for `gateway_ipv4` always passes. DHCP from the owning manager always passes, and a manager blocks DHCP replies from tenant workloads when its backend can.
- Policy acts only on interfaces bound to the group ([Binding](#410-task-reference)); on the overlay, the Kubernetes Manager's baseline deny ([Kubernetes `create_subnet`](#kubernetes-create_subnet--delete_subnet)) covers pods that no binding selects. OSAC does not check enforcement at run time.

| | |
|---|---|
| Called | When a SecurityGroup is created, also an automatic one (CaaS), after its VirtualNetwork is Ready; again on each rule update (below). Delete: after no NetworkAttachment selects the group, and after the Kubernetes `delete_security_group`. |
| Input | `resource`: SecurityGroup snapshot (`spec.ingressRules`, `spec.egressRules`); `virtual_network`. |
| Must do | Create the policy object for the group, keyed by its API ID, that enforces exactly its rules on every bare-metal port and VM address later bound to it. Creating it changes no traffic, because nothing is bound yet, and needs no Subnet or attachment. A re-run with other rules replaces the object's rules atomically: all or nothing, and on failure the object keeps its previous rules. |
| Rule update | A [rule update](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup), which the API accepts only for a READY group with no update in progress or a FAILED group, stores a new input (§4.5). OSAC runs `create_security_group` with it as the next attempt on each manager recorded on the group, in manager order (Fabric, then Kubernetes; §4.7), also after a final failure. When the Fabric run fails finally, the Kubernetes run does not start; the group is FAILED and the Kubernetes Manager keeps the rules of its last successful run. Later retries and the delete get the newest input. No attachment task runs: every bound interface follows the object. [Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup) defines the status. [Edge cases](#updates-while-a-job-runs) covers a bind during an update. |
| Delete | Remove the policy object. |

```yaml
resource:
  apiVersion: osac.openshift.io/v1alpha1
  kind: SecurityGroup
  id: <SecurityGroup API ID>
  metadata: {name: <CR name>, namespace: <hub namespace>, uid: <CR UID>, generation: 2}
  spec:
    ingressRules:
      - {protocol: tcp, portFrom: 22, portTo: 22, sourceCidr: 0.0.0.0/0}
      - {protocol: all, sourceCidr: 10.0.1.0/24}
    egressRules:
      - {protocol: all, destinationCidr: 0.0.0.0/0}
virtual_network: <snapshot>
```

#### Fabric `apply_network_attachment` / `delete_network_attachment`

One task for both interface types; `network_attachment.interface.type` says which.

**Physical interface** (bare metal):

| | |
|---|---|
| Called | After BMaaS provisions the host on the provisioning network and creates the NetworkAttachment, only on a Subnet whose `physical_ipv4_cidrs` is not empty (§4.8). Delete: after BMaaS powers off the host. |
| Input | Attachment inputs, with `interface.type: physical`, `target` = `{kind: BareMetalInstance, id, host_name}`, `interface.name` = the port name from the host's BareMetalInstanceType, and `interface.mac_address` = that port's MAC. `host_name` is the BareMetalInstance `spec.externalHostName`, the host's inventory name (Metal3: BareMetalHost name; Ironic: node name; BCM and NetBox: device name), and is never empty, because BMaaS assigns only hosts that have an inventory name ([BMaaS — BareMetalInstanceType and interface selection](/enhancements/OSAC-1437-bmaas-networking/design.md#baremetalinstancetype-and-interface-selection)). |
| Must do | First check that the segment's DHCP has an address from `physical_ipv4_cidrs` for `interface.mac_address` (already held or free); if not, fail with `retryable: false` and change nothing. Bind the interface to the policy objects of `security_group_ids` (Binding, §4.10); this bind may be a documented no-op (Enabled services, §4.10). Then move the switch port of host interface `interface.name` from the provisioning network to the Subnet segment, and take every other fabric port of the host off the provisioning network. Fabric ports are the host ports on the provisioning network while the host is idle; ports in a FabricDomain are never fabric ports, and FabricDomain tasks never move fabric ports. Make sure the segment's DHCP gives `interface.mac_address` one address from `physical_ipv4_cidrs`, the same one while the attachment exists. On a Subnet created with `network_type: evpn` (known from the manager's own state for the Subnet API ID), also advertise the MAC/IP behind the port (§4.9). The manager maps `host_name` and `interface.name` to a switch port, and finds the provisioning network, from its own inventory and settings (§4.3); that map is a Fabric Manager prerequisite. |
| Delete | Return every fabric port of the host to the provisioning network, unbind the interface from its SecurityGroups, release the MAC's DHCP address, and withdraw the port's EVPN advertisements (§4.9). Success means the host is back on the provisioning network. |

**Overlay interface** (VM):

| | |
|---|---|
| Called | For a VM's NetworkAttachment, after the [Kubernetes apply](#kubernetes-apply_network_attachment--delete_network_attachment) succeeded and VMaaS reported the VM's address ([VMaaS — Network status](/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery)). VMaaS creates the VM between the two applies. Delete: after the VM is gone, before the Kubernetes delete. |
| Input | Attachment inputs, with `interface.type: overlay`, `target` = `{kind: ComputeInstance, id}`, and `interface.ipv4_address` = the VM's IPv4 address. OSAC adds `ipv4_address`, the address VMaaS reported, to the stored input (§4.5) before the first Fabric apply; the VM keeps its address across restarts and live migration, so the key never changes. Every later task of the attachment gets it too, also the Kubernetes delete (§4.5). |
| Must do | Bind `interface.ipv4_address` on the Subnet, in the fabric, to the policy objects of `security_group_ids` (Binding, §4.10), keyed by `resource.id` (for example as ACL membership), or do nothing as a documented no-op. The no-op is allowed in every deployment, because the Kubernetes Manager always enforces the VM's SecurityGroups. Change nothing else: the Kubernetes Manager attached the VM. |
| Delete | Unbind the address from its SecurityGroups. |

#### Fabric `query_dhcp_lease`

| | |
|---|---|
| Called | After the physical apply succeeds and BMaaS confirms the handoff reboot (`NetworkHandoffComplete=True`); retried as §4.6 and §4.7 state. A final failure or a rejected result stops the queries: the NetworkAttachment stays Ready, its `query_dhcp_lease` job entry has state `Failed`, and BMaaS reports it on the BareMetalInstance. |
| Input | Attachment inputs of the same NetworkAttachment. |
| Must do | Find the active DHCP lease the host obtained for `interface.mac_address` on the Subnet after its port moved; a reservation alone is not a lease. Change nothing. When there is no lease yet, or more than one active lease matches, fail with `retryable: true` and a message that says which; OSAC keeps querying (§4.7 Retries). |
| Result | `dhcp_lease: {ip_address: 10.0.1.130, mac_address: aa:bb:cc:dd:ee:ff}`. OSAC accepts it only when `mac_address` equals the input MAC and `ip_address` is a canonical IPv4 address in `physical_ipv4_cidrs` other than the network, broadcast, or gateway address. |

#### Fabric `create_external_ip_pool` / `delete_external_ip_pool`

| | |
|---|---|
| Called | When a Cloud Infrastructure Admin creates the ExternalIPPool. Delete: after no ExternalIP uses the pool. |
| Input | `resource`: ExternalIPPool snapshot (`spec.cidrs`, exactly one IPv4 CIDR). |
| Must do | Make every eligible address of the CIDR available for allocation, and route it to the fabric from wherever the provider exposes external addresses. Eligible addresses are all but the network and broadcast addresses; in a /31 or /32, every address. Fail when the backend cannot serve every eligible address. |
| Delete | Remove the pool from the backend. |

#### Fabric `create_external_ip` / `delete_external_ip`

| | |
|---|---|
| Called | When an ExternalIP is created. Delete: after no ExternalIPAttachment or NATGateway uses it. |
| Input | `resource`: ExternalIP snapshot (`spec.pool`: the pool's API ID); `external_ip_pool`: the pool's snapshot (`spec.cidrs`). |
| Must do | Reserve one free address of the pool under the ExternalIP's API ID. A retry returns the same address. When the pool has no free address, fail with `retryable: false` and a message that says the pool is full. |
| Result | `external_ip: {address: 198.51.100.19}`. OSAC accepts it only when the address is canonical and an eligible address of the pool CIDR, then writes it to `ExternalIP.status.address`. |
| Delete | Release the reservation. Success means the address is free. |

#### Fabric `attach_external_ip` / `detach_external_ip`

| | |
|---|---|
| Called | When an ExternalIPAttachment is created, after the ExternalIP is ALLOCATED and the target endpoint (a workload or cluster endpoint) is ready, as the workload service design defines. Delete: before the ExternalIP or the target is deleted. |
| Input | `resource`: ExternalIPAttachment snapshot; `external_ip: {id, address}`; `destination` (below). |
| Must do | Create one-to-one inbound destination NAT (DNAT) from `external_ip.address` to `destination.address` in `destination.routing_domain`, for all protocols and ports. The DNAT also applies to traffic that reaches `external_ip.address` from any VirtualNetwork through its NATGateway, including from the same VirtualNetwork (hairpin), with replies on the same path. The DNAT is inbound only: replies to its connections return through the translation, also when the VirtualNetwork has no NATGateway, and new outbound connections from `destination.address` use the NATGateway's address, never `external_ip.address`. Keep the client's source address on inbound traffic (destination NAT only); for hairpin traffic the destination sees the client VirtualNetwork's NATGateway address. |
| Delete | Remove the translation. |

```yaml
destination:
  address: 10.0.1.17                       # resolved by OSAC from the target (the workload service designs define how)
  routing_domain:
    type: tenant_virtual_network           # or provider_management: the provider's management network, found in the manager's settings
    virtual_network_id: <API ID>           # tenant_virtual_network only
    subnet_id: <API ID>                    # tenant_virtual_network only
```

#### Fabric `create_nat_gateway` / `delete_nat_gateway`

| | |
|---|---|
| Called | When a NATGateway is created (one per VirtualNetwork), after its ExternalIP is ALLOCATED. Delete: before its ExternalIP is deleted. |
| Input | `resource`: NATGateway snapshot; `virtual_network`; `external_ip: {id, address}`. |
| Must do | Translate the source address of outbound traffic from the VirtualNetwork's CIDR to `external_ip.address` (source NAT, SNAT). Allow no new inbound connections. |
| Delete | Remove the translation. |

#### Fabric `reserve_cluster_ingress_ip` / `release_cluster_ingress_ip`

| | |
|---|---|
| Called | When CaaS needs the guest ingress address for a Cluster; released when the Cluster is deleted. OSAC runs it on the Fabric Manager recorded on the Subnet, never on a Subnet whose `lb_vip_ipv4_cidrs` is `[]` (§4.8). See the [CaaS design](/enhancements/OSAC-1436-caas-networking/design.md). |
| Input | `resource`: ClusterOrder snapshot; `cluster_id`: Cluster API ID; `virtual_network`; `subnet`; `ipam`. |
| Must do | Reserve one address from `ipam.lb_vip_ipv4_cidrs` for `cluster_id` (the ownership key, not `resource.id`), distinct from other clusters on the Subnet, until `release_cluster_ingress_ip` succeeds. A retry returns the same address. When none is free, fail with `retryable: false` and a message that says the range is full. While reserved, the address may move between the Subnet's physical attachments (guest MetalLB in L2 mode); the Fabric carries its traffic to whichever port answers ARP for it and never drops it as a spoofed source. |
| Result | `cluster_ingress: {address: 10.0.1.193}`. OSAC accepts it only when the address is canonical, in `ipam.lb_vip_ipv4_cidrs`, not the Subnet's broadcast address, and equal to any address already accepted for `cluster_id`. |
| Delete | Release the reservation. |

#### Fabric `create_fabric_domain` / `delete_fabric_domain` (optional)

| | |
|---|---|
| Called | Only when the Fabric Manager declares `eastWestEthernet`, NetworkClass enables Ethernet east-west, and BMaaS is enabled, because the domain's servers are bare-metal hosts ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates) reject a FabricDomain create otherwise). The [Multi-Fabric East-West Networking Design](/enhancements/OSAC-1382-multi-fabric-east-west-networking/design.md) defines the behavior. |
| Input | `resource`: FabricDomain snapshot (`spec.type`, `spec.servers`); `virtual_network`. `spec.type` is `ethernet_ew` (the only value this release); `spec.servers` lists inventory host names, the same names as `host_name` ([physical attachment](#fabric-apply_network_attachment--delete_network_attachment)), and never changes ([Unified — API operation constraint](/enhancements/OSAC-1433-unified-networking/design.md#api-operation-constraint)). Anything else the domain needs (for example a backend template) comes from the manager's settings (§4.3). |
| Must do | Create the Ethernet east-west domain bound to the VirtualNetwork, containing exactly the listed servers. |
| Result | Optional `backend_id` (string), shown in `status.backendId`. |
| Delete | Remove the domain. |

#### OSAC Kubernetes Manager tasks (OSAC-internal)

OSAC's internal interface to its own Kubernetes Managers, not a provider obligation; Fabric authors read it only to know what runs on the hub.

**`cudn_evpn` limit.** OVN-Kubernetes needs a distinct IP-VRF VNI per network, and the fabric has one per VirtualNetwork (§4.9), so `cudn_evpn` builds one hub network per VirtualNetwork, owned by one Subnet.
- Kubernetes `create_subnet` claims the network when none exists, and the network records the owner Subnet's API ID. In a tenant's default VirtualNetwork the default Subnet is the owner, because no other Subnet can be created there before it is READY ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)); in any other VirtualNetwork the owner is the first Subnet whose Kubernetes `create_subnet` runs. The owner's `delete_subnet` removes the network, so the next Subnet created claims it.
- No handover: every other Subnet follows the implementation-limit rule (§4.7): its VM attachment applies fail, bare-metal attachments work, and its overlay range stays unused (it keeps the §4.8 layout for life).
- [Edge cases](#kubernetes-manager-hub-network) covers a claim while the owner is being deleted.
- When OVN-Kubernetes allows several networks per IP-VRF, only `cudn_evpn` changes (one hub network per Subnet); the contract, OSAC, and Fabric Managers stay the same.

##### Kubernetes `create_virtual_network` / `delete_virtual_network`

| | |
|---|---|
| Called | When the VirtualNetwork has a Kubernetes Manager (§4.1): after the Fabric create. Delete: before the Fabric delete. |
| Input | `resource`: VirtualNetwork snapshot (`spec.ipv4Cidr`). |
| Must do | Create any VirtualNetwork-level construct the hub needs (`cudn_evpn`: none). |
| Delete | Remove it. |

##### Kubernetes `create_subnet` / `delete_subnet`

| | |
|---|---|
| Called | For every Subnet that has a Kubernetes Manager (§4.1), after the Fabric `create_subnet`. Delete: after every overlay attachment on the Subnet is deleted, and before the Fabric `delete_subnet`. |
| Input | `resource`: Subnet snapshot (`spec.ipv4Cidr`); `virtual_network`; `ipam`; `network_segment` (§4.9). |
| Must do | Create the Subnet's hub network, connected to the Fabric segment so that VMs and physical hosts on the Subnet share one L2 domain. For `evpn`: a ClusterUserDefinedNetwork (Layer2, primary, `transport: EVPN`, `evpn.vtep` = the VTEP CR from installation, `evpn.macVRF.vni` = `l2_vni`, `evpn.ipVRF.vni` = `l3_vni`, no route targets). Hand out VM addresses only from `overlay_ipv4_cidrs`, with `gateway_ipv4` as router. Install a baseline deny: block tenant traffic both ways, except DHCP and ARP, for every pod on the Subnet's network that no SecurityGroup binding selects (a VM pod not yet bound, or any other pod such as a disk import pod). Give VMs, through the network's DHCP, the resolvers of the setting `CUDN_EVPN_DNS_RESOLVERS` (§4.3). While a hub prerequisite (§4.12) or that setting is missing, fail with `retryable: true`, so an administrator can add it. When the hub AS is above 65535 and a VNI in `network_segment` is above 65535, fail with `retryable: false` and a message naming the VNI rule (§4.9). |
| Delete | Remove the network, the baseline, and any namespace the manager created for the Subnet. |

##### Kubernetes `create_security_group` / `delete_security_group`

| | |
|---|---|
| Called | When the SecurityGroup's VirtualNetwork has a Kubernetes Manager (§4.1): at create and on each [rule update](#fabric-create_security_group--delete_security_group), after the Fabric run. Delete: after no NetworkAttachment selects the group, before the Fabric delete. |
| Input | As the [Fabric task](#fabric-create_security_group--delete_security_group). |
| Must do | As the Fabric task, for VM pods ([SecurityGroup rules](#fabric-create_security_group--delete_security_group)). `cudn_evpn` creates the group's policy objects for the VirtualNetwork's hub network, selecting no VM until an attachment binds one; creating them needs no Subnet, hub network, or attachment ([CUDN EVPN design](/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md) defines the objects). NetworkPolicy is namespaced: a manager that keeps a copy per attachment namespace creates the copy at bind, from the group's current rules, and every `create_security_group` run, also a re-run, updates all copies. NetworkPolicy cannot match ICMP, so the manager enforces ICMP rules another way (for example OVN ACLs) or fails with `retryable: false`; a NetworkPolicy sets both `Ingress` and `Egress` in `policyTypes`, even when a direction has no rules. |
| Delete | Remove the policy objects. |

##### Kubernetes `apply_network_attachment` / `delete_network_attachment`

| | |
|---|---|
| Called | After VMaaS creates the NetworkAttachment, before the VM exists. Delete: after the VM is gone and after the [Fabric delete](#fabric-apply_network_attachment--delete_network_attachment). |
| Input | Attachment inputs, with `interface.type: overlay` and `target` = `{kind: ComputeInstance, id}`; `network_segment` (§4.9). |
| Must do | Make sure a namespace exists with the label `osac.openshift.io/tenant: <tenant>` whose primary network is the Subnet's network (for example an OVN-Kubernetes primary user-defined network whose namespace selector matches it); only primary networks are supported. A VM on this attachment keeps the same address across restarts and live migration. Bind the VM's pod, selected by the label `osac.openshift.io/compute-instance-id: <target.id>`, to the policy objects of `security_group_ids` (Binding, §4.10). Never read or modify the VM. |
| Result | `vm_attachment: {namespace: <namespace>}`: the namespace where VMaaS creates the VM, always the same for the same target and Subnet, including on retry. OSAC rejects any key other than `namespace`, and accepts it only when the namespace exists in the hub with the label `osac.openshift.io/tenant` equal to `osac_job_vars.tenant`. |
| Delete | Unbind the VM from its SecurityGroups, remove its per-VM backend objects, and any namespace the manager created only for this attachment. |

### 4.11 Conformance tests

Networking is an area of the [OSAC conformance suite](/enhancements/OSAC-XXXX-conformance-suite/design.md), the image `ghcr.io/osac-project/osac-conformance:<OSAC release>`. The suite defines how it runs, its two layers (component tests and profiles), the test Tenant and cleanup, the common configuration, the report, and the support policy. Providers test only their Fabric Manager, the networking component. This section defines what networking adds; the [test plan](testplan.md#conformance-suite) lists every test with its pass condition.

| Layer | Runs against | Checks |
|---|---|---|
| Task tests (the component tests) | The Fabric Manager's role in its EE image and the provider backend. No OSAC installation and no hub peering; a scratch cluster stands in for the hub. | Every Fabric task (§4.10) that applies to the enabled services, with generated inputs: results, re-runs, deletes, rejections, the network segment, parallel jobs on distinct resources, empty ranges and two address plans, SecurityGroup re-runs and binding. No traffic. |
| Profiles | A lab with this OSAC release and the Fabric Manager selected, through OSAC's normal APIs. | One scenario per enabled workload service (below). |

**Task tests:**
- **How a test runs.** The suite runs the role exactly as the generic playbook does (§4.3): `include_role` with `tasks_from: <task>`, one `osac_job_vars`, inside the manager's EE image, with the settings and secrets of the lab's ConfigMap and Secret `network-fulfillment-ig` (§4.3) as environment variables, and `K8S_AUTH_KUBECONFIG` set to `taskTests.kubeconfig`, whose namespace holds the hub objects the tasks create. It generates the inputs, with fresh API IDs on every run. When the task's resource has parents (§4.1), the test first runs the parents' create tasks with the same role, in §4.7 order, and deletes them after the test, children first; a parent task that does not succeed fails the test with `setup: <task> failed: <message>`. Task tests use the lab's backend and its VNI and source-NAT ranges, so keep headroom in them.
- **Address plans.** It lays out each Subnet as §4.8 does, with at least two plans (overlay/fabric/lbVip), so the manager must accept `[]` lists: with a network type 0.75/0.25/0 and 1/0/0; without one 0/0.75/0.25 and 0/1/0, only when the lab NetworkClass has no Kubernetes Manager (with one, every Subnet has a network type).
- **Which runs are selected.** It selects the runs from the registration and the lab's enabled services, which it reads from the Capabilities `enabled_services` ([OSAC-3046](/enhancements/OSAC-3046-per-service-enablement/design.md)) through `lab.apiURL`. It runs every Fabric task, except:
  - the **host runs** (physical attachment and `query_dhcp_lease`), only when BMaaS or CaaS is enabled;
  - the **overlay attachment runs** (overlay `apply_network_attachment` and its delete), only when VMaaS is enabled;
  - the **FabricDomain runs**, also host runs, only when the registration declares `eastWestEthernet` and BMaaS is enabled;
  - the **ingress runs** (`reserve_cluster_ingress_ip`, `release_cluster_ingress_ip`), only when CaaS is enabled.

  A run that is not selected reports `skip` and does not block conformance (§4.10 Enabled services). The host runs need `taskTests.hosts`; without it they report `skip`. The lease run needs the host powered on and still requesting DHCP on that interface after its port moves (for example a ramdisk that retries DHCP); the suite never powers hosts and polls `query_dhcp_lease` every 30 seconds for up to `timeouts.bareMetalReady`.

**Profiles.** Creating the suite's test Tenant creates its [Default Networking](/enhancements/OSAC-1433-default-networking/design.md), including the default NAT ExternalIP from a READY pool that the [Default Networking rule](/enhancements/OSAC-1433-default-networking/design.md#server-validation-fulfillment-service) chooses (a lab pool or the suite's pool); deleting the Tenant releases it. Each workload gets an explicit ExternalIP from the suite's own ExternalIPPool, created from `externalIPPoolCIDR` and deleted after the Tenant, never automatic external access; only a Cluster, whose external access CaaS makes automatic, takes its ExternalIPs from any READY pool ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)). So other Tenants and pools may exist in the lab. The runner must reach ExternalIPs from outside the tenant networks. The test plan's [Profile setup](testplan.md#profile-setup) gives the steps.

| Profile | Required when | Core checks |
|---|---|---|
| `baremetal` | BMaaS is enabled. | One bare-metal instance: address in the fabric range, SSH through its ExternalIP, a port its SecurityGroup does not allow stays closed, egress through a NATGateway, clean delete. |
| `vm` | VMaaS is enabled. VMaaS needs a Kubernetes Manager, so the registration lists `evpn`. | Two VMs on one Subnet: address in the overlay range, SSH through an ExternalIP, egress, one SecurityGroup allow/deny check and one rule update. It runs both managers and proves the Fabric gateway for VMs. |
| `cluster` | CaaS is enabled. Cluster workers are bare metal, so this profile also needs BMaaS enabled. | The smallest Cluster: Ready; `api` and `*.apps` answer from the runner. |

The provider enables in the lab exactly the services it supports, and the suite runs exactly the required profiles. East-west has no profile for now.

**Configuration.** The `networking` section of `conformance.yaml` has these keys; nothing the suite reads from the lab hub is restated. The suite reads the manager name, role, network types, and capabilities from the Fabric registration ConfigMap (§4.2), the Fabric Manager's settings and secrets from the ConfigMap and Secret `network-fulfillment-ig` (§4.3), the address plan from the NetworkClass, and the free hosts from the bare-metal inventory. It resolves the lab's EE image (the Helm value `aap.configAsCode.eeImage`, §4.3) to its digest (`eeImageDigest`); the task tests run in that image, and `collectionVersion` is the version of the collection of `ansible_role` installed in it.

| Key | Meaning |
|---|---|
| `externalIPPoolCIDR` | An IPv4 CIDR of at least a /28, or a /27 when more than one profile is required, that the backend can serve and that overlaps nothing the lab's [ExternalIPPool overlap rule](/enhancements/OSAC-1433-unified-networking/design.md#externalippool) forbids, including any VirtualNetwork CIDR and the default `virtual_network_ipv4_cidr`. The suite carves every pool it creates from it, never two that overlap at once: first the task tests' pools (including their /31 and /32 pools), then a /29 per required profile, which holds its ExternalIPs, its NATGateway's ExternalIP, and the test Tenant's default NAT address if it comes from the suite's pool. It deletes each pool at the end. |
| `egressURL` | A public HTTPS URL a workload fetches to check egress. |
| `taskTests.kubeconfig`, `taskTests.namespace` | A scratch cluster and a writable namespace in it, used as the hub networking namespace. |
| `taskTests.hosts` | Needed only when BMaaS or CaaS is enabled: two bare-metal hosts, each `hostName`, `interface`, `macAddress`. Withhold both from the lab's BMaaS inventory for the run (for example not available for assignment, or under maintenance): the task tests move their ports directly, so BMaaS must not assign them. |
| `baremetal.catalogItem`, `cluster.template`, `vm.image` | Needed only for a required profile that uses it, because OSAC has no default: the bare-metal catalog item (`baremetal`), the Cluster template (`cluster`), and the VM disk image with `nc` and `curl` (`vm`). The `vm` profile uses OSAC's VM template. |
| `timeouts` (top level) | Networking's keys and defaults: `networkReady` 15m (the test Tenant's Default Networking and each profile's networking resources), `vmReady` 15m, `bareMetalReady` 60m, `clusterReady` 90m, and `delete` 30m. A task test's job times out after 60 minutes. |

The suite stops with a configuration error only when a required profile cannot run: `vm` without `evpn` in the registration, `cluster` without BMaaS enabled, provider networking disabled ([Unified — Provider networking control](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control)), an address plan that leaves a required profile a range it uses empty (`vm`: overlay; `baremetal`: fabric; `cluster`: fabric and lbVip), an `externalIPPoolCIDR` that overlaps (its pool create fails), `vm` required and the lab's ConfigMap `network-fulfillment-ig` without a valid `CUDN_EVPN_DNS_RESOLVERS`, or too few free hosts for the required profiles together. Free hosts are the hosts available for BMaaS assignment, counted from the lab inventory; `baremetal` needs one, `cluster` the Cluster template's worker count, and `vm` none.

**Report.** Networking reports its component in `components[]` with the area `networking` and the Fabric Manager as the lab hub registers it: `name`, `ansibleRole`, `collectionVersion`, `eeImageDigest`, `networkTypes`, `capabilities`. A test's `id` is its case ID, with the task for a per-task run (for example `TC-CONTRACT-01/query_dhcp_lease`) and, where a case runs one task several ways, the part: `overlay` or `physical`, the kill point (`25`, `50`, `75`), the network type or `none`, or the plan `<overlay>-<fabric>-<lbVip>` (for example `TC-PLAN-01/create_subnet/evpn/0.75-0.25-0`). The title in its name is the case's Title in the test plan. `networkTypes` and `capabilities` are lists. A profile passes only when every test that counts toward it passes: its scenario, and for `baremetal` the host runs, so it does not pass without `taskTests.hosts`. The Fabric Manager is `conformant` for a release when every task test that applies passes and every required profile passes; a run the suite does not select does not apply. Support condition: a workload service's networking is supported only with a `conformant` report whose profile for that service passed (`baremetal`, `vm`, or `cluster`); the report is self-reported, and OSAC does not enforce this.

**Evidence.** On a profile failure, the suite also saves the NetworkClass status, the test Tenant's `DefaultNetworkingReady` condition, and the area's objects: for `vm`, the VirtualMachine, the VirtualMachineInstance, the launcher pod's events and log, the guest serial console, and the Subnet's ClusterUserDefinedNetwork; for `baremetal`, the BareMetalInstance and its NetworkAttachments; for `cluster`, the Cluster and its worker NetworkAttachments.

**Ownership.** OSAC runs the task tests in its own CI for each release with the reference no-op and mock managers ([test fixtures](testplan.md#test-fixtures)); the no-op manager passes every task test it supports. OSAC runs the task tests and profiles in its E2E lab with a real EVPN Fabric Manager and `cudn_evpn`.

**Follow-up.** Network-behavior tests stay a [follow-up](testplan.md#follow-up-network-behavior-tests): the isolation matrix, DHCP ranges, Fabric SecurityGroup enforcement, the NAT and hairpin matrix, and a cleanup audit.

### 4.12 Security, RBAC, and tenancy

- No tenant-facing RBAC changes. Cloud Infrastructure Admins manage the Fabric Manager's registration ConfigMap.
- Each manager design lists the hub permissions its jobs need (OSAC's Kubernetes Managers, for example, namespaces, ClusterUserDefinedNetworks, and NetworkPolicies). Networking jobs run as OSAC's job service account, which the OSAC installation binds to `cluster-admin`, so a provider grants nothing extra.
- `tenant` is informational: managers use it to label backend objects, never to authorize. Isolation comes from VirtualNetwork and Subnet identity (§4.7). CaaS worker attachments carry tenant `system` (see the CaaS design).
- Each manager design lists its installation prerequisites, configured at installation, not by tasks. For `evpn`, the Cloud Infrastructure Admin configures the hub prerequisites of `cudn_evpn` ([CUDN EVPN design](/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md)), and agrees with the provider on the hub AS, the hub nodes' BGP addresses, the VTEP CIDR of the VTEP CR, the fabric's BGP peers and AS, the VNI range for OSAC, and the DNS resolver addresses given to workloads. The hub AS, the VTEP CIDR, and the VNI range are fixed at installation; changing them means reinstalling. The hub AS and the VTEP CIDR live only in the hub prerequisites (the FRRConfiguration and the VTEP CR) and in the Fabric Manager's settings. OSAC keeps no copy, so it cannot detect a change or compare the two sides; the Cloud Infrastructure Admin and the provider compare them before the first install. The Fabric peers over EVPN with every hub node and routes the VTEP CIDR in the underlay; this peering is installation work that the provider maintains as hub nodes are added or removed, and tasks only add VRFs to it (§4.9). The Fabric Manager reads its side from its settings (§4.3).

### 4.13 Risks and drawbacks

| Risk or cost | Mitigation |
|---|---|
| A manager returns success without the behavior. | Result validation is separate from conformance; the Fabric Manager must pass the conformance tests (§4.11). |
| The Fabric's EVPN setup does not interoperate with OSAC's Kubernetes Manager. | The `evpn` schema stays provisional until lab-tested against a real EVPN fabric (§4.9); until then a later OSAC release may change the schema and duties in its contract and suite. The `vm` conformance profile runs both managers. |
| A task fails midway and leaves partial state. | Idempotent stable-ID tasks; readiness and finalizer gates hold until cleanup succeeds. |
| Every Fabric Manager must implement every task of the services the deployment enables, and SecurityGroup semantics. | Accepted: it keeps the tenant API identical across providers. |
| Workload create and delete depend on manager availability. | Accepted: the attachment gates keep traffic safe. |
| Restarts, races, and partial failures are not yet fully specified. | [Edge cases that need handling](#edge-cases-that-need-handling) lists each known case with its proposed handling; each becomes a rule when implemented. |

### Edge cases that need handling

These cases are not normative yet: the body describes the normal flow and does not depend on them. Each entry gives the case, why it matters, and the handling we propose. Edge cases of the fulfillment service and status are in [Unified — Edge cases](/enhancements/OSAC-1433-unified-networking/design.md#edge-cases-that-need-handling); service-specific ones are in the [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md#edge-cases-that-need-handling), [BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md#edge-cases-that-need-handling), and [CaaS](/enhancements/OSAC-1436-caas-networking/design.md#edge-cases-that-need-handling) designs.

#### Restarts and job tracking

| Case | Why it matters | Proposed handling |
|---|---|---|
| Two operator instances, or a reconcile from a stale cached CR, launch the same job. | Two jobs of one task would run. | Leader election: one operator instance acts at a time. OSAC writes the `Running` entry as a status update conditional on the CR's `resourceVersion` and launches only after it succeeds; on a conflict, or with a cached CR older than the entry or the deletionTimestamp, it rereads and launches nothing in that pass. |
| An entry is `Running` with an empty `jobID` (the launch call failed, or the operator restarted before writing `jobID`). | The job may or may not exist in AAP. | Resolve it by its AAP label: running → track it; ended → process its result; absent → look again 2 minutes after the failed call, or after this instance became leader (a launch call times out after 60 seconds). Still absent: launch it if launch is still allowed, else set it `Cancelled`; a delete also cancels, by that label, a job AAP creates later. |
| Several AAP jobs carry one label (AAP created a job more than 2 minutes after a failed launch call). | Two jobs could change the backend. | Track the lowest job ID, cancel the others in AAP, and ignore their results; idempotent tasks make a late or orphaned run harmless. OSAC never compares AAP times with hub times. |
| AAP purges old job records. | The empty-`jobID` lookup above finds nothing for a purged job. | Accepted limit: the entry is resolved as absent. The installer documentation recommends keeping AAP job records at least as long as networking resources live. |
| AAP lost the job record (not found for the job ID). | OSAC cannot read the result. | Treat it as a retryable failure; with a delete pending, start the delete once it is marked failed. Any other AAP error is a failed read, retried with no state change. |
| AAP never starts a job (`new`, `pending`, or `waiting`). | The 60-minute timeout covers only running time, so the resource would wait forever. | 30 minutes after launch, counted on the hub from the launch call or from when this instance became leader, cancel it in AAP. Once it ended, treat it like `error` (backoff, not `Cancelled`), with the entry message 'AAP did not start the job within 30 minutes'. |
| An administrator cancels a job in AAP, with no delete pending. | The create would stop with no owner action. | AAP `canceled` is retryable unless the resource or its target has a deletionTimestamp. A create, apply, attach, reserve, or `query_dhcp_lease` whose latest entry is `Cancelled` and that nothing deletes is launched again at once as the next attempt. |
| A job ended, but a delete arrives before OSAC processed its result. | OSAC could act on a result for a resource being deleted. | When OSAC first sees the deletionTimestamp, it treats every unprocessed job like a running one: `Cancelled` once AAP reports it ended, whatever its AAP status, and its result ignored. |
| The operator restarts during a retry wait. | The next retry time in the message is stale. | The wait restarts, and OSAC rewrites the next retry time in the message. |
| The operator restarts while a Subnet task holds the VirtualNetwork's slot. | A second Subnet task of the VirtualNetwork could start. | A `Running` entry for a Subnet task, even with an empty `jobID`, holds the slot, except an entry whose job has ended and whose segment waits for a delete (§4.9). OSAC applies the per-VirtualNetwork rule under one operator lock per VirtualNetwork, reads Subnet CRs from the API server, and holds the lock until its status write succeeds. |
| A check reads a stale informer cache. | It could accept a conflict or a missing object. | Read from the API server: Subnet CRs under the locks above and in segment acceptance, `cudn_evpn`'s owner Subnet, and the namespace in the `vm_attachment` acceptance check. |

#### Updates while a job runs

| Case | Why it matters | Proposed handling |
|---|---|---|
| `apply_network_attachment` binds while `create_security_group` updates the group's rules. | The interface could keep the old rules. | The manager makes both converge to the newest rules without a lock, for example by binding the interface to the group's one policy object, which every `create_security_group` run replaces atomically, or by failing with `retryable: true` on a conflict. |

#### Network segment acceptance

| Case | Why it matters | Proposed handling |
|---|---|---|
| Two `create_subnet` results with one VNI are processed at once. | Both could pass the uniqueness check. | Accept segments one at a time under one operator-wide lock, reading Subnet CRs from the API server. |

#### Registration and image

| Case | Why it matters | Proposed handling |
|---|---|---|
| A wrong but well-formed `ansible_role`. | It passes resolution (§4.2) and then fails every task, deletes included. | Roll out an image that has a role at the recorded name (it may wrap the right role), so retries succeed, then [replace the NetworkClass](/enhancements/OSAC-1433-default-networking/design.md#replacing-the-networkclass) if wanted. |
| Registrations change while the operator is down. | A FAILED NetworkClass would never resolve. | At operator start, resolve every NetworkClass that is not READY, never a READY one. A ConfigMap that gains or loses a manager-type label counts as a registration added or removed; any other ConfigMap update triggers nothing. |

#### Kubernetes Manager hub network

| Case | Why it matters | Proposed handling |
|---|---|---|
| A Subnet's `create_subnet` runs while the owner Subnet is being deleted. | It would find the network owned and fall under the implementation limit for life. | Fail `retryable: true`, so it claims the network once the owner's delete finishes. The owner exists while its Subnet CR exists, also while being deleted. |

## 5. Interface Changes

| ID | Change | Requirements |
|---|---|---|
| IC-1 | Registration ConfigMaps, network types, and resolver validation (§4.2, §4.9). | FR-4, FR-7 |
| IC-2 | One generic playbook includes the registered `ansible_role` with `tasks_from: <task>`; settings and credentials come from the networking instance group's ConfigMap and Secret (§4.3). | FR-2, FR-8 |
| IC-3 | Fixed task set per manager type; OSAC never routes a task to the other manager (§4.10). | FR-1, FR-2, FR-4 |
| IC-4 | `osac_job_vars` input with snapshots and `ipam`; `osac_result` and `osac_error`; ordering and retries (§4.5–§4.8). | FR-6, FR-10, FR-12 |
| IC-5 | Fabric `network_type` input and `network_segment` result (§4.9). | FR-5 |
| IC-6 | `vm_attachment` result; SecurityGroup tasks, binding by `security_group_ids`, policy before traffic (§4.10). | FR-12, FR-13, FR-14 |
| IC-7 | Versioned conformance suite (§4.11). | FR-9, FR-11 |

## 6. Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Managers call each other directly. | Couples implementations and credentials; bypasses OSAC ordering, retries, and result checks. |
| Fabric and Kubernetes jobs run independently. | No guarantee that the consumer runs after the producer or that delete runs in reverse. |
| Managers exchange provider values through a ConfigMap OSAC never reads. | OSAC writes every consumer, so typed values it validates and shows in status are simpler. |
| Provider-written Kubernetes Managers. | Providers differ in their fabric, not in the hub; OSAC owns hub networking. |
| A `network_type` field on the NetworkClass. | The type follows from the registrations; deployments without VMs need no type. |
| The Fabric Manager chooses and publishes its own address range. | The bare-metal/VM split is deployment policy; a Fabric choice depends on the Kubernetes Manager and can starve VMs. |
| Return raw KubeVirt `networks` and `interfaces`. | OSAC would validate arbitrary VM spec, and managers would need KubeVirt knowledge. |
| Create the VM and let the Kubernetes Manager patch it. | The manager would edit a resource it does not own, and the VM would need a separate gate before use. |
| One attachment template per Subnet instead of per attachment. | Cannot carry per-VM needs (SDN ports, address reservations, per-VM policy). |
| Send each group's complete rules with every attachment, with no SecurityGroup task. | A rule update would rerun every attachment that selects the group; with one policy object per group it reruns one task per manager, and bound interfaces follow. |
| Workload tests that need a dedicated lab (no other Tenants or pools) and restate the registration in their config. | Providers rarely have a spare lab, and restated fields drift. Profiles with explicit ExternalIPs from the suite's own pool run in a shared lab and read the hub, as Gateway API conformance profiles and `csi-sanity` do. |

## 7. Observability and Monitoring

- NetworkClass `status.state` and `status.message` report resolution failures (§4.2).
- Resource and NetworkAttachment status report task failures, rejected results, the `osac_error` message, and retry state.
- Diagnostics include manager name and type, task, owner API ID, and AAP job ID, never credentials.
- The conformance report keeps pass, fail, or skip per test and per profile.

## 8. Impact and Compatibility

The contract adds no tenant-facing fields; Unified lists the fields removed in this release ([Upgrade and Downgrade Strategy](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy)).

**Installation order:**
1. Install the generic AAP job templates and an execution environment built on OSAC's image with the provider's Fabric collection.
2. Configure the ConfigMap and Secret `network-fulfillment-ig`, including `CUDN_EVPN_DNS_RESOLVERS` when the deployment selects `cudn_evpn`.
3. When the deployment selects `cudn_evpn`, configure its hub prerequisites (§4.12).
4. Create the Fabric Manager's registration ConfigMap. The installer creates the NetworkClass from Helm values and the registrations of OSAC's Kubernetes Managers; these may exist in any order (§4.2).
5. Networking creates are admitted once the NetworkClass is READY ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)).

Upgrading an existing installation is not supported ([Unified — Upgrade and Downgrade Strategy](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy)).

---

## Provenance

Authored: revise @ design 0.11.5 - a58bdf7, workspace docs/unified-networking-docs-structure @ 64da781
Final: revise @ design 0.11.5 - a58bdf7, workspace docs/unified-networking-docs-structure @ 64da781 (dirty)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"64da781 (dirty)","source_repo_branch":"docs/unified-networking-docs-structure","commits_behind_main":0,"commits_ahead_main":60,"main_ref":"main","phases":["revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
