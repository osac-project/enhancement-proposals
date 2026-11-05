---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-11-04
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
    - [Repair mark](#repair-mark)
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
- Enabling BMaaS on a deployment that already has networking resources ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).
- Keeping the tenant OS off the provisioning network: Metal3 boots the new OS once at the end of provisioning, before the port move (a follow-up feature reduces provisioning to one boot).

## Proposal

The fulfillment service validates and stores the single network attachment. BMF provisions the host and creates one NetworkAttachment CR; the networking controller runs the Fabric tasks on it. BMF then uses its existing management API to power the host off and on, confirms both states, and reports the selected port's discovered address.

### Workflow Description

Actors: the Tenant User and the [components](#component-responsibilities). The inventory backend (Metal3, Ironic, NVIDIA Base Command Manager (BCM), or NetBox) holds each host's port-name-to-MAC map and repair mark. BMF resolves the selected port's MAC through the common inventory `GetHostLogicalPortMACs` interface and parser. The management backend powers the host: Metal3 (also for BCM and NetBox hosts, [OSAC-1339](/enhancements/OSAC-1339-bcm-backend/design.md), [OSAC-1610](/enhancements/OSAC-1610-netbox-inventory/design.md)) or Ironic. AAP templates install the OS. RunStrategy (`run_strategy`: `Always`, the default, or `Halted`) is the requested power state; each change of the counter `restart_trigger` requests one reboot.

Starting state: provider networking enabled; READY tenant default networking ([Default Networking](/enhancements/OSAC-1433-default-networking/design.md)); a NetworkClass selecting a conformant Fabric Manager; every free host's fabric ports on the provisioning network.

#### Create

1. The Tenant User creates the BMI:
   ```bash
   osac create baremetalinstance --catalog-item bcm-h100 --name my-server \
     --network-attachment subnet=my-subnet,interface=data-0,security-groups=web-sg,db-sg
   osac create baremetalinstance --catalog-item bcm-h100 --name my-server2 --external-ip-attachment
   ```
   Form 1 picks a Subnet, port `data-0`, and two SecurityGroups (syntax: `--network-attachment [subnet=<name or ID>][,interface=<port>][,security-groups=<name or ID>,...]`, each part optional, `security-groups=` last). Form 2 uses the tenant defaults and requests automatic external access (`auto_external_ip_attachment`). The CLI rejects a second `--network-attachment`.
2. The fulfillment service validates the attachment ([Network attachment and validation](#network-attachment-and-validation)); a failure stores nothing. In one transaction it stores the BMI and, if requested with provider networking enabled, one automatic ExternalIP ([Automatic external access](#automatic-external-access)), then creates their CRs; the BMI CR carries `spec.networkAttachments`.
3. The BareMetalInstance cleanup and feedback controllers add `osac.openshift.io/baremetalinstance-cleanup` and `osac.openshift.io/baremetalinstance-feedback`. BMF sets phase `Allocating`, assigns a free host (finalizer `osac.openshift.io/inventory`) that has an inventory name and a valid MAC for the selected port ([interface selection](#baremetalinstancetype-and-interface-selection)), records that MAC in `status.networkAttachmentStatuses[0].macAddress`, sets `spec.externalHostName` to the host's inventory name, and adds its management finalizer `osac.openshift.io/baremetalinstance`. In phase `Progressing`, AAP provisions the OS on the provisioning network (DHCP, no static address); then `ProvisionTemplateComplete=True`.
4. BMF adds `osac.openshift.io/baremetalinstance-networking`, writes the rest of `status.networkAttachmentStatuses[0]`, creates the NetworkAttachment in the OSAC release namespace with the recorded MAC ([NetworkAttachment and address discovery](#networkattachment-and-address-discovery)), and sets `NetworkAttachmentsReady=False`, reason `Progressing`.
5. The networking controller runs Fabric `apply_network_attachment`, again after each retryable failure; BMF copies the job message into its administrator-visible BMI condition/event. The Fabric Manager binds the port to the policy objects of its SecurityGroups, moves the port to the Subnet segment, takes the other fabric ports off the provisioning network, and keeps one fixed DHCP address for the port's MAC. When OSAC accepts the result, the NetworkAttachment is Ready; BMF sets `NetworkAttachmentsReady=True` (event `NetworkAttached`). A final failure sets `NetworkAttachmentFailed` and phase `Failed`; Fulfillment exposes a fixed tenant message for that condition reason.
6. BMF performs one handoff power cycle through the existing management interface (`NetworkHandoffComplete=False`), ignoring RunStrategy and `restart_trigger` until handoff is complete. It calls `SetPowerState(OFF)` and polls `GetPowerState` until the host is off, then calls `SetPowerState(ON)` and polls until it is on. Metal3 maps these operations to the existing `BareMetalHost.spec.online` field; Ironic uses its existing power operations. BMF retries idempotently and adds no handoff-specific management method or BareMetalHost annotation.

   On confirmation: `NetworkHandoffComplete=True`, `IPDiscoveryComplete=False` (`LeasePending`), and the OS requests its tenant address over DHCP. The controller owns the 15-minute deadline from `NetworkAttachmentsReady=True`; it checks the observed power state before declaring timeout. The handoff fails (`NetworkHandoffFailed`, phase `Failed`) when the backend reports a failure or the deadline expires ([Network status and phase](#network-status-and-phase)).
7. The networking controller watches BMIs and checks each one's NetworkAttachment on each BMI event and every 30 seconds. Once it observes `NetworkHandoffComplete=True` (a provisioning-network lease or a successful apply is not discovery), it runs Fabric `query_dhcp_lease`, retrying per [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership) (after 30 seconds, and every 5 minutes from the 20th attempt), and records the accepted lease in NetworkAttachment `status.dhcpLease`. BMF retains job diagnostics in administrator-visible conditions/events. With no lease 10 minutes after the handoff, BMF emits the Warning event `LeaseNotFound`; queries continue. Fulfillment exposes a fixed tenant message for the applicable `NETWORK_READY` reason.
8. BMF copies the address into `status.networkAttachmentStatuses[0].ipAddress`, sets `IPDiscoveryComplete=True` (event `IPDiscovered`) and phase `Ready`, and only then applies RunStrategy and any `restart_trigger` change made before Ready (one reboot). On the feedback controller's signal, the fulfillment service reads the status: state RUNNING (STOPPED for `Halted`), `NETWORK_READY` `True`, reason `IPDiscovered`.
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
        B->>B: Add finalizer osac.openshift.io/baremetalinstance-networking, write status.networkAttachmentStatuses[0]
        B->>N: Create NetworkAttachment baremetalinstance-(BMI API ID)
        B->>B: NetworkAttachmentsReady=False (Progressing)
        loop retryable failure, with backoff (BMF retains diagnostics for administrators)
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
                loop retryable failure, 30 s, every 5 min from attempt 20 (BMF retains diagnostics for administrators)
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

1. The [deletion guard](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards) rejects the delete with `FAILED_PRECONDITION` while a manually created ExternalIPAttachment targets the BMI; otherwise the state becomes DELETING. A Delete of a DELETING BMI returns OK ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#status)).
2. The fulfillment service deletes the automatic ExternalIPAttachment, then the automatic ExternalIP, then the BMI CR, in the [Unified order](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access). Jobs and retries follow [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership). The phase becomes `Deleting`.
3. From the deletionTimestamp on, BMF applies no RunStrategy or `restart_trigger`, requests no handoff and creates no NetworkAttachment; the networking controller starts no apply or query job and cancels a running one ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). BMF waits for the cleanup controller to remove its finalizer. With no host assigned (`spec.externalHostName` empty), BMF skips deprovisioning and the release (steps 7 and 8).
4. If the NetworkAttachment exists, BMF sets `NetworkOffboardComplete=False` (`Progressing`) and calls `SetPowerState(OFF)`, polling `GetPowerState` until off while the host is still on the tenant network. When power-off is confirmed (at once if already off), it sets `NetworkOffboardComplete=True`. Metal3 maps these existing management operations to `BareMetalHost.spec.online`; no handoff annotation is used. With no NetworkAttachment (always with [provider networking disabled](#provider-networking-disabled)), no tenant network is attached: BMF goes to step 7 without power-off or condition.
5. BMF calls the shared `networkattachment.DeleteOwned` helper with the deterministic BMI-derived NetworkAttachment key and BMF finalizer. The helper reads that object, issues deletion, and removes only BMF's finalizer when it is the sole remaining finalizer; the stable API-ID key identifies the BMI's attachment. BMF keeps its BMI finalizer until the NetworkAttachment is gone. The networking controller runs Fabric `delete_network_attachment` until it succeeds, unless no apply job ever started; BMF retains raw job diagnostics on administrator-visible conditions/events. The task returns all the host's fabric ports to the provisioning network, removes the policy and releases the DHCP address. If cleanup outcome is uncertain, BMF keeps the host unavailable and retains or writes the repair mark before inventory release. Then the networking controller removes its finalizer.
6. With only BMF's finalizer left, BMF removes it.
7. With no NetworkAttachment left, BMF removes `osac.openshift.io/baremetalinstance-networking` from the BMI. The AAP deprovisioning job cleans the host on the provisioning network, never booting the tenant OS. Then BMF removes `osac.openshift.io/baremetalinstance`.
8. If a FabricDomain whose `create_fabric_domain` ever started lists the host in `spec.servers`, or provider cleanup has an uncertain outcome, BMF writes or retains the [repair mark](#repair-mark) before inventory release. The mark names the FabricDomain when applicable. If writing the mark fails or the backend does not support it, BMF fails closed: it keeps host ownership and does not release the host. Otherwise, BMF releases the host with the mark and removes `osac.openshift.io/inventory`; selection skips a marked host until the authorized [repair procedure](#support-procedures) clears the mark. The feedback controller removes its finalizer last, as [Unified](/enhancements/OSAC-1433-unified-networking/design.md#hub-crs) defines, and the fulfillment service removes the record.

Each step waits for the previous one. A failed step keeps its finalizer, and the host stays owned. Deprovisioning and release are the BMaaS host lifecycle ([OSAC-1118](/enhancements/OSAC-1118-baremetal-instance-api/README.md)). A host provisioning job still running at the deletionTimestamp is cancelled, and deprovisioning starts after AAP reports it ended; BMF retries a failed deprovisioning job or release with the [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership) backoff until it succeeds. Tenant default networking resources stay.

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
    B->>B: Stop RunStrategy, restart_trigger, handoff, and NetworkAttachment create
    opt apply or query job running
        N->>M: Cancel it in AAP, wait until it ended
    end
    C->>C: Remove finalizer osac.openshift.io/baremetalinstance-cleanup
    opt NetworkAttachment exists
        B->>B: NetworkOffboardComplete=False (Progressing)
        loop every 30 s until power-off confirmed (failure: PowerOffFailed)
            B->>I: SetPowerState(OFF), observe with GetPowerState
        end
        B->>B: NetworkOffboardComplete=True
        B->>B: DeleteOwned(NetworkAttachment key, BMF finalizer)
        B->>N: Networking controller observes deletion
        B->>B: NetworkAttachmentsReady=False (Detaching)
        alt an apply job started
            loop until success, with backoff (BMF retains diagnostics for administrators)
                N->>M: delete_network_attachment
            end
            M-->>N: Fabric ports on provisioning network, SecurityGroup binding removed, DHCP address released
            N->>N: Remove finalizer osac.openshift.io/networkattachment
        else no apply job started
            N->>N: Remove finalizer osac.openshift.io/networkattachment without a task
        end
        B->>B: Remove finalizer osac.openshift.io/baremetalinstance-networking from NetworkAttachment
    end
    B->>B: Remove finalizer osac.openshift.io/baremetalinstance-networking from BMI
    opt host assigned
        loop failure, with backoff, until success
            B->>I: Deprovision (backend cleaning on provisioning network)
        end
    end
    B->>B: Remove finalizer osac.openshift.io/baremetalinstance
    opt host assigned
        opt a FabricDomain whose create job ever started lists the host in spec.servers
            B->>I: Write repair mark (naming the FabricDomain)
        end
        loop failure, with backoff, until success
            B->>I: Release host (with its mark, if any)
        end
    end
    B->>B: Remove finalizer osac.openshift.io/inventory
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
- **Inventory:** the per-host port-name-to-MAC map ([BareMetalInstanceType and interface selection](#baremetalinstancetype-and-interface-selection)) and the [repair mark](#repair-mark).
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

A `system`-tenant BMI (CaaS worker) passes the [CaaS worker check](#caas-workers) instead of the interface check. When the fulfillment service builds the BMI CR, it copies the resolved attachment into it.

#### Network planes

The BMC network (Redfish or IPMI: power, virtual media) is a deployment prerequisite outside the fabric attachment. The provisioning network carries host DHCP, image download, and the Ironic Python Agent (IPA) callback, in-band on the fabric ports. The tenant network is the Subnet segment. The Fabric Manager moves fabric ports between the last two and never touches the BMC network. Which host ports are fabric ports: [contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment).

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
- CaaS workers skip both checks ([CaaS workers](#caas-workers)).

The port name is the key in `BareMetalNetworkAttachment.interface`, the NetworkAttachment CR, task input `network_attachment.interface.name`, and each host's inventory map, a JSON object `{"<port name>": "<mac>"}`:

- Metal3: the BareMetalHost annotation `osac.openshift.io/interface-macs`;
- Ironic: node `extra["osac_interface_macs"]`;
- BCM: device `extra_values["osac_interface_macs"]`, a JSON object, or a JSON string holding one;
- NetBox: device `custom_fields.osac_interface_macs` ([OSAC-1610](/enhancements/OSAC-1610-netbox-inventory/design.md)).

BMF uses the common inventory `GetHostLogicalPortMACs` interface and its existing parser for every backend. Host selection resolves the requested logical port's MAC before assignment, accepts `:` or `-` separators in any case, and stores the canonical lowercase colon-separated MAC. An invalid or missing selected-port MAC prevents host assignment and provider work. NetBox continues to use only `custom_fields.osac_interface_macs`; this change does not merge or alter its MAC sources. An invalid MAC entry is malformed; invalid JSON makes every entry malformed.

Not supported in this release: hosts without an inventory name, or without a valid MAC for the selected fabric port in the inventory map. With provider networking enabled, BMF host selection skips such a host and logs "host <name> skipped: no inventory name" or "host <name> skipped: no valid MAC for port <port>".

#### Provisioning network and port moves

A provider-managed provisioning network (DHCP, gateway, SNAT) holds every host's fabric ports while the host is idle and during provisioning and cleaning; deployment bootstrap puts each host there. It is not an OSAC Subnet and not task input: it exists only in the Fabric Manager's backend and configuration, under the same name used at bootstrap. Without it, an unassigned host has no default gateway and IPA cannot download its image.

The port moves ([Create](#create), step 5; [Delete](#delete), step 5) follow OS provisioning, so the tenant cannot reach the host during imaging or first boot (G4); first-boot egress uses the isolated provisioning network ([Security Considerations](#security-considerations)). BMF does not depend on which network carries the IPA callback (Metal3 `Provisioning` CR configuration).

#### NetworkAttachment and address discovery

BMF creates one NetworkAttachment per BMI in the OSAC release namespace ([Unified — NetworkAttachment](/enhancements/OSAC-1433-unified-networking/design.md#networkattachment)). BMF and the networking controller run in that same namespace; there is no separately configurable networking namespace:

- name `baremetalinstance-<BMI API ID>`; BMF and the networking controller find the BMI for an API ID by its label `osac.openshift.io/baremetalinstance-uuid`;
- annotation `osac.openshift.io/tenant` from the BMI (`system` for CaaS workers);
- finalizers: BMF's `osac.openshift.io/baremetalinstance-networking` and the networking controller's `osac.openshift.io/networkattachment` ([Delete](#delete), steps 5 and 6);
- `target` = `{kind: BareMetalInstance, id: <BMI API ID>}`, identifying the owning BMI;
- `subnet` and `securityGroups` = the API IDs in `spec.networkAttachments[0]`;
- `interface` = `{type: physical, name: <spec.networkAttachments[0].interface>, macAddress: <recorded MAC>}`.

BMF resolves the MAC once, during host selection, through `GetHostLogicalPortMACs` and the common parser ([BareMetalInstanceType and interface selection](#baremetalinstancetype-and-interface-selection)), and records it as `macAddress` (CRD only) in `status.networkAttachmentStatuses[0]`. It writes `interface`, `subnetRef`, and `primary: true` there before it creates the NetworkAttachment, and `ipAddress` at discovery. The NetworkAttachment name is deterministically `baremetalinstance-<BMI API ID>` under the enforced max-one contract. BMF reads the namespaced object through an uncached API reader and polls on requeue; it does not watch NetworkAttachments. No host-name or interface-name fallback exists, also for CaaS workers.

The networking controller runs the three Fabric tasks on the manager in `status.networkManagers.fabric` ([contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#410-task-reference)), with `target` `{kind: BareMetalInstance, id, host_name}`. `host_name` is `spec.externalHostName` ([contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-apply_network_attachment--delete_network_attachment)), as the Fabric Manager's switch-port map uses it ([Infrastructure Needed](#infrastructure-needed)). BMF never launches a port-move or lease job; it copies the latest job message from `status.jobs` into its conditions.

Address discovery ([Create](#create), step 7):

- Lease acceptance and final failure: [contract — `query_dhcp_lease`](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-query_dhcp_lease). Queries never change NetworkAttachment `Ready`, so `NetworkAttachmentsReady` stays `True`.
- The Fabric DHCP keeps the MAC's address while the NetworkAttachment exists, so discovery runs once.
- Physical address range: [contract §4.8](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#48-addressing); sizing: [Risks](#risks-and-mitigations).

#### CaaS workers

CaaS worker BMIs use the same flow, in tenant `system`, with the annotation `osac.openshift.io/cluster-api-id: <Cluster API ID>` and the node set's stored `fabric_interface` as `interface`. Instead of the port check, the fulfillment service checks the worker's Subnet, SecurityGroups, and interface against what the Cluster authorizes ([CaaS worker network authorization](/enhancements/OSAC-1436-caas-networking/design.md#caas-worker-network-authorization)). The SecurityGroups include the Cluster's [automatic SecurityGroup](/enhancements/OSAC-1436-caas-networking/design.md#automatic-cluster-securitygroup); attachment tasks carry tenant `system`. The [CaaS design](/enhancements/OSAC-1436-caas-networking/design.md) defines the rest.

#### Repair mark

A repair mark keeps a released host out of selection until the Cloud Provider Admin repairs it ([Support Procedures](#support-procedures)). When cleanup leaves provider state uncertain, the mark and its details are persisted before inventory release. The delete flow also marks a host when a FabricDomain lists it ([Delete](#delete), step 8). BMF's common inventory contract writes the mark; failure to write or an unsupported backend blocks inventory release:

| Backend | Mark | Details |
|---|---|---|
| Metal3 | BareMetalHost label `osac.openshift.io/network-repair-required: "true"` | BareMetalHost annotation `osac.openshift.io/network-repair-details` |
| Ironic | Node `extra["osac_network_repair_required"]` | Node `extra["osac_network_repair_details"]` |
| BCM | Device `extra_values["osac_network_repair_required"]` | Device `extra_values["osac_network_repair_details"]` |
| NetBox | Device custom field `osac_network_repair_required` | Device custom field `osac_network_repair_details` |

The details are JSON `{baremetalInstance, subnet, interface, fabricDomains}` with API IDs; `subnet` and `interface` come from `spec.networkAttachments[0]` (empty without one). An uncertain cleanup outcome retains the mark and allocation hold until provider cleanup is confirmed or an authorized repair clears it.

#### Network status and phase

"Phase" means only the BMI `status.phase`: `Allocating`, `Progressing`, `Ready`, `Failed`, or `Deleting`. BMF sets these network conditions on the BMI:

| Condition | True when | `False` reasons |
|---|---|---|
| `NetworkAttachmentsReady` | The NetworkAttachment is Ready. | `Progressing`: apply running or retrying; latest apply diagnostic. `NetworkAttachmentFailed`: final apply failure; the NetworkAttachment `Ready` diagnostic; phase `Failed`. `Detaching`: NetworkAttachment deleting; latest `delete_network_attachment` diagnostic. |
| `NetworkHandoffComplete` | The host is observed ON after the requested off/on cycle; never reset. | `PoweringOff` / `PoweringOn`: current requested step. `NetworkHandoffFailed`: reported failed or not confirmed in time; phase `Failed`. |
| `IPDiscoveryComplete` | The accepted lease is mirrored into `ipAddress`. | `LeasePending`: from `NetworkHandoffComplete=True` on; phase stays `Progressing`; administrator condition/event retains the latest `query_dhcp_lease` diagnostic and AAP job ID, once one exists. `IPDiscoveryFailed`: that entry is `Failed`; phase `Failed`. |
| `NetworkOffboardComplete` | During delete, power-off is confirmed while still on the tenant network. | `Progressing`: powering off. `PowerOffFailed`: reported failed with administrator-visible backend diagnostic; retried every 30 seconds. |

Backend failure signal for a handoff power cycle or offboard power-off: Metal3 (also BCM and NetBox hosts), BareMetalHost `status.operationalStatus=error`, `status.errorType=power management error` and `status.errorMessage`; Ironic, the node's `last_error` from the power action.

The phase is `Ready` only when the first three conditions are `True`. BMF never reports a tenant IP before that, nor ever the provisioning-network address. During a delete, the phase is `Deleting`.

The fulfillment service maps these conditions to the API condition `NETWORK_READY` when it reads the BMI status. It checks `NetworkOffboardComplete` (only once set), `NetworkAttachmentsReady`, `NetworkHandoffComplete`, and `IPDiscoveryComplete` in an explicit ordered list and selects the first condition that is not `True`; adding a condition cannot change precedence by changing append order. It preserves the condition status and reason but maps each known reason to a fixed tenant-facing message, as `PROVISIONED` does. The message map is:

| Condition reason | Tenant-facing message |
|---|---|
| `NetworkAttachmentFailed` | `Network attachment did not complete.` |
| `NetworkHandoffFailed` | `Network handoff did not complete.` |
| `IPDiscoveryFailed` | `IP address discovery did not complete.` |
| `Progressing` | `Network attachment is in progress.` |
| `PoweringOff`, `PoweringOn` | `Network handoff is in progress.` |
| `LeasePending` | `IP address discovery is in progress.` |
| `Detaching` | `Network cleanup is in progress.` |
| All network phases complete | `Network setup is complete.` |
| `ProvisioningDisabled` | `Provider networking is disabled; network setup was skipped.` |
| `PowerOffFailed` | `Network cleanup did not complete.` |
| Any other network reason | `Network setup did not complete.` |

Provider, manager, BMC, and AAP error text and job IDs remain in administrator-visible BMI conditions/events and are not copied into tenant messages. If all network conditions are `True`, Fulfillment uses reason `ProvisioningDisabled` when the provider phases were skipped ([Provider networking disabled](#provider-networking-disabled)), else `IPDiscovered`. A BMI that fails before any network condition (host assignment or OS provisioning) has no `NETWORK_READY`.

Once the delete is accepted, the API state is DELETING, whatever the phase ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#status)). Before that, and before phase `Ready`, it is PROVISIONING (FAILED for phase `Failed`). The handoff power calls do not update BMF's power-state condition `PowerSynced`, so the tenant never sees STOPPING, STARTING, or RUNNING during the handoff.

#### ExternalIPAttachment target `baremetal_instance`

| Item | BMaaS definition |
|---|---|
| Endpoints | One per BMI. `target_endpoint` other than `UNSPECIFIED`: `INVALID_ARGUMENT`. |
| Endpoint ready | Fulfillment service: API state RUNNING, `ip_address` set, not being deleted; else `FAILED_PRECONDITION`. The cleanup controller tests the hub CR: phase `Ready`, `status.networkAttachmentStatuses[0].ipAddress` set, no deletionTimestamp, `status.runStrategy=Always` (BMF's observed power state). A stopped (`Halted`) BMI is not ready. |
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
- No repair mark: no FabricDomain task ever ran.

#### Component responsibilities

BMaaS uses the NetworkClass's Fabric Manager and runs no Kubernetes Manager task for its NetworkAttachment, also when the deployment selects one, because the Kubernetes Manager has no enforcement point on a physical port ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary), [contract §4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#410-task-reference)). A provider may implement the Fabric tasks with its own switch, router, and DHCP APIs; BMF uses the same gates either way.

| Component | Responsibility |
|---|---|
| fulfillment-service | Validation, gates, and guards; the BMI CR and automatic resources. |
| BMF | Inventory, OS provisioning, power, MAC resolution, NetworkAttachment create and delete, handoff, offboard power-off, repair mark, status mirroring, the disabled fallback. Never calls a manager. |
| Networking controller | Runs every BMaaS manager task; builds `destination`; reports status. |
| Fabric Manager | Binds ports to SecurityGroup policy objects, moves ports, serves DHCP, and returns the selected MAC's lease; restores the ports on delete. Never reboots the host. |
| osac-operator BareMetalInstance cleanup controller | Adds its finalizer on first reconcile of every BMI with the API ID label; requests the automatic ExternalIPAttachment; on delete, removes its finalizer once no automatic CR for the BMI remains, deleting none ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)). |
| osac-operator BareMetalInstance feedback controller | Adds its finalizer on first reconcile; signals the fulfillment service on status changes and after it removes its finalizer; removes its finalizer last ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#hub-crs)). |

BMF and osac-operator act on the same BMI CR and coordinate only through conditions, NetworkAttachment status, finalizers, and the repair mark.

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

- Shared tenancy model: [Unified — RBAC / Tenancy](/enhancements/OSAC-1433-unified-networking/design.md#rbac--tenancy). A `system`-tenant worker is admitted only through the CaaS worker check; private API credentials alone do not authorize a foreign network.
- The port is bound to its SecurityGroups' policy objects before it joins the Subnet segment.
- The tenant OS, with its `user_data`, first boots on the provisioning network and stays there while a port move waits, or for good with provider networking disabled. The provider must isolate hosts there: port isolation or a private VLAN, DHCP snooping so only the provider's DHCP answers, and filters allowing only DHCP, the image source, Ironic, and outbound SNAT, except the traffic a Cluster needs with provider networking disabled ([CaaS](/enhancements/OSAC-1436-caas-networking/design.md#infrastructure-needed)).

### Failure Handling and Recovery

Retries follow [contract §4.6](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#46-task-result-and-errors) and [§4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership). Restart, race, and partial-failure cases: [Edge cases](#edge-cases-that-need-handling).

| Failure | What the user sees | Recovery |
|---|---|---|
| Apply, handoff, or lease failure | Retryable: phase `Progressing`; final: phase `Failed` ([Network status and phase](#network-status-and-phase)). | Automatic retry; after a final failure BMF does not retry and the tenant deletes the BMI. |
| Automatic ExternalIP or ExternalIPAttachment fails | Shown on that resource only. | Per Unified. |
| A cleanup step fails or its provider outcome is uncertain | Phase `Deleting`; finalizer and host ownership stay; administrator diagnostic in `NetworkOffboardComplete` (`PowerOffFailed`) or `NetworkAttachmentsReady` (`Detaching`); retain/write the repair mark and keep the host unavailable before inventory release. | Retry owned cleanup until confirmed. If uncertainty remains, fail closed; release only with a durable repair mark, and clear it only after confirmed cleanup or authorized repair. Admission rejects removing finalizers by hand ([Unified — Non-Goals](/enhancements/OSAC-1433-unified-networking/design.md#non-goals)). |
| BMI CR or NetworkAttachment deleted or lost outside OSAC | The OSAC admission policy rejects a delete; a loss is unsupported ([Unified — Non-Goals](/enhancements/OSAC-1433-unified-networking/design.md#non-goals)). | None by OSAC. |

### RBAC / Tenancy

- BMF: create, get, patch, and delete NetworkAttachments, and get, list, and watch FabricDomains, in the OSAC release namespace. BMF reads NetworkAttachments by namespaced key through the API reader and polls on requeue; it does not watch or list them.
- Networking controller: get, list, and watch BareMetalInstances, including status; read VirtualNetworks, Subnets, SecurityGroups, and the NetworkClass; update NetworkAttachment status and finalizers.
- BareMetalInstance cleanup controller: get, list, and watch BareMetalInstances, and update their finalizers; get, list, and watch `externalipattachments` and `externalips` in the hub networking namespace; call the fulfillment private API.
- The fulfillment service checks the network's tenant when it admits the BMI. The networking controller does not check tenants, because worker BMIs are in tenant `system`. The controllers and networking objects use the OSAC release namespace; there is no `OSAC_NETWORKING_NAMESPACE` setting or startup check.
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

No networking metrics or alerts; the BMaaS provisioning duration and failure metrics apply. Task diagnostics: [contract §7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#7-observability-and-monitoring). Automatic external access logs: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#observability-and-monitoring).

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| The Fabric Manager or provisioning network is missing or late. | Enable BMaaS only after the Fabric Manager has a conformant report whose `baremetal` profile passed ([contract §4.11](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#411-conformance-tests)); the follow-up network-behavior tests measure physical policy. |
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
| BMF restarts during the handoff. | The power cycle is lost or repeated out of order. | Persist `PoweringOff` before requesting OFF and `PoweringOn` after OFF is observed. On restart, repeat the existing `SetPowerState` call for the persisted step and use `GetPowerState` to observe progress; mark complete only after ON is observed. No handoff annotation or in-memory-only step is used. |
| A cached BareMetalHost is stale during a handoff or offboard decision. | A stale power observation can falsely confirm the step. | Use the management interface's `GetPowerState` observation for each decision and do not infer completion from a cached BareMetalHost. |
| BMF restarts after the NetworkAttachment create, before its status write. | A second create, or a BMI stuck without a condition. | Fixed name `baremetalinstance-<BMI API ID>`; create only if missing, and an `AlreadyExists` reply counts as created. |
| BMF stops between the `networkAttachmentStatuses[0]` write and the NetworkAttachment create. | A live BMI waits forever, or a delete expects a NetworkAttachment. | A live BMI gets the NetworkAttachment created after the restart and runs the handoff; a delete finds none and skips the power-off. |
| BMF restarts during host assignment. | A host is assigned twice or leaked. | Follow the [OSAC-1118](/enhancements/OSAC-1118-baremetal-instance-api/README.md) host lifecycle. |
| BMF loses the job ID of a host provisioning job before a delete. | The running job is not cancelled before deprovisioning. | Find it by its AAP label, as the contract does for manager jobs, cancel it, and deprovision after AAP reports it ended. |
| `LeaseNotFound` after a BMF restart. | The warning may repeat once. | Accepted. |

### Delete races

| Case | Why it matters | Proposed handling |
|---|---|---|
| The create flow continues after the delete is accepted but before the BMI CR is deleted. | Status could look like progress. | The API state stays DELETING whatever BMF does; BMF stops at the deletionTimestamp. |
| Delete during a pending handoff. | The host could power on onto the tenant network during cleanup. | At deletion, stop the handoff sequence, call `SetPowerState(OFF)`, and do not issue the ON step; wait for `GetPowerState` to confirm OFF before network cleanup. |
| Delete during an apply or query job. | A late result could fail or advance the BMI. | Cancel the job; it ends `Cancelled`, which is never a failure reason, and the phase stays `Deleting`. |

### Handoff

| Case | Why it matters | Proposed handling |
|---|---|---|
| The handoff confirmation arrives near the 15-minute deadline, or Ironic moves from `PoweringOff` to `PoweringOn`. | A confirmed power cycle is treated as failed, or the clock restarts. | Check for confirmation before the deadline on each reconcile, so a confirmation present when the deadline check runs still succeeds; the `PoweringOn` write does not move the deadline. |

## Alternatives (Not Implemented)

| Alternative | Why rejected |
|---|---|
| Merge BMF into osac-operator. | BMF owns the inventory and management backends; separate operators keep host lifecycle and networking apart. |
| OSAC allocates static per-host addresses. | Needs per-OS templates (cloud-init, NMState, kickstart), per-host allocation and cross-operator locking. Fabric DHCP works for every OS. |
| Attach the tenant network before OS provisioning. | The tenant could reach a half-built host, and provisioning traffic would cross the tenant network. |
| Default gateway on the BMC NIC instead of a provisioning network. | Two default routes once the tenant Subnet is attached. |

## Test Plan

Shared task and result checks: [contract test plan](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md) and [Unified test plan](/enhancements/OSAC-1433-unified-networking/design.md#test-plan).

This plan has 13 automated cases covering FR-1, FR-3, FR-7, FR-8, FR-12, FR-13, and NFR-2 (7 of 15 parent requirements): 4 critical, 8 high, and 1 medium. FR-2, FR-4, FR-5, FR-6, FR-9, FR-10, FR-11, and NFR-1 remain with their owning implementation work. Unit, integration, and contract evidence belongs to the owning DEV work; deployed cross-component journeys belong to QE.

### Unit Tests

- Fulfillment service:
  - Each [validation](#network-attachment-and-validation) rule and code: no `fabric` port, type from catalog item or template, no resolvable type, Update of an immutable field.
  - A worker with the authorized `fabric_interface` skips the port check; stored defaults `primary: true`, `run_strategy: Always`.
  - ExternalIPAttachment endpoint-ready (also a stopped BMI) and `target_endpoint` checks.
  - Subnet delete rejected while a BMI references it.
  - Each `NETWORK_READY` case, also during a delete with provider networking disabled; PROVISIONING before `Ready` whatever the power state; DELETING once the delete is accepted, whatever the phase.
- BMF:
  - MAC resolution per backend (BCM: object and string), normalization, malformed entry, unparsable map.
  - `spec.externalHostName`; exact NetworkAttachment spec, annotation, and finalizer; host assignment skips a host without an inventory name or a valid MAC for the selected port, and records the MAC.
  - Handoff per backend (Metal3, also on BCM and NetBox hosts; Ironic); `NetworkHandoffFailed` per backend signal and at 15 minutes.
  - Each row of [Network status and phase](#network-status-and-phase), including copied messages and job IDs.
  - After the deletionTimestamp: no NetworkAttachment, handoff, RunStrategy, or `restart_trigger`.
  - Repair mark per backend: written before release, kept at release, honored by selection; deprovisioning still runs.
  - Provider networking disabled: `ProvisioningDisabled` only after `ProvisionTemplateComplete=True`; no MAC resolution.
- Networking controller:
  - `target.host_name` from `spec.externalHostName`; `tenant` from the annotation.
  - Query only after `NetworkHandoffComplete=True`; retry after 30 seconds, every 5 minutes from attempt 20.
  - Wrong-MAC or out-of-range lease rejected.
- BareMetalInstance cleanup controller: finalizer lifecycle ([Component responsibilities](#component-responsibilities)); hub endpoint test; `FAILED_PRECONDITION` retried at the 30-second recheck.
- Feedback controller: finalizer added on first reconcile, removed last.

**Requirement-mapped cases**

#### FR-1: At most one attachment

##### TC-FR1-01: Reject more than one attachment

| Requirement | Priority | Automation |
|---|---|---|
| FR-1 | high | automated |

**Preconditions:** The request otherwise has a valid BMI type and network attachment.

**Steps:**

1. Submit a BMI create request with two network attachments.
2. Read the BMI list for the tenant.

**Expected Results:** Fulfillment returns `INVALID_ARGUMENT` with the at-most-one validation message and stores no BMI.
**Evidence:** DEV unit; run `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; API validation is real and persistence is stubbed.

#### FR-3: Validate the selected interface

##### TC-FR3-01: Reject invalid or non-tenant interface

| Requirement | Priority | Automation |
|---|---|---|
| FR-3 | high | automated |

**Preconditions:** The catalog type has at least one fabric port.

**Steps:**

1. Submit a BMI request with an interface absent from the type's port catalog.
2. Submit a BMI request with a system-only/non-fabric interface.
3. Check the API response and verify no BMI CR was created for either request.

**Expected Results:** Both requests fail with `INVALID_ARGUMENT` before a BMI CR or provider operation is created.
**Evidence:** DEV unit; run `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` and `make test` from `bare-metal-fulfillment-operator/`; production validation/selection code is real and catalogs/inventory are fixtures.

### Integration Tests

envtest or kind with BMF, osac-operator, and the mock Fabric Manager:
- Create follows [Create](#create) order; RunStrategy, and one reboot for a `restart_trigger` change made earlier, only after discovery.
- Final apply failure (`NetworkAttachmentFailed`) and a failed query entry (`IPDiscoveryFailed`) give phase `Failed`; retryable query failures keep `LeasePending` and `NetworkAttachmentsReady=True`.
- Delete runs in [Delete](#delete) order, feedback finalizer last; every cleanup failure keeps its finalizer.
- Automatic access: requested only when the endpoint is ready and the ExternalIP ALLOCATED; none after delete starts; a failed allocation does not block readiness.
- Provider networking disabled: host jobs run, no networking task, `ProvisioningDisabled` conditions, empty statuses; delete deprovisions without power-off or NetworkAttachment.

**Requirement-mapped cases**

#### FR-7: Configure connectivity after provisioning

##### TC-FR7-01: Move selected port, power-cycle, then discover lease

| Requirement | Priority | Automation |
|---|---|---|
| FR-7 | high | automated |

###### Preconditions

- The selected interface resolves to a valid MAC.
- OS provisioning has completed and the deployment-provided provisioning network is available.

###### Steps

1. Reconcile the BMI through network setup and handoff.
2. Observe the shared networking request, management power API calls, and final BMI status.

###### Expected Results

- The shared networking controller receives one move for the selected logical port from provisioning to tenant network.
- BMF calls `SetPowerState(OFF)`, observes `OFF`, calls `SetPowerState(ON)`, and observes `ON` before lease discovery starts.
- The tenant status reaches `NETWORK_READY` only after a selected-MAC lease is reported.

**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; `make test` in `bare-metal-fulfillment-operator/`; real reconciliation and Kubernetes persistence with inventory, management, and provider transitions faked.

##### TC-FR7-02: Wait for provider move readiness before handoff

| Requirement | Priority | Automation |
|---|---|---|
| FR-7 | medium | automated |

**Preconditions:** A BMI has completed OS provisioning and has a NetworkAttachment with an `apply_network_attachment` job in progress.

**Steps:**

1. Reconcile the BMI repeatedly while the NetworkAttachment remains not Ready.
2. Mark the NetworkAttachment Ready and reconcile the BMI again.

**Expected Results:** While the attachment is pending, BMF does not start the handoff or lease discovery. After Ready, BMF starts exactly one OFF/ON handoff sequence.
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; `make test` in `bare-metal-fulfillment-operator/`; provider response is faked. Confirm real AAP/provider retry semantics under OSAC-4843 where needed.

#### FR-8: Expose the selected attachment address

##### TC-FR8-01: Report lease for selected MAC and saved network

| Requirement | Priority | Automation |
|---|---|---|
| FR-8 | high | automated |

**Preconditions:** The BMI handoff is complete, and the selected interface's MAC and tenant network are stored in the NetworkAttachment.

**Steps:**

1. Return a DHCP lease for the selected MAC in the saved tenant network context.
2. Reconcile the NetworkAttachment and BMI feedback.

**Expected Results:** The BMI attachment status contains that lease address and Fulfillment exposes the same address to the tenant.
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; run `ginkgo run --timeout 20m internal/controllers/baremetalinstance` from `fulfillment-service/` and `make test` from BMF; provider response is a fixture, while the Kubernetes status and service mapping code are real.

##### TC-FR8-02: Ignore leases for a different MAC

| Requirement | Priority | Automation |
|---|---|---|
| FR-8 | high | automated |

**Preconditions:** The BMI handoff is complete, and the selected interface's MAC is recorded.

**Steps:**

1. Return a DHCP lease whose MAC belongs to a different port.
2. Reconcile the NetworkAttachment and BMI feedback.

**Expected Results:** The Networking controller rejects the lease because its MAC differs from the selected interface; BMI status contains no tenant address, IP discovery fails, and Fulfillment reports `IP address discovery did not complete.`
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; run `ginkgo run --timeout 20m internal/controllers/baremetalinstance` from `fulfillment-service/` and `make test` from BMF; lease records are fixtures.

#### FR-12: Delete the attachment and release its address

##### TC-FR12-01: Delete owned attachment and release tenant connectivity

| Requirement | Priority | Automation |
|---|---|---|
| FR-12 | critical | automated |

**Preconditions:** A Ready BMI has an attachment at its deterministic BMI-derived key and a known tenant lease.

**Steps:**

1. Delete the BMI through Fulfillment.
2. Observe BMF's power state calls, NetworkAttachment deletion, and finalizer state.
3. Observe the shared networking controller complete tenant-to-provisioning cleanup.

**Expected Results:** BMF powers off the host, and the shared networking controller cleans up the selected port. The BMI finalizer remains until cleanup succeeds or a durable repair hold is recorded before inventory release. Confirmed cleanup releases the tenant attachment/address.
**Evidence:** BM-DEV-02 Envtest, BM-DEV-03 osac-operator unit/Envtest, and BM-DEV-04 Kind; `make test` in BMF and osac-operator, then `make integration-tests` in BMF. Kubernetes lifecycle is real in Envtest/Kind; provider release is simulated. Use OSAC-4843 for provider contract evidence.

##### TC-FR12-02: Retain repair mark and allocation hold on uncertain cleanup

| Requirement | Priority | Automation |
|---|---|---|
| FR-12 | critical | automated |

**Preconditions:** A Ready BMI owns a host with a NetworkAttachment and inventory entry.

**Steps:**

1. Make tenant-to-provisioning cleanup return an uncertain outcome.
2. Reconcile the BMI through the repair-hold decision.
3. Attempt to allocate another BMI from the same inventory.

**Expected Results:** The repair mark is persisted before inventory release and the host is not selected for the second BMI. If the marker is unsupported or cannot be written, BMF retains inventory ownership and the BMI finalizer. The mark is cleared only after confirmed provider cleanup or the authorized repair workflow resolves the host.
**Evidence:** BM-DEV-02 Envtest persists the marker across reconciles; `make test` in BMF. Inventory/provider responses are faked. Verify the marker's real inventory contract under OSAC-4843.

##### TC-FR12-03: Preserve unrelated attachments and retry cleanup

| Requirement | Priority | Automation |
|---|---|---|
| FR-12 | critical | automated |

**Preconditions:** The namespace contains the BMI attachment at its deterministic key and an unrelated/manual attachment at a different key.

**Steps:**

1. Make cleanup of the BMI attachment fail once.
2. Reconcile the delete again and allow cleanup to succeed.
3. Read both NetworkAttachments and the BMI finalizer state.

**Expected Results:** The shared cleanup helper deletes the object at the BMI-derived key; the unrelated attachment remains. The BMI finalizer remains after the first failure and is removed only after cleanup succeeds. Existing ComputeInstance cleanup results remain unchanged.
**Evidence:** BM-DEV-03 unit/Envtest and BM-DEV-04 Kind; extend `osac-operator/internal/controller/networking_contract_test.go`, `osac-operator/internal/controller/baremetalinstance_cleanup_controller_test.go`, and `osac-operator/internal/controller/computeinstance_cleanup_test.go`, plus `bare-metal-fulfillment-operator/test/integration/networking_cleanup_test.go`; run `make test` in osac-operator and `make integration-tests` in BMF. Kubernetes objects are real in Envtest/Kind; provider transitions are faked.

#### FR-13: Provider networking disabled

##### TC-FR13-01: Preserve disabled-networking provisioning behavior

| Requirement | Priority | Automation |
|---|---|---|
| FR-13 | high | automated |

**Preconditions:** The OSAC deployment has provider networking disabled before installation.

**Steps:**

1. Create and reconcile a BMI with a network attachment request.
2. Wait for OS provisioning and inspect NetworkAttachment, power, and lease activity.
3. Delete the BMI and observe deprovisioning.

**Expected Results:** OS provisioning remains available; BMF submits no tenant port move, handoff power cycle, or lease query; skipped phases do not claim tenant connectivity or an IP address. Delete deprovisions without power-off or NetworkAttachment cleanup.
**Evidence:** BM-DEV-02 Envtest and BM-DEV-04 Kind; `make test` and `make integration-tests` in `bare-metal-fulfillment-operator/`; API server/operator wiring is real in Kind and provider calls are observed through fakes.

### E2E Tests

With a real Fabric Manager and Metal3 or Ironic:
- Provision, discover, and delete a BMI and a CaaS worker on one Subnet; ports move provisioning → tenant → provisioning; a freed host can inspect again.
- Isolation until ready: tenant reachability only after the move and reboot; host then off the provisioning network.
- `RunStrategy=Halted`: the handoff powers the host on; discovery completes before RunStrategy applies.
- `--external-ip-attachment`: both automatic resources appear, inbound traffic to the ExternalIP reaches the host, and both are removed on delete.
- A SecurityGroup binding failure prevents readiness and tenant traffic.

**Requirement-mapped cases**

#### FR-7: Configure connectivity after provisioning

##### TC-FR7-03: Verify tenant handoff in deployed BMaaS

| Requirement | Priority | Automation |
|---|---|---|
| FR-7 | high | automated |

**Preconditions:** The deployed BMaaS test environment has an available BMH, Netris fabric, tenant subnet, and tenant DHCP.

**Steps:**

1. Create a BMI with one selected interface.
2. Wait for the BMI to reach network readiness and read its tenant IP from Fulfillment.
3. Inspect the selected port's fabric placement and lease.

**Expected Results:** The selected fabric port is on the tenant network after the handoff power cycle, and the address visible in Fulfillment matches the lease for that port on the tenant network.
**Evidence:** Proposed QE extension to `tests/e2e/networking/bmaas/test_bmaas_networking.py`; run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires Netris BMaaS services, BMH SSH endpoints, `OSAC_BMI_NETWORK_INTERFACE`, fabric, and tenant DHCP. OSAC, BMC, fabric, DHCP, and status feedback run for real; no provider fakes.

#### FR-12: Delete the attachment and release its address

##### TC-FR12-04: Verify tenant port cleanup in deployed BMaaS

| Requirement | Priority | Automation |
|---|---|---|
| FR-12 | critical | automated |

**Preconditions:** The deployed BMaaS test environment has a Ready BMI with a selected-MAC tenant lease.

**Steps:**

1. Delete the BMI through Fulfillment.
2. Wait for the BMI and its NetworkAttachment to disappear.
3. Inspect the selected port's network and lease state.

**Expected Results:** The tenant-to-provisioning port move is confirmed before the host is released, and the deleted BMI's NetworkAttachment no longer appears in the API; unrelated tenant resources remain.
**Evidence:** Proposed QE extension to `tests/e2e/networking/bmaas/test_bmaas_networking.py`; run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires Netris BMaaS services, BMH SSH endpoints, fabric, tenant DHCP, and API access. Provider movement and Kubernetes/API state are real.

#### NFR-2: Connectivity completes within two minutes

##### TC-NFR2-01: Meet the two-minute connectivity target

| Requirement | Priority | Automation |
|---|---|---|
| NFR-2 | high | automated |

###### Preconditions

- Run against the Netris BMaaS profile with live BMH, fabric, and tenant DHCP; provider outcomes are not faked.

###### Steps

1. Start a monotonic timer when the BMI reports `ProvisionTemplateComplete=True`.
2. Wait for the deployed Fulfillment API to expose the selected attachment IP and `NETWORK_READY` status.
3. Stop the timer and compare the elapsed time with the 120-second bound.

###### Expected Results

- The selected attachment address is visible to the tenant no later than 120 seconds after `ProvisionTemplateComplete=True`.

**Evidence:** QE deployed E2E; collect with `uv run pytest --collect-only -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`, then run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires the Netris BMaaS services, BMH SSH endpoints, `OSAC_BMI_NETWORK_INTERFACE`, and fabric/DHCP integration. Fabric and DHCP are real; test fixtures are not used for provider outcomes. Provider-disabled test runs do not satisfy this case.

### Edge-case tests (later)

For the [edge cases](#edge-cases-that-need-handling), once their handling is accepted:
- A BMF restart at each handoff point (after `PoweringOff`, after OFF is observed, after `PoweringOn`, after ON is observed) resumes the persisted step through `SetPowerState`/`GetPowerState` and reaches `Ready` without a handoff annotation.
- Handoff deadline: measured from `NetworkAttachmentsReady=True` and unchanged by the `PoweringOn` write; a confirmation seen after 15 minutes still succeeds; no deadline check after the confirmation.
- Delete during an apply or query cancels it (`Cancelled`, phase `Deleting`); during the handoff, BMF confirms OFF and issues no subsequent ON request.
- BMF stops between the `networkAttachmentStatuses[0]` write and the NetworkAttachment create: after the restart, a live BMI gets it created and runs the handoff; a delete finds none and skips the power-off.
- A BMI delete while a FabricDomain whose create started lists its host in `spec.servers`: deprovisioning runs, the mark is written, the host is released and skipped until the mark is deleted; with no such FabricDomain, no mark.
- A restart during offboarding boots only the cleaning ramdisk after the ports return, never the tenant OS.

## Graduation Criteria

Tech Preview:
- API and CRD fields, validation, and CEL rules; BareMetalInstanceType `network_ports`.
- BMF NetworkAttachment lifecycle, handoff, and status mirroring; the networking controller's three Fabric tasks.
- Test environments with the provisioning network and each host's initial attach.
- Unit and integration tests pass; E2E covers one-attachment validation, automatic access, discovery, and isolation until ready.
- User documentation for BMI networking and external access.

GA:
- The selected Fabric Manager has a conformant report whose `baremetal` profile passed, and passes the follow-up network-behavior tests that measure stateful policy on physical ports ([contract §4.11](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#411-conformance-tests)).
- Stable contract registration, task execution and result handling, and NATGateway stack (OSAC-1443).
- A verified production deployment; user feedback incorporated.

## Upgrade and Downgrade Strategy

Not supported: delete everything and reinstall ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy)).

## Version Skew Strategy

Shared rules: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy). BMF shares the handoff and cleanup protocol with the components that Unified lists, so it comes from the same release; an incompatible component must not start new work. The CLI keeps the single `--network-attachment` flag across one minor version both ways; both sides reject a second attachment.

## Support Procedures

Tenants see the `NETWORK_READY` reason and its fixed message; provider diagnostics remain in administrator-visible BMI conditions and events ([Network status and phase](#network-status-and-phase)).

**BMI `Failed` or stuck `Progressing` with `NetworkAttachmentsReady=False`.** `NetworkAttachmentFailed` or `Progressing`: read the NetworkAttachment status (task, `osac_error` message, AAP job ID), then the Fabric Manager role's job log; for a full physical range, see [Risks](#risks-and-mitigations).

**Handoff failed (`NetworkHandoffComplete=False`, reason `NetworkHandoffFailed`).** Check the power state with `GetPowerState`, then inspect the administrator-visible BMI condition/event and backend failure signal ([Network status and phase](#network-status-and-phase)). The tenant deletes and recreates the BMI.

**No tenant IP (`IPDiscoveryComplete=False`).** For `LeasePending` or `LeaseNotFound`, check that the host booted after the handoff and requested DHCP, and that the Fabric DHCP has a lease for the MAC. `IPDiscoveryFailed`: read the failed `query_dhcp_lease` entry in `status.jobs`; the tenant deletes and recreates the BMI.

**ExternalIPAttachment create rejected with `FAILED_PRECONDITION`.** The [endpoint is not ready](#externalipattachment-target-baremetal_instance) (not `Ready` with an IP, stopped, or deleting). Wait for `Ready` and retry.

**Delete waits.** The remaining finalizer names the blocked [Delete](#delete) step; `osac.openshift.io/baremetalinstance-networking` carries `PowerOffFailed` or `Detaching`. For `osac.openshift.io/baremetalinstance` (deprovisioning) or `osac.openshift.io/inventory` (release), read the BMF log and the AAP deprovisioning job. For `osac.openshift.io/baremetalinstance-cleanup`, see [Default Networking — Support Procedures](/enhancements/OSAC-1433-default-networking/design.md#support-procedures). Repair the cause; retries continue.

**Host with the [repair mark](#repair-mark).** The Cloud Provider Admin deletes the mark and its details once no FabricDomain lists the host in `spec.servers` (the tenant deletes such a FabricDomain to free the host), or once the admin confirms in the backend that no east-west domain contains the host; assignment then uses the host again.

**Stop automatic ExternalIP requests.** See [Default Networking — Support Procedures](/enhancements/OSAC-1433-default-networking/design.md#support-procedures).

## Infrastructure Needed

- A Fabric Manager Ansible role in the AAP execution environment with `apply_network_attachment`, `delete_network_attachment`, and `query_dhcp_lease`.
- Deployment prerequisites: the provisioning network with host isolation ([Security Considerations](#security-considerations)), each host's initial attach, BMC reachability on a tenant-isolated management network, the inventory's port-name-to-MAC maps (for NetBox, the `dcim.device` custom fields `osac_interface_macs`, `osac_network_repair_required`, and `osac_network_repair_details`), and the Fabric Manager's map from host name and port name to switch port (its settings or inventory), keyed by the inventory host names ([NetworkAttachment and address discovery](#networkattachment-and-address-discovery)).
- An integration environment with a Fabric Manager and a Metal3 or Ironic backend.

---

## Provenance

Authored: revise @ design 0.14.0 - 70405a6, workspace OSAC-6779-migrate-metallb-to-v1 @ 077d97689 (60 behind origin/main)
Phases: draft, revise, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.14.0","ai_workflows":"70405a6","source_repo":"077d97689","source_repo_branch":"OSAC-6779-migrate-metallb-to-v1","commits_behind_main":60,"commits_ahead_main":2,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
