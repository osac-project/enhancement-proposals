---
title: OSAC-1433 Network Manager Integration Contract Test Plan
last-updated: 2026-10-28
---

# Test Plan — OSAC-1433 Network Manager Integration Contract

## Contents

- [Overview](#overview)
  - [Test layers](#test-layers)
  - [Requirements traceability](#requirements-traceability)
- [Conformance suite](#conformance-suite)
  - [Task tests](#task-tests)
    - [TC-DELETE-02: Controlled create/delete overlap](#tc-delete-02)
  - [Profiles](#profiles)
  - [Profile setup](#profile-setup)
  - [Follow-up: network behavior tests](#follow-up-network-behavior-tests)
- [Test Cases](#test-cases)
  - [Test fixtures](#test-fixtures)
  - [Manager registration and fixed task set](#manager-registration-and-fixed-task-set)
    - [TC-REG-01: Reject invalid registration and NetworkClass selections](#tc-reg-01-reject-invalid-registration-and-networkclass-selections)
    - [TC-INVOKE-01: Run every fixed manager task through the generic playbook](#tc-invoke-01-run-every-fixed-manager-task-through-the-generic-playbook)
    - [TC-CONTRACT-02: Exercise task envelope fixtures](#tc-contract-02-exercise-task-envelope-fixtures)
    - [TC-FR2-01: Manually review manager requirements](#tc-fr2-01-manually-review-manager-requirements)
    - [TC-SETTINGS-01: Provide manager settings and credentials through the networking instance group](#tc-settings-01-provide-manager-settings-and-credentials-through-the-networking-instance-group)
    - [TC-SNAPSHOT-01: Send only the listed snapshot fields](#tc-snapshot-01-send-only-the-listed-snapshot-fields)
    - [TC-MANAGER-DELETE-01: Delete with the manager names recorded at create](#tc-manager-delete-01-delete-with-the-manager-names-recorded-at-create)
  - [VM attachment result and VM creation](#vm-attachment-result-and-vm-creation)
    - [TC-DESC-01: Return a valid `vm_attachment` from OSAC's Kubernetes Manager](#tc-desc-01-return-a-valid-vm_attachment-from-osacs-kubernetes-manager)
    - [TC-DESC-02: Build the VM network fields for Linux and Windows VMs](#tc-desc-02-build-the-vm-network-fields-for-linux-and-windows-vms)
    - [TC-DESC-03: Reject malformed `vm_attachment` results](#tc-desc-03-reject-malformed-vm_attachment-results)
    - [TC-VM-02: Create the VM after the attachment is ready](#tc-vm-02-create-the-vm-after-the-attachment-is-ready)
    - [TC-READY-01: Report readiness after both managers for a VM](#tc-ready-01-report-readiness-after-both-managers-for-a-vm)
    - [TC-POLICY-01: Select policy with the ComputeInstance API ID label](#tc-policy-01-select-policy-with-the-computeinstance-api-id-label)
    - [TC-VM-DELETE-01: Delete the VM before attachment policy cleanup](#tc-vm-delete-01-delete-the-vm-before-attachment-policy-cleanup)
  - [Network segment and results](#network-segment-and-results)
    - [TC-SEGMENT-02: Validate, store, and pass the network segment](#tc-segment-02-validate-store-and-pass-the-network-segment)
    - [TC-FR6-01: Validate typed outputs and task errors](#tc-fr6-01-validate-typed-outputs-and-task-errors)
    - [TC-FR6-02: Accept east-west FabricDomain results](#tc-fr6-02-accept-east-west-fabricdomain-results)
  - [Retries and concurrency](#retries-and-concurrency)
    - [TC-RETRY-03: Retry idempotently and serialize opposite actions](#tc-retry-03-retry-idempotently-and-serialize-opposite-actions)
    - [TC-CONCURRENCY-02: Serialize Subnet tasks per VirtualNetwork](#tc-concurrency-02-serialize-subnet-tasks-per-virtualnetwork)
  - [Addressing and lifecycle rules](#addressing-and-lifecycle-rules)
    - [TC-IPAM-01: Compute, record, and honor the Subnet address layout](#tc-ipam-01-compute-record-and-honor-the-subnet-address-layout)
    - [TC-IPAM-02: Handle empty ranges](#tc-ipam-02-handle-empty-ranges)
    - [TC-RULES-01: Verify the remaining contract rules](#tc-rules-01-verify-the-remaining-contract-rules)
    - [TC-WORKLOAD-01: Exercise bare-metal and Cluster workload flows](#tc-workload-01-exercise-bare-metal-and-cluster-workload-flows)
  - [Suite self-test](#suite-self-test)
    - [TC-CONFORMANCE-01: Report suite outcomes](#tc-conformance-01-report-suite-outcomes)
  - [Edge-case tests (later)](#edge-case-tests-later)
    - [TC-RETRY-02: Treat a lost AAP job as failed and never launch a job twice](#tc-retry-02-treat-a-lost-aap-job-as-failed-and-never-launch-a-job-twice)
    - [TC-EDGE-01: Resolve registrations across operator restarts](#tc-edge-01-resolve-registrations-across-operator-restarts)
    - [TC-EDGE-02: Accept segments under races and restarts](#tc-edge-02-accept-segments-under-races-and-restarts)
    - [TC-EDGE-03: Claim the `cudn_evpn` hub network after the owner's delete](#tc-edge-03-claim-the-cudn_evpn-hub-network-after-the-owners-delete)

## Overview

- **Feature:** OSAC-1433 Network Manager Integration Contract
- **Requirements covered:** FR-1 through FR-14

The [conformance suite](#conformance-suite) is what a provider runs against its Fabric Manager ([contract §4.11](design.md#411-conformance-tests)). The [test cases](#test-cases) are OSAC implementation tests, which OSAC runs, mostly with its mock and no-op managers and its own Kubernetes Managers; they are not part of the provider suite. A skipped required test is never a pass.

### Test layers

| Layer | Purpose |
|---|---|
| Task tests | Provider suite: every Fabric task in the manager's EE image with generated inputs, without OSAC ([contract §4.11](design.md#411-conformance-tests)). |
| Profiles | Provider suite: the `baremetal`, `vm`, and `cluster` scenarios of the lab's enabled services, run through OSAC's APIs in a test Tenant of a shared lab. |
| OSAC implementation tests | OSAC's own tests of registration, task selection, input capture, result validation, retries, and workload sequencing, mostly with the mock and no-op managers. |

TC-FR2-01 is a manual review. TC-CONFORMANCE-01 is OSAC's self-test of the suite. [Edge-case tests](#edge-case-tests-later) check the proposed handling of [contract edge cases](design.md#edge-cases-that-need-handling) and run once those rules are implemented. Network-behavior tests are a [follow-up](#follow-up-network-behavior-tests). Non-goals: [PRD](prd.md#22-non-goals).

### Requirements traceability

| Requirement | Test cases |
|---|---|
| FR-1 | TC-INVOKE-01, TC-CONTRACT-01, TC-PLAN-01, TC-VM-01, TC-BM-01, TC-CLUSTER-01 |
| FR-2 | TC-FR2-01, TC-CONTRACT-01, TC-CONTRACT-02, TC-SNAPSHOT-01 |
| FR-3 | TC-VM-01, TC-VM-02, TC-BM-01, TC-CLUSTER-01, TC-WORKLOAD-01 |
| FR-4 | TC-REG-01, TC-INVOKE-01 |
| FR-5 | TC-SEGMENT-01, TC-SEGMENT-02, TC-VM-01, TC-EDGE-02 |
| FR-6 | TC-FR6-01, TC-CONTRACT-02, TC-DESC-01, TC-DESC-03, TC-RESULT-01, TC-FR6-02 |
| FR-7 | TC-REG-01, TC-EDGE-01 |
| FR-8 | TC-SETTINGS-01, TC-SNAPSHOT-01 |
| FR-9 | TC-CONFORMANCE-01, TC-VM-01, TC-SG-01, TC-BM-01, TC-CLUSTER-01 |
| FR-10 | TC-RETRY-01, TC-RETRY-03, TC-DELETE-01, TC-DELETE-02, TC-CONCURRENCY-01, TC-CONCURRENCY-02, TC-VM-DELETE-01, TC-MANAGER-DELETE-01, TC-RULES-01, TC-RETRY-02, TC-EDGE-03 |
| FR-11 | TC-CONFORMANCE-01 |
| FR-12 | TC-IPAM-01, TC-IPAM-02, TC-CONTRACT-01, TC-PLAN-01, TC-EXHAUST-01, TC-VM-01, TC-BM-01 |
| FR-13 | TC-POLICY-01, TC-SG-01, TC-SG-02, TC-REJECT-01, TC-READY-01, TC-RULES-01 |
| FR-14 | TC-DESC-02, TC-VM-02, TC-READY-01 |

## Conformance suite

These are the networking tests of the [OSAC conformance suite](/enhancements/OSAC-XXXX-conformance-suite/design.md) (one image per OSAC release, `ghcr.io/osac-project/osac-conformance:<OSAC release>`), run against a Fabric Manager. The suite defines the run, the common configuration, the test Tenant and cleanup, and the report; [contract §4.11](design.md#411-conformance-tests) defines what networking adds: its configuration section, the profiles, and its report entry.

### Task tests

[Contract §4.11](design.md#411-conformance-tests) defines how a task test runs, its address plans, and which runs (host, overlay attachment, FabricDomain, ingress) it selects.

| Case ID | Title | Runs when | What it does | Pass condition | Contract section |
|---|---|---|---|---|---|
| TC-CONTRACT-01 | succeeds with valid input and returns exactly its typed output | Always; its host, overlay attachment, FabricDomain, and ingress runs as §4.11 selects them. | Runs each task with valid generated input and fresh API IDs; a documented no-op passes. | The task succeeds. `osac_result` has exactly the task's typed outputs, each passing its §4.10 acceptance rule (`dhcp_lease`: a lease the host obtained after its port moved; `backend_id`: a string). Every object that appeared in `taskTests.namespace` during the job carries both owner labels (the suite lists the namespace before and after each job). | §4.3, §4.6, §4.8, §4.10 |
| TC-RETRY-01 | returns the same result when run again with the same input | As TC-CONTRACT-01. | Runs every create, apply, attach, reserve, and `query_dhcp_lease` task again with the same input. | It succeeds with the same result. | §4.7 (Idempotency) |
| TC-DELETE-01 | succeeds twice after its create and once for an API ID never created | As TC-CONTRACT-01. | Runs each delete, detach, and release twice after its create, and once for an API ID that was never created. | Every run succeeds. | §4.6, §4.7 (Idempotency) |
| TC-DELETE-02 | cleans a cancelled task with ordered completion or a fenced late write | As TC-CONTRACT-01, for each stateful task; permitted no-ops use the no-write check below. | [Controlled create/delete overlap](#tc-delete-02): pause an issued mutation, cancel its job, start matching cleanup, observe delete progress or success, then release the mutation without waiting for delete success. Retain a second live API ID as an isolation control. | Delete succeeds within the configured deadline after ordered cleanup or with an enforced late-write fence. Backend inventory, hub state and mutation history show no state for the deleted ownership key after success, and the live control is unchanged. Inspect before repeating delete or any corrective cleanup; the repeat succeeds. | §4.7 (Cancel on delete, Ownership) |
| TC-REJECT-01 | enforces SecurityGroup rules exactly or rejects them as final | Always. | Runs `create_security_group` with rules of each protocol (`tcp`, `udp`, `icmp`, `all`), one group per protocol, and one group with 1,000 `tcp` ingress rules of distinct ports (capacity). | Each create succeeds (also as a documented no-op), or fails with `osac_error` and `retryable: false` (a rule the backend cannot enforce exactly, or a rule set it cannot hold). After a failure, the delete succeeds and no hub object with the group's owner ID remains. | §4.10 (SecurityGroup) |
| TC-SG-02 | reruns SecurityGroup rules and binds attachments by SecurityGroup ID | Always; the overlay apply and its delete only when VMaaS is enabled; the physical apply and its delete are host runs. | Runs `create_security_group`, then again with other rules (an enforceable change, then one with a rule or rule set TC-REJECT-01 found unenforceable or too large, if any); runs the overlay `apply_network_attachment` (with an `interface.ipv4_address` from the overlay range) and the physical one, each with that group's ID in `security_group_ids`, their deletes, and then `delete_security_group`. | The create and the enforceable re-run succeed (also as documented no-ops); the unenforceable or too large re-run fails with `retryable: false`; each apply binds by ID and succeeds (the overlay apply may be a documented no-op; the physical apply too); every delete succeeds. | §4.10 (SecurityGroup, attachments) |
| TC-EXHAUST-01 | fails as final when a pool or LB VIP range is full | Always; the `reserve_cluster_ingress_ip` part is an ingress run. | Runs `create_external_ip` on a /31 pool until no address is free, and `reserve_cluster_ingress_ip` with distinct `cluster_id`s on a /26 Subnet whose LB VIP range is one /28 (plan 0.5/0.25/0.25 or 0/0.75/0.25) until that range is full; then once more each. | The extra calls fail with `osac_error` and `retryable: false`; the suite logs the message for review and does not check its wording. | §4.10 |
| TC-SEGMENT-01 | returns a valid and stable network segment | Always; the `network_type` runs for each declared network type; the runs without `network_type` only when the lab NetworkClass has no Kubernetes Manager. | Runs `create_virtual_network` and `create_subnet` with each declared network type as `network_type` (two Subnets in one VirtualNetwork, one in a second), and again without it (see Runs when); reruns each `create_subnet`. | With `network_type`, `create_subnet` returns `network_segment` with `type` equal to the input, and `l2_vni` and `l3_vni` YAML/JSON integers (not strings) from 1 to 16777215 that differ; the rerun returns the same values. Subnets of one VirtualNetwork return different `l2_vni` and the same `l3_vni`; Subnets of two VirtualNetworks share no VNI. Without `network_type`, no `network_segment`. | §4.9 |
| TC-PLAN-01 | accepts both address plans, including empty ranges | Always; the runs without `network_type` only when the lab NetworkClass has no Kubernetes Manager. | Runs `create_subnet`, a rerun, and `delete_subnet` on Subnets laid out from two plans each (overlay/fabric/lbVip): with each declared network type 0.75/0.25/0 and 1/0/0, without `network_type` 0/0.75/0.25 and 0/1/0. | Every run succeeds, also with `[]` for `physical_ipv4_cidrs` or `lb_vip_ipv4_cidrs`, and the rerun returns the same result. | §4.8, §4.10 |
| TC-CONCURRENCY-01 | runs parallel jobs on distinct resources with distinct results | Always; the `reserve_cluster_ingress_ip` pair is an ingress run. | Starts two jobs on distinct resources at once: two `create_external_ip` in one pool, two `reserve_cluster_ingress_ip` on one Subnet, and, with each declared network type, two `create_subnet` in different VirtualNetworks. | Each job succeeds, at once or when the suite reruns it after a failure with `retryable: true` (at most 3 reruns); the two addresses differ; the two Subnets share no VNI. | §4.7 (Concurrency) |
| TC-RESULT-01 | returns only contract-shaped results and errors, with no secret | Always. | Checks every result and error of the run. | No `osac_result` key outside the task's typed outputs; no `osac_result` from a task without one; every `osac_error` is exactly `{message, retryable}`, with a non-empty string and a boolean. No value of the Secret `network-fulfillment-ig` appears in any result, error, or job output. One extra run of `create_virtual_network` with none of the manager's settings set fails with `retryable: true`. | §4.3, §4.6 |

<a id="tc-delete-02"></a>

#### TC-DELETE-02: Controlled create/delete overlap

**Planned fixture requirements.** The conformance harness needs provider-specific test controls that pause/release an already-issued mutation, signal that cleanup reached the backend or is waiting behind that mutation, and expose operation settlement, commit/rejection history and owned backend inventory. These are test-fixture requirements under the conformance work, not new production manager APIs or claims that such hooks already exist. Record the actual ownership key from §4.7 (for attachment state, the target API ID), not an assumed resource-name match. Use the configured `timeouts.delete` as a bounded failure deadline for progress and completion; elapsed time or an absent GET is never evidence that an outstanding mutation settled.

1. Prepare the task's normal parents, a fresh subject API ID and a second live API ID of the same resource kind. Snapshot the control's backend/hub state. Use a separate parent for the control where capacity requires it, such as the /32 ExternalIP allocation case.
2. Start the subject's create, apply, attach or reserve task and pause one already-issued backend mutation before it commits. Record the operation ID, ownership key and pause stage. Cancel the job as AAP cancellation would, then start the matching delete, detach or release with its stored input.
3. Wait for an explicit fixture event showing that cleanup reached the backend, is waiting behind the outstanding mutation, or already succeeded. Record the event and operation ordering. Do not require delete success before releasing the paused mutation.
4. Release that exact mutation. Wait for authoritative settlement of the released operation and cleanup completion within the configured deadline. Evaluate the actual recorded success/commit order using the two allowed outcomes below, including when a delete that was initially pending subsequently establishes a fence.
5. Inspect backend inventory, hub objects and mutation history before retrying delete or performing corrective cleanup. Nothing owned by the subject may remain after successful deletion or be recreated afterward. The live control must retain its state. A later cleanup that removes resurrected state does not make the test pass.
6. Repeat the matching delete and require success. For a killed `create_external_ip` using a /32 pool, create with a new API ID and verify the address is available again only after the subject's successful cleanup.

| Observed order | Required outcome |
|---|---|
| Outstanding mutation settles before delete succeeds | Deletion may remain pending while the mutation is held. After release, it removes all partial/committed state before reporting success. |
| Delete succeeds before the outstanding mutation settles | The backend enforces closure against that exact mutation. On release it is rejected or becomes a no-op, with no post-success recreation, even temporarily. |

A task that is expressly permitted to be a documented no-op has no mutation to pause: verify its no-write trace and successful matching cleanup, and report that path explicitly. Missing controls for a task with real side effects are missing evidence, not a successful no-op result. A timeout, an operation with unknown outcome, or indefinitely pending cleanup is not a pass.

The suite's oracle self-test must pass both safe fixtures (ordered completion and an enforced fence) and fail a deliberately unsafe fixture that reports delete success and then permits the held write to recreate state. Retain traces of task/job events, operation IDs, mutation ordering, backend IDs and inventories. This checks the test's acceptance rules without claiming a real provider's fencing or ordering mechanism has been demonstrated.

### Profiles

Each case runs as described in [Profile setup](#profile-setup).

| Case ID | Title | Profile | What it does | Pass condition | Contract section |
|---|---|---|---|---|---|
| TC-BM-01 | a bare-metal instance gets a fabric address, SSH, and egress, and a blocked port stays closed | `baremetal` | Creates a bare-metal instance ([BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md)) with an ExternalIP from the suite's pool, then deletes it. The instance listens with `nc -l` on TCP 8080, which its SecurityGroup does not allow. | Ready within `bareMetalReady`, with the port move done: the lease is found and `NETWORK_READY` is True. Address in `physical_ipv4_cidrs`. The runner reaches it with SSH through its ExternalIP, and `curl -sS <egressURL>` run there succeeds through the NATGateway. From the runner, TCP 8080 on its ExternalIP does not connect while SSH does. Within `delete` after the delete: the ExternalIP no longer answers, and the instance and its NetworkAttachment are gone. | §4.8, §4.10 (physical attachment, `query_dhcp_lease`) |
| TC-VM-01 | two VMs on one Subnet are reachable through their ExternalIPs and reach the outside | `vm` | Creates two VMs on one Subnet ([VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md)), each with an ExternalIP from the suite's pool, then deletes them. Egress and inbound traffic cross the Fabric gateway for VMs, so this also proves the hub extension (§4.9). | Ready within `vmReady`. Addresses in `overlay_ipv4_cidrs`. The runner reaches each VM with SSH through its ExternalIP, and `curl -sS <egressURL>` run there succeeds through the NATGateway. Cleanup as in TC-BM-01. | §4.8, §4.9, §4.10 |
| TC-SG-01 | a SecurityGroup allows and blocks ports between two VMs, and a rule update swaps them | `vm` | On the two VMs of TC-VM-01, with different SecurityGroups: `nc -l` on an allowed and a blocked port in one VM, connect from the other; then update the listening VM's group rules to allow only the blocked port. Each manager enforces VM SecurityGroups, or documents its Fabric part as a no-op. | The allowed port connects; the blocked port does not. After the Update, the suite waits until the SecurityGroup's `Ready` reason went to `Updating` and back to `Succeeded` (its `create_security_group` re-run done on both managers, with no attachment task); then the two ports swap. | §4.10 (SecurityGroup) |
| TC-CLUSTER-01 | the smallest Cluster becomes Ready and its api and *.apps names answer | `cluster` | Creates the smallest Cluster ([CaaS](/enhancements/OSAC-1436-caas-networking/design.md)), then deletes it. Its external access is automatic, as CaaS requires. | Ready within `clusterReady`; workers join, which needs the hairpin from the NATGateway to the API ExternalIP. Worker addresses in `physical_ipv4_cidrs`. `api` and `*.apps` names resolve to the automatic ExternalIPs and answer from the runner. A pod the suite starts with the Cluster's kubeconfig, through the public `api` name, runs `curl -sS <egressURL>` successfully through the NATGateway. After the delete: the Cluster, the worker NetworkAttachments, and the automatic resources are gone, and the ExternalIPs no longer answer. | §4.8, §4.10 (`attach_external_ip`, `reserve_cluster_ingress_ip`) |

### Profile setup

The [OSAC conformance suite](/enhancements/OSAC-XXXX-conformance-suite/design.md) defines the test Tenant and the final cleanup; [contract §4.11](design.md#411-conformance-tests) defines the suite's ExternalIPPool and the networking configuration errors. Other Tenants and pools may exist in the lab. Creating the test Tenant creates its Default Networking, including the default NAT ExternalIP from a READY lab pool or the suite's pool; the final cleanup deletes the Tenant, with its defaults, before the suite's pool. Every profile:
- creates its resources through the private API with `metadata.tenant` set to the test Tenant;
- waits for the test Tenant's `DefaultNetworkingReady`, and for every networking resource it creates to be READY, within `networkReady`; on a timeout every test of the profile fails with the resource's state, message, and latest job entry, naming its manager (the Fabric Manager or OSAC's Kubernetes Manager);
- creates its own VirtualNetwork `10.200.0.0/16` and Subnet `10.200.0.0/22` (or the next free /16 in `10.0.0.0/8` when that overlaps a lab pool, `excludedIpv4Cidrs`, or a Cluster pod or service CIDR), laid out from the lab's address plan ([contract §4.8](design.md#48-addressing)), its SecurityGroups, and a NATGateway on an ExternalIP from the suite's pool;
- has its workloads select one SecurityGroup that allows `all` from the Subnet CIDR, `tcp` 22 from anywhere, and egress `all` to anywhere; except the two VMs of the `vm` profile, which select from creation only TC-SG-01's groups (listener: `tcp` 22 from anywhere and the allowed port from the Subnet CIDR; client: `tcp` 22 from anywhere; both egress `all`);
- creates its workloads without automatic external access (a Cluster always has it) and with the suite's SSH public key (through the workload's SSH key or `user_data` field), and waits for Ready within its `timeouts` value;
- gives each VM or bare-metal workload an ExternalIP from the suite's pool through an ExternalIPAttachment, reaches it by SSH through that ExternalIP from the runner, and runs `curl -sS <egressURL>` over that session; for a Cluster, its `api` and `*.apps` names answer through its automatic ExternalIPs, and `curl` runs in a pod started with the Cluster's kubeconfig through the public `api` name;
- deletes its ExternalIPAttachments and checks that the ExternalIPs no longer answer, then deletes its workloads and checks that they, their NetworkAttachments, and a Cluster's automatic resources are gone.

### Follow-up: network behavior tests

A later suite layer measures network behavior directly; until then these are not conformance cases:

- Isolation: overlapping CIDRs stay apart across VirtualNetworks; Subnets of one VirtualNetwork route at L3 and stay separate L2 domains; workloads on one Subnet share its L2 domain.
- DHCP: each server hands out only its own range and answers only its own interfaces, with the Subnet's mask, `gateway_ipv4`, and reachable resolvers.
- SecurityGroups: the full ingress and egress matrix for both managers, measured with probes, including ICMP, Fabric enforcement on bare-metal ports and VM addresses, and the overlay baseline deny.
- NAT: the NATGateway source address, no new inbound connections, and hairpin from a NATGateway to an ExternalIP within one VirtualNetwork and across VirtualNetworks, beyond what TC-CLUSTER-01 covers.
- Cleanup audit: no backend state left for deleted API IDs.

## Test Cases

OSAC implementation tests ([Overview](#overview)).

### Test fixtures

- **Reference no-op manager:** an OSAC test role that implements every Fabric task as a documented no-op and returns no typed output, so it passes only the task tests that need none.
- **Mock manager:** an OSAC test role for both manager types that returns deterministic, valid typed outputs keyed by resource API ID. It has a one-shot failpoint keyed by manager type, task, and stable resource API ID. The failpoint can stop a task after its backend side effect but before it publishes `osac_result`, and can also wrap another manager's role (TC-CONFORMANCE-01). Test cases clear the failpoint explicitly before retrying.

Both live in OSAC's test code; providers do not use them.

### Manager registration and fixed task set

#### TC-REG-01: Reject invalid registration and NetworkClass selections

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Test each FAILED condition of [contract §4.2](design.md#42-registration-and-capabilities) as its own case, including `network_type` on a Fabric Manager, `capabilities` on a Kubernetes Manager, the typo `networkTypes`, and a Kubernetes Manager whose `network_type` the Fabric Manager does not declare (the message names both). Each sets the NetworkClass to FAILED with the reason in `status.message` and launches no AAP job. A key with an empty value (for example `capabilities: ""`) is accepted as absent. A valid selection records the Kubernetes Manager's type in the NetworkClass status `network_type`, or leaves it empty without one. Creating or deleting a labelled registration resolves a FAILED NetworkClass again. Create both registrations before the NetworkClass CR and verify it becomes READY. Delete a READY NetworkClass's registration and verify the NetworkClass stays READY. A task outside the manager type's fixed task set is rejected, not routed elsewhere.

#### TC-INVOKE-01: Run every fixed manager task through the generic playbook

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Run a task against two implementations of a manager type. Verify OSAC selects the manager from NetworkClass and the task from the fixed set, includes the registered `ansible_role` with `tasks_from: <task>`, and sends both the same input; providers add no AAP job templates. Verify every networking job template sets `ask_labels_on_launch: true` and an AAP job timeout of 60 minutes. Verify every job has the AAP label `osac-<task>-<manager>-<resource API ID>-<attempt>`, `attempt` grows by one per launch, and the `status.jobs` entry is `Running` before the launch and has the `jobID` after it. With the registered role or its task file missing from the image, verify the job fails with `osac_error.retryable: true` and a retry succeeds once the image has it.

#### TC-CONTRACT-02: Exercise task envelope fixtures

##### Preconditions

- **Tier / owner:** Component integration / [DEV].

Run the reference no-op manager for tasks without typed outputs and the mock manager for tasks with them, with at least one fixture per fixed task (including the optional pair when enabled). Verify each fixture supplies the common and task-specific inputs and OSAC accepts a matching result of the expected shape. Verify an unknown task launches no job, and managers neither call one another nor write OSAC workload objects.

#### TC-FR2-01: Manually review manager requirements

Review every task section in the contract's Task reference and verify it defines when it is called, its inputs and the spec fields it uses, the end state it must reach, its typed result, and its delete behavior. Confirm a provider can implement a Fabric Manager from the contract alone.

#### TC-SETTINGS-01: Provide manager settings and credentials through the networking instance group

##### Preconditions

- **Tier / owner:** Component integration / [DEV].

Put a test value in the ConfigMap and Secret `network-fulfillment-ig`, launch a manager task, and verify the manager receives both as environment variables. Verify a task also runs with no ConfigMap and an empty Secret, and secret values are absent from `osac_job_vars`, `osac_result`, and task logs.

#### TC-SNAPSHOT-01: Send only the listed snapshot fields

##### Preconditions

- **Tier / owner:** Unit / [DEV].

For every task fixture, verify each snapshot's `spec` has only the fields the task's [§4.10](design.md#410-task-reference) section lists, and unlisted keys are absent from `osac_job_vars`. Verify a physical attachment's `target` is exactly `{kind: BareMetalInstance, id, host_name}`, every attachment's `network_attachment.security_group_ids` holds only the selected groups' API IDs (no rules), the Kubernetes overlay apply gets no `interface.ipv4_address` and every later task of the attachment (the Fabric apply and both deletes) gets the same VM address in it, and that `tenant` equals the CR's `osac.openshift.io/tenant` annotation. Set secret-bearing CR fields (for example a ClusterOrder pull secret and BareMetalInstance user data) and verify none of them reaches `osac_job_vars` or task logs.

#### TC-MANAGER-DELETE-01: Delete with the manager names recorded at create

##### Preconditions

- **Tier / owner:** Unit / [DEV].

After a resource is created, recreate the manager's registration ConfigMap with a different `ansible_role`, then delete the resource. Verify the delete runs the `{name, ansibleRole}` recorded in `status.networkManagers`.

### VM attachment result and VM creation

#### TC-DESC-01: Return a valid `vm_attachment` from OSAC's Kubernetes Manager

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Run `cudn_evpn`'s `apply_network_attachment` with valid input. Verify `vm_attachment` has only `namespace`, and that namespace exists in the hub with `osac.openshift.io/tenant` equal to the input `tenant`.

#### TC-DESC-02: Build the VM network fields for Linux and Windows VMs

##### Preconditions

- **Tier / owner:** Unit / [DEV].

VMaaS flow ([VMaaS design](/enhancements/OSAC-1435-vmaas-networking/design.md)). Verify VMaaS creates the VM in the `vm_attachment` namespace with exactly `networks: [{name: tenant, pod: {}}]` and `interfaces: [{name: tenant, binding: {name: l2bridge}}]` in both Linux and Windows templates, and that the VM gets its address from the namespace's primary network.

#### TC-DESC-03: Reject malformed `vm_attachment` results

##### Preconditions

- **Tier / owner:** Unit / [DEV].

For Kubernetes `apply_network_attachment`, reject: missing `namespace`; nonexistent namespace; namespace without `osac.openshift.io/tenant` equal to the tenant API ID from `osac_job_vars.tenant`; and any additional field such as `network`, `binding`, `labels`, or raw `networks`. The NetworkAttachment stays non-ready and VMaaS creates no VM.

#### TC-VM-02: Create the VM after the attachment is ready

##### Preconditions

- **Tier / owner:** E2E / [QE].

Create an overlay NetworkAttachment with `spec.target` = `{kind: ComputeInstance, id: <API ID>}` and `spec.subnet` = the Subnet API ID. While the Kubernetes apply runs, verify no VirtualMachine exists. After OSAC accepts the `vm_attachment` result, verify VMaaS creates the VM with the mapped network fields and requested run strategy, and the manager never reads or modifies the VM. Verify the Fabric overlay apply starts only once VMaaS reported the VM's address, and the NetworkAttachment becomes Ready only after it succeeds.

#### TC-READY-01: Report readiness after both managers for a VM

##### Preconditions

- **Tier / owner:** Component integration / [DEV].

On a Subnet with both managers recorded, verify the Subnet becomes Ready only after both managers' create tasks succeed; a SecurityGroup becomes READY only after both managers' `create_security_group` succeed (Fabric first), whatever services are enabled; an overlay NetworkAttachment becomes Ready only after the Kubernetes and then the Fabric `apply_network_attachment` succeed; a physical one after the Fabric `apply_network_attachment` succeeds, with no Kubernetes attachment task; an ExternalIP becomes ALLOCATED after its Fabric task alone.

#### TC-POLICY-01: Select policy with the ComputeInstance API ID label

##### Preconditions

- **Tier / owner:** E2E / [QE].

Verify VMaaS sets `osac.openshift.io/compute-instance-id: <ComputeInstance API ID>` in the VM's `spec.template.metadata.labels`. Verify the Kubernetes attachment binds the VM pod by the API ID label, the Fabric overlay attachment gets the VM's address in `interface.ipv4_address`, and a VM pod (`kubevirt.io: virt-launcher`) without that label receives no tenant traffic under the Subnet baseline. Verify a disk import pod on the Subnet's network that no attachment policy selects also receives no tenant traffic. Run `cudn_evpn` `create_security_group` with an ICMP rule and verify ICMP is enforced exactly as the rule says (or the task fails with `retryable: false`), and every NetworkPolicy sets both `Ingress` and `Egress` in `policyTypes`.

#### TC-VM-DELETE-01: Delete the VM before attachment policy cleanup

##### Preconditions

- **Tier / owner:** E2E / [QE].

Verify VMaaS deletes the VM and sees it gone before deleting the NetworkAttachment, and the Fabric `delete_network_attachment` runs before the Kubernetes one. Make the mock manager fail the Kubernetes `delete_network_attachment` once; verify the failure keeps the NetworkAttachment finalizer and blocks ComputeInstance deletion, and after the failpoint is cleared the retry unbinds the VM and removes its per-VM objects.

### Network segment and results

#### TC-SEGMENT-02: Validate, store, and pass the network segment

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With the mock manager, verify:
- the Fabric task runs first on create and the Kubernetes task first on delete;
- a VirtualNetwork records `status.networkType` with its managers, its children copy it, and ExternalIPPools and their children have none;
- Fabric `create_virtual_network`, `create_subnet`, and their deletes get `network_type` only when the resource records a Kubernetes Manager;
- OSAC accepts a valid `network_segment` and writes it to `Subnet.status.networkSegment` in the status update that sets the Fabric `create_subnet` entry to `Succeeded`, and no Kubernetes task of the Subnet or its NetworkAttachments starts without it;
- the segment goes to every Kubernetes task of the Subnet and its NetworkAttachments and to no Kubernetes `create_virtual_network`, and `status.taskInput` stores neither `network_type` nor `network_segment`;
- each acceptance rule of [contract §4.9](design.md#49-network-types-and-the-network-segment) gets one case, including string VNIs, a value that differs from the stored one (which stays), and a segment returned without `network_type` in the input. Each is a final failure whose tenant-visible message names only the broken rule, with no VNI or resource ID;
- a segment reusing the VNIs of a Subnet whose Fabric `delete_subnet` succeeded is accepted, even while that Subnet's CR exists;
- a segment whose only conflict is a Subnet in another VirtualNetwork, or a sibling in the same VirtualNetwork, whose Fabric `delete_subnet` is running, waiting for a retry (also after it freed the VNI and then failed), or has succeeded and is not yet processed, is not rejected and is accepted once that delete succeeds; for the sibling, the delete's retry starts while the waiting create's entry is `Running`.

The manager side is TC-SEGMENT-01.

#### TC-FR6-01: Validate typed outputs and task errors

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Verify OSAC rejects, before dependent work starts, a result that breaks [contract §4.6](design.md#46-task-result-and-errors) or a [§4.10](design.md#410-task-reference) acceptance rule, one case per rule (ExternalIP, cluster ingress including the Subnet's broadcast address, `dhcp_lease` MAC and address, `vm_attachment`), and reads results only from the job it launched. For create, apply, attach, reserve, and `query_dhcp_lease`, verify OSAC retries only in the §4.6 cases; for the timeout case the test shortens the job template timeout and verifies OSAC detects it from the AAP job record (status `failed` with AAP's timeout job explanation, no `osac_error`) and records the entry message 'job timed out after 60 minutes'. For create, apply, attach, and reserve, verify the CR shows `Ready=False`, reason `Progressing`, meanwhile, and that `retryable: false`, a failed play without `osac_error`, and a rejected result stop retries with `Ready=False`, reason `Failed`, and the message in status. For `query_dhcp_lease`, verify the NetworkAttachment `Ready` condition never changes, while it retries and after a final or rejected result, which stops the queries and sets its `query_dhcp_lease` job entry to state `Failed`. Verify success sets `Ready=True`, reason `Succeeded`. Verify delete tasks are retried after every failure.

#### TC-FR6-02: Accept east-west FabricDomain results

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With Ethernet east-west enabled and the Fabric Manager declaring `eastWestEthernet`, create and delete a FabricDomain. Verify OSAC runs `create_fabric_domain` and `delete_fabric_domain`, accepts results only from the job it launched, and updates status only after each accepted result. Without east-west, the capability, or BMaaS enabled, verify no FabricDomain task is launched.

### Retries and concurrency

#### TC-RETRY-03: Retry idempotently and serialize opposite actions

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With the mock manager, verify:
- Partial create: the mock completes a backend create/apply but fails before OSAC accepts its result. After the job is terminal, the retry gets the same stored input, returns the same typed output, and creates no duplicate backend state.
- Delete/detach during a running create/apply job (separate resource and workload-interface cases): OSAC cancels the job in AAP. Only when AAP reports it ended does OSAC set its `status.jobs` entry to `Cancelled` (also when the job succeeded) and ignore its result. OSAC then launches the delete with the stored input and the managers in `status.networkManagers`, without waiting for the job's work to finish. The delete cleans up the partial state the cancelled job left.
- A delete while an entry is `Retrying`: the entry becomes `Cancelled`, and no retry starts.
- A failing create is retried after 2, 4, 8, 16, 30, and 30 minutes, then every 30 minutes with no attempt limit. Meanwhile the CR shows `Ready=False`, reason `Progressing`, and the API message has the manager's message and the next retry time.
- Once the resource, the NetworkAttachment, or its target workload has a deletionTimestamp, OSAC starts no create, apply, attach, reserve, or `query_dhcp_lease` job.

#### TC-CONCURRENCY-02: Serialize Subnet tasks per VirtualNetwork

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Create two Subnets in one VirtualNetwork at once. Verify OSAC runs at most one Subnet task at a time per VirtualNetwork, and the second Subnet's task starts only after the first ends. Create attachments for two workloads on one Subnet at once and verify their tasks run in parallel. On one ClusterOrder, verify two jobs of one task never run at once, while jobs of different tasks (for example `publish_public_dns_api` and `reserve_cluster_ingress_ip`) run in parallel.

### Addressing and lifecycle rules

#### TC-IPAM-01: Compute, record, and honor the Subnet address layout

##### Preconditions

- **Tier / owner:** Unit / [DEV].

On a /24, create Subnets with the plans (overlay/fabric/lbVip) 0.5/0.25/0.25, 0.75/0.25/0, 1/0/0, and 0.5625/0.25/0.1875 with a Kubernetes Manager, and 0/0.75/0.25 and 0/1/0 without one. Verify `status.ipam` follows [contract §4.8](design.md#48-addressing): ranges in the order overlay, fabric, lbVip from the network address, each the fewest aligned CIDRs in ascending order (0.5625/0.25/0.1875 of `x.0/24`: `[x.0/25, x.128/28]`, `[x.144/28, x.160/27, x.192/28]`, `[x.208/28, x.224/27]`), `[]` for a share of 0, and `gateway_ipv4` the network address plus one; and that both managers receive it unchanged in `osac_job_vars.ipam`. Attach one VM and one bare-metal host to a shared Subnet and verify the VM address is in `overlay_ipv4_cidrs`, the host address is in `physical_ipv4_cidrs`, neither is in `lb_vip_ipv4_cidrs` or equal to `gateway_ipv4`, and both DHCP servers hand out the Subnet's mask and `gateway_ipv4` as the router. Verify the Fabric DHCP does not answer the VM's MAC and the Kubernetes Manager's DHCP does not answer the host's MAC. Verify later tasks, including delete, receive the recorded layout from `status.ipam`, not a recomputed one. Verify a rollout that changes the plan while a VirtualNetwork exists fails and names the field. Verify fulfillment rejects a Subnet whose prefix length is too long for its plan (for example a /27 with 0.5/0.25/0.25 or a /25 with 0.5625/0.25/0.1875; [Unified — Subnet address layout](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout)), and no manager task runs for it.

#### TC-IPAM-02: Handle empty ranges

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With the mock manager, verify Fabric `create_subnet` and `delete_subnet` run and succeed with `[]` lists. On a Subnet with no overlay range (0/1/0), a `dhcp_lease` equal to `gateway_ipv4` (now in the physical range) is rejected. Run `cudn_evpn` `create_subnet` with 0.5/0.25/0.25, 0.75/0.25/0, and 1/0/0 and verify `reservedSubnets` lists exactly the CIDRs outside `overlay_ipv4_cidrs` (none for 1/0/0).

#### TC-RULES-01: Verify the remaining contract rules

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With the mock manager, verify OSAC handles each rule; the suite checks the manager side in TC-DELETE-01, TC-DELETE-02, TC-REJECT-01, TC-SG-02, and TC-CONCURRENCY-01:
- An implementation-limit Subnet of a Kubernetes Manager: its Subnet tasks succeed without changes, the attachment apply fails with `retryable: false`, and the attachment delete then succeeds. Run with `cudn_evpn` instead of the mock, only the first Subnet whose Kubernetes `create_subnet` runs gets the hub network (in a tenant's default VirtualNetwork, the default Subnet), which records that Subnet's API ID; a rerun keeps it; a Subnet created after the owner is deleted claims it. A missing hub prerequisite fails `create_subnet` with `retryable: true`.
- A resource or NetworkAttachment whose create, apply, attach, or reserve job never started for a manager is deleted without that manager's matching delete, detach, or release task, and its finalizer is removed once every manager whose create started has deleted. After OSAC rejects a Subnet's `network_segment`, the Subnet delete runs only the Fabric `delete_subnet`.
- A delete succeeds when its create never ran or was cancelled.
- Every object the manager creates in the hub carries `osac.openshift.io/owner-kind` (lower-case kind) and `osac.openshift.io/owner-id`.
- A SecurityGroup rule update captures a new input and runs `create_security_group` on the recorded managers (Fabric, then Kubernetes) as the next attempt (also for a FAILED group), and no attachment task; a READY group shows `Updating` from the Update's own transaction and keeps `Ready=True`, reason `Updating`, until the run on every recorded manager succeeds, then `Succeeded` ([Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup)); a final failure sets it FAILED. A workload create that selects a SecurityGroup that is not READY is rejected ([Unified creation gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)).
- A SecurityGroup records the Fabric Manager, and the Kubernetes Manager when its VirtualNetwork has one, whatever services are enabled (also with only VMaaS); its create, rule updates, and delete run on both.
- `create_external_ip_pool` makes every eligible address available, including both addresses of a /31 and the one address of a /32, and fails when the backend cannot serve every eligible address.
- Parallel `create_external_ip` calls on one pool, and parallel `reserve_cluster_ingress_ip` calls on one Subnet, never return the same address.
- A delete requested during a running job recorded in `status.jobs` that is not part of the delete (attach, reserve, `query_dhcp_lease`, or a `manager: none` job) cancels that job first.
- With provider networking disabled, OSAC launches no networking job, and every delete removes the finalizer without a task. A delete during a VMaaS `provision` job or a CaaS core install job cancels it, and the deprovision or core delete job starts only after AAP reports it ended.

#### TC-WORKLOAD-01: Exercise bare-metal and Cluster workload flows

##### Preconditions

- **Tier / owner:** E2E / [QE].

With the mock manager, run BMaaS and CaaS worker create/delete flows with the same fixed manager contract (the provider profiles' cases are TC-BM-01 and TC-CLUSTER-01). Verify the NetworkAttachment is Ready before the handoff reboot, `query_dhcp_lease` follows the reboot and, while no lease is found, repeats every 30 seconds and every 5 minutes from the 20th attempt, and teardown waits for port restoration. Verify CaaS worker attachment tasks carry tenant `system`. The Cluster flow follows the CaaS workload service design and adds no task fields to the shared input.

### Suite self-test

#### TC-CONFORMANCE-01: Report suite outcomes

##### Preconditions

- **Tier / owner:** E2E / [QE].

Suite self-test of the networking area, run by OSAC for each release ([contract §4.11](design.md#411-conformance-tests), Ownership). The generic behavior (report keys, JUnit XML, result rules, cleanup after a failing profile, focused runs) is tested by the [conformance suite test plan](/enhancements/OSAC-XXXX-conformance-suite/testplan.md). This case covers only what networking adds:
- In CI, run the task tests against the reference no-op manager: every task test the no-op supports passes.
- Exercise the [TC-DELETE-02 oracle](#tc-delete-02) against safe ordered and fenced backend fixtures, which pass, and an unsafe post-success resurrection fixture, which the oracle rejects.
- In the E2E lab with a real EVPN Fabric Manager and VMaaS, BMaaS, and CaaS enabled, run without `taskTests.hosts`: the host runs are `skip` and `baremetal` does not pass.
- In a second lab installed with only VMaaS enabled and without `taskTests.hosts` (enabling BMaaS or CaaS on a lab with networking resources is not supported): the host and ingress runs are `skip`; the SecurityGroup and overlay attachment runs (TC-REJECT-01, TC-SG-02 without its physical part) run; only `vm` is required; the report is `conformant`.
- The networking entry in `components[]` matches the lab hub's registration (§4.11), and `profiles[]` has `required: true` exactly for the profiles of the enabled services (`baremetal`: BMaaS, `vm`: VMaaS, `cluster`: CaaS).
- The task tests use the settings and secrets of the lab's ConfigMap and Secret `network-fulfillment-ig`.
- The suite stops with a configuration error for each check of §4.11 (`vm` without `evpn` in the registration, `cluster` without BMaaS enabled, provider networking disabled, an address plan that leaves a required profile a range it uses empty, an overlapping `externalIPPoolCIDR`, too few free hosts).
- In a lab with another Tenant and another READY ExternalIPPool, both stay untouched, except the test Tenant's default NAT address, which the Tenant delete releases.

### Edge-case tests (later)

These cases test the proposed handling in [contract edge cases](design.md#edge-cases-that-need-handling). They are not release gates yet; each runs once its rule is implemented.

#### TC-RETRY-02: Treat a lost AAP job as failed and never launch a job twice

##### Preconditions

- **Tier / owner:** Unit / [DEV].

- Lost job: remove a tracked create job's record from AAP. OSAC fails it with `retryable: true` and retries with the contract backoff; with a delete pending, it starts the delete once it marks the lost job failed.
- After one failed launch call, OSAC resolves the entry by its AAP label.
- Restart with an entry `Retrying`: the wait before the retry starts again.
- Restart with an entry `Running` and an empty `jobID`:
  - never launched: OSAC launches it once, only 2 minutes after the restart;
  - never launched and the CR now has a deletionTimestamp: OSAC launches nothing and sets the entry to `Cancelled`;
  - still running: OSAC tracks it;
  - finished: OSAC processes its result.

  In each case OSAC ignores a job of an earlier attempt (for example an earlier `query_dhcp_lease`) and never launches a second job.
- The AAP mock creates the job 30 seconds after the launch call failed: OSAC launches nothing, then tracks that job, also if the CR gets a deletionTimestamp meanwhile and across an operator restart.
- Job not started: the AAP mock keeps a launched create job `pending`. 30 minutes after launch OSAC cancels it in AAP, sets the entry to `Retrying` with the message 'AAP did not start the job within 30 minutes', and retries after the contract backoff, not at once as for `Cancelled`.
- Two jobs with one label: OSAC tracks the lower job ID, cancels the other, and ignores its result.
- Reconcile from a cached CR older than the entry, or older than the deletionTimestamp: no launch.
- A create job cancelled by hand in AAP, with no delete: OSAC retries it.
- A create job that succeeded, deleted before OSAC processes its result: the entry becomes `Cancelled`, and the result is ignored.
- Two Subnets of one VirtualNetwork created at once, with an operator restart while the first Subnet's task runs: the second Subnet's task still starts only after the first ends.

#### TC-EDGE-01: Resolve registrations across operator restarts

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Restart the operator after creating a missing registration while it was down and verify the FAILED NetworkClass is resolved at start. Delete a READY NetworkClass's registration while the operator is down, restart it, and verify the NetworkClass stays READY and is not resolved again. Adding or removing the manager-type label on an existing ConfigMap resolves a FAILED NetworkClass again; any other ConfigMap update triggers nothing.

#### TC-EDGE-02: Accept segments under races and restarts

##### Preconditions

- **Tier / owner:** Unit / [DEV].

With the mock manager, verify:
- with an operator restart around the status update that sets the Fabric `create_subnet` entry to `Succeeded`, no Kubernetes task of the Subnet or its NetworkAttachments starts without `status.networkSegment`;
- two results with one VNI processed at once are not both accepted.

#### TC-EDGE-03: Claim the `cudn_evpn` hub network after the owner's delete

##### Preconditions

- **Tier / owner:** Unit / [DEV].

Run `cudn_evpn`: a `create_subnet` while the owner Subnet is being deleted fails with `retryable: true` and claims the network once the owner's delete finishes.

---

## Provenance

Authored: draft @ design 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Final: manual-edit [manual] @ design 0.11.5 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between draft and manual-edit.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","manual-edit","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
