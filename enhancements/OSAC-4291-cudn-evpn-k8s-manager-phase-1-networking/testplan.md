# Testplan — OSAC-4291

## Overview

- **Feature:** CUDN EVPN K8s Manager for the fabric-backed evpn-vxlan profile
- **Design:** [design.md](design.md)
- **Authority:** Tests verify the Network Manager Integration Contract v1 and this implementation's CUDN realization.
- **Total test cases:** 9
- **Requirements covered:** registration, handoff, CUDN/NAD provisioning, connectivity, IP exclusions, retry, deletion, and diagnostics

## Test Cases

### TC-1: Register and select the manager

Register cudn_evpn with the K8s Manager label, implementationRef osac.templates.cudn_evpn, contractVersion v1, and ipv4,evpn-vxlan capabilities. Verify the manager is discoverable. Remove either required capability and verify OSAC rejects the registration/profile before creating an AAP job.

### TC-2: Validate the Fabric-to-K8s handoff

Create a Subnet with an evpn-vxlan Fabric Manager. Verify Fabric completes first and returns osac_result with the correct operation, Subnet UID, generation, and data.fabricHandoff. Verify OSAC persists the validated result and passes it unchanged as context.fabricHandoff to cudn_evpn.subnet.create. Missing, malformed, wrong-UID, wrong-generation, or out-of-range data must prevent K8s dispatch and leave the Subnet non-ready.

### TC-3: Provision one CUDN/NAD for every Subnet

Create two Subnets under one VirtualNetwork, then repeat in reverse order. Verify each Subnet UID owns one namespace, secondary CUDN, and NAD; each CUDN uses the matching handoff and Subnet CIDR. Verify VMaaS selects the NAD by the requested Subnet reference.

### TC-4: Verify same-Subnet and cross-Subnet connectivity

Attach two VMs to one Subnet under different SecurityGroups, attach multiple groups to one VM, and attach a fabric-connected bare-metal endpoint with explicit SecurityGroup rules. Verify L2 connectivity only for the effective union of each endpoint's own groups and deny unmatched flows. Attach endpoints to different Subnets in the same VirtualNetwork with explicit allow rules and verify connectivity through the physical fabric's L3 routing domain; verify established return traffic and deny a flow with no matching rule. The selected Fabric Manager enforces SecurityGroup behavior for the ComputeInstance target, including group binding add/remove and rule updates. The result must be the same regardless of Subnet creation order.

### TC-5: Preserve reserved fabric addresses

Return one or more reservedIPv4CIDRs in the Fabric handoff. Verify the CUDN excludes every supplied range from OVN address assignment. Reject a reserved range outside the Subnet CIDR.

### TC-6: Retry after partial provisioning

Interrupt creation after namespace creation and before CUDN/NAD completion. Retry the same Subnet UID and generation. Verify reconciliation completes without duplicate objects and returns a valid K8s osac_result.

### TC-7: Reject invalid K8s results

Return a missing, malformed, stale-generation, wrong-operation, or wrong-UID osac_result from the K8s task. Verify OSAC does not mark the Subnet Ready and reports a diagnostic that identifies the invalid result field.

### TC-8: Delete one Subnet without affecting its sibling

Create two Ready Subnets with VMs attached. Remove the VM from one Subnet and delete that Subnet. Verify subnet.delete removes only resources owned by its UID, reports success after those resources are absent, and OSAC starts Fabric cleanup afterward. Verify the sibling CUDN, NAD, namespace, and VM remain ready.

### TC-9: Verify infrastructure and troubleshooting prerequisites

With VTEP, FRR, or BGP underlay unavailable, attempt provisioning. Verify the CUDN does not become Ready, the Subnet remains non-ready with a useful diagnostic, and support procedures identify the failed prerequisite. Restore the prerequisite and verify retry succeeds.

## Gaps

A passing test run demonstrates this implementation's conformance only for the evpn-vxlan K8s Manager role. It does not certify the Fabric Manager or the K8s-only fallback role.
