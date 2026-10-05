# Testplan — OSAC-4291

## Overview

- **Feature:** CUDN EVPN K8s Manager for the fabric-backed evpn-vxlan profile
- **Design:** [design.md](design.md)
- **Authority:** Tests verify the Network Manager Integration Contract v1 and this implementation's CUDN realization.
- **Total test cases:** 9
- **Requirements covered:** registration, handoff, CUDN/NAD provisioning, connectivity, IP exclusions, retry, deletion, and diagnostics

## Test Cases

### TC-1: Register and select the manager

Use test-only registrations for candidate Netris and cudn_evpn collection versions, with both managers mutually naming each other. First run each manager's assigned-role conformance suite, then run the pair integration suite. Publish neither reciprocal peer declaration in a release registration unless all gates pass. Exercise the compatible pair, remove a required capability, remove either side's peer declaration, and pair cudn_evpn with Agentless VLAN; verify OSAC and the Enclave UI accept only the tested pair and reject each invalid pairing before creating an AAP job.

### TC-2: Validate the Fabric-to-K8s handoff

Create a Subnet with the registered compatible Fabric Manager. Verify Fabric completes first, writes the standard ConfigMap containing contract version, profile, Subnet UID/generation, L2/L3 VNIs, import/export route targets, and reserved IPv4 CIDRs, then returns the common osac_result envelope with data: {}. Verify OSAC validates the ConfigMap and passes its UID/resourceVersion-pinned reference to cudn_evpn, which reads the same object. Missing, malformed, wrong-UID, changed-resourceVersion, stale-generation, invalid-route-target, or out-of-range data must prevent K8s provisioning and leave the Subnet non-ready.

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

A passing pair test demonstrates interoperability only for the tested Netris and cudn_evpn collection versions and the evpn-vxlan profile. It does not certify either manager with an untested peer or certify the K8s-only fallback role.
