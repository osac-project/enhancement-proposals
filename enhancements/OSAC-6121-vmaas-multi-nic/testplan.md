# Testplan — OSAC-6121

## Overview

- **Feature:** [OSAC-6121](https://redhat.atlassian.net/browse/OSAC-6121) — VMaaS: multi-NIC support (provider-managed primary workload attachment plus shared OOB attachment)
- **Sources:** PRD [#389](https://github.com/osac-project/enhancement-proposals/pull/389) (`prd.md`, FR 1-11, nine acceptance criteria) and design [#396](https://github.com/osac-project/enhancement-proposals/pull/396) (`design.md`, which carries the role-based network type commits of [#393](https://github.com/osac-project/enhancement-proposals/pull/393) and makes the "OSAC-6121 Provider-Managed OOB Path" section authoritative). Both PRs are open; this plan follows their heads, unchanged as of 2026-11-12.
- **Total test cases:** 51
- **Requirements covered:** 11 of 11 (FR-1 to FR-11); acceptance criteria AC-1 to AC-9 all have at least one case
- **Status:** planning only. No case has run. Every case is `Not run`, and the cases that depend on the missing localnet K8s manager or on an OOB-capable lab are `Blocked` (see [Gaps](#gaps)). The E2E cases target [LAB-MNIC](#e2e-lab-lab-mnic), a single-host libvirt lab.

### What the feature does

Today a VMaaS ComputeInstance has at most one network attachment, so a VM has
one NIC. Some provider-managed VMs also need an out-of-band (OOB) interface: a
second NIC on a physical management network, with a fixed address that the
provider's management systems outside the cluster can reach. OSAC-6121 adds
that second NIC without changing the single-NIC path for anyone else.

The result is a VM with two kinds of interface:

| | Primary NIC | OOB NIC |
|---|---|---|
| Network | The tenant's workload VirtualNetwork | The one shared OOB VirtualNetwork of the deployment |
| Implementation | CUDN with EVPN through the fabric (existing `cudn_evpn` path) | Localnet CUDN bridged to a physical VLAN (new localnet Kubernetes Manager) |
| KubeVirt wiring | Pod network, `l2bridge` binding | Multus network on a NAD local to the VM namespace, `bridge` binding |
| Address | Assigned by the network | Static IPv4 reserved by the provider and injected through cloud-init |
| Default route, ExternalIP, NAT | Yes, only here | Never; the OOB NIC only answers OOB clients |

How it works:

- **Roles.** The deployment keeps one NetworkClass, which now maps network
  roles (for example `workload` and `oob`) to a Fabric Manager and Kubernetes
  Manager pair. Each VirtualNetwork picks a role; its Subnets are provisioned by
  that role's managers.
- **Provider-managed.** The provider admin creates the networks, reserves the
  OOB address and creates the VM; the tenant receives the VM and can see both
  addresses but cannot create, select or change OOB networking.
- **Capability gate.** Multi-NIC is accepted only when every manager on both
  paths declares support (`supports_multi_nic`). Otherwise requests with more
  than one attachment are rejected before anything is stored, exactly as today.
- **Primary marker.** With several attachments, exactly one carries
  `primary: true`. A single attachment stays implicitly primary. The limit stays
  at eight attachments.
- **Generic composition.** Each Subnet publishes a `SubnetNetworkBinding` (how
  KubeVirt attaches to it, the NAD name, the namespace label that makes the NAD
  appear). The VM is composed from those bindings with no manager-specific code.
- **Fabric handoff.** The OOB Fabric Manager configures the switch VLAN and
  hands the physical network data to the localnet manager, which only then
  creates the Localnet CUDN.
- **Fixed after creation.** Attachments, their Subnets, the primary choice and
  the OOB address cannot change; changing them means recreating the VM.
- **Isolation.** A provider MultiNetworkPolicy on the OOB NAD stops VMs from
  reaching each other over OOB; only the management hosts can reach them.

Not in this feature: CaaS and BMaaS, NIC hot-plug, tenant-created OOB networks,
arbitrary combinations of VirtualNetworks, IPv6, and a UI to create managed VMs
(the UI only displays both attachments).

### Acceptance criteria IDs

The PRD acceptance criteria are unnumbered; this plan numbers them in PRD order.

| ID | PRD acceptance criterion (short) |
|---|---|
| AC-1 | Role mappings resolve primary to CUDN+EVPN and OOB to localnet; `supports_multi_nic` stays false unless both paths advertise support |
| AC-2 | One shared OOB VirtualNetwork and Subnet reused by OOB attachments of several managed VMs |
| AC-3 | Managed VM gets a primary `l2bridge` interface and a secondary Multus/bridge interface; the OOB guest interface has its reserved static IPv4 |
| AC-4 | Multi-attachment rejected before persistence when the capability is false or unset; omitted and single attachment unchanged |
| AC-5 | Enabled: up to eight valid attachments accepted, nine rejected; listed invalid requests rejected |
| AC-6 | VM reconciler consumes `SubnetNetworkBinding` without manager-specific logic; localnet manager creates a local NAD in the VM namespace through the namespace-label contract |
| AC-7 | Per-attachment status and details UI; primary identifiable; ExternalIP DNAT on primary; OOB changes neither default route nor NAT; OOB replies leave through OOB |
| AC-8 | Attachments, Subnets, primary and OOB static address immutable after creation |
| AC-9 | Unsupported deployments keep OSAC-1435 single-NIC and default networking; CaaS and BMaaS unchanged |

### Tiers and ownership

Tier names and ownership follow the OSAC [integration testing guide](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#shared-tiers-and-boundaries): Unit, Envtest, Component integration and Contract cases are `[DEV]` work for the story that changes the code; deployed cross-component journeys (E2E) are `[QE]` work. No implementation or QE story exists under OSAC-6121 yet, so the **Story** column names the Feature (see [Gaps](#gaps)). Per-component suites, boundaries and commands are in the component suite guides (`docs/testing/<component>.md`) and each component's `AGENTS.md`; the matrix commands were checked there.

## Coverage matrix

One row per suite and boundary. Each case names its row in its preconditions. "Existing" paths and commands were checked against `osac-project/osac` `main` on 2026-11-12; everything marked *proposed* does not exist yet.

| Row | Component / tier / owner | Behavior and cases | Suite or location | Command (working dir) | Runs for real | Faked or omitted | Status / follow-up |
|---|---|---|---|---|---|---|---|
| M1 | fulfillment-service / Component integration (server/PostgreSQL) / [DEV] | Create, update and validation of ComputeInstance attachments, VirtualNetwork `network_type`, capability gate: TC-FR1-01, TC-FR1-02, TC-FR4-03, TC-FR4-04, TC-FR4-05, TC-FR4-06, TC-FR4-08, TC-FR5-01, TC-FR5-02, TC-FR5-03, TC-FR5-04, TC-FR5-05, TC-FR5-06, TC-FR10-01 | Existing `internal/servers/private_compute_instances_server_test.go` (contexts `network_attachments`, `NetworkAttachments validation`, `NetworkAttachments immutability`), `internal/servers/private_virtual_networks_server_test.go`, `internal/servers/network_attachment_resolution_test.go`; new contexts *proposed* in the same files | `ginkgo run --timeout 10m internal/servers` (`fulfillment-service/`) | In-process Fulfillment servers, real PostgreSQL in a test container, real reference validator | Tenancy and external APIs controlled; no operator, AAP or provider | Not run |
| M2 | fulfillment-service / Component integration (deployed) / [DEV] | Caller authorization for the shared OOB exception, no persistence on rejection, per-attachment status through the API, single-NIC regression: TC-FR2-01, TC-FR3-02, TC-FR5-07, TC-FR8-03, TC-FR11-01 | Existing `it/it_compute_subnet_test.go` (Describe "ComputeInstance with Subnet attachment") and `it/it_compute_instance_network_attachment_status_test.go` (label `compute-networking`); new file *proposed* `it/it_compute_multi_nic_test.go` | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (repository root); focused: `ginkgo run --timeout 20m --focus '<Describe>' it` (`fulfillment-service/`) against a deployed environment | Deployed Fulfillment API and controller, PostgreSQL, Keycloak, CLI built from the checkout | Network readiness and operator feedback are fixture-supplied; no AAP, KubeVirt or provider. The standard target deploys with provider networking disabled, and specs gated on it skip there (`docs/testing/fulfillment-service.md`) | Not run. TC-FR2-01, TC-FR3-02, TC-FR5-07 and TC-FR8-03 need `supports_multi_nic: true`: either the fixture sets it with provider networking disabled, or they run in the `networking-operator` phase. A skip is not coverage |
| M3 | fulfillment-service / Unit / [DEV] | Hub CR mapping of `primary` and `static_ipv4_address`; automatic ExternalIPAttachment picks the primary address: TC-FR7-04, TC-FR8-05 | Existing `internal/controllers/computeinstance/computeinstance_reconciler_function_test.go` (Describe "buildSpec network attachments"), `internal/controllers/autoexternalipattachment/auto_external_ip_attachment_reconciler_function_test.go` | `go test ./internal/controllers/computeinstance ./internal/controllers/autoexternalipattachment` (`fulfillment-service/`) | Reconciler functions | Kubernetes and Fulfillment clients controlled | Not run |
| M4 | osac-operator / Unit / [DEV] | `supports_multi_nic` derivation from manager registrations: TC-FR4-01 | Existing `pkg/networkmanager/networkmanager_test.go` ("Resolve (TC-REG-01)"; the `security_group_icmp` intersection is the pattern) | `make test` (`osac-operator/`) | Resolution logic | Registrations are in-memory fixtures | Not run |
| M5 | osac-operator / Envtest / [DEV] | NetworkClass capability status, role selection for Subnet tasks, handoff gating, binding validation, VM composition, namespace labels, per-attachment feedback, CRD rules: TC-FR1-03, TC-FR1-04, TC-FR4-02, TC-FR4-07, TC-FR8-01, TC-FR8-02, TC-FR9-01, TC-FR9-02, TC-FR9-03, TC-FR9-05, TC-FR9-06, TC-FR10-02 | Existing `internal/controller/networkclass_controller_test.go`, `networking_resources_test.go` (Describe "Subnet controller"), `computeinstance_networking_test.go` ("ComputeInstance VMaaS networking"), `computeinstance_feedback_controller_test.go` (Context "network attachment IP feedback"), `computeinstance_validation_test.go` ("ComputeInstance CEL Validation", "MaxItems validation") | `make test` (`osac-operator/`) | Kubernetes API server, etcd, loaded CRDs, in-process reconcilers | AAP job results, VMI status and Fulfillment responses are test-controlled | Not run |
| M6 | osac-operator / Component integration (Kind) / [DEV] | Installed CRD accepts multi-attachment with one primary and rejects the rest: TC-FR4-09 | Existing `test/integration/networking_crd_validation_test.go` | Deploy the current operator into Kind, then `make integration-tests` (`osac-operator/`); CI: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=operator` (repository root) | Installed operator, CRDs and API server | Fulfillment client disabled; no AAP or provider | Not run |
| M7 | osac-aap / Unit (isolated role transform) / [DEV] | `ocp_virt_vm` renders the OOB static address and no OOB gateway: TC-FR6-01 | Existing `collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tests/test.yml`; new test *proposed* there | *Proposed:* register the new test in `make test` the way Tests 15-17 are registered (`osac-aap/`) | Real role tasks and templates | No Kubernetes objects | Not run. `tests/integration/run_tests.sh` runs only Tests 15-17 of this file, so the new test must be registered or it never runs |
| M8 | osac-aap / Component integration (Kind) / [DEV] | Multi-interface `vm_network` passthrough and cloud-init network data in the created VM: TC-FR6-02 | Existing target `tests/integration/targets/compute_instance_create/`; new task file *proposed* `tasks/multi_nic.yml` | *Proposed:* `uv run ansible-playbook targets/compute_instance_create/tasks/multi_nic.yml -e '@common_vars.yml'` (`osac-aap/tests/integration/`); also registered in `make test` | Ansible role tasks against real Kind APIs and CRDs | KubeVirt is not running (VM CR stored, not started); AAP controller not real | Not run |
| M9 | osac-aap / Component integration (Kind) / [DEV] | Localnet K8s manager tasks through `playbook_osac_network_task.yml`: TC-FR9-04 | *Proposed* target `tests/integration/targets/cudn_localnet/tasks/baseline.yml`, modelled on existing `targets/cudn_evpn/tasks/baseline.yml` | *Proposed:* `uv run ansible-playbook targets/cudn_localnet/tasks/baseline.yml -e '@common_vars.yml'` (`osac-aap/tests/integration/`) | Generic network task playbook, manager role, Kind API with the CUDN CRD | OVN-Kubernetes does not reconcile the CUDN in Kind (no NAD generated); fabric handoff is a fixture | **Blocked:** no localnet manager exists (`cudn_net/meta/osac.yaml` points to OSAC-1511); implementation epic [OSAC-1512](https://redhat.atlassian.net/browse/OSAC-1512) is New |
| M10 | osac-ui / Unit (Vitest) / [DEV] | Read-only details page with one row per attachment: TC-FR8-04 | Existing `libs/ui-components/src/components/vm/DetailsPage/VmNetworkingSection.test.tsx` | `pnpm test` (`osac-ui/`) | React component and row hook | API responses are fixtures | Not run |
| M11 | tests/e2e / E2E / [QE] | Managed primary-plus-OOB journey, shared OOB reuse, guest addressing, routing, ExternalIP, NAT, isolation, teardown, upgrade: TC-FR2-02, TC-FR3-01, TC-FR6-03, TC-FR7-01, TC-FR7-02, TC-FR7-03, TC-FR9-07, TC-FR9-08, TC-FR11-04 | *Proposed* `tests/e2e/networking/vmaas/test_vmaas_multi_nic.py` (see [E2E lab: LAB-MNIC](#e2e-lab-lab-mnic)), reusing the stack, SSH helper Pod and failure reporting of `test_vmaas_networking.py` | *Proposed:* `OSAC_E2E_OOB_MGMT_HOST=<addr> uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_multi_nic.py` (repository root, on the lab host); TC-FR11-04 is a manual procedure | Fulfillment, operator, AAP, KubeVirt, OVN-Kubernetes CUDN EVPN and Localnet, the primary Fabric Manager (L-1) and the OOB Fabric Manager on Cumulus VX, guest OS, out-of-cluster `oob-mgmt` host | Nodes, switches and routers are libvirt VMs or containers, not hardware; LVMS local storage, so no live migration | **Blocked:** needs the localnet manager (M9), the lab decisions L-1 and L-2 (OQ-13) and LAB-MNIC, which is not built and has no ticket — unresolved |
| M12 | tests/e2e / E2E / [QE] | Single-NIC regression on a deployment without the capability: TC-FR11-02 | Existing `tests/e2e/networking/vmaas/test_vmaas_networking.py` (`test_00`..`test_14`) | `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` (repository root); CI `/test vmaas-netris` | Fulfillment, operator, AAP, KubeVirt, CUDN EVPN, Netris | Nothing faked | Not run against this feature |
| M13 | fulfillment-service / Component integration (server/PostgreSQL) / [DEV] | BMaaS and Cluster attachment contracts unchanged: TC-FR11-03 | Existing `internal/servers/private_baremetal_instances_server_test.go`, `private_clusters_server_test.go`, `clusters_server_test.go` | `ginkgo run --timeout 10m internal/servers` (`fulfillment-service/`) | As in M1 | As in M1 | Not run |
| M14 | osac-operator / Envtest / [DEV] | ClusterOrder attachment contract unchanged: TC-FR11-05 | Existing `internal/controller/clusterorder_envtest_test.go` | `make test` (`osac-operator/`) | As in M5 | As in M5 | Not run |

## PRD versus the proposed implementation

No code implementing OSAC-6121 exists yet: no `osac` PR, and no fork branch
beyond the documentation change of osac #1841 (checked 2026-11-12). The
expected behaviour therefore comes from the open PRs, read as the intended
final behaviour:

- **PRD** — EP [#389](https://github.com/osac-project/enhancement-proposals/pull/389), head `68fbb4e`.
- **Design** — EP [#396](https://github.com/osac-project/enhancement-proposals/pull/396), head `dd3d852`, which carries the role framework of #393 plus the authoritative "OSAC-6121 Provider-Managed OOB Path" section. EP [#393](https://github.com/osac-project/enhancement-proposals/pull/393) has moved on since: its head `74a17f1` (2026-10-21) removes the provider-managed section, and nothing about the static address, `supports_multi_nic` or the shared OOB network remains in it (OQ-11).
- **Decisions** — osac [#1841](https://github.com/osac-project/osac/pull/1841), the `networking-decisions.md` update, which is more specific than the design about the handoff fields.

Where the three agree, the cases assert that behaviour. Where they disagree,
or the code on `main` differs, the cases cite the open question.

| FR | PRD says | Design (#396) and decisions (#1841) say | Verdict | Plan impact |
|---|---|---|---|---|
| FR-1 Roles | One NetworkClass maps each role to **one** Fabric Manager and one K8s Manager; VirtualNetwork `network_type` immutable; omitted type keeps the default managers for single-NIC | Same model (`network_types` field 13, `NetworkType`, VirtualNetwork `network_type` field 5, unknown roles rejected). But `NetworkType.fabric_manager` is optional ("Empty = no fabric manager") and the OOB example has none | Partly aligned: the Fabric Manager is mandatory in the PRD, optional in the design | OQ-1 (name clash), OQ-12; TC-FR1-01 to TC-FR1-04 |
| FR-2 Shared OOB | One shared OOB VirtualNetwork per deployment, reused by managed VMs; tenants cannot create or select others | Same; where its identity is configured is design open question 3; enforcement of "one" is not described | Aligned on intent; enforcement unspecified | OQ-6; TC-FR2-01, TC-FR2-02 |
| FR-3 Managed flow | Provider admin creates everything; tenant consumes; UI read-only with per-attachment status | Same actors and sequence (workflow steps 1-7). The design says nothing about the UI | UI only in the PRD | OQ-16; TC-FR3-01, TC-FR3-02, TC-FR8-04 |
| FR-4 Capability and cardinality | `supports_multi_nic` true only when the primary Fabric and CUDN managers and the OOB Fabric and localnet managers all advertise it; false/unset rejects >1 attachment; true allows eight with exactly one `primary`; single attachment implicitly primary, "identified on readback" | Same, plus: the provider may **disable** the computed value; computed by the existing capabilities intersection; the managed section requires the OOB role to resolve to "the fabric/localnet pair"; multiple OOB secondaries allowed on the shared OOB VirtualNetwork | Aligned, with two design additions; readback of an implicit primary unresolved | OQ-4, OQ-5, OQ-12; TC-FR4-01 to TC-FR4-09 |
| FR-5 Validation | Before persistence: primary Subnet READY and tenant-owned; OOB Subnet READY and in the shared OOB VirtualNetwork; provider authorization; unique Subnets; supported roles; **SecurityGroup readiness and alignment**; one primary; static address in CIDR and reserved | Same list, plus Subnets must have `network_binding` populated. OOB isolation is a provider MultiNetworkPolicy, and tenant SecurityGroup changes "cannot weaken" it; what a SecurityGroup on the OOB attachment means is not stated. On `main`, an attachment outside the tenant's default VirtualNetwork **requires** at least one SecurityGroup | Conflict on OOB SecurityGroups | OQ-14; TC-FR5-01 to TC-FR5-07 |
| FR-6 Static OOB address | Every OOB attachment has one provider-assigned IPv4, injected at creation, no default route, uniqueness via the provider's reservation process | Same (`static_ipv4_address` field 4; cloud-init on Linux; Windows only after Sysprep support), plus: the reported OOB address must equal the injected one before the VM is network-ready | Aligned; reservation source and primary-attachment case open | OQ-7, OQ-8, OQ-10; TC-FR6-01 to TC-FR6-03, TC-FR8-02 |
| FR-7 Routing | Primary is the default route, ExternalIP DNAT target and NAT path; OOB return path symmetric; routed OOB prefixes provider-supplied | Same in both | Aligned; route source open | OQ-9; TC-FR7-01 to TC-FR7-04 |
| FR-8 Status | One status entry per attachment (Subnet, IP); primary identifiable by the spec marker | Same, plus: correlate by interface identity, not order; legacy single-IP view keeps the primary IP; delayed guest data retries | Aligned | TC-FR8-01 to TC-FR8-05 |
| FR-9 Composition | VM reconciler renders from each `SubnetNetworkBinding`, no manager-specific branches; localnet manager creates a local NAD via the namespace-label contract | Same contract. #393 and #1841 say the VM reconciler composes; #396 also says "the AAP template loops over the attachments". Handoff: "the OSAC-4291 fabric-output ConfigMap pattern", carrying physical network name, VLAN ID and optional MTU (#1841). On `main` the operator composes, and the EVPN handoff travels in task results and Subnet/VirtualNetwork status, not a ConfigMap | Composition location and handoff mechanism conflict with `main` | OQ-2, OQ-3, OQ-15; TC-FR9-01 to TC-FR9-08 |
| FR-10 Immutability | Attachments, Subnets, primary and OOB address create-time-only; SecurityGroup updates unchanged | Same; CEL may enforce immutability, fulfillment stays authoritative | Aligned | TC-FR10-01, TC-FR10-02 |
| FR-11 Regression | Capability false/unset keeps OSAC-1435/OSAC-5557 behaviour; CaaS and BMaaS unchanged | Same; upgrade is additive, downgrade may orphan secondary Subnets | Aligned | TC-FR11-01 to TC-FR11-05 |

## Contract drift and open questions

The PRD and design describe how OSAC networking works, and the test cases
are written from them. In several places that description no longer matches
the code on the `main` branch of
[`osac-project/osac`](https://github.com/osac-project/osac) (checked
2026-11-12). This matters because a test asserts concrete things: a field name
and its meaning, an error message, a Kubernetes label, the component that does
the work. A test written from the design could therefore check something the
code never does, and fail even when the feature works. Or it could pass while
checking the wrong thing.

For example, the design adds a VirtualNetwork field `network_type` holding a
role such as `"workload"`. On `main`, `network_type` already exists on the
NetworkClass status and in manager registrations, with another meaning: the
segment type the managers share, such as `"evpn"` (OQ-1). Until the design
renames the new field or redefines the old one, TC-FR1-01 cannot say which
field and value to assert. Likewise, the design says the AAP template builds
the VM's interfaces, but on `main` the operator builds them and AAP only
copies them (OQ-3). That decides whether TC-FR9-01 is an operator Envtest or
an AAP integration test, and so which `[DEV]` story owns it.

The table lists each mismatch and each open decision, with the evidence and
the cases it affects; those cases cite the ID in their preconditions. They stay
in the plan, written against the behaviour the PRD intends. They should not
become release-blocking until the PRD or design resolves the item, and their
assertions may need updating then.

| ID | Issue | Evidence | Affected cases |
|---|---|---|---|
| OQ-1 | **`network_type` already means something else.** The design adds VirtualNetwork `network_type` as a role ("tenant", "secondary_vlan"). On `main`, `NetworkClass.status.network_type` is the segment type the managers share ("evpn"), manager registrations carry `network_types` as segment types, and Fabric `create_virtual_network` receives `network_type: evpn`. | `proto/private/osac/private/v1/network_class_type.proto` (field 7); `docs/agent-context/networking-decisions.md` ("EVPN handoff implementation status", "Manager registrations") | TC-FR1-01 to TC-FR1-04, TC-FR4-08, TC-FR5-05 |
| OQ-2 | **The design describes a dispatcher that no longer exists.** It uses a dispatcher, `set_stats` output and the registration label `osac.openshift.io/network/k8s-manager`. `main` runs every manager task through `playbook_osac_network_task.yml` with `osac_result`/`osac_error`, and registrations use `osac.openshift.io/network-k8s-manager`. Cases assert observable outcomes; field and label names wait for the aligned design. | `networking-decisions.md` ("There is no dispatcher and no per-manager or per-kind playbook") | TC-FR1-04, TC-FR9-03, TC-FR9-04, TC-FR9-05 |
| OQ-3 | **Where is the VM network spec composed?** The design says the AAP template loops over attachments. On `main` the operator composes `vm_network` (`vmNetwork()` in `computeinstance_controller.go`, one hard-coded interface) and `ocp_virt_vm` copies it unchanged. This plan places composition in the operator (Envtest, TC-FR9-01) and AAP passthrough in TC-FR6-02; if the design moves composition to AAP, TC-FR9-01 moves to row M8. | `osac-operator/internal/controller/computeinstance_controller.go`; `docs/testing/osac-aap.md` (`compute_instance_create` target: `vm_network` taken unchanged) | TC-FR9-01, TC-FR6-02 |
| OQ-4 | **Eight valid attachments vs the managed profile.** AC-5 requires eight valid attachments to pass. The design allows several OOB secondaries, but only on the shared OOB VirtualNetwork, and forbids duplicate Subnets, so eight means one primary plus seven OOB Subnets in that one VirtualNetwork, each with its own static address. Neither document says a shared OOB VirtualNetwork may hold seven Subnets, nor how the localnet manager maps several Subnets to VLANs. | PRD FR-4, AC-5; design "Validation Rules" 5 and "Scope and attachment model" | TC-FR4-05 |
| OQ-5 | **Readback of an implicit primary.** The PRD says "the spec marker identifies it on readback" for a single attachment, but the design says the marker is optional. Unspecified: does a stored single attachment read back with `primary: true`? | PRD FR-4; design "ComputeNetworkAttachment for the Managed OOB Path" | TC-FR4-06 |
| OQ-6 | **Identity and enforcement of the one shared OOB VirtualNetwork.** Where it is configured is design open question 3. Unspecified: is a second VirtualNetwork with the OOB role rejected, or merely unusable for attachments? | Design "Open questions for implementation" 3 | TC-FR2-01, TC-FR5-02 |
| OQ-7 | **Static address reservation source.** Which reservation system makes "already reserved" detectable is design open question 1. | Design open question 1; PRD assumption 1 | TC-FR5-06 (reservation step) |
| OQ-8 | **`static_ipv4_address` on the primary attachment, or missing on an OOB attachment.** The PRD says every OOB attachment has one; the reject behaviour for a primary attachment that carries one is unspecified. | PRD FR-6 | TC-FR5-06 |
| OQ-9 | **Routed OOB client prefixes.** Their source and encoding are design open question 4; until answered only directly connected OOB clients are testable. | Design open question 4 | TC-FR7-03 (routed part) |
| OQ-10 | **Supported guest OS.** Design open question 2. A Windows template with an OOB static address has no defined behaviour (reject, or provision without OOB address). | PRD assumption 2 | TC-FR6-01, TC-FR6-03; Windows not covered |
| OQ-11 | **The design PRs have diverged.** #393 and #396 both write `enhancements/OSAC-6121-vmaas-multi-nic/design.md`. #396 (head `dd3d852`) has the managed OOB path; #393's newer head `74a17f1` removes the provider-managed section and contains nothing about the static address, `supports_multi_nic` or the shared OOB network. If #393 merges as it stands, the merged design does not describe the PRD's feature. This plan follows #396. | PR heads; `git log ep-396..ep-393` | All |
| OQ-12 | **Is an OOB Fabric Manager mandatory, and how is the capability intersected?** The PRD and the design's managed section require the OOB role to resolve to a Fabric/localnet pair, and #1841 has the Fabric Manager configure the switch VLAN; but `NetworkType.fabric_manager` is optional and the design's own OOB example omits it. The design computes the capability with "the existing intersection behaviour", but the existing `security_group_icmp` intersection accepts an absent Kubernetes Manager, while `supports_multi_nic` must be false when any of the four managers is missing. | `osac-operator/pkg/networkmanager/networkmanager.go` (`SecurityGroupICMP()`); design `NetworkType` comment and NetworkClass example vs "NetworkClass capability and role mapping"; PRD FR-1, FR-4 | TC-FR1-03, TC-FR4-01 |
| OQ-13 | **Which Fabric Manager serves the OOB role in the lab?** The PRD needs an OOB Fabric Manager that configures the switch VLAN and publishes the handoff. `agentless_net` configures Cumulus VLANs but its registration says it advertises no Kubernetes network type and does not support VM overlays; Netris manages the simulated fabric but not a separate OOB switch. Either an existing manager gains the OOB role and handoff, or the lab needs a new one. | `osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/meta/osac.yaml`; PRD FR-4 | TC-FR2-02, TC-FR3-01, TC-FR7-03, TC-FR9-07, TC-FR9-08 |
| OQ-14 | **SecurityGroups on the OOB attachment.** The PRD validates SecurityGroup readiness and alignment for every attachment. On `main`, an attachment whose Subnet is outside the tenant's default VirtualNetwork must list at least one SecurityGroup ("at least one SecurityGroup is required for a Subnet outside the tenant's default VirtualNetwork"), and the OOB VirtualNetwork is always outside it. The design isolates OOB with a provider MultiNetworkPolicy and leaves SecurityGroups on secondary networks open (design open question 2). Unspecified: are OOB SecurityGroups required, optional or rejected; who owns them (the OOB VirtualNetwork is provider-owned); and does the localnet manager enforce them? | `fulfillment-service/internal/servers/network_attachment_resolution.go`; PRD FR-5; design open question 2 | TC-FR5-04, TC-FR9-07, ATT-PAIR fixture |
| OQ-15 | **Handoff mechanism.** The design and #1841 say the OOB Fabric Manager publishes its output through "the existing OSAC-4291 fabric-output ConfigMap pattern". On `main` the OSAC-4291 handoff is not a ConfigMap: the Fabric task result is recorded in `Subnet.status.networkSegment` and `VirtualNetwork.status.l3Vni` and passed to the Kubernetes task as `network_segment` and the VirtualNetwork snapshot. #1841 names the fields (physical network name, VLAN ID, optional MTU); the design adds bridge mapping identity, readiness and a schema version. | `osac-aap/.../roles/cudn_evpn/README.md`; `networking-decisions.md` "EVPN handoff implementation status"; design "Provider Admin workflow and fabric handoff" 3-4 | TC-FR9-04, TC-FR9-05 |
| OQ-16 | **UI not in the design.** The PRD puts per-attachment status on the existing read-only ComputeInstance details surface (FR-3, In Scope); the design has no UI section, and a reviewer asked on #389 for the UI to be part of the PRD. TC-FR8-04 follows the PRD. | PRD FR-3; #389 review thread (ygalblum, 2026-10-15) | TC-FR8-04 |

## E2E lab: LAB-MNIC

The E2E cases (rows M11 and M12) run on LAB-MNIC: a common OSAC VMaaS lab
topology, an OpenShift cluster on three libvirt VMs on one KVM host, extended
with extra libvirt networks for the fabric and OOB paths. This section is the
target layout. **Status: not built; no ticket.**

### Base

| Item | Requirement |
|---|---|
| Host | One RHEL-family KVM host. Sizing: the three-master cluster plus about 10 GiB RAM and 4 vCPU for the lab additions below, without CPU oversubscription |
| Cluster | OpenShift 4.22, three schedulable masters (`master-0..2`) as libvirt VMs, no workers |
| Network | One libvirt network for the cluster: machine network, API/apps VIPs, MetalLB L2 pool |
| OSAC | osac-installer `vmaas-ci` profile (LVMS, CNV); provider networking enabled once the primary fabric (L-1) is in place |

Three nodes, unlike the single-node Netris CI lab, let the plan prove the OOB
bridge mapping and OOB isolation across nodes.

### Added libvirt networks and VMs

Each master VM gets two extra NICs (libvirt `attach-interface --persistent`,
then a node reboot through the MachineConfigPool or NMState). All new networks
are libvirt networks with no DHCP and no host address unless stated.

| # | Name | Attached to | Purpose |
|---|---|---|---|
| N1 | `mnic-underlay` (`10.250.0.0/24`) | NIC 2 of each master; NIC 1 of `fabric-gw` | Fabric underlay: node uplink and VTEP addresses, BGP/EVPN sessions to the fabric (installer `evpn.enabled: true`, `vtepCIDR`, per-node uplink) |
| N2 | `mnic-oob-trunk` | NIC 3 of each master; `swp1`-`swp3` of `oob-leaf` | Physical OOB network: NMState creates OVS bridge `br-oob` on NIC 3 of every node with the OVN bridge mapping `oob-physnet:br-oob` |
| N3 | `mnic-oob-access` | `swp4` of `oob-leaf`; `eth0` of `oob-mgmt` | Access side of the OOB VLAN where the management host sits |
| V1 | `fabric-gw` VM (2 vCPU, 4 GiB) | N1 and the cluster network | The primary-network fabric (see L-1): EVPN peer and gateway for the tenant VRFs, NAT to the outside |
| V2 | `oob-leaf` (Containerlab Cumulus VX on the host, about 2 GiB) | N2 (`swp1`-`swp3`, trunk VLAN 100) and N3 (`swp4`, access VLAN 100) | The switch the OOB Fabric Manager configures, as in the OSAC-3664 AgentlessNet lab |
| V3 | `oob-mgmt` VM (1 vCPU, 2 GiB) | N3 (`172.16.0.1/24`) and the cluster network (SSH from the pytest host) | The out-of-cluster OOB client of PRD FR-7 |

Budget: about 10 GiB RAM and 4 vCPU beyond the base cluster. A host whose
masters already oversubscribe its CPUs needs smaller masters first.

### Lab decisions

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| L-1 | **Primary-network Fabric Manager.** `cudn_evpn` needs a Fabric Manager that returns the L2/L3 VNIs and serves the EVPN peer; the only one today is `netris`. A deployable mock exists only as a test fixture (`osac-aap/tests/integration/targets/network_task_playbook`). | (a) Run the Netris simulated fabric (`osac-test-infra/infra/netris`) on the same host and connect N1 to a Netris leaf, so `fabric-gw` is replaced by Netris softgates; (b) `fabric-gw` running FRR as EVPN peer plus a lab-only Fabric Manager role that allocates VNIs and configures FRR | (a): it matches the `vmaas-netris` CI and keeps ExternalIP and NAT real; (b) needs a new manager that no product ships |
| L-2 | **OOB Fabric Manager** (OQ-13). | `agentless_net` extended for the OOB role and handoff, or a new manager | Decide in the design; the lab only needs one that configures VLAN 100 on `oob-leaf` |
| L-3 | **Routed ExternalIPPool.** | From the Netris softgates (L-1 a) or a `/29` on N1 routed by `fabric-gw` (L-1 b) | Follows L-1 |

### Addresses

| Item | Value |
|---|---|
| OOB VirtualNetwork / Subnet (VN-OOB / SUB-OOB) | `172.16.0.0/24` |
| Physical network name / VLAN | `oob-physnet` / `100` |
| `oob-mgmt` | `172.16.0.1` |
| VM-A (tenant `t1`) / VM-B (tenant `t2`) OOB addresses | `172.16.0.21` / `172.16.0.22` |
| Workload Subnets | `t1`: `10.10.1.0/24`; `t2`: `10.20.1.0/24` |
| Node underlay / VTEP addresses | `10.250.0.11`-`.13` on N1 |
| Routed ExternalIPPool | `OSAC_EXTERNAL_IP_POOL_CIDR`, per L-3 |

### Lab acceptance (before any case runs)

These checks prove the lab, not OSAC, so a later failure points at the feature:

1. `oc get nncp` shows the `br-oob` policy `Available` on all three nodes; on each node `oc debug node/<n> -- chroot /host ovs-vsctl get open . external_ids:ovn-bridge-mappings` contains `oob-physnet:br-oob`.
2. A hand-made Localnet CUDN on `oob-physnet`, VLAN 100, IPAM disabled, selecting a scratch namespace, and one Fedora test VM per node there (`172.16.0.250`-`.252`, pinned with `nodeSelector`): `oob-mgmt` pings all three. Delete them afterwards.
3. `oob-leaf` (`nv show interface swp1 bridge`) carries VLAN 100 only after the OOB Fabric Manager ran for SUB-OOB.
4. The single-NIC suite `test_vmaas_networking.py` passes (this is TC-FR11-02), which proves the primary EVPN path, ExternalIP and NAT.

### Suite shape

*Proposed* `tests/e2e/networking/vmaas/test_vmaas_multi_nic.py`, one ordered
module like `test_vmaas_networking.py`: module fixtures create the networks and
both tenants' resources (`stack.run_parallel`, every child waits for its parent
READY in the CR and the API), and the numbered tests run serially with `-x`.
Cleanup does not depend on reaching the last test: as in
`test_vmaas_networking.py`, the module fixtures register finalizers that delete
whatever is left (VMs, Subnets, VirtualNetworks, address reservations, and the
`oob-leaf` VLAN through the OOB Fabric Manager), so a stop at the first failure
still cleans up. `test_08` runs the teardown in dependency order and asserts
that nothing is left; when it is reached, the finalizers find nothing to do.
`OSAC_E2E_KEEP_RESOURCES=true` skips both for debugging, as in the existing
suite. Guest commands on the
primary network go through the existing SSH helper Pod; OOB probes run on
`oob-mgmt` over SSH from the pytest host. A failure snapshot also records
`oob-leaf` VLAN state and the node bridge mappings
(`OSAC_E2E_FABRIC_SNAPSHOT_CMD`).

- **Command (proposed):** `OSAC_E2E_OOB_MGMT_HOST=<oob-mgmt address> uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_multi_nic.py` (repository root, on the lab host).
- **CI:** none. Like the AgentlessNet VLAN lab, this is a local deployed-lab run until a CI backend exists.
- **Order:** `test_00` lab and capability preflight → `test_01` TC-FR3-01 → `test_02` TC-FR6-03 → `test_03` TC-FR7-01 → `test_04` TC-FR7-02 → `test_05` TC-FR7-03 → `test_06` TC-FR2-02 → `test_07` TC-FR9-07 → `test_08` TC-FR9-08 (teardown).
- **Phases.** The lab runs three phases in order, each against the build and network setup its cases need:
  1. **Upgrade (TC-FR11-04):** the previous OSAC release with the primary fabric only, and two single-NIC VMs created on it; then upgrade to the feature build and run the post-upgrade checks.
  2. **Single-NIC regression (TC-FR11-02):** the feature build, a NetworkClass without `network_types`, and no OOB networks (N2, N3, V2, V3) or OOB managers yet; run `test_vmaas_networking.py`.
  3. **Multi-NIC (this module):** add the OOB networks and managers and NC-MULTI, then run `test_vmaas_multi_nic.py`.

## Test Cases

Common fixtures (referred to by name in the cases):

- **NC-MULTI:** the deployment NetworkClass with top-level `fabric_manager`/`k8s_manager` and two roles: `workload` → (`netris`, `cudn_evpn`), `supports_primary: true`, `supports_secondary: false`; `oob` → (`<oob fabric manager>`, `cudn_localnet`), `supports_primary: false`, `supports_secondary: true`. Role names are placeholders pending OQ-1.
- **VN-W / SUB-W:** tenant `t1` VirtualNetwork with role `workload`, CIDR `10.10.0.0/16`, Subnet `10.10.1.0/24`, READY; SecurityGroup **SG-W** in VN-W, READY.
- **VN-OOB / SUB-OOB:** the provider-owned shared OOB VirtualNetwork with role `oob`, CIDR `172.16.0.0/24`, Subnet `172.16.0.0/24`, READY; SecurityGroup **SG-OOB** in VN-OOB, READY, if the design keeps SecurityGroups on OOB attachments.
- **ATT-PAIR:** `network_attachments: [{subnet: SUB-W, security_groups: [SG-W], primary: true}, {subnet: SUB-OOB, security_groups: [SG-OOB], static_ipv4_address: "172.16.0.21"}]`.
- **Provider caller:** the provider-admin identity allowed to create managed ComputeInstances for `t1`. **Tenant caller:** a `t1` tenant user.

### FR-1: Role-based network selection

#### TC-FR1-01: VirtualNetwork accepts a known role and rejects an unknown one

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Depends on OQ-1.
- NetworkClass NC-MULTI exists.

##### Steps

1. `VirtualNetworks/Create` (private) with `spec.network_type: "workload"`, CIDR `10.10.0.0/16`.
2. `VirtualNetworks/Get` on the returned ID.
3. `VirtualNetworks/Create` with `spec.network_type: "storage"` (not in NC-MULTI).
4. `VirtualNetworks/Create` with `network_type` omitted.

##### Expected Results

- Step 1 succeeds; step 2 returns `network_type: "workload"`.
- Step 3 fails with `INVALID_ARGUMENT` naming `spec.network_type` and the unknown value; `VirtualNetworks/List` shows no new VirtualNetwork.
- Step 4 succeeds with `network_type` unset (top-level managers apply).

#### TC-FR1-02: VirtualNetwork role is immutable

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | medium | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1.
- VN-W exists with role `workload`.

##### Steps

1. `VirtualNetworks/Update` VN-W with `spec.network_type: "oob"` and an update mask containing `spec.network_type`.
2. `VirtualNetworks/Update` VN-W setting `network_type` to empty.
3. `VirtualNetworks/Get` VN-W.

##### Expected Results

- Steps 1 and 2 fail with `INVALID_ARGUMENT` stating the field is immutable.
- Step 3 still returns `network_type: "workload"` and an unchanged `metadata.version`.

#### TC-FR1-03: NetworkClass rejects duplicate roles and unregistered managers

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (`networkclass_controller_test.go`). Depends on OQ-1.
- Registration ConfigMaps for `netris` and `cudn_evpn` exist; none for `cudn_localnet`.

##### Steps

1. Create a NetworkClass CR whose `network_types` lists `workload` twice.
2. Create a NetworkClass CR with role `oob` → `k8s_manager: cudn_localnet`.
3. Add a `cudn_localnet` registration ConfigMap; wait for reconcile.

##### Expected Results

- Step 1 is rejected (admission or `Ready=False`, reason naming the duplicate role `workload`).
- Step 2 reaches `Ready=False` with a message naming the unregistered manager `cudn_localnet`.
- After step 3 the NetworkClass becomes `Ready=True` with both roles resolved in status.

#### TC-FR1-04: Subnet manager tasks follow the VirtualNetwork role

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | critical | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (Describe "Subnet controller" in `networking_resources_test.go`). Depends on OQ-1, OQ-2.
- NC-MULTI resolved; VN-W, VN-OOB and a VirtualNetwork VN-D without `network_type`.

##### Steps

1. Create a Subnet in each of VN-W, VN-OOB and VN-D.
2. Inspect the network task jobs the operator creates for each Subnet (manager and `ansible_role` in the task input).

##### Expected Results

- SUB-W tasks run `netris` then `cudn_evpn`.
- SUB-OOB tasks run the OOB Fabric Manager then `cudn_localnet`, and never `cudn_evpn`.
- VN-D Subnet tasks run the top-level managers, matching the behaviour before this feature.

### FR-2: One shared OOB network

#### TC-FR2-01: Only the provider identity can use the shared OOB VirtualNetwork

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-2, AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (deployed) / [DEV]. Row M2 (*proposed* `it/it_compute_multi_nic_test.go`). Depends on OQ-6. Must not skip with provider networking disabled; see row M2.
- Capability `supports_multi_nic` true (fixture); VN-OOB configured as the shared OOB network; SUB-W in `t1`.

##### Steps

1. As **Tenant caller**, `ComputeInstances/Create` (public) with ATT-PAIR.
2. As **Tenant caller**, `VirtualNetworks/Create` with role `oob`.
3. As **Provider caller**, `ComputeInstances/Create` (private) for `t1` with ATT-PAIR.

##### Expected Results

- Step 1 fails with `PERMISSION_DENIED` (or `INVALID_ARGUMENT` naming `spec.network_attachments[1].subnet`) and no ComputeInstance is stored.
- Step 2 fails; the tenant cannot create an OOB-role network (PRD FR-2). Exact code waits on OQ-6.
- Step 3 succeeds; the stored instance carries tenant `t1` and both attachments.

#### TC-FR2-02: Two tenants' managed VMs share the OOB network; an unrelated namespace gets no NAD

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-2, AC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_06`. **Blocked** (localnet manager, lab not built).
- VM-A of `t1` from TC-FR3-01 is READY; tenant `t2` has its workload VirtualNetwork, Subnet `10.20.1.0/24` and SecurityGroup READY; namespace `mnic-unrelated` exists with no VM.

##### Steps

1. As **Provider caller**, create VM-B for `t2` with a primary attachment on `t2`'s Subnet and an OOB attachment on SUB-OOB with `static_ipv4_address: "172.16.0.22"`; wait for `READY`.
2. `oc get vmi -A -o wide` for VM-A and VM-B. If both run on the same node, delete and recreate VM-B, at most twice; if they still share a node, stop the case and report it **inconclusive** for the cross-node path (the remaining checks run, but the result does not claim cross-node coverage).
3. `oc get net-attach-def -A -o wide` and `oc get ns -L <binding label key>`.
4. `oc get clusteruserdefinednetwork -o yaml` for the OOB CUDN.
5. From `oob-mgmt`, `ping -c 3 172.16.0.21` and `ping -c 3 172.16.0.22`.

##### Expected Results

- VM-A and VM-B run on different nodes after step 2; otherwise the case is inconclusive for the cross-node path, not passed.
- VM-B is READY within the VMaaS ready timeout of `test_vmaas_networking.py`; VM-A is unaffected (no restart; `ComputeInstances/Get` unchanged).
- The OOB NAD exists in VM-A's and VM-B's primary namespaces and not in `mnic-unrelated`; only those two namespaces carry the binding label.
- There is still exactly one OOB CUDN; its `namespaceSelector` is the binding label, not a namespace list.
- Both pings from `oob-mgmt` succeed.

### FR-3: Managed creation flow

#### TC-FR3-01: Provider admin creates a managed primary-plus-OOB VM end to end

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-3, AC-6, AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_01`. **Blocked** (localnet manager, lab not built).
- `test_00` passed: NC-MULTI is READY with `supports_multi_nic: true`; VN-W/SUB-W (`10.10.1.0/24`), SG-W (tcp/22 ingress), VN-OOB/SUB-OOB and SG-OOB are READY in the API and the CR; `oob-leaf` carries VLAN 100 on `swp1`; `172.16.0.21` is reserved for VM-A.
- Linux VM template with cloud-init; the routed ExternalIPPool is READY.

##### Steps

1. As **Provider caller**, `ComputeInstances/Create` (private) for `t1` with ATT-PAIR and `auto_external_ip_attachment: true`.
2. Wait for `READY` in the API.
3. `oc get vm <name> -n <SUB-W namespace> -o yaml`.
4. `ComputeInstances/Get` as **Provider caller**, and again as **Tenant caller** (public).
5. `osac get computeinstance <name> -o yaml` as **Tenant caller**.

##### Expected Results

- READY within the VMaaS ready timeout of `test_vmaas_networking.py`.
- The VM is in SUB-W's namespace. `spec.template.spec.networks`: one `pod: {}` and one `multus.networkName` equal to SUB-OOB's `status.network_binding.nad_name`, which exists in that namespace. `interfaces`: `binding.name: l2bridge` on the primary and `bridge: {}` on the OOB network.
- Both API reads and the CLI show two `compute_network_attachment_statuses`: SUB-W with a `10.10.1.x` address, SUB-OOB with `172.16.0.21`; `spec.network_attachments[0].primary` is `true`.

#### TC-FR3-02: A tenant cannot add or change attachments of a managed VM

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-8 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (deployed) / [DEV]. Row M2. Must not skip with provider networking disabled; see row M2.
- Managed VM created by **Provider caller** with ATT-PAIR.

##### Steps

1. As **Tenant caller**, `ComputeInstances/Update` (public) removing the OOB attachment.
2. As **Tenant caller**, `ComputeInstances/Update` changing `static_ipv4_address` to `172.16.0.30`.
3. As **Tenant caller**, `ComputeInstances/Get`.

##### Expected Results

- Steps 1 and 2 fail with `INVALID_ARGUMENT` (immutable field); the stored attachments are unchanged.
- Step 3 returns both attachments and statuses (the tenant can read, PRD tenant story 2).

### FR-4: Capability and cardinality

#### TC-FR4-01: `supports_multi_nic` is true only when all four managers declare it

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV]. Row M4. Depends on OQ-12.
- In-memory registrations for primary Fabric, primary K8s (`cudn_evpn`), OOB Fabric and OOB K8s (`cudn_localnet`).

##### Steps

1. Resolve NC-MULTI with every combination of the four managers declaring or not declaring the capability token (16 cases, table-driven).
2. Remove one registration at a time, each run with the other three declaring the token: the primary Fabric Manager (`netris`), the primary Kubernetes Manager (`cudn_evpn`), the OOB Fabric Manager, and `cudn_localnet`.
3. Resolve a NetworkClass with no `network_types`.
4. Resolve NC-MULTI with the `oob` role's `fabric_manager` empty and `cudn_localnet` declaring the token.

##### Expected Results

- Only the case where all four declare it yields true; the other 15 yield false.
- Each of the four runs of step 2 yields false, and step 3 yields false.
- Step 4 yields false: the managed path needs an OOB Fabric Manager (PRD FR-4, design managed section; OQ-12).

#### TC-FR4-02: The operator records the capability and honours the provider disable

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (`networkclass_controller_test.go`, pattern "records security_group_icmp true when every manager declares it").
- All four registrations declare the capability.

##### Steps

1. Create NC-MULTI; wait for reconcile.
2. Set the provider disable control (shape per design "A provider may disable the computed capability").
3. Clear the provider disable control.
4. Remove the capability token from the `cudn_localnet` registration (replace the immutable ConfigMap).

##### Expected Results

- After step 1 NetworkClass status reports `supportsMultiNic: true`.
- After step 2 it reports false even though all managers declare it.
- After step 3 it reports true again.
- After step 4, with no disable set, it reports false because one manager no longer declares the token.

#### TC-FR4-03: Fulfillment exposes the capability read-only

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1 | medium | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1.
- NetworkClass stored with operator-reported `supports_multi_nic: false`.

##### Steps

1. Private `NetworkClasses/Update` setting `status.supports_multi_nic: true` through the public or tenant-facing path.
2. `NetworkClasses/Get`.

##### Expected Results

- Step 1 is rejected or ignores the status field; step 2 still returns false. Tenants cannot set or override the value (PRD FR-4).

#### TC-FR4-04: Capability false or unset rejects two attachments before persistence

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1; extends the existing multi-attachment reject in Context `network_attachments` of `private_compute_instances_server_test.go`.
- Run once with `supports_multi_nic: false` and once with it unset.

##### Steps

1. `ComputeInstances/Create` with ATT-PAIR and `auto_external_ip_attachment: true`.
2. `ComputeInstances/Get` on the requested ID; `ExternalIPs/List` for `t1`.

##### Expected Results

- Step 1 fails with `INVALID_ARGUMENT`; the message keeps the current text "at most one network attachment is supported" or its documented successor.
- Get returns `NOT_FOUND`; no ExternalIP was created.

#### TC-FR4-05: Capability true accepts eight attachments and rejects nine

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Depends on OQ-4.
- `supports_multi_nic: true`; SUB-W plus OOB Subnets SUB-OOB-1 to SUB-OOB-8 in VN-OOB, all READY.

##### Steps

1. Create with SUB-W (primary) plus SUB-OOB-1 to SUB-OOB-7, each with a distinct static address.
2. Create with SUB-W plus SUB-OOB-1 to SUB-OOB-8.

##### Expected Results

- Step 1 succeeds with eight stored attachments in request order.
- Step 2 fails with `INVALID_ARGUMENT` naming the eight-attachment limit; nothing is stored.

#### TC-FR4-06: Primary marker rules

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Readback step depends on OQ-5.
- `supports_multi_nic: true`.

##### Steps

1. Create with ATT-PAIR but no `primary` on either attachment.
2. Create with `primary: true` on both.
3. Create with `primary: false` on SUB-W and `primary: true` on SUB-OOB.
4. Create with only SUB-W and no `primary`; then `Get`.

##### Expected Results

- Steps 1 and 2 fail with `INVALID_ARGUMENT` stating exactly one primary is required.
- Step 3 fails because the `oob` role has `supports_primary: false` (message names `spec.network_attachments[1]`).
- Step 4 succeeds; on readback the attachment is identified as primary (`primary: true` or unset, per OQ-5).

#### TC-FR4-07: CRD enforces eight items and exactly one primary

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5; extends "should reject multiple networkAttachments" and "MaxItems validation" in `computeinstance_validation_test.go`.

##### Steps

1. Create a ComputeInstance CR with two `networkAttachments`, one `primary: true`.
2. Create one with two attachments and no primary; one with two primaries.
3. Create one with nine attachments.
4. Create one with two attachments on the same `subnetRef`.

##### Expected Results

- Step 1 is admitted (the current "at most one network attachment" rule no longer blocks it).
- Steps 2-4 are rejected with admission messages naming the primary rule, the item limit and Subnet uniqueness respectively.

#### TC-FR4-08: Only the primary-plus-shared-OOB combination is accepted

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Depends on OQ-1.
- `supports_multi_nic: true`; a second tenant VirtualNetwork VN-W2 (role `workload`) with Subnet SUB-W2; VN-D without `network_type` with Subnet SUB-D; a provider VirtualNetwork VN-X with role `oob` that is **not** the configured shared OOB network.

##### Steps

1. Create with SUB-W (primary) + SUB-W2.
2. Create with SUB-D (primary) + SUB-OOB.
3. Create with SUB-W (primary) + a Subnet of VN-X.

##### Expected Results

- All three fail with `INVALID_ARGUMENT` naming the offending attachment index; step 2 states that multi-attachment requests need an explicit `network_type`.

#### TC-FR4-09: Installed CRD on Kind accepts a valid pair and rejects a pair without primary

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | medium | automated |

##### Preconditions

- **Tier / owner:** Component integration (Kind) / [DEV]. Row M6 (`test/integration/networking_crd_validation_test.go`).

##### Steps

1. Apply a ComputeInstance CR with two attachments and one primary.
2. Apply one with two attachments and no primary.

##### Expected Results

- Step 1 is stored; step 2 is rejected by the installed CRD, with the same message as TC-FR4-07.

### FR-5: Validation

#### TC-FR5-01: Primary Subnet must belong to the tenant and be READY

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1; extends Context "NetworkAttachments validation".
- `supports_multi_nic: true`; SUB-T2 is a READY Subnet of tenant `t2`; SUB-PEND is a `t1` Subnet in state PENDING.

##### Steps

1. Create for `t1` with SUB-T2 (primary) + SUB-OOB.
2. Create for `t1` with SUB-PEND (primary) + SUB-OOB.

##### Expected Results

- Step 1 fails with `INVALID_ARGUMENT` or `NOT_FOUND` for `spec.network_attachments[0].subnet` without revealing `t2` data.
- Step 2 fails with `FAILED_PRECONDITION` or `INVALID_ARGUMENT` stating the Subnet is not READY. Nothing is stored in either case.

#### TC-FR5-02: OOB Subnet must be READY and in the shared OOB VirtualNetwork

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Depends on OQ-6.
- SUB-OOB-PEND is a PENDING Subnet of VN-OOB.

##### Steps

1. Create with SUB-W (primary) + SUB-OOB-PEND.
2. Create with SUB-W (primary) + SUB-W2 marked secondary (not in VN-OOB).

##### Expected Results

- Both fail before persistence; the messages name `spec.network_attachments[1].subnet`, giving "not READY" and "not in the shared OOB VirtualNetwork" respectively.

#### TC-FR5-03: Duplicate Subnet references are rejected

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1.

##### Steps

1. Create with SUB-W (primary) + SUB-OOB (`172.16.0.21`) + SUB-OOB (`172.16.0.22`).
2. Repeat referencing SUB-OOB once by ID and once by name.

##### Expected Results

- Both fail with `INVALID_ARGUMENT` stating the Subnet is listed twice.

#### TC-FR5-04: SecurityGroups must be READY and in their attachment's VirtualNetwork

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1; same assertions as the existing single-attachment SG specs, now on index 1. Depends on OQ-14: if OOB SecurityGroups are rejected or optional, step 1 and step 2 change to that rule.
- SG-PEND is a PENDING SecurityGroup in VN-OOB.

##### Steps

1. Create with ATT-PAIR but SG-W on the OOB attachment.
2. Create with ATT-PAIR but SG-PEND on the OOB attachment.

##### Expected Results

- Step 1 fails with "belongs to another VirtualNetwork than Subnet" prefixed by `spec.network_attachments[1]`.
- Step 2 fails with a not-READY message for that SecurityGroup.

#### TC-FR5-05: Role position support is enforced

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Depends on OQ-1.
- NC-MULTI as defined (`workload` primary-only, `oob` secondary-only).

##### Steps

1. Create with SUB-OOB marked `primary: true` and SUB-W secondary.
2. Create with SUB-W primary and a second `workload` Subnet in VN-W as secondary.

##### Expected Results

- Step 1 fails: role `oob` cannot be primary.
- Step 2 fails: role `workload` cannot be secondary (and is a second Subnet outside the shared OOB network).

#### TC-FR5-06: Static OOB address validation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1. Steps 6 and 7 depend on OQ-7 and OQ-8.
- `172.16.0.21` is already used by an existing managed VM.

##### Steps

Create with ATT-PAIR, varying only the OOB `static_ipv4_address`:

1. `172.17.0.5` (outside `172.16.0.0/24`).
2. `172.16.0.300` (malformed).
3. `fd00::5` (IPv6, out of scope).
4. `172.16.0.0` and `172.16.0.255` (network and broadcast).
5. Omitted.
6. `172.16.0.21` (already reserved).
7. Valid OOB address plus `static_ipv4_address: "10.10.1.50"` on the primary attachment.

##### Expected Results

- Steps 1-6 fail with `INVALID_ARGUMENT` naming `spec.network_attachments[1].static_ipv4_address` and the reason (outside CIDR, malformed, not IPv4, reserved address, required, already reserved).
- Step 7 behaviour is defined by OQ-8; the plan expects rejection.
- No ComputeInstance or ExternalIP is stored for any step.

#### TC-FR5-07: Rejected requests persist nothing in a deployed Fulfillment

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-4, AC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (deployed) / [DEV]. Row M2; pattern of "rejects multiple ComputeInstance network attachments without persisting the instance" in `it/it_compute_subnet_test.go`. Must not skip with provider networking disabled; see row M2.
- Deployed Fulfillment with the capability fixture true.

##### Steps

1. As **Provider caller**, Create with ATT-PAIR, `auto_external_ip_attachment: true` and an OOB address outside the CIDR.
2. As **Tenant caller**, Create with ATT-PAIR.
3. `ComputeInstances/List` and `ExternalIPs/List` for `t1` after each step.

##### Expected Results

- Step 1 fails with `INVALID_ARGUMENT`; step 2 fails with `PERMISSION_DENIED` or `INVALID_ARGUMENT`.
- Lists show no new ComputeInstance and no auto-created ExternalIP.

### FR-6: Static OOB address

#### TC-FR6-01: `ocp_virt_vm` renders the static OOB address without an OOB gateway

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-3, AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit (isolated role transform) / [DEV]. Row M7. Depends on OQ-10.
- `osac_job_vars` with two attachments: primary `subnetRef` SUB-W; OOB `subnetRef` SUB-OOB, `staticIPv4Address: 172.16.0.21`, prefix 24.

##### Steps

1. Run the role's build tasks with a Linux template.
2. Inspect the rendered cloud-init NoCloud `networkData`.

##### Expected Results

- `networkData` configures the OOB interface (matched by MAC or interface name, not by position) with `172.16.0.21/24` and no `gateway4`/default route.
- The primary interface keeps DHCP; user `userData` is unchanged.

#### TC-FR6-02: Kind-created VM carries two interfaces and the network data Secret

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-3 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (Kind) / [DEV]. Row M8. Depends on OQ-3.
- Operator-shaped `vm_network` with two networks (`pod: {}`, `multus: {networkName: oob-nad}`) and two interfaces (`l2bridge`, `bridge: {}`).

##### Steps

1. Run the `compute_instance_create` workflow with the *proposed* `multi_nic.yml` task file.
2. `kubectl get vm -o yaml` and the cloud-init Secret in the target namespace.

##### Expected Results

- The VM's `networks` and `interfaces` equal the input in order and content.
- The cloud-init Secret contains `networkdata` with the OOB static address, and carries the `osac.openshift.io/tenant` annotation.

#### TC-FR6-03: Guest OOB interface has the static address and no default route, across a restart

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-3, AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_02`. **Blocked**. Linux guest only (OQ-10).
- VM-A from TC-FR3-01 is READY.

##### Steps

1. Through the SSH helper Pod, `ssh` to VM-A's primary address and run `ip -4 -o addr show`, `ip route show default` and `ip -4 route show table all | grep 172.16.0`.
2. `virtctl restart <vm> -n <ns>`; wait for READY; repeat step 1.
3. `ComputeInstances/Get` after the restart.

##### Expected Results

- Exactly one interface has `172.16.0.21/24` and it is the interface whose MAC matches the VMI's OOB interface (not identified by position).
- There is exactly one default route and it uses the primary interface; `172.16.0.0/24` is only a connected route on the OOB interface.
- After the restart the addresses, routes and status entries are unchanged.

### FR-7: Primary routing and external access

#### TC-FR7-01: ExternalIP ingress reaches the primary address

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_03`. **Blocked**.
- VM-A from TC-FR3-01 with `auto_external_ip_attachment: true`; the routed pool of lab decision L-3.

##### Steps

1. Wait for the automatic ExternalIP to be ALLOCATED and its ExternalIPAttachment READY.
2. From the pytest host, `ssh` to the ExternalIP.
3. In the guest, `ss -tnH state established '( sport = :22 )'`.

##### Expected Results

- The attachment's target address equals the SUB-W status IP, never `172.16.0.21`.
- SSH succeeds within the timeout `test_10_manual_external_ip_ingress` uses; the session's local address is the primary address.

#### TC-FR7-02: NAT egress uses the primary route

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_04`. **Blocked**.
- NATGateway on VN-W with an ExternalIP from the routed pool, as in `test_09_nat_gateway_egress`.

##### Steps

1. In VM-A, `ip route get <egressURL address>`.
2. In VM-A, `curl -sS <egressURL>` and record the source address the endpoint reports.
3. On `oob-mgmt`, start `timeout 15 tcpdump -ni eth0 -c 1 not arp` before step 2 and let it run through it.

##### Expected Results

- Step 1 resolves through the primary interface.
- Step 2 succeeds and reports the NATGateway ExternalIP as the source.
- Step 3 ends by the timeout (exit code 124) with 0 packets captured: no egress leaks onto the OOB segment.

#### TC-FR7-03: OOB management access and symmetric return path

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_05`. **Blocked**. Routed OOB prefixes are out of this case until OQ-9 is resolved.
- VM-A READY; the provider MultiNetworkPolicy allows `172.16.0.1/32` on the OOB NAD; the pytest host reaches `oob-mgmt` over its `eth1`.

##### Steps

1. On `oob-mgmt`, `ping -c 3 -W 3 172.16.0.21` and `ssh -o ConnectTimeout=5 <user>@172.16.0.21 hostname`.
2. In VM-A, during step 1, `ip route get 172.16.0.1` and `tcpdump -ni <oob iface> -c 4 host 172.16.0.1`.
3. In VM-A, start `timeout 15 tcpdump -ni <primary iface> -c 1 host 172.16.0.1` before step 1 and let it run through it.

##### Expected Results

- Every probe of step 1 succeeds within 3 seconds; `hostname` returns VM-A's name.
- `ip route get` names the OOB interface; the OOB capture shows requests and replies.
- The primary capture ends by the timeout (exit code 124) with 0 packets: replies never leave through the primary interface.

#### TC-FR7-04: Automatic ExternalIPAttachment targets the primary status entry

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV]. Row M3 (`auto_external_ip_attachment_reconciler_function_test.go`).
- ComputeInstance with two attachment statuses: OOB listed first with `172.16.0.21`, primary second with `10.10.1.5`.

##### Steps

1. Run the reconciler.
2. Run it again with only the OOB status populated.

##### Expected Results

- Step 1 creates the attachment for `10.10.1.5`.
- Step 2 waits (the existing "rechecks while the VM has no address" path) and never uses the OOB address.

### FR-8: Status

#### TC-FR8-01: Feedback correlates VMI interfaces by identity, not order

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (Context "network attachment IP feedback" in `computeinstance_feedback_controller_test.go`).
- ComputeInstance CR with two attachments; test-controlled VMI status listing the OOB interface first.

##### Steps

1. Set VMI `status.interfaces` to `[{name: oob-…, ipAddress: 172.16.0.21}, {name: tenant, ipAddress: 10.10.1.5}]`.
2. Read ComputeInstance status.

##### Expected Results

- Two entries: SUB-W → `10.10.1.5`, SUB-OOB → `172.16.0.21`.
- The legacy single-IP field reports `10.10.1.5`.

#### TC-FR8-02: OOB status must match the static address before network-ready

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5.
- Attachment SUB-OOB with `staticIPv4Address: 172.16.0.21`.

##### Steps

1. VMI reports no address for the OOB interface (guest agent delayed).
2. VMI reports `172.16.0.99` for the OOB interface.
3. VMI reports `172.16.0.21`.

##### Expected Results

- Step 1: the OOB status entry stays empty and the VM is not network-ready; the address is not taken from another interface.
- Step 2: not network-ready, with a condition naming the mismatch.
- Step 3: network-ready.

#### TC-FR8-03: The public API returns both attachment statuses

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (deployed) / [DEV]. Row M2; extends `it/it_compute_instance_network_attachment_status_test.go`. Must not skip with provider networking disabled; see row M2.
- Hub CR status fixture with the two entries from TC-FR8-01.

##### Steps

1. As **Tenant caller**, `ComputeInstances/Get` (public).

##### Expected Results

- `status.compute_network_attachment_statuses` has two entries with the expected `subnet_ref` and `ip_address`; `spec.network_attachments[0].primary` identifies the primary.

#### TC-FR8-04: Details page shows one row per attachment and stays read-only

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-7 | medium | automated |

##### Preconditions

- **Tier / owner:** Unit (Vitest) / [DEV]. Row M10 (`VmNetworkingSection.test.tsx`). Follows the PRD; the design has no UI section (OQ-16).
- ComputeInstance fixture with two attachments and statuses; `internalIpAddress` set.

##### Steps

1. Render `VmNetworkingSection`.

##### Expected Results

- Two rows with Subnet name and IP; the primary row is labelled primary.
- The `internalIpAddress` fallback is not used (it applies only to a single attachment).
- No edit, add or OOB-selection control is rendered.

#### TC-FR8-05: Hub CR mapping carries `primary` and the static address

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-3, AC-7 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV]. Row M3 (Describe "buildSpec network attachments").
- Private ComputeInstance with ATT-PAIR.

##### Steps

1. Build the hub ComputeInstance spec.

##### Expected Results

- `networkAttachments` has two entries in request order; the first has `primary: true`; the second has `staticIPv4Address: 172.16.0.21` and the SG-OOB reference.

### FR-9: Generic VM composition

#### TC-FR9-01: VM networks are composed from bindings with no manager-specific branch

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (`computeinstance_networking_test.go`). Depends on OQ-3.
- SUB-W binding `{kubevirt_binding: l2bridge, namespace_name: <ns>}`; secondary Subnet binding `{kubevirt_binding: bridge, nad_name: acme-nad, namespace_label_key: acme.example/oob, namespace_label_value: "true"}` produced by a fake manager named `acme_vlan`.

##### Steps

1. Create a ComputeInstance CR with both attachments; let the controller build `vm_network`.

##### Expected Results

- `vm_network.namespace` is SUB-W's namespace.
- `networks`: `{name: tenant, pod: {}}` and `{multus: {networkName: acme-nad}}`; `interfaces`: `binding.name: l2bridge` and `bridge: {}`.
- The result is identical when the secondary manager is renamed; no code path reads the manager name.

#### TC-FR9-02: Namespace labels are added, conflicts rejected, and removed with the last user

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-6 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5.
- Two ComputeInstances VM-1 and VM-2 in SUB-W's namespace, both with the OOB attachment; a third Subnet whose binding uses the same label key with value `"false"`.

##### Steps

1. Create VM-1 and VM-2.
2. Create VM-3 with the conflicting-label Subnet.
3. Delete VM-1; then delete VM-2.

##### Expected Results

- After step 1 the namespace has the OOB label once.
- Step 2 fails before any namespace mutation, with a condition naming the conflicting key.
- The label stays after VM-1's deletion and is removed after VM-2's.

#### TC-FR9-03: Subnet is READY only with a valid binding

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-6 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5 (Describe "Subnet controller"). Depends on OQ-2.
- Test-controlled Kubernetes task results for a secondary Subnet.

##### Steps

1. Complete the K8s task with a binding missing `nad_name`.
2. Complete it with `namespace_label_key` but no value.
3. Complete it with an unsupported `kubevirt_binding: macvtap`.
4. Complete it with a valid binding.

##### Expected Results

- Steps 1-3: Subnet `Ready=False`, reason `Failed`, message naming the missing or invalid field; `status.network_binding` unset.
- Step 4: `Ready=True` and `status.network_binding` equal to the result.

#### TC-FR9-04: Localnet manager creates the Localnet CUDN and returns its binding

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-1, AC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (Kind) / [DEV]. Row M9. **Blocked** (no localnet manager; [OSAC-1512](https://redhat.atlassian.net/browse/OSAC-1512)). Depends on OQ-2.
- Fabric handoff fixture: physical network name `oob-physnet`, VLAN 100, schema version 1.

##### Steps

1. Run `create_subnet` for SUB-OOB through `playbook_osac_network_task.yml`.
2. `kubectl get clusteruserdefinednetwork -o yaml`.
3. Rerun step 1; then run `delete_subnet` twice.

##### Expected Results

- The CUDN has `topology: Localnet`, `role: Secondary`, `physicalNetworkName: oob-physnet`, IPAM disabled, a `namespaceSelector` on the binding label, and the tenant and owner-reference metadata.
- `osac_result` carries a binding with `kubevirt_binding: bridge`, `nad_name` and the label pair.
- The rerun returns the same result; both deletes succeed and nothing owned by the Subnet remains.

#### TC-FR9-05: Fabric handoff gates the localnet task

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-6 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5; pattern of OSAC-4291 TC-R2-01/TC-R2-02. Depends on OQ-2 and OQ-15. Handoff fields per #1841: physical network name, VLAN ID, optional MTU.
- SUB-OOB with the OOB Fabric task still running.

##### Steps

1. Observe the jobs before the Fabric task succeeds.
2. Complete the Fabric task with handoff output missing the physical network name; then with VLAN ID `4095`; then with schema version 99.
3. Complete it with valid output.

##### Expected Results

- No Kubernetes job exists before the Fabric task succeeds.
- Step 2 leaves the Subnet `Ready=False` with an actionable message, and no K8s job is created.
- Step 3 creates the K8s job with the handoff data in its input; the input contains no credentials.

#### TC-FR9-06: A missing per-VM NAD blocks only that VM

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-6 | medium | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5.
- VM-1 in namespace NS-1, where the OOB NAD exists; VM-2 in NS-2, where it does not.

##### Steps

1. Create both ComputeInstances.
2. Create the NAD in NS-2.

##### Expected Results

- VM-1 provisioning job starts; VM-2 stays not-ready with a condition naming the missing NAD and no AAP job.
- After step 2, VM-2's job starts.

#### TC-FR9-07: OOB isolation between VMs

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-2 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_07`. **Blocked**. Steps 4-5 depend on OQ-14.
- VM-A (`172.16.0.21`) and VM-B (`172.16.0.22`) from TC-FR2-02.

##### Steps

1. `oc get multi-networkpolicy -A -o yaml` in each VM namespace.
2. In VM-A, `ping -c 3 -W 2 -I <oob iface> 172.16.0.22` and `nc -zv -w 3 -s 172.16.0.21 172.16.0.22 22`.
3. From `oob-mgmt`, `ping -c 3 172.16.0.22`.
4. As **Tenant caller** of `t1`, try to add an ingress rule allowing `172.16.0.0/24` to SG-OOB (the provider-owned SecurityGroup on the OOB attachment).
5. As **Tenant caller** of `t1`, add the same rule to SG-W; repeat step 2.

##### Expected Results

- Each policy carries `k8s.v1.cni.cncf.io/policy-for` naming the OOB NAD.
- Step 2 fails (no ICMP reply, TCP connect timeout); step 3 succeeds.
- Step 4 is refused (`PERMISSION_DENIED`, or `NOT_FOUND` if the tenant cannot see SG-OOB) and SG-OOB is unchanged; the exact rule depends on OQ-14.
- After step 5 step 2 still fails: tenant SecurityGroup changes cannot weaken OOB isolation (design "Security, ownership, and validation").

#### TC-FR9-08: Teardown removes per-VM OOB wiring and leaves nothing

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-2, AC-6 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC, `test_08` (last test of the module). **Blocked**.
- VM-A and VM-B READY, both attached to SUB-OOB.

##### Steps

1. Delete VM-A; wait until it is gone from the API and the cluster.
2. Check VM-A's namespace labels and NADs, VM-B's OOB reachability from `oob-mgmt`, and the OOB CUDN.
3. Delete VM-B; then delete SUB-OOB, VN-OOB and the workload resources in dependency order, as `test_14_teardown_leaves_nothing` does.
4. Check `oob-leaf` (`nv show interface swp1 bridge`), `oc get clusteruserdefinednetwork`, `oc get net-attach-def -A`, and the reservations of `172.16.0.21` and `.22`.

##### Expected Results

- After step 1 VM-A's namespace no longer carries the OOB label or NAD (unless the namespace is deleted with the VM); VM-B still answers `oob-mgmt` and the OOB CUDN remains.
- After step 3 every delete completes within the timeouts of `test_14_teardown_leaves_nothing`.
- Step 4: VLAN 100 is gone from `oob-leaf`, no OOB CUDN or NAD remains, and both addresses can be reserved again (per the reservation source, OQ-7).

### FR-10: Immutability

#### TC-FR10-01: API rejects every attachment change after creation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-8 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M1; extends Context "NetworkAttachments immutability".
- Stored managed VM with ATT-PAIR.

##### Steps

`ComputeInstances/Update` (private, as **Provider caller**) with each change:

1. OOB `static_ipv4_address` → `172.16.0.30`.
2. Move `primary: true` to the OOB attachment.
3. Remove the OOB attachment; add a second OOB attachment; swap their order.
4. Change only SG-W's rules through `SecurityGroups/Update`.

##### Expected Results

- Steps 1-3 fail with `INVALID_ARGUMENT` stating attachments are immutable after creation; `Get` returns the original spec.
- Step 4 behaves as before this feature (PRD FR-10: SecurityGroup updates unchanged).

#### TC-FR10-02: CRD rejects attachment changes

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-8 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M5; extends "NetworkAttachment immutability" in `computeinstance_validation_test.go`.

##### Steps

1. Update a stored two-attachment CR changing `staticIPv4Address`, then `primary`, then removing an item.

##### Expected Results

- Each update is rejected with "networkAttachments are immutable after creation".

### FR-11: Regression

#### TC-FR11-01: Single-NIC and default networking unchanged in deployed Fulfillment

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-4, AC-9 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration (deployed) / [DEV]. Row M2.
- Capability unset (default deployment).

##### Steps

1. Run the existing Describe "ComputeInstance with Subnet attachment" in `it/it_compute_subnet_test.go` unchanged, including "uses tenant defaults when network_attachments is omitted", TC-ATTACH-01, TC-ATTACH-02 and the multi-attachment reject.

##### Expected Results

- Every existing spec passes without edits to its assertions.

#### TC-FR11-02: VMaaS networking E2E stays green without the capability

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-9 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M12. Runs on LAB-MNIC before the OOB networks and the feature's OOB managers are added, or on the `vmaas-netris` CI backend.
- osac-installer `vmaas-ci` with `values/vmaas-ci/netris.yaml`, built from the feature branch; NetworkClass without `network_types`.

##### Steps

1. Run `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` from the repository root.
2. `NetworkClasses/Get`.

##### Expected Results

- `test_00` to `test_14` pass.
- The NetworkClass reports the capability false; every VM of the run has one interface.

#### TC-FR11-03: CaaS and BMaaS contracts unchanged

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-9 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration (server/PostgreSQL) / [DEV]. Row M13. The operator side is TC-FR11-05.

##### Steps

1. Run unchanged the BareMetalInstance attachment specs in `private_baremetal_instances_server_test.go` (single attachment with `primary` normalized or `true`, `primary: false` rejected, the multiple-attachment reject of OSAC-5560).
2. Run unchanged the Cluster `network_attachment` specs (OSAC-5708) in `private_clusters_server_test.go` and `clusters_server_test.go`.

##### Expected Results

- All pass without edits to their assertions; the BMaaS reject keeps the message "at most one network attachment is supported".
- The diff changes no BMaaS or Cluster attachment proto field.

#### TC-FR11-04: Upgrade keeps existing single-NIC VMs working

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-9 | high | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE]. Row M11, LAB-MNIC (primary fabric only) on the previous OSAC release. Not blocked by the localnet manager.
- **Manual procedure:** run from the lab host with `oc` and the `osac` CLI; no repository working directory. Manual because the release upgrade is not automated in `tests/e2e/`.
- Two running single-NIC VMs, each with an ExternalIP.

##### Steps

1. Record each VM's `status.created`/VMI `creationTimestamp` and interfaces.
2. Upgrade OSAC to the feature build (`install-osac` with the new images); add `network_types` to the NetworkClass.
3. Re-read VMI `creationTimestamp` and interfaces; SSH to each ExternalIP.
4. Check each existing Subnet's `status.network_binding` after its next reconcile.
5. Create one new single-NIC VM on an existing Subnet.

##### Expected Results

- VMI timestamps unchanged (no restart); one interface each; SSH succeeds.
- Existing Subnets gain a binding without new Fabric or Kubernetes Manager jobs (design "Upgrade").
- The new VM provisions as before the upgrade.

#### TC-FR11-05: ClusterOrder attachment rule unchanged in the operator

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-6121 | AC-9 | high | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV]. Row M14. The fulfillment side is TC-FR11-03.

##### Steps

1. Run unchanged the ClusterOrder `networkAttachment` specs in `osac-operator/internal/controller/clusterorder_envtest_test.go`.
2. Inspect the generated ClusterOrder and BareMetalInstance CRDs in the diff.

##### Expected Results

- Every update that changes or removes `networkAttachment` is still rejected with "networkAttachment is immutable after creation".
- The ClusterOrder and BareMetalInstance CRD schemas are unchanged; only the ComputeInstance CRD gains multi-attachment rules.

## Gaps

- **Localnet K8s manager missing.** No `cudn_localnet` role exists; [OSAC-1511](https://redhat.atlassian.net/browse/OSAC-1511) is Closed ("frozen in favor of OVN EVPN"), the implementation epic [OSAC-1512](https://redhat.atlassian.net/browse/OSAC-1512) and its tasks are New, and the EP task [OSAC-1830](https://redhat.atlassian.net/browse/OSAC-1830) is New. TC-FR9-04 and all of row M11 are blocked by it. None of these is linked to OSAC-6121.
- **E2E lab not built.** [LAB-MNIC](#e2e-lab-lab-mnic) extends a three-master libvirt cluster with an underlay network and fabric peer, an OOB trunk, a Containerlab Cumulus VX OOB switch and an `oob-mgmt` host. It is not built, its primary Fabric Manager (L-1) is undecided, and no ticket owns the build — **unresolved**. Until it exists TC-FR2-02, TC-FR3-01, TC-FR6-03, TC-FR7-01 to TC-FR7-03, TC-FR9-07 and TC-FR9-08 have no execution path.
- **Live migration.** LAB-MNIC uses LVMS local storage, so live migration of a VM with an OOB interface is not covered — **unresolved**.
- **No implementation or QE stories.** OSAC-6121 has only PRD/Design/UX/UI tasks ([OSAC-6355](https://redhat.atlassian.net/browse/OSAC-6355), [OSAC-6390](https://redhat.atlassian.net/browse/OSAC-6390)). The `[DEV]` rows M1-M10 and M13 and the `[QE]` rows M11-M12 need owning stories; until then **Story** names the Feature — **unresolved**.
- **`ocp_virt_vm` test runner.** `osac-aap/tests/integration/run_tests.sh` runs only Tests 15-17 of `ocp_virt_vm/tests/test.yml`; TC-FR6-01 must be registered there or it never runs — **unresolved**, no ticket.
- **No proto CEL test harness.** `proto/` has no tests for ComputeInstanceSpec rules; the API-level rules are covered through M1 and M5 instead.
- **UI end-to-end.** The osac-ui Playwright suites are manual and not in CI; TC-FR8-04 is Unit only. No deployed UI case is planned, because the UI change is read-only display (PRD FR-3).
- **Windows guests.** Not covered; behaviour is undefined (OQ-10).
- **Routed OOB prefixes.** Only directly connected OOB clients are testable (OQ-9).
- **Open questions.** OQ-1 to OQ-16 change assertions in the cases they list; those cases are not release-blocking until the PRD/design resolve them.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 51 |
| Critical / High / Medium / Low | 21 / 25 / 5 / 0 |
| Automated / Manual | 50 / 1 |
| [DEV] (Unit, Envtest, Component integration) / [QE] (E2E) | 41 / 10 |
| Blocked (localnet manager, OOB Fabric Manager or lab) | 9 |
| Requirements covered | 11 of 11 |
