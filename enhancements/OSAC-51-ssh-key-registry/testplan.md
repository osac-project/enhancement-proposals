# Test Plan — OSAC-51 Public SSH Key Registry

**Status:** Working draft for planning
**Updated:** 2026-10-22
**Scope:** VMaaS registered SSH-key behavior in the initial OSAC-51 feature context and current VM implementation work. The plan is not final across the other SSH-key epics.

## Overview

**Feature:** [OSAC-51 — Public SSH Key Registry](prd.md) (VMaaS scope)

**Total test cases:** 15 (13 functional, 2 nonfunctional)

**VMaaS requirement areas mapped:** 5 of 5 (ComputeInstance behavior only; this is a coverage map, not execution evidence).

**Interface areas covered:** 4 — Secret registration/lifecycle API and CLI; ComputeInstance key selection API and CLI; provisioning handoff; guest SSH authentication.

- **Supporting unit coverage:** 6 cases mapped to functional scenarios; not counted again above.
- **Policy flags:** 4 POLICY-SENSITIVE cases; 2 POLICY-PENDING behaviors.
- **Regression status:** `main` has one deployed registered-key sanity scenario but no registered-key VMaaS regression-marked case; five regression targets are planned.
- **Implementation status:** This change documents coverage; it adds no unit, integration, or E2E test code.
- **Execution status:** Existing and in-flight unit/integration anchors are identified; PR-reported unit results are noted below. The full integration suite was not run, and guest SSH checks in TC-02–05 and TC-12 remain manual.

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
| Deployed E2E | One VMaaS sanity case creates a VM and checks key projection into the ComputeInstance CR; it does not verify guest SSH login. | No deployed VMaaS E2E coverage is added by PR #1828. | Add regression-marked VMaaS cases. Guest login in TC-02–05 and TC-12 remains manual until the runner can route to the VM (see OSAC-6526). |

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

### Behavior flags

- **POLICY-SENSITIVE:** expected behavior is provisional; confirm it before making the case release-blocking.
- **POLICY-PENDING:** behavior is undecided; keep the case non-blocking until planning records a decision.

Update flagged outcomes and link the decision to its requirement or issue.

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
another VM with it. CatalogItem and shared-tenant behavior retain their
separate flags.

Use an IPv4 ExternalIP address reachable from the test client. Networking is a
prerequisite, not a behavior under test. This follows the current
[VMaaS networking contract](../OSAC-1435-vmaas-networking/design.md), where
ExternalIP replaces the legacy PublicIP name and is not necessarily
internet-routable.

## Detailed existing coverage and test infrastructure

This snapshot was checked against upstream [`main` at `a6d3626`](https://github.com/osac-project/osac/commit/a6d3626e5a50b503862f4a16faef44e68d13dbd6) on 2026-10-22. [PR #1828](https://github.com/osac-project/osac/pull/1828) is still open and has not merged; its tests are labeled **PR #1828**, not current coverage. All paths are relative to the OSAC repository root. Detailed behavior is specified once in the cases below.

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
| IT-SSH-01 / TC-01 — Secret lifecycle | `fulfillment-service/it/it_cli_ssh_key_lifecycle_test.go` creates, gets, and deletes a key through the CLI; it checks the name/ID and that get reports no object after deletion. | Happy-path lifecycle is covered. Duplicate-name rejection, delete-in-progress behavior/name reuse, and response/log hygiene are not asserted by this case. |
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

## Unit test cases

These cases check individual parts of Fulfillment without launching a real VM.
The coverage inventory above shows which checks already exist, which are in PR
#1828, and which still need to be added. The integration and end-to-end cases
below check behavior across deployed services and inside a VM.

### UT-SSH-01 — Public-key payload validation

**Description:** Check that OSAC accepts a saved SSH key only when it contains
one valid public key. Bad text, a private key, extra keys, or missing data must
be rejected.

**Automation:** Partial; add the unasserted malformed, trailing-content,
and private-key-like inputs. See the unit coverage inventory for test paths.

| Input | Expected result |
|---|---|
| Valid Ed25519 OpenSSH public key. | Accepted by the SSH-key validator. |
| Malformed/empty payload, private-key PEM, second key, or trailing content. | Rejected. |
| Secret with wrong type or missing public_key field. | Rejected with a typed validation error. |

### UT-SSH-02 — CLI selector grammar

**Description:** Check what users can type after `--ssh-key` when creating a VM.
Supported ways to name a key should work; incomplete or misspelled forms
should fail before a VM is created.

**Automation:** Bare-name selection is on `main`; structured grammar is in
unmerged PR #1828.

Accept the supported bare-name form and structured name/project form. Reject empty or missing name, duplicate name/project fields, unknown fields, empty fragments, missing equals sign, and commas in an unstructured bare name.

### UT-SSH-03 — Reference resolution and error disclosure

**Description:** Check that a VM request finds the exact saved key the user
selected, including a key in another project when the creator can access both
projects. If the user cannot access either project, the request must fail
without revealing whether the key exists.

**Automation:** Tenant lookup is on `main`; project-aware lookup, defaulting,
and non-disclosure are in unmerged PR #1828. Add missing source/destination
access and default-project assertions where that PR does not cover them.

Verify canonical ID/name/project after name or ID lookup; access to both the VM
destination and selected key project, including the default project in either
role; deterministic lookup when different projects in one tenant contain the
same key name; generic externally observable errors for missing, hidden, or
out-of-scope keys; shared-reference rejection if retained; and compatibility
behavior for previously stored ID/name-only references if still supported.

### UT-SSH-04 — CatalogItem SSH-key policy

**Description:** Check what happens when a VM offering supplies a default SSH
key or prevents users from changing that choice. The VM should use the allowed
key, and a rejected choice must not create a VM.

**Automation:** A dedicated unit policy test is in unmerged PR #1828;
default, override, lock, and no-key assertions depend on planning.

For each supported policy, assert whether the input is accepted, the resulting reference is canonical, locked values cannot be changed, and rejected requests do not create a ComputeInstance.

### UT-SSH-05 — Immutable references and deletion guard

**Description:** Check that users cannot change or clear the key saved on an
existing VM. If the final policy protects keys used by VMs, deleting such a
key must also fail until the VM is removed.

**Automation:** Immutability is on `main`; add an SSH-key in-use deletion
assertion only if the final contract requires it.

Verify that a stored SSH reference cannot be changed/cleared through supported mutation paths. Verify deletion of an in-use Secret is rejected without changing the Secret or referenced VM, and deletion succeeds after the reference is removed, if this guard remains in the final contract.

### UT-SSH-06 — Controller handoff and retry classification

**Description:** Check that OSAC passes the selected public key to the part of
the system that prepares VM login. A missing or invalid key should stop
further attempts; a temporary service problem should be tried again.

**Automation:** Handoff and retry classification are on `main`; PR #1828
updates the reference shape.

Verify that the resolved public key reaches the existing guest access handoff. Invalid/not-found references are permanent failures; transient unavailable, deadline, and cancellation errors remain retryable according to controller policy.

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

Use a disposable test tenant and unique resource names. Keep private keys only on the test client.

~~~bash
RUN_ID="$(date +%s)"
TEST_TMPDIR="${TMPDIR:-/tmp}"
TEST_TMPDIR="$(cd -- "$TEST_TMPDIR" && pwd -P)"
readonly TEST_TMPDIR
KEY_DIR="$(mktemp -d "$TEST_TMPDIR/osac51-ssh-key-test.XXXXXX")"
readonly KEY_DIR
ssh-keygen -t ed25519 -f "$KEY_DIR/id_ed25519" -N '' -C osac-51-test

TENANT_A='replace-with-test-tenant'
TENANT_B='replace-with-second-test-tenant'
PROJECT_A='replace-with-project-a'
PROJECT_B='replace-with-project-b'
TENANT_B_PROJECT='replace-with-tenant-b-project'
CATALOG_ITEM='replace-with-linux-cloud-init-catalog-item'
EDITABLE_KEY_CATALOG_ITEM='replace-with-editable-key-default-catalog-item'
LOCKED_KEY_CATALOG_ITEM='replace-with-locked-key-default-catalog-item'
NO_KEY_CATALOG_ITEM='replace-with-no-key-default-catalog-item'
WINDOWS_CATALOG_ITEM='replace-with-windows-catalog-item'
IGNITION_CATALOG_ITEM='replace-with-ignition-catalog-item'
NETWORK_ATTACHMENT='subnet=replace-with-subnet-id,security-groups=replace-with-ssh-security-group-id'
VM_USER='replace-with-image-login-user'
SSH_E2E_VIRTUAL_NETWORK='replace-with-test-virtual-network'
SSH_E2E_SUBNET='replace-with-test-subnet'
SSH_TEST_CLIENT_CIDR='replace-with-test-client-egress-ip/32'
SSH_TEST_SECURITY_GROUP="osac51-ssh-sg-$RUN_ID"
SSH_TEST_EGRESS_RULE='replace-with-minimal-approved-egress-rule'
SSH_E2E_NETWORK_ATTACHMENT="subnet=$SSH_E2E_SUBNET,security-groups=$SSH_TEST_SECURITY_GROUP"
EXTERNAL_IP_POOL='replace-with-external-ip-pool'
DEFAULT_KEY="osac51-default-$RUN_ID"
LIFECYCLE_KEY="osac51-lifecycle-$RUN_ID"
PROJECT_KEY="osac51-project-a-$RUN_ID"
PROJECT_B_KEY="osac51-project-b-$RUN_ID"
IMMUTABLE_KEY="osac51-immutable-$RUN_ID"
COLLISION_KEY="osac51-collision-$RUN_ID"
TENANT_COLLISION_KEY="osac51-tenant-collision-$RUN_ID"
VM_DD="osac51-dd-$RUN_ID"
VM_DD_STRUCTURED="osac51-dd-structured-$RUN_ID"
VM_DA="osac51-da-$RUN_ID"
VM_AA="osac51-aa-$RUN_ID"
VM_AB="osac51-ab-$RUN_ID"
VM_AD="osac51-ad-$RUN_ID"
VM_COLLISION="osac51-collision-vm-$RUN_ID"
VM_TENANT_B="osac51-tenant-b-$RUN_ID"
VM_REVOKED="osac51-revoked-$RUN_ID"
VM_REVOKED_INITIAL="osac51-revoked-initial-$RUN_ID"
VM_IMMUTABLE="osac51-immutable-$RUN_ID"
VM_SSH_E2E="osac51-ssh-e2e-$RUN_ID"
EXTERNAL_IP_NAME="osac51-ip-$RUN_ID"
EXTERNAL_IP_ATTACHMENT="osac51-ip-attachment-$RUN_ID"
KNOWN_HOSTS="$KEY_DIR/known_hosts"
readonly KNOWN_HOSTS
ssh-keygen -t ed25519 -f "$KEY_DIR/id_ed25519_b" -N '' -C osac-51-test-b
~~~

After deleting all test ComputeInstances and Secrets, remove only the temporary directory created for this run. Do not reuse or override `KEY_DIR`.

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
      "$KEY_DIR/known_hosts"
    rmdir -- "$KEY_DIR"
    ;;
  *)
    printf 'Refusing to remove unexpected key directory: %s\n' "$KEY_DIR" >&2
    exit 1
    ;;
esac
~~~

Select the tenant, clear any saved project, and verify that Projects A and B exist:

~~~bash
osac tenant "$TENANT_A"
osac project --clear
osac get projects
~~~

Create a default-project key for the selection and guest tests. Keep it until common cleanup; TC-01 uses a separate Secret so its deletion/recreation checks do not affect other cases.

~~~bash
osac create secret --name "$DEFAULT_KEY" --type ssh-public-key \
  --from-file "public_key=$KEY_DIR/id_ed25519.pub"
~~~

For every status or deletion poll below, check at most once every 10 seconds.
Stop after 30 minutes for VM readiness and 10 minutes for other resources;
record the last observed status when a deadline expires. Treat a missed
readiness deadline as inconclusive until the VM or network cause is known.

Create Secrets inside each functional test through the CLI where the target build supports it. The project-scoped Secret command below is a setup check: verify the returned Secret has `metadata.project: PROJECT_A`. If it does not, create that fixture with the supported administrative/service API and record the request and response. Keep ComputeInstance creation and key selection on the public CLI.

Before a positive SSH assertion:

1. Wait for the ComputeInstance/VM to reach Ready.
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

### TC-01 — SSH-key Secret lifecycle

**Description:** Follow one saved public key from registration through listing,
inspection, deletion, and reuse of its name. Trying to register the same name
twice must not create a second record or change the first one.

**Category:** Mixed
**Test tier:** Component integration; unit validation supports invalid-input assertions
**Priority:** High
**Automation:** CLI lifecycle integration anchor exists; extend missing assertions
**Flag:** POLICY-SENSITIVE — name reuse while deletion is in progress

**Prerequisite:** Tenant User is authorized for the selected project.

| Step | Action | Expected result |
|---|---|---|
| 1 | Use the Ed25519 key pair generated in common setup. | Both files exist; private key remains local. |
| 2 | Run `osac create secret --name "$LIFECYCLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. | Exactly one Secret persists with the SSH public-key type and public_key data. |
| 3 | Run `osac get secrets` and `osac get secret "$LIFECYCLE_KEY" -o yaml`. | It appears once with expected metadata/type; private key material is never returned or logged. |
| 4 | Repeat `osac create secret --name "$LIFECYCLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. | Non-zero exit; original ID/data remain unchanged and no duplicate persists. |
| 5 | Run `osac delete secret "$LIFECYCLE_KEY"` and poll with `osac get secret "$LIFECYCLE_KEY" -o yaml` until the Secret is absent or marked deleting. | Delete succeeds; record whether an intermediate deleting state is observable. |
| 6 | While deletion is pending, repeat step 2's create command for `$LIFECYCLE_KEY`; after `osac get secret "$LIFECYCLE_KEY" -o yaml` returns not found, run `osac create secret --name "$LIFECYCLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`. | No duplicate is created during deletion. After deletion completes, assert the name-reuse behavior approved in planning. |

### TC-02 — Default key, default-project VM

**Description:** Create two VMs in the default project, naming the same saved
key in two supported command formats. Both VMs should point to that key and
allow login with its matching private key.

**Category:** Positive
**Test tier:** Deployed E2E; service resolution is covered by component integration
**Priority:** Critical for guest authentication
**Automation:** CR projection is on `main`; add guest login when routing permits.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac project --clear`, then create two VMs with `osac create computeinstance --name "$VM_DD" --catalog-item "$CATALOG_ITEM" --ssh-key "$DEFAULT_KEY" --network-attachment "$NETWORK_ATTACHMENT"` and `osac create computeinstance --name "$VM_DD_STRUCTURED" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$DEFAULT_KEY" --network-attachment "$NETWORK_ATTACHMENT"`. | Both VMs are created in the default project. |
| 2 | Wait for both VMs to reach Ready; inspect them with `osac get computeinstance "$VM_DD" -o yaml` and `osac get computeinstance "$VM_DD_STRUCTURED" -o yaml`; run the SSH command above against each. | Both references resolve to the same Secret ID/name and empty project; the matching private key authenticates to both VMs. A CR reference alone is not a pass. |

### TC-03 — Default key, named-project VM

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
| 3 | Run `osac --project "$PROJECT_A" get computeinstance "$VM_DA" -o yaml` and run the shared SSH verification command. | The reference has the default-project key's ID/name and an empty project; the matching private key authenticates. |

### TC-04 — Named key, VM in the same project

**Description:** Save a key in Project A and create a VM in that same project
using it. The VM should point to Project A's key and allow login with the
matching private key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Project selection is in PR #1828; add named-project E2E.

**Prerequisite:** Tenant User has access to Project A.

| Step | Action | Expected result |
|---|---|---|
| 1 | Try `osac --project "$PROJECT_A" create secret --name "$PROJECT_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then inspect with `osac --project "$PROJECT_A" get secret "$PROJECT_KEY" -o yaml`. If the target CLI does not create a Secret in Project A, use the supported administrative/service fixture and record its request and response. | Exactly one key fixture persists in the agreed scope, with Project A recorded when the model is project-scoped. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "$VM_AA" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. | VM is created with a canonical reference to Project A's key. |
| 3 | Inspect with `osac --project "$PROJECT_A" get computeinstance "$VM_AA" -o yaml` and run SSH verification. | The VM resolves A's key and the matching private key authenticates. |

### TC-05 — Named-project key, VM in another project or the default project

**Description:** Save different keys in Projects A and B. Use A's key for a VM
in B and for a VM in the default project, then prove that only A's private key
logs in. Then save two more keys with the same name, one in each project, and
prove that naming the project selects the intended key.

**Category:** Positive
**Test tier:** Component integration and deployed E2E
**Priority:** High
**Automation:** Unmerged PR #1828 covers named-project key selection for a default-project VM at the integration boundary; add both deployed E2E paths and real SSH login.

**Prerequisite:** Tenant User has access to Projects A and B and the default
project. `$PROJECT_KEY` exists in A from TC-04.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a different key in B with `osac --project "$PROJECT_B" create secret --name "$PROJECT_B_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect it with `osac --project "$PROJECT_B" get secret "$PROJECT_B_KEY" -o yaml` and inspect A's `$PROJECT_KEY` with `osac --project "$PROJECT_A" get secret "$PROJECT_KEY" -o yaml`. If project-scoped create is unavailable, use the supported administrative/service fixture and record its request and response. | Both keys have distinct names, IDs, public-key values, and the intended projects. |
| 2 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_AB" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. | VM is created in B with a canonical reference to A's key because the creator can access both projects. |
| 3 | Inspect with `osac --project "$PROJECT_B" get computeinstance "$VM_AB" -o yaml`; run the shared strict SSH command using A's private key, then repeat using `$KEY_DIR/id_ed25519_b`. | The reference points to A's key. A's private key authenticates; B's private key fails. |
| 4 | Run `osac project --clear`, then `osac create computeinstance --name "$VM_AD" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. Inspect with `osac get computeinstance "$VM_AD" -o yaml` and repeat both SSH attempts from step 3. | VM is created in the default project with A's key. Its reference points to A; A's private key authenticates and B's private key fails. |
| 5 | Create `$COLLISION_KEY` in A with `osac --project "$PROJECT_A" create secret --name "$COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"` and in B with `osac --project "$PROJECT_B" create secret --name "$COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519_b.pub"`. Inspect each with `osac --project "$PROJECT_A" get secret "$COLLISION_KEY" -o yaml` and `osac --project "$PROJECT_B" get secret "$COLLISION_KEY" -o yaml`. Use the administrative/service fixture if the CLI cannot create project-scoped Secrets. | Both registrations succeed; the keys share a name but have different projects, IDs, and public-key values. |
| 6 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_COLLISION" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$COLLISION_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac --project "$PROJECT_B" get computeinstance "$VM_COLLISION" -o yaml` and try both private keys. | The VM selects A's key; A's private key authenticates and B's private key fails. Clean up this VM with the other fixtures. |

### TC-06 — CatalogItem defaults, overrides, locks, and no-key behavior

**Description:** Use VM offerings that supply a default key, let users choose
another key, forbid changes, or specify no key. Check that each request either
uses the key allowed by the final policy or is rejected before a VM is created.

**Category:** Mixed
**Test tier:** Unit and component integration; deployed E2E if required
**Priority:** High
**Automation:** Locked-key policy is on `main`; add approved override/no-key paths and guest login.
**Flag:** POLICY-SENSITIVE

**Prerequisite:** A Project A key exists from TC-04. `CATALOG_ITEM` has no SSH-key default. CatalogItems for editable, locked, and no-key behavior are available. Inspect them with `osac get computeinstancecatalogitems "$EDITABLE_KEY_CATALOG_ITEM" -o yaml`, and repeat for the locked and no-key items. The OSAC-51 design excludes CatalogItem defaults, so these cases are non-blocking unless planning includes them.

| Step | Action | Expected result |
|---|---|---|
| 1 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-default-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"`, omitting `--ssh-key`; inspect with `osac --project "$PROJECT_A" get computeinstance "osac51-ci-default-$RUN_ID" -o yaml`. | If defaults are in scope, VM uses the canonical default key. |
| 2 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-override-$RUN_ID" --catalog-item "$EDITABLE_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`, then inspect with `osac --project "$PROJECT_A" get computeinstance "osac51-ci-override-$RUN_ID" -o yaml`. | Result matches the approved override policy; current implementation draft expects override to persist. |
| 3 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-locked-$RUN_ID" --catalog-item "$LOCKED_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A"`; query the VM name afterward. | If lock is in scope, request fails; get returns not found, no VM persists, and the locked value is unchanged. |
| 4 | Run `osac --project "$PROJECT_A" create computeinstance --name "osac51-ci-none-$RUN_ID" --catalog-item "$NO_KEY_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"`, without `--ssh-key`; inspect with `osac --project "$PROJECT_A" get computeinstance "osac51-ci-none-$RUN_ID" -o yaml`. | VM persists without registered-key reference/injection if this mode is supported. |

### TC-07 — Project, tenant, and shared isolation

**Description:** Try to use keys from a project the user cannot access, from
another tenant, and from shared resources. Forbidden requests should reveal
no key details and create no VM; keys belonging to different tenants must
stay separate even when they have the same name.

**Category:** Mixed
**Test tier:** Component integration for API authorization/persistence; deployed E2E only for CR/provider absence
**Priority:** Critical
**Automation:** PR #1828 covers denied-project lookup and shared-key creation rejection; add the missing access-transition and tenant-isolation assertions.
**Flag:** POLICY-SENSITIVE — shared-tenant rules only

**Prerequisite:** Tenant User can access Projects A and B; `$PROJECT_KEY` exists from TC-04. Tenant-B User has access to `$TENANT_B_PROJECT` but is not a member of Tenant A.

| Step | Action | Expected result |
|---|---|---|
| 1 | Tenant Admin keeps the user assigned to Project B, removes the user's Project A assignment through the membership API/fixture, and waits for convergence. User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-key-project-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`, then Tenant Admin queries that VM name. Restore Project A assignment and wait for convergence before the next step. | Creation fails because the user lacks access to the key's project, even though they can access the VM's project. The error does not disclose key details; the authorized query returns not found and no VM persists. |
| 2 | Tenant Admin removes the user's Project B assignment while retaining Project A access. User runs `osac --project "$PROJECT_B" create computeinstance --name "osac51-destination-access-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. After the request, Tenant Admin checks the VM name through the API, then restores Project B access and waits for convergence. | Destination-project authorization fails; the authorized API check returns not found. A deployed E2E check must separately confirm no ComputeInstance CR/provider operation; Project B access is restored. |
| 3 | As Tenant-B User, run `osac tenant "$TENANT_B"`, then `osac project --clear`, then `osac --project "$TENANT_B_PROJECT" create computeinstance --name "$VM_TENANT_B" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`, then run `osac --project "$TENANT_B_PROJECT" get computeinstance "$VM_TENANT_B" -o yaml`. | Same non-disclosing failure class; get returns not found and Tenant-A Secret details remain hidden. |
| 4 | Create `$TENANT_COLLISION_KEY` in both tenants: run `osac tenant "$TENANT_A"`, `osac project --clear`, and `osac create secret --name "$TENANT_COLLISION_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`; repeat in Tenant B with `id_ed25519_b.pub`. Switch back to Tenant B, clear the project, and run `osac --project "$TENANT_B_PROJECT" create computeinstance --name "osac51-tenant-collision-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "$TENANT_COLLISION_KEY" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac --project "$TENANT_B_PROJECT" get computeinstance "osac51-tenant-collision-$RUN_ID" -o yaml`. Restore `osac tenant "$TENANT_A"` and `osac project --clear` before the next case. | Only Tenant B's Secret ID resolves under the tenant-isolation contract; the canonical reference is tenant B-scoped and not shared. The CLI context returns to Tenant A. |
| 5 | Through the administrative/API fixture, submit an SSH-key Secret create request targeting the shared tenant, then list/get through the fixture. The public CLI has no shared-tenant creation command. | Rejected and no Secret persists if shared-tenant restrictions remain in scope; record the status/code. |
| 6 | Through the administrative/API fixture, attempt to create a ComputeInstance with a shared reference if the API permits constructing one; then query the VM name as an authorized Tenant Admin. | Rejected before VM persistence if shared references remain prohibited; the authorized query returns not found. A deployed E2E check is required to assert no CR/provider operation. |

### TC-08 — Key-project access revoked after VM creation

**Description:** Create a VM in Project B using a key from Project A. Then
remove the creator's access to A while keeping access to B. Another VM request
using A's key must be denied. The first VM keeps the key it received at
creation and remains accessible with the matching private key.

**Category:** Mixed
**Test tier:** Component integration for API authorization/persistence; deployed E2E for guest authentication and CR/provider absence
**Priority:** High
**Automation:** PR #1828 covers denied lookup; add the source-project access-revocation transition and existing-VM assertion.

**Prerequisite:** `$PROJECT_KEY` exists in Project A from TC-04. Tenant User
has access to Projects A and B. Tenant Admin can revoke and restore the user's
Project A assignment through the supported membership fixture.

| Step | Action | Expected result |
|---|---|---|
| 1 | Tenant Admin confirms the user can access both A and B through the membership API/fixture and waits for convergence. | Both project assignments are effective. |
| 2 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED_INITIAL" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac --project "$PROJECT_B" get computeinstance "$VM_REVOKED_INITIAL" -o yaml`. In deployed E2E, wait for Ready and prove that the shared strict SSH command succeeds before revoking access. | VM-1 persists in B with a canonical reference to A's key; in deployed E2E, it is running and the matching private key authenticates before revocation. |
| 3 | Tenant Admin revokes only the user's Project A assignment through the supported membership API/fixture and waits for convergence. | The user still has destination-project access but no longer has access to the key's project. |
| 4 | Run `osac --project "$PROJECT_B" create computeinstance --name "$VM_REVOKED" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$PROJECT_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`; then Tenant Admin queries `$VM_REVOKED`. | The new request is denied because the user cannot access A. The authorized query returns not found; a deployed E2E check separately confirms no CR/provider operation. |
| 5 | As the user, inspect the existing VM with `osac --project "$PROJECT_B" get computeinstance "$VM_REVOKED_INITIAL" -o yaml`. For deployed E2E, run the shared strict SSH command with the original private key. | The original key reference and VM status are unchanged; the same private key still authenticates to the running VM. |
| 6 | Tenant Admin restores Project A assignment through the supported membership API/fixture and waits for convergence. | The user's original access is restored. |

### TC-09 — Strict key and reference validation

**Description:** Try to save invalid public keys, then try to create VMs with
a key that is missing, deleted, or stored as a different kind of Secret. Each
request should fail without saving a VM or revealing hidden key details.

**Category:** Mixed
**Test tier:** Unit and component integration for API rejection/no-persistence; deployed E2E for CR/provider absence
**Priority:** Critical
**Automation:** Existing OpenSSH payload tests cover core shapes; extend for supported contract

Create synthetic invalid fixtures locally. Use private-key-like test text, not the generated private key or PEM contents, so the test never uploads private-key material.

For missing, deleted, hidden, and out-of-project references, the current
OSAC-6584/PR #1828 expectation is gRPC `InvalidArgument` with the same generic
message: `SSH key Secret was not found or is not visible in the selected project.`
Update this assertion if planning changes the contract. Component integration
can prove that no API object persists; assert absence of a ComputeInstance CR or
provider operation only in a deployed E2E harness.

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
for INVALID_CASE in malformed private-key-like empty two-keys trailing; do
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
    printf 'Unexpectedly accepted invalid key: %s\n' "$INVALID_CASE" >&2
    exit 1
  fi
  if osac get secret "$SECRET_NAME" -o yaml; then
    printf 'Invalid Secret persisted: %s\n' "$SECRET_NAME" >&2
    exit 1
  fi
done
~~~

| Input / CLI action | Expected result |
|---|---|
| Valid Ed25519: `osac create secret --name "osac51-valid-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`; inspect with `osac get secret "osac51-valid-$RUN_ID" -o yaml`. Generate RSA/ECDSA keys and repeat only if the final contract supports those formats. | Accepted; exactly one Secret persists with the expected type and public_key data. |
| Malformed, private-key-like, empty, two-key, and trailing-content fixtures. | Execute the loop above for each fixture. Each create is rejected, the follow-up get returns not found, and no Secret persists. |
| Wrong field: run `osac create secret --name "osac51-wrong-field-$RUN_ID" --type ssh-public-key --from-file "key=$KEY_DIR/id_ed25519.pub"`, then `osac get secret "osac51-wrong-field-$RUN_ID" -o yaml`. | Rejected because required public_key data is absent; get returns not found and no Secret persists. |
| Missing reference: run `osac --project "$PROJECT_A" create computeinstance --name "osac51-missing-ref-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "osac51-missing-$RUN_ID" --network-attachment "$NETWORK_ATTACHMENT"`, then `osac --project "$PROJECT_A" get computeinstance "osac51-missing-ref-$RUN_ID" -o yaml`. | Generic missing-reference error; the authorized API query returns not found. Use deployed E2E to assert no ComputeInstance CR/provider operation. |
| Deleted reference: create `osac51-deleted-ref-key-$RUN_ID` in Project A with `osac --project "$PROJECT_A" create secret --name "osac51-deleted-ref-key-$RUN_ID" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, delete it with `osac --project "$PROJECT_A" delete secret "osac51-deleted-ref-key-$RUN_ID"`, then create `osac --project "$PROJECT_A" create computeinstance --name "osac51-deleted-ref-vm-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=osac51-deleted-ref-key-$RUN_ID,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"` and query the VM name. | Generic missing-reference error; an authorized API query returns not found and no Secret remains. A deployed E2E check is needed to assert no ComputeInstance CR/provider operation. |
| Wrong type: create an opaque Secret in Project A with `osac --project "$PROJECT_A" create secret --name "osac51-opaque-$RUN_ID" --type opaque --from-file "public_key=$KEY_DIR/id_ed25519.pub"`, then select it with `osac --project "$PROJECT_A" create computeinstance --name "osac51-wrong-type-$RUN_ID" --catalog-item "$CATALOG_ITEM" --ssh-key "name=osac51-opaque-$RUN_ID,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"` and query the VM name as an authorized user. | Reference rejected for wrong type; the authorized API query returns not found. Use an API fixture for omitted data or lifecycle states not constructible through the CLI. |

### TC-10 — Selector grammar, immutable reference, and in-use deletion

**Description:** Try badly formatted `--ssh-key` values and attempts to change
the key already selected for a VM. Also check whether a key still used by a VM
can be deleted, according to the final policy.

**Category:** Negative with positive cleanup
**Test tier:** Unit and component integration for API behavior; deployed E2E if checking provider side effects
**Priority:** Critical
**Automation:** Selection and immutability are partially covered; add the in-use deletion boundary if policy requires it.
**Flag:** POLICY-SENSITIVE — TC-10 step 4 only; in-use deletion behavior is not explicit in the OSAC-51 contract.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create an independent test Secret and VM using `osac --project "$PROJECT_A" create secret --name "$IMMUTABLE_KEY" --type ssh-public-key --from-file "public_key=$KEY_DIR/id_ed25519.pub"` and `osac --project "$PROJECT_A" create computeinstance --name "$VM_IMMUTABLE" --catalog-item "$CATALOG_ITEM" --ssh-key "name=$IMMUTABLE_KEY,project=$PROJECT_A" --network-attachment "$NETWORK_ATTACHMENT"`. | The VM persists with a canonical reference to `$IMMUTABLE_KEY`. |
| 2 | For each malformed selector in the matrix below, run the CLI command and query the unique VM name afterward. | Every malformed selector fails and no API ComputeInstance persists. Use deployed E2E, not component integration, to assert no CR/provider operation. |
| 3 | Use an authenticated API test client to call `ComputeInstances.Update` for `$VM_IMMUTABLE`, first replacing `spec.ssh_key` with the existing default-project reference `$DEFAULT_KEY`, then clearing it, with `update_mask: ["spec.ssh_key"]`. The public CLI has no update command for this field. | Both updates are rejected; the original canonical reference remains. Record each request and response. |
| 4 | Run `osac --project "$PROJECT_A" delete secret "$IMMUTABLE_KEY"` while `$VM_IMMUTABLE` references it, then inspect with `osac --project "$PROJECT_A" get secret "$IMMUTABLE_KEY" -o yaml` and `osac --project "$PROJECT_A" get computeinstance "$VM_IMMUTABLE" -o yaml`. | Delete fails; key remains unchanged and VM is unaffected if in-use protection remains in the final contract. |
| 5 | Run `osac --project "$PROJECT_A" delete computeinstance "$VM_IMMUTABLE"` and poll until absent; then run `osac --project "$PROJECT_A" delete secret "$IMMUTABLE_KEY"` and poll until absent. | Both deletes succeed and resources eventually disappear. |

Use distinct selectors to exercise each parser failure:

~~~bash
BAD_SELECTORS=(
  'name='
  "project=$PROJECT_A"
  "name=$DEFAULT_KEY,name=$DEFAULT_KEY"
  "name=$DEFAULT_KEY,project=$PROJECT_A,project=$PROJECT_B"
  "name=$DEFAULT_KEY,region=x"
  "name=$DEFAULT_KEY,"
  "name$DEFAULT_KEY"
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
  if osac --project "$PROJECT_A" get computeinstance "$INVALID_VM" -o yaml; then
    osac --project "$PROJECT_A" delete computeinstance "$INVALID_VM"
    printf 'Invalid-selector VM persisted: %s\n' "$INVALID_VM" >&2
    exit 1
  fi
done
~~~

### TC-11 — Supported and unsupported guest combinations

**Description:** Check that Linux VMs can start with or without a saved key,
while a Windows VM request that asks for key injection is rejected. Record
what happens with a Linux image that uses a different setup method (Ignition)
once that behavior is decided.

**Category:** Mixed
**Test tier:** Unit validation and deployed E2E provisioning; component integration for API acceptance/rejection
**Priority:** High
**Automation:** Windows rejection and Linux projection are covered; ignition needs a policy and fixture.

| Guest scenario | CLI command | Expected result |
|---|---|---|
| Linux cloud-init with a registered key. | `osac create computeinstance --name "osac51-linux-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`; inspect with `osac get computeinstance "osac51-linux-key-$RUN_ID" -o yaml`. | VM reaches Ready and receives key through provisioning. |
| Linux cloud-init without a key. | `osac create computeinstance --name "osac51-linux-no-key-$RUN_ID" --catalog-item "$CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT"`; inspect with `osac get computeinstance "osac51-linux-no-key-$RUN_ID" -o yaml`. | VM reaches Ready without a registered-key reference/injection. |
| Windows template with a key. | `osac create computeinstance --name "osac51-windows-key-$RUN_ID" --catalog-item "$WINDOWS_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`. | Rejected before provider provisioning; `osac get computeinstance "osac51-windows-key-$RUN_ID" -o yaml` returns not found. The PRD excludes key injection into Windows. |
| Ignition/non-cloud-init Linux template with a key. | Run `osac create computeinstance --name "osac51-ignition-key-$RUN_ID" --catalog-item "$IGNITION_CATALOG_ITEM" --network-attachment "$NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`, then inspect with `osac get computeinstance "osac51-ignition-key-$RUN_ID" -o yaml`. | POLICY-PENDING: record the actual result and evidence; do not block release until planning defines the expected behavior and a deterministic fixture is available. |

This is a negative compatibility test for registered-key injection. It does not assert that a keyless Windows VM cannot be created.

### TC-12 — VM with real SSH authentication

**Description:** Create a VM the test client can reach for remote login (SSH).
Log in using the private key that matches the saved public key, then confirm
that an unrelated private key cannot log in.

**Category:** Positive E2E plus negative authentication
**Test tier:** Manual deployed E2E
**Priority:** Critical
**Automation:** Current E2E verifies resource projection, not actual login

**Preconditions:** The test tenant has a READY VirtualNetwork and Subnet in
that network, a READY ExternalIPPool with capacity, and a stable client egress
IPv4 address. The allocated ExternalIP must be routable from that client. The
test SecurityGroup's egress policy must permit the selected template's required
provisioning and runtime traffic. Set `SSH_TEST_EGRESS_RULE` to a reviewed,
least-privilege rule for that traffic and record the rule used. If multiple
rules are required, pass each with a separate `--egress` flag. Never use
unrestricted egress for this case.

| Step | Action | Expected result |
|---|---|---|
| 1 | Create a dedicated SecurityGroup with `osac create securitygroup --name "$SSH_TEST_SECURITY_GROUP" --virtual-network "$SSH_E2E_VIRTUAL_NETWORK" --ingress "protocol=tcp,port-from=22,port-to=22,ipv4-cidr=$SSH_TEST_CLIENT_CIDR" --egress "$SSH_TEST_EGRESS_RULE"`; poll `osac get securitygroup "$SSH_TEST_SECURITY_GROUP" -o yaml` until Ready. Verify that the egress policy contains only the approved rules. Create the VM with `osac create computeinstance --name "$VM_SSH_E2E" --catalog-item "$CATALOG_ITEM" --network-attachment "$SSH_E2E_NETWORK_ATTACHMENT" --ssh-key "$DEFAULT_KEY"`; poll `osac get computeinstance "$VM_SSH_E2E" -o yaml` until Ready and its network attachment status has an IP address. | The SecurityGroup allows TCP/22 only from the test client's IPv4 CIDR and uses the reviewed least-privilege egress policy without an unrestricted egress rule. The VM becomes Ready with this group attached. |
| 2 | Check pool readiness and capacity with `osac get externalippool "$EXTERNAL_IP_POOL" -o yaml`. Allocate an ExternalIP with `osac create externalip --name "$EXTERNAL_IP_NAME" --pool "$EXTERNAL_IP_POOL"`, wait until allocated, then attach it with `osac create externalipattachment --name "$EXTERNAL_IP_ATTACHMENT" --externalip "$EXTERNAL_IP_NAME" --compute-instance "$VM_SSH_E2E"`. Poll `osac get externalip "$EXTERNAL_IP_NAME" -o yaml` and `osac get externalipattachment "$EXTERNAL_IP_ATTACHMENT" -o yaml` until allocated/ready; copy `status.address` to `EXTERNAL_IP_ADDRESS`. | ExternalIP and attachment reach their expected states; the test client can route to the address on TCP/22. If the allocated address is not reachable from the test client, classify this case as inconclusive. |
| 3 | Populate `$KNOWN_HOSTS` from a trusted host-key source, set `VM_ADDRESS="$EXTERNAL_IP_ADDRESS"`, and run the common strict SSH command from the setup section. | Exit 0; stdout is OSAC_SSH_OK; no password prompt. |
| 4 | Repeat the common SSH command with `-i "$KEY_DIR/id_ed25519_b"` instead of `-i "$KEY_DIR/id_ed25519"`; keep the same target and strict host-key settings. | Non-zero authentication failure. |
| 5 | On failure, capture serial console, cloud-init, and sshd evidence before cleanup. | Evidence separates key injection failure from VM or network readiness issues. |
| 6 | Run `osac delete externalipattachment "$EXTERNAL_IP_ATTACHMENT"` and wait for detach; then delete the ExternalIP, VM, SecurityGroup, and Secret with `osac delete externalip "$EXTERNAL_IP_NAME"`, `osac delete computeinstance "$VM_SSH_E2E"`, `osac delete securitygroup "$SSH_TEST_SECURITY_GROUP"`, and `osac delete secret "$DEFAULT_KEY"`; poll each to absence. | All test resources eventually disappear. |

### TC-13 — Key-data update policy

**Description:** Once OSAC defines whether saved keys may be changed, try an
update before and after a VM uses the key. Check the expected rejection or,
if updates are allowed, their effect on new VMs without changing an existing VM.

**Category:** Pending
**Test tier:** Confirm after planning
**Priority:** Deferred pending the policy decision
**Automation:** Not scheduled
**Flag:** POLICY-PENDING

Keep this case disabled until registered Secret data-update behavior is
finalized. OSAC-51 excludes changing the key already injected into a running
VM; do not treat that as a supported rotation path. If Secret updates are
allowed, test the updated Secret on a newly created VM and verify the existing
VM remains unchanged. If updates are rejected while referenced, verify that
rejection and confirm the original Secret data remains intact.

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
| 1 | Use the TC-01 and TC-09 CLI commands to register a key from the public-key file, then inspect CLI/API responses and normal logs. | The private key is never uploaded, persisted, returned, or logged. Public-key data is not exposed to another tenant. |
| 2 | Trigger the TC-09 invalid-key and missing-reference CLI cases; inspect CLI output and service logs. | Errors include enough context to diagnose the failure without printing private key material or disclosing another tenant's key data. |

### NFR-SSH-02 — Non-disclosing authorization failures

**Description:** Compare the error shown for a key that does not exist with
errors for keys the user is not allowed to use. The responses must not let the
user discover that a hidden key exists, and no VM should be created.

**Test tier:** Unit and component integration
**Priority:** High

**Automation:** PR #1828 adds unit and component-integration assertions for missing, hidden, out-of-project, and project-inaccessible references. Cross-tenant equivalence and output/log hygiene remain gaps.

Use the TC-07 and TC-09 CLI/API-fixture attempts involving a missing key, a key in another tenant, and a key outside the caller's authorized scope. Where the contract requires non-disclosure, the caller receives the same externally observable error class/message and cannot infer whether the hidden key exists. Verify that no VM is persisted for any denied attempt; verify no CR/provider operation only in deployed E2E.

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
| Key-name requirement wording | The confirmed rule allows the same name in different projects of one tenant, while the current PRD says names are unique within a tenant. | Align the PRD wording with per-tenant, per-project uniqueness; execute TC-05 steps 5–6. |
| CatalogItem support | OSAC-51 design excludes CatalogItem defaults; current task/PR includes related policy behavior. | Confirm release scope; keep TC-06 flagged until decided. |
| Project membership/revocation | New VM creation requires access to both projects. After key-project access is revoked, the previously created VM retains its injected key and remains accessible. PR #1828 tests denied lookup, but not this transition. | Add TC-08 transition assertions at component integration and deployed E2E tiers. |
| Shared-tenant rules | Current PR reports rejection of shared-tenant SSH-key creation. | Confirm expected shared-tenant behavior and test both create and resolve paths. |
| In-use SSH-key deletion | `main` has a generic Secret deletion guard for a different resource; there is no SSH-key/ComputeInstance deletion assertion in `main` or PR #1828. | Decide whether a referenced key Secret must be protected from deletion. If yes, add the SSH-key-specific unit and component-integration assertions; otherwise change TC-10 step 4. |
| Guest compatibility | Windows validation exists; no deterministic ignition fixture identified. | Prepare fixture or mark ignition case out of scope with follow-up issue. |
| Real SSH in CI | Existing E2E checks resource projection; runner cannot route to guest subnet. | Run manual TC-12; track routed automation under [OSAC-6526](https://redhat.atlassian.net/browse/OSAC-6526) if required. |
| Key-data update behavior | No final behavior is agreed. | Keep TC-13 POLICY-PENDING and non-blocking. |
| Integration execution | PR #1828 reports integration package compile only because host mappings were unavailable. | Run component integration suite in a suitable environment before marking it executed. |

## Exit criteria

- The planned cases trace to agreed requirements and the cross-project access decision; flagged behavior is finalized before becoming release-blocking.
- Each successful VM reference resolves to the expected key; for SSH acceptance cases, the matching private key authenticates.
- Negative cases use the agreed error class, disclose no cross-scope key metadata, and persist no unintended VM. Where required, deployed E2E also confirms no ComputeInstance CR or provider operation.
- The wrong private key fails authentication; tests use strict host-key verification.
- In-use deletion, name reuse, CatalogItem behavior, and updates match the final recorded policy.
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
| Dedicated manual real-SSH E2E case | 1 (TC-12; TC-02–05 also require guest SSH) |
| Policy-sensitive / policy-pending behaviors | 4 / 2 |
| Executable test code added by this plan PR | 0 |

**Execution status:** No manual or deployed execution is recorded for this plan.
