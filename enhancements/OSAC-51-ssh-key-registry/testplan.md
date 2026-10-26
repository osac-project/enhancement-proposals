# Test Plan — OSAC-51 Public SSH Key Registry

**Status:** Working draft for planning
**Updated:** 2026-10-26
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
- **Decisions still needed:** TC-06 (CatalogItem key defaults), TC-10 step 4
  (deleting a key used by a VM), and TC-13 (updating saved key data). Keep
  those checks non-blocking until their expected behavior is agreed. TC-11's
  non-cloud-init row has a stated rejection expectation but needs a test fixture.
- **Regression status:** `main` has one deployed registered-key sanity scenario but no registered-key VMaaS regression-marked case; five regression targets are planned.
- **Implementation status:** This change documents coverage; it adds no unit, integration, or E2E test code.
- **Execution status:** Existing and in-flight unit/integration anchors are identified; PR-reported unit results are noted below. The full integration suite was not run, and guest SSH checks in TC-03–05 and TC-12 remain manual.

**Manual run gate before PR #1828 is deployed:** TC-01 and TC-09's basic
Secret inputs; the bare-name path of TC-02 and TC-09's default-project VM
references when VM fixtures are ready; TC-11's Linux and available Windows
paths; and TC-12 when the VM is reachable. Run NFR-SSH-01 alongside TC-01/09.
Keep project-aware checks and full NFR-SSH-02 marked Not run until a build
containing PR #1828 is deployed. Defer TC-06, TC-10 step 4, and TC-13 until
their decisions are recorded; defer TC-11's non-cloud-init row until its
fixture is available.

| OSAC-51 PRD requirement | Test coverage | Coverage note |
|---|---|---|
| Register, list, retrieve, and delete SSH public-key Secrets | TC-01; UT-SSH-01 | Lifecycle and data shape are covered. |
| Select a registered key when creating an instance and inject it at first boot | TC-02–05, TC-11–12; UT-SSH-03, UT-SSH-06 | This plan maps the ComputeInstance/VMaaS behavior only. |
| Keep keys tenant-scoped and available only to authorized tenant users | TC-03–05, TC-07–08; NFR-SSH-02; UT-SSH-03 | Direct cross-project key selection requires the VM creator to have access to both projects, including when either is the default project. |
| Reject malformed OpenSSH public keys | TC-09; UT-SSH-01 | Public-key validation is covered at unit and API boundary tiers. |
| Enforce key-name uniqueness (PRD wording needs alignment) | TC-01, TC-05, TC-07; UT-SSH-03 | Names are unique within a tenant and project. TC-05 verifies the same name can exist in two projects of one tenant, and TC-01 rejects a duplicate in one project. |

These are planned mappings, not evidence that every case has executed or passed.

## Automation status at a glance

**On `main`** means present in upstream at the snapshot date. **PR #1828** is
open and unmerged, so its tests are not current coverage. **Next** identifies
gaps to automate or validate manually; planned work is not implemented yet.

| Tier | Already automated on `main` | In PR #1828 (unmerged) | Next automation or manual validation |
|---|---|---|---|
| Unit | SSH-key payload/type validation, bare-name `--ssh-key` selection, ComputeInstance reference resolution/immutability, Windows rejection, and controller key handoff. | Strict key syntax, project-aware selector/reference checks, and CatalogItem policy tests. | Extend only uncovered assertions: malformed payload edge cases, project-scope denial/non-disclosure, and in-use SSH-key deletion if required by the final contract. |
| Component integration | Secret CLI lifecycle; ComputeInstance CatalogItem locked/editable policy; CatalogItem CLI display. Generic Secret isolation does not prove ComputeInstance key-reference behavior. | Direct ComputeInstance selection, project selection/defaulting, denied-project non-disclosure, and shared-key creation rejection. | Run the fulfillment integration suite in a suitable environment; add invalid-reference/no-side-effect and access-revocation cases. Add deletion guards if the final contract requires them. |
| Deployed E2E | One VMaaS sanity case creates a VM and checks key projection into the ComputeInstance CR; it does not verify guest SSH login. | No deployed VMaaS E2E coverage is added by PR #1828. | Add regression-marked VMaaS cases. Guest login in TC-03–05 and TC-12 remains manual until the runner can route to the VM (see OSAC-6526). |

The detailed inventory below lists the existing test files, PR-only changes,
and gaps. UT-SSH-01–06 describe target assertion areas; they map to existing
coverage as well as gaps and do not mean six entirely new unit tests.

## Plan description

Verify the key lifecycle, selection during VM creation, and guest
authentication. The 13 functional cases preserve the first draft. Unit,
integration, and regression coverage are mapped to existing tests and
outstanding gaps.

Seeing a key reference on a ComputeInstance does not prove guest access; positive acceptance cases require SSH login when policy permits VM creation.

**Terms used below:** A *VM* is a virtual computer, and *SSH* is a way to log
in to it remotely. A *Secret* is OSAC's record for the saved public key. A
*CatalogItem* is a VM offering with preset settings. A *tenant* is an isolated
resource space, and a *project* groups resources and access within it. The
*guest* is the operating system inside a VM. OSAC stores the public key, while
the matching private key stays with the tester and is used to log in.

Context: [OSAC-51](https://redhat.atlassian.net/browse/OSAC-51), VM work [OSAC-5428](https://redhat.atlassian.net/browse/OSAC-5428) and [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584), and [OSAC PR #1828](https://github.com/osac-project/osac/pull/1828). Add remaining epic requirements after planning.

### How to read deferred checks

The cross-project rules in TC-03–05 and TC-08 are agreed; they await a build
with PR #1828. The three decisions listed in the Overview concern different
behaviors. Record the decision and expected result before treating those
specific checks as pass/fail criteria.

### Contract and scope gate

The 2026-10-22 cross-project reference decision allows a VM in one project to
select an SSH-key Secret in another when the VM creator can access both
projects. Either project may be the default project. TC-03, TC-05, and TC-07
use that rule as their expected behavior. [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584)
and unmerged [PR #1828](https://github.com/osac-project/osac/pull/1828) add
project-aware selection; the earlier [OSAC-51 design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-51-ssh-key-registry/design.md)
describes a tenant-scoped local reference. The confirmed naming rule is unique
within each tenant and project: two projects in one tenant may each contain a
key with the same name. The [PRD](prd.md) still says names are unique within a
tenant and needs to be aligned with this decision. A key is injected when the
VM is created. If its creator later loses access to the key's project, the
running VM remains accessible with that key, but the user cannot create
another VM with it. CatalogItem defaults remain a separate open decision.
PR #1828 proposes rejection of shared-tenant SSH keys; validate that behavior
after its reviewed build is deployed.

Use an IPv4 ExternalIP address reachable from the test client. Networking is a
prerequisite, not a behavior under test. This follows the current
[VMaaS networking contract](../OSAC-1435-vmaas-networking/design.md), where
ExternalIP replaces the legacy PublicIP name and is not necessarily
internet-routable.

## Detailed existing coverage and test infrastructure

This snapshot was checked against upstream [`main` at `a6d3626`](https://github.com/osac-project/osac/commit/a6d3626e5a50b503862f4a16faef44e68d13dbd6) on 2026-10-22. [PR #1828](https://github.com/osac-project/osac/pull/1828) is still open and has not merged; its tests are labeled **PR #1828**, not current coverage. All paths are relative to the OSAC repository root. Detailed behavior is specified once in the cases below.

<details>
<summary>Show test files, coverage gaps, and run commands</summary>

### Unit test coverage

| Coverage / cases | On upstream `main` | PR #1828 (open) / remaining gap |
|---|---|---|
| UT-SSH-01 / TC-09 — payload validation | `fulfillment-service/internal/servers/secret_validation_test.go` checks valid, missing, and malformed data; `internal/servers/private_compute_instances_ssh_key_test.go` checks wrong type and missing `public_key`; `internal/servers/private_secrets_server_test.go` checks valid/invalid Hub-backed SSH-key data; `internal/cmd/cli/create/secret/create_secret_cmd_test.go` recognizes the `ssh-public-key` type. | Adds `internal/sshkey/validation_test.go` and invalid OpenSSH syntax coverage in the ComputeInstance server tests. `main` does not cover all planned malformed, trailing-content, or private-key-like inputs. |
| UT-SSH-02 / TC-10 — CLI selector | `fulfillment-service/internal/cmd/cli/create/computeinstance/create_compute_instance_cmd_test.go` checks bare-name reference construction and `--ssh-key` registration. | Adds project-aware selector parsing/validation. Structured `name`/`project` grammar and its invalid forms are not covered on `main`. |
| UT-SSH-03 / TC-02–05, TC-07 — reference resolution | `fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go` checks canonicalization by name/ID, immutability, Vault-backed reads/failures, empty references, type/data validation, and Windows rejection. The `main` contract is tenant-scoped. | Adds `internal/servers/compute_instance_ssh_reference_contract_test.go` and `internal/cmd/service/start/grpcserver/reference_validator_ssh_key_test.go` for project lookup, non-disclosing errors, shared-reference rejection, handler routing, full-reference immutability, and legacy decode. Project-aware behavior is not on `main`. |
| UT-SSH-04 / TC-06 — CatalogItem policy | No dedicated SSH-key policy-validation unit test was found on `main`. `fulfillment-service/internal/cmd/cli/describe/catalogitem/view_test.go` checks rendering the SSH-key policy as editable. The policy behavior below has component-integration coverage. | Adds `internal/servers/catalog_item_ssh_key_policy_test.go` for shared-reference restrictions and an editable field without a default. Full default/override/lock/no-key behavior remains dependent on planning. |
| UT-SSH-05 / TC-10 — immutability and deletion | The ComputeInstance test above checks reference immutability. `fulfillment-service/internal/servers/private_secrets_server_test.go` has a general Vault Secret in-use deletion guard for another active-resource reference; it is not an SSH-key/ComputeInstance assertion. | PR #1828 extends reference tests, but does not add a ComputeInstance-specific in-use SSH-key deletion test. Keep that boundary as a gap if deletion protection is part of the final contract. |
| UT-SSH-06 / TC-11 — controller handoff | `fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go` checks public-key handoff to the operator spec and classifies NotFound/InvalidArgument as permanent versus Unavailable/DeadlineExceeded/Canceled as retryable. | The same suite is updated for the PR's new reference shape. Core handoff and retry classification already exist on `main`. |

### Integration test coverage

| Coverage / cases | On upstream `main` | PR #1828 (open) / remaining gap |
|---|---|---|
| IT-SSH-01 / TC-01 — Secret lifecycle | `fulfillment-service/it/it_cli_ssh_key_lifecycle_test.go` creates, gets, and deletes a key through the CLI; it checks the name/ID and that get reports no object after deletion. | Happy-path lifecycle is covered. Duplicate-name rejection and response/log hygiene are not asserted by this case. |
| IT-SSH-02 / TC-02–05 — direct VM key selection | No dedicated registered-key ComputeInstance API/CLI integration test was found on `main`. | Adds `fulfillment-service/it/it_compute_instance_ssh_key_test.go`: name/ID lookup in a selected project, unnamed-project defaulting, non-disclosing missing/out-of-scope errors, bare/project-aware CLI selection, and a named-project CatalogItem default. It is not merged. |
| IT-SSH-03 / TC-06 — CatalogItem key policy | `fulfillment-service/it/it_compute_instance_catalog_items_test.go` creates a VM from a locked key policy and verifies the stored key ID; it also verifies editable-default policy read/update to locked without changing an unrelated field. `it_cli_catalog_item_describe_test.go` checks CLI rendering of the SSH-key policy. | Adds named-project CatalogItem selection in the new SSH-key integration suite. VM creation with editable override/no-key policy and guest login remain uncovered or policy-dependent. |
| IT-SSH-04 / TC-07–08 — authorization and isolation | `fulfillment-service/it/it_public_secrets_test.go` covers generic Secret visibility and cross-tenant get/delete, but not a ComputeInstance's SSH-key reference, project membership, or revocation. | The new VM integration suite adds a denied-project/non-disclosure case. Membership removal/revocation and all no-side-effect assertions remain gaps. |
| IT-SSH-05 / TC-07 — shared-tenant restrictions | No SSH-key-specific shared-tenant integration case was found on `main`. | PR #1828 adds shared SSH-key creation rejection to `fulfillment-service/it/it_public_secrets_test.go` and unit reference/policy checks. Shared-key resolution at the ComputeInstance integration boundary remains unproven. |
| IT-SSH-06 / TC-09 — invalid reference boundary | No ComputeInstance integration case on `main` asserts malformed, missing, or wrong-type SSH-key rejection before persistence/provisioning. Unit validation does not prove this boundary. | PR #1828 adds missing/out-of-scope lookup integration cases; malformed payload and wrong-type rejection at the ComputeInstance integration boundary remain gaps. Confirm scope under [OSAC-6584](https://redhat.atlassian.net/browse/OSAC-6584) or link the owning follow-up. |
| IT-SSH-07 / TC-10 — update/deletion guards | Main covers immutable references at unit level and unreferenced-key deletion in the lifecycle integration. It does not verify ComputeInstance reference updates or deletion of an in-use SSH key through the deployed API. | No such integration assertion was found in PR #1828. Add it only if the final contract requires those guards; link the owning follow-up if deferred. |

### E2E test coverage

| Coverage / cases | On upstream `main` | PR #1828 / remaining gap |
|---|---|---|
| E2E-SSH-01 / TC-02 and Linux part of TC-11 | `tests/e2e/vmaas/sanity/test_compute_instance_registered_ssh_key.py` generates/registers a key, creates a VM, waits for provisioned/running, and asserts the resolved key in the ComputeInstance CR. The same file has two local cleanup-helper tests; they do not deploy a VM. | This is one deployed `sanity` scenario, not guest-authentication coverage. No project matrix, keyless regression, wrong-key check, or real SSH login is covered. |
| E2E-SSH-02 / TC-03–05 | No deployed cross-project registered-key scenario exists on `main`. | PR #1828 adds component integration, not deployed E2E. Add default-to-named, named-to-named, named-to-default, and same-name project selection with guest SSH login. |
| E2E-SSH-03 / TC-12 | Manual test; no current CI anchor | Real login and wrong-key rejection require a client routed to the tenant VM subnet. Track CI/routing automation under [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526) if required. |

PR #1828 reports 2,337 server specs and 89 CLI specs passing. Its integration package was compile-only because host mappings were unavailable; these are PR-reported results, not execution evidence for this plan.

No registered-key test was found under `tests/e2e/vmaas/regression` on `main`. The regression table below is proposed coverage; the existing deployed VM key case is in `sanity`.

Run these checks from the OSAC repository root:

~~~bash
# Existing unit suites on main
(cd fulfillment-service && ginkgo run --timeout 10m internal/servers)
(cd fulfillment-service && ginkgo run --timeout 10m internal/cmd/cli/create/secret internal/cmd/cli/create/computeinstance internal/cmd/cli/describe/catalogitem)
(cd fulfillment-service && ginkgo run --timeout 10m internal/controllers/computeinstance)

# Added by PR #1828; package is not present on main
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

**Existing tests:** <code>fulfillment-service/internal/servers/secret_validation_test.go</code> and <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code>; PR #1828 adds <code>fulfillment-service/internal/sshkey/validation_test.go</code>. **Gap:** TC-09 adds a real Secret-create boundary check for cases not asserted by component integration.

### UT-SSH-02 — Parse the CLI key selector into the requested project

**Purpose:** Ensure the CLI's selector produces the intended Secret reference before VM creation. A bare name targets the unnamed project; the project-aware form must preserve an explicit project.

| Action | Expected result |
|---|---|
| Omit <code>--ssh-key</code>. | The CLI leaves the SSH-key reference unset; this is a valid no-key request. |
| Parse a bare name, <code>name=KEY</code>, and <code>name=KEY,project=</code>. | Reference name is KEY and project is empty. |
| Parse <code>name=KEY,project=PROJECT</code>. | Reference name is KEY and project is PROJECT. |
| Reject whitespace-only input, <code>name=</code>, missing <code>name</code>, duplicate or unknown fields, empty comma fragments, a structured fragment without <code>=</code>, or a bare value containing a comma. | Local CLI error begins <code>invalid --ssh-key value</code>; no API Create call occurs. |

**Existing tests:** <code>fulfillment-service/internal/cmd/cli/create/computeinstance/create_compute_instance_cmd_test.go</code> covers the bare name on current builds and structured parsing in PR #1828. **Gap:** TC-10 is an optional installed-CLI smoke check; do not duplicate every parser table row manually.

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

**Existing tests:** Current <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code>; PR #1828 adds <code>fulfillment-service/internal/servers/compute_instance_ssh_reference_contract_test.go</code> and <code>fulfillment-service/internal/cmd/service/start/grpcserver/reference_validator_ssh_key_test.go</code>. **Gap:** TC-07/TC-08 cover access changes across real authorization boundaries.

### UT-SSH-04 — Apply a CatalogItem key default without losing its project

**Purpose:** Check the policy path that supplies a key when the VM caller omits <code>--ssh-key</code>. Use distinct Secret IDs for the default and override so the selected key is visible; editable and locked policy outcomes should be checked separately.

| Action | Expected result |
|---|---|
| Apply an editable default with an explicit key project. | VM candidate receives that key's canonical ID, name, and project. |
| Override an editable default or attempt to override a locked default. | An allowed override selects the requested key; a locked override is rejected before VM persistence. |
| Omit a key when the CatalogItem has no key default and permits omission. | VM candidate has no SSH key reference. |

**Existing tests:** <code>fulfillment-service/it/it_compute_instance_catalog_items_test.go</code> covers locked/editable policy at the component boundary; PR #1828 adds <code>fulfillment-service/internal/servers/catalog_item_ssh_key_policy_test.go</code> for shared-reference restrictions and a named-project default integration case. **Gap:** Complete unit assertions for override/lock/no-key policy have not been verified; TC-06 checks the full default in an installed build.

### UT-SSH-05 — Keep a created VM's SSH key reference immutable

**Purpose:** Confirm an update cannot change or clear the key on a created VM. Secret deletion while referenced is a separate lifecycle rule and must not be inferred from immutability.

| Action | Expected result |
|---|---|
| Update a VM with a different key ID or project, or clear the reference. | <code>InvalidArgument</code>; original canonical reference remains unchanged. |
| Repeat an update without changing the reference identity. | No false immutability rejection. |
| If the final policy protects referenced keys, attempt to delete the Secret while its VM exists; delete the VM and retry. | First deletion is rejected and the later deletion succeeds. This remains deferred until the policy is agreed and implemented. |

**Existing tests:** <code>fulfillment-service/internal/servers/private_compute_instances_ssh_key_test.go</code>, extended in PR #1828 for the full reference. **Gap:** In-use Secret deletion protection is required by the clarification but is not implemented or tested by PR #1828; see the coverage inventory above.

### UT-SSH-06 — Pass the resolved key to the VM controller

**Purpose:** Verify the controller uses the registered Secret's public key when building the ComputeInstance CR, and classifies permanent reference failures separately from transient store failures.

| Action | Expected result |
|---|---|
| Reconcile a VM with a valid registered key. | Operator-facing ComputeInstance spec receives the exact public-key bytes. |
| Reconcile with <code>NotFound</code>/<code>InvalidArgument</code> versus <code>Unavailable</code>/<code>DeadlineExceeded</code>/<code>Canceled</code> lookup failures. | Invalid or missing references are permanent; the listed transient failures follow the controller's retry policy. |

**Existing tests:** <code>fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go</code>, updated in PR #1828 for the new reference shape. **Gap:** The existing deployed sanity test checks the CR; TC-12 checks real guest authentication.

**Run these suites:** From <code>fulfillment-service/</code>, run <code>go test ./internal/servers ./internal/controllers/computeinstance ./internal/cmd/cli/create/computeinstance -timeout 20m</code> on current source. On PR #1828 source, include <code>./internal/sshkey</code>. These commands test in-process logic with mocks or local collaborators; use the component integration and E2E commands below for real service and guest boundaries.

## Actors and prerequisites

| Role | Responsibility |
|---|---|
| Tenant User | Registers SSH-key Secrets, creates ComputeInstances, selects CatalogItems, and performs SSH verification. |
| Tenant Admin | Creates test projects and assigns/revokes Tenant User access where required by the test environment. |
| Cloud Provider Admin | Prepares published Linux/Windows/ignition templates, CatalogItems, and routable VM/network fixtures. |
| Administrative test fixture | Attempts shared-tenant key creation and verifies rejection/no persistence; this is setup, not a normal user persona. |
| Tenant-B User | Runs cross-tenant isolation checks. |

**Authorization model for test setup:** Treat tenant as the isolation boundary.
For a direct SSH-key reference, the VM creator must have access to both the VM
destination project and the selected key's project.

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
IGNITION_CATALOG_ITEM='replace-with-ignition-catalog-item'
NETWORK_ATTACHMENT='subnet=replace-with-subnet-id,security-groups=replace-with-ssh-security-group-id'
TENANT_B_NETWORK_ATTACHMENT='subnet=replace-with-tenant-b-subnet-id,security-groups=replace-with-tenant-b-ssh-security-group-id'
VM_USER='replace-with-image-login-user'
EXTERNAL_IP_POOL='replace-with-external-ip-pool'
DEFAULT_KEY="osac51-default-$RUN_ID"
LIFECYCLE_KEY="osac51-lifecycle-$RUN_ID"
PROJECT_KEY="osac51-project-a-$RUN_ID"
IMMUTABLE_KEY="osac51-immutable-$RUN_ID"
TENANT_COLLISION_KEY="osac51-tenant-collision-$RUN_ID"
SHARED_KEY="osac51-shared-$RUN_ID"
VM_DD="osac51-dd-$RUN_ID"
VM_DA="osac51-da-$RUN_ID"
VM_AA="osac51-aa-$RUN_ID"
VM_AB="osac51-ab-$RUN_ID"
VM_AD="osac51-ad-$RUN_ID"
VM_TENANT_B="osac51-tenant-b-$RUN_ID"
VM_REVOKED="osac51-revoked-$RUN_ID"
VM_REVOKED_INITIAL="osac51-revoked-initial-$RUN_ID"
VM_IMMUTABLE="osac51-immutable-$RUN_ID"
VM_SSH_E2E="osac51-ssh-e2e-$RUN_ID"
EXTERNAL_IP_NAME="osac51-ip-$RUN_ID"
EXTERNAL_IP_ATTACHMENT="osac51-ip-attachment-$RUN_ID"
KNOWN_HOSTS="$KEY_DIR/known_hosts"
ssh-keygen -t ed25519 -f "$KEY_DIR/id_ed25519_b" -N '' -C osac-51-test-b
~~~

`NETWORK_ATTACHMENT` must name a Ready Subnet and a Ready SecurityGroup that
permits TCP/22 from the test client and only the egress needed by the guest.
It must be selectable for VMs in Tenant A's default project and Projects A/B.
For TC-07, the Tenant B CatalogItem and network attachment must be valid in
Tenant B before testing a cross-tenant SSH-key rejection; otherwise a VM
request could fail for an unrelated missing fixture.
TC-12 also needs a Ready ExternalIPPool with capacity and a routable address.
Before VM cases, confirm the selected project and CatalogItem are usable and
the attachment resources are Ready. If the tenant's default project is still
Pending, continue only with Secret-only cases and mark VM cases Not run until
the prerequisites are ready.

At final cleanup, delete all test ComputeInstances before deleting their
Secrets, including `$DEFAULT_KEY`. Then remove only the temporary directory
created for this run. Do not reuse or override `KEY_DIR`.

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

Confirm that `osac whoami` shows a Tenant User in `$TENANT_A`, clear any saved
project, and verify that Projects A and B exist:

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
API and record its request and response.

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
4. Disable password fallback and use only the intended private key.

~~~bash
ssh -i "$KEY_DIR/id_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes \
  -o PreferredAuthentications=publickey -o PasswordAuthentication=no \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=10 \
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
projection. It does not test guest login.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`, then `osac create computeinstance --name "$VM_DD" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" --network-attachment "$NETWORK_ATTACHMENT"`. | One VM is created in the tenant's default project. |
| 2 | Wait for the VM to report Running. Run `osac get computeinstance "$VM_DD" -o yaml` and compare `spec.ssh_key.id`, `spec.ssh_key.name`, and `spec.ssh_key.project` with `$DEFAULT_KEY_ID`, `$DEFAULT_KEY`, and an empty project. | The VM is Running and its saved reference identifies the exact default-project Secret registered in common setup. This step does not assert that SSH login works. |

### TC-03 — Create a project A VM using a default-project SSH key

**Description:** Create a VM in Project A while selecting a key stored in the
default project. A user with access to both projects should be able to create
the VM and log in using the matching private key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Project selection is in unmerged PR #1828; add named-project deployed E2E.

**Prerequisite:** Tenant User has access to Project A and the default project.

| Step | Action | Expected result |
|---|---|---|
| 1 | Use the default-project key created in common setup and inspect it with `osac get secret "$DEFAULT_KEY" -o yaml`. | Key persists in the default project. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "$VM_DA" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" --network-attachment "$NETWORK_ATTACHMENT"`. | VM is created in Project A using the default-project key. |
| 3 | Run `osac --project "$PROJECT_A" get computeinstance "$VM_DA" -o yaml`. Once the VM is Running and reachable, set `$VM_ADDRESS` and run the strict SSH command from common setup. | The reference contains `$DEFAULT_KEY`'s ID/name and no named key project; the matching private key authenticates. |

### TC-04 — Create a project A VM using a key stored in project A

**Description:** Create a VM in Project A using a key saved in that same
project. The VM should point to Project A's key and allow login with the
matching private key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Project selection is in PR #1828; add named-project E2E.

**Prerequisite:** Tenant User has access to Project A.

| Step | Action | Expected result |
|---|---|---|
| 1 | Prepare `$PROJECT_KEY` in Project A as described in common setup, or inspect it there if already prepared. | Exactly one Secret exists with Project A recorded and the expected public key. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "$VM_AA" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. | VM is created with a canonical reference to Project A's key. |
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
**Automation:** Unmerged PR #1828 covers named-project key selection for a
default-project VM at the integration boundary. Add same-project duplicate
rejection, same-name cross-project selection, both deployed E2E paths, and real
SSH login to the relevant suites.

**Prerequisite:** Tenant User has access to Projects A and B and the default
project. `$PROJECT_KEY` exists in A as described in common setup and contains
`$KEY_DIR/id_ed25519.pub`.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a key in B with the **same name** as A's key but a different public key: `osac --project "$PROJECT_B" create secret --name "$PROJECT_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect both with `osac --project "$PROJECT_A" get secret "$PROJECT_KEY" -o yaml` and `osac --project "$PROJECT_B" get secret "$PROJECT_KEY" -o yaml`. If the CLI cannot create project-scoped Secrets, use the supported administrative/service fixture and record its request and response. | Both Secrets exist under one tenant with the same name but different projects, IDs, and public-key values. |
| 2 | Try to create another key named `$PROJECT_KEY` in A using `osac --project "$PROJECT_A" create secret --name "$PROJECT_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect A's key again. | The second create in A fails with `AlreadyExists`; A's original Secret ID and public key do not change. |
| 3 | Create a VM in B with `osac --project "$PROJECT_B" create computeinstance --name "$VM_AB" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. Inspect it with `osac --project "$PROJECT_B" get computeinstance "$VM_AB" -o yaml`. | The VM is created in B, and its saved SSH-key reference contains A's Secret ID and Project A, not B's Secret ID. |
| 4 | Once the B VM is Running and reachable, set `$VM_ADDRESS` to its address and run the common strict SSH command with `$KEY_DIR/id_ed25519`. Repeat with `$KEY_DIR/id_ed25519_b`. | A's private key authenticates; B's private key fails. This proves the VM received A's public key. |
| 5 | Run `osac project --clear`, then create a default-project VM with `osac create computeinstance --name "$VM_AD" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. Inspect it with `osac get computeinstance "$VM_AD" -o yaml`. When Running and reachable, set `$VM_ADDRESS` to this VM and try both private keys as in step 4. | The VM is created in the default project. Its reference contains A's Secret ID and Project A; A's private key authenticates and B's private key fails. |

### TC-06 — Create VMs with editable, locked, and empty CatalogItem key policies

**Description:** Check how a VM offering (CatalogItem) and a user's key choice
interact. One offering supplies a default key that the user may replace;
another locks its default key; a third has no key. The default and override
must be different Secrets so the saved VM reference shows which one won.

**Category:** Mixed
**Test tier:** Unit and component integration; deployed E2E if required
**Priority:** High
**Automation:** Locked-key policy is on `main`; add approved override/no-key paths and guest login.
**Decision needed:** The OSAC-51 design excludes CatalogItem key defaults.
Confirm that these offering behaviors belong in this release before using
the draft expected results below as pass/fail criteria.

**Prerequisite:** `$PROJECT_KEY` exists in Project A as described in common
setup. `CATALOG_ITEM` has no SSH-key default. Configure the editable and
locked CatalogItems with `$DEFAULT_KEY` from the default project; configure
the no-key item without a default. `$PROJECT_KEY` must have a different ID
so it can serve as the override. Inspect the CatalogItems with
`osac get computeinstancecatalogitems "$EDITABLE_KEY_CATALOG_ITEM" -o yaml`,
and repeat for the locked and no-key items.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a VM in A from `$EDITABLE_KEY_CATALOG_ITEM` without `--ssh-key`: `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-default-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"`. Inspect the VM with `osac --project "$PROJECT_A" get computeinstance "osac51-ci-default-$RUN_ID" -o yaml`. | Draft expectation: the saved reference contains `$DEFAULT_KEY`'s ID and default project. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-override-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`, then inspect the VM. | Draft expectation: the editable offering accepts the override and saves `$PROJECT_KEY`'s ID and Project A, rather than `$DEFAULT_KEY`'s ID. |
| 3 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-locked-$RUN_ID" --catalog-item "$LOCKED_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`, then query that VM name. | Draft expectation: the request fails, the lookup returns `[]`, no VM persists, and the locked CatalogItem still points to `$DEFAULT_KEY`. |
| 4 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-none-$RUN_ID" --catalog-item "$NO_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"` without `--ssh-key`, then inspect the VM. | Draft expectation: the VM is created without a registered-key reference. Confirm guest provisioning only if this keyless offering is supported. |

### TC-07 — Reject VM creation with an inaccessible, cross-tenant, or shared key

**Description:** Check three boundaries. First, a user must have access to
both the VM's project and the key's project. Second, a VM in Tenant B must
never select Tenant A's key, even when the tenants use the same key name.
Third, the PR #1828 contract rejects SSH keys in shared scope. Rejected VM
requests must not reveal the protected key or save a VM.

**Category:** Mixed
**Test tier:** Unit for `shared: true` reference validation; component integration for API authorization/persistence; deployed E2E only for CR/provider absence
**Priority:** Critical
**Automation:** PR #1828 (unmerged) covers denied-project lookup, rejects
shared-tenant SSH-key creation with no persistence, and has a unit test that
rejects `shared: true` on a VM key reference before Secret lookup. Add the
missing access-transition and tenant-isolation assertions.

**Prerequisite:** Tenant User can access Projects A and B; `$PROJECT_KEY`
exists in Project A as described in common setup. Tenant-B User has access to
`$TENANT_B_PROJECT` but is not a member of Tenant A. Authenticate separately
as each tenant's user and confirm the account and tenant with `osac whoami`
before issuing commands. Run the shared-scope checks only on a build with
PR #1828. Verify `$TENANT_B_CATALOG_ITEM` and `$TENANT_B_NETWORK_ATTACHMENT`
are usable in Tenant B before steps 3–6.

**Scope distinction:** A Secret does not have a `shared` boolean. To test
shared SSH-key creation, target the shared tenant (explicitly or through the
platform administrator's shared-tenant default). The `shared: true` field is
on the SSH-key reference in a ComputeInstance request.
In step 6, the bare-name selector looks in Tenant B's default project;
compare the VM reference with Tenant B's Secret ID, not just its name.

| Step | Action | Expected result |
|---|---|---|
| 1 | Tenant Admin keeps the user assigned to Project B, removes the user's Project A assignment through the membership API/fixture, and waits for convergence. User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-key-project-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`, then Tenant Admin queries that VM name. Restore Project A assignment and wait for convergence before the next step. | Creation fails because the user lacks access to the key's project, even though they can access the VM's project. The error does not disclose key details; the authorized query returns not found and no VM persists. |
| 2 | Tenant Admin removes the user's Project B assignment while retaining Project A access. User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-destination-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. After the request, Tenant Admin checks the VM name through the API, then restores Project B access and waits for convergence. | Destination-project authorization fails; the authorized API check returns not found. A deployed E2E check must separately confirm no ComputeInstance CR/provider operation; Project B access is restored. |
| 3 | Record `$DEFAULT_KEY_ID` from Tenant A's default-project Secret before switching accounts. In the authenticated Tenant-B User context, confirm `osac whoami` shows Tenant B. Through the public API, attempt to create `$VM_TENANT_B` in `$TENANT_B_PROJECT` with `spec.ssh_key={id: "$DEFAULT_KEY_ID", project: ""}`, `$TENANT_B_CATALOG_ITEM`, and `$TENANT_B_NETWORK_ATTACHMENT`. Query that VM name as an authorized Tenant-B actor. | Tenant B cannot resolve Tenant A's Secret ID even though the reference names the default project. Creation fails with a non-disclosing reference error; no VM persists and no Tenant-A Secret data is returned. |
| 4 | Authenticate as Tenant-A User; confirm Tenant A with `osac whoami`, run `osac project --clear`, and create `osac create secret --name "$TENANT_COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. Record the Secret ID. | A key with this name and A's public-key value exists in Tenant A's default project. |
| 5 | Authenticate as Tenant-B User; confirm Tenant B with `osac whoami`, run `osac project --clear`, and create `osac create secret --name "$TENANT_COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Record this Secret ID. | Tenant B can use the same name, but the ID and public-key value differ from Tenant A's key. |
| 6 | Run `osac --project "$TENANT_B_PROJECT" create computeinstance --name "osac51-tenant-collision-$RUN_ID" --catalog-item "$TENANT_B_CATALOG_ITEM" --ssh-key "$TENANT_COLLISION_KEY" --network-attachment "$TENANT_B_NETWORK_ATTACHMENT"`; inspect with `osac --project "$TENANT_B_PROJECT" get computeinstance "osac51-tenant-collision-$RUN_ID" -o yaml`. Restore Tenant-A authentication afterward. | The VM's canonical key reference contains Tenant B's Secret ID and default project, not Tenant A's ID. The authenticated context returns to Tenant A. |
| 7 | Through the administrative/API fixture, attempt to create `$SHARED_KEY` with type `SECRET_TYPE_SSH_PUBLIC_KEY`, valid `public_key` data, and `metadata.tenant=shared`. List by that unique name in the shared tenant afterward. The public CLI has no `shared` Secret-create flag. | On the PR #1828 build, creation returns `InvalidArgument` and the authorized follow-up list is empty; no Secret persists. Record the status and response. |
| 8 | In the unit reference-validation test, submit a VM request with `spec.ssh_key={name: "$DEFAULT_KEY", shared: true}` and verify rejection occurs before Secret lookup. If the public API accepts this request shape, repeat through the API and query the attempted VM name as an authorized Tenant Admin. | On the PR #1828 build, the request returns `InvalidArgument` with `SSH key reference must be tenant-scoped.` The VM is not persisted; a deployed E2E check can also confirm no CR/provider operation. |

### TC-08 — Reject new VM creation after access to the key project is revoked

**Description:** Create a VM in Project B using a key from Project A. Then
remove the creator's access to A while keeping access to B. Another VM request
using A's key must be denied. The first VM keeps the key it received at
creation and remains accessible with the matching private key.

**Category:** Mixed
**Test tier:** Component integration for API authorization/persistence; deployed E2E for guest authentication and CR/provider absence
**Priority:** High
**Automation:** PR #1828 covers denied lookup; add the source-project access-revocation transition and existing-VM assertion.

**Prerequisite:** `$PROJECT_KEY` exists in Project A as described in common
setup. Tenant User has access to Projects A and B. Tenant Admin can revoke
and restore that user's Project A assignment through the supported membership
fixture.

| Step | Action | Expected result |
|---|---|---|
| 1 | Tenant Admin confirms the user can access both A and B through the membership API/fixture and waits for convergence. | Both project assignments are effective. |
| 2 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED_INITIAL" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac --project "$PROJECT_B" get computeinstance "$VM_REVOKED_INITIAL" -o yaml`. In deployed E2E, wait for Running and prove that the shared strict SSH command succeeds before revoking access. | VM-1 persists in B with a canonical reference to A's key; in deployed E2E, it is Running and the matching private key authenticates before revocation. |
| 3 | Tenant Admin revokes only the user's Project A assignment through the supported membership API/fixture and waits for convergence. | The user still has destination-project access but no longer has access to the key's project. |
| 4 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`; then Tenant Admin queries `$VM_REVOKED`. | The new request is denied because the user cannot access A. The authorized query returns not found; a deployed E2E check separately confirms no CR/provider operation. |
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
missing, deleted, and wrong-type references. Run the basic invalid-key inputs.
After PR #1828 reaches the target build, add the two-key and trailing-content
inputs and assert the final project-aware error contract.

Run `osac project --clear` before this case so every Secret and VM below is
in the tenant's default project. Each table row is an independent attempt;
check that rejected create commands return a nonzero status.

Create synthetic invalid fixtures locally. Use private-key-like test text, not the generated private key or PEM contents, so the test never uploads private-key material.

On a build containing PR #1828, missing, deleted, hidden, and out-of-project
references should return gRPC `InvalidArgument` with the same generic message:
`SSH key Secret was not found or is not visible in the selected project.` On
the current build, record the actual error and require rejection with no VM;
do not apply the PR-only message assertion yet. Component integration can prove
that no API object persists; assert CR/provider absence only in deployed E2E.

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
INVALID_CASES=(malformed private-key-like empty)
# Add two-keys and trailing after a build containing PR #1828 is deployed:
# INVALID_CASES+=(two-keys trailing)
for INVALID_CASE in "${INVALID_CASES[@]}"; do
  case "$INVALID_CASE" in
    malformed) INVALID_FILE="$KEY_DIR/malformed.pub" ;;
    private-key-like) INVALID_FILE="$KEY_DIR/private-key-like.txt" ;;
    empty) INVALID_FILE="$KEY_DIR/empty.pub" ;;
    two-keys) INVALID_FILE="$KEY_DIR/two-keys.pub" ;;
    trailing) INVALID_FILE="$KEY_DIR/trailing.pub" ;;
  esac
  SECRET_NAME="osac51-invalid-$RUN_ID-$INVALID_CASE"
  if osac create secret --name "$SECRET_NAME" --type ssh-public-key \
    --from-file "public_key=$INVALID_FILE"; then
    osac delete secret "$SECRET_NAME"
    printf 'Unexpectedly accepted invalid key: %s\n' "$INVALID_CASE" >&2
    exit 1
  fi
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
| Two-key and trailing-content fixtures. | Add them to `INVALID_CASES` after PR #1828 is deployed. Until then, record any result as exploratory. On the target build, both creates are rejected with no Secret persisted. |
| Wrong field: run `osac create secret --name "osac51-wrong-field-$RUN_ID" --type ssh-public-key --from-file "key=$KEY_DIR/id_ed25519.pub"`, then `osac get secrets "osac51-wrong-field-$RUN_ID" -o yaml`. | Rejected because required public_key data is absent; the lookup returns `[]` and no Secret persists. |
| Missing reference: run `osac project --clear`, then `osac create computeinstance --name "osac51-missing-ref-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-missing-$RUN_ID" --network-attachment "$NETWORK_ATTACHMENT"`; run `osac get computeinstance "osac51-missing-ref-$RUN_ID" -o yaml`. | Creation is rejected; the VM lookup returns `[]`. On the PR build, assert the generic missing-reference error. Use deployed E2E to assert no CR/provider operation. |
| Deleted reference: run `osac create secret --name "osac51-deleted-ref-key-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then `osac delete secret "osac51-deleted-ref-key-$RUN_ID"` and `osac get secrets "osac51-deleted-ref-key-$RUN_ID" -o yaml`. Run `osac create computeinstance --name "osac51-deleted-ref-vm-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-deleted-ref-key-$RUN_ID" --network-attachment "$NETWORK_ATTACHMENT"`, then `osac get computeinstance "osac51-deleted-ref-vm-$RUN_ID" -o yaml`. | Creation is rejected; the Secret and VM lookups return `[]`. On the PR build, assert the generic missing-reference error. |
| Wrong type: run `osac create secret --name "osac51-opaque-$RUN_ID" --type opaque --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then `osac create computeinstance --name "osac51-wrong-type-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-opaque-$RUN_ID" --network-attachment "$NETWORK_ATTACHMENT"`; run `osac get computeinstance "osac51-wrong-type-$RUN_ID" -o yaml`. | The reference is rejected for wrong type and the VM lookup returns `[]`. Use an API fixture for missing data or lifecycle states not constructible through the CLI. |

### TC-10 — Reject malformed selectors and VM key changes, then check in-use deletion

**Description:** Try badly formatted `--ssh-key` values and attempts to change
the key already selected for a VM. Also check whether a key still used by a VM
can be deleted, according to the final policy.

**Category:** Negative with positive cleanup
**Test tier:** Unit and component integration for API behavior; deployed E2E if checking provider side effects
**Priority:** Critical
**Automation:** Selection and immutability are partially covered; add the in-use deletion boundary if policy requires it.
**Decision needed:** Run step 4 as a release check only after the expected
behavior for deleting an in-use SSH-key Secret is recorded. Selector parsing
and VM reference immutability already have defined expected results.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create an independent test Secret and VM using `osac --project "$PROJECT_A" create secret --name "$IMMUTABLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"` and `osac --project "$PROJECT_A" create computeinstance --name "$VM_IMMUTABLE" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$IMMUTABLE_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. | The VM persists with a canonical reference to `$IMMUTABLE_KEY`. |
| 2 | For each malformed selector in the matrix below, run the CLI command and query the unique VM name afterward. | Every malformed selector fails and no API ComputeInstance persists. Use deployed E2E, not component integration, to assert no CR/provider operation. |
| 3 | Use an authenticated API test client to call `ComputeInstances.Update` for `$VM_IMMUTABLE`, first replacing `spec.ssh_key` with `$DEFAULT_KEY`, then clearing it, each with `update_mask: ["spec.ssh_key"]`. After each attempt, get the VM through the same API and record the request/response. The public CLI has no update command for this field. | Both updates are rejected; each follow-up get still contains `$IMMUTABLE_KEY`'s original canonical ID/name/project. |
| 4 | After the deletion policy is decided, run `osac --project "$PROJECT_A" delete secret "$IMMUTABLE_KEY"` while `$VM_IMMUTABLE` references it. Inspect the Secret and VM afterward. | If in-use protection is required, deletion fails and both resources remain unchanged. If deletion is allowed, record that result and update this expectation before making the check release-blocking. |
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
    --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$SELECTOR"; then
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
**Automation:** Windows rejection and Linux projection are covered; the
incompatible non-cloud-init row needs a deterministic CatalogItem fixture.

Run `osac project --clear` before each row so all four VMs use the default
project. The Linux fixtures must not contain the freshly generated test key
except when OSAC injects it through `--ssh-key`.

| Guest scenario | CLI command | Expected result |
|---|---|---|
| Linux cloud-init with a registered key. | `osac create computeinstance --name "osac51-linux-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`; inspect with `osac get computeinstance "osac51-linux-key-$RUN_ID" -o yaml`. | VM reaches Running with the selected key reference. TC-12 independently tests guest login. |
| Linux cloud-init without a key. | `osac create computeinstance --name "osac51-linux-no-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac get computeinstance "osac51-linux-no-key-$RUN_ID" -o yaml`. | VM reaches Running with no `spec.ssh_key` reference. If trusted guest inspection is available, the generated test public key is absent from the guest's authorized keys. |
| Windows template with a key. | Run `osac create computeinstance --name "osac51-windows-key-$RUN_ID" --catalog-item "$WINDOWS_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`, then `osac get computeinstance "osac51-windows-key-$RUN_ID" -o yaml`. | Create is rejected and the filtered get returns `[]`. In deployed E2E, confirm no ComputeInstance CR or provider operation began. |
| Incompatible non-cloud-init Linux template with a key. | After a deterministic fixture exists, run `osac create computeinstance --name "osac51-ignition-key-$RUN_ID" --catalog-item "$IGNITION_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`, then inspect with `osac get computeinstance "osac51-ignition-key-$RUN_ID" -o yaml`. | The OSAC-51 design excludes injection into incompatible first-boot formats: create is rejected and the filtered get returns `[]`. Confirm CR/provider absence in deployed E2E; do not mark this row executed until the fixture is available. |

This is a negative compatibility test for registered-key injection. It does not assert that a keyless Windows VM cannot be created.

### TC-12 — Log in with the matching private key and reject an unrelated key

**Description:** Create a Linux VM with a saved key and give it an address
reachable from the test client. Log in with the matching private key, then
confirm that an unrelated private key cannot log in.

**Category:** Positive E2E plus negative authentication
**Test tier:** Manual deployed E2E
**Priority:** Critical
**Automation:** Current E2E verifies resource projection, not actual login

**Preconditions:** `$DEFAULT_KEY` and a Ready Subnet and SecurityGroup exist
from common setup. The test tenant has a Ready ExternalIPPool with capacity,
and the allocated address is routable from the test client. Record the
SecurityGroup's approved egress rules. If routing is unavailable, mark this
case Inconclusive.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear` and inspect `osac get externalippool "$EXTERNAL_IP_POOL" -o yaml`; stop before creating a VM if the pool is not Ready or has no capacity. Then run `osac create computeinstance --name "$VM_SSH_E2E" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`; wait for Running and inspect with `osac get computeinstance "$VM_SSH_E2E" -o yaml`. | The pool is usable. The VM is Running in the default project with `$DEFAULT_KEY`'s reference and the prepared network attachment. |
| 2 | Run `osac create externalip --name "$EXTERNAL_IP_NAME" --pool "$EXTERNAL_IP_POOL"`; wait until Allocated. Run `osac create externalipattachment --name "$EXTERNAL_IP_ATTACHMENT" --externalip "$EXTERNAL_IP_NAME" --compute-instance "$VM_SSH_E2E"`. Poll `osac get externalip "$EXTERNAL_IP_NAME" -o yaml` and `osac get externalipattachment "$EXTERNAL_IP_ATTACHMENT" -o yaml` until Allocated/Ready; copy the nonempty `status.address` into `EXTERNAL_IP_ADDRESS`. | The ExternalIP is Allocated, the attachment is Ready, and the test client can route to the address on TCP/22. If routing fails, record Inconclusive. |
| 3 | Populate `$KNOWN_HOSTS` from a trusted host-key source, set `VM_ADDRESS="$EXTERNAL_IP_ADDRESS"`, and run the common strict SSH command from the setup section. | Exit 0; stdout is OSAC_SSH_OK; no password prompt. |
| 4 | Repeat the strict SSH command with `-i "$KEY_DIR/id_ed25519_b"` instead of the matching private key; keep the same target and host-key settings. | Authentication fails with a nonzero exit. A timeout or host-key error is Inconclusive, not evidence that the wrong key was rejected. |
| 5 | If either login result is unexpected, collect the serial console, cloud-init, and sshd evidence available for this VM before cleanup. | Evidence distinguishes key injection, VM readiness, and network failures. |
| 6 | Delete the created ExternalIPAttachment and wait for detach, then delete the ExternalIP and `$VM_SSH_E2E`; poll each to absence. Run the corresponding `osac delete externalipattachment "$EXTERNAL_IP_ATTACHMENT"`, `osac delete externalip "$EXTERNAL_IP_NAME"`, and `osac delete computeinstance "$VM_SSH_E2E"` commands only for resources that were created. Delete `$DEFAULT_KEY` in final cleanup after every VM using it is removed. | The attachment is removed before the VM, as required for a manual attachment. All resources created by this case disappear; the shared key remains for other cases. |

### TC-13 — Check how key updates affect existing and future VMs (decision needed)

**Description:** Once OSAC defines whether saved keys may be changed, try an
update before and after a VM uses the key. Check the expected rejection or,
if updates are allowed, their effect on new VMs without changing an existing VM.

**Category:** Deferred
**Test tier:** Component integration and deployed E2E after the decision
**Priority:** Deferred until the update rule is agreed
**Automation:** Not scheduled
**Decision needed:** Whether `data.public_key` on a registered Secret can be
updated, including while a VM refers to that Secret.
**Prerequisite:** An authenticated public API client can call `Secrets.Update`.
The Linux CatalogItem and network attachment from common setup are Ready;
guest-login steps also need a reachable VM address and trusted host key as in
TC-12.

Keep this case disabled until the expected update behavior is agreed. Use the
two distinct key pairs from common setup; only their `.pub` files are sent to
OSAC. For each update, use an authenticated public `Secrets.Update` request
with the existing Secret ID, the replacement `data.public_key` bytes from
`$KEY_DIR/id_ed25519_b.pub`, and `update_mask.paths: ["data"]`. Preserve the
Secret's other fields and record the request, status, and response. Inspect
the Secret after each attempt because an update response may redact its data.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`. Create an unused key with `osac create secret --name "osac51-update-unused-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`; repeat with the name `osac51-update-in-use-$RUN_ID`. Inspect both and record their IDs and public-key data. | Both Secrets contain the original public key and have different IDs. Neither is used by a VM yet. |
| 2 | Try to replace the unused Secret's `data.public_key` with the second public key through `Secrets.Update`, then get the Secret again. | If updates are allowed, the ID stays the same and the stored bytes match `id_ed25519_b.pub`. If updates are forbidden, the request fails and the original data remains unchanged. Apply the agreed policy before marking this step pass or fail. |
| 3 | Run `osac create computeinstance --name "osac51-update-original-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "osac51-update-in-use-$RUN_ID"`. Inspect its saved reference; once Running and reachable, log in with `$KEY_DIR/id_ed25519` using the strict SSH procedure in common setup. | The reference identifies the in-use Secret and the original private key authenticates. Record the VM address and login result before attempting the update. |
| 4 | Try to replace the in-use Secret's `data.public_key` with the second public key through `Secrets.Update`, then get the Secret and retry SSH to the existing VM with both private keys. | If the update is forbidden, the Secret retains the original key. If allowed, it stores the second key. In either case, the existing VM keeps its initially injected key: the original private key works and the second private key fails. Apply the agreed update policy before marking the API result pass or fail. |
| 5 | Run `osac create computeinstance --name "osac51-update-future-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "osac51-update-in-use-$RUN_ID"`. Once Running and reachable, try both private keys with strict SSH verification. | If step 4 updated the Secret, the second private key works and the original fails. If step 4 was rejected, the original works and the second fails. This checks which key a new VM receives. |
| 6 | Delete both VMs with `osac delete computeinstance` and wait until absent; then delete `osac51-update-unused-$RUN_ID` and `osac51-update-in-use-$RUN_ID` with `osac delete secret` and confirm both are absent. | No resources created by this case remain. |

OSAC-51 excludes changing a key already injected into a running VM.

## Nonfunctional checks

### NFR-SSH-01 — Private-key handling and output hygiene

**Description:** Check that only the public key is sent to OSAC. Command
output, API responses, and service logs must never show the matching private
key or another tenant's key data.

**Test tier:** Unit or component integration; manual confirmation
**Priority:** High
**Automation:** `fulfillment-service/internal/logging/logging_interceptor_test.go` on `main` verifies SSH public-key Secret data is redacted from body logs while the source request remains unchanged. CLI/API output hygiene and all relevant log paths still need confirmation.

| Step | Action | Expected result |
|---|---|---|
| 1 | In TC-01, pass only `$KEY_DIR/id_ed25519.pub` to `--from-file`. Inspect the create/get output and the Secret request/response log path covered by the logging unit test. | The private-key file is never supplied to OSAC. API and normal logs do not contain private-key material; Secret body logs redact `data.public_key`. |
| 2 | Trigger TC-09's invalid-key and missing-reference requests, then inspect their CLI errors and normal service logs. | Errors identify invalid input or an unavailable reference without printing key data or details of an inaccessible Secret. |
| 3 | As Tenant-B User in TC-07, try to get Tenant A's key by its known Secret ID through the supported public API. | Tenant B receives no key data; use NFR-SSH-02 to compare the error disclosure and confirm no VM is created. |

### NFR-SSH-02 — Non-disclosing authorization failures

**Description:** Compare the error shown for a key that does not exist with
errors for keys the user is not allowed to use. The responses must not let the
user discover that a hidden key exists, and no VM should be created.

**Test tier:** Unit and component integration
**Priority:** High

**Automation:** PR #1828 adds unit and component-integration assertions for missing, hidden, out-of-project, and project-inaccessible references. Cross-tenant equivalence and output/log hygiene remain gaps.

Use the same authenticated caller and VM destination for each comparison so
only the selected key changes. Record the gRPC status and public message;
do not compare internal logs that may legitimately carry a diagnostic reason.

| Step | Action | Expected result |
|---|---|---|
| 1 | Use TC-09's missing-key request as the baseline. Record the public error and query the attempted VM name. | The request fails and no VM persists. |
| 2 | With the same caller, select an existing key in a project the caller cannot access, as in TC-07 step 1; query the attempted VM name. | The public error class/message matches step 1, reveals no Secret metadata, and no VM persists. |
| 3 | Repeat with Tenant A's Secret ID from TC-07 step 3 while authenticated as Tenant-B User. Compare it with an unknown Secret ID using the same caller and VM destination. | Both public errors are non-disclosing and no VM persists. Check CR/provider absence only in deployed E2E. |

## Regression coverage

Add regression cases to
`tests/e2e/vmaas/regression/test_compute_instance_registered_ssh_key.py` and
mark them with `pytest.mark.regression`. Run from the OSAC repository root:

~~~bash
uv run pytest -m regression tests/e2e/vmaas/regression/test_compute_instance_registered_ssh_key.py
~~~

This planned E2E test requires the configured VMaaS environment, credentials, and VM fixtures. Guest-authentication coverage also requires a client routed to the test VM on TCP/22. The existing registered-key E2E remains a `sanity` smoke check. This documentation change adds no test code.

| Regression target | Test case mapping | Test tier | Current status and expected assertion |
|---|---|---|---|
| A normal VM without a registered key continues to create and run. | TC-11 | Deployed E2E regression | Planned regression case. Assert the VM reaches Running and has no registered-key reference or injected registered key. |
| A VM created with a registered key still receives the exact selected public key. | TC-02–05 | Deployed E2E | TC-02 is covered by the existing sanity test at the ComputeInstance resource boundary. Add default-to-named, same-project, named-to-named, named-to-default, and same-name project selection to regression coverage. |
| Invalid, missing, or out-of-scope keys do not persist a VM. | TC-07; TC-09; NFR-SSH-02 | Unit/component-integration for no persistence; deployed E2E for CR/provider absence | Existing unit anchors cover parts of this contract; extend authorization and no-persistence assertions. Provider-side absence remains a separate deployed E2E gap. |
| In-use key deletion and immutable key references retain the agreed behavior. | TC-10; UT-SSH-05 | Unit and component integration regression | `main` tests reference immutability and has a generic Secret in-use guard for another resource; it has no SSH-key/ComputeInstance deletion-boundary assertion. |
| The selected key authenticates, and an unrelated private key is rejected. | TC-12 | Manual deployed E2E | Manual regression until the runner can route to tenant VM addresses; strict host-key verification is required. |

These targets map functional cases to regression automation; they are not additional scenarios.

## Gaps and planning decisions

| Gap / decision | Current evidence | Follow-up |
|---|---|---|
| Direct cross-project key selection | The 2026-10-22 decision permits a VM creator with access to both projects to select a key across projects, including the default project in either role. PR #1828 is unmerged. | Apply the agreed rule in TC-03/05/07 and verify it at the component-integration and deployed E2E boundaries. |
| Key-name requirement wording | The confirmed rule allows the same name in different projects of one tenant, while the current PRD says names are unique within a tenant. | Align the PRD wording with per-tenant, per-project uniqueness; execute TC-05's same-name creation and project-qualified VM checks. |
| CatalogItem support | OSAC-51 design excludes CatalogItem defaults; current task/PR includes related policy behavior. The cross-project meeting scheduled a separate CatalogItem discussion. | Confirm release scope; keep TC-06 deferred until its expected behavior is recorded. |
| Project membership/revocation | New VM creation requires access to both projects. After key-project access is revoked, the previously created VM retains its injected key and remains accessible. PR #1828 tests denied lookup, but not this transition. | Add TC-08 transition assertions at component integration and deployed E2E tiers. |
| Shared-tenant rules | PR #1828 rejects SSH-key Secret creation in the shared tenant and has a unit test rejecting `shared: true` on a ComputeInstance SSH-key reference before Secret lookup. Both checks are PR-only until that build is deployed. | Verify the reviewed PR behavior after deployment; keep Secret creation and shared-reference checks distinct in TC-07. |
| In-use SSH-key deletion | `main` has a generic Secret deletion guard for a different resource; there is no SSH-key/ComputeInstance deletion assertion in `main` or PR #1828. | Decide whether a referenced key Secret must be protected from deletion. If yes, add the SSH-key-specific unit and component-integration assertions; otherwise change TC-10 step 4. |
| Guest compatibility | Windows validation exists; no deterministic incompatible non-cloud-init fixture is identified. The OSAC-51 design rejects unsupported first-boot formats. | Prepare that fixture, then verify rejection before provisioning in TC-11. |
| Real SSH in CI | Existing E2E checks resource projection; runner cannot route to guest subnet. | Run manual TC-12; track routed automation under [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526) if required. |
| Key-data update behavior | The design says Secrets use the generic update lifecycle, but the rule for changing an unused or in-use registered key is not explicit. | Record the expected update rule before running TC-13 as a pass/fail check. |
| Integration execution | PR #1828 reports integration package compile only because host mappings were unavailable. | Run component integration suite in a suitable environment before marking it executed. |

## Exit criteria

- The planned cases trace to agreed requirements and the cross-project access decision; TC-06, TC-10 step 4, and TC-13 receive explicit expected results before becoming release-blocking.
- Each successful VM reference resolves to the expected key; for SSH acceptance cases, the matching private key authenticates.
- Negative cases use the agreed error class, disclose no cross-scope key metadata, and persist no unintended VM. Where required, deployed E2E also confirms no ComputeInstance CR or provider operation.
- The wrong private key fails authentication; tests use strict host-key verification.
- In-use deletion, CatalogItem behavior, and updates match the final recorded policy.
- Cleanup leaves no test resources.
- Coverage spans unit, component integration, and deployed cross-component journeys without duplication or gaps.
- Mark a case Executed only after recording target build SHA, environment, command, outcome, and evidence. This document and PR-reported unit results alone do not mean manual/deployed cases have run.

## Summary

| Metric | Count |
|---|---:|
| Total scenario cases | 15 (13 functional, 2 nonfunctional) |
| Priority | 5 critical, 9 high; TC-13 deferred pending the policy decision |
| VMaaS PRD requirement areas mapped | 5 / 5; ComputeInstance behavior only |
| Planned unit coverage slices | 6 |
| Planned component-integration coverage slices | 7 |
| Existing SSH-key-specific component-integration files on `main` | 3 (Secret lifecycle, ComputeInstance CatalogItem behavior, and CatalogItem CLI display); generic Secret authorization is separate |
| Existing deployed VMaaS SSH-key sanity scenarios on `main` | 1 (CR key projection; no guest login) |
| Local cleanup-helper tests in the sanity file | 2 (no VM deployment) |
| Existing registered-key VMaaS regression-marked cases on `main` | 0 |
| Regression targets mapped (not additional cases) | 5 |
| Dedicated manual real-SSH E2E case | 1 (TC-12; TC-03–05 also require guest SSH) |
| Checks needing a decision (listed in Overview) | 3: TC-06, TC-10 step 4, TC-13 |
| Fixture-dependent compatibility check | 1: TC-11 non-cloud-init row |
| Executable test code added by this plan PR | 0 |

**Execution status:** Record manual results and evidence separately; this plan
does not mark a case passed merely because its steps are documented.
