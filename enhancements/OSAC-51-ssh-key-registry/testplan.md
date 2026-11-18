# Test Plan — OSAC-51 Public SSH Key Registry

**Status:** Working draft for planning
**Updated:** 2026-11-08
**Scope:** VMaaS registered SSH-key behavior in the initial OSAC-51 feature context and current VM implementation work. The plan is not final across the other SSH-key epics.

**Description:** This plan verifies SSH public-key Secret registration, VM key
selection, and guest SSH login. It also checks project scope: a VM may reference
a key in another project, including the default project on either side, when
the creator has access to both projects.

## Overview

**Feature:** [OSAC-51 — Public SSH Key Registry](prd.md) (VMaaS scope)

**Total test cases:** 15 (13 functional, 2 nonfunctional)

**VMaaS requirement areas mapped:** 5 of 5 (ComputeInstance behavior only; this is a coverage map, not execution evidence).

**Interface areas covered:** 4 — Secret registration/lifecycle API and CLI; ComputeInstance key selection API and CLI; provisioning handoff; guest SSH authentication.

- **Supporting unit coverage:** 6 cases mapped to functional scenarios; not counted again above.
- **Decisions still needed:** TC-06 (whether CatalogItem key policies are in
  OSAC-51 scope), TC-10 step 4 (whether deleting a key used by a VM is
  intended), and TC-13 (whether saved key data may be updated). Deployed
  behavior is recorded below; keep these checks non-blocking until the
  product contract is agreed. TC-11's Ignition row cannot be expressed by the
  current `guest_os_family` API and is Not run.
- **Regression status:** `main` has one deployed registered-key sanity scenario but no registered-key VMaaS regression-marked case; five regression targets are planned.
- **Implementation status:** This change documents coverage; it adds no unit, integration, or E2E test code.
- **Execution status:** The deployed Ansible run in [OSAC-7284](https://redhat.atlassian.net/browse/OSAC-7284) passed the executable rows in TC-01–12 on `edge120`, upstream OSAC build `c8d3165d6` (`failed=0`, 2h 14m). TC-11's Ignition row was Not run; TC-13 ran as a record-only observation, without a policy assertion. NFR-SSH-01 passed, and NFR-SSH-02 was exercised in TC-07a, TC-07b, and TC-08. See the [run report](https://redhat.atlassian.net/browse/OSAC-6527?focusedCommentId=19366401) and [Ansible suite](https://gitlab.cee.redhat.com/frmoreno/osac-vmaas-deployment/-/blob/main/e2e/vmaas_ssh_key_registry.yml?ref_type=heads).

**Execution limits:** OSAC-7284 is deployed Ansible E2E evidence; it is not a
run of the Fulfillment component-integration suite. PR #1828's integration
package was compile-only because required host mappings were unavailable.
Keep the TC-06, TC-10 step 4, and TC-13 policy questions open even though their
current deployed behavior is recorded. TC-11's Ignition row remains Not run
until the API can express a compatible fixture. The run also found
[OSAC-7250](https://redhat.atlassian.net/browse/OSAC-7250), which blocks tenant
deletion while User records remain, and
[OSAC-7276](https://redhat.atlassian.net/browse/OSAC-7276), where projects
created through the private API never become ACTIVE. Treat inactive project
fixtures and tenant teardown failures as setup/cleanup issues, not SSH-key
results. One ProjectMembership deletion stalled for about 32 minutes and did
not recur in 10 reruns; plain cleanup errors are not retried and may wait for
the hourly full sync. Verify membership convergence after changes and mark
TC-07/TC-08 Inconclusive if it has not converged.

| OSAC-51 PRD requirement | Test coverage | Coverage note |
|---|---|---|
| Register, list, retrieve, and delete SSH public-key Secrets | TC-01; UT-SSH-01 | Lifecycle and data shape are covered. |
| Select a registered key when creating an instance and inject it at first boot | TC-02–05, TC-11–12; UT-SSH-03, UT-SSH-06 | This plan maps the ComputeInstance/VMaaS behavior only. |
| Keep keys tenant-scoped and available only to authorized tenant users | TC-03–05, TC-07–08; NFR-SSH-02; UT-SSH-03 | Direct cross-project key selection requires the VM creator to have access to both projects, including when either is the default project. |
| Reject malformed OpenSSH public keys | TC-09; UT-SSH-01 | Public-key validation is covered at unit and API boundary tiers. |
| Enforce key-name uniqueness (PRD wording needs alignment) | TC-01, TC-05, TC-07; UT-SSH-03 | Names are unique within a tenant and project. TC-05 verifies the same name can exist in two projects of one tenant, and TC-01 rejects a duplicate in one project. |

This table maps requirements to cases; the execution status and evidence are
recorded separately above and in the case rows.

## Automation status at a glance

**On `main`** means present in upstream at the snapshot date. [PR #1828](https://github.com/osac-project/osac/pull/1828)
merged on 2026-10-28; its component tests are now current coverage.
**Next** identifies gaps to automate or validate; planned work is not
implemented yet. The external deployed run in OSAC-7284 is execution evidence,
not a test checked into the OSAC repository.

| Tier | Automated on `main` after PR #1828 | Deployed execution evidence | Remaining automation or manual validation |
|---|---|---|---|
| Unit | SSH-key payload/type validation, CLI selector parsing, project-aware ComputeInstance reference resolution and immutability, shared-reference rejection, CatalogItem policy checks, Windows rejection, and controller key handoff. | OSAC-7284 reports the deployed Ansible run on `edge120`, upstream `c8d3165d6`, with `failed=0`; it complements unit coverage and is not a unit run. | Add only missing assertions, including in-use SSH-key deletion if required by the final contract. |
| Component integration | Secret CLI lifecycle; project-aware ComputeInstance selection and non-disclosing lookup; shared-key creation rejection; CatalogItem locked/editable policy and CLI display. Generic Secret isolation does not prove all ComputeInstance side effects. | OSAC-7284 deployed E2E covered the reported project/tenant cases; it does not replace component integration. | Run the fulfillment integration suite in a suitable environment; add missing no-side-effect and access-revocation checks at the documented boundary. Add deletion guards if the final contract requires them. |
| Deployed E2E | One OSAC VMaaS sanity case creates a VM and checks key projection into the ComputeInstance CR; it does not verify guest SSH login. | The external Ansible suite in OSAC-7284 reports TC-01–12 and guest SSH login passed on `edge120`; TC-11 Ignition was not run. | Move required scenarios into maintained OSAC E2E automation and regression coverage; routed guest login automation remains a gap (see OSAC-6526). |

The detailed inventory below lists current test files and gaps. UT-SSH-01–06
describe target assertion areas; they map to existing coverage as well as gaps
and do not mean six entirely new unit tests.

## Plan description

Verify the key lifecycle, selection during VM creation, and guest
authentication. The 13 functional cases preserve the first draft. Unit,
integration, and regression coverage are mapped to current tests and
outstanding gaps. The execution record links deployed Ansible results to
their source build; it does not imply this document or the external run added
OSAC test code.

Seeing a key reference on a ComputeInstance does not prove guest access; positive acceptance cases require SSH login when policy permits VM creation.

**Terms used below:** A *VM* is a virtual computer, and *SSH* is a way to log
in to it remotely. A *Secret* is OSAC's record for the saved public key. A
*CatalogItem* is a VM offering with preset settings. A *tenant* is an isolated
resource space, and a *project* groups resources and access within it. The
*guest* is the operating system inside a VM. OSAC stores the public key, while
the matching private key stays with the tester and is used to log in.

Context: [OSAC-51](https://redhat.atlassian.net/browse/OSAC-51), VM work [OSAC-5428](https://redhat.atlassian.net/browse/OSAC-5428) and [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584), and [OSAC PR #1828](https://github.com/osac-project/osac/pull/1828). Add remaining epic requirements after planning.

### How to read deferred checks

The cross-project rules in TC-03–05 and TC-08 are implemented in merged
PR #1828 and were exercised in the OSAC-7284 deployed run. The three decisions
listed in the Overview concern product scope or policy, not whether current
behavior was observed. Record a decision before treating those checks as
release acceptance criteria.

### Contract and scope gate

The 2026-10-22 cross-project reference decision allows a VM in one project to
select an SSH-key Secret in another when the VM creator can access both
projects. Either project may be the default project. TC-03, TC-05, and TC-07
use that rule as their expected behavior. [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584)
and merged [PR #1828](https://github.com/osac-project/osac/pull/1828) implement
project-aware selection; the earlier [OSAC-51 design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-51-ssh-key-registry/design.md)
describes a tenant-scoped local reference. The confirmed naming rule is unique
within each tenant and project: two projects in one tenant may each contain a
key with the same name. The [PRD](prd.md) still says names are unique within a
tenant and needs to be aligned with this decision. A key is injected when the
VM is created. If its creator later loses access to the key's project, the
running VM remains accessible with that key, but the user cannot create
another VM with it. CatalogItem defaults remain a separate open decision.
PR #1828 rejects creation of SSH-key Secrets in the shared tenant and rejects
shared references. The OSAC-7284 run provides deployed execution evidence for
the tenant-scoping cases; the CatalogItem design-scope discrepancy remains
open.

Use an IPv4 ExternalIP address reachable from the test client. Networking is a
prerequisite, not a behavior under test. This follows the current
[VMaaS networking contract](../OSAC-1435-vmaas-networking/design.md), where
ExternalIP replaces the legacy PublicIP name and is not necessarily
internet-routable.

## Detailed existing coverage and test infrastructure

This inventory was refreshed against upstream [`main` at `28ec02f8`](https://github.com/osac-project/osac/commit/28ec02f8d759d921cc75bcdcad90cb4c3d628ec3) on 2026-11-08. PR #1828 merged on 2026-10-28, so its unit and component-integration tests are current coverage. All paths are relative to the OSAC repository root. Detailed behavior is specified once in the cases below.

<details>
<summary>Show test files, coverage gaps, and run commands</summary>

### Unit test coverage

| Coverage / cases | On upstream `main` | Remaining gap |
|---|---|---|
| UT-SSH-01 / TC-09 — payload validation | `fulfillment-service/internal/sshkey/validation_test.go` and `internal/servers/secret_validation_test.go` cover SSH-key syntax and payload validation; `internal/servers/private_compute_instances_ssh_key_test.go` checks wrong type and missing `public_key`; `internal/servers/private_secrets_server_test.go` checks Hub-backed SSH-key data; the CLI test recognizes the `ssh-public-key` type. | Add cases only for malformed, trailing-content, or private-key-like inputs not asserted by these tests. |
| UT-SSH-02 / TC-10 — CLI selector | `fulfillment-service/internal/cmd/cli/create/computeinstance/create_compute_instance_cmd_test.go` and `internal/cmd/cli/create/fieldutil/fieldutil_test.go` cover bare-name and project-qualified selector parsing, including invalid forms before API access. | TC-10 is an optional installed-CLI smoke check; do not duplicate every parser table row manually. |
| UT-SSH-03 / TC-02–05, TC-07 — reference resolution | `fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go`, `internal/servers/compute_instance_ssh_reference_contract_test.go`, and `internal/cmd/service/start/grpcserver/reference_validator_ssh_key_test.go` cover canonicalization, project lookup, non-disclosing errors, shared-reference rejection, handler routing, full-reference immutability, and legacy decode. | TC-07/TC-08 cover access changes and tenant isolation across real authorization boundaries. |
| UT-SSH-04 / TC-06 — CatalogItem policy | `fulfillment-service/internal/servers/catalog_item_ssh_key_policy_test.go` covers SSH-key policy validation; `fulfillment-service/internal/cmd/cli/describe/catalogitem/view_test.go` checks CLI rendering. | TC-06 records deployed defaults, overrides, locks, and no-key behavior; keep OSAC-51 design scope as an explicit product decision. |
| UT-SSH-05 / TC-10 — immutability and deletion | The ComputeInstance tests cover reference immutability. `fulfillment-service/internal/servers/private_secrets_server_test.go` has a general Vault Secret in-use deletion guard for another resource. | No SSH-key/ComputeInstance in-use deletion assertion exists. Add one only if protection is required by the final contract. |
| UT-SSH-06 / TC-11 — controller handoff | `fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go` checks public-key handoff and permanent versus retryable lookup failures. | TC-11's deployed Windows rejection is covered by OSAC-7284; no OSAC-51-compatible Ignition case can currently be expressed through `guest_os_family`. |

### Integration test coverage

| Coverage / cases | On upstream `main` | Remaining gap |
|---|---|---|
| IT-SSH-01 / TC-01 — Secret lifecycle | `fulfillment-service/it/it_cli_ssh_key_lifecycle_test.go` creates, gets, and deletes a key through the CLI; it checks the name/ID and that get reports no object after deletion. | Happy-path lifecycle is covered. Duplicate-name rejection and response/log hygiene are not asserted by this case. |
| IT-SSH-02 / TC-02–05 — direct VM key selection | `fulfillment-service/it/it_compute_instance_ssh_key_test.go` covers name/ID lookup in selected and default projects, non-disclosing missing/out-of-scope errors, bare/project-qualified CLI selection, and named-project CatalogItem defaults. | Deployed guest login and the full project matrix are not asserted by this component suite. |
| IT-SSH-03 / TC-06 — CatalogItem key policy | `fulfillment-service/it/it_compute_instance_catalog_items_test.go` checks locked/editable policy and stored key ID; the SSH-key integration suite covers named-project defaults; `it_cli_catalog_item_describe_test.go` checks CLI rendering. | Editable override/no-key behavior and guest login remain separate assertions; release scope remains a product decision. |
| IT-SSH-04 / TC-07–08 — authorization and isolation | The SSH-key integration suite covers denied-project/non-disclosure; `fulfillment-service/it/it_public_secrets_test.go` covers generic Secret visibility and cross-tenant get/delete. | Membership removal/revocation transitions and full no-side-effect checks remain gaps. |
| IT-SSH-05 / TC-07 — shared-tenant restrictions | `fulfillment-service/it/it_public_secrets_test.go` rejects shared-tenant SSH-key creation; unit reference/policy tests reject shared references. | Shared-key resolution at the ComputeInstance integration boundary remains a separate assertion. |
| IT-SSH-06 / TC-09 — invalid reference boundary | The SSH-key integration suite covers missing/out-of-scope lookup. | Malformed payload and wrong-type rejection at the ComputeInstance integration boundary remain gaps. Confirm scope under [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584) or link the owning follow-up. |
| IT-SSH-07 / TC-10 — update/deletion guards | The lifecycle integration covers deletion of an unreferenced key; unit tests cover immutable ComputeInstance references. | No integration assertion covers updating the reference or deleting an in-use SSH key. Add it only if the final contract requires those guards. |

### E2E test coverage

| Coverage / cases | On upstream `main` | Deployed evidence and remaining gap |
|---|---|---|
| E2E-SSH-01 / TC-02 and Linux part of TC-11 | `tests/e2e/vmaas/sanity/test_compute_instance_registered_ssh_key.py` generates/registers a key, creates a VM, waits for provisioned/running, and asserts the resolved key in the ComputeInstance CR. The same file has two local cleanup-helper tests; they do not deploy a VM. | This is one deployed `sanity` scenario, not guest-authentication coverage. No project matrix, keyless regression, wrong-key check, or real SSH login is covered. |
| E2E-SSH-02 / TC-03–05 | No project-matrix registered-key scenario is checked into OSAC E2E on `main`. | OSAC-7284 reports deployed project-selection and guest-login coverage. Move required scenarios into maintained OSAC E2E automation if CI regression coverage is required. |
| E2E-SSH-03 / TC-12 | No real-SSH login case is checked into OSAC E2E on `main`. | OSAC-7284 reports matching-key login and wrong-key rejection. Track maintained CI routing automation under [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526) if required. |

The merged PR #1828 reports 2,337 server specs and 89 CLI specs passing. Its integration package was compile-only because host mappings were unavailable. OSAC-7284 is separate deployed execution evidence for this plan; it does not establish that the component-integration suite ran.

No registered-key test was found under `tests/e2e/vmaas/regression` on `main`. The regression table below is proposed coverage; the existing deployed VM key case is in `sanity`.

Run these checks from the OSAC repository root:

~~~bash
# Existing unit suites on main
(cd fulfillment-service && ginkgo run --timeout 10m internal/servers)
(cd fulfillment-service && ginkgo run --timeout 10m internal/cmd/cli/create/secret internal/cmd/cli/create/computeinstance internal/cmd/cli/describe/catalogitem)
(cd fulfillment-service && ginkgo run --timeout 10m internal/controllers/computeinstance)

# SSH-key validation unit suite on main
(cd fulfillment-service && go test ./internal/sshkey)

# Component integration
make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment

# Deployed E2E sanity
uv run pytest tests/e2e/vmaas/sanity/test_compute_instance_registered_ssh_key.py
~~~

Unit tests use fakes/in-process collaborators. The `SUITE=fulfillment` component integration suite uses deployed Fulfillment, database, Keycloak, and CLI, with the operator disabled; it proves API authorization and persistence, not ComputeInstance CR creation or provider side effects. Deployed E2E covers reconciliation and VM provisioning. The current sanity SSH-key test verifies the resolved CR field, not a guest login. Each tier covers a different boundary, so the cases are mapped separately to avoid gaps or duplicate assertions.

</details>

## Unit test cases

These are the focused assertion areas from the original plan. They run in-process and do not prove database authorization, project membership reconciliation, VM provisioning, or guest login. The functional cases below retain their existing steps and expected results. Extend a unit suite only for an assertion it does not already make.

### UT-SSH-01 — Accept one valid SSH public key and reject invalid data

**Purpose:** Validate the data stored under <code>public_key</code> for an SSH public-key Secret. The parser accepts one OpenSSH authorized key; malformed text, a private key, a second key, trailing content, or a missing entry must fail before persistence.

| Action | Expected result |
|---|---|
| Validate one Ed25519 authorized key, with and without a comment. | Validation succeeds; the caller retains the supplied public-key bytes. |
| Validate empty or malformed data, private-key text, a second key, or trailing non-key content. | Validation returns an invalid-input error. |
| Validate a wrong Secret type or missing <code>public_key</code> when selected for a VM. | Validation rejects the reference with <code>InvalidArgument</code>. |

**Existing tests:** <code>fulfillment-service/internal/sshkey/validation_test.go</code>, <code>fulfillment-service/internal/servers/secret_validation_test.go</code>, and <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code>. **Gap:** TC-09 adds a real Secret-create boundary check for cases not asserted by component integration.

### UT-SSH-02 — Parse the CLI key selector into the requested project

**Purpose:** Ensure the CLI's selector produces the intended Secret reference before VM creation. A bare name targets the unnamed project; the project-aware form must preserve an explicit project.

| Action | Expected result |
|---|---|
| Omit <code>--ssh-key</code>. | The CLI leaves the SSH-key reference unset; this is a valid no-key request. |
| Parse a bare name, <code>name=KEY</code>, and <code>name=KEY,project=</code>. | Reference name is KEY and project is empty. |
| Parse <code>name=KEY,project=PROJECT</code>. | Reference name is KEY and project is PROJECT. |
| Reject whitespace-only input, <code>name=</code>, missing <code>name</code>, duplicate or unknown fields, empty comma fragments, a structured fragment without <code>=</code>, or a bare value containing a comma. | Local CLI error begins <code>invalid --ssh-key value</code>; no API Create call occurs. |

**Existing tests:** <code>fulfillment-service/internal/cmd/cli/create/computeinstance/create_compute_instance_cmd_test.go</code> and <code>fulfillment-service/internal/cmd/cli/create/fieldutil/fieldutil_test.go</code> cover bare names, project-qualified parsing, and malformed selectors before API access. **Gap:** TC-10 is an optional installed-CLI smoke check; do not duplicate every parser table row manually.

### UT-SSH-03 — Resolve a visible key to its canonical ID, name, and project

**Purpose:** Exercise the reference resolver and its non-disclosing lookup errors. The requesting user must be able to access the selected key project, independently of the VM destination project.

| Action | Expected result |
|---|---|
| Resolve a visible key by name or ID in the selected project, including the unnamed project. | Stored reference has that Secret's ID, name, and project; <code>shared</code> is false. |
| Select between same-named keys in two projects, with the default project as either VM destination or key location. | The canonical ID, name, and project identify the selected Secret rather than the same-named Secret elsewhere. |
| Resolve an inaccessible, missing, wrong-project, or other-tenant key. | <code>NotFound</code> with the same non-disclosing key message. Component integration separately checks that no VM is saved. |
| Deny VM creation when destination-project access is missing but key-project access remains. | Destination authorization fails; TC-07 checks at the component boundary that no VM persists. |
| Set <code>shared: true</code> on an SSH key reference. | <code>InvalidArgument</code> with “SSH key reference must be tenant-scoped.” |
| Decode an old ID/name-only reference if legacy decoding is supported. | The existing key identity remains readable; record the PR's compatibility behavior without assuming a named project. |

**Existing tests:** <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code>, <code>fulfillment-service/internal/servers/compute_instance_ssh_reference_contract_test.go</code>, and <code>fulfillment-service/internal/cmd/service/start/grpcserver/reference_validator_ssh_key_test.go</code>. **Gap:** TC-07/TC-08 cover access changes across real authorization boundaries.

### UT-SSH-04 — Apply a CatalogItem key default without losing its project

**Purpose:** Check the policy path that supplies a key when the VM caller omits <code>--ssh-key</code>. Use distinct Secret IDs for the default and override so the selected key is visible; editable and locked policy outcomes should be checked separately.

| Action | Expected result |
|---|---|
| Apply an editable default with an explicit key project. | VM candidate receives that key's canonical ID, name, and project. |
| Override an editable default or attempt to override a locked default. | An allowed override selects the requested key; a locked override is rejected before VM persistence. |
| Omit a key when the CatalogItem has no key default and permits omission. | VM candidate has no SSH key reference. |

**Existing tests:** <code>fulfillment-service/internal/servers/catalog_item_ssh_key_policy_test.go</code> covers policy validation; <code>fulfillment-service/it/it_compute_instance_catalog_items_test.go</code> covers locked/editable policy and project-scoped defaults at the component boundary. **Gap:** TC-06 records the deployed default/override/lock/no-key behavior; whether it is in OSAC-51 scope remains a product decision.

### UT-SSH-05 — Keep a created VM's SSH key reference immutable

**Purpose:** Confirm an update cannot change or clear the key on a created VM. Secret deletion while referenced is a separate lifecycle rule and must not be inferred from immutability.

| Action | Expected result |
|---|---|
| Update a VM with a different key ID or project, or clear the reference. | <code>InvalidArgument</code>; original canonical reference remains unchanged. |
| Repeat an update without changing the reference identity. | No false immutability rejection. |
| If the final policy protects referenced keys, attempt to delete the Secret while its VM exists; delete the VM and retry. | First deletion is rejected and the later deletion succeeds. This remains deferred until the policy is agreed and implemented. |

**Existing tests:** <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code> and <code>fulfillment-service/internal/servers/compute_instance_ssh_reference_contract_test.go</code> cover reference immutability. **Gap:** No SSH-key/ComputeInstance in-use deletion protection test exists; add one only if the final policy requires it.

### UT-SSH-06 — Pass the resolved key to the VM controller

**Purpose:** Verify the controller uses the registered Secret's public key when building the ComputeInstance CR, and classifies permanent reference failures separately from transient store failures.

| Action | Expected result |
|---|---|
| Reconcile a VM with a valid registered key. | Operator-facing ComputeInstance spec receives the exact public-key bytes. |
| Reconcile with <code>NotFound</code>/<code>InvalidArgument</code> versus <code>Unavailable</code>/<code>DeadlineExceeded</code>/<code>Canceled</code> lookup failures. | Invalid or missing references are permanent; the listed transient failures follow the controller's retry policy. |

**Existing tests:** <code>fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go</code> covers the current reference shape and error classification. **Gap:** The existing OSAC sanity test checks the CR; OSAC-7284 reports deployed guest authentication, but no maintained OSAC E2E login case exists.

**Run these suites:** From <code>fulfillment-service/</code>, run <code>go test ./internal/servers ./internal/sshkey ./internal/controllers/computeinstance ./internal/cmd/cli/create/computeinstance -timeout 20m</code> on current source. These commands test in-process logic with mocks or local collaborators; use the component integration and deployed E2E commands below for real service and guest boundaries.

## Actors and prerequisites

| Role | Responsibility |
|---|---|
| Tenant User | A regular tenant member who registers SSH-key Secrets, creates ComputeInstances, selects CatalogItems, and performs SSH verification. |
| Tenant Admin | Creates test projects and assigns/revokes Tenant User access where required by the test environment. |
| Cloud Provider Admin | Prepares published Linux/Windows/ignition templates, CatalogItems, and routable VM/network fixtures. |
| Administrative test fixture | Attempts shared-tenant key creation and verifies rejection/no persistence; this is setup, not a normal user persona. |
| Tenant-B User | Runs cross-tenant isolation checks. |

**Authorization model for test setup:** Treat tenant as the isolation boundary.
For a direct SSH-key reference, the VM creator must have access to both the VM
destination project and the selected key's project.

**Tenant User setup:** Create the test user in the tenant's Keycloak
organization and assign a regular tenant-member role. The Users API does not
create a Keycloak account. Do not use the break-glass tenant-admin account as
the Tenant User: it can see every project. After changing project membership,
log in again as the user before testing the new access.

### Common setup

Run the shell snippets in Bash. Use a disposable test tenant and unique
resource names. Keep private keys only on the test client.

~~~bash
RUN_ID="$(date +%s)"
TEST_TMPDIR="${TMPDIR:-/tmp}"
TEST_TMPDIR="$(cd -- "$TEST_TMPDIR" && pwd -P)"
KEY_DIR="$(mktemp -d "$TEST_TMPDIR/osac51-ssh-key-test.XXXXXX")"
ssh-keygen -t ed25519 -f "$KEY_DIR/id_ed25519" -N '' -C osac-51-test

TENANT_A='replace-with-test-tenant'
TENANT_B='replace-with-second-test-tenant'
PROJECT_A='replace-with-project-a'
PROJECT_B='replace-with-project-b'
TENANT_B_PROJECT='replace-with-tenant-b-project'
CATALOG_ITEM='replace-with-linux-cloud-init-catalog-item'
TENANT_B_CATALOG_ITEM='replace-with-tenant-b-linux-cloud-init-catalog-item'
EDITABLE_KEY_CATALOG_ITEM='replace-with-editable-key-default-catalog-item'
LOCKED_KEY_CATALOG_ITEM='replace-with-locked-key-default-catalog-item'
NO_KEY_CATALOG_ITEM='replace-with-no-key-default-catalog-item'
WINDOWS_CATALOG_ITEM='replace-with-windows-catalog-item'
NETWORK_ATTACHMENT='subnet=replace-with-subnet-id,security-groups=replace-with-ssh-security-group-id'
TENANT_B_NETWORK_ATTACHMENT='subnet=replace-with-tenant-b-subnet-id,security-groups=replace-with-tenant-b-ssh-security-group-id'
# Set from the deployed OSAC operator configuration before VM cases.
PROVIDER_NETWORKING_ENABLED='replace-with-true-or-false'
NETWORK_ARGS=()
TENANT_B_NETWORK_ARGS=()
if [ "$PROVIDER_NETWORKING_ENABLED" = true ]; then
  NETWORK_ARGS=(--network-attachment "$NETWORK_ATTACHMENT")
  TENANT_B_NETWORK_ARGS=(--network-attachment "$TENANT_B_NETWORK_ATTACHMENT")
elif [ "$PROVIDER_NETWORKING_ENABLED" != false ]; then
  printf 'Set PROVIDER_NETWORKING_ENABLED to true or false.\n' >&2
  exit 1
fi
VM_USER='replace-with-image-login-user'
VM_PORT='22'
EXTERNAL_IP_POOL='replace-with-external-ip-pool'
DEFAULT_KEY="osac51-default-$RUN_ID"
LIFECYCLE_KEY="osac51-lifecycle-$RUN_ID"
PROJECT_KEY="osac51-project-a-$RUN_ID"
TENANT_A_NAME_KEY="osac51-tenant-a-name-$RUN_ID"
IMMUTABLE_KEY="osac51-immutable-$RUN_ID"
TENANT_COLLISION_KEY="osac51-tenant-collision-$RUN_ID"
SHARED_KEY="osac51-shared-$RUN_ID"
VM_DD="osac51-dd-$RUN_ID"
VM_DA="osac51-da-$RUN_ID"
VM_AA="osac51-aa-$RUN_ID"
VM_AB="osac51-ab-$RUN_ID"
VM_AD="osac51-ad-$RUN_ID"
VM_TENANT_B="osac51-tenant-b-$RUN_ID"
NFR_MISSING_KEY_B="osac51-nfr-missing-b-key-$RUN_ID"
VM_NFR_MISSING_B="osac51-nfr-missing-b-$RUN_ID"
VM_REVOKED="osac51-revoked-$RUN_ID"
VM_REVOKED_INITIAL="osac51-revoked-initial-$RUN_ID"
VM_IMMUTABLE="osac51-immutable-$RUN_ID"
VM_SSH_E2E="osac51-ssh-e2e-$RUN_ID"
EXTERNAL_IP_NAME="osac51-ip-$RUN_ID"
EXTERNAL_IP_ATTACHMENT="osac51-ip-attachment-$RUN_ID"
KNOWN_HOSTS="$KEY_DIR/known_hosts"
ssh-keygen -t ed25519 -f "$KEY_DIR/id_ed25519_b" -N '' -C osac-51-test-b
~~~

`PROVIDER_NETWORKING_ENABLED` must reflect the deployed operator
configuration before VM cases. The common setup builds `NETWORK_ARGS` and
`TENANT_B_NETWORK_ARGS`: each contains its `--network-attachment` only when
provider networking is enabled and is empty otherwise. Use the matching array
in every VM create command; never pass a placeholder Subnet or SecurityGroup
when provider networking is disabled.

When provider networking is enabled, `NETWORK_ATTACHMENT` must name a Ready
Subnet and SecurityGroup that permits TCP/22 from the test client and only the
egress needed by the guest. It must be selectable for VMs in Tenant A's default
project and Projects A/B. With provider networking disabled, VMaaS creates no
NetworkAttachment and uses the cluster default interface; default Subnet and
SecurityGroup readiness does not imply provider connectivity or policy. Do not
require an ExternalIP or provider SecurityGroup rule in that mode. TC-12 needs
the lab's separate test-client route described below.
For TC-07, the Tenant B CatalogItem and network attachment must be valid in
Tenant B before testing a cross-tenant SSH-key rejection; otherwise a VM
request could fail for an unrelated missing fixture.
With provider networking enabled, TC-12 also needs a Ready ExternalIPPool with
capacity and a routable address. Before VM cases, confirm the selected project
and CatalogItem are usable and the required default networking resources are
Ready. If the tenant's default project is still Pending, continue only with
Secret-only cases and mark VM cases Not run until the prerequisites are ready.

At final cleanup, delete all test ComputeInstances before deleting their
Secrets, including `$DEFAULT_KEY` and `$TENANT_A_NAME_KEY`. Then remove only
the temporary directory created for this run. Do not reuse or override `KEY_DIR`.

<details>
<summary>Local key-file cleanup commands</summary>

~~~bash
KEY_DIR_PARENT="$(cd -- "$(dirname -- "$KEY_DIR")" && pwd -P)"
KEY_DIR_NAME="${KEY_DIR##*/}"
if [ "$KEY_DIR_PARENT" != "$TEST_TMPDIR" ] || [ -L "$KEY_DIR" ] || \
  [ ! -d "$KEY_DIR" ]; then
  printf 'Refusing to remove unexpected key directory: %s\n' "$KEY_DIR" >&2
  exit 1
fi

case "$KEY_DIR_NAME" in
  osac51-ssh-key-test.*)
    rm -f -- "$KEY_DIR/id_ed25519" "$KEY_DIR/id_ed25519.pub" \
      "$KEY_DIR/id_ed25519_b" "$KEY_DIR/id_ed25519_b.pub" \
      "$KEY_DIR/known_hosts" "$KEY_DIR/malformed.pub" \
      "$KEY_DIR/empty.pub" "$KEY_DIR/private-key-like.txt" \
      "$KEY_DIR/two-keys.pub" "$KEY_DIR/trailing.pub"
    rmdir -- "$KEY_DIR"
    ;;
  *)
    printf 'Refusing to remove unexpected key directory: %s\n' "$KEY_DIR" >&2
    exit 1
    ;;
esac
~~~

</details>

Confirm that `osac whoami` shows the regular Tenant User in `$TENANT_A`, clear
any saved project, and verify Projects A, B, and `$TENANT_B_PROJECT` are
ACTIVE. After membership changes, refresh the user's login before continuing:

~~~bash
osac whoami
osac project --clear
osac get projects
~~~

Create a default-project key for the selection and guest tests. Keep it until common cleanup; TC-01 uses a separate Secret so its deletion/recreation checks do not affect other cases.

~~~bash
osac create secret --name "$DEFAULT_KEY" --type ssh-public-key \
  --from-file "public_key=$KEY_DIR/id_ed25519.pub"
DEFAULT_KEY_ID="$(osac get secrets "$DEFAULT_KEY" -o yaml | yq -r '.id')"
~~~

For any of TC-04–08, also prepare `$PROJECT_KEY` in Project A if it does not
already exist. This is a reusable fixture, so these cases can run in any order.
Run the create command below only when the key is absent; always inspect it
and confirm it belongs to Project A with the expected public key. If the CLI
cannot create a project-scoped Secret, use the supported administrative/service
API and record its request and response. TC-07b separately creates
`$TENANT_A_NAME_KEY` in Tenant A's default project for its by-name
cross-tenant comparison.

~~~bash
osac --project "$PROJECT_A" create secret --name "$PROJECT_KEY" \
  --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"
osac --project "$PROJECT_A" get secret "$PROJECT_KEY" -o yaml
~~~

For every status or deletion poll below, check at most once every 10 seconds.
Stop after 30 minutes for VM readiness and 10 minutes for other resources;
record the last observed status when a deadline expires. Treat a missed
readiness deadline as inconclusive until the VM or network cause is known.

Create additional Secrets inside each functional test through the CLI where the
target build supports it. For every project-scoped fixture, confirm its
`metadata.project`; use the supported administrative/service API if the CLI
cannot create it. Keep ComputeInstance creation and key selection on the
public CLI.

Before a positive SSH assertion:

1. Wait for `osac get computeinstance` to report
   `COMPUTE_INSTANCE_STATE_RUNNING` (shown as Running in some CLI views).
2. Obtain the VM address and verify client routing to TCP/22.
3. Populate KNOWN_HOSTS from a trusted host-key source. Do not trust a key retrieved over the same unverified connection.
4. Use an isolated SSH configuration, disable agent identities and connection sharing, and use only the intended private key.

~~~bash
ssh -F /dev/null -i "$KEY_DIR/id_ed25519" -o IdentityAgent=none \
  -o IdentitiesOnly=yes -o ControlMaster=no -o ControlPath=none \
  -o BatchMode=yes -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=10 \
  -p "$VM_PORT" \
  "$VM_USER@$VM_ADDRESS" 'printf OSAC_SSH_OK'
~~~

A network timeout makes the case inconclusive, not passed. Do not use `StrictHostKeyChecking=no` or a discarded known_hosts file.

## Functional test cases

### TC-01 — Register, inspect, and delete an SSH public-key Secret

**Description:** Follow one saved public key through registration, listing,
inspection, duplicate-registration rejection, and deletion in the tenant's
default project. No named project is selected, so the Secret is expected to
have `metadata.project: null`. A second registration with the same name must
fail without changing the original Secret.

**Category:** Mixed
**Test tier:** Component integration; unit validation supports invalid-input assertions
**Priority:** High
**Automation:** CLI lifecycle integration anchor exists; extend missing assertions
**Execution identity:** Run every step as a non-admin Tenant User authorized
for the selected tenant and project. Confirm `osac whoami` identifies that
user and `osac get projects` lists the tenant. Run `osac project --clear` so
this case uses the tenant's default project. Selecting a tenant while logged
in as the platform `admin` does not satisfy this precondition.

| Step | Action | Expected result |
|---|---|---|
| 1 | Use the Ed25519 key pair generated in common setup. | Both files exist; private key remains local. |
| 2 | Run `osac create secret --name "$LIFECYCLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. Record the returned Secret ID. | The command succeeds and reports the new Secret's name and ID. |
| 3 | Run `osac get secrets "$LIFECYCLE_KEY" -o yaml`. Decode `data.public_key` and compare it with the local file using the command below. | Exactly one Secret is returned in the tenant's default project with the ID from step 2, SSH public-key type, and the same public-key bytes; `cmp` exits 0. The private key is not returned. |
| 4 | Repeat `osac create secret --name "$LIFECYCLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then inspect the Secret again with `osac get secrets "$LIFECYCLE_KEY" -o yaml`. | The duplicate create fails; the original Secret ID and data are unchanged, and exactly one Secret remains. |
| 5 | Run `osac delete secret "$LIFECYCLE_KEY"`, then run `osac get secrets "$LIFECYCLE_KEY" -o yaml`. | Delete succeeds; the filtered get returns `[]` on the current CLI. No Secret with that name remains. |

For TC-01 step 3, compare the stored public-key bytes with the generated file:

~~~bash
set -o pipefail
osac get secrets "$LIFECYCLE_KEY" -o yaml \
  | yq -r '.data.public_key' \
  | base64 --decode \
  | cmp - "$KEY_DIR/id_ed25519.pub"
~~~

### TC-02 — Create a default-project VM using its registered SSH key

**Description:** Check that `--ssh-key "$DEFAULT_KEY"` finds the key registered
in the tenant's default project. The command supplies only the key's name,
without `name=` or `project=`. After the Linux VM starts, its saved SSH-key
reference must contain that Secret's ID and name and no named project. This
proves the VM selected the intended registered key. TC-12 separately checks
whether the key actually lets someone log in to the guest.

**Category:** Positive
**Test tier:** Deployed E2E; service resolution is covered by component integration
**Priority:** Critical
**Automation:** The sanity E2E on `main` checks the saved reference and CR
projection. OSAC-7284 reports deployed guest login; no maintained OSAC E2E
case checks login.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`, then `osac create computeinstance --name "$VM_DD" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" "${NETWORK_ARGS[@]}"`. | One VM is created in the tenant's default project. |
| 2 | Wait for the VM to report Running. Run `osac get computeinstance "$VM_DD" -o yaml` and compare `spec.ssh_key.id`, `spec.ssh_key.name`, and `spec.ssh_key.project` with `$DEFAULT_KEY_ID`, `$DEFAULT_KEY`, and an empty project. | The VM is Running and its saved reference identifies the exact default-project Secret registered in common setup. This step does not assert that SSH login works. |

### TC-03 — Create a project A VM using a default-project SSH key

**Description:** Create a VM in Project A while selecting a key stored in the
default project. A user with access to both projects should be able to create
the VM and log in using the matching private key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Project selection is on `main` after merged PR #1828. OSAC-7284
reports the deployed project and guest-login case; move coverage into
maintained OSAC E2E if regression automation is required.

**Prerequisite:** Tenant User has access to Project A and the default project.

| Step | Action | Expected result |
|---|---|---|
| 1 | Use the default-project key created in common setup and inspect it with `osac get secret "$DEFAULT_KEY" -o yaml`. | Key persists in the default project. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "$VM_DA" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" "${NETWORK_ARGS[@]}"`. | VM is created in Project A using the default-project key. |
| 3 | Run `osac --project "$PROJECT_A" get computeinstance "$VM_DA" -o yaml`. Once the VM is Running and reachable, set `$VM_ADDRESS` and run the strict SSH command from common setup. | The reference contains `$DEFAULT_KEY`'s ID/name and no named key project; the matching private key authenticates. |

### TC-04 — Create a project A VM using a key stored in project A

**Description:** Create a VM in Project A using a key saved in that same
project. The VM should point to Project A's key and allow login with the
matching private key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Project selection is on `main` after merged PR #1828. OSAC-7284
reports the deployed project and guest-login case; move coverage into
maintained OSAC E2E if regression automation is required.

**Prerequisite:** Tenant User has access to Project A.

| Step | Action | Expected result |
|---|---|---|
| 1 | Prepare `$PROJECT_KEY` in Project A as described in common setup, or inspect it there if already prepared. | Exactly one Secret exists with Project A recorded and the expected public key. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "$VM_AA" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`. | VM is created with a canonical reference to Project A's key. |
| 3 | Inspect with `osac --project "$PROJECT_A" get computeinstance "$VM_AA" -o yaml`. Once the VM is Running and reachable, set `$VM_ADDRESS` and run the strict SSH command from common setup. | The VM reference contains Project A's Secret ID/name/project and the matching private key authenticates. |

### TC-05 — Select Project A's key for VMs in B and default despite a duplicate name

**Description:** A user who can access Projects A and B creates a VM in B
using A's SSH key. The same user also creates a VM in the tenant's default
project using A's key. Both VMs must use A's key, so A's private key should
allow login and B's private key should fail. Give the keys in A and B the
same name to prove that explicitly selecting Project A finds the right one.
A second key with that name cannot be created inside A.

**Category:** Mixed
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** The integration suite on `main` covers named-project key
selection for a default-project VM. OSAC-7284 reports deployed project
selection and guest login; add maintained regression coverage for the full
same-name project matrix.

**Prerequisite:** Tenant User has access to Projects A and B and the default
project. `$PROJECT_KEY` exists in A as described in common setup and contains
`$KEY_DIR/id_ed25519.pub`.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a key in B with the **same name** as A's key but a different public key: `osac --project "$PROJECT_B" create secret --name "$PROJECT_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect both with `osac --project "$PROJECT_A" get secret "$PROJECT_KEY" -o yaml` and `osac --project "$PROJECT_B" get secret "$PROJECT_KEY" -o yaml`. If the CLI cannot create project-scoped Secrets, use the supported administrative/service fixture and record its request and response. | Both Secrets exist under one tenant with the same name but different projects, IDs, and public-key values. |
| 2 | Try to create another key named `$PROJECT_KEY` in A using `osac --project "$PROJECT_A" create secret --name "$PROJECT_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect A's key again. | The second create in A fails with `AlreadyExists`; A's original Secret ID and public key do not change. |
| 3 | Create a VM in B with `osac --project "$PROJECT_B" create computeinstance --name "$VM_AB" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`. Inspect it with `osac --project "$PROJECT_B" get computeinstance "$VM_AB" -o yaml`. | The VM is created in B, and its saved SSH-key reference contains A's Secret ID and Project A, not B's Secret ID. |
| 4 | Once the B VM is Running and reachable, set `$VM_ADDRESS` to its address and run the common strict SSH command with `$KEY_DIR/id_ed25519`. Repeat with `$KEY_DIR/id_ed25519_b`. | A's private key authenticates; B's private key fails. This proves the VM received A's public key. |
| 5 | Run `osac project --clear`, then create a default-project VM with `osac create computeinstance --name "$VM_AD" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`. Inspect it with `osac get computeinstance "$VM_AD" -o yaml`. When Running and reachable, set `$VM_ADDRESS` to this VM and try both private keys as in step 4. | The VM is created in the default project. Its reference contains A's Secret ID and Project A; A's private key authenticates and B's private key fails. |

### TC-06 — Create VMs with editable, locked, and empty CatalogItem key policies

**Description:** Check how a VM offering (CatalogItem) and a user's key choice
interact. One offering supplies a default key that the user may replace;
another locks its default key; a third has no key. The default and override
must be different Secrets so the saved VM reference shows which one won.

**Category:** Mixed
**Test tier:** Unit and component integration; deployed E2E if required
**Priority:** High
**Automation:** Defaults, overrides, and locks are implemented on `main` and
were exercised in OSAC-7284. A locked item rejects `--ssh-key` with
`InvalidArgument: ssh_key: field is not editable`.
**Decision needed:** The OSAC-51 design excludes CatalogItem key defaults,
while the deployed service supports them. Confirm whether this behavior is in
OSAC-51 scope before treating it as a release acceptance criterion.

**Prerequisite:** `$PROJECT_KEY` exists in Project A as described in common
setup. `CATALOG_ITEM` has no SSH-key default. All three policy CatalogItems
must be tenant-scoped; a shared CatalogItem cannot hold a key default or lock.
Configure the editable and locked CatalogItems with `$DEFAULT_KEY` from the
default project. Configure the no-key item without an `ssh_key` policy; the
API cannot lock the key to `none`. `$PROJECT_KEY` must have a different ID so
it can serve as the override. Inspect the CatalogItems with
`osac get computeinstancecatalogitems "$EDITABLE_KEY_CATALOG_ITEM" -o yaml`,
and repeat for the locked and no-key items.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a VM in A from `$EDITABLE_KEY_CATALOG_ITEM` without `--ssh-key`: `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-default-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" "${NETWORK_ARGS[@]}"`. Inspect the VM with `osac --project "$PROJECT_A" get computeinstance "osac51-ci-default-$RUN_ID" -o yaml`. | The saved reference contains `$DEFAULT_KEY`'s ID and default project. This default behavior was observed in OSAC-7284. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-override-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`, then inspect the VM. | The editable offering accepts the override and saves `$PROJECT_KEY`'s ID and Project A, rather than `$DEFAULT_KEY`'s ID. This override was observed in OSAC-7284. |
| 3 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-locked-$RUN_ID" --catalog-item "$LOCKED_KEY_CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`, then query that VM name. | The request fails with `InvalidArgument: ssh_key: field is not editable`; the lookup returns `[]`, no VM persists, and the locked CatalogItem still points to `$DEFAULT_KEY`. |
| 4 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-none-$RUN_ID" --catalog-item "$NO_KEY_CATALOG_ITEM" "${NETWORK_ARGS[@]}"` without `--ssh-key`, then inspect the VM. | The VM is created without a registered-key reference. The no-key policy is a CatalogItem with no `ssh_key` policy. |

### TC-07 — Reject VM creation with an inaccessible, cross-tenant, or shared key

**Description:** Check three boundaries. First, a user must have access to
both the VM's project and the key's project. Second, a VM in Tenant B must
never select Tenant A's key, even when the tenants use the same key name.
Third, merged PR #1828 rejects SSH keys in shared scope. Rejected VM requests
must not reveal the protected key or save a VM.

**Category:** Mixed
**Test tier:** Unit for `shared: true` reference validation; component integration for API authorization/persistence; deployed E2E only for CR/provider absence
**Priority:** Critical
**Automation:** Current `main` covers denied-project lookup,
shared-tenant SSH-key creation rejection, and `shared: true` reference
rejection. OSAC-7284 reports deployed cross-tenant checks by ID and name;
TC-08's membership-revocation transition remains a separate plan case.

**Prerequisite:** Tenant User can access Projects A and B; `$PROJECT_KEY`
exists in Project A as described in common setup. Tenant-B User has access to
`$TENANT_B_PROJECT` but is not a member of Tenant A. Authenticate separately
as each regular tenant user's account and confirm the account and tenant with
`osac whoami` before issuing commands. Verify `$TENANT_B_CATALOG_ITEM` and
`$TENANT_B_NETWORK_ATTACHMENT`
are usable in Tenant B before steps 5–8.

**Scope distinction:** A Secret does not have a `shared` boolean. To test
shared SSH-key creation, target the shared tenant (explicitly or through the
platform administrator's shared-tenant default). The `shared: true` field is
on the SSH-key reference in a ComputeInstance request. Shared CatalogItems
cannot define SSH-key defaults or locks; TC-06 uses tenant-scoped items.
In step 8, the bare-name selector looks in Tenant B's default project;
compare the VM reference with Tenant B's Secret ID, not just its name.

| Step | Action | Expected result |
|---|---|---|
| 1 | Prepare TC-07a: Tenant Admin keeps the user assigned to Project B, removes the user's Project A assignment through the membership API/fixture, and waits for membership convergence. | The user's membership remains effective in Project B and is removed from Project A. If the change does not converge, mark this access check Inconclusive. |
| 2 | **TC-07a — hidden or inaccessible key.** After reauthentication, User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-key-project-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`; Tenant Admin queries that VM name. | General reference validation rejects the key with `NotFound: SSH key Secret was not found or is not visible in the selected project`, the same public response as a missing key. Do not assert a dedicated project-membership check. No key metadata is disclosed and no VM persists. |
| 3 | Tenant Admin restores Project A assignment through the membership fixture, waits for convergence, and the User reauthenticates. | The user's access to Project A is restored. |
| 4 | Tenant Admin removes the user's Project B assignment while retaining Project A access. User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-destination-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`. After the request, Tenant Admin checks the VM name through the API, then restores Project B access and waits for convergence. | Destination-project authorization fails; the authorized API check returns not found. A deployed E2E check must separately confirm no ComputeInstance CR/provider operation; Project B access is restored. |
| 5 | **TC-07b — cross-tenant non-disclosure.** Record `$DEFAULT_KEY_ID` from Tenant A's default-project Secret. As Tenant-A User, clear the project and create `$TENANT_A_NAME_KEY` in Tenant A's default project; verify it exists there. As Tenant-B User, use the public API in `$TENANT_B_PROJECT` to compare requests selecting Tenant A's default-project key by ID (`spec.ssh_key={id: "$DEFAULT_KEY_ID", project: ""}`) and by name (`spec.ssh_key={name: "$TENANT_A_NAME_KEY", project: ""}`) with corresponding unknown ID and name references. Keep each known/unknown pair on the same caller and destination. | Tenant B cannot resolve Tenant A's ID or default-project key name. Each response matches its corresponding unknown-key response, including `NotFound: SSH key Secret was not found or is not visible in the selected project`; no VM persists and no Tenant-A Secret data is returned. |
| 6 | **TC-07c — same-name key isolation.** Authenticate as Tenant-A User; confirm Tenant A with `osac whoami`, run `osac project --clear`, and create `osac create secret --name "$TENANT_COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. Record the Secret ID. | A key with this name and A's public-key value exists in Tenant A's default project. |
| 7 | Authenticate as Tenant-B User; confirm Tenant B with `osac whoami`, run `osac project --clear`, and create `osac create secret --name "$TENANT_COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Record this Secret ID. | Tenant B can use the same name, but the ID and public-key value differ from Tenant A's key. |
| 8 | Run `osac --project "$TENANT_B_PROJECT" create computeinstance --name "osac51-tenant-collision-$RUN_ID" --catalog-item "$TENANT_B_CATALOG_ITEM" --ssh-key "$TENANT_COLLISION_KEY" "${TENANT_B_NETWORK_ARGS[@]}"`; inspect with `osac --project "$TENANT_B_PROJECT" get computeinstance "osac51-tenant-collision-$RUN_ID" -o yaml`. Restore Tenant-A authentication afterward. | The VM's canonical key reference contains Tenant B's Secret ID and default project, not Tenant A's ID. The authenticated context returns to Tenant A. |
| 9 | Through the administrative/API fixture, attempt to create `$SHARED_KEY` with type `SECRET_TYPE_SSH_PUBLIC_KEY`, valid `public_key` data, and `metadata.tenant=shared`. List by that unique name in the shared tenant afterward. The public CLI has no `shared` Secret-create flag. | On current `main`, creation returns `InvalidArgument` and the authorized follow-up list is empty; no Secret persists. |
| 10 | In the unit reference-validation test, submit a VM request with `spec.ssh_key={name: "$DEFAULT_KEY", shared: true}` and verify rejection occurs before Secret lookup. If the public API accepts this request shape, repeat through the API and query the attempted VM name as an authorized Tenant Admin. | On current `main`, the request returns `InvalidArgument` with `SSH key reference must be tenant-scoped.` The VM is not persisted; use deployed E2E to confirm no CR/provider operation if that side-effect assertion is required. |

### TC-08 — Reject new VM creation after access to the key project is revoked

**Description:** Create a VM in Project B using a key from Project A. Then
remove the creator's access to A while keeping access to B. Another VM request
using A's key must be denied. The first VM keeps the key it received at
creation and remains accessible with the matching private key.

**Category:** Mixed
**Test tier:** Component integration for API authorization/persistence; deployed E2E for guest authentication and CR/provider absence
**Priority:** High
**Automation:** Merged PR #1828 covers denied lookup. OSAC-7284 reports the
source-project access-revocation transition and existing-VM login passed;
maintained component-integration coverage for that transition remains open.

**Prerequisite:** `$PROJECT_KEY` exists in Project A as described in common
setup. Tenant User has access to Projects A and B. Tenant Admin can revoke
and restore that user's Project A assignment through the supported membership
fixture.

| Step | Action | Expected result |
|---|---|---|
| 1 | Tenant Admin confirms the user can access both A and B through the membership API/fixture and waits for convergence. | Both project assignments are effective. |
| 2 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED_INITIAL" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`; inspect with `osac --project "$PROJECT_B" get computeinstance "$VM_REVOKED_INITIAL" -o yaml`. In deployed E2E, wait for Running and prove that the shared strict SSH command succeeds before revoking access. | VM-1 persists in B with a canonical reference to A's key; in deployed E2E, it is Running and the matching private key authenticates before revocation. |
| 3 | Tenant Admin revokes only the user's Project A assignment through the supported membership API/fixture and waits for convergence. | The user still has destination-project access but no longer has access to the key's project. |
| 4 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`; then Tenant Admin queries `$VM_REVOKED`. | The new request is denied because the user cannot access A. The authorized query returns not found; a deployed E2E check separately confirms no CR/provider operation. |
| 5 | As the user, inspect the existing VM with `osac --project "$PROJECT_B" get computeinstance "$VM_REVOKED_INITIAL" -o yaml`. In deployed E2E, set `$VM_ADDRESS` to this VM's reachable address and retry the strict SSH command with its original private key. | The original VM remains available in B and still references A's Secret ID. The private key that worked before revocation still authenticates; no reinjection is needed. |
| 6 | Tenant Admin restores Project A assignment through the supported membership API/fixture and waits for convergence. | The user's original access is restored. |

### TC-09 — Reject invalid SSH-key data and unusable Secret references

**Description:** Try to save invalid public keys, then try to create VMs with
a key that is missing, deleted, or stored as a different kind of Secret. Each
request should fail without saving a VM or revealing hidden key details.

**Category:** Mixed
**Test tier:** Unit and component integration for API rejection/no-persistence; deployed E2E for CR/provider absence
**Priority:** Critical
**Automation:** Existing OpenSSH payload tests cover core shapes; extend for supported contract
**Run now:** Use the tenant's default project and bare-name selectors for
missing, deleted, and wrong-type references. Run all invalid-key fixtures,
including two-key and trailing-content inputs, on current `main`.

Run `osac project --clear` before this case so every Secret and VM below is
in the tenant's default project. Each table row is an independent attempt;
check that rejected create commands return a nonzero status.

Create synthetic invalid fixtures locally. Use private-key-like test text, not the generated private key or PEM contents, so the test never uploads private-key material.

Missing, deleted, hidden, and out-of-project references return gRPC
`NotFound` with the same generic message:
`SSH key Secret was not found or is not visible in the selected project`
Wrong-type and invalid-key payloads are validation errors and should be
reported separately. Component integration can prove that no API object
persists; assert CR/provider absence only in deployed E2E.

For a filtered CLI `get` with no match, the current CLI prints `[]` and exits
successfully. The checks below inspect the result instead of the exit code.

~~~bash
printf 'not an OpenSSH public key\n' > "$KEY_DIR/malformed.pub"
: > "$KEY_DIR/empty.pub"
printf '%s\n' 'OpenSSH private-key-like test text' 'TEST-ONLY-NOT-A-KEY' \
  > "$KEY_DIR/private-key-like.txt"
cat "$KEY_DIR/id_ed25519.pub" "$KEY_DIR/id_ed25519_b.pub" > "$KEY_DIR/two-keys.pub"
cp "$KEY_DIR/id_ed25519.pub" "$KEY_DIR/trailing.pub"
printf ' trailing-content\n' >> "$KEY_DIR/trailing.pub"
~~~

For each invalid fixture, map its case name to the file and run:

~~~bash
INVALID_CASES=(malformed private-key-like empty two-keys trailing)
for INVALID_CASE in "${INVALID_CASES[@]}"; do
  case "$INVALID_CASE" in
    malformed) INVALID_FILE="$KEY_DIR/malformed.pub" ;;
    private-key-like) INVALID_FILE="$KEY_DIR/private-key-like.txt" ;;
    empty) INVALID_FILE="$KEY_DIR/empty.pub" ;;
    two-keys) INVALID_FILE="$KEY_DIR/two-keys.pub" ;;
    trailing) INVALID_FILE="$KEY_DIR/trailing.pub" ;;
  esac
  SECRET_NAME="osac51-invalid-$RUN_ID-$INVALID_CASE"
  if CREATE_OUTPUT="$(osac create secret --name "$SECRET_NAME" --type ssh-public-key \
    --from-file "public_key=$INVALID_FILE" 2>&1)"; then
    osac delete secret "$SECRET_NAME"
    printf 'Unexpectedly accepted invalid key: %s\n' "$INVALID_CASE" >&2
    exit 1
  fi
  case "$CREATE_OUTPUT" in
    *InvalidArgument*) ;;
    *)
      printf 'Invalid key lacked the expected InvalidArgument status: %s\n' "$INVALID_CASE" >&2
      exit 1
      ;;
  esac
  SECRET_RESULT="$(osac get secrets "$SECRET_NAME" -o yaml)"
  if [ "$SECRET_RESULT" != '[]' ]; then
    printf 'Invalid Secret persisted: %s\n' "$SECRET_NAME" >&2
    exit 1
  fi
done
~~~

| Input / CLI action | Expected result |
|---|---|
| Valid Ed25519: run `osac get secrets "$DEFAULT_KEY" -o yaml` and compare its decoded `data.public_key` with `$KEY_DIR/id_ed25519.pub`. | One SSH public-key Secret exists with the same public-key bytes. Test RSA/ECDSA only if the final contract supports those formats. |
| Malformed, private-key-like, and empty fixtures. | Run the loop above now. Each create is rejected and the lookup returns `[]`; no Secret persists. |
| Two-key and trailing-content fixtures. | Run them with the loop above. Both creates are rejected and no Secret persists. |
| Wrong field: run `osac create secret --name "osac51-wrong-field-$RUN_ID" --type ssh-public-key --from-file "key=$KEY_DIR/id_ed25519.pub"`, then `osac get secrets "osac51-wrong-field-$RUN_ID" -o yaml`. | Rejected with `InvalidArgument` because required public_key data is absent; the lookup returns `[]` and no Secret persists. |
| Missing reference: run `osac project --clear`, then `osac create computeinstance --name "osac51-missing-ref-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-missing-$RUN_ID" "${NETWORK_ARGS[@]}"`; run `osac get computeinstance "osac51-missing-ref-$RUN_ID" -o yaml`. | Creation is rejected with `NotFound: SSH key Secret was not found or is not visible in the selected project`; the VM lookup returns `[]`. Use deployed E2E to assert no CR/provider operation. |
| Deleted reference: run `osac create secret --name "osac51-deleted-ref-key-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then `osac delete secret "osac51-deleted-ref-key-$RUN_ID"` and `osac get secrets "osac51-deleted-ref-key-$RUN_ID" -o yaml`. Run `osac create computeinstance --name "osac51-deleted-ref-vm-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-deleted-ref-key-$RUN_ID" "${NETWORK_ARGS[@]}"`, then `osac get computeinstance "osac51-deleted-ref-vm-$RUN_ID" -o yaml`. | Creation is rejected with the same `NotFound` message as a missing key; the Secret and VM lookups return `[]`. |
| Wrong type: run `osac create secret --name "osac51-opaque-$RUN_ID" --type opaque --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then `osac create computeinstance --name "osac51-wrong-type-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-opaque-$RUN_ID" "${NETWORK_ARGS[@]}"`; run `osac get computeinstance "osac51-wrong-type-$RUN_ID" -o yaml`. | The reference is rejected for wrong type and the VM lookup returns `[]`. Use an API fixture for missing data or lifecycle states not constructible through the CLI. |

### TC-10 — Reject malformed selectors and VM key changes, then check in-use deletion

**Description:** Try badly formatted `--ssh-key` values and attempts to change
the key already selected for a VM. Also check whether a key still used by a VM
can be deleted, according to the final policy.

**Category:** Negative with positive cleanup
**Test tier:** Unit for selector parsing; component integration for API immutability; deployed E2E if checking provider side effects
**Priority:** Critical
**Automation:** Selector parsing and VM reference immutability are covered on
`main`; no in-use deletion boundary test exists. OSAC-7284 observed that
deleting an in-use key is currently allowed.
**Decision needed:** Whether allowing deletion of an in-use SSH-key Secret is
intended. Keep step 4 non-blocking until the expected policy is recorded.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create an independent test Secret and VM using `osac --project "$PROJECT_A" create secret --name "$IMMUTABLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"` and `osac --project "$PROJECT_A" create computeinstance --name "$VM_IMMUTABLE" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$IMMUTABLE_KEY,project=$PROJECT_A" "${NETWORK_ARGS[@]}"`. | The VM persists with a canonical reference to `$IMMUTABLE_KEY`. |
| 2 | For each malformed selector in the matrix below, run the CLI command and query the unique VM name afterward. Where the test harness can count requests, record whether the CLI sent a Create request. Record the rejection layer for every selector. | A selector rejected by local CLI parsing returns `invalid --ssh-key value` and sends no Create request. If a selector passes the parser and is rejected by the API, record the server response separately. Every attempt leaves the filtered VM lookup at `[]`; do not attribute a local CLI error to server validation. |
| 3 | Run `osac --project "$PROJECT_A" edit computeinstance "$VM_IMMUTABLE"`. In the editor, change only `spec.ssh_key` to `$DEFAULT_KEY`'s canonical reference, save, and close. Repeat, removing `spec.ssh_key` from the edited YAML. Record each CLI response and get the VM after each attempt. `osac edit` sends an update for the fields changed in the editor. | Both updates are rejected with `InvalidArgument: ssh_key is immutable after creation`; each follow-up get still contains `$IMMUTABLE_KEY`'s original canonical ID/name/project. |
| 4 | Run `osac --project "$PROJECT_A" delete secret "$IMMUTABLE_KEY"` while `$VM_IMMUTABLE` references it. Inspect the Secret and VM afterward. | OSAC-7284 observed that deletion succeeds. Record the Secret and VM state; treat the result as an observation, not pass/fail, until an owner confirms whether allowing in-use deletion is intended. |
| 5 | Delete `$VM_IMMUTABLE` with `osac --project "$PROJECT_A" delete computeinstance "$VM_IMMUTABLE"` and wait until absent. If `$IMMUTABLE_KEY` still exists, delete it with `osac --project "$PROJECT_A" delete secret "$IMMUTABLE_KEY"` and wait until absent. | The VM is removed; the test Secret is also removed regardless of the step 4 policy. |

Use distinct selectors to exercise each parser failure:

~~~bash
BAD_SELECTORS=(
  '   '
  'name='
  "project=$PROJECT_A"
  "name=$DEFAULT_KEY,name=$DEFAULT_KEY"
  "name=$DEFAULT_KEY,project=$PROJECT_A,project=$PROJECT_B"
  "name=$DEFAULT_KEY,region=x"
  "name=$DEFAULT_KEY,"
  "name=$DEFAULT_KEY,project"
  "$DEFAULT_KEY,$PROJECT_KEY"
)

for INDEX in "${!BAD_SELECTORS[@]}"; do
  SELECTOR="${BAD_SELECTORS[$INDEX]}"
  INVALID_VM="osac51-invalid-selector-$RUN_ID-$INDEX"
  if osac --project "$PROJECT_A" create computeinstance \
    --name "$INVALID_VM" --catalog-item "$CATALOG_ITEM" \
    "${NETWORK_ARGS[@]}" --ssh-key "$SELECTOR"; then
    osac --project "$PROJECT_A" delete computeinstance "$INVALID_VM"
    printf 'Unexpectedly accepted selector: %s\n' "$SELECTOR" >&2
    exit 1
  fi
  VM_RESULT="$(osac --project "$PROJECT_A" get computeinstance "$INVALID_VM" -o yaml)"
  if [ "$VM_RESULT" != '[]' ]; then
    osac --project "$PROJECT_A" delete computeinstance "$INVALID_VM"
    printf 'Invalid-selector VM persisted: %s\n' "$INVALID_VM" >&2
    exit 1
  fi
done
~~~

### TC-11 — Create Linux VMs with or without keys and reject unsupported guests

**Description:** Compare VM images that can and cannot receive a registered
key at first boot. A cloud-init Linux VM with a key is the positive control;
a keyless Linux VM must still start normally. A Windows or incompatible
non-cloud-init image must not silently accept a key it cannot inject.

**Category:** Mixed
**Test tier:** Unit validation and deployed E2E provisioning; component integration for API acceptance/rejection
**Priority:** High
**Automation:** Linux projection and Windows rejection were exercised in
OSAC-7284. The Ignition row is Not run because the API's `guest_os_family`
field exposes only `LINUX` and `WINDOWS`.

Run `osac project --clear` before each executable row so the VMs use the default
project. The Linux fixtures must not contain the freshly generated test key
except when OSAC injects it through `--ssh-key`.

| Guest scenario | CLI command | Expected result |
|---|---|---|
| Linux cloud-init with a registered key. | `osac create computeinstance --name "osac51-linux-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "$DEFAULT_KEY"`; inspect with `osac get computeinstance "osac51-linux-key-$RUN_ID" -o yaml`. | VM reaches Running with the selected key reference. TC-12 independently tests guest login. |
| Linux cloud-init without a key. | `osac create computeinstance --name "osac51-linux-no-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" "${NETWORK_ARGS[@]}"`; inspect with `osac get computeinstance "osac51-linux-no-key-$RUN_ID" -o yaml`. | VM reaches Running with no `spec.ssh_key` reference. If trusted guest inspection is available, the generated test public key is absent from the guest's authorized keys. |
| Windows DiskImage locked by the CatalogItem; its SSH-key policy is not locked, and a registered key is explicitly selected. | Run `osac create computeinstance --name "osac51-windows-key-$RUN_ID" --catalog-item "$WINDOWS_CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "$DEFAULT_KEY"`, then `osac get computeinstance "osac51-windows-key-$RUN_ID" -o yaml`. | Create reaches guest compatibility validation and is rejected with `InvalidArgument: SSH key injection is not supported for Windows instances` before provisioning; the filtered get returns `[]`. |
| Ignition/non-cloud-init Linux image with a key. | Not executable with the current API: `guest_os_family` offers only `LINUX` and `WINDOWS`, so the Ignition row cannot be represented by a supported create request. Do not run a substitute CatalogItem and label it an Ignition test. | Not run in OSAC-7284. Keep the unsupported-first-boot-format contract as an API/design gap until the request model can express the case. |

This is a negative compatibility test for registered-key injection. It does not assert that a keyless Windows VM cannot be created.

### TC-12 — Log in with the matching private key and reject an unrelated key

**Description:** Create a Linux VM with a saved key and give it an address
reachable from the test client. Log in with the matching private key, then
confirm that an unrelated private key cannot log in.

**Category:** Positive E2E plus negative authentication
**Test tier:** Manual deployed E2E
**Priority:** Critical
**Automation:** OSAC-7284 reports matching-key login and wrong-key rejection;
the current OSAC E2E still verifies resource projection, not actual login.
Javier's [`ssh_probe.yml`](https://gitlab.cee.redhat.com/frmoreno/osac-vmaas-deployment/-/blob/main/e2e/roles/vmaas_ssh_key_registry/tasks/actions/ssh_probe.yml?ref_type=heads)
uses `IdentitiesOnly=yes` but does not isolate SSH configuration or disable
agent identities and control sockets. Treat its reported result as observed
behavior until the helper adopts the isolated SSH options above; maintained
login automation remains tracked by [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526).

The current
[`tc_12_ssh.yml`](https://gitlab.cee.redhat.com/frmoreno/osac-vmaas-deployment/-/blob/main/e2e/roles/vmaas_ssh_key_registry/tasks/testcases/tc_12_ssh.yml?ref_type=heads)
also places `--network-attachment` in its create argv unconditionally, while
its login helper has a provider-disabled MetalLB branch. The external suite
needs a mode-aware create argument before that branch verifies VM creation
without provider networking.

**Preconditions:** `$DEFAULT_KEY` exists from common setup. With provider
networking enabled, use a Ready Subnet/SecurityGroup and a routable ExternalIP
when available. With provider networking disabled, OSAC provides no tenant
ExternalIP or NetworkAttachment; the VM uses its default interface. For that
lab mode, use the MetalLB LoadBalancer and `virtctl port-forward` route
exercised in OSAC-7284. This is test-client access outside OSAC's ExternalIP
contract. Record applicable SecurityGroup rules and use strict host-key
verification. If neither route works, mark this case Inconclusive.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`, then create the VM with `osac create computeinstance --name "$VM_SSH_E2E" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" "${NETWORK_ARGS[@]}"`. Wait for Running and inspect with `osac get computeinstance "$VM_SSH_E2E" -o yaml`. | The VM is Running in the default project with `$DEFAULT_KEY`'s reference. With provider networking enabled it has the prepared attachment; with it disabled it uses the documented default-interface fallback. |
| 2 | With provider networking enabled and a Ready ExternalIPPool with capacity, run `osac create externalip --name "$EXTERNAL_IP_NAME" --pool "$EXTERNAL_IP_POOL"`; wait until Allocated, then run `osac create externalipattachment --name "$EXTERNAL_IP_ATTACHMENT" --externalip "$EXTERNAL_IP_NAME" --compute-instance "$VM_SSH_E2E"`. Poll both resources until Allocated/Ready; set `VM_ADDRESS` to `status.address` and `VM_PORT=22`. If provider networking is disabled, do not create OSAC ExternalIP resources; use the VMaaS lab's MetalLB LoadBalancer and start `virtctl port-forward` to guest TCP/22; set `VM_ADDRESS=127.0.0.1` and `VM_PORT` to the forwarded local port (for example, 2222). Record the chosen route and endpoint. | The test client reaches guest TCP/22 through the chosen route. If neither route works, record Inconclusive. |
| 3 | Obtain and pin the guest host key using the approved lab procedure over the chosen route, set `KNOWN_HOSTS`, `VM_ADDRESS`, and `VM_PORT`, and run the common strict SSH command from the setup section. | Exit 0; stdout is OSAC_SSH_OK; no password prompt. |
| 4 | Repeat the strict SSH command with `-i "$KEY_DIR/id_ed25519_b"` instead of the matching private key; keep the same target and host-key settings. | Authentication fails with a nonzero exit. A timeout or host-key error is Inconclusive, not evidence that the wrong key was rejected. |
| 5 | If either login result is unexpected, collect the serial console, cloud-init, and sshd evidence available for this VM before cleanup. | Evidence distinguishes key injection, VM readiness, and network failures. |
| 6 | Stop the `virtctl port-forward` process if used. If this case created an ExternalIP attachment, detach it and wait, then delete the ExternalIP. Delete `$VM_SSH_E2E`; remove only the route resources created by this case. Delete `$DEFAULT_KEY` in final cleanup after every VM using it is removed. | Route resources are removed before their VM dependencies; all resources created by this case disappear and the shared key remains for other cases. |

### TC-13 — Record how key updates affect existing and future VMs (policy decision needed)

**Description:** Record what happens when saved key data is changed before
and after a VM uses it. This is an observation case, not a pass/fail test,
until OSAC defines whether those updates are intended.

**Category:** Record-only
**Test tier:** Component integration and deployed E2E
**Priority:** Medium
**Execution status:** OSAC-7284 recorded both updates as accepted and observed
the effect on existing and future guests; no product policy was asserted.
**Automation:** The observation is in the external deployed Ansible suite; it
is not a maintained OSAC regression case.
**Decision needed:** Whether `data.public_key` on a registered Secret can be
updated, including while a VM refers to that Secret.
**Prerequisite:** An authenticated public API client can call `Secrets.Update`.
The Linux CatalogItem and network attachment from common setup are Ready;
guest-login steps also need a reachable VM address and trusted host key as in
TC-12.

Use the two distinct key pairs from common setup; only their `.pub` files are
sent to OSAC. For each update, use an authenticated public `Secrets.Update` request
with the existing Secret ID, the replacement `data.public_key` bytes from
`$KEY_DIR/id_ed25519_b.pub`, and `update_mask.paths: ["data"]`. Preserve the
Secret's other fields and record the request, status, and response. Inspect
the Secret after each attempt because an update response may redact its data.
Do not report these observations as a pass or fail until the update policy is
approved.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`. Create an unused key with `osac create secret --name "osac51-update-unused-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`; repeat with the name `osac51-update-in-use-$RUN_ID`. Inspect both and record their IDs and public-key data. | Both Secrets contain the original public key and have different IDs. Neither is used by a VM yet. |
| 2 | Replace the unused Secret's `data.public_key` with the second public key through `Secrets.Update`, then get the Secret again. | Observed in OSAC-7284: update is accepted; the ID stays the same and stored bytes match `id_ed25519_b.pub`. Record only; the intended policy is unresolved. |
| 3 | Run `osac create computeinstance --name "osac51-update-original-$RUN_ID" --catalog-item "$CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "osac51-update-in-use-$RUN_ID"`. Inspect its saved reference; once Running and reachable, log in with `$KEY_DIR/id_ed25519` using the strict SSH procedure in common setup. | The reference identifies the in-use Secret and the original private key authenticates. Record the VM address and login result before attempting the update. |
| 4 | Replace the in-use Secret's `data.public_key` with the second public key through `Secrets.Update`, then get the Secret and retry SSH to the existing VM with both private keys. | Observed in OSAC-7284: update is accepted; the existing VM still accepts the original private key and rejects the second. Its reference identifies a Secret whose current data no longer matches the key injected into that guest. Record only; the intended policy is unresolved. |
| 5 | Run `osac create computeinstance --name "osac51-update-future-$RUN_ID" --catalog-item "$CATALOG_ITEM" "${NETWORK_ARGS[@]}" --ssh-key "osac51-update-in-use-$RUN_ID"`. Once Running and reachable, try both private keys with strict SSH verification. | Observed in OSAC-7284: the new VM accepts the second private key and rejects the original. Record only; the intended update policy is unresolved. |
| 6 | Delete both VMs with `osac delete computeinstance` and wait until absent; then delete `osac51-update-unused-$RUN_ID` and `osac51-update-in-use-$RUN_ID` with `osac delete secret` and confirm both are absent. | No resources created by this case remain. |

The observed behavior leaves existing guests unchanged while changing what a
new VM receives from the same Secret. Whether to allow this state is an open
product decision.

## Nonfunctional checks

### NFR-SSH-01 — Private-key handling and output hygiene

**Description:** Check that only the public key is sent to OSAC. Command
output, API responses, and service logs must never show the matching private
key or another tenant's key data.

**Test tier:** Unit for log redaction; deployed E2E for CLI, OSAC pod, and AAP output
**Priority:** High
**Automation:** `fulfillment-service/internal/logging/logging_interceptor_test.go`
on `main` verifies SSH public-key Secret data is redacted from body logs.
OSAC-7284 reports a deployed leak scan passed.

| Step | Action | Expected result |
|---|---|---|
| 1 | In TC-01, pass only `$KEY_DIR/id_ed25519.pub` to `--from-file`. Capture CLI output, API responses, all OSAC pod logs, and the AAP job output for the case. | The private-key file is never supplied to OSAC. The public key may appear in API responses; it does not appear in service or AAP logs. |
| 2 | Trigger TC-09's invalid-key request with a synthetic invalid payload. Scan captured CLI output and all captured OSAC pod/AAP logs for the private key and submitted invalid payload, each in raw and base64-encoded form. Run the scanner's self-test before accepting its result. | The scanner self-test passes and finds no private-key material or invalid payload in CLI output or logs. OSAC-7284 reports this result; public-key data appeared only in API responses. |
| 3 | As Tenant-B User in TC-07b, try to select Tenant A's key by ID and name through the supported public API. | Tenant B receives no key data; TC-07b and NFR-SSH-02 compare each response with its nonexistent-key equivalent and confirm no VM is created. |

### NFR-SSH-02 — Non-disclosing authorization failures

**Description:** Compare the error shown for a key that does not exist with
errors for keys the user is not allowed to use. The responses must not let the
user discover that a hidden key exists, and no VM should be created.

**Test tier:** Unit, component integration, and deployed E2E
**Priority:** High

**Automation:** Current `main` covers missing, hidden, and out-of-project
references in unit/component-integration tests. OSAC-7284 reports deployed
cross-tenant equivalence by ID and name; output/log hygiene is covered by
NFR-SSH-01.

Use the same authenticated caller and VM destination for each comparison so
only the selected key changes. Record the gRPC status and public message;
do not compare internal logs that may legitimately carry a diagnostic reason.

| Step | Action | Expected result |
|---|---|---|
| 1 | As the Tenant User in TC-07a after Project A access is removed, run `osac --project "$PROJECT_B" create computeinstance --name "$VM_NFR_MISSING_B" --catalog-item "$CATALOG_ITEM" --ssh-key "$NFR_MISSING_KEY_B" "${NETWORK_ARGS[@]}"`; Tenant Admin queries that VM name. | This Project B request returns `NotFound: SSH key Secret was not found or is not visible in the selected project`; no VM persists. |
| 2 | With the same caller, Project B destination, CatalogItem, and network arguments, run TC-07a step 2 with the existing key in Project A; query the attempted VM name. | The public error class and message match step 1, disclose no Secret metadata, and no VM persists. The rejection comes from general reference validation, not a dedicated project-membership check. |
| 3 | As Tenant-B User, repeat TC-07b's known Tenant-A key lookups by ID and name, and compare them with unknown ID/name references using the same caller and VM destination. | The known other-tenant key is refused exactly like a missing key by both ID and name; no VM persists. OSAC-7284 reports this at deployed tier. |

## Regression coverage

Add regression cases to
`tests/e2e/vmaas/regression/test_compute_instance_registered_ssh_key.py` and
mark them with `pytest.mark.regression`. Run from the OSAC repository root:

~~~bash
uv run pytest -m regression tests/e2e/vmaas/regression/test_compute_instance_registered_ssh_key.py
~~~

These regression cases require the configured VMaaS environment, credentials,
and VM fixtures. OSAC-7284 reports a deployed Ansible run for TC-01–12,
including guest authentication; those results are not maintained OSAC CI
coverage. The existing registered-key OSAC E2E remains a `sanity` smoke check.
This documentation change adds no test code.

| Regression target | Test case mapping | Test tier | Current status and expected assertion |
|---|---|---|---|
| A normal VM without a registered key continues to create and run. | TC-11 | Deployed E2E regression | OSAC-7284 reports this path passed. Add a maintained regression case asserting Running and no registered-key reference or injected registered key. |
| A VM created with a registered key still receives the exact selected public key. | TC-02–05 | Deployed E2E | OSAC-7284 reports the project-selection matrix passed. The existing OSAC sanity test checks only TC-02's resource boundary; add the matrix to maintained regression coverage. |
| Invalid, missing, or out-of-scope keys do not persist a VM. | TC-07; TC-09; NFR-SSH-02 | Unit/component-integration for no persistence; deployed E2E for CR/provider absence | OSAC-7284 reports deployed negative cases passed. Maintained E2E coverage for CR/provider absence remains a gap. |
| In-use key deletion and immutable key references retain the agreed behavior. | TC-10; UT-SSH-05 | Unit and component integration regression | Reference immutability is covered on `main`; OSAC-7284 observed in-use deletion is allowed. The deletion policy and an SSH-key-specific deletion assertion remain open. |
| The selected key authenticates, and an unrelated private key is rejected. | TC-12 | Deployed E2E | OSAC-7284 reports both authentication checks passed. Maintained OSAC regression coverage still needs routed access and strict host-key verification. |

These targets map functional cases to regression automation; they are not additional scenarios.

## Gaps and planning decisions

| Gap / decision | Current evidence | Follow-up |
|---|---|---|
| Direct cross-project key selection | The 2026-10-22 decision permits a VM creator with access to both projects to select a key across projects, including the default project in either role. Merged PR #1828 implements project-aware selection; OSAC-7284 reports deployed coverage. | Keep the rule in TC-03/05/07 and move the deployed project matrix into maintained OSAC E2E coverage if required. |
| Key-name requirement wording | The confirmed rule allows the same name in different projects of one tenant, while the current PRD says names are unique within a tenant. | Align the PRD wording with per-tenant, per-project uniqueness; execute TC-05's same-name creation and project-qualified VM checks. |
| CatalogItem support | OSAC-51 design excludes CatalogItem defaults; the current service and OSAC-7284 run demonstrate defaults, overrides, and locks for tenant-scoped items. Shared items cannot hold key policy, and an empty policy represents no key. | Confirm release scope; keep TC-06 observed behavior separate from acceptance until the design/product contract is aligned. |
| Project membership/revocation | New VM creation requires access to both projects. OSAC-7284 reports that after revocation a new VM is denied while the existing VM remains accessible with its injected key. | Retain TC-08; add this transition to maintained component-integration/E2E coverage if required. |
| Shared-tenant rules | Merged PR #1828 rejects SSH-key Secret creation in the shared tenant and rejects `shared: true` references. OSAC-7284 reports the deployed isolation cases passed. | Keep Secret creation and reference checks distinct in TC-07 and maintained regression coverage. |
| In-use SSH-key deletion | OSAC-7284 observed that deleting a Secret referenced by a VM is currently allowed; no SSH-key/ComputeInstance deletion assertion exists on `main`. | Decide whether a referenced key Secret must be protected. Add a specific unit/component-integration assertion if protection is required. |
| Guest compatibility | Windows DiskImage key injection is rejected before provisioning with `InvalidArgument: SSH key injection is not supported for Windows instances`. `guest_os_family` only exposes `LINUX` and `WINDOWS`, so the Ignition row cannot be expressed and was Not run. | Keep the Ignition contract as an API/design gap until the request model can express it; do not claim an executable test. |
| Real SSH in maintained CI | OSAC-7284 reports guest login and wrong-key rejection through its deployed Ansible suite. The OSAC sanity E2E only checks resource projection. | Add the SSH route and login assertions to maintained E2E if required; track under [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526). |
| Key-data update behavior | OSAC-7284 observed that updates are accepted before and while a VM uses the key. Existing guests keep the old key; new VMs receive the new key, leaving the existing VM reference pointing at changed Secret data. | Decide whether this is intended. Keep TC-13 record-only until the policy is approved. |
| Integration execution | PR #1828's integration package was compile-only because host mappings were unavailable. OSAC-7284 is deployed E2E evidence, not a component-integration run. | Run the component-integration suite in a suitable environment before marking it executed. |

## Exit criteria

- The planned cases trace to agreed requirements and the cross-project access decision; TC-06, TC-10 step 4, and TC-13 receive explicit expected results before becoming release-blocking.
- Each successful VM reference resolves to the expected key; for SSH acceptance cases, the matching private key authenticates.
- Negative cases use the agreed error class, disclose no cross-scope key metadata, and persist no unintended VM. Where required, deployed E2E also confirms no ComputeInstance CR or provider operation.
- The wrong private key fails authentication; tests use strict host-key verification.
- In-use deletion, CatalogItem behavior, and updates match the final recorded policy.
- Cleanup leaves no test resources.
- Coverage spans unit, component integration, and deployed cross-component journeys without duplication or gaps.
- OSAC-7284 records deployed Ansible results on `edge120` at upstream `c8d3165d6`, `failed=0`, in 2h 14m. TC-11's Ignition row is Not run and TC-13 is record-only; neither is a pass/fail acceptance result.
- Mark future cases Executed only after recording target build SHA, environment, command, outcome, and evidence. External run results do not establish that the component-integration suite ran.

## Summary

| Metric | Count |
|---|---:|
| Total scenario cases | 15 (13 functional, 2 nonfunctional) |
| Priority | 5 critical, 9 high, 1 medium (TC-13 record-only pending policy decision) |
| VMaaS PRD requirement areas mapped | 5 / 5; ComputeInstance behavior only |
| Planned unit coverage slices | 6 |
| Planned component-integration coverage slices | 7 |
| Existing SSH-key-specific component-integration files on `main` | 5 (Secret lifecycle, direct ComputeInstance selection, ComputeInstance CatalogItem behavior, CatalogItem CLI display, and shared-key creation); generic Secret authorization remains a separate concern |
| Existing deployed VMaaS SSH-key sanity scenarios on `main` | 1 (CR key projection; no guest login) |
| Local cleanup-helper tests in the sanity file | 2 (no VM deployment) |
| Existing registered-key VMaaS regression-marked cases on `main` | 0 |
| Regression targets mapped (not additional cases) | 5 |
| Dedicated real-SSH E2E case | 1 (TC-12; OSAC-7284 reports it passed, but it is not maintained OSAC CI coverage) |
| Checks needing a decision (listed in Overview) | 3: TC-06, TC-10 step 4, TC-13 |
| Unsupported compatibility row | 1: TC-11 Ignition is not expressible and was Not run |
| Executable test code added by this plan PR | 0 |

**Execution status:** OSAC-7284 reports TC-01–12 passed on `edge120` at
upstream `c8d3165d6`, with `failed=0` in 2h 14m. TC-11's Ignition row was Not
run; TC-13 ran as a record-only observation without a policy assertion.
NFR-SSH-01 passed and NFR-SSH-02 was covered in
TC-07a, TC-07b, and TC-08. See the linked [Jira run report](https://redhat.atlassian.net/browse/OSAC-6527?focusedCommentId=19366401).
