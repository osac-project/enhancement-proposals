# CaaS Networking — Optional Attachments and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-07-08 |

## 1. Problem Statement

Cluster currently has NO networking fields. All networking is handled inline by the CaaS template via step collections (`osac.service.cluster_infra` and `osac.service.external_access` dispatching to `{{ network_steps_collection }}.cluster_infra` and `{{ network_steps_collection }}.external_access`). Tenants have no control over which VirtualNetwork or Subnet their cluster nodes use. The CaaS template does ALL networking (VLAN creation, SNAT, DNAT, IP allocation, DNS, MetalLB) — none goes through the OSAC Networking API. Tenants cannot place two clusters in the same VirtualNetwork or isolate them in separate VNs. The `network_steps_collection` env var selects the ENTIRE networking backend — it's deployment-wide, not per-resource. Step collections (netris.steps, agentless_net.steps) duplicate functionality that should be in the networking API. Creating a cluster with external access requires understanding the template's inline networking, and tenants have no visibility into or control over the provisioned networking resources.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a Cluster with explicit `network_attachments` specifying Subnet and SecurityGroups per node set
- Cluster supports `ClusterNetworkAttachment` message mapping node sets to Subnets with resolved fabric interfaces from HostType
- A tenant can create a Cluster with `--external-ip=auto-all` and have the system allocate two ExternalIPs (API and ingress) and attach them automatically
- A tenant can create a Cluster with `--nat-gateway=auto` and have the system provision or reuse a NATGateway on the cluster's VirtualNetwork for outbound connectivity
- Optional `network_attachments` field — when omitted, the system populates with tenant's default Subnet and SecurityGroup per node set
- CaaS operator handles agent selection and network attachment provisioning (dispatcher calls `create_network_attachment` per BM node before HyperShift provisioning)
- Template provisions MetalLB VIPs and writes them to ClusterOrder status for feedback loop to ExternalIPAttachment controller
- Step collections (`osac.service.cluster_infra`, `osac.service.external_access`) removed from CaaS template

### 2.2 Non-Goals

- VMaaS or BMaaS networking (this PRD covers CaaS only; ComputeInstance and BaremetalInstance are addressed in separate enhancements)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Multi-manager tracking (Jira OSAC-1459) implementation
- DNS API (DNS record creation remains inline in template)
- VM-based cluster node sets (HyperShift ↔ CUDN integration deferred)

## 3. Requirements

### 3.1 Functional Requirements

#### ClusterNetworkAttachment Proto

- **FR-1:** Cluster uses `ClusterNetworkAttachment` message specific to CaaS. The message includes `subnet` (Subnet ID), `security_groups` (SecurityGroup IDs), `node_set` (optional node set name), and `fabric_interface` (system-populated from HostType). [Source: `.planning/caas-networking-design.md` — API Changes]

#### Fabric Interface Resolution from HostType

- **FR-2:** HostType resource includes a `repeated NetworkInterface interfaces` field (name, role, description). For BM host types, the interfaces list describes physical interfaces. For VM host types, the list is empty (discriminator: interfaces present = BM, empty = VM). [Source: `.planning/caas-networking-design.md` — HostType and Interface Resolution]

- **FR-3:** When ClusterNetworkAttachment is created, fulfillment-service resolves the node set's `host_type` → HostType → picks the first interface with role `fabric` and stores as `fabric_interface` on the attachment. The `fabric_interface` field is immutable and system-populated. [Source: `.planning/caas-networking-design.md` — How CaaS Uses HostType]

#### Optional Network Attachments with Defaults

- **FR-4:** The `network_attachments` field on ClusterSpec is optional. When omitted, the fulfillment-service populates it with the tenant's default Subnet and default SecurityGroup per node set (see Simplified Resource Creation PRD). The resolved attachments are stored in the resource spec so the resource is self-describing after creation. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 5]

#### Auto ExternalIP for API and Ingress

- **FR-5:** ClusterSpec supports an `external_ip_mode` field with values `NONE` (default), `AUTO_API`, `AUTO_INGRESS`, and `AUTO_ALL`. When `AUTO_API`, the system auto-selects an ExternalIPPool, creates one ExternalIP, and creates one ExternalIPAttachment with `target_endpoint: API` in Pending state. When `AUTO_INGRESS`, creates one ExternalIP + ExternalIPAttachment with `target_endpoint: INGRESS`. When `AUTO_ALL`, creates two ExternalIPs and two ExternalIPAttachments (one API, one INGRESS). ExternalIPs and ExternalIPAttachments are labeled `osac.openshift.io/auto-provisioned: "true"`. ExternalIPAttachments are created BEFORE the ClusterOrder to resolve prerequisite ordering. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 5]

#### Auto NATGateway

- **FR-6:** ClusterSpec supports a `nat_gateway_mode` field with values `NONE` (default) and `AUTO`. When `AUTO`, the system creates a NATGateway on the cluster's VirtualNetwork (reuses existing NATGateway if one already exists, regardless of state or whether it was manually or auto-created). [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 5]

#### Operator Agent Selection

- **FR-7:** osac-operator ClusterOrder controller `reconcileAgentSelection` (NEW) selects suitable agents from inventory based on node set's `host_type`, availability, and labels. Labels and reserves selected agents for this cluster. Stores selected agent references on ClusterOrder status. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 6a]

#### Operator Network Attachment Provisioning

- **FR-8:** osac-operator ClusterOrder controller `reconcileNetworking` (NEW) runs after agent selection, before provisioning. For each node set attachment, for each selected agent in that node set, dispatcher calls `osac.templates.{{ fabric_manager }}.create_network_attachment` passing `host_id`, `host_class`, `fabric_interface`, `subnet_ref`. The fabric manager adds each server's interface to the subnet's fabric segment. Network attachments must be Ready before provisioning proceeds. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 6b]

#### VIP Discovery and Feedback Loop

- **FR-9:** CaaS template provisions MetalLB LoadBalancer Services for API server + ingress VIPs, waits for MetalLB to allocate IPs from the subnet, and writes the discovered VIPs to ClusterOrder CR status: `apiEndpoint` and `ingressEndpoint`. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 7b]

- **FR-10:** osac-operator feedback controller watches ClusterOrder status. When `apiEndpoint` and `ingressEndpoint` are populated, fires Signal RPC to fulfillment-service. fulfillment-service re-reads ClusterOrder CR and syncs `api_endpoint` and `ingress_endpoint` from ClusterOrder status to the Cluster object. [Source: `.planning/caas-networking-design.md` — Phase 3: VIP Feedback Loop]

#### ExternalIPAttachment Pending to Ready Lifecycle

- **FR-11:** ExternalIPAttachment with `target: cluster` and `target_endpoint: API` or `INGRESS` is created in Pending state. After the VIP feedback loop populates Cluster's `api_endpoint` or `ingress_endpoint`, the ExternalIPAttachment controller reads the endpoint IP, calls `osac.templates.{{ fabric_manager }}.create_external_ip_attachment` with the target IP, and transitions the ExternalIPAttachment to Ready. [Source: `.planning/caas-networking-design.md` — Proposed Flow, step 10]

#### BM-only for v0.2

- **FR-12:** For v0.2, CaaS supports BM node sets only. VM-based cluster node sets are deferred (HyperShift ↔ CUDN integration not in scope). [Source: `.planning/caas-networking-design.md` — HostType and Interface Resolution]

#### Auto-Cleanup on Deletion

- **FR-13:** When a Cluster with auto-provisioned resources is deleted: if ExternalIPs/ExternalIPAttachments/NATGateway were created by the system (`external_ip_mode=AUTO_*`, `nat_gateway_mode=AUTO`, labeled `osac.openshift.io/auto-provisioned: "true"`), parent finalizer deletes ExternalIPAttachments first, then ExternalIPs, then NATGateway (if auto-created). Manually created resources are NOT cleaned up — they persist after the cluster is deleted. [Source: `.planning/caas-networking-design.md` — Deletion]

#### Step Collection Removal

- **FR-14:** CaaS template removes `osac.service.cluster_infra` and `osac.service.external_access` dispatch to `{{ network_steps_collection }}.cluster_infra` and `{{ network_steps_collection }}.external_access`. Template removes agent selection logic (moved to operator). Template keeps HyperShift HostedCluster + NodePool creation referencing pre-selected agents, MetalLB VIP provisioning, DNS cleanup, kubeconfig retrieval, wait for nodes/operators. [Source: `.planning/caas-networking-design.md` — What Changes vs. Today]

### 3.2 Non-Functional Requirements

- **NFR-1:** Auto ExternalIP allocation completes synchronously within the create API call (no async allocation delay). If no pool has available capacity, the create API call returns an error. [Source: Simplified Resource Creation PRD]

## 4. Acceptance Criteria

- [ ] A Tenant User can create a Cluster with multiple `--network-attachment` flags mapping node sets to Subnets
- [ ] A Tenant User can create a Cluster with `--external-ip=auto-all` and no explicit `network_attachments` — the cluster is created on the default subnet with two auto-provisioned ExternalIPs for API and ingress inbound access
- [ ] A Tenant User can create a Cluster with `--nat-gateway=auto` and no explicit `network_attachments` — the cluster is provisioned with a NATGateway for outbound connectivity
- [ ] A Tenant User can create a Cluster with both `--external-ip=auto-all` and `--nat-gateway=auto` — the cluster is fully connected (inbound + outbound) in a single API call
- [ ] ClusterOrder controller selects agents before provisioning, labels them, and stores references in ClusterOrder status
- [ ] ClusterOrder controller calls dispatcher `create_network_attachment` per BM node before HyperShift provisioning
- [ ] CaaS template provisions MetalLB VIPs and writes `apiEndpoint` and `ingressEndpoint` to ClusterOrder status
- [ ] Feedback controller syncs VIPs from ClusterOrder status to Cluster object
- [ ] ExternalIPAttachment controller reads Cluster `api_endpoint` / `ingress_endpoint`, creates DNAT rule, transitions from Pending to Ready
- [ ] Auto-created ExternalIPs, ExternalIPAttachments, and NATGateway are labeled `osac.openshift.io/auto-provisioned: "true"` and visible in list views
- [ ] Deleting a Cluster with auto-provisioned ExternalIPs causes the auto-created ExternalIPs and ExternalIPAttachments to be cleaned up via the parent's finalizer
- [ ] CaaS template no longer calls `osac.service.cluster_infra` or `osac.service.external_access`
- [ ] ClusterNetworkAttachment `fabric_interface` is system-populated from HostType's first `fabric` role interface

## 5. Assumptions

- The tenant has default networking resources (VirtualNetwork, Subnet, SecurityGroup) pre-created by the Tenant controller (see Simplified Resource Creation PRD). If defaults are not configured, creating a cluster without explicit `network_attachments` fails with a clear error.
- The target region's NetworkClass has `fabric_manager` configured for network attachment provisioning (switch port configuration).
- HostType resources for BM host types have `interfaces` list populated with name, role, description. VM host types have empty `interfaces` list.
- Agent inventory (Agent CRs or equivalent) is available for the operator to query and select from.

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Simplified Resource Creation PRD** — default Subnet and SecurityGroup selection behavior defined in [Simplified Resource Creation PRD](/enhancements/simplified-resource-creation)
- **Dispatcher core** — Jira OSAC-1457, OSAC-1458, OSAC-1460 (in progress)
- **Multi-job tracking** — Jira OSAC-1459 (new, required for Subnet controller to trigger both fabric_manager and k8s_manager AAP jobs)
- **NATGateway full stack** — Jira OSAC-1443 (10 tasks, 1/10 in progress)
- **ExternalIPAttachment cluster target in CRD** — Jira OSAC-2041 (new)
- **Cluster DNAT flow in controller** — Jira OSAC-1495 (new)

## 7. Risks

### 7.1 Agent selection logic implementation unclear

- **Owner:** osac-operator team
- **Mitigation:** Open question: does the operator call an AAP job for agent selection, or interact with Agent CRs directly via K8s API? Spike required to determine approach. Document decision in design phase.

### 7.2 NMState NNCP configuration ownership unclear

- **Owner:** osac-operator / osac-aap teams
- **Mitigation:** Open question: with agent selection and switch port config in the operator, does NMState config also move to the operator (as part of reconcileNetworking), or stay in the template? Spike required to determine approach.

### 7.3 MetalLB IP pool configuration ownership unclear

- **Owner:** osac-operator / osac-aap teams
- **Mitigation:** Open question: MetalLB needs an IPAddressPool CR for the subnet CIDR. Is this created at subnet creation time (by the k8s_manager), or by the CaaS template at cluster provisioning time? Document decision in design phase.

### 7.4 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

### 7.5 Auto NATGateway reuses failed or deleting NATGateway

- **Owner:** fulfillment-service / osac-operator
- **Mitigation:** Auto NATGateway reuses existing NATGateway regardless of state. If the existing NATGateway is Failed or Deleting, the cluster's outbound connectivity will not work. Document expected behavior: tenants must manually delete failed NATGateway and retry cluster creation.

## 8. Open Questions

### 8.1 How does the operator select agents?

- **Owner:** osac-operator team
- **Impact:** Affects FR-7. Current design defers implementation approach. Options: operator calls AAP job for selection, or operator queries Agent CRs directly via K8s API.

### 8.2 Who configures NMState NNCP?

- **Owner:** osac-operator / osac-aap teams
- **Impact:** Affects FR-8 and template changes. Currently done by cluster_infra. With agent selection and switch port config in the operator, does NMState config also move to the operator (as part of reconcileNetworking), or stay in the template?

### 8.3 Who creates MetalLB IPAddressPool CR?

- **Owner:** osac-operator / osac-aap teams
- **Impact:** Affects FR-9 and Subnet controller. MetalLB needs an IPAddressPool CR for the subnet CIDR so it can allocate VIPs. Is this created at subnet creation time (by the k8s_manager), or by the CaaS template at cluster provisioning time?

### 8.4 How does the operator know the fabric_manager name?

- **Owner:** osac-operator team
- **Impact:** Affects FR-8. For the dispatcher call, the operator needs the fabric_manager name to select the right AAP template. Options: read NetworkClass CR, or env var.

### 8.5 Should auto NATGateway check existing NATGateway state before reusing?

- **Owner:** API design team
- **Impact:** Affects FR-6. Current proposal reuses any existing NATGateway (simplest, avoids conflict). Alternative: only reuse if READY, otherwise create a new one (more complex, could create duplicate NATGateways during transient failures).
