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

#### Answer

Cloud Infrastructure Admin work during initial OSAC installation.

#### Impact

PRD user stories will target Cloud Infrastructure Admin for EVPN setup/configuration workflows. Tenant-facing sections describe VirtualNetwork/Subnet provisioning with no EVPN visibility.

#### Decision (D1)

EVPN configuration is Cloud Infrastructure Admin responsibility during installation - not tenant-facing, not automatic, not per-region onboarding.

---

### R1.Q2: Tenant visibility — Is EVPN transparent to tenants?

When a Tenant User or Tenant Admin provisions a VM, do they:
- Choose EVPN vs. other networking methods explicitly (e.g., via a dropdown or flag)?
- See EVPN mentioned anywhere in the UI/CLI (e.g., "Network type: EVPN")?
- Experience EVPN as completely infrastructure-transparent (no visibility)?

#### Answer

Tenants use VirtualNetwork / Subnet. They do not choose EVPN, set VNIs or route-targets, or peer BGP. The provider picks how the hosting cluster joins the fabric.

#### Impact

PRD will not include tenant-facing EVPN configuration options. Tenant user stories focus on VirtualNetwork/Subnet provisioning. All EVPN implementation details (VNI, route targets, BGP peering) are infrastructure-side only.

#### Decision (D2)

EVPN is completely transparent to tenants. No UI/CLI exposure of EVPN-specific concepts (VNI, route targets, BGP) in tenant workflows.

---

### R1.Q3: Scope — VNI Management

The demo shows **Netris manages VPC/VNet allocations (sets VNI IDs)** and **OSAC allocates VPC/Subnet → Netris provisions VNIs → CUDN consumes them**.

For Phase 1:
- Does the PRD include **automatic VNI extraction from Netris** and propagation to CUDN?
- Or is manual VNI coordination (like the demo's Phase 4/5) acceptable for 0.3?
- Should Phase 1 include the **`0:VNI_ID` route-target standardization** the demo mentions Netris will fix?

#### Answer

Phase 1 will not include `0:VNI_ID` route-target standardization. VNI extraction happens automatically - when creating VPC on Netris, the VNI is automatically set in CUDN.

#### Impact

PRD scope includes automatic VNI propagation (no manual extraction step like demo Phase 4). Out of scope: `0:VNI_ID` route-target format (deferred until Netris implements it). Netris VPC creation must return VNI ID, which OSAC's k8s manager consumes when creating CUDN.

#### Decision (D3)

Automatic VNI extraction and propagation to CUDN is in scope for Phase 1. The `0:VNI_ID` route-target standardization is out of scope (Phase 1 uses `(leaf ASN % 65536):VNI` formula from demo).

---

### R1.Q4: Edge case — CUDN Single-Subnet Limitation

The demo states **"CUDN is limited to a single subnet per VPC ipVRF — cannot reuse a VPC and add more subnets."**

This is stricter than the Jira description's "one VM-subnet per VirtualNetwork" constraint:
- Is the constraint **one CUDN per VPC ipVRF** (demo limitation)?
- Or **one VM-hosting subnet per VirtualNetwork** (Jira wording)?
- Where is this validated? (When creating the Subnet? When creating the CUDN? When provisioning the VM?)

#### Answer

The limit is one subnet per VirtualNetwork. The validation happens when creating the subnet - a second subnet under the same VirtualNetwork won't be allowed.

#### Impact

PRD validation requirements: fulfillment-service Subnet creation API must reject a second subnet when the parent VirtualNetwork already has one subnet. Error message should reference OVN Connectors limitation. No operator-side validation needed (API rejection prevents the CR from ever being created).

#### Decision (D4)

Validation enforced at Subnet API creation time in fulfillment-service. Constraint is one subnet per VirtualNetwork (not the stricter "one CUDN per VPC ipVRF"). Second subnet creation attempt returns validation error.

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

NetworkClass ConfigMap should contain: `name: cudn_evpn` with capabilities `ipv4` or `dualstack` (same structure as other k8s managers, no additional EVPN-specific fields).

#### Impact

PRD documents NetworkClass ConfigMap schema matching existing pattern from OSAC-1433 unified networking. No EVPN-specific ConfigMap fields beyond standard name and capabilities.

---

### R2.Q5: Route Target Calculation

The demo uses formula `(leaf ASN % 65536):VNI` to calculate route targets.

For Phase 1:
- Does the k8s manager **calculate** route targets using this formula?
- Or does Netris **return** the route target when creating VPC/VNet?

#### Answer

Route target is automatically set during CUDN creation. The route target is not known until Netris creates the VPC and subnet. The k8s manager then uses that route target when creating the CUDN. No manual configuration by users.

#### Impact

PRD workflow: Netris VPC/VNet creation returns route target values → k8s manager uses those values in FRRConfiguration when creating CUDN. No route-target calculation logic in k8s manager. Netris is source of truth for route targets.

#### Decision (D7)

Route targets come from Netris (returned during VPC/VNet creation). K8s manager uses Netris-provided route target values when creating CUDN - no client-side calculation.

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
1. **Netris creates VPC and subnet first** (allocates VNIs and route targets)
2. **Only after that, CUDN is created** (reuses Netris VNIs and route-targets)
3. **When CUDN is set up, EVPN routes are updated**

### Subnet Flexibility (from Round 3 discussion)

- CUDN can reuse existing VPC and VNet from Netris if we get the VNI for Layer 2, Layer 3, and route-targets
- The subnet can be the same as Netris or different
- In case of different subnets (OCP CUDN subnet vs. Netris VNet subnet), Layer 3 VNI (ipVRF) is used for routing between them

---

## Locked Decisions Summary

- **D1:** EVPN configuration is Cloud Infrastructure Admin responsibility during installation
- **D2:** EVPN is completely transparent to tenants
- **D3:** Automatic VNI extraction and propagation to CUDN is in scope; `0:VNI_ID` route-target format is out of scope
- **D4:** One-subnet-per-VirtualNetwork validation enforced at Subnet API creation time in fulfillment-service
- **D5:** FRRConfiguration for EVPN overlay is automatic; BGP underlay peering is manual prerequisite
- **D6:** Underlay configuration is documented prerequisite, not automated
- **D7:** Route targets come from Netris (no client-side calculation)
- **D8:** Integration test is automated in CI with real Netris fabric
- **D9:** MetalLB IPAddressPool creation is out of scope
- **D10:** Design extends OSAC-1433, not a new document
