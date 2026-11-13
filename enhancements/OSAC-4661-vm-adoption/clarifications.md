# Clarification Log — OSAC-4661

## Status

- Rounds completed: 12
- Open product-requirement gaps: 0 blocking PRD drafting
- Open design/validation work: 3 groups (existing network/storage and native-operation compatibility, concrete qualification and validation resources, external-management risk)
- Exit criteria met: Yes, for PRD drafting; feasibility and deployed acceptance evidence remain outstanding.

## Current MVP Scope

Adopt an eligible existing OpenShift Virtualization VM that is already running in an OSAC-managed namespace. The VM must work with existing OSAC networking and storage capabilities; this MVP does not add or change OSAC networking or storage features. Preserve the existing VM and disk during adoption, use an explicit reference, and provide same-release native VM behavior after adoption. Admission must reject incompatible configurations with an actionable reason.

Full OSAC Volume behavior for the existing disk remains required **only where existing storage capabilities already provide it**; incompatible VMs are rejected. Do not introduce new storage behavior, allocate a replacement disk, fabricate a Volume or copy data to make adoption possible. This qualification (D35) refines D3, D5 and D12. Any missing prerequisite is a feasibility gap, not implicit permission to expand this MVP.

The source issue's broader requirements—including general existing-cluster import and automatic source-label mapping—remain on OSAC-4661 until delivered or explicitly assigned. The source artifact and Jira are unchanged.

## Round 1 — Pilot scope and user experience

### R1.Q1: PRD boundary

Should this PRD describe only the first MTV adoption pilot, while retaining broader import requirements on OSAC-4661 until delivered or assigned?

#### Answer

Pilot PRD.

#### Impact

Describe the first increment while preserving broader existing-cluster and disk-to-Volume requirements on OSAC-4661 until delivered or assigned to owned, traceable follow-up work. No Jira scope change is implied.

#### Decision (D1)

The PRD covers the first adoption pilot. Broader requirements remain on OSAC-4661 until delivered or explicitly assigned. R8.Q1 (D26) later removes the MTV-origin restriction from that pilot.

---

### R1.Q2: Pilot interfaces

Which interfaces must the first pilot provide for VM adoption and tenant operation?

#### Answer

CLI/API only.

#### Impact

Specify the required admin and tenant workflows through CLI/API rather than requiring new pilot UI workflows. Clarify how correct guest console access is provided through the selected interfaces.

#### Decision (D2)

The first pilot requires CLI/API, not new UI workflows for adoption or tenant operation.

---

### R1.Q3: Existing guest disk

For the pilot, what must tenants be able to do with the existing guest disk?

#### Answer

Full Volume support: require the existing disk to become an OSAC Volume with agreed independent Volume capabilities before admission.

#### Impact

Treat full existing-Volume semantics as a first-admission prerequisite, not merely a disclosed observed binding. Identify which independent capabilities are required and preserve the existing disk without an extra copy or fabricated allocation.

#### Decision (D3)

Full existing-Volume support is required for the pilot before admission; observed binding alone is insufficient. D35 later restricts this to cases already supported by existing OSAC storage capabilities, without changing storage features.

---

### R1.Q4: Pilot VM power and lifecycle actions

Which power actions should authorized tenant users have on an admitted pilot VM?

#### Answer

Everything which is possible with native OSAC VMs today.

#### Impact

Identify and verify the existing native VM action set before stating parity. Reconcile the requested parity with the source's explicit restrictions on destructive imported deletion, unsupported updates, recreation and forceful recovery; do not silently assume those restrictions are waived.

#### Decision (D4)

Target the same available actions as native OSAC VMs today, subject to resolving the conflict with the source's explicit imported-VM safety restrictions.

## Round 2 — Lifecycle, storage and admission

### R2.Q1: VM deletion after adoption

What should deleting an adopted VM do in the pilot, given native-VM action parity and the source's data-retention rule?

#### Answer

The user thinks the source's deletion exclusion refers to the migration/import process, not the VM after that process finishes, and asks whether that interpretation makes sense.

#### Impact

Distinguish protection during migration and admission from explicitly authorized post-admission operations. The source says destructive imported deletion is rejected server-side without explicitly limiting that rule to the import process; this interpretation is not yet a confirmed change to that requirement. Clarify expected post-admission VM and disk deletion effects.

---

### R2.Q2: Independent Volume operations

For the existing disk as a full OSAC Volume, which independent operations are required in the pilot?

#### Answer

Native Volume parity: match supported native Volume operations, including deletion when permitted, with attachment and data safeguards explicitly resolved.

#### Impact

Identify supported native Volume operations and required safety guards; ensure full existing-Volume functionality is available before adoption without extra disk copies or fabricated allocation.

#### Decision (D5)

Target parity with supported native Volume operations for the adopted disk, including deletion when permitted, subject to explicit attachment and data safeguards. D35 later restricts eligibility to capabilities already supported without storage feature changes.

---

### R2.Q3: VM configuration changes

Should adopted VMs support the same native-VM configuration changes, such as resizing, when those changes might alter the preserved guest?

#### Answer

Native update parity: support native-VM updates, subject to explicit authorization and normal validation; revise the original restriction.

#### Impact

The PRD needs native configuration-update parity after admission and must reconcile that decision with non-mutating validation and preservation during migration and admission. Verify actual native capabilities and their impact.

#### Decision (D6)

Support native-VM update parity for adopted VMs, subject to authorization and normal validation; do not treat the original blanket update restriction as settled.

---

### R2.Q4: Quota and accounting

How should pilot admission handle tenant quota and accounting for an existing VM and disk?

#### Answer

Enforce normal limits: apply tenant quota and accounting; refuse admission when limits or required checks cannot be satisfied.

#### Impact

Require ordinary tenant quota and accounting for the VM and disk and an actionable rejection if limits or required checks cannot be satisfied. Availability of those capabilities is a dependency to verify.

#### Decision (D7)

Admission enforces normal tenant quota and accounting for the VM and disk; it fails when limits or required checks cannot be satisfied.

## Round 3 — Safety boundary and recovery

### R3.Q1: Post-adoption deletion

After adoption succeeds, should an authorized user be able to delete the VM with normal native-VM deletion behavior, even when that behavior removes the VM or guest data?

#### Answer

Normal deletion: allow native deletion after adoption, with normal permissions and safeguards; prohibit unintended deletion during import.

#### Impact

Separate migration/admission safety from explicitly authorized post-adoption deletion. Document native deletion effects and safeguards based on verified behavior; revise the source's blanket exclusion for imported-VM deletion.

#### Decision (D8)

After successful adoption, an authorized user may delete the VM with normal native-VM deletion behavior. Import must not unintentionally delete the guest or its data.

---

### R3.Q2: Forceful power actions

If native OSAC VMs offer forceful power actions, should those actions be available after adoption?

#### Answer

Explicit force only: allow supported force actions when explicitly requested and authorized; graceful actions never silently escalate.

#### Impact

Verify which forceful actions native VMs actually offer. A graceful operation cannot silently turn into a forceful one.

#### Decision (D9)

Supported native force actions may be used after adoption only when explicitly requested and authorized; graceful actions never silently escalate.

---

### R3.Q3: Network verification failure

If adoption checks cannot verify the VM's tenant network attachment and isolation, what should the administrator see?

#### Answer

Reject with reason: refuse admission with an actionable reason; preserve the existing VM and data.

#### Impact

Require an actionable admission refusal when network attachment or tenant isolation cannot be verified, without modifying or deleting the VM and guest data.

#### Decision (D10)

Unverified tenant attachment or isolation blocks admission with an actionable reason; the existing VM and data are preserved.

---

### R3.Q4: Recovery communication

Who should receive an actionable failure when adoption is interrupted or a partial claim needs recovery?

#### Answer

The user who requested the migration/import. That user escalates to administrators when needed.

#### Impact

The requesting user receives actionable failure and recovery information and decides when to escalate. This does not assign the administrator or operational owner responsible for executing a recovery.

#### Decision (D11)

Report actionable migration/import failure to the requester, who escalates to administrators as needed.

## Round 4 — Pilot readiness and interfaces

### R4.Q1: Volume prerequisite timing

When must full existing-Volume support be available for the pilot?

#### Answer

Before admission: allow migration first; require the capability before adoption, with explicit responsibility for the intermediate state.

#### Impact

The adoption PRD requires full Volume support before admission, not necessarily before MTV execution. This changes the source's sequencing assumption that full existing-Volume capability must be available before migration when needed initially; specify safe intermediate-state retention and operational ownership with the sibling Features.

#### Decision (D12)

Full existing-Volume support must be available before admission. Migration may occur first if the intermediate state has explicit responsibility. D35 later clarifies that only already-supported storage capabilities are in MVP scope; migration is not required for an otherwise eligible VM.

---

### R4.Q2: Console access

What console access must CLI/API-only pilot users receive after adoption?

#### Answer

Native console parity: provide the same supported console access as native OSAC VMs through available CLI/API interfaces.

#### Impact

Identify supported native console access and its CLI/API exposure; require the correct adopted VM's console with equivalent authorization, without inventing an interface.

#### Decision (D13)

Provide native-VM console parity through available CLI/API interfaces for adopted VMs.

---

### R4.Q3: Pilot qualification breadth

How broad must the pilot's supported VM and infrastructure combinations be?

#### Answer

One qualified path: qualify at least one agreed guest, target and storage backend; document other combinations as unsupported until qualified.

#### Impact

Define one demonstrably supported guest/target/backend path and disclose the qualification boundary. Specific versions, guest, backend and lab resources remain to be selected.

#### Decision (D14)

Qualify at least one agreed guest, target and storage backend; other combinations are unsupported until qualified.

---

### R4.Q4: Requester recovery

After an import fails or is interrupted, what must the requester be able to do?

#### Answer

See status and retry: see actionable status and safely retry after problems are corrected; escalate to admins when needed.

#### Impact

Require actionable requester-visible failure status and safe retry following correction. The requester may escalate; operational ownership of repair and partially migrated resources remains to be assigned.

#### Decision (D15)

The requester can see actionable status and safely retry after problems are corrected, escalating to administrators as needed.

## Round 5 — Ownership and pilot qualification

### R5.Q1: Handoff ownership

Who owns the migrated VM and its data while it waits for OSAC admission, including when Volume support is not ready?

#### Answer

Migration owner: the migration operator retains responsibility until admission succeeds and ownership is explicitly handed over.

#### Impact

Document an explicit handoff from the prior owner at successful admission. This is a dependency and safety boundary; the Feature does not perform migration.

#### Decision (D16)

The migration owner remains responsible for the VM and data until admission succeeds and ownership is explicitly handed over.

---

### R5.Q2: Admission requester

Who may request pilot admission of the already-migrated VM into a tenant?

#### Answer

Tenant admin too: allow authorized Cloud Provider and Tenant Admins to request admission to their permitted tenants.

#### Impact

Cover both requester personas, their authorized tenant boundaries and their requester-visible failure and retry experiences.

#### Decision (D17)

Authorized Cloud Provider Admins and Tenant Admins may request admission for tenants within their permissions.

---

### R5.Q3: Pilot qualification timing and Feature scope

When must the specific guest, versions, target, backend and lab for the one pilot path be selected?

#### Answer

The user questioned repeated references to migration and clarified that OSAC-4661 concerns adopting an already migrated VM, not carrying out migration. No qualification-timing option was selected.

#### Impact

Keep the PRD focused on admission and management after the VM exists. Treat migration and its handoff as external prerequisites; do not expand this Feature to perform or orchestrate migration. Exact qualification timing remains open.

#### Decision (D18)

OSAC-4661 covers adoption and management of an existing VM, not execution or orchestration of migration. R8.Q1 (D26) later clarifies that the VM need not originate from any specific tool.

---

### R5.Q4: Failure retention and ownership

When adoption fails after migration, what happens to the migrated VM while the requester arranges recovery?

#### Answer

Keep under prior owner: preserve the VM and data under its existing operational owner until safe retry or an explicit handoff.

#### Impact

Admission failures must not abandon the guest or its data. Requester-visible status and retry coexist with the prior owner's responsibility and explicit handoff.

#### Decision (D19)

On failed adoption, preserve the VM and data under the prior owner until safe retry or an explicit handoff.

## Round 6 — Adoption behavior

### R6.Q1: Qualification timing

When must the pilot's exact supported guest, OSAC/OpenShift versions, target and storage backend be agreed?

#### Answer

Before admission: select and verify at least one complete supported combination before admitting the pilot VM.

#### Impact

Make a verified guest/version/target/backend combination an admission prerequisite; identify the exact combination and validation resources in delivery planning.

#### Decision (D20)

Select and verify at least one supported guest, version, target and backend combination before pilot admission.

---

### R6.Q2: Tags and metadata

What existing tags and metadata must the pilot expose on the adopted VM?

#### Answer

The user asked which metadata and tags the question refers to. After the distinction between required tenant/VM identity and optional user-defined labels was explained, the user said some kind of identity is needed, options should be mentioned, and the decision should be left to design. No label-mapping scope option was selected.

#### Impact

The PRD must require unambiguous identification of the correct VM and tenant; the design can compare suitable identity options without selecting a mechanism in the PRD. User-defined organization/cost labels and backend metadata are separate from identity; their pilot scope is resolved in R7.Q1. Do not assume any particular tag exists or that all labels can safely be copied.

---

### R6.Q3: Repair after partial claim

If a partial adoption claim needs repair before retry, who performs the repair?

#### Answer

Prior owner with admin: the prior owner coordinates with an authorized OSAC administrator; the requester receives status and initiates escalation.

#### Impact

Document coordinated recovery while preserving the prior owner's responsibility for the VM and data until explicit handoff; retain the requester's status and safe retry requirements.

#### Decision (D21)

The prior owner coordinates partial-claim repair with an authorized OSAC administrator; the requester receives status and escalates as needed.

## Round 7 — Remaining product boundaries

### R7.Q1: Label mapping

Should the pilot include mapping existing user-defined organization or cost-allocation labels into OSAC?

#### Answer

The user initially did not know what this refers to, then proposed treating labels like any other VMaaS VM. They confirmed the pilot should use normal native-VM label and metadata behavior without requiring automatic source-label mapping.

#### Impact

Apply normal native-VM label and metadata permissions and validation to adopted VMs. Automatic mapping of existing source labels is not a pilot requirement, but remains part of the broader OSAC-4661 requirements until delivered or explicitly assigned.

#### Decision (D25)

Use normal native-VM label and metadata behavior for the pilot. Automatic mapping of existing source labels remains retained broader scope.

---

### R7.Q2: Unsupported parity

If an otherwise eligible VM cannot support the agreed native-VM or Volume capabilities, should pilot admission proceed?

#### Answer

Reject with reason: refuse admission until required parity can be supported; preserve the VM and its data.

#### Impact

Define unsupported required capabilities as an actionable admission blocker; do not claim successful adoption with reduced parity.

#### Decision (D22)

Reject admission with an actionable reason when required native-VM or Volume parity cannot be supported; preserve the VM and data.

---

### R7.Q3: Running state during adoption

May an eligible VM remain running during adoption?

#### Answer

Stopping is permitted for the MVP, but should be avoided.

#### Impact

The pilot may require a stop when necessary; aim to avoid downtime and communicate any required stop. Do not claim uninterrupted adoption is guaranteed.

#### Decision (D23)

A stop is permitted for the MVP when necessary but should be avoided.

---

### R7.Q4: Management ownership

After successful adoption, how should OSAC handle competing management of the same VM?

#### Answer

Exclusive management is desired, but OSAC cannot control whether others manage the VM.

#### Impact

Describe OSAC as the intended exclusive manager after handoff without promising technical enforcement over external actors. The source requires no competing mutation owner or active retry at admission; design must assess detection, coordination and risks of outside changes.

#### Decision (D24)

Exclusive OSAC management is the desired operational model after handoff; enforcement against external managers is not assumed.

## Round 8 — Eligibility and interruption

### R8.Q1: Origin of eligible VM

Must pilot admission depend on which tool created the existing OpenShift Virtualization VM?

#### Answer

Any eligible VM: accept any existing VM meeting pilot eligibility and safety requirements, regardless of origin.

#### Impact

This revises the source's MTV-output-only pilot and the earlier MTV-specific framing in D1. Keep one qualified guest/target/backend path (D14); do not conflate origin independence with support for every possible configuration, generic fleet discovery, or cluster registration.

#### Decision (D26)

Pilot eligibility is independent of the tool that created the existing VM, subject to qualification and safety requirements.

---

### R8.Q2: Native parity baseline

Which native OSAC capability set should define parity for the pilot?

#### Answer

Same release: match supported native VM and Volume capabilities in the OSAC release used for adoption.

#### Impact

Identify and verify the actual supported native operation and console set for the selected release. Do not infer deployed support from an API declaration alone.

#### Decision (D27)

Adopted VM and Volume parity is measured against supported native capabilities in the same OSAC release.

---

### R8.Q3: Authorization to stop

If adoption requires stopping a running VM, how should the requester authorize that interruption?

#### Answer

Explicit approval: explain the required stop and obtain requester approval before OSAC initiates it.

#### Impact

Keep non-mutating validation distinct from any later authorized interruption. Describe the interruption and obtain approval before OSAC stops the guest.

#### Decision (D28)

Obtain explicit requester approval before OSAC initiates a stop required for adoption.

---

### R8.Q4: Power state after failure

If adoption fails after the guest was stopped for admission, what should happen to its power state?

#### Answer

Restore if safe: restore the prior running state when safe; report failures and leave recovery to the prior owner if restoration is unsafe.

#### Impact

Specify safe power-state restoration and actionable failure reporting, without overriding the prior owner's authority or endangering data.

#### Decision (D29)

After an admission failure, restore the prior running state when safe; otherwise report the failure and leave recovery to the prior owner.

## Round 9 — Adoption workflow

### R9.Q1: Existing namespace

Must the pilot use an OpenShift Virtualization target already registered and supported by OSAC?

#### Answer

The user asked what target meant and clarified that the intended operation imports an OCP VM running in a namespace already known to OSAC.

#### Impact

Describe adoption of an existing OpenShift Virtualization VM in an OSAC-known namespace, not a new cluster-onboarding workflow. The question used target to mean the hosting cluster. A known namespace alone does not prove correct tenant authority, networking or storage eligibility; existing admission validation requirements remain applicable. Do not infer a specific registration mechanism from this answer.

#### Decision (D30)

The pilot adopts an existing OpenShift Virtualization VM in a namespace already known to OSAC.

---

### R9.Q2: VM selection

How should an authorized requester identify the existing VM to adopt through CLI/API?

#### Answer

Explicit reference: provide an explicit VM reference; fleet discovery is not required for the pilot.

#### Impact

Require an explicit-reference adoption workflow through CLI/API. The design chooses how that reference establishes unambiguous identity and guards against replacement; no selection-list capability is required for this pilot.

#### Decision (D31)

The requester identifies the existing VM through an explicit reference; pilot fleet discovery is not required.

---

### R9.Q3: Power state after successful adoption

If an approved stop was needed and adoption succeeds, what should happen to a VM that was previously running?

#### Answer

Restore if safe: return it to its prior running state when safe, and report any failure.

#### Impact

Cover power restoration after successful adoption as well as the failure-time restoration in D29. Report restoration failures rather than implying the workload resumed successfully.

#### Decision (D32)

If adoption stopped a previously running VM, restore its prior running state after successful adoption when safe and report any failure.

---

### R9.Q4: Tenant deletion assumption

What should happen if a tenant deletion is requested while it still contains an adopted VM?

#### Answer

Not relevant for the MVP; assume no one deletes the tenant.

#### Impact

Record no tenant deletion as an MVP operating assumption, not a new tenant-cleanup feature or acceptance journey. This does not authorize bypassing existing tenant isolation, dependency guards or data-safety controls. Assess cleanup paths and the consequences of violating this assumption during design and validation.

#### Decision (D33)

The MVP assumes the tenant is not deleted; a tenant-deletion user journey is not part of the pilot.

## Round 10 — MVP scope and existing capabilities

### R10.Q1: MVP boundary

What scope should the PRD cover?

#### Answer

Handle the MVP only: adopt an OpenShift Virtualization VM that already runs in an OSAC-managed namespace and does not require changes to OSAC network or storage features.

#### Impact

Scope the PRD to adoption of a VM that is already compatible with existing OSAC networking and storage capabilities. Existing networking and storage are dependencies, not workstreams to extend; reject incompatible configurations instead of adding functionality to make them fit. This does not waive tenant isolation, correct identity, safe handling of the guest and disk, or verification of existing compatibility.

#### Decision (D34)

The MVP adopts an existing OpenShift Virtualization VM in an OSAC-managed namespace, without changes to OSAC networking or storage features.

---

### R10.Q2: Existing guest disk and Volume support

For the MVP, how should OSAC represent the existing VM disk without changing storage features?

#### Answer

Existing Volume only: require full OSAC Volume support only where existing storage capabilities already provide it; reject incompatible VMs.

#### Impact

Retain the full existing-Volume requirement from D3, D5 and D12 only for configurations supported by existing OSAC storage functionality. Verify that such a configuration actually exists and preserves the original disk; do not implement new storage features, fabricate a Volume or copy the disk. If the prerequisite is unavailable, report the MVP as blocked rather than describing it as delivered.

#### Decision (D35)

Require full OSAC Volume support for the existing disk only where existing storage capabilities already provide it; reject incompatible VMs without changing storage features.

---

### R10.Q3: Post-adoption VM operations

After adoption, how much native-VM operation parity belongs in this MVP?

#### Answer

Same as for any VMaaS VM.

#### Impact

Retain same-release native-VM behavior after adoption, including earlier decisions about authorized lifecycle operations and console. Verify the actual supported operations; this does not authorize changes to OSAC network or storage features or bypass the compatibility gate.

#### Decision (D36)

After adoption, the VM has the same supported operations as other VMaaS VMs in the same OSAC release, without changes to OSAC networking or storage features.

## Round 11 — Terminology

### R11.Q1: Name of the capability

What should the PRD call the process that makes an existing OpenShift Virtualization VM an OSAC ComputeInstance?

#### Answer

Use adoption. Do not change Jira.

#### Impact

Use “VM adoption” for the capability and “adopt an existing VM” for the action throughout the PRD. Validation is a step in adoption; avoid using import, onboarding or migration as synonyms for the adoption process. Jira and raw source requirements remain unchanged.

#### Decision (D37)

The canonical PRD term is VM adoption. Do not update Jira.

## Round 12 — External management

### R12.Q1: Changes outside OSAC after handoff

#### User feedback

External managers should not make changes after adoption. OSAC cannot control that, so assume users do not make such changes.

#### Impact

State the operating assumption explicitly: after handoff, users do not change the VM through another management tool. Do not claim OSAC enforces this assumption. This clarifies D24.

## Clarification exit assessment

- Functional requirements are enumerable: explicit-reference admission, preflight validation, existing-Volume support, native lifecycle/console/metadata parity, requester status and safe retry.
- Personas are identified: authorized Cloud Provider Admins and Tenant Admins request admission; authorized tenant users operate the adopted VM; prior owners coordinate recovery with administrators.
- Scope is explicit: existing VM in an OSAC-managed namespace, tool-independent origin, CLI/API and one qualified path; existing network/storage capabilities only, with no changes to OSAC network or storage features, migration execution or general cluster onboarding.
- Source conflicts are resolved by recorded decisions: post-adoption native deletion/update/force behavior, Volume prerequisite timing, requester roles and origin independence revise the original Jira pilot. The source artifact remains unchanged and Jira has not been updated.
- Assumptions are explicit: intended exclusive management cannot guarantee control of outside actors; no tenant deletion during the MVP.
- Observable safety constraints are concrete: no recreation or extra disk copy during adoption, tenant isolation, unambiguous identity, actionable refusal, idempotent retry, approval before stopping, safe power restoration and preserved guest data on failed adoption.
- Dependencies are identified: supported native capabilities for the same release, full existing-Volume support already provided without storage feature changes, eligible OSAC-managed namespace and existing network/storage capabilities, and a qualified environment with real guest/backend validation.
- Exact implementation choices, capability evidence and lab selection remain design/validation work; they are not evidence of deployed readiness and are not waived by drafting readiness.

## Native capability evidence (local source review)

- `fulfillment-service/docs/COMPUTE_INSTANCES.md` and `docs/guides/developer/computeinstance-resize-guide.md` describe native ComputeInstance resize via InstanceType update, restart signaling, and update constraints. The network attachment is documented as fixed after creation.
- `fulfillment-service/docs/VM_CONSOLE.md` documents serial and VNC console CLI commands and gRPC console transport.
- `proto/private/osac/private/v1/volumes_service.proto` and `fulfillment-service/internal/servers/volumes_server.go` expose Volume list, get, create, update and delete. The server documents metadata-only updates, immutable spec, and block-protocol validation for create.
- These local sources do not demonstrate existing-disk adoption, complete native operation parity, runtime behavior in a selected deployment, or attached-disk retention safeguards. Those remain verification and prerequisite gaps.

## Remaining Design and Validation Work

- Verify native VM and Volume operations and console access for the selected release, including a qualifying existing disk with full Volume support and compatible networking using unchanged OSAC features. Prove data/attachment safeguards and identify prerequisite ownership and availability; report infeasibility if these capabilities do not already exist.
- Select the specific qualified guest, versions, hosting cluster/backend and acceptance evidence; assign lab resources and validation ownership before admission.
- Assess how to detect and respond to conflicting outside changes without claiming OSAC can control external managers; assess cleanup paths without adding a tenant-deletion pilot journey.

## Retained Scope and Design Choices

- Automatic mapping of existing source labels is outside the pilot but remains retained broader OSAC-4661 scope until delivered or explicitly assigned. General existing-cluster import remains broader retained scope as well.
- Required tenant and VM identity remain mandatory. Mention identity options, but leave the identification mechanism to design.
- Full existing-Volume support is a pilot eligibility prerequisite only when already provided by existing OSAC storage capabilities; changing storage features to provide it is outside this MVP.
