# Test Plan: CUDN EVPN Kubernetes Manager

## Overview

- Feature: [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291); manager implementation [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761).
- 34 active planned cases; 13 of 13 named PRD outcome groups mapped below.
- Scope and interface definitions: [PRD](prd.md), [design](design.md#interface-changes), IC-1 through IC-6.
- Story/Task entries identify existing owning work; AC entries below cite named PRD outcomes, not invented Jira AC numbers. Child-task/Jira-AC mapping must be finalized during decomposition. No decomposition or sync manifest exists and no assignments are claimed.
- Cases describe planned coverage, not executed results. The strict backend deletion proof remains an explicit implementation blocker.

## Fixtures and Entry Points

Common saved fixture: tenant-a, VN vn-a (11111111-1111-4111-8111-111111111111), owner Subnet subnet-a (22222222-2222-4222-8222-222222222222), group web (33333333-3333-4333-8333-333333333333), L2=10100, parent L3=20001. IPAM is the design's 192.0.2.0/24 example; use fresh IDs for independent cases and retain separate live controls for deletion. Task-execution cases supply the applicable task envelope from the eight-task interface, capture that task's osac_result/osac_error and API mutation trace, and snapshot existing objects before mutations. E2E cases drive normal OSAC API/workload flows and collect resource/job status, guest DHCP/address data, route observations and permitted/denied packet results; they do not directly invoke every task. Manual documentation cases retain reviewed document/source references and finding notes, with no required task envelope, job artifacts or mutation trace. Malformed data tests change one field at a time. Unsupported inputs expect retryable:false; missing prerequisites/conflicts expect retryable:true; tasks without a typed result emit no osac_result. No secrets appear in artifacts.

| Tier / owner | Existing pattern and planned entry point | Real / faked boundary |
|---|---|---|
| Unit / DEV | osac-aap/tests/unit/test_cudn_evpn_role.py: `_render_cudn`, `_run_role_with_inputs`, test_cudn_template_separates_infrastructure_ips_from_netris_dhcp_range; deletion-order file test_cudn_evpn_delete_order.py. `uv run pytest tests/unit/test_cudn_evpn_role.py tests/unit/test_cudn_evpn_delete_order.py` from osac-aap | Real Python/Jinja/Ansible transformations; APIs and packets omitted |
| Component integration / DEV | Planned osac-aap/tests/integration/targets/cudn_evpn/tasks/baseline.yml plus separate race plays, following targets/metallb_l2_detach_annotation/tasks/baseline.yml's independent-process API-conflict pattern. Register in run_tests.sh. `make -C osac-aap test` from OSAC root; focused `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml` from the prepared integration directory | Real Ansible and Kind API; installed CUDN schema/prerequisites explicitly fixture-driven, no OVN/FRR/KubeVirt/Fabric packets or deployed AAP |
| Core/installer integration / DEV | Owning existing suites under OSAC-6766/6769; typed-output and preflight fixtures must capture actual job input/status. Installer host schema/render validation includes planned `make -C osac-installer evpn-render-test` dependency from osac #1993 | Real declared API/render boundary; fake jobs never establish packet behavior |
| E2E / QE | Planned tests/e2e/vmaas/regression/test_cudn_evpn_networking.py, patterned on sanity/test_virtual_network_lifecycle.py, sanity/test_subnet_lifecycle.py and regression/test_networking_api_contract.py. Existing root conftest.py fixtures `grpc`, `k8s_hub_client` and vmaas/conftest.py fixtures `k8s_virt_client`, `vm_template`; core/helpers.py `wait_for_subnet_ready`, `wait_for_vmi_ip`; core/runner.py `poll_until`. `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py` from OSAC root once implemented | Full deployed core/operator/AAP, OVN/FRR/KubeVirt and real selected Fabric. Record all versions and omitted dependencies |
| Documentation / DEV | Review installed-prerequisite and tenant error guidance against the complete design examples | No runtime execution |

The dedicated CUDN target and deployed file are required implementation deliverables, not existing passing tests. An unrelated passing suite cannot satisfy them. The common Fabric conformance runner is separate shared-core work; its existing shared IDs below are always qualified as Shared.

### Execution and Work-Item Evidence

Each case below includes its own command, working directory, environment, execution status and real/faked/omitted dependency record. "Verified entry point" means the command/target and named pattern were inspected in the source, not executed. Proposed CUDN targets/files must be implemented before the command covers this case. Per-case Preconditions add to, rather than replace, the listed environment. Planned automated coverage is never a passing execution result.

| Work | Tracking and mapping state |
|---|---|
| Manager DEV | [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761); maps the manager cases below |
| Core DEV | Owning epic [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766); this plan maps no individual child Task or assignee |
| Installation DEV | [OSAC-6769](https://redhat.atlassian.net/browse/OSAC-6769); host-render delivery additionally depends on [osac #1993](https://github.com/osac-project/osac/pull/1993) |
| Deployed QE | No QE ticket is mapped or created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291). A concrete QE Task must be selected during decomposition before execution ownership is accepted |

Jira inventory could not be queried because the Jira CLI is unavailable. These are explicit mapping gaps, not a claim that no suitable issue exists in Jira. No assignee or Jira AC number is fabricated. AC-source cells trace to the named PRD outcome groups; final Task/AC links are required during decomposition.

## Requirements and Interface Coverage

| PRD outcome group | Cases | Design interface |
|---|---|---|
| Installation and diagnostics | TC-R1-01, TC-R7-01, TC-SETTINGS-01, TC-R8-01 | IC-1 |
| VN L3/Subnet L2 typed handoff | TC-R2-01, TC-R2-02, TC-INPUT-01, TC-INPUT-02 | IC-2, IC-3 |
| Primary CUDN realization | TC-R3-01 | IC-3 |
| Matching route targets and pair qualification | TC-RT-01, TC-RT-02, TC-PAIR-01 | IC-3 |
| Owner-Subnet limit and conflict safety | TC-R5-04 through TC-R5-07 | IC-4, IC-6 |
| Disjoint pools, gateway and DNS | TC-IPAM-01, TC-R6-01, TC-R4-02, TC-SETTINGS-01 | IC-3 |
| VM/physical L2 and same-VN routed connectivity | TC-R4-01, TC-R4-02, TC-PAIR-01 | IC-3, IC-6 |
| Baseline/exact policy and explicit unsupported ICMP | TC-POLICY-01 through TC-POLICY-05 | IC-5, IC-6 |
| VN/Subnet API and state preservation | TC-COMPAT-01, TC-COMPAT-02 | IC-2, IC-3, IC-4, IC-6 |
| Fresh-only activation and legacy refusal | TC-COMPAT-03 | IC-1, IC-2 |
| Namespace-before-VM and persistent addressing | TC-ATTACH-01, TC-ATTACH-02 | IC-6 |
| Retry, cancellation and owned cleanup | TC-RETRY-01, TC-ATTACH-03, TC-DELETE-01, TC-CUDN-DELETE-02, TC-R5-07 | IC-2, IC-4 |
| Administrator guidance and failure classification | TC-R7-01, TC-R8-01 | IC-1 |

## Test Cases

### Planned Manager Cases

#### TC-COMPAT-01: Preserve the VirtualNetwork and Subnet API contract

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) (owning epic; no child Task/assignee mapped in this plan) | PRD outcome: VN/Subnet API and state preservation | critical | automated | IC-2, IC-3 |

- **Tier / owner:** Core component integration / owning DEV OSAC-6766. **IC:** IC-2, IC-3. **Boundary:** real fulfillment API/persistence and CR projection; manager completion is an explicit fixture, with no Fabric packet path.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing suite `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; this case needs an added/extended test |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Installed Kind dev profile, PostgreSQL/Keycloak/API access, the suite's operator-enabled NetworkClass phases where applicable, and controlled manager completion fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/persistence, Kind CR projection and selected controller phase; faked: Fabric/AAP completions and backend realization; omitted: OVN/FRR/KubeVirt/Fabric packet enforcement |
| Existing source pattern | osac-installer/Makefile test SUITE=fulfillment; fulfillment-service/it; tests/e2e/vmaas/regression/test_networking_api_contract.py for request-shape controls |

##### Preconditions

Existing the manager integration contract VN/Subnet client fixtures, tenant defaults and saved IDs/specs/parent references, recorded managers, IPAM and accepted segments.

##### Steps

1. Run the unchanged Create/Get/List client fixtures with explicit references and tenant-default resolution.
2. For existing fixtures under the amended lifecycle, compare immutable state before and after namespace/group preparation and reconciliation.
3. Exercise Delete on a separate unreferenced fixture and rejection on a referenced fixture.

##### Expected Results

Existing requests need no new namespace/policy field or tenant Update. IDs, names, tenant/parent references, immutable specs, manager identities, CIDRs, gateway, pools and VNIs are retained; internal progress does not allocate again or replace records/CRs. Existing readiness and dependency guards still apply to create/delete.

#### TC-COMPAT-02: Reuse compatible network objects on supported retries

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: VN/Subnet API and state preservation | critical | automated | IC-2, IC-3, IC-4, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761 with core lifecycle DEV. **IC:** IC-2, IC-3, IC-4, IC-6. **Boundary:** real Kind objects and independent Ansible invocations; OVN/Fabric traffic is omitted.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

A compatible recorded VN/owner-Subnet realization from fresh activation of the amended lifecycle, namespace and CUDN, sibling Subnet, group policy and attachment fixtures; snapshot all names, UIDs, owner identities, selectors, accepted segment and IPAM.

##### Steps

1. Retry VN/Subnet create and group/binding preparation, inject a response loss/conflict, then restart and reconcile from persisted state.

##### Expected Results

Namespace and CUDN retain names and UIDs; VN/Subnet specs, owner, recorded pools/VNIs and attachment namespace remain identical. No second namespace/network, deletion/recreation, reallocation, sibling takeover or VM operation occurs. Policy tasks change only their owned policy/binding state according to selected rules.

#### TC-COMPAT-03: Refuse live legacy activation before mutation

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) (owning epic; no child Task/assignee mapped in this plan) | PRD outcome: Fresh-only activation and legacy refusal | critical | automated | IC-1, IC-2, IC-3, IC-4, IC-6 |

- **Tier / owner:** Core/installer component integration / owning DEV OSAC-6766/6769 with manager DEV. **IC:** IC-1, IC-2, IC-3, IC-4, IC-6. **Boundary:** real activation preflight and Kubernetes inventory; legacy CUDN/VM objects are explicit fixtures and do not prove packet continuity.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing suite `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; this case needs an added/extended test |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Installed Kind dev profile, PostgreSQL/Keycloak/API access, the suite's operator-enabled NetworkClass phases where applicable, and controlled manager completion fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/persistence, Kind CR projection and selected controller phase; faked: Fabric/AAP completions and backend realization; omitted: OVN/FRR/KubeVirt/Fabric packet enforcement |
| Existing source pattern | osac-installer/Makefile test SUITE=fulfillment; fulfillment-service/it; tests/e2e/vmaas/regression/test_networking_api_contract.py for request-shape controls |

##### Preconditions

Live legacy VN/Subnet records, a Subnet-named namespace, VN-named CUDN, existing selectors/ownership/RTs/IPAM and workload fixtures; capture configuration, API state and object UIDs/specs. Include an RT mismatch and ambiguous legacy ownership.

##### Steps

1. Attempt to activate the new namespace/policy lifecycle over that inventory.

##### Expected Results

Preflight rejects activation with the unsupported legacy-state reason before changing configuration, resetting readiness or dispatching provisioning/cleanup. Records, CRs, UIDs, allocations, selectors, RTs and workload placement remain identical. No `ce-<VN UUID>` replacement namespace, ownership transfer, baseline-deny policy or network deletion is issued. This is rejection coverage, not an in-place migration claim.

#### TC-R1-01: Resolve the installed compatible manager

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) (owning epic; no child Task/assignee mapped in this plan) | PRD outcome: Installation and diagnostics | high | automated | IC-1 |

- **Tier / owner:** Core/installer component integration / owning DEV. **IC:** IC-1. **Boundary:** real registration/controller API with declared installer rendering; no Fabric traffic.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing suite `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; this case needs an added/extended test |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Installed Kind dev profile, PostgreSQL/Keycloak/API access, the suite's operator-enabled NetworkClass phases where applicable, and controlled manager completion fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/persistence, Kind CR projection and selected controller phase; faked: Fabric/AAP completions and backend realization; omitted: OVN/FRR/KubeVirt/Fabric packet enforcement |
| Existing source pattern | osac-installer/Makefile test SUITE=fulfillment; fulfillment-service/it; tests/e2e/vmaas/regression/test_networking_api_contract.py for request-shape controls |

##### Preconditions

Installed registration fixtures, networking readiness controller and exact the manager integration contract registration schema.

##### Steps

1. Install the immutable `cudn_evpn` registration with its `ansible_role` and `network_type: evpn`; select a compatible Fabric registration.
2. Repeat with missing role/type, mutable or duplicate registration and incompatible type.

##### Expected Results

Valid selection records the OSAC role/type. Invalid selection fails with an actionable readiness diagnostic before manager tasks; it never falls back to another manager. No runtime connectivity claim follows from registration success.

#### TC-R2-01: Pass only the accepted typed segment to Kubernetes

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) (owning epic; no child Task/assignee mapped in this plan) | PRD outcome: VN L3/Subnet L2 typed handoff | critical | automated | IC-2, IC-3 |

- **Tier / owner:** Core component integration / owning DEV. **IC:** IC-2, IC-3. **Boundary:** controller/job and stored status; Fabric/AAP execution may be fixture-driven.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing suite `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; this case needs an added/extended test |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Installed Kind dev profile, PostgreSQL/Keycloak/API access, the suite's operator-enabled NetworkClass phases where applicable, and controlled manager completion fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/persistence, Kind CR projection and selected controller phase; faked: Fabric/AAP completions and backend realization; omitted: OVN/FRR/KubeVirt/Fabric packet enforcement |
| Existing source pattern | osac-installer/Makefile test SUITE=fulfillment; fulfillment-service/it; tests/e2e/vmaas/regression/test_networking_api_contract.py for request-shape controls |

##### Preconditions

VN vn-a, Subnet subnet-a, saved /24 IPAM and controlled Fabric completions; parent result `l3_vni: 20001` and Subnet result `{type: evpn, l2_vni: 10100}`.

##### Steps

1. Complete Fabric VN create and inspect private `VirtualNetwork.status.l3Vni`.
2. Start each manager Subnet task and inspect `l3_vni: 20001`.
3. Complete Fabric Subnet create with the two-key segment.
4. Inspect saved status and Kubernetes input; repeat create/delete with the saved values.

##### Expected Results

VN L3 acceptance precedes Subnet dispatch. Both Subnet tasks receive integer 20001; Kubernetes receives exactly `{type: evpn, l2_vni: 10100}` plus the separate parent L3 value. Saved allocations do not change on retries; no manager-specific free-form transfer or tenant VNI field appears.

#### TC-R2-02: Reject invalid or changed Fabric segments before launch

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) (owning epic; no child Task/assignee mapped in this plan) | PRD outcome: VN L3/Subnet L2 typed handoff | critical | automated | IC-2, IC-3 |

- **Tier / owner:** Core contract/integration / owning DEV. **IC:** IC-2, IC-3. **Boundary:** real typed-output/status acceptance; Fabric output is a fixture.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing suite `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; this case needs an added/extended test |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Installed Kind dev profile, PostgreSQL/Keycloak/API access, the suite's operator-enabled NetworkClass phases where applicable, and controlled manager completion fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/persistence, Kind CR projection and selected controller phase; faked: Fabric/AAP completions and backend realization; omitted: OVN/FRR/KubeVirt/Fabric packet enforcement |
| Existing source pattern | osac-installer/Makefile test SUITE=fulfillment; fulfillment-service/it; tests/e2e/vmaas/regression/test_networking_api_contract.py for request-shape controls |

##### Preconditions

The valid VN/Subnet results and input fixture from TC-R2-01, with configurable ASN and VNI values.

##### Steps

1. Test missing/extra fields, string VNIs, 0, 16777216, changed retry values and L2/L3 collisions.
2. Reject a Subnet result containing `l3_vni`. Accept valid bounds 1 and 16777215 for each L2/L3 field with the other VNI distinct, using fresh IDs per allocation.
3. For L2 with fixed distinct parent L3=20001, exercise ASN/VNI pairs (65536,65535), (65535,65536), (65536,65536), and (4209999999,16777215).

##### Expected Results

Malformed/out-of-range/colliding/changed outputs are rejected before Kubernetes launch and saved values remain. All four valid ASN/VNI pairs are accepted: no ASN-based 16-bit restriction remains. The tenant error identifies the broken rule without exposing other resource IDs/VNIs.

#### TC-INPUT-01: Exercise all eight entry points and exact outputs

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: VN L3/Subnet L2 typed handoff | high | automated | IC-2 |

- **Tier / owner:** Contract / DEV OSAC-6761. **IC:** IC-2. **Boundary:** fresh Ansible invocation and captured set_stats; Kubernetes backend is a declared fixture here.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Exact minimal snapshot fixtures for all four task pairs, without tenant annotations or arbitrary full CR fields.

##### Steps

1. Invoke each task with one `osac_job_vars`; capture artifacts and process outcome.
2. Run VN namespace create/delete and non-owner Subnet no-ops as well as overlay apply.

##### Expected Results

All required files exist. No-output success publishes no `osac_result`; apply publishes exactly `{vm_attachment: {namespace}}`. No version/profile/identity wrapper or secret enters artifacts. State changes use top-level API IDs and explicit tenant. Proposed VN tasks create/safely remove their shared namespace without typed output; they are no longer documented no-ops.

#### TC-INPUT-02: Reject invalid identities and sanitize failures

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: VN L3/Subnet L2 typed handoff | high | automated | IC-2 |

- **Tier / owner:** Unit/Contract / DEV OSAC-6761. **IC:** IC-2. **Boundary:** input checks and real error serialization; failing backend is a fixture.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing `uv run pytest tests/unit/test_cudn_evpn_role.py tests/unit/test_cudn_evpn_delete_order.py`; extend these files for this case |
| Working directory | osac/osac-aap |
| Environment prerequisites | uv development dependencies, Python/Jinja/Ansible and the shared exact-input/render/error fixtures; no cluster |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: local transforms, render and isolated Ansible invocation where specified; faked: API/provider responses; omitted: deployed core/AAP, Kubernetes/OVN/FRR/KubeVirt and Fabric packets |
| Existing source pattern | tests/unit/test_cudn_evpn_role.py: _render_cudn/_run_role_with_inputs; tests/unit/test_cudn_evpn_delete_order.py: owned cleanup and absence-order assertions |

##### Preconditions

Valid input controls and a write-recording backend fixture containing deliberately sensitive error arguments.

##### Steps

1. Vary missing/mismatched IDs, tenant/parents, manager/task, resource kind, target/interface and duplicate group IDs.
2. Inject a backend timeout and a permanent unsupported rule.

##### Expected Results

Invalid inputs fail before writes. Reported errors contain only nonempty message and boolean retryable, with the expected classification; the play fails. No raw failed-result/invocation, token or secret value is emitted.

#### TC-SETTINGS-01: Validate installation defaults and recover missing prerequisites

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6769](https://redhat.atlassian.net/browse/OSAC-6769) with [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcomes: Installation and diagnostics; explicit unsupported ICMP | high | automated | IC-1, IC-2, IC-3 |

- **Tier / owner:** Core/installer and manager component integration / DEV OSAC-6769 with OSAC-6761. **IC:** IC-1, IC-2, IC-3. **Boundary:** real activation-preflight API/configuration and Kind/Ansible lookup; prerequisite objects/controller status are fixtures, not live FRR/OVN.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Extend verified `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` for activation-preflight/default validation. Missing-manager-setting checks use the proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`, registered in `make -C osac-aap test` |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared Kind, fulfillment activation-preflight API/config fixtures and a zero-dispatch recorder for the unsupported default; plus K8S_AUTH_KUBECONFIG, the CUDN schema fixture and Ansible environment for missing-setting role checks |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: activation-preflight configuration/API, Kind objects and independent Ansible processes; faked: dispatch recorder, prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packets |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Owner-capable Subnet input and the selected installer prerequisite profile. Prepare a fresh activation with otherwise valid defaults and an explicit default ingress rule `{protocol: PROTOCOL_ICMP, ipv4Cidr: 0.0.0.0/0}`. Snapshot configuration/readiness and record provisioning, cleanup and tenant-onboarding dispatches; initially no tenant network exists.

##### Steps

1. Omit or malform DNS resolver setting, then omit installed VTEP/required FRR/hub prerequisite.
2. Repair one prerequisite at a time and repeat the same input.
3. With prerequisites valid, submit the activation fixture containing the explicit ICMP default rule. Inspect the activation error, retained configuration/readiness and all dispatch/mutation records.
4. Replace that default with a supported TCP/UDP rule and retry normal activation before allowing tenant onboarding.

##### Expected Results

Each missing/malformed setting/prerequisite fails retryably and names the item without a success artifact. Repair permits convergence without duplicate state. No task silently installs peering or substitutes a default resolver. An explicit ICMP default blocks activation before tenant onboarding, with the same permanent `cudn_evpn does not support explicit ICMP SecurityGroup rules` diagnostic. No provisioning or cleanup mutation/dispatch occurs and the prior configuration/readiness is unchanged. Supported corrected defaults pass that validation without weakening policy.

#### TC-R3-01: Realize the exact primary EVPN network

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Primary CUDN realization | critical | automated | IC-3 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-3. **Boundary:** real Kind API plus declared CUDN/prerequisite schema fixtures; no OVN dataplane.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

VN/Subnet snapshots and the full namespace/CUDN example in design.md; install the selected CUDN CRD on real API integration runs.

##### Steps

1. Render and create the VN-keyed CUDN for Subnet subnet-a using the saved pools, L2=10100 and parent L3=20001.
2. Inspect its labels, selector, IPAM and VRFs.
3. Supply stale ready conditions from another generation, then current-generation readiness.

##### Expected Results

Exact `evpn: "true"`, VN/tenant ownership and namespace selector are present. Layer2 is Primary, MTU=1500, defaultGatewayIPs=[192.0.2.1], infrastructureSubnets=[192.0.2.1/32,192.0.2.2/32], reservedSubnets=[192.0.2.128/25], ipam.mode=Enabled and lifecycle=Persistent. RTs are 0:10100 and 0:20001. Stale readiness is not accepted. OVN serves the VM gateway; a render is not traffic proof.

#### TC-RT-01: Preserve PR #1971's two explicit route targets

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Matching route targets and pair qualification | critical | automated | IC-3 |

- **Tier / owner:** Unit/Contract / DEV OSAC-6761. **IC:** IC-3. **Boundary:** real Jinja/role rendering; no switch or BGP session.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing `uv run pytest tests/unit/test_cudn_evpn_role.py tests/unit/test_cudn_evpn_delete_order.py`; extend these files for this case |
| Working directory | osac/osac-aap |
| Environment prerequisites | uv development dependencies, Python/Jinja/Ansible and the shared exact-input/render/error fixtures; no cluster |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: local transforms, render and isolated Ansible invocation where specified; faked: API/provider responses; omitted: deployed core/AAP, Kubernetes/OVN/FRR/KubeVirt and Fabric packets |
| Existing source pattern | tests/unit/test_cudn_evpn_role.py: _render_cudn/_run_role_with_inputs; tests/unit/test_cudn_evpn_delete_order.py: owned cleanup and absence-order assertions |

##### Preconditions

The complete CUDN manifest fixture with L2=10100, L3=20001 and no vendor-conditioned rendering.

##### Steps

1. Render for each selected Fabric registration with the same saved identifiers.
2. Inspect both routeTarget values.
3. Repeat with another valid L2 and distinct parent L3.

##### Expected Results

Every render contains MAC-VRF 0:<l2_vni> and IP-VRF 0:<l3_vni>. No hub-AS derivation or vendor switch exists. This asserts host behavior only; pair support requires TC-RT-02 and TC-PAIR-01.

#### TC-RT-02: Verify matching Fabric import/export and expose mismatch

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Matching route targets and pair qualification | critical | automated | IC-3 |

- **Tier / owner:** E2E / QE with Fabric integration owners. **IC:** IC-3. **Boundary:** real OVN/FRR and the selected Fabric's MAC/IP VRFs.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

The reviewed matching RT contract and an authorized lab with the explicit host RTs and a matching configured Fabric pair; packet probes otherwise permitted by policy.

##### Steps

1. Observe the CUDN RTs and Fabric MAC/IP import/export configuration, imported routes and successful permitted traffic.
2. In the lab, introduce a controlled RT mismatch, observe the affected routes/traffic, then restore the matching configuration.
3. Record each claimed vendor/controller/version separately.

##### Expected Results

The matching pair exchanges the required tenant routes and forwards permitted traffic. The mismatch is detected through RT/route and traffic evidence even if BGP remains established. Restoring matching policies restores the path. No Arista/Cumulus/FRR default or universal pair support is inferred; a host-only change cannot satisfy this case.

#### TC-IPAM-01: Preserve the recorded allocation plan

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: VN L3/Subnet L2 typed handoff | critical | automated | IC-3 |

- **Tier / owner:** Unit / DEV OSAC-6761. **IC:** IC-3. **Boundary:** IPAM validation/exclusion transform and render; no DHCP server.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing `uv run pytest tests/unit/test_cudn_evpn_role.py tests/unit/test_cudn_evpn_delete_order.py`; extend these files for this case |
| Working directory | osac/osac-aap |
| Environment prerequisites | uv development dependencies, Python/Jinja/Ansible and the shared exact-input/render/error fixtures; no cluster |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: local transforms, render and isolated Ansible invocation where specified; faked: API/provider responses; omitted: deployed core/AAP, Kubernetes/OVN/FRR/KubeVirt and Fabric packets |
| Existing source pattern | tests/unit/test_cudn_evpn_role.py: _render_cudn/_run_role_with_inputs; tests/unit/test_cudn_evpn_delete_order.py: owned cleanup and absence-order assertions |

##### Preconditions

Saved 192.0.2.0/24 allocation: overlay=.0/25, physical=.128/26, VIP=.192/26; gateway=.1 and infrastructure=.2. Include empty physical/VIP lists and fragmented fixtures requiring exactly 25 and 26 minimal reserved CIDRs.

##### Steps

1. Build the disjoint infrastructure and minimal reserved cover without altering saved pools.
2. Assert the example values and allocations for each empty-list plan.
3. Submit the 25-entry and 26-entry fixtures, recording writes.

##### Expected Results

Example infrastructure=[192.0.2.1/32,192.0.2.2/32], reserved=[192.0.2.128/25], with no overlap or workload allocation from either list, network or broadcast. Exactly 25 entries are allowed; 26 fails retryable:false with reservedSubnets exceeds 25 entries before writes. No approximation includes an allowed workload address and no retry reallocates IPAM.

#### TC-R6-01: Observe real DHCP pools, OVN gateway and DNS

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Disjoint pools, gateway and DNS | critical | automated | IC-3, IC-6 |

- **Tier / owner:** E2E / QE. **IC:** IC-3, IC-6. **Boundary:** deployed OVN DHCP, KubeVirt guest, real Fabric/physical DHCP and resolvers.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Deployed OVN/KubeVirt/Fabric pair, the recorded IPAM example and an installed DNS-Service profile whose IPv4 addresses equal CUDN_EVPN_DNS_RESOLVERS.

##### Steps

1. Boot the VM through normal OSAC creation.
2. Inspect its DHCP lease/address, /24 prefix, gateway, resolver list and MTU.
3. Query the agreed resolver and a permitted Fabric endpoint.
4. Repeat after correcting a deliberately mismatched DNS-Service configuration.

##### Expected Results

Address belongs to the saved overlay pool and excludes reserved infrastructure; router is 192.0.2.1 served by OVN; resolvers exactly match the agreed ordered list; MTU is 1500 and permitted queries succeed. A mismatch fails preflight/task retryably before mutation, never substitutes DNS or invents a CUDN field.

#### TC-R5-04: Let the first executing create claim ownership

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Owner-Subnet limit and conflict safety | critical | automated | IC-4 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-4. **Boundary:** real Kubernetes state and independent Ansible runs, with core ordering represented explicitly.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Two sibling Subnet snapshots with reversed creation-time versus execution order; unowned VN state.

##### Steps

1. Run the newer Subnet's create first, then the older one, and retry both.
2. Exercise the default-Subnet ordering as a shared-core fixture.

##### Expected Results

The first successful claim records that Subnet's API ID, independent of timestamp/name. Exactly one network exists. Retries do not change ownership. Default ordering is a core guarantee, not a manager timestamp election.

#### TC-R5-05: Preserve owner VMs when another Subnet is added

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Owner-Subnet limit and conflict safety | critical | automated | IC-4, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-4, IC-6. **Boundary:** real Kind network/state/policy objects; VM execution is omitted.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Owned network and owner binding plus a sibling's valid recorded plan/segment.

##### Steps

1. Run sibling create/delete and an overlay apply/delete for it; inspect owner resources and recorded sibling plan.

##### Expected Results

Sibling Subnet tasks succeed without creating a second network; overlay apply fails permanently naming the owner-network limitation and writes no attachment artifacts. Its absent delete succeeds. Owner bindings/network and both recorded plans remain unchanged. A core/Fabric companion check establishes that physical sibling attachments remain available.

#### TC-R5-06: Release ownership without handover

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Owner-Subnet limit and conflict safety | critical | automated | IC-4 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-4. **Boundary:** real Kind objects and Ansible cleanup.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Owner Subnet, a surviving sibling and dependency-ordered attachment cleanup already complete.

##### Steps

1. Delete the owner, repeat delete, then inspect the sibling; run a subsequent new Subnet create.
2. Include no-op deletion of a non-owner and already-absent state.

##### Expected Results

Owner network/baseline are removed before claim release; the VN-owned namespace and surviving group policies remain. A later owner reuses that namespace without inheriting old bindings. No surviving sibling is promoted. A subsequent create can claim the released network. Non-owner/absent cleanup does not delete foreign or newly claimed state.

#### TC-R5-07: Exercise owner termination and late create/delete writes

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Owner-Subnet limit and conflict safety | critical | automated | IC-4 |

- **Tier / owner:** Component integration / DEV OSAC-6761 with core lifecycle DEV. **IC:** IC-4. **Boundary:** real API conflicts and independently paused Ansible/backend operations for Kubernetes Manager-owned hub objects; no packet path. The provider Fabric backend is covered separately by shared contract Shared TC-DELETE-02 (provider-owned conformance coverage).


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed; issued-POST/delete/restart branches BLOCKED until the strict backend proof is reviewed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Reviewed deletion ownership/delete-wins mechanism; controls that pause/release exact Namespace, CUDN and NetworkPolicy mutations, expose cleanup progress/waiting and authoritative settlement, and record commit/rejection order. Keep a separate live ownership control and snapshot its state. Use the configured cleanup deadline as a failure bound, not proof of mutation completion. The post-success-create branch remains blocked until the strict backend mechanism is selected and proven; do not mark it passing with a fake fence.

##### Steps

1. Start another create while the owner CR is terminating; finish owner cleanup and retry the claim.
2. Separately pause an already-issued create mutation before commit, cancel its job and start matching deletion with the stored input.
3. Observe deletion reaching cleanup, waiting for the outstanding operation, or succeeding; then release the exact mutation without waiting for deletion to succeed first.
4. Await operation settlement and successful cleanup within the configured deadline. Repeat the trace for Namespace, CUDN and NetworkPolicy.
5. Inspect owned objects and mutation history before a repeated delete or corrective cleanup. Verify the live control is unchanged, then require repeated deletion to succeed. Separately race cleanup from an old API ID with a new claim and verify the new owner's objects survive.

##### Expected Results

A terminating owner is treated as present and produces a retryable claim failure; retry after release can claim safely. Ordered cleanup may stay pending until the held operation settles, then removes all state before success. If delete succeeds first, the released write must be rejected or become a no-op through an enforced backend fence; no later or transient recreation is permitted. Post-success corrective cleanup cannot hide a leak. Old cleanup never removes the new owner's objects. A preflight tombstone read or journal alone does not prove safety; unknown/indefinitely pending operations do not pass. No manager Lease is required. The separately proposed shared deletion oracle must accept safe ordered completion or an enforced fence and reject post-success resurrection; it is not an existing provider runner.

#### TC-POLICY-01: Create unbound groups and update the shared policy

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Baseline/exact policy and explicit unsupported ICMP | critical | automated | IC-5 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-5. **Boundary:** real policy/state API objects; no packet enforcement.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

The selected shared VN namespace model, VN snapshot and group rules; initially no Subnet, network or attachment.

##### Steps

1. Run VN create twice, then create the group before a Subnet exists.
2. Bind two target IDs in the shared namespace, replace rules with a rerun, retry, then delete after unbinding and repeat deletion.
3. Include another group's policies and a foreign-tenant ownership control.

##### Expected Results

Initial group creation needs no network and selects no VM. One VN-owned namespace and one SG-owned policy exist; all bound target IDs follow its accepted replacement. Retries create no duplicates. Group deletion removes only its policy and preserves the namespace. Repeated deletion succeeds; other groups and tenant state remain unchanged. No attachment rerun is needed for the update.

#### TC-POLICY-02: Reject unsupported policy and preserve empty directions

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Baseline/exact policy and explicit unsupported ICMP | critical | automated | IC-2, IC-5 |

- **Tier / owner:** Unit/Contract / DEV OSAC-6761. **IC:** IC-2, IC-5. **Boundary:** rule translation and captured object replacements; Kubernetes policy engine omitted.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Verified existing `uv run pytest tests/unit/test_cudn_evpn_role.py tests/unit/test_cudn_evpn_delete_order.py`; extend these files for this case |
| Working directory | osac/osac-aap |
| Environment prerequisites | uv development dependencies, Python/Jinja/Ansible and the shared exact-input/render/error fixtures; no cluster |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: local transforms, render and isolated Ansible invocation where specified; faked: API/provider responses; omitted: deployed core/AAP, Kubernetes/OVN/FRR/KubeVirt and Fabric packets |
| Existing source pattern | tests/unit/test_cudn_evpn_role.py: _render_cudn/_run_role_with_inputs; tests/unit/test_cudn_evpn_delete_order.py: owned cleanup and absence-order assertions |

##### Preconditions

Last-successful group rules and exact TCP/UDP/all-protocol inputs, empty directions and ICMP cases.

##### Steps

1. Render both policy directions, port boundaries/ranges and remote CIDRs.
2. Attempt malformed/unsupported rules and inject replacement failure.
3. Submit an explicit `icmp` rule without ports and require `osac_error.retryable: false` with `cudn_evpn does not support explicit ICMP SecurityGroup rules` before any backend mutation. Compare the saved policy and membership with their pre-request values; no successful ICMP implementation path is allowed.

##### Expected Results

Every NetworkPolicy includes Ingress and Egress, even with no rules in one direction. Rules retain exact allowed traffic semantics. Explicit ICMP is rejected permanently before mutation, never implemented or silently dropped. A definitively rejected replacement retains the previous rules and membership; a lost/unknown response is reconciled without asserting rollback or success.

#### TC-POLICY-03: Deny unbound traffic while preserving DHCP/ARP

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Baseline/exact policy and explicit unsupported ICMP | critical | automated | IC-5 |

- **Tier / owner:** E2E / QE. **IC:** IC-5. **Boundary:** actual primary EVPN dataplane.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Ready owner network, baseline installed, unbound VM/import or other pods and a reachable test endpoint.

##### Steps

1. Probe application ingress/egress from unbound pods; perform DHCP renewal and gateway/peer ARP.
2. Where backend supports the restriction, send a tenant-originated DHCP reply.

##### Expected Results

Application traffic is blocked both ways before any binding. Owning DHCP and permitted ARP succeed. Supported rogue-DHCP protection blocks tenant replies. Results identify actual backend/version and any unimplemented protection explicitly.

#### TC-POLICY-04: Enforce selected group union and updates

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Baseline/exact policy and explicit unsupported ICMP | critical | automated | IC-5, IC-6 |

- **Tier / owner:** E2E / QE. **IC:** IC-5, IC-6. **Boundary:** real VM/Fabric traffic and policy engine.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Two groups with distinct ingress/egress allows, multiple bound VMs and an unbound control pod; known last-successful rules.

##### Steps

1. Probe allowed/denied TCP/UDP/all cases and stateful replies, replace a group's rules, probe each bound target in the shared namespace, and exercise the permanent unsupported-ICMP path.

##### Expected Results

Each VM receives exactly its selected union in both directions, follows the successful update without reattachment, and permits stateful replies. Empty directions allow no application traffic through that policy contribution. Unbound/control traffic remains protected. Unsupported ICMP is a visible failed group, not an unfiltered success. This case proves VM-pod enforcement only; physical-port enforcement is separately required by shared contract TC-BM-01, and a Fabric no-op is nonconformant whenever BMaaS or CaaS is enabled.

#### TC-POLICY-05: Converge a bind racing a rule replacement

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Baseline/exact policy and explicit unsupported ICMP | critical | automated | IC-5, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-5, IC-6. **Boundary:** real policy/state API conflicts with controlled independent Ansible operations.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Real Kind NetworkPolicy with known UID/RV, source generation=2, digest d2 and targets vm-a/vm-b. Two independent Ansible processes can pause exact fixed JSON patches. Namespace/group deletion and missing-target fixtures are available.

##### Steps

1. Race a rule patch with a bind/unbind patch using the same RV.
2. Retry the rejected operation from fresh authorized state.
3. Submit an older generation and equal-generation/different-digest update.
4. Delete the policy, then release an old fixed patch.
5. Repeat with target already absent.
6. Lose a committed patch response, then reconcile from its generation/digest.

##### Expected Results

Only UID/RV-tested application/json-patch+json is used. Conflicts are retryable and preserve the other field set; older/conflicting generations cannot win. A missing policy rejects the old patch and no object is recreated; an already-absent target unbind is idempotent, without an RV write against a missing object. Unknown responses never prove rollback or success. POST/delete safety remains blocked separately by the backend proof; SSA/upsert is forbidden for these patches.

#### TC-ATTACH-01: Prepare deterministic namespace and policy before a VM

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Namespace-before-VM and persistent addressing | critical | automated | IC-2, IC-5, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-2, IC-5, IC-6. **Boundary:** real Kind namespace/selection/policy writes and captured result; no VM CR is installed.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

VN namespace, owner CUDN/baseline and two current group policies exist; target ComputeInstance API ID is known but its VM does not exist. A request recorder rejects every VM/VMI request and records attempted calls.

##### Steps

1. Invoke apply_network_attachment with target.kind=ComputeInstance, interface.type=overlay, the owner Subnet and selected group IDs.
2. Inspect policy selectors and exact osac_result.
3. Repeat with the same input and inspect the request recorder.

##### Expected Results

Apply succeeds before VM creation and returns only vm_attachment.namespace, equal to the shared VN namespace. Both policies select the sorted unique target API ID while retaining current rules. Retry retains the namespace UID and membership. The recorder contains zero VM/VMI calls, including rejected reads; an unavailable VM API alone is not sufficient proof.

#### TC-ATTACH-02: Keep the VM address through restart and migration

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Namespace-before-VM and persistent addressing | critical | automated | IC-3, IC-6 |

- **Tier / owner:** E2E / QE. **IC:** IC-3, IC-6. **Boundary:** actual KubeVirt restart/live migration, OVN allocation and Fabric binding.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Reviewed DNS supported mechanism, migratable VM, observed overlay address and completed Fabric policy bind.

##### Steps

1. Record address/DHCP/network state, restart the VM, then migrate it to another eligible hub node.
2. Observe address and permitted traffic after each transition without a new allocation/bind input.

##### Expected Results

The same address is retained within the recorded overlay pool; Fabric traffic continues with the existing binding after convergence. No per-operation RT or duplicate allocation is introduced. Record actual supported versions and interruption measurements without inventing a latency SLA.

#### TC-ATTACH-03: Clean only owned attachment resources

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Namespace-before-VM and persistent addressing | critical | automated | IC-4, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-4, IC-6. **Boundary:** real namespace/policy/state API objects.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Two live target bindings and a foreign-owned control in the VN-owned namespace; groups contain current rules.

##### Steps

1. Delete one attachment twice; exercise partial apply state and an unsupported Subnet attachment that created nothing.
2. Attempt cleanup with stale/foreign ownership and with another live resource present.

##### Expected Results

Only the target's owned binding/artifacts disappear; the other binding, shared namespace and foreign objects remain. The VN namespace is never removed by attachment deletion; other memberships and current group rules remain unchanged. Never-created cleanup succeeds. No VM/VMI is read, patched or deleted by the manager.

#### TC-RETRY-01: Resume partial work and clean after cancellation

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Retry, cancellation and owned cleanup | critical | automated | IC-2, IC-4, IC-5, IC-6 |

- **Tier / owner:** Component integration / DEV OSAC-6761. **IC:** IC-2, IC-4, IC-5, IC-6. **Boundary:** fresh Ansible processes and real API state, with controlled failure injection.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e @common_vars.yml`; register this new target/race plays in the existing `make -C osac-aap test` aggregate |
| Working directory | osac/osac-aap/tests/integration for the focused command; osac root for make |
| Environment prerequisites | Prepared real Kind and K8S_AUTH_KUBECONFIG, installed CUDN schema fixture, isolated case IDs/parents, Ansible environment and independently controlled requests |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed; issued-POST/delete/restart branches BLOCKED until the strict backend proof is reviewed |
| Real / faked / omitted | Real: Kind API storage/conflicts, Namespace/CUDN/policy objects and independent Ansible processes; faked: prerequisite objects/CUDN controller status and specified fault injection; omitted: deployed AAP and OVN/FRR/KubeVirt/Fabric packet behavior |
| Existing source pattern | tests/integration/targets/metallb_l2_detach_annotation/tasks/baseline.yml for independent conditional-write processes; tests/unit/test_cudn_evpn_role.py for input/manifest fixtures |

##### Preconditions

Fixtures for all eight task entry points and barriers after each meaningful backend write.

##### Steps

1. For each of the eight task entry points, prepare its normal parents and an independent live-ID control; save the input and object inventory.
2. Run the task twice successfully and compare namespace/CUDN UIDs, owner, pools, VNIs, membership and typed output.
3. Stop a fresh process before it submits its first write; restart from saved state and retry the same input.
4. Pause an exact already-issued write, cancel the job/process and start matching cleanup. Keep unknown outcomes pending; release the write using the controlled race procedure from TC-R5-07.
5. Commit a write but drop its response, stop the process and restart. Reconcile the actual persisted state without allocating another address or changing ownership.
6. Inject a transient API error; require a failed play and osac_error.retryable=true with no success artifact, then repair and retry.
7. Submit a permanently unsupported explicit ICMP rule; require retryable=false and no policy mutation.
8. Run the matching delete on partial state and on an API ID whose create never started; repeat deletion and compare the live control with its snapshot.
9. For every post-submission ambiguity, record the authoritative settlement/fence evidence before accepting successful deletion. Mark the case blocked where the reviewed backend mechanism is still missing.

##### Expected Results

Retries converge with the same identities/output, without duplicates or changed addresses/owners. Unsupported input is final, transient faults publish retryable errors, and deletes complete owned cleanup from partial/absent state. An unknown create outcome keeps cleanup retryably pending; an empty GET or timeout alone cannot produce a successful delete. Indefinite unknown state does not establish restart recovery. Failed deletes remain failures for core to retry; no success artifact conceals a cleanup error.

#### TC-DELETE-01: Observe VMaaS-owned teardown before network cleanup

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Retry, cancellation and owned cleanup | critical | automated | IC-4, IC-6 |

- **Tier / owner:** E2E / QE with core lifecycle DEV fixtures. **IC:** IC-4, IC-6. **Boundary:** deployed VMaaS/operator/AAP/OVN/Fabric.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Running owner VM and selected group; sibling/foreign live controls; ability to inject a manager cleanup failure.

##### Steps

1. Delete the VM; observe VMaaS removal before Fabric then Kubernetes attachment deletes.
2. Delete the owner Subnet after attachments, then its groups/VN through dependency guards.
3. Retry a failed cleanup.

##### Expected Results

Manager tasks never delete the VM. Finalizers retain ownership until cleanup succeeds. Network/baseline removal follows attachment teardown and releases the owner without handover. The VN namespace and surviving groups remain through Subnet deletion; final VN cleanup removes its namespace only after child teardown and foreign/live-resource safety checks. Foreign/sibling live resources remain, and no released VNI/state is reused before its owning Fabric delete succeeds.

#### TC-CUDN-DELETE-02: Review stale-VRF support without automatic disruption

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Retry, cancellation and owned cleanup | critical | manual | IC-4 |

- **Tier / owner:** Documentation review / documentation DEV; any recovery execution needs the platform team's approved lab procedure. **IC:** IC-4.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Manual document/source review; no executable command |
| Working directory | enhancement-proposals (documentation repository) |
| Environment prerequisites | Current manager/contract documents and the source/evidence specified in this case; no cluster execution |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: source documents and examples; faked: none; omitted: every runtime API, workload and packet path |
| Existing source pattern | design.md Support Procedures, Installation and RBAC sections; existing source task/manifest examples |

##### Preconditions

A deleted CUDN and evidence of an apparent node VRF remnant; inventory of remaining live networks/attachments.

##### Steps

1. Verify the support guidance requests ownership/OVN/FRR evidence and platform review; inspect manager delete behavior for disruptive host operations.

##### Expected Results

Guidance distinguishes a remnant from a live owned network. Routine delete never restarts networking pods or deletes host VRFs. Any platform recovery records its effect on other node workloads; no direct-delete recipe is treated as universally safe.

#### TC-R7-01: Review installation and Enclave handoff guidance

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Administrator guidance and failure classification | medium | manual | IC-1 |

- **Tier / owner:** Documentation review / documentation DEV, coordinated with OSAC-6769 and Enclave owners. **IC:** IC-1.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Manual document/source review; no executable command |
| Working directory | enhancement-proposals (documentation repository) |
| Environment prerequisites | Current manager/contract documents and the source/evidence specified in this case; no cluster execution |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: source documents and examples; faked: none; omitted: every runtime API, workload and packet path |
| Existing source pattern | design.md Support Procedures, Installation and RBAC sections; existing source task/manifest examples |

##### Preconditions

Current installation reference, confirmed plugin/Wizard consumer/version when available.

##### Steps

1. Review VTEP/FRR/node peering, per-node ASNs, VNI range and MTU, underlay VTEP routing, DNS setting/environment and immutable registration.
2. Trace installer schema → plugin → Wizard controls/errors.

##### Expected Results

Guidance states that OVN serves the VM gateway, both VRFs use explicit 0:VNI RTs and matching Fabric imports/exports, and installer EVPN values own host networking. It includes evpn: "true", the VN namespace lifetime, ICMP-default rejection and Enclave schema consumption. The open installer delivery dependency and required real-pair evidence are explicit; no assignment or runtime support is invented.

#### TC-R8-01: Review actionable diagnostic and ownership guidance

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761) | PRD outcome: Administrator guidance and failure classification | medium | manual | IC-1, IC-2, IC-4 |

- **Tier / owner:** Documentation review / documentation DEV. **IC:** IC-1, IC-2, IC-4.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Manual document/source review; no executable command |
| Working directory | enhancement-proposals (documentation repository) |
| Environment prerequisites | Current manager/contract documents and the source/evidence specified in this case; no cluster execution |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: source documents and examples; faked: none; omitted: every runtime API, workload and packet path |
| Existing source pattern | design.md Support Procedures, Installation and RBAC sections; existing source task/manifest examples |

##### Preconditions

Sanitized example task errors and CUDN/namespace/FRR/Fabric evidence.

##### Steps

1. Follow guidance for missing prerequisites, out-of-range VNI rejection, owner-limit failure, policy rejection, transient conflict and traffic failure despite successful tasks.

##### Expected Results

Each path identifies the responsible setting/owner and supported repair/lifecycle action. Read-only commands show segment/route/peering/ownership evidence. No secret, other-tenant IDs, arbitrary finalizer removal or unsupported adoption path is exposed.

#### TC-PAIR-01: Record the supported real EVPN pair

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Matching route targets and pair qualification | critical | automated | IC-1, IC-3, IC-5, IC-6 |

- **Tier / owner:** E2E / QE with Fabric and OVN integration owners. **IC:** IC-1, IC-3, IC-5, IC-6. **Boundary:** complete deployed path and real Netris initially.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

platform and deletion acceptance gates closure, approved shared RT amendment, qualifying hub/Fabric infrastructure, applicable service profiles and actual common-runner entrypoint when supplied by core.

##### Steps

1. Execute applicable VM/task profiles and the referenced traffic/lifecycle cases.
2. With workloads running under the supported amended contract, repeat reconciliation and manager retry/restart; compare VN/Subnet IDs/specs, stored pools/VNIs, namespace/CUDN UIDs, guest addresses and allowed/denied probes before and after.
3. Capture actual versions, inputs, gateway/RT/route behavior, commands and each pass/fail/skip.
4. Repeat separately for any additional claimed Fabric pair.

##### Expected Results

Report distinguishes real endpoints from fixtures and required skips from passes. It resolves the provisional Fabric route behavior from evidence. Supported retry/restart retains resource and backend identities, pools/VNIs, VM placement/addresses and the same allowed/denied probe outcomes without network or workload recreation. Registration/unit/Kind success is not accepted as proof of an Arista/Cumulus/Netris packet path.

#### TC-R4-01: Prove permitted same-Subnet VM-to-physical L2 traffic

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: VM/physical L2 and same-VN routed connectivity | critical | automated | IC-3, IC-5, IC-6 |

- **Tier / owner:** E2E / QE. **IC:** IC-3, IC-5, IC-6. **Boundary:** real Fabric, VM and physical client.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

VM on owner Subnet and physical peer on that same L2 segment, completed bindings and policy permitting a known TCP/UDP probe.

##### Steps

1. Probe both directions with allowed policy, remove the necessary allow at one enforcement point, and repeat; inspect actual MAC/IP and EVPN learning.

##### Expected Results

Allowed probes and replies succeed, one-sided policy denial blocks application traffic, and the learned path belongs to the recorded segment/VTEP. No unapproved latency threshold or unsupported ICMP assumption determines success.

#### TC-R4-02: Prove Fabric-routed traffic within one VirtualNetwork

| Story / Task | AC source | Priority | Automation | Interface Change |
|---|---|---|---|---|
| No QE ticket mapped/created by this plan; parent [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) | PRD outcome: Disjoint pools, gateway and DNS | critical | automated | IC-3, IC-5, IC-6 |

- **Tier / owner:** E2E / QE. **IC:** IC-3, IC-5, IC-6. **Boundary:** real Fabric IP-VRF, owner VM and physical peer on a sibling Subnet.


| Execution evidence | Planned value |
|---|---|
| Command / verification | Proposed `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py`; target file must be added |
| Working directory | osac (mono-repo root) |
| Environment prerequisites | Deployed compatible OSAC/AAP, OVN/FRR/KubeVirt, tenant credentials, VM template/image, DNS prerequisites and real selected Fabric pair; this case's policy/peer fixtures |
| Execution status | Release acceptance gated on #427; not run; planned case/extension, no passing evidence claimed |
| Real / faked / omitted | Real: fulfillment API/DB, operator, AAP jobs, hub/VM APIs, OVN/FRR, guest DHCP/DNS and Fabric; faked: none permitted; omitted: none of the case's required boundaries |
| Existing source pattern | tests/e2e/conftest.py: grpc/k8s_hub_client; tests/e2e/vmaas/conftest.py: k8s_virt_client/vm_template; core/helpers.py: wait_for_subnet_ready/wait_for_vmi_ip; core/runner.py: poll_until |

##### Preconditions

Same VN/L3 VNI, distinct Subnet/L2 VNIs, a valid owner overlay attachment and a physical sibling attachment, with permitted policy.

##### Steps

1. Probe the remote Subnet through the recorded OVN VM gateway and Fabric routing and inspect ARP, routes and the actual EVPN path.
2. Repeat with policy denial and an unrelated overlapping-CIDR VN as an isolation control.

##### Expected Results

Permitted same-VN routed traffic succeeds; denied/unrelated-VN traffic fails. The Fabric supplies routing without a second CUDN gateway or inter-VRF-peering assumption. Record actual supported route types; do not require type-5 until the lab establishes that behavior.

## Gaps and Acceptance Gates

- Prerequisite [manager-contract amendment #427](https://github.com/osac-project/enhancement-proposals/pull/427) must be approved and merged before release acceptance of all 34 active cases. It defines the gateway, identifier handoff, RTs, namespace lifetime and installer ownership they rely on. Unit fixtures may be developed/run before approval, but do not waive that contract gate; all activation and supported-pair claims remain blocked until it closes.

- The strict backend create/delete ordering or fencing proof is not selected or demonstrated. TC-R5-07's relevant create/delete/restart branches remain blocked; no timeout, absent GET, preflight tombstone or fake backend can make them pass.
- Platform versions, installed DNS-Service wiring, primary-network policy, persistent-IP and real Fabric validation must be recorded before activation. A component CRD fixture is not a supported-platform result.
- The dedicated Kind target, deployed CUDN E2E file and shared core/installer extensions are planned work. Existing render tests provide patterns only.
- Story/Task and Jira-AC mapping will be finalized in decomposition against real work items. The named PRD outcome/IC coverage above is complete; no Jira AC identifiers, created Tasks or assignments are fabricated.

## Retired and Renamed IDs

- Existing retired IDs TC-R5-01, TC-R5-02, TC-R5-03, TC-R9-01 remain reserved and must not be reused; their historical expectations were superseded by the current task/owner model.
- TC-VNI-01 is retired: its ASN-based rejection is removed from the contract. Integer bounds, uniqueness, stability and ASN-independent acceptance are covered by TC-R2-02.
- The manager's former TC-DELETE-02 is now TC-CUDN-DELETE-02; update downstream references to the new local ID. The shared contract's TC-DELETE-02 retains its own identity. No active ID is reused.

## Summary

| Metric | Count |
|---|---|
| Active cases | 34 |
| Named PRD outcome groups covered | 13 / 13 |
| Interface changes covered | 6 / 6 |
| Priority: critical | 28 |
| Priority: high | 4 |
| Priority: medium | 2 |
| Priority: low | 0 |
| Automation: automated | 31 |
| Automation: manual | 3 |

Automation classifications describe intended execution, not completed automation or passing results. All cases retain their named boundary and owner; blocked acceptance gates are not waived.
