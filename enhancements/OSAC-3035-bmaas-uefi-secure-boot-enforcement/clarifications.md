# Clarification Log — OSAC-3035

## Status

- Rounds completed: 3
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Core product behavior

### R1.Q1: Enforcement model — where does the secure-boot setting live?

**Question:** Confirm the enforcement model (default always-on unless the
BareMetalInstanceType states otherwise) and who may author an opt-out type.

#### Answer

The user is converging on an attribute-based model and asked for analysis:
does it make sense to put a UEFI secure boot compatible attribute on both
BareMetalInstanceType and DiskImage — such that picking a type that requires
UEFI Secure Boot triggers a check that the disk image has the attribute — or
should the setting belong to the BareMetalInstance spec directly?

#### Impact

The PRD's functional requirements depend on this choice: it determines
whether the feature is expressed as a DiskImage attribute, an instance-type
mandate, a per-instance user preference, or a combination. A three-level
model (image possibility × type mandate × instance preference) was proposed
in response and awaits confirmation (Round 2).

---

### R1.Q2: Verification meaning and tenant-visible surface

**Question:** What should "Secure Boot status verified during provisioning
flow" mean, and where does the tenant see it?

#### Answer

Deferred to the enforcement-model decision ("see the first answer") — the
verification story follows from which model is chosen.

#### Impact

The assurance requirement (Tenant Admin user story) cannot be drafted until
the model is confirmed. A derived proposal (provisioned-with-secure-boot as
verification, plus an instance status indicator) is presented in Round 2.

---

### R1.Q3: Failure handling when a host cannot enable Secure Boot

**Question:** What should happen when a host fails verification or cannot
enable Secure Boot?

#### Answer

Checking at allocation time is fragile because there are no guarantees about
inventory data. The user prefers: fail the provisioning, then use the same
pattern as other filters — quarantine if a mechanism exists, otherwise
return the host to the pool.

Follow-up codebase review found generic allocation protection but no Secure
Boot-specific quarantine mechanism. A failed instance continues to claim its
host until deletion and cleanup; Metal3 and OpenStack also exclude hosts that
are claimed or not available. However, provisioning reports a generic backend
failure and cannot reliably attribute it to the hardware rather than the
DiskImage. The user approved narrowing the requirement to the observable
request outcome instead of requiring host quarantine.

#### Impact

The PRD specifies that provisioning fails, the requester can see the
provisioning error, and the host is not delivered to the tenant. Automatic
failure attribution and Secure Boot-specific host quarantine are explicitly
out of scope.

#### Decision (D1, revised)

If provisioning cannot complete with Secure Boot enabled, the request fails,
the requester can see the provisioning error, and the host is not delivered
to the tenant. Automatic attribution of that failure to hardware versus the
DiskImage, and a Secure Boot-specific host quarantine mechanism, are out of
scope. Generic backend allocation behavior is not a product guarantee of this
feature. This replaces the original D1 quarantine conclusion after the
follow-up review and explicit user approval.

---

### R1.Q4: DiskImage secure-boot compatibility metadata

**Question:** Should the platform know image secure-boot compatibility up
front, given unsigned images cannot boot under Secure Boot?

#### Answer

Yes — attribute plus fail-fast validation.

#### Impact

DiskImage gains a secure-boot compatibility attribute, and BareMetalInstance
creation rejects incompatible image/type combinations with an actionable
error before any host is allocated (the existing architecture-compatibility
validation pattern).

#### Decision (D2)

DiskImage carries a secure-boot compatibility attribute, validated at
BareMetalInstance creation time (fail fast, architecture-check pattern).

---

### R1.Q5: Workload scope and default behavior

**Question:** Which provisioning flows does the always-on default apply to,
given CaaS cluster workers are provisioned as BareMetalInstances too?

#### Answer

The user does not want a situation where the user chose nothing and the
deployment fails because the DiskImage does not support Secure Boot. The
reasoning should be: "default to Secure Boot if the disk image declares it
is possible, unless stated explicitly otherwise by the user."

#### Impact

The default is image-driven rather than unconditionally always-on: the
DiskImage compatibility attribute (D2) drives the default, and an explicit
user statement can override. This supersedes the earlier "always-on unless
the BMIType states otherwise" framing and is being folded into the combined
model proposal in Round 2 (which also reintroduces the type-level mandate
the user raised in R1.Q1).

---

## Round 2 — Attribute model, verification, interfaces

### R2.Q1: Attribute model — what each level means

**Question:** Confirm the three-level model (possibility on DiskImage ×
mandate on BMIType × preference on BMI spec) with the proposed resolution
table.

#### Answer

The user corrected the framing: BMIType is **informative hardware
description**, not a mandate. BMITypes describe the supported bare metal in
the existing pool; an attribute "UEFI Secure Boot: true" means the hardware
supports secure boot. Existing BMIType attributes are informative and are
not verified against real hardware — and should stay that way. Summary per
the user: BMIType is informative for the hardware, DiskImage is informative
for the software, and the BMI spec is the user intention. Default to "on"
when possible, even if the user says nothing.

#### Impact

The PRD expresses the feature as three declarations: a hardware-support
attribute on BareMetalInstanceType (informative, not verified), a
compatibility attribute on DiskImage (informative), and a user-intent field
on the BareMetalInstance spec. There is no provider-side enforcement
mandate; the compliance posture comes from defaults plus create-time
validation rather than a required flag.

#### Decision (D3)

Three-level informative model: BareMetalInstanceType declares whether its
hardware supports UEFI Secure Boot (informative, two values: supported or
not); DiskImage declares whether the image is Secure Boot compatible
(informative); the BareMetalInstance spec carries the user intention.
Default is Secure Boot **on** when possible (hardware supported and image
compatible) even when the user states nothing.

---

### R2.Q2: Verification semantics and feasibility

**Question:** Confirm verification = "provisioned with Secure Boot
requested" plus an instance status indicator, without a Redfish read-back.

#### Answer

The user agrees with "Provisioned = verified + status" but was unsure
whether it is possible across all management implementations.

Codebase finding: both supported host classes (`metal3` and `openstack`)
provision through Ironic, which enables secure boot at deploy time and
fails provisioning when it cannot. The Metal3 path sets it via the
BareMetalHost boot mode; the OpenStack path has an equivalent Ironic
mechanism with different wiring. "Provisioned = verified" is therefore
feasible on both paths; the exact OpenStack wiring is a design-phase
detail.

#### Impact

The PRD can state the assurance story as: an instance that reaches
provisioned state with Secure Boot requested booted with Secure Boot
enabled, and the effective state is visible on the instance status.

#### Decision (D4)

Verification means "instance provisioned with Secure Boot requested";
the effective Secure Boot state is exposed on the BareMetalInstance status
via API and CLI. No boot-time Redfish read-back in this feature.

---

### R2.Q3: BMIType attribute values

**Question:** Should the BMIType attribute be tri-state
(required/default/disabled)?

#### Answer

Two values only: the hardware supports Secure Boot or it does not
(see R2.Q1 — the attribute is informative, never a mandate).

#### Impact

Subsumed by D3: the BareMetalInstanceType attribute is a boolean
hardware-support declaration.

---

### R2.Q4: Interfaces for the new attributes and status

**Question:** Which user-facing interfaces expose the new attributes and
the status indicator?

#### Answer

API + CLI now, UI later.

#### Impact

The PRD scopes the public API and the `osac` CLI for the DiskImage and
BareMetalInstanceType attributes and the instance status indicator;
osac-ui screens are a follow-up.

#### Decision (D5)

API and CLI expose the new attributes and the status indicator in this
feature; UI screens are deferred to a follow-up.

---

### R2.Q5: Edge case — explicit Secure Boot with an incompatible image

**Question:** What happens when the user explicitly requests Secure Boot
but the chosen DiskImage does not declare compatibility?

#### Answer

DiskImages should **always** declare whether they are compatible. If they
are not compatible and the user requests Secure Boot, fail early at
create.

#### Impact

The DiskImage compatibility attribute is required at creation (not
optional metadata), and BareMetalInstance creation rejects an explicit
Secure Boot request paired with an incompatible image before any host is
allocated.

#### Decision (D6)

The DiskImage secure-boot compatibility attribute is declared at creation
for every image. Explicit Secure Boot requests paired with an incompatible
image are rejected at BareMetalInstance creation time.

---

## Round 3 — Migration defaults and remaining edge cases

### R3.Q1: Migration default for existing DiskImages

**Question:** The DiskImage compatibility attribute is required at creation
(D6). What happens to existing DiskImages created before this feature?

#### Answer

Avoid writing a database migration. Treat a missing attribute on an
existing DiskImage as "does not support UEFI Secure Boot" — a defensive
interpretation at read time.

#### Impact

Existing images keep today's boot behavior (Secure Boot off) until their
owner updates the declaration. No migration step, no upgrade disruption.

#### Decision (D7)

No data migration for the new attributes. A missing DiskImage
secure-boot attribute is interpreted as not compatible.

---

### R3.Q2: Migration default for existing BMITypes

**Question:** What is the migration default for existing BMITypes when the
hardware-support attribute is introduced?

#### Answer

Same approach: no migration; a missing attribute is interpreted as false
(hardware does not support Secure Boot).

#### Impact

Existing types keep today's boot behavior until the provider updates the
declaration. No existing deployment changes boot behavior on upgrade.

#### Decision (D8)

No data migration for the new attributes. A missing
BareMetalInstanceType hardware-support attribute is interpreted as not
supported.

---

### R3.Q3: Explicit Secure Boot on unsupported hardware

**Question:** The user explicitly requests Secure Boot, the image is
compatible, but the BMIType declares the hardware does not support it.
What happens?

#### Answer

Reject at create, mirroring the image rule.

#### Impact

Symmetric fail-fast validation: both the image compatibility and the type
hardware-support declarations are checked at BareMetalInstance creation
when Secure Boot is explicitly requested.

#### Decision (D9)

Explicit Secure Boot requests paired with a type whose hardware-support
declaration is false are rejected at BareMetalInstance creation time.

---

### R3.Q4: CaaS worker instances

**Question:** Do CaaS cluster worker BareMetalInstances follow the same
"default on when possible" rule?

#### Answer

Same rule, no special case.

#### Impact

Worker instances provisioned by the CaaS controller are covered by the
same defaults and validation; provider-configured worker OS images declare
compatibility like any other image. No mechanism to distinguish workers is
needed.

#### Decision (D10)

CaaS worker BareMetalInstances follow the same "default on when possible"
rule as tenant-created instances; no special casing.

---

## Remaining Gaps

None. Exit criteria met: functional requirements are enumerable, personas
are identified (Cloud Provider Admin declares types and images; Tenant
Admin sets intent and reads status), scope boundaries are clear (Secure
Boot enable/disable only; TPM measured boot, TPM clearing, Redfish
read-back, automatic failure attribution, Secure Boot-specific host
quarantine, and UI screens are out of scope or deferred), no unresolved
contradictions remain (the Round 1 "always-on" framing was superseded by
D3), key assumptions are confirmed (both host classes provision through
Ironic, which supports deploy-time Secure Boot), non-functional
constraints are enumerable (backward-compatible defensive defaults, E2E
coverage), and dependencies are identified (BMO/Ironic Secure Boot
support in the pinned metal3 API and the OpenStack Ironic path).
