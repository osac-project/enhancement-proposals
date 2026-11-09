---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-11-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md"
  - "CaaS Networking: /enhancements/OSAC-1436-caas-networking"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
  - "baremetal-instance-api: https://github.com/osac-project/baremetal-instance-api"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
  - [Goals](#goals)
  - [Non-Goals](#non-goals)
- [Proposal](#proposal)
  - [Workflow Description](#workflow-description)
    - [Create](#create)
    - [Delete](#delete)
    - [External access](#external-access)
  - [API Extensions](#api-extensions)
  - [UX Alignment](#ux-alignment)
  - [Implementation Details/Notes/Constraints](#implementation-detailsnotesconstraints)
    - [Network attachment and validation](#network-attachment-and-validation)
    - [Network planes](#network-planes)
    - [BareMetalInstanceType and interface selection](#baremetalinstancetype-and-interface-selection)
    - [Provisioning network and port moves](#provisioning-network-and-port-moves)
    - [NetworkAttachment and address discovery](#networkattachment-and-address-discovery)
    - [CaaS workers](#caas-workers)
    - [Network status and phase](#network-status-and-phase)
    - [ExternalIPAttachment target `baremetal_instance`](#externalipattachment-target-baremetal_instance)
    - [Automatic external access](#automatic-external-access)
    - [Provider networking disabled](#provider-networking-disabled)
    - [Component responsibilities](#component-responsibilities)
    - [Workload service design checklist](#workload-service-design-checklist)
  - [Security Considerations](#security-considerations)
  - [Failure Handling and Recovery](#failure-handling-and-recovery)
  - [RBAC / Tenancy](#rbac--tenancy)
  - [Observability and Monitoring](#observability-and-monitoring)
  - [Risks and Mitigations](#risks-and-mitigations)
  - [Drawbacks](#drawbacks)
- [Edge cases that need handling](#edge-cases-that-need-handling)
  - [Restarts and job tracking](#restarts-and-job-tracking)
  - [Delete races](#delete-races)
  - [Handoff](#handoff)
- [Alternatives (Not Implemented)](#alternatives-not-implemented)
- [Test Plan](#test-plan)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [E2E Tests](#e2e-tests)
  - [Edge-case tests (later)](#edge-case-tests-later)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)

## Summary

This design connects a BareMetalInstance (BMI) to its tenant Subnet. After provisioning on the provider-managed provisioning network, the Fabric Manager moves the selected port to the Subnet segment. BMF confirms the handoff through an off/on cycle using the existing power-state API, and OSAC reports the selected port's DHCP lease. [Unified Networking](/enhancements/OSAC-1433-unified-networking/design.md) owns shared resources, gates, guards, and support boundaries; the [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md) ("the contract") owns tasks, retries, and cleanup. Requirements: [PRD](prd.md).

## Motivation

A VM gets its interface from hub Kubernetes networking. A bare-metal NIC plugs into a physical switch port, so that port must join the Subnet's segment, after the host is imaged on another network (G2, G4).

### Goals

- **G1 OS-agnostic addressing.** Every address comes from DHCP; no per-OS network configuration; exactly one default route at any time.
- **G2 Provisioning connectivity.** During inspection, provisioning, and cleaning, the host reaches its image source and the Ironic conductor.
- **G3 Minimal final state.** After provisioning, the host is on exactly one tenant Subnet segment and off the provisioning network.
- **G4 Isolated until ready.** The tenant reaches the host only when it is provisioned and on its final network; provisioning traffic never crosses the tenant network.
- **G5 Stock Metal3 and any conforming Fabric Manager.** The bare-metal-fulfillment-operator (BMF) never calls a switch or DHCP API; the networking controller runs every provider task.

### Non-Goals

- VMaaS networking; CaaS networking beyond worker BMIs ([CaaS workers](#caas-workers)).
- More than one network attachment per BMI, NIC bonding, or failover.
- Creating the provisioning network and each host's initial attach (deployment prerequisites).
- Re-provisioning a Ready BMI in place: provisioning inputs are immutable; recreate the BMI to change the OS.
- Ironic standalone networking or a dedicated provisioning NIC.
- Enabling BMaaS on a deployment that already has networking resources is unsupported. Unified Networking's fulfillment service rejects startup when BMaaS or CaaS is newly enabled while a VirtualNetwork exists. This design does not migrate or backfill existing resources ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).
- Keeping the tenant OS off the provisioning network: the provisioning flow boots the new OS once at the end of provisioning, before the port move (a follow-up feature reduces provisioning to one boot).

## Proposal

The fulfillment service validates and stores the single network attachment. BMF provisions the host and creates one NetworkAttachment CR; the networking controller runs the Fabric tasks on it. BMF then uses its existing management API to power the host off and on, confirms both states, and reports the selected port's discovered address.

### Workflow Description

Actors: the Tenant User and the [components](#component-responsibilities). The inventory contract supplies a map from logical port names to MAC addresses. BMF resolves and validates the selected port's MAC through `GetHostLogicalPortMACs` and the common parser. The management interface controls host power; AAP templates install the OS. RunStrategy (`run_strategy`: `Always`, the default, or `Halted`) is the requested power state; each change of `restart_trigger` requests one reboot.

Starting state: provider networking enabled; READY tenant default networking ([Default Networking](/enhancements/OSAC-1433-default-networking/design.md)); a NetworkClass selecting a conformant Fabric Manager; every free host's fabric ports on the provider-managed provisioning network described in [Provisioning network and port moves](#provisioning-network-and-port-moves).

#### Create

1. The Tenant User creates the BMI:
   ```bash
   osac create baremetalinstance --catalog-item bcm-h100 --name my-server \
     --network-attachment subnet=my-subnet,interface=data-0,security-groups=web-sg,db-sg
   osac create baremetalinstance --catalog-item bcm-h100 --name my-server2 --external-ip-attachment
   ```
   Form 1 picks a Subnet, port `data-0`, and two SecurityGroups (syntax: `--network-attachment [subnet=<name or ID>][,interface=<port>][,security-groups=<name or ID>,...]`, each part optional, `security-groups=` last). Form 2 uses the tenant defaults and requests automatic external access (`auto_external_ip_attachment`). The CLI rejects a second `--network-attachment`.
2. The fulfillment service validates the attachment ([Network attachment and validation](#network-attachment-and-validation)); a failure stores nothing. In one transaction it stores the BMI and, if requested with provider networking enabled, one automatic ExternalIP ([Automatic external access](#automatic-external-access)), then creates their CRs; the BMI CR carries `spec.networkAttachments`.
3. BMF assigns a free host with an inventory name and a valid selected-port MAC ([interface selection](#baremetalinstancetype-and-interface-selection)), sets `spec.externalHostName` to that inventory name, records the attachment status by its `subnetRef`, and provisions the OS on the provisioning network using DHCP. When provisioning finishes, `ProvisionTemplateComplete=True`.
4. BMF adds the `osac.openshift.io/baremetalinstance-networking` finalizer to protect the BMI while its NetworkAttachment is being cleaned up. It writes the remaining status for that attachment and creates the NetworkAttachment in the hub networking namespace ([NetworkAttachment and address discovery](#networkattachment-and-address-discovery)). It sets `NetworkAttachmentsReady=False`, reason `Progressing`.
5. BMF observes the NetworkAttachment's readiness and failure conditions. When it becomes Ready, BMF sets `NetworkAttachmentsReady=True` and begins the handoff. For a final failure, BMF sets `NetworkAttachmentFailed` and phase `Failed`, preserving the actionable administrator diagnostic and stable reason. Fulfillment maps the condition to a fixed tenant-facing message. The networking controller binds SecurityGroup policy before joining the tenant segment, as required by the [integration contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment).
6. BMF performs one handoff power cycle through the existing management interface (`NetworkHandoffComplete=False`), ignoring RunStrategy and `restart_trigger` until handoff is complete. For each persisted step, BMF calls `SetPowerState` for its target, then observes `GetPowerState`. A step completes only when a successful observation reports the target state and `IsTransitioning=false`; an accepted request alone does not complete it. `ErrTransitioning` means that the requested transition is already in progress, so BMF keeps the persisted step pending, observes progress, and retries the same target as needed. It is not a request failure. Other request errors or a current terminal power failure fail the handoff. A `GetPowerState` error is an observation error, not a status; BMF keeps the step pending and retries until the existing deadline. BMF adds no handoff-specific management method or annotation.

   BMF owns a 15-minute timeout measured from the persisted `NetworkAttachmentsReady=True` transition time in BMI status. Every reconcile uses that same timestamp, so a restart does not reset the timeout. On each reconcile, BMF checks whether the off/on cycle is complete before checking the timeout. An observed completion succeeds even if the observation arrives after 15 minutes; if the cycle is still incomplete when a reconcile checks an elapsed timeout, the handoff fails ([Network status and phase](#network-status-and-phase)).
7. The networking controller runs Fabric `query_dhcp_lease` after `NetworkHandoffComplete=True` (an apply result or provisioning-network lease is not tenant address discovery). It records the accepted lease in NetworkAttachment status and retries per [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership). If no lease is found 10 minutes after handoff, BMF emits `LeaseNotFound` and queries continue.
8. BMF copies the accepted address into the matching `networkAttachmentStatuses` entry, sets `IPDiscoveryComplete=True` (event `IPDiscovered`) and phase `Ready`, and only then applies RunStrategy and any pending `restart_trigger`. Fulfillment reports `NETWORK_READY=True`, reason `IPDiscovered`, and the tenant address.
9. With an automatic ExternalIP, the cleanup controller requests the automatic ExternalIPAttachment (Fabric `attach_external_ip`; [Automatic external access](#automatic-external-access)).

Final failures stop the flow ([Network status and phase](#network-status-and-phase)).

```mermaid
sequenceDiagram
    actor T as Tenant User
    participant F as Fulfillment service
    participant C as BMI cleanup controller
    participant FB as Feedback controllers
    participant B as BMF
    participant I as Inventory and management backends
    participant N as Networking controller
    participant M as Fabric Manager (AAP)
    T->>F: Create BareMetalInstance
    F->>F: Resolve and validate attachment, check gates
    break gate or validation fails
        F-->>T: Error, nothing stored
    end
    F->>F: One transaction: BMI and, if requested, the automatic ExternalIP (PENDING)
    F-->>T: BareMetalInstance (PROVISIONING)
    F->>B: Create BMI CR
    par Automatic ExternalIP
        opt automatic ExternalIP stored
            F->>N: Create ExternalIP CR
            loop retryable failure, with backoff
                N->>M: create_external_ip
            end
            alt final failure
                FB->>F: Signal, ExternalIP FAILED, BMI works without external access
            else success
                M-->>N: Address
                FB->>F: Signal, ExternalIP ALLOCATED
            end
        end
    and Host and network
        C->>C: Add finalizer osac.openshift.io/baremetalinstance-cleanup
        FB->>FB: Add finalizer osac.openshift.io/baremetalinstance-feedback
        B->>I: Phase Allocating, assign a free host with an inventory name and the port's MAC (finalizer osac.openshift.io/inventory), record the MAC
        B->>B: Set spec.externalHostName, add finalizer osac.openshift.io/baremetalinstance, phase Progressing
        B->>I: Provision OS on provisioning network
        I-->>B: ProvisionTemplateComplete=True
        B->>B: Add networking finalizer; write status for the matching subnetRef entry
        B->>N: Create NetworkAttachment using BMI API ID
        B->>B: NetworkAttachmentsReady=False (Progressing)
        loop retryable failure, with backoff (administrator condition/event includes actionable diagnostic and stable reason; tenant message is fixed)
            N->>M: apply_network_attachment
        end
        alt final failure or rejected result
            N-->>B: NetworkAttachment Ready=False, Failed
            B->>B: NetworkAttachmentFailed, phase Failed
        else apply accepted
            M-->>N: Port bound to SecurityGroup policy and on Subnet segment, other fabric ports off provisioning network, fixed DHCP address
            N-->>B: NetworkAttachment Ready=True
            B->>B: NetworkAttachmentsReady=True, event NetworkAttached
            B->>I: SetPowerState(OFF), observe with GetPowerState
            B->>I: SetPowerState(ON), observe with GetPowerState
            alt failure reported, or no confirmation within 15 min
                B->>B: NetworkHandoffFailed, phase Failed
            else off/on handoff confirmed
                B->>B: NetworkHandoffComplete=True, IPDiscoveryComplete=False (LeasePending)
                loop retryable failure, 30 s, every 5 min from attempt 20 (administrator condition/event includes actionable diagnostic and stable reason; tenant message is fixed)
                    N->>M: query_dhcp_lease
                end
                alt final query failure
                    N-->>B: query_dhcp_lease entry Failed
                    B->>B: IPDiscoveryFailed, phase Failed
                else lease accepted
                    N->>N: Record status.dhcpLease
                    B->>B: Set ipAddress, IPDiscoveryComplete=True, event IPDiscovered, phase Ready
                    B->>I: Apply RunStrategy, and one reboot for a restart_trigger change made before Ready
                    FB->>F: Signal
                    F->>F: Read status (RUNNING, or STOPPED for Halted, NETWORK_READY True)
                end
            end
        end
    end
    opt automatic ExternalIP ALLOCATED and endpoint ready
        C->>F: Request auto-eipa-(ExternalIP API ID)
        F->>N: Create ExternalIPAttachment CR
        N->>N: Build destination from the BMI tenant IP, record status.destination
        loop retryable failure, with backoff
            N->>M: attach_external_ip
        end
        alt final failure
            FB->>F: Signal, ExternalIPAttachment FAILED, BMI works without external access
        else success
            FB->>F: Signal, ExternalIPAttachment READY
        end
    end
```

#### Delete

1. The [deletion guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards) reject the delete with `FAILED_PRECONDITION` while a manually created ExternalIPAttachment targets the BMI or a FabricDomain `spec.servers` entry matches the BMI host name in `spec.externalHostName`. The fulfillment service checks the FabricDomain dependency; BMF needs no FabricDomain access. Otherwise the state becomes DELETING. A Delete of a DELETING BMI returns OK ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#status)).
2. The fulfillment service deletes the automatic ExternalIPAttachment, then the automatic ExternalIP, then the BMI CR, in the [Unified order](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access). Jobs and retries follow [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership). The phase becomes `Deleting`.
3. From the deletionTimestamp on, BMF applies no RunStrategy or `restart_trigger`, requests no new handoff and creates no NetworkAttachment; the networking controller starts no apply or query job and cancels a running one ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). BMF waits for the cleanup controller to remove its finalizer. Before taking the no-attachment branch in step 4, BMF waits for any NetworkAttachment create request sent before deletion to settle, then performs a fresh lookup by the deterministic name. A timed-out or otherwise uncertain create is not settled; BMF retains its finalizer and host ownership while retrying lookup, because the request may still commit. A definitively settled create followed by a fresh `NotFound` allows the no-attachment branch. With no host assigned (`spec.externalHostName` empty), BMF skips deprovisioning and inventory release (step 7). If an ON request was already sent, BMF records the delete request, waits for that request to reach a terminal observed state, and only then starts offboarding; per-host power operations are serialized.
4. If the NetworkAttachment exists, BMF sets `NetworkOffboardComplete=False` (`Offboarding`) and calls `SetPowerState(OFF)` while the host is still on the tenant network. A step is complete only when a successful `GetPowerState` observation reports OFF and `IsTransitioning=false`. `ErrTransitioning` or a `GetPowerState` error leaves offboarding pending; BMF observes and retries while retaining host ownership and its finalizer. Other request errors or a current terminal power failure set `PowerOffFailed`; cleanup remains blocked and retries. BMF sends no concurrent OFF while an ON request is outstanding and starts network cleanup only after the completion condition is observed. This API completion check does not establish that the observation is a fresh physical-state reading; see [Edge cases](#restarts-and-job-tracking). When power-off is confirmed (at once if already off), BMF sets `NetworkOffboardComplete=True`. If no attachment exists because deletion arrived before creation and no apply task started, or provider networking is disabled, BMF goes to step 7 without power-off or condition.
5. BMF deletes the NetworkAttachment named `baremetalinstance-<BMI API ID>` and keeps its finalizer until the object is gone. If a create request has an uncertain outcome, BMF retains host ownership and retries lookup by that name; one `NotFound` result does not release inventory. The networking controller completes deletion under the [integration contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment), including returning ports to the provisioning network before it removes its finalizer. BMF reports the stable failure reason and actionable diagnostic in administrator-visible BMI conditions and events; Fulfillment maps the condition to a fixed tenant-facing message.
6. After a confirmed successful delete, with only BMF's finalizer left, BMF removes it.
7. After confirmed cleanup and with no NetworkAttachment left, BMF removes `osac.openshift.io/baremetalinstance-networking` from the BMI. If a host is assigned, the AAP deprovisioning job cleans it on the provisioning network, never booting the tenant OS. After deprovisioning succeeds, BMF removes `osac.openshift.io/baremetalinstance`, releases the host to inventory, and removes `osac.openshift.io/inventory`. If no host is assigned, BMF skips deprovisioning and inventory release.
8. The feedback controller removes its finalizer last, as [Unified](/enhancements/OSAC-1433-unified-networking/design.md#hub-crs) defines, and the fulfillment service removes the record.

Each step waits for the previous one; a failed step keeps its finalizer and the host stays owned while cleanup retries. Deprovisioning and release are the BMaaS host lifecycle ([OSAC-1118](/enhancements/OSAC-1118-baremetal-instance-api/README.md)). A host provisioning job still running at the deletionTimestamp is cancelled, and deprovisioning starts after AAP reports it ended; BMF retries a failed deprovisioning job or release with the [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership) backoff until it succeeds. Tenant default networking resources stay.

```mermaid
sequenceDiagram
    actor T as Tenant User
    participant F as Fulfillment service
    participant C as BMI cleanup controller
    participant FB as Feedback controllers
    participant B as BMF
    participant I as Inventory and management backends
    participant N as Networking controller
    participant M as Fabric Manager (AAP)
    T->>F: Delete BareMetalInstance
    break a manual ExternalIPAttachment targets the BMI
        F-->>T: FAILED_PRECONDITION
    end
    F->>F: State DELETING
    opt automatic ExternalIP exists
        opt automatic ExternalIPAttachment exists
            F->>N: Delete ExternalIPAttachment auto-eipa-(ExternalIP API ID)
            alt an attach job started
                opt attach job running
                    N->>M: Cancel it in AAP, wait until it ended
                end
                loop until success, with backoff
                    N->>M: detach_external_ip
                end
            else no attach job started
                N->>N: Remove its finalizer without a task
            end
            FB->>F: Signal, ExternalIPAttachment gone
        end
        F->>N: Delete automatic ExternalIP
        alt a create job started
            opt create job running
                N->>M: Cancel it in AAP, wait until it ended
            end
            loop until success, with backoff
                N->>M: delete_external_ip
            end
        else no create job started
            N->>N: Remove its finalizer without a task
        end
        FB->>F: Signal, ExternalIP gone
    end
    F->>B: Delete BMI CR (phase Deleting)
    B->>B: Stop RunStrategy, restart_trigger, new handoff, and NetworkAttachment create
    opt ON operation already sent
        B->>I: Resolve the outstanding operation and observe its terminal power state
    end
    opt apply or query job running
        N->>M: Cancel it in AAP, wait until it ended
    end
    C->>C: Remove finalizer osac.openshift.io/baremetalinstance-cleanup
    opt NetworkAttachment exists
        B->>B: NetworkOffboardComplete=False (Offboarding)
        loop every 30 s until power-off confirmed (failure: PowerOffFailed)
            B->>I: SetPowerState(OFF), observe with GetPowerState
        end
        B->>B: NetworkOffboardComplete=True
        B->>B: DeleteOwned(BMI-derived NetworkAttachment name, BMF finalizer)
        B->>N: Networking controller observes deletion
        B->>B: NetworkAttachmentsReady=False (NetworkDetaching)
        alt a network task started
            loop retry with backoff until success
                N->>M: delete_network_attachment
            end
            M-->>N: Fabric ports on provisioning network, policy removed, DHCP address released
            N->>N: Remove finalizer osac.openshift.io/networkattachment
        else no network task started
            N->>N: Remove finalizer osac.openshift.io/networkattachment without a task
        end
        B->>B: Remove BMF NetworkAttachment finalizer after the networking finalizer
    else no NetworkAttachment exists
        B->>B: Skip offboard power-off and network cleanup
    end
    B->>B: Remove finalizer osac.openshift.io/baremetalinstance-networking
    opt host assigned
        loop failure, with backoff, until success
            B->>I: Deprovision (backend cleaning on provisioning network)
        end
        B->>B: Remove finalizer osac.openshift.io/baremetalinstance
        loop failure, with backoff, until success
            B->>I: Release host to inventory
        end
        B->>B: Remove finalizer osac.openshift.io/inventory
    end
    FB->>FB: Remove osac.openshift.io/baremetalinstance-feedback last
    FB->>F: Signal
    F->>F: BMI CR gone, remove BMI record
```

#### External access

A Tenant User exposes a ready BMI through an ExternalIP:

```bash
osac create externalip --pool external-pool-1 --name my-ip
osac create externalipattachment --externalip my-ip --baremetal-instance my-server --name bm-att
```

Rules: [ExternalIPAttachment target](#externalipattachment-target-baremetal_instance). Once stored, the networking controller runs Fabric `attach_external_ip`. `--external-ip-attachment` automates this ([Automatic external access](#automatic-external-access)).

### API Extensions

- **fulfillment-service, BareMetalInstance:** `spec.network_attachments` (repeated `BareMetalNetworkAttachment`, at most one), `spec.auto_external_ip_attachment`, `status.network_attachment_statuses` (protos below; [validation](#network-attachment-and-validation)); condition type `BARE_METAL_INSTANCE_CONDITION_TYPE_NETWORK_READY = 7` in the public and private `BareMetalInstanceConditionType` ([Network status and phase](#network-status-and-phase)).
- **fulfillment-service, BareMetalInstanceType:** `hardware_spec.network_ports` ([OSAC-1201](/enhancements/OSAC-1201-baremetal-instance-types/design.md)).
- **fulfillment-service, ExternalIPAttachment:** target `baremetal_instance` (Unified; endpoint [here](#externalipattachment-target-baremetal_instance)).
- **BMF BareMetalInstance CRD:** `spec.networkAttachments`, `status.networkAttachmentStatuses`, the [conditions](#network-status-and-phase), and the finalizer `osac.openshift.io/baremetalinstance-networking` (on the BMI and its NetworkAttachment). Networking jobs are recorded only in the NetworkAttachment `status.jobs`.
- **Inventory:** the per-host port-name-to-MAC map ([BareMetalInstanceType and interface selection](#baremetalinstancetype-and-interface-selection)).
- **osac-operator:** the networking controller reconciles physical NetworkAttachments, ExternalIPs, and ExternalIPAttachments and watches BareMetalInstances; BareMetalInstance cleanup and feedback controllers ([Component responsibilities](#component-responsibilities)).
- **Controllers down.** No BMF: no host provisioning and no NetworkAttachment. No networking controller: BMIs stay `Progressing`; deletes wait for the NetworkAttachment. No cleanup controller: no automatic ExternalIPAttachment; deletes wait for its finalizer. No feedback controller: API status freezes and deleted BMI records stay.

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1;                          // optional on input; immutable
  repeated SecurityGroupLocalReference security_groups = 2; // optional on input; immutable
  optional string interface = 3;                            // port name; default: first fabric port
  optional bool primary = 4;                                // omitted or true; false is rejected
}
message BareMetalInstanceSpec {
  // ... other fields ...
  repeated BareMetalNetworkAttachment network_attachments = 8; // immutable; at most one
  optional bool auto_external_ip_attachment = 9;               // immutable
}
message BareMetalNetworkAttachmentStatus {
  string interface = 1;
  string subnet_ref = 2;  // Subnet API ID
  string ip_address = 3;  // tenant address from the accepted lease
  bool primary = 4;       // always true
}
```

The single attachment is the host's default route, so `primary` carries no choice. The BMF CRD mirrors these fields as `spec.networkAttachments[]` (`subnetRef`, `securityGroupRefs`, `interface`, `primary`; refs hold API IDs, never names) and `status.networkAttachmentStatuses[]`. CEL rules make the list and every field immutable and cap the list at one entry. To change the network, delete and recreate the BMI.

### UX Alignment

The UI uses these fields. The bare-metal create wizard uses the [bare-metal adapter of the shared network attachment pickers](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers): READY Subnets and SecurityGroups of one VirtualNetwork, and the type's `fabric` ports as interfaces (first is default). The UI shows the network conditions and the tenant IP.

### Implementation Details/Notes/Constraints

#### Network attachment and validation

Fields: [API Extensions](#api-extensions).

The fulfillment service applies the [Unified defaulting table](/enhancements/OSAC-1433-unified-networking/design.md#network-attachment-field-presence-and-defaulting), [creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates), and [error codes](/enhancements/OSAC-1433-unified-networking/design.md#error-codes), plus these checks:

| Check | Error |
|---|---|
| `primary: false` | `INVALID_ARGUMENT` |
| More than one `network_attachment` is provided | `INVALID_ARGUMENT` |
| `interface` fails [BareMetalInstanceType and interface selection](#baremetalinstancetype-and-interface-selection) (against `instance_type` or the type from the catalog item or template), or no type resolves | `INVALID_ARGUMENT` |
| Update of `network_attachments` or `auto_external_ip_attachment` | `INVALID_ARGUMENT` |

A CaaS worker BMI uses its Cluster's tenant and the Cluster-authorized Subnet, SecurityGroups, and `fabric_interface` ([CaaS workers](#caas-workers)). Fulfillment rejects a missing Cluster, a tenant mismatch, or an attachment outside the Cluster's authorized network. The Cluster identity and network authorization are checked separately from the tenant value.

#### Network planes

The BMC management network carries power and virtual-media access and stays outside the fabric attachment. The provisioning network carries host DHCP, image download, and provisioning-agent callbacks over the fabric ports. The tenant network is the Subnet segment. The Fabric Manager moves fabric ports between the provisioning and tenant networks and never touches the BMC network. Which host ports are fabric ports: [contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment).

#### BareMetalInstanceType and interface selection

The BareMetalInstanceType ([OSAC-1201](/enhancements/OSAC-1201-baremetal-instance-types/design.md)) lists the host's ports in order:

```protobuf
message BareMetalNetworkPortSpec {
  string name = 1;  // unique within the type, e.g. "data-0"
  string role = 2;  // port role, e.g. fabric, management, storage, lifecycle
  string type = 3;  // informational, e.g. "Ethernet"
  string speed = 4; // informational, e.g. "100Gbps"
}
```

- OSAC-1201 owns the role field. Example roles: `fabric` (tenant traffic), `management` (in-band control), `storage`, `lifecycle` (BMC/PXE port).
- A type with no `fabric` port, or a selected port that is not a `fabric` port in `network_ports`: `INVALID_ARGUMENT`. Default: the first `fabric` port.
- For a CaaS worker, the Cluster's authorized `fabric_interface` must identify a tenant-facing port on the assigned host ([CaaS workers](#caas-workers)).

Every inventory backend implements port-aware host selection through the common inventory `Client` interface. A backend that cannot provide it returns the shared not-implemented error. With provider networking enabled, BMF does not assign a host when it receives that error: it sets the BMI phase to `Failed` and `Allocated=False`, reason `InventoryNotSupported`, with an administrator-visible diagnostic. It does not retry an unsupported capability as though no host were available. For a supported backend, a host with a missing or invalid selected-port MAC is skipped; if no usable host remains, BMF reports the existing no-matching-host result. BMF validates the selected logical port through the common MAC parser, accepts `:` or `-` separators in any case, and stores the canonical lowercase, colon-separated MAC. NetBox uses its configured custom-field MAC source only ([OSAC-1610](https://redhat.atlassian.net/browse/OSAC-1610)); it does not merge MACs from other fields.

Not supported in this release: hosts without an inventory name, or without a valid MAC for the selected fabric port in the inventory map. With provider networking enabled, BMF records a structured skip reason (`MissingInventoryName` or `SelectedPortMACUnavailable`) without logging host names, port names, or inventory values.

#### Provisioning network and port moves

A provider-managed default provisioning network (DHCP, gateway, and SNAT) is defined in Fabric Manager configuration or inventory, separately from OSAC tenant Subnets. Deployment bootstrap attaches each free host's fabric ports to it; after a tenant attachment is deleted, the ports return to this default. It is not an OSAC Subnet or NetworkAttachment task input, and BMF does not configure it. Without it, an unassigned host has no default gateway and the provisioning agent cannot download its image.

The port moves ([Create](#create), steps 5–6; [Delete](#delete), step 5) follow OS provisioning. The tenant OS and its `user_data` first boot on the provisioning network before the port moves; if provider networking is disabled, the host remains there. The provider isolates hosts and restricts this network as described in [Security Considerations](#security-considerations). The design does not depend on which network carries the provisioning-agent callback.

#### NetworkAttachment and address discovery

BMF creates the NetworkAttachment in the hub networking namespace ([Unified — NetworkAttachment](/enhancements/OSAC-1433-unified-networking/design.md#networkattachment)). The shared contract defines this as the OSAC release namespace where the operator runs; it is not a separate configurable namespace. Provider networking is enabled by `global.networking.provisioningEnabled`; BMF has no `OSAC_NETWORKING_NAMESPACE` setting or namespace startup check.

- name `baremetalinstance-<BMI API ID>`, for the current one-attachment limit;
- annotation `osac.openshift.io/tenant` from the BMI, including the Cluster tenant for CaaS workers;
- finalizers: BMF's `osac.openshift.io/baremetalinstance-networking` and the networking controller's `osac.openshift.io/networkattachment` ([Delete](#delete), steps 5 and 6);
- `target` = `{kind: BareMetalInstance, id: <BMI API ID>, host_name: <BMI spec.externalHostName>}`, identifying the owning BMI and its assigned inventory host;
- `subnet` and `securityGroups` = the API IDs in the attachment entry;
- `interface` = `{type: physical, name: <attachment.interface>, macAddress: <recorded MAC>}`.

BMF records interface, Subnet reference, primary status, selected MAC, and discovered IP in the status entry matched by immutable `subnetRef`. The current release supports one attachment per BMI and keeps the name `baremetalinstance-<BMI API ID>`. Supporting multiple attachments is out of scope for this design. It will require a shared contract change: managers currently use the workload API ID to identify attachment state, so each attachment will need a stable identity used consistently for creation, lookup, restart recovery, status, and deletion across Unified, the manager contract, BMaaS, and VMaaS. Because two ports can use one Subnet, `subnetRef` alone cannot identify each attachment. This design does not introduce that identity. BMF watches NetworkAttachments with a namespace-scoped cache and maps `spec.target.id` to the BMI through the `osac.openshift.io/baremetalinstance-uuid` label and a target-ID index. It does not rely on owner references. Timed requeues remain for handoff deadlines and restart recovery; create and delete use direct reads so the watch is not the only source of truth.

The networking controller runs the Fabric tasks on the manager in `status.networkManagers.fabric` ([contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#410-task-reference)). BMF does not launch port-move or lease jobs. It mirrors the NetworkAttachment reason and actionable task diagnostic into administrator-visible BMI conditions and events. Fulfillment exposes only the fixed tenant message defined in [Unified status policy](/enhancements/OSAC-1433-unified-networking/design.md#status).

Address discovery ([Create](#create), step 7):

- Lease acceptance and final failure: [contract — `query_dhcp_lease`](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-query_dhcp_lease). Queries never change NetworkAttachment `Ready`, so `NetworkAttachmentsReady` stays `True`.
- The Fabric DHCP keeps the MAC's address while the NetworkAttachment exists, so discovery runs once.
- Physical address range: [contract §4.8](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#48-addressing); sizing: [Risks](#risks-and-mitigations).

#### CaaS workers

CaaS worker BMIs use the Cluster's tenant, recorded from Cluster metadata, and carry the server-owned `osac.openshift.io/cluster-api-id: <Cluster API ID>` annotation. Only the private `BareMetalWorkerReconciler` path may create a BMI with this marker; a public BMI Create request that supplies it is rejected with `INVALID_ARGUMENT`. The node set's authorized `fabric_interface` selects the port. Fulfillment resolves the Cluster by that identity, rejects a missing Cluster or failed ownership lookup, verifies the BMI belongs to the Cluster's tenant, and checks the Subnet and SecurityGroups against the Cluster-authorized resources ([CaaS worker network authorization](/enhancements/OSAC-1436-caas-networking/design.md#caas-worker-network-authorization)). The attachment task carries the Cluster tenant. A public ExternalIPAttachment cannot target a worker BMI; Cluster external access uses the `cluster` target. Tenant visibility and update/delete behavior are defined in the [CaaS worker design](/enhancements/OSAC-1436-caas-networking/design.md#worker-bmis).

#### Network status and phase

"Phase" means only the BMI `status.phase`: `Allocating`, `Progressing`, `Ready`, `Failed`, or `Deleting`. BMF sets these network conditions on the BMI:

| Condition | True when | `False` reasons |
|---|---|---|
| `NetworkAttachmentsReady` | The NetworkAttachment is Ready. | `Progressing`: apply running or retrying. `NetworkAttachmentFailed`: final apply failure; phase `Failed`. `NetworkDetaching`: NetworkAttachment deleting. |
| `NetworkHandoffComplete` | The host is observed ON after the requested off/on cycle; never reset. | `PoweringOff` / `PoweringOn`: current requested step. `NetworkHandoffFailed`: reported failed or not confirmed in time; phase `Failed`. |
| `IPDiscoveryComplete` | The accepted lease is mirrored into the matching attachment-status entry and BMI `ipAddress`. | `LeasePending`: from `NetworkHandoffComplete=True` on; phase stays `Progressing`; stable failure reason, actionable administrator diagnostic, and opaque AAP job ID, once one exists. `IPDiscoveryFailed`: that entry is `Failed`; phase `Failed`. |
| `NetworkOffboardComplete` | During delete, power-off is confirmed while still on the tenant network. | `Offboarding`: powering off. `PowerOffFailed`: reported failed; retried every 30 seconds. |

The power API returns request errors separately from `PowerStatus`, which contains only `State` and `IsTransitioning`. `ErrTransitioning` leaves the persisted step pending; BMF observes progress and retries the same target without resetting the deadline. Before each `SetPowerState`, BMF records the backend error baseline. A terminal failure is recognized only when a new or changed backend error follows the request and no transition is in progress: for Ironic, a changed `last_error`; for Metal3, `operationalStatus=error` with `errorType=power management error`. Prior errors do not fail a new request. A successful `GetPowerState` completes a step only when its `State` matches the target and `IsTransitioning=false`; errors from `GetPowerState` are handled separately as observation errors. BMF maps terminal failures to `NetworkHandoffFailed` during create or `PowerOffFailed` during delete. Administrator-visible BMI conditions and events retain actionable manager and BMC error details after redacting credentials, tokens, secret values, session identifiers, and personal information.

The phase is `Ready` only when the first three conditions are `True`. With provider networking enabled, a missing BMF network condition maps to `NETWORK_READY=False`, reason `Progressing`, with the fixed message `Network setup is in progress.` The fulfillment service maps in-progress reasons (`PoweringOff`, `PoweringOn`, `LeasePending`, `NetworkDetaching`, and `Offboarding`) to PROVISIONING, and terminal `*Failed` reasons to FAILED; these in-progress networking reasons never make `PROVISIONED` report a failure. DELETING takes precedence during cleanup. BMF never reports a tenant IP before the network conditions are ready, nor ever the provisioning-network address.

The fulfillment service maps these conditions to the API condition `NETWORK_READY` when it reads the BMI status. It checks `NetworkOffboardComplete` (only once set), `NetworkAttachmentsReady`, `NetworkHandoffComplete`, and `IPDiscoveryComplete` in an explicit ordered list and selects the first condition that is not `True`; adding a condition cannot change precedence by changing append order. It preserves the condition status and reason but maps each known reason to a fixed tenant-facing message, as `PROVISIONED` does. The message map is:

| Condition reason | Tenant-facing message |
|---|---|
| `NetworkAttachmentFailed` | `Network attachment did not complete.` |
| `NetworkHandoffFailed` | `Network handoff did not complete.` |
| `IPDiscoveryFailed` | `IP address discovery did not complete.` |
| `Progressing` | `Network attachment is in progress.` |
| `Offboarding` | `Network cleanup is in progress.` |
| `PoweringOff`, `PoweringOn` | `Network handoff is in progress.` |
| `LeasePending` | `IP address discovery is in progress.` |
| `NetworkDetaching` | `Network cleanup is in progress.` |
| `Progressing` when no BMF network condition exists yet | `Network setup is in progress.` |
| All network phases complete | `Network setup is complete.` |
| `ProvisioningDisabled` | `Provider networking is disabled; network setup was skipped.` |
| `PowerOffFailed` | `Network cleanup did not complete.` |
| Any other network reason | `Network setup did not complete.` |

OSAC persists stable failure reasons, actionable provider, manager, BMC, and AAP error details, and opaque AAP job IDs in administrator-visible BMI conditions and events. It redacts credentials, tokens, secret values, session identifiers, and personal information while retaining useful operational context for administrators. Fulfillment maps each known condition reason to a fixed tenant-facing message and never exposes diagnostic text or job IDs to tenants. Ansible error handling uses `no_log` for credentials and raw secret-bearing responses; controller logs do not include credentials or secret values. Unknown failures use the generic tenant-safe reason and retain an actionable administrator diagnostic when one is available. If all network conditions are `True`, Fulfillment uses reason `ProvisioningDisabled` when provider phases were skipped ([Provider networking disabled](#provider-networking-disabled)), else `IPDiscovered`. A missing BMF condition while provider networking is enabled uses the fixed `Progressing` mapping above.

Once the delete is accepted, the API state is DELETING, whatever the phase ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#status)). Before that, and before phase `Ready`, it is PROVISIONING (FAILED for phase `Failed`). The handoff power calls do not update BMF's power-state condition `PowerSynced`, so the tenant never sees STOPPING, STARTING, or RUNNING during the handoff.

#### ExternalIPAttachment target `baremetal_instance`

| Item | BMaaS definition |
|---|---|
| Endpoints | One per BMI. `target_endpoint` other than `UNSPECIFIED`: `INVALID_ARGUMENT`. |
| Endpoint ready | Fulfillment service: API state RUNNING, `ip_address` set, not being deleted; else `FAILED_PRECONDITION`. The cleanup controller checks the hub CR: phase `Ready`, an address in the matching attachment-status entry, no deletionTimestamp, and `status.runStrategy=Always`. A stopped (`Halted`) BMI is not ready. |
| `destination.address` | The BMI tenant IP (`ipAddress`). While empty, the ExternalIPAttachment stays PENDING and no job starts. |
| `destination.routing_domain` | `{type: tenant_virtual_network, virtual_network_id: <VirtualNetwork API ID of the BMI's Subnet>, subnet_id: <BMI's Subnet API ID>}`. |
| Automatic access | One endpoint, the BMI ([Automatic external access](#automatic-external-access)). |

#### Automatic external access

`auto_external_ip_attachment: true` requests one endpoint, the BMI. Shared rules, including labels and when the recheck stops: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access).

The cleanup controller requests the ExternalIPAttachment `auto-eipa-<ExternalIP API ID>` through the fulfillment private API once the automatic ExternalIP is ALLOCATED and the [endpoint is ready](#externalipattachment-target-baremetal_instance), and retries a `FAILED_PRECONDITION` reply (status not copied yet) at the 30-second recheck. BMI readiness never waits for it; if automatic access fails, the BMI works without it.

#### Provider networking disabled

Shared rules: [Unified — Provider networking control](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control). With provider networking disabled, OSAC runs no networking job and hosts still provision. BMF reads the deployment setting and uses this fallback:

- Inventory, power, OS provisioning, and deprovisioning run as usual, with the host on the provisioning network throughout. RunStrategy `Always` still powers it on.
- No MAC recording, NetworkAttachment, handoff, or lease query. After `ProvisionTemplateComplete=True`, BMF sets `NetworkAttachmentsReady`, `NetworkHandoffComplete`, and `IPDiscoveryComplete` to `True`, reason `ProvisioningDisabled`, with a message naming the skipped operation; phase `Ready` then attests only OS provisioning, and BMF applies RunStrategy and any `restart_trigger` change made before Ready (one reboot). `status.networkAttachmentStatuses` stays empty, so no provisioning address is shown as a tenant IP.
- Delete finds no NetworkAttachment and skips the power-off ([Delete](#delete), step 4).
- No NetworkAttachment or Fabric task exists to clean up.

#### Component responsibilities

BMaaS uses the NetworkClass's Fabric Manager and runs no Kubernetes Manager task for its NetworkAttachment, also when the deployment selects one, because the Kubernetes Manager has no enforcement point on a physical port ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary), [contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#410-task-reference)). A provider may implement the Fabric tasks with its own switch, router, and DHCP APIs; BMF uses the same gates either way.

| Component | Responsibility |
|---|---|
| fulfillment-service | Validation, gates, and guards; the BMI CR and automatic resources. |
| BMF | Inventory, OS provisioning, power, MAC resolution, NetworkAttachment create and delete, handoff, offboard power-off, status mirroring, and the disabled fallback. Never calls a manager. |
| Networking controller | Runs every BMaaS manager task; builds `destination`; reports status. |
| Fabric Manager | Binds ports to SecurityGroup policy objects, moves ports, serves DHCP, and returns the selected MAC's lease; restores the ports on delete. Never reboots the host. |
| osac-operator BareMetalInstance cleanup controller | Adds its finalizer on first reconcile of every BMI with the API ID label; requests the automatic ExternalIPAttachment; on delete, removes its finalizer once no automatic CR for the BMI remains, deleting none ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)). |
| osac-operator BareMetalInstance feedback controller | Adds its finalizer on first reconcile; signals the fulfillment service on status changes and after it removes its finalizer; removes its finalizer last ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#hub-crs)). |

BMF and osac-operator act on the same BMI CR and coordinate through conditions, NetworkAttachment status, and finalizers.

#### Workload service design checklist

| [Checklist](/enhancements/OSAC-1433-unified-networking/design.md#workload-service-design-checklist) item | BMaaS |
|---|---|
| Network attachment field and target identity | [Network attachment and validation](#network-attachment-and-validation); [NetworkAttachment](#networkattachment-and-address-discovery) `target` |
| Interface-selection field and default | [BareMetalInstanceType](#baremetalinstancetype-and-interface-selection) |
| NetworkAttachment owner and timing | BMF ([Workflow](#workflow-description)) |
| Waiting and address reporting | [NetworkAttachment and address discovery](#networkattachment-and-address-discovery), [Network status and phase](#network-status-and-phase) |
| ExternalIPAttachment target: readiness, `destination.address`, `destination.routing_domain` | [ExternalIPAttachment target](#externalipattachment-target-baremetal_instance) |
| Automatic external access field and endpoints | [Automatic external access](#automatic-external-access) |
| Provider networking disabled fallback | [Provider networking disabled](#provider-networking-disabled) |
| Subnet LB VIP range | Not used |

### Security Considerations

- Shared tenancy model: [Unified — RBAC / Tenancy](/enhancements/OSAC-1433-unified-networking/design.md#rbac--tenancy). A CaaS worker BMI belongs to the Cluster tenant. Fulfillment checks Cluster ownership and authorized networking references; tenant metadata alone does not identify or authorize a worker.
- The port is bound to its SecurityGroups' policy objects before it joins the Subnet segment.
- The tenant OS runs user-controlled `user_data` during first boot on the provisioning network. It remains there while a port move waits and when provider networking is disabled. The provider must isolate hosts from one another, block rogue DHCP, restrict access to management services, and allow only required provisioning traffic. These remain provider prerequisites; OSAC does not configure, verify, or enforce physical isolation at startup. Operator installation documentation must warn that tenant-controlled code runs on this network and describe the provider-side isolation prerequisites. The OSAC QE lab owns a qualification report as Tech Preview graduation evidence for the reference lab only; it is not a general pre-enablement gate or attestation for external deployments.

### Failure Handling and Recovery

Retries follow [contract §4.6](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#46-task-result-and-errors) and [§4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership). Restart, race, and partial-failure cases: [Edge cases](#edge-cases-that-need-handling).

| Failure | What the user sees | Recovery |
|---|---|---|
| Apply, handoff, or lease failure | Retryable: phase `Progressing`; final: phase `Failed` ([Network status and phase](#network-status-and-phase)). | Automatic retry; after a final failure BMF does not retry and the tenant deletes the BMI. |
| Automatic ExternalIP or ExternalIPAttachment fails | Shown on that resource only, with fixed tenant-facing text. | Per Unified. |
| A cleanup step fails | Phase `Deleting`; administrator-visible diagnostic, stable failure reason, and opaque job ID in `NetworkOffboardComplete` (`PowerOffFailed`) or `NetworkAttachmentsReady` (`NetworkDetaching`). | Retry the owned cleanup and retain the relevant finalizers and host ownership until it succeeds; deprovision and release the host only after network cleanup completes. Admission rejects removing finalizers by hand ([Unified — Non-Goals](/enhancements/OSAC-1433-unified-networking/design.md#non-goals)). |
| BMI CR or NetworkAttachment deleted or lost outside OSAC | The OSAC admission policy rejects a delete; a loss is unsupported ([Unified — Non-Goals](/enhancements/OSAC-1433-unified-networking/design.md#non-goals)). | None by OSAC. |

### RBAC / Tenancy

- BMF: create, get, list, watch, patch, and delete NetworkAttachments in the OSAC release namespace. Configure the NetworkAttachment cache with a namespace-scoped `ByObject` entry and a `spec.target.id` index; do not start a cluster-wide NetworkAttachment cache. Direct API-server reads remain for create/delete decisions and power-state observations, and timed requeues remain for deadlines and recovery. Create and patch events through `events.k8s.io` in the OSAC release namespace.
- Networking controller: get, list, and watch BareMetalInstances, including status; read VirtualNetworks, Subnets, SecurityGroups, and the NetworkClass; update NetworkAttachment status and finalizers.
- BareMetalInstance cleanup controller: get, list, and watch BareMetalInstances, and update their finalizers; get, list, and watch `externalipattachments` and `externalips` in the hub networking namespace; call the fulfillment private API.
- Fulfillment checks the Cluster identity, Cluster tenant ownership, and authorized network references for CaaS worker BMIs; a missing Cluster or failed lookup is rejected. The NetworkAttachment tenant annotation carries the Cluster's tenant. Fulfillment enforces the FabricDomain deletion dependency, so BMF needs no FabricDomain get/list/watch permission. The hub networking namespace is the OSAC release namespace; there is no separate namespace setting or startup check.
- Manager-job access follows [contract §4.12](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#412-security-rbac-and-tenancy).

### Observability and Monitoring

Kubernetes events on the BMI; each name has one meaning, and an event for a condition reason uses that reason's name. `LeaseNotFound` is an event only.

| Event | Type | When |
|---|---|---|
| `NetworkAttached` | Normal | The NetworkAttachment became Ready. |
| `NetworkAttachmentFailed` | Warning | Final apply failure. |
| `NetworkHandoffFailed` | Warning | The handoff power cycle failed or was not confirmed in time. |
| `LeaseNotFound` | Warning | No lease 10 minutes after the handoff; queries continue. |
| `IPDiscoveryFailed` | Warning | Final `query_dhcp_lease` failure. |
| `IPDiscovered` | Normal | The tenant IP was mirrored into status. |

No networking metrics or alerts; the BMaaS provisioning duration and failure metrics apply. Task diagnostics follow [contract §7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#7-observability-and-monitoring), with the BMaaS safe-message rules above. Automatic external access logs: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#observability-and-monitoring).

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| The Fabric Manager or provisioning network is missing or late. | Run the Fabric Manager conformance suite and follow-up physical network-behavior tests as part of qualification. A conformant `baremetal` profile is a GA criterion, not a general pre-enablement gate ([contract §4.11](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#411-conformance-tests)). |
| The provider provisioning network exposes tenant-controlled first-boot code to other hosts, rogue DHCP, or management services. | The provider owns and validates physical isolation. OSAC does not configure, verify, or enforce it at startup. The OSAC QE lab qualification report is evidence for Tech Preview graduation in the reference lab only, not a general pre-enablement gate or proof for an external deployment. |
| Bare-metal ports have only stateless switch ACLs, which the [contract SecurityGroup task](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-create_security_group--delete_security_group) does not accept. | Put a stateful enforcement point (for example a distributed firewall or a DPU) in each physical interface's path. |
| The physical range is the plan's `fabric` share of the Subnet ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout)) and also serves the provider's fabric devices, so it can be small (64 addresses on a /24 with a 0.25 share), also on a Subnet where `cudn_evpn` serves no VMs and the overlay range stays unused ([VMaaS risks](/enhancements/OSAC-1435-vmaas-networking/design.md#risks-and-mitigations)). When it is full, the apply fails finally ([contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment)) with `NetworkAttachmentFailed`. | Size such Subnets for bare metal (a /22 with a 0.25 share gives 256 physical addresses). |
| Inventory and BareMetalInstanceType port names differ, so the wrong NIC is moved or queried. | Same names in inventory tooling and type registration; a host without a valid MAC for the port is never assigned. |

### Drawbacks

- The BMF/osac-operator split needs ordered finalizers and status mirroring.
- The handoff adds one power cycle to every provisioning.
- Discovery depends on a Fabric DHCP lease API.

## Edge cases that need handling

These cases are not normative yet: the body describes the normal flow and does not depend on them. Each entry gives the case, why it matters, and the handling we propose. Job-tracking cases shared by every service (AAP label lookup, failed launch calls, not-started jobs, leader election): [contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#edge-cases-that-need-handling). Fulfillment service concurrency and status cases: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#edge-cases-that-need-handling).

### Restarts and job tracking

| Case | Why it matters | Proposed handling |
|---|---|---|
| BMF restarts during the handoff. | The power cycle is lost or repeated out of order. | Persist `PoweringOff` before requesting OFF and `PoweringOn` after OFF is observed. On restart, repeat the existing `SetPowerState` call for the persisted step and use `GetPowerState` to observe progress; `ErrTransitioning` leaves the step pending and retrying the same target. Mark complete only after ON is observed. No handoff annotation or in-memory-only step is used. |
| A management backend returns a stale power observation during handoff or offboarding. | A stale observation can falsely confirm a step or release a host still on a tenant network. | Read power state directly from the API server, not an informer cache; deletion must not rely on a cached OFF value. This reduces cache staleness but does not prove physical freshness. Metal3 observation freshness remains unverified and requires a tracked implementation issue. |
| BMF restarts after the NetworkAttachment create, before status is written. | A duplicate attachment or a BMI stuck without a condition. | Reconcile by the BMI-derived NetworkAttachment name; create only if missing. |
| BMF stops between writing the matching attachment-status entry and creating its NetworkAttachment. | A live BMI waits forever, or a delete expects an attachment. | A live BMI creates or finds the attachment by the BMI-derived name after restart; a delete looks up that name and skips offboard power-off only when no attachment or apply task exists and no create request remains unsettled. |
| BMF restarts during host assignment. | A host is assigned twice or leaked. | Follow the [OSAC-1118](/enhancements/OSAC-1118-baremetal-instance-api/README.md) host lifecycle. |
| BMF loses the job ID of a host provisioning job before a delete. | The running job is not cancelled before deprovisioning. | Find it by its AAP label, as the contract does for manager jobs, cancel it, and deprovision after AAP reports it ended. |
| `LeaseNotFound` after a BMF restart. | The warning may repeat once. | Accepted. |

### Delete races

| Case | Why it matters | Proposed handling |
|---|---|---|
| The create flow continues after the delete is accepted but before the BMI CR is deleted. | Status could look like progress. | The API state stays DELETING whatever BMF does; BMF stops at the deletionTimestamp. |
| Delete arrives while a NetworkAttachment create request sent before deletion is still in flight. | A delayed create could appear after BMF treats `NotFound` as no attachment, leaving an orphaned finalizer and releasing a host still referenced by the attachment. | BMF waits for the create request to settle, then performs a fresh lookup by the deterministic name before taking the no-attachment branch. A timeout or uncertain result keeps the BMI finalizer and host ownership; if the attachment appears, BMF completes its cleanup before release. |
| Delete during a pending handoff. | The host could power on onto the tenant network during cleanup. | At deletion, stop the handoff sequence, persist the offboarding step, call `SetPowerState(OFF)`, and do not issue the ON step; wait for a successful `GetPowerState` status showing OFF with `IsTransitioning=false` before network cleanup. `ErrTransitioning` and observation errors keep the step pending. |
| Delete during an apply or query job. | A late result could fail or advance the BMI. | Cancel the job; it ends `Cancelled`, which is never a failure reason, and the phase stays `Deleting`. |

### Handoff

| Case | Why it matters | Proposed handling |
|---|---|---|
| The handoff confirmation arrives near or after the 15-minute deadline. | A confirmed power cycle is treated as failed, or the clock restarts. | On every reconcile, check for a completed off/on cycle before the timeout. A completion observed after 15 minutes succeeds; if the cycle is still incomplete when a reconcile checks an elapsed timeout, fail. Persisting the next handoff step does not move the deadline. |

## Alternatives (Not Implemented)

| Alternative | Why rejected |
|---|---|
| OSAC allocates static per-host addresses. | Needs per-OS templates (cloud-init, NMState, kickstart), per-host allocation and cross-operator locking. Fabric DHCP works for every OS. |
| Attach the tenant network before OS provisioning. | The tenant could reach a half-built host, and provisioning traffic would cross the tenant network. |
| Default gateway on the BMC NIC instead of a provisioning network. | Two default routes once the tenant Subnet is attached. |

## Test Plan

Shared task and result checks: [contract test plan](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md) and [Unified test plan](/enhancements/OSAC-1433-unified-networking/design.md#test-plan). The closed baseline under [OSAC-1448](https://redhat.atlassian.net/browse/OSAC-1448) / [OSAC-1510](https://redhat.atlassian.net/browse/OSAC-1510) remains the attachment and Netris E2E foundation. CaaS worker coverage belongs to [OSAC-5688](https://redhat.atlassian.net/browse/OSAC-5688); cover a worker BMI only when testing shared Subnet behavior.

**Ownership.** Unit, Envtest, and Kind component-integration tests belong to DEV; deployed BMaaS lifecycle tests belong to QE ([OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820)). The Fabric Manager owns Fabric tasks. Tests must exercise apply, delete, and `query_dhcp_lease` through the networking controller and NetworkAttachment `status.jobs`, never through a BMF-to-manager client.

### Unit Tests

DEV-owned unit tests: run `make test` in BMF and osac-operator, and the existing Ginkgo suites in fulfillment-service.

- Fulfillment service:
  - Reject more than one attachment, an interface absent from the type or a system-only interface, and updates to immutable fields; accept an authorized worker `fabric_interface` and apply the documented defaults.
  - Reject a worker BMI when its Cluster cannot be resolved, ownership lookup fails, the tenant does not match, or the requested network is outside the Cluster's authorization.
  - Check ExternalIPAttachment target and endpoint readiness for running and stopped BMIs; reject deletion of a Subnet referenced by a BMI.
- BMF:
  - Resolve and normalize the selected port MAC across supported inventory formats, including malformed entries; skip hosts without an inventory name or valid selected-port MAC. If port-aware host selection returns the shared not-implemented error, verify BMF reports phase `Failed`, `Allocated=False`, reason `InventoryNotSupported`, without assigning a host.
  - Assign a host with inventory name `host-a`; verify BMF sets `spec.externalHostName` to `host-a` and sends `target.host_name: host-a` when it creates the NetworkAttachment.
  - Create the NetworkAttachment with the selected interface, MAC, annotation, and finalizer; derive its host and tenant identity from the recorded attachment data.
  - Exercise handoff success and failure through the management interface, including `ErrTransitioning` on both persisted targets, retries after restart without resetting the deadline, `GetPowerState` observation errors, other request errors, current terminal failures, and the 15-minute timeout. Complete each step only when the observed state matches the target and `IsTransitioning=false`; preserve actionable administrator diagnostics, fixed tenant messages, stable reasons, and opaque job IDs.
  - Map provider failures to stable reasons and administrator-visible diagnostics; verify credentials, tokens, secret values, session identifiers, and personal information are redacted while useful manager and BMC error context remains, and `NETWORK_READY` retains its fixed message.
  - Verify the BMI-derived NetworkAttachment name is reused across reconcile and restart without creating duplicates.
  - Verify the target-ID watch maps a NetworkAttachment change to its BMI and that the controller retains deadline and recovery requeues.
  - After deletion starts, do not create or update a NetworkAttachment, start a handoff, or change RunStrategy or `restart_trigger`.
  - With provider networking disabled, report `ProvisioningDisabled` only after provisioning and do not resolve a MAC.
- Networking controller:
  - Query only after `NetworkHandoffComplete`; retry after 30 seconds and every 5 minutes from attempt 20.
  - Report the lease for the selected MAC in the saved tenant network context; reject a lease for another MAC or outside that context.
- Cleanup and feedback controllers: cover finalizer lifecycle, deletion of only the BMI-owned attachment, hub endpoint handling, and retry of `FAILED_PRECONDITION`.

### Integration Tests

DEV-owned Envtest or Kind tests with BMF, osac-operator, and the mock Fabric Manager. Run `make test` in the affected components; run `make integration-tests` in BMF against a pre-existing Kind cluster.

- With `global.networking.provisioningEnabled=true`, run a Kind integration case using the mock Fabric Manager; verify the NetworkAttachment is created in the OSAC release namespace and the host moves to the selected tenant network only after the attachment is Ready and the handoff power cycle completes.
- Create follows the [Create](#create) order. Wait for the NetworkAttachment port move to become Ready before one OFF/ON handoff; start lease discovery and apply RunStrategy or a pending `restart_trigger` reboot only afterward.
- If deletion arrives after an ON request is sent, serialize power operations, keep an in-progress operation pending, confirm OFF only when `GetPowerState` reports OFF and `IsTransitioning=false`, then delete the NetworkAttachment.
- Final apply or query failures set the expected failure status; retryable query failures remain pending and retry.
- Delete follows the [Delete](#delete) order, retries network cleanup until success while retaining finalizers and host ownership, then deprovisions and releases the host; it removes only the BMI-owned attachment and preserves unrelated attachments. Deletion before any NetworkAttachment create request was sent skips offboard power-off with provider networking either enabled or disabled.
- Delay a NetworkAttachment create response until after deletion begins; verify BMF retains the BMI finalizer and host ownership, waits for the create to settle, finds the attachment with a fresh lookup, and completes cleanup before release. A timed-out or uncertain create must not take the no-attachment branch based on one `NotFound` response.
- Verify offboarding reports `Network cleanup is in progress.` and does not reuse the attachment-progress message.
- Request automatic external access only when the endpoint is ready; an allocation failure does not block BMI readiness.
- With provider networking disabled, keep OS provisioning available but run no tenant network task, handoff, lease query, or delete-time power-off; deprovision without NetworkAttachment cleanup.

### E2E Tests

QE-owned deployed BMaaS tests (OSAC-6820) with a real Fabric Manager and a supported bare-metal provisioning backend. Run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas` with BMaaS services, host access for test assertions, and `OSAC_BMI_NETWORK_INTERFACE` available.

- Provision, discover, and delete a BMI. Verify the selected port moves to the tenant network, Fulfillment reports its selected-MAC lease, and cleanup returns the port before the host is released.
- Verify tenant isolation until Ready and across tenants; exercise `RunStrategy=Halted`, automatic external access and inbound traffic, and a SecurityGroup binding failure that prevents readiness and tenant traffic.
- Verify selected SecurityGroups enforce stateful policy on the physical port: allowed traffic and established replies work, unsolicited inbound traffic is blocked, and policy failure prevents readiness and tenant traffic.
- During Netris test teardown, leave the suite-owned ExternalIPPool in place when its only remaining holders are tenant `default-nat` ExternalIPs; fail cleanup if any other ExternalIP or consumer holds the pool.
- Verify the provisioning network blocks cross-host access and rogue DHCP and restricts management-service access, including while a tenant OS runs `user_data` on first boot and when provider networking is disabled.
- Verify shared BMI/ComputeInstance Subnet behavior with `uv run pytest -n 0 -m requires_stretched_networking tests/e2e/networking/stretched`.
- Measure connectivity from completion of the handoff power cycle until the selected address is visible and the BMI is `NETWORK_READY`; the target is within two minutes.

### Edge-case tests (later)

DEV-owned follow-up tests, not current suite coverage, for the [edge cases](#edge-cases-that-need-handling) once their handling is accepted:

- A BMF restart at each handoff point, including after `ErrTransitioning`, resumes the persisted OFF or ON step through `SetPowerState`/`GetPowerState`; the step stays pending until the target state is observed with `IsTransitioning=false`, and the existing deadline is unchanged.
- Handoff deadline: measured from the persisted `NetworkAttachmentsReady=True` transition time and unchanged by the `PoweringOn` write. A completion observed after 15 minutes succeeds because each reconcile checks for completion before the timeout; if still incomplete when a reconcile checks an elapsed timeout, the handoff fails.
- BMF stops between writing the attachment-status entry and creating the NetworkAttachment: after restart, a live BMI finds or creates it by the BMI-derived name; a delete before any create request was sent skips offboard power-off, with provider networking enabled or disabled. An unsettled create sent before deletion follows the pending-create delete-race handling above.
- A restart during offboarding boots only the cleaning ramdisk after the ports return, never the tenant OS.

## Graduation Criteria

Tech Preview:
- API and CRD fields, validation, and CEL rules; BareMetalInstanceType `network_ports`.
- BMF NetworkAttachment lifecycle, handoff, and status mirroring; the networking controller's three Fabric tasks.
- Test environments with the provisioning network and each host's initial attach.
- Tech Preview graduation criterion for the reference OSAC QE lab: a QE-owned qualification report covers provisioning-network host isolation, rogue-DHCP prevention, and restricted management access. This is not a general pre-enablement gate or proof of physical isolation for an external deployment.
- Unit and integration tests pass; E2E covers one-attachment validation, automatic access, discovery, and isolation until ready.
- Operator documentation warns that tenant-controlled `user_data` runs on the provisioning network and explains the provider-side isolation prerequisites; user documentation covers BMI networking and external access.

GA:
- The selected Fabric Manager has a conformant report whose `baremetal` profile passed, and passes the follow-up network-behavior tests that measure stateful policy on physical ports ([contract §4.11](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#411-conformance-tests)).
- Stable contract registration, task execution and result handling, and NATGateway stack (OSAC-1443).
- A verified production deployment; user feedback incorporated.

## Upgrade and Downgrade Strategy

Not supported: delete everything and reinstall ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy)).

## Version Skew Strategy

Shared rules: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy). BMF shares the handoff and cleanup protocol with the components that Unified lists, so it comes from the same release; an incompatible component must not start new work. The CLI keeps the single `--network-attachment` flag across one minor version both ways; both sides reject a second attachment.

## Support Procedures

Tenants see the `NETWORK_READY` reason and its fixed message, as defined by the [Unified status policy](/enhancements/OSAC-1433-unified-networking/design.md#status). Administrator-visible BMI conditions and events contain a stable failure reason, actionable provider diagnostic, and opaque AAP job ID. Credentials, tokens, secret values, session identifiers, and personal information are redacted while useful operational context remains available to administrators ([Network status and phase](#network-status-and-phase)).

**BMI `Failed` or stuck `Progressing` with `NetworkAttachmentsReady=False`.** `NetworkAttachmentFailed` or `Progressing`: read the administrator-visible condition/event diagnostic, stable reason, and opaque AAP job ID; investigate through the authorized provider support process. For a full physical range, see [Risks](#risks-and-mitigations).

**Handoff failed (`NetworkHandoffComplete=False`, reason `NetworkHandoffFailed`).** Check the power state with `GetPowerState`, then inspect the administrator-visible BMI condition/event and backend failure signal ([Network status and phase](#network-status-and-phase)). The tenant deletes and recreates the BMI.

**No tenant IP (`IPDiscoveryComplete=False`).** For `LeasePending` or `LeaseNotFound`, check that the host booted after the handoff and requested DHCP, and that the Fabric DHCP has a lease for the MAC. `IPDiscoveryFailed`: use the administrator-visible condition/event diagnostic, stable reason, and opaque job ID to investigate through the authorized provider support process; the tenant deletes and recreates the BMI.

**ExternalIPAttachment create rejected with `FAILED_PRECONDITION`.** The [endpoint is not ready](#externalipattachment-target-baremetal_instance) (not `Ready` with an IP, stopped, or deleting). Wait for `Ready` and retry.

**Delete waits.** The remaining finalizer names the blocked [Delete](#delete) step; `osac.openshift.io/baremetalinstance-networking` carries `PowerOffFailed` or `NetworkDetaching`. For `osac.openshift.io/baremetalinstance` (deprovisioning) or `osac.openshift.io/inventory` (release), read the administrator-visible BMF diagnostic, stable reason, and opaque job ID. For `osac.openshift.io/baremetalinstance-cleanup`, see [Default Networking — Support Procedures](/enhancements/OSAC-1433-default-networking/design.md#support-procedures). Resolve the reported cause; cleanup retries while the host remains unavailable for reuse.

**Stop automatic ExternalIP requests.** See [Default Networking — Support Procedures](/enhancements/OSAC-1433-default-networking/design.md#support-procedures).

## Infrastructure Needed

- A Fabric Manager Ansible role in the AAP execution environment with `apply_network_attachment`, `delete_network_attachment`, and `query_dhcp_lease`.
- Deployment prerequisites: provider-side provisioning-network isolation as described in [Security Considerations](#security-considerations), each host's initial attach, BMC reachability on a tenant-isolated management network, inventory logical-port-to-MAC maps, and a Fabric Manager mapping from inventory host and logical port to switch port ([NetworkAttachment and address discovery](#networkattachment-and-address-discovery)).
- An integration environment with a conformant Fabric Manager and supported bare-metal provisioning backend.

---

## Provenance

Committed: commit @ design 0.14.0 - 70405a6, workspace design/OSAC-6818 @ e3a2add (1 behind origin/main, dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.14.0","ai_workflows":"70405a6","source_repo":"e3a2add (dirty)","source_repo_branch":"design/OSAC-6818","commits_behind_main":1,"commits_ahead_main":1547,"main_ref":"main","phases":["commit","commit","commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
