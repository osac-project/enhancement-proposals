# Clarification Log — OSAC-51

## Status

- Rounds completed: 3
- Open gaps: 0 (one item carried into PRD Open Questions per D8, not a clarification gap)
- Exit criteria met: Yes

## Round 1 — Scope, Personas, Validation

### R1.Q1: Service boundary — VMaaS-only vs. multi-service registry

The Definition of Done ties key injection specifically to ComputeInstance/cloud-init (VMaaS). Is the SSH key registry itself VMaaS-only for this milestone, or should the API be designed so BMaaS (bare metal) and CaaS (cluster) provisioning could reference the same registry in a later milestone?

#### Answer

SSH key management should be available for other services in the future. The Definition of Done for this specific feature is VMaaS-only (ComputeInstance).

#### Impact

The registry API (create/list/get/delete) should be designed as a standalone, service-agnostic resource rather than embedded in ComputeInstance-specific logic, so BMaaS and CaaS can reference it later without rework. This feature's delivered scope (injection at creation time) remains limited to ComputeInstance/VMaaS.

#### Decision (D1)

The SSH key registry API is designed as a service-agnostic resource. This feature's Definition of Done delivers key injection for ComputeInstance (VMaaS) only; BMaaS and CaaS integration are out of scope for this milestone but not precluded by the API design.

---

### R1.Q2: Ownership and visibility — Tenant Admin access to another user's keys

Only the Tenant User persona is mentioned in the user stories. Are registered keys private to the individual Tenant User who created them, or visible/manageable by other users in the same tenant org (e.g., can a Tenant Admin see or delete another user's keys)?

#### Answer

The visibility scope is the same as for any other resource — the Tenant Admin can manage them as well.

#### Impact

Confirmed against the existing OSAC authorization model (`osac/fulfillment-service/docs/AUTH.md`): visibility and authorization for tenant resources (ComputeInstance, VirtualNetwork, etc.) are keyed on `metadata.tenant`, not on the creating user — `metadata.creator` is informational only. There is no existing per-user ownership/visibility restriction for any comparable resource. Applying the same model here means any Tenant Admin in the org can see, use, and delete any Tenant User's registered SSH keys, and any Tenant User can potentially see keys registered by others in the same tenant (list scope = tenant, not creator). The PRD's Tenant Admin user stories and acceptance criteria must reflect full CRUD parity with Tenant User, scoped by tenant.

#### Decision (D2)

SSH key visibility and management follow OSAC's standard tenant-scoped resource model: authorization is keyed on tenant, not on the creating user. Tenant Admin has the same create/list/get/delete capabilities as Tenant User over all SSH keys in their tenant.

---

### R1.Q3: UI scope

The Definition of Done lists API and CLI (`osac create/get/delete sshkey`) but no UI. Is UI support for the SSH key registry in scope for this milestone, or explicitly deferred (API/CLI-only)?

#### Answer

Yes, UI should be included — both for lifecycle management and for using keys with ComputeInstances.

#### Impact

UI is added as an in-scope interface alongside API and CLI, covering two distinct workflows: (1) key lifecycle management (register, list, delete) and (2) key selection when creating a ComputeInstance. The Definition of Done and User Stories must be updated to include UI-facing acceptance criteria for both personas (Tenant User, Tenant Admin per D2).

#### Decision (D3)

UI support is in scope for this milestone, covering both SSH key lifecycle management (create/list/delete) and key selection during ComputeInstance creation.

---

### R1.Q4: Validation rules

Which public key formats must be accepted (e.g., RSA, ED25519, ECDSA)? What counts as "invalid" for the failure-on-create user story — malformed/unparseable key material only, or also policy checks like minimum key strength?

#### Answer

BMaaS already implements validation for this. Use the same validation this feature requires.

#### Impact

Confirmed BMaaS's existing implementation (`osac/fulfillment-service/internal/servers/ssh_validation.go`): it parses the key using `golang.org/x/crypto/ssh`'s `ssh.ParseAuthorizedKey` against the OpenSSH authorized-keys line format, accepting whatever key types that parser supports (e.g., `ssh-rsa`, `ssh-ed25519`, `ecdsa-sha2-*`), and rejects on parse failure or unexpected trailing content after the key. There is no key-strength or algorithm-allowlist check beyond successful parsing. This feature reuses that same validation rule and error behavior rather than defining new format or strength policy.

#### Decision (D4)

SSH public key validation matches BMaaS's existing implementation: keys must parse as a single OpenSSH authorized-keys-format public key (via `ssh.ParseAuthorizedKey` semantics); validation is parse-only, with no additional key-strength or algorithm-allowlist restriction. Registration fails with an error if the key does not meet this bar.

---

### R1.Q5: Non-goal — external secret manager / ESO integration

A review comment on the Jira issue raised automated secret syncing into tenant namespaces via an external secrets operator as a related but only partially-covered requirement. Should the PRD state explicitly that this kind of external-secrets-manager integration is out of scope for this feature?

#### Answer

Yes, add it to Out of Scope.

#### Impact

The PRD's Out of Scope section gets an explicit line stating that automated secret syncing into tenant namespaces via an external secrets operator (e.g., External Secrets Operator) is not covered by this feature, distinct from the already-noted "external secret managers (Vault, ESO)" non-goal — this makes clear the specific syncing capability raised in review is not partially satisfied by this feature.

#### Decision (D5)

Out of Scope explicitly states that automated secret syncing into tenant namespaces via an external secrets operator is not covered by this feature.

---

## Round 2 — Naming, Limits, Deletion, Testing

### R2.Q1: Naming/uniqueness scope

Given keys are tenant-scoped (D2), must a key's name be unique per tenant (across all users in the org), or only unique per the user who registered it (allowing two users in the same tenant to both name a key "laptop")?

#### Answer

Unique per tenant, across all users.

#### Impact

Key name uniqueness is validated at the tenant level, consistent with the tenant-scoped visibility model from D2. Registration must fail if another user in the same tenant has already registered a key with that name.

#### Decision (D6)

SSH key names must be unique per tenant, across all users in that tenant — not just per the registering user.

---

### R2.Q2: Quota on registered keys

Should there be a limit on the number of SSH keys a tenant (or user) can register, or is this unbounded for this milestone?

#### Answer

Unbounded.

#### Impact

No quota/limit is enforced on the number of registered SSH keys for this milestone. The PRD does not need a quota-management requirement for this feature.

#### Decision (D7)

No limit is placed on the number of SSH keys a tenant may register in this milestone.

---

### R2.Q3: Delete-while-referenced behavior

Since key injection happens only on first boot (per the Definition of Done), if a user deletes a key that was used to provision an existing, already-running ComputeInstance, should the delete be blocked (key still "in use"), or allowed (deleting the registry entry doesn't affect a VM that already has the key baked in)?

#### Answer

Do not block the deletion. Also carry this forward as an open question in the first PRD draft, to discuss with reviewers.

#### Impact

Deletion of a registered key is unconditionally allowed, even if a ComputeInstance was previously provisioned with it — since injection is first-boot-only, the already-provisioned VM is unaffected. This is recorded as a locked decision for drafting, but the PRD's Open Questions section must still flag it for reviewer discussion (e.g., whether a warning or reference count should surface to the user before deletion).

#### Decision (D8)

Deleting a registered SSH key is never blocked by existing ComputeInstance references — already-provisioned VMs retain the key from first boot regardless of later deletion from the registry. This decision is also carried into the PRD's Open Questions section for reviewer discussion.

---

### R2.Q4: E2E test coverage

Which flows must have E2E coverage for this milestone — registry CRUD only (create/list/get/delete a key), or also the full path of selecting a key at ComputeInstance creation and verifying it lands in the VM via cloud-init?

#### Answer

E2E should cover the full path of selecting a key at ComputeInstance creation and verifying it lands in the VM. Registry lifecycle (create/list/get/delete) doesn't need full E2E since keys never leave the service — integration-level coverage is sufficient there.

#### Impact

Test coverage requirements are split by depth: registry CRUD is covered at the integration test level (within `fulfillment-service`), while the ComputeInstance-creation-to-cloud-init-injection path requires full E2E coverage in `osac-test-infra`, since it crosses service boundaries into the provisioned VM.

#### Decision (D9)

SSH key registry lifecycle (create/list/get/delete) is covered by integration tests, not full E2E. The path from selecting a key at ComputeInstance creation through cloud-init injection into the VM requires full E2E coverage.

---

## Round 3 — NFRs and Rename

### R3.Q1: Non-functional constraints

Are there any specific constraints for this feature — e.g., a maximum accepted key size/length, or a requirement to audit/trace which key name was used when a ComputeInstance was created — or is this deliberately minimal for this milestone?

#### Answer

Nothing special. Same as the current validation in BMaaS.

#### Impact

No additional non-functional requirements beyond the validation behavior already captured in D4. No audit/traceability requirement or size/length constraint beyond what `ssh.ParseAuthorizedKey` enforces.

---

### R3.Q2: Rename support

The Definition of Done lists create/list/get/delete only, with no update endpoint. Is renaming a registered key explicitly out of scope for this milestone?

#### Answer

No — the user needs to recreate (delete and re-register) to change a key's name.

#### Impact

Confirms no update/rename endpoint is part of this feature's API surface. This is added as an explicit Out of Scope line so reviewers don't assume an update capability exists.

#### Decision (D10)

Renaming a registered SSH key is out of scope. To change a key's name, the user deletes the existing entry and registers a new one.

---

## Remaining Gaps

None. All identified gaps were resolved across rounds 1–3. One resolved decision (D8 — delete-while-referenced) is additionally carried into the PRD's Open Questions section for reviewer discussion, per the user's request — this is not an unresolved clarification gap.
