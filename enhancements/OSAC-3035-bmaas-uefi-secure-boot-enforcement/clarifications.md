# Clarification Log — OSAC-3035

## Status

- Rounds completed: 5
- Open product-requirement gaps: 0
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
requested" plus an instance status indicator, without an independent
firmware read-back.

#### Answer

The initial answer used "provisioned with Secure Boot requested" as the
verification boundary and required the same outcome across all supported
management implementations. Round 5 strengthened this boundary: the backend
must confirm Secure Boot before tenant-image boot, and successful provisioning
alone is insufficient without that confirmation. Current dependency or
implementation limitations do not reduce the requirement.

Follow-up evidence distinguishes the backend mechanisms and the limits of
what provisioning can prove:

- A Metal3 maintainer confirmed on 2026-11-05 that BMO and Ironic perform no
  pre-flight check that the hardware can toggle Secure Boot and do not inspect
  target-image signatures. BMO rejects BMC driver types that declare no Secure
  Boot support, and Redfish setting errors or confirmation timeouts fail.
  However, when the Redfish endpoint lacks the `SecureBoot` resource, Ironic's
  automatic deployment path logs an unsupported-operation warning and can
  continue. The design must close this gap before tenant-image boot.
- An unsigned image is not rejected before deployment. Firmware may reject it
  only when attempting to boot, consistent with the image declaration being
  informative and not independently verified by OSAC.
- For the OpenStack path, the pinned `python-ironicclient` exposes Ironic's
  standalone Secure Boot state API. The design must invoke that API before the
  existing wait-for-active deployment. An API error fails the invoking task;
  the deployment wait also fails when Ironic reports a failed provision state
  or `last_error`. The current OSAC task does not yet wire this call, and exact
  task wiring plus real-provider validation belong in the design and test plan.

#### Impact

The PRD retains the full assurance contract: every supported backend must
apply and confirm Secure Boot before tenant-image boot, fail provisioning when
it cannot, and expose the completed outcome. Tenant-visible verification is
reported only after successful provisioning, but successful provisioning
without the pre-boot confirmation does not satisfy the requirement. This is
not post-provision firmware attestation, image-signature inspection, or proof
that the guest operating system booted. Backend wiring and validation gaps are
design constraints, not reductions of the product requirement.

#### Decision (D4, revised)

Every supported backend must confirm Secure Boot is enabled before the first
boot attempt from the tenant-selected DiskImage and treat inability to apply
or confirm it as a provisioning failure. The effective outcome is exposed via
API and CLI only after successful provisioning. This feature does not add
post-provision runtime firmware attestation, cryptographic image verification,
or guest-boot attestation.

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

## Round 4 — Pre-allocation declaration validation

### R4.Q1: What FR-4 validates before host allocation

**Question:** Can FR-4 validate Secure Boot compatibility before a physical
host has been allocated, and what does an incompatible declaration mean?

#### Answer

Before host allocation, OSAC validates only the declarations on the selected
BareMetalInstanceType and DiskImage. A type declaration that says its hardware
does not support Secure Boot, or an image declaration that says the image is
not Secure Boot compatible, blocks an explicit request to enable Secure Boot.
A missing declaration also blocks explicit enablement under the established
legacy defaults.

This does not mean that OSAC has determined a declaration is factually false.
For example, a resource may declare support even if the eventual hardware or
image does not work in practice; declaration accuracy is not independently
verified at create time.

#### Impact

FR-4 must describe unsupported, incompatible, or missing declaration values
instead of referring to a declaration as "false," which could be read as
detecting inaccurate information. Host-specific checks cannot occur until a
host has been allocated and remain provisioning design and test work.

#### Decision (D11)

FR-4 performs declaration-only validation before host allocation. An explicit
request to enable Secure Boot is rejected when the selected
BareMetalInstanceType declares its hardware unsupported, the selected
DiskImage declares itself incompatible, or either required declaration is
missing. This validation does not verify the declarations against the eventual
host or image contents.

---

### R4.Q2: Rejection message

**Question:** What must the requester be told when create-time declaration
validation rejects explicit Secure Boot enablement?

#### Answer

The rejection message explains why the request cannot proceed and identifies
each selected resource whose declaration says Secure Boot is unsupported,
incompatible, or missing. It does not need to discover or enumerate other
resources as alternatives.

#### Impact

FR-4 requires an actionable explanation of the selected resources' blocking
declarations without promising catalog-wide alternative discovery.

#### Decision (D12)

The create-time error identifies each blocking BareMetalInstanceType or
DiskImage declaration and explains why explicit Secure Boot enablement was
rejected. It does not promise to list compatible alternatives.

---

## Round 5 — Pre-boot enforcement and failure handling

### R5.Q1: Which operating system is protected by the pre-boot gate?

**Question:** Does the requirement that an operating system must not start
before Secure Boot is confirmed apply to the tenant-selected DiskImage, while
allowing trusted inspection or provisioning environments to run beforehand?

#### Answer

Yes. The protected boundary is the first boot attempt from the
tenant-selected DiskImage. Trusted inspection or provisioning environments
may run earlier as required by the backend.

#### Impact

The PRD can require a pre-boot gate without prohibiting the provisioning
ramdisks used by supported backends.

#### Decision (D13)

When Secure Boot is effective, the backend must confirm that it is enabled
before the first boot attempt from the tenant-selected DiskImage. This gate
does not prohibit trusted inspection or provisioning environments.

---

### R5.Q2: Failure behavior and fallback

**Question:** What happens when Secure Boot cannot be enabled or confirmed,
and may OSAC retry automatically with Secure Boot disabled?

#### Answer

The request fails closed without starting the tenant OS. OSAC does not retry
automatically with Secure Boot disabled. A tenant who still wants the bare
metal resource may submit a new request that explicitly disables Secure Boot.
The same behavior applies when Secure Boot is enabled explicitly or selected
by the default.

#### Impact

The original failure remains visible instead of being hidden by an insecure
automatic fallback. Tenant choice remains available through a separate,
explicit request, and the platform does not need retry orchestration for this
feature.

#### Decision (D14)

Secure Boot enablement and confirmation fail closed for both explicit and
default-on requests. OSAC never retries the request automatically with Secure
Boot disabled; the tenant may explicitly submit a separate disabled request.

---

### R5.Q3: Failure attribution and provider visibility

**Question:** Must OSAC identify whether an inaccurate hardware or image
declaration caused the failure, and is a separate Cloud Provider Admin failure
reporting capability required?

#### Answer

No separate provider-reporting requirement is needed. Existing provisioning
errors can surface the reason supplied by the backend when one is available.
OSAC can distinguish an enablement or confirmation failure before tenant-image
boot from a later provisioning failure, but it cannot always determine the
underlying cause. After Secure Boot is confirmed, an image may fail because
firmware rejected its boot chain or because of an unrelated image or
provisioning problem.

#### Impact

The feature does not promise automatic attribution to an inaccurate
BareMetalInstanceType or DiskImage declaration. It preserves available backend
diagnostics without introducing notifications, mandatory provider-specific
error classification, or quarantine behavior.

#### Decision (D15)

OSAC surfaces available backend provisioning errors through existing
mechanisms but does not guarantee hardware-versus-image or Secure
Boot-versus-unrelated failure attribution. No separate provider-visible
failure capability is introduced by this feature.

---

### R5.Q4: Confirmation trust boundary

**Question:** Is successful provider or BMC confirmation that Secure Boot is
enabled sufficient for the pre-boot gate, while independent signature checks
and post-boot attestation remain outside the feature?

#### Answer

Yes. If Secure Boot is enabled and the firmware trust configuration operates
correctly, firmware prevents an untrusted boot chain from progressing. The
confirmation does not independently prove which keys are enrolled, inspect
the DiskImage signatures, or attest the running guest.

#### Impact

The design must obtain provider or BMC confirmation before tenant-image boot,
but the feature does not add duplicate cryptographic verification or runtime
attestation.

#### Decision (D16)

Provider or BMC confirmation is the pre-boot trust boundary. DiskImage
signature inspection, firmware-key validation, and post-boot guest attestation
remain outside this feature.

---

## Remaining Gaps

None at the product-requirement level. Exit criteria met: functional
requirements are enumerable, every affected persona has defined declaration,
intent, and visibility behavior, and scope boundaries are clear (Secure Boot
enable/disable only; TPM measured boot, TPM clearing, post-provision runtime
firmware attestation, automatic failure attribution, Secure Boot-specific host
quarantine, and UI screens are out of scope or deferred). No unresolved
product contradiction remains. Backend-specific wiring and real-provider
validation remain mandatory design and test work; they do not reduce the
cross-backend requirement.
