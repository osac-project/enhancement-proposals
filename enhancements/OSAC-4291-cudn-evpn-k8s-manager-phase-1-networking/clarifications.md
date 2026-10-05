# Clarification Log — OSAC-4291

## Status

- Rounds completed: 3
- Open gaps: None
- Exit criteria met: Yes

## Round 1 — User Personas and Visibility

### R1.Q1: Personas — Who configures EVPN?

The feature describes k8s manager registration, CUDN creation, and BGP peering setup. Which OSAC persona(s) are responsible for enabling EVPN for a deployment/region? Is this:
- Cloud Infrastructure Admin work during initial OSAC installation?
- Cloud Provider Admin work when onboarding a new region?
- Automatically enabled based on infrastructure detection?

#### Earlier Answer (superseded)

The initial demo-based interpretation limited this implementation to one Subnet per VirtualNetwork. That restriction is not part of the current contract-aligned design.

#### Current Impact

The target creates one CUDN/NAD per OSAC Subnet. Multiple Subnets under one VirtualNetwork are supported, and Subnet creation must not reject a second Subnet because of the selected K8s Manager. The legacy single-CUDN implementation requires an explicit migration to the UID-owned per-Subnet model.

#### Current Decision (D4)

`cudn_evpn` provisions one CUDN/NAD per Subnet and supports multiple Subnets per VirtualNetwork. There is no one-Subnet-per-VirtualNetwork validation.
---

### R1.Q5: Scope — IPAM and Gateway Management

The demo shows **OCP CUDN runs IPAM** (not Netris DHCP) and **gateway IP collision requires same MAC address on both sides**.

For Phase 1:
- Is **dual gateway MAC coordination** in scope (OCP CUDN gateway + Netris VNet gateway must match)?
- Or is this a **known limitation** to document (out of scope for automatic handling)?
- Does Phase 1 handle **DHCP range coordination** to avoid IP collisions?

#### Answer

Dual gateway MAC coordination is a known limitation (out of scope for automatic handling). Phase 1 handles DHCP range coordination to avoid IP collisions.

#### Impact

PRD Known Limitations section documents dual gateway MAC requirement (manual coordination needed). PRD scope includes DHCP range coordination mechanism - k8s manager must configure OCP CUDN IPAM to avoid overlap with Netris DHCP ranges.

---

## Round 2 — BGP Configuration and Automation

### R2.Q1: BGP Configuration Automation

The demo shows **manual FRRConfiguration CRD creation** (40+ lines of YAML with ASN, router ID, neighbor config, route targets).

For Phase 1:
- Does the k8s manager **automatically create** the FRRConfiguration CRD when a subnet is created?
- Or does the Cloud Infrastructure Admin **manually create** it during installation (one-time setup)?
- If automatic: what parameters come from Netris vs. NetworkClass configuration?

#### Answer

When CUDN is created, FRRConfiguration is created for the VirtualNetwork and Subnet. But the Cloud Infrastructure Admin should create the BGP session with Netris (underlay peering is manual prerequisite).

The required BGP configuration fields are:
- BGP local AS
- BGP remote AS (from Netris)
- BGP peer address (from same subnet as physical interface IP)
- BGP peer local interface address (peering with Netris IP)

#### Impact

PRD scope: k8s manager automatically creates FRRConfiguration for EVPN overlay when CUDN is created (VNI-specific route targets, L2VPN EVPN config). Out of scope: BGP underlay session setup (manual prerequisite). Prerequisites section documents what Cloud Infrastructure Admin must configure before creating first VirtualNetwork.

#### Decision (D5)

FRRConfiguration for EVPN overlay (VNI, route targets) is automatic. BGP underlay peering (physical link, neighbor session) is a manual prerequisite configured by Cloud Infrastructure Admin.

---

### R2.Q2: VTEP Configuration Automation

The demo shows **manual VTEP setup** (VTEP CRD + NMState dummy interface with `10.200.255.1/32`).

For Phase 1:
- Does the k8s manager **automatically provision** the VTEP interface on each hosting cluster node?
- Or is VTEP setup a **prerequisite** (Cloud Infrastructure Admin does it once before enabling EVPN)?
- If automatic: where does the VTEP IP range come from?

#### Answer

VTEP address should be predefined once per node by infrastructure (same as BGP configuration with Netris as underlay). This is a prerequisite setup, not automatic provisioning.

#### Impact

PRD Prerequisites section documents VTEP setup (VTEP CRD + NMState NNCP per node with dummy interface and /32 IP). VTEP configuration is one-time infrastructure setup, not per-VirtualNetwork automation.

---

### R2.Q3: NMState Underlay Configuration

The demo shows **manual underlay link setup** (Netris API + NMState NNCP for physical interface IP).

For Phase 1:
- Is underlay link configuration a **prerequisite** documented in installation docs?
- Or does Phase 1 include **automation** for underlay provisioning?

#### Answer

Installation prerequisites must be documented in the PRD. Before creating CUDN, the worker must join the fabric and establish BGP. This means: the port connected to the worker is set in Netris as underlay, which configures BGP on the Netris side.

#### Impact

PRD includes "Installation Prerequisites" section documenting the infrastructure setup workflow:
1. Configure underlay link in Netris (port → underlay mode)
2. Configure physical interface IP via NMState
3. Set up VTEP interface per node
4. Verify BGP session established

All steps are manual Cloud Infrastructure Admin work, prerequisite to creating first VirtualNetwork.

#### Decision (D6)

Underlay configuration (physical link, Netris port setup, BGP session) is a documented prerequisite, not automated by Phase 1. PRD includes detailed Prerequisites section.

---

### R2.Q4: NetworkClass ConfigMap Schema

The Jira mentions "k8s manager registration via ConfigMap with declared capabilities."

What exact fields are in the ConfigMap?

#### Answer

The K8s Manager registration contains the common contract fields and `compatibleFabricManagers` list in addition to its capabilities. CUDN EVPN declares only Fabric Manager names that have passed pair integration testing. IPv6 and dual-stack networking are not supported.

#### Impact

PRD and design reference the Network Manager Integration Contract for the exact registration schema, including the compatibility peer list. Fabric/K8s pair selection is mutual and pair-tested; the implementation design does not duplicate the registration schema.

---

### R2.Q5: Route Target Calculation

The demo uses formula `(leaf ASN % 65536):VNI` to calculate route targets.

For Phase 1:
- Does the k8s manager **calculate** route targets using this formula?
- Or does Netris **return** the route target when creating VPC/VNet?

#### Answer

The Fabric Manager allocates or selects the actual route targets while it creates the physical Subnet and writes them into the shared contract ConfigMap. The K8s Manager reads and applies those values when it creates the CUDN; it does not calculate or substitute them. This generalizes the original Netris-specific assumption to any Fabric Manager that passes pair testing.

#### Impact

Contract workflow: the selected Fabric Manager writes its actual L2/L3 import/export route-target values to the standard Subnet handoff ConfigMap; the K8s Manager reads and applies those values when creating CUDN/FRRConfiguration. The K8s Manager does not calculate or substitute route targets. Pair integration tests validate the values and resulting connectivity for each declared Fabric/K8s pair.

#### Decision (D7)

Route targets come from the selected Fabric Manager through the standard ConfigMap; the K8s Manager applies them without client-side calculation. The original Netris-only wording is superseded by the source-neutral manager contract.

---

## Round 3 — Testing, Observability, and Design Context

### R3.Q1: Integration Test Scope

The Jira Definition of Done mentions "Integration test covering subnet creation → CUDN + EVPN → VM placement → fabric reachability."

For Phase 1:
- What test infrastructure is required? (Real Netris fabric? Simulated? Kind cluster?)
- What does "fabric reachability" verification mean specifically?
- Does the test run in CI, or is it a manual verification step?

#### Answer

Phase 1 requires a real Netris fabric (not simulated). Fabric reachability means ping from worker's IP (BGP source) to Netris switch port, and verify BGP session is up.

Integration test runs automatically in CI. Setup requires creating BGP configuration and configuring the worker OCP as underlay peer to Netris. VM-to-bare-metal connectivity is checked only after CUDN is created, VM booted up, and bare-metal configured on Netris with same VPC subnet.

#### Impact

PRD Test Plan section documents CI integration test requirements:
- Real Netris fabric infrastructure (not mocked)
- Automated setup: BGP underlay peering between OCP worker and Netris ns-leaf
- Test phases: 1) Verify BGP session up (ping worker to switch), 2) Create VirtualNetwork/Subnet via OSAC API, 3) Verify CUDN creation with correct VNI/route-targets, 4) Deploy VM, 5) Provision bare-metal node on Netris in same VPC subnet, 6) Verify VM-to-bare-metal connectivity

#### Decision (D8)

Integration test is automated in CI, requires real Netris fabric, and validates full path from subnet creation through VM-to-bare-metal connectivity.

---

### R3.Q2: EVPN Failure Modes and Observability

If BGP peering fails or EVPN routes aren't advertised properly:
- What does the user observe?
- What diagnostic tools does the Cloud Infrastructure Admin have?
- Are there automated health checks before marking Subnet as "Ready"?

#### Answer

In case BGP peering is up but there is a mismatch in VNI or route-target between VMs and Netris bare-metal, the user won't have traffic/ping to remote nodes in the same VPC. VM provisions successfully but connectivity fails (silent failure).

Cloud Infrastructure Admin can verify VNI created properly by running FRR commands:
- `show evpn vni`
- `show bgp l2vpn evpn`
- `show bgp vni <VNI ID>`
- `show bgp l2vpn evpn summary`

#### Impact

PRD Known Limitations section documents failure mode: VNI/route-target mismatch results in silent connectivity failure (VM provisions but can't reach fabric). No automated health checks in Phase 1 - verification is manual via FRR commands. PRD Troubleshooting section documents diagnostic commands for Cloud Infrastructure Admin.

---

### R3.Q3: MetalLB IPAddressPool Creation

The Jira Definition of Done mentions "MetalLB IPAddressPool created at subnet creation (for CaaS VIP allocation)."

Is this in scope for Phase 1?

#### Answer

MetalLB IPAddressPool is out of scope for Phase 1.

#### Impact

PRD Out of Scope section explicitly lists MetalLB IPAddressPool creation. This is handled separately in OSAC-1436 (CaaS Networking).

#### Decision (D9)

MetalLB IPAddressPool creation is out of scope for Phase 1 (deferred to OSAC-1436 CaaS Networking).

---

### R3.Q4: Relationship to OSAC-1433 Design

Does this feature extend the existing OSAC-1433 design document, or create a new design document?

#### Answer

This extends the existing OSAC-1433 design document.

#### Impact

Design phase will add an "OVN EVPN k8s Manager" section to the existing OSAC-1433 unified networking design document, not create a standalone design.

#### Decision (D10)

Design extends OSAC-1433 (unified networking architecture) - not a new standalone document.

---

## Additional Context Captured

### Installation Prerequisites (from R2.Q3 and Round 3 discussion)

Cloud Infrastructure Admin must complete these steps before creating the first VirtualNetwork:

1. **Configure VTEP on all OCP nodes** (VTEP CRD + NMState NNCP per node with dummy interface and /32 IP)
2. **Configure address on physical interface on worker** (will be BGP peer)
3. **Ensure worker interface has connectivity to fabric switch**
4. **Configure underlay link in Netris** (set port to underlay mode)
5. **Create BGP peer between worker and ns-leaf** (FRRConfiguration with local AS, remote AS from Netris, peer addresses)
6. **Verify BGP session established** (Netris adds OCP worker as underlay, worker configures BGP and enables EVPN)

### CUDN Creation Workflow (from Round 3 discussion)

When tenant creates VirtualNetwork/Subnet:
1. **The selected Fabric Manager creates the physical Subnet first** and writes its VNIs, route targets, and reserved IPv4 ranges to the shared contract ConfigMap.
2. **Only after OSAC validates that ConfigMap does the K8s Manager create the CUDN**, reusing the exact VNI and route-target values.
3. **When CUDN is set up, EVPN routes are updated.**

### Subnet Flexibility (from Round 3 discussion)

- CUDN can reuse the physical routing domain and segment when the selected Fabric Manager publishes the L2/L3 VNIs and import/export route targets required by the standard handoff schema
- The subnet can be the same as Netris or different
- In case of different subnets (OCP CUDN subnet vs. Netris VNet subnet), Layer 3 VNI (ipVRF) is used for routing between them

---

## Locked Decisions Summary

- **D1:** EVPN configuration is Cloud Infrastructure Admin responsibility during installation
- **D2:** EVPN is completely transparent to tenants
- **D3:** Automatic VNI and assigned route-target propagation from Fabric to K8s through the standard contract ConfigMap is in scope; route-target calculation/derivation conventions (including `0:VNI_ID`) are out of scope
- **D4:** One CUDN/NAD per Subnet; multiple Subnets per VirtualNetwork are supported. This supersedes the initial single-Subnet interpretation.
- **D5:** FRRConfiguration for EVPN overlay is automatic; BGP underlay peering is manual prerequisite
- **D6:** Underlay configuration is documented prerequisite, not automated
- **D7:** Route targets come from the selected Fabric Manager through the contract ConfigMap (no K8s-side calculation). The earlier Netris-only source is superseded by the user's source-neutral manager requirement.
- **D8:** Integration test is automated in CI with real Netris fabric and the pinned `cudn_evpn` collection, including validation of the standard handoff ConfigMap and end-to-end reachability
- **D9:** MetalLB IPAddressPool creation is out of scope
- **D10:** Design extends OSAC-1433, not a new document
- **D11:** For Fabric-backed EVPN, Fabric writes the shared, contract-defined VNI/route-target/reserved-CIDR ConfigMap; OSAC validates and pins it; K8s consumes it. Supplier-specific handoff objects are not used. [User, 2026-10-05]
- **D12:** A Fabric/K8s pair is eligible only when both registrations mutually declare compatibility and the pair's supported collection versions pass integration testing. Capabilities alone do not establish compatibility. [User, 2026-10-05]
