# Clarification Log — OSAC-3857

## Status

- Rounds completed: 2
- Outstanding clarification answers: 0
- PRD open questions retained by request: 1
- Exit criteria met: Yes (identifier format remains an explicit open question at the user's direction)

## Round 1 — Scope, coverage, and user-visible behavior

### R1.Q1: Hardware inventory scope

BFX03-01 names chassis, baseboard, network adapters, CPU, and GPU, followed by “etc.” Which additional hardware categories are in scope, if any? The PRD is for BMaaS and its primary resource is BareMetalInstance (BMI); firmware-version inspection for compute nodes and NV switch trays is out of scope.

#### Owner

Feature owner

#### Answer

The PRD is for BMaaS, whose primary custom resource is BareMetalInstance (BMI). BFX03-01 scope is exactly the NVIDIA-defined set: chassis, baseboard, CPU, GPU, and NIC. All other hardware categories are out of scope.

#### Impact

Defines the exact hardware categories and anchors the feature to BMaaS/BMI.

#### Decision (D1)

Only BFX03-01 identifiers for chassis, baseboard, CPU, GPU, and NIC associated with BMaaS/BMI are in scope. Other hardware categories and BFX03-02 firmware inspection are out of scope.

---

### R1.Q2: Backend coverage and unavailable identifiers

All inventory backend implementations are expected to support the five in-scope categories, but some hardware may have no readable serial and backends have different gaps. What should users see when a component exists but has no readable serial? How should backend-specific gaps be documented?

#### Owner

Feature owner

#### Answer

All inventory backends are expected to support returning identifiers for the five in-scope categories when data is available. A serial must not be invented; when no readable serial exists, its identifier field should be empty. Backend-specific gaps should be documented. At the time of this round, whether a component with no readable serial should still be represented and who should receive gap documentation remained open; Round 2 resolves both.

#### Impact

Defines the expected backend coverage, prohibits fabricated values, and requires backend-specific gaps to be documented. Round 2 clarifies that known hardware remains visible without a readable serial and that gap documentation is user-visible for Cloud Provider Admins.

#### Decision (D2)

All inventory backends are expected to support the five in-scope identifier categories when data is available. No serial identifier may be fabricated; when a serial is unavailable or unreadable, its value is empty. Each backend's category coverage and known gaps must be documented for Cloud Provider Admins.

---

### R1.Q3: Identifier representation and audience

BFX03-01 allows stable obfuscated identifiers, while the user stories mention physical inventory and vendor-support correlation. Should Cloud Provider Admins, Cloud Infrastructure Admins, and Tenant Admins see manufacturer serial numbers or stable obfuscated identifiers? Should the representation differ by persona?

#### Owner

Feature owner

#### Answer

The representation need not differ by persona; use a shared representation across personas as an assumption. Whether identifiers are raw or obfuscated remains open and should be carried into the PRD as an open question.

#### Impact

Supports one shared representation assumption across personas. The raw-versus-obfuscated choice remains open for the PRD.

---

### R1.Q4: CLI support

Jira names the UI and gRPC/REST API. Should the OSAC CLI also expose these identifiers? If so, which user-facing CLI workflows should show them?

#### Owner

Feature owner

#### Answer

The OSAC CLI should include identifiers in `osac get baremetalinstance -o yaml` and `osac get baremetalinstance -o json` output. Table output does not need to display them.

#### Impact

Adds YAML and JSON CLI output to the required interfaces; table output is excluded.

#### Decision (D3)

The OSAC CLI returns identifiers in BareMetalInstance YAML and JSON output. The table view omits them.

---

### R1.Q5: Compliance verification

What user-observable evidence should satisfy the compliance-verification item for BFX03-01? Should completion be demonstrated by authorized personas retrieving or viewing the required identifiers for a BareMetalInstance, or is an external compliance review also required?

#### Owner

Feature owner

#### Answer

The NVIDIA AI Cloud Validation Suite provides a BFX03-01 validation. Its requirements matrix lists full coverage; the BFX03-01 issue is marked done and linked to PR #539, and the suite changelog records the check and a break-fix suite with NICo coverage. `isvctl` is the suite's CLI. The OSAC provider configuration still needs to be identified for the eventual run.

#### Impact

The BFX03-01 validation in NVIDIA's AI Cloud Validation Suite is the compliance verification. Run it through `isvctl` using the OSAC provider's break-fix configuration; record the result and any explicit backend capability gaps.

#### Sources

- [NVIDIA AI Cloud Validation BFX03-01 issue #320](https://github.com/NVIDIA/ai-cloud-validation/issues/320) (closed as done, linked to PR #539)
- [NVIDIA AI Cloud Validation test-requirements matrix](https://github.com/NVIDIA/ai-cloud-validation/blob/main/docs/requirements/test-requirements-matrix.adoc) (lists full BFX03-01 coverage)
- [NVIDIA AI Cloud Validation changelog](https://github.com/NVIDIA/ai-cloud-validation/blob/main/CHANGELOG.md) (records BFX03-01 and the break-fix suite)

#### Decision (D4)

Use NVIDIA's BFX03-01 validation from the AI Cloud Validation Suite as the compliance verification, run through `isvctl` with OSAC provider wiring. Capture the validation result and any explicit backend capability gaps.

---

## Round 2 — Missing-component representation and gap documentation

### R2.Q1: Component with no readable serial

When a chassis, baseboard, CPU, GPU, or NIC is present but has no readable serial, should it remain represented in the BMI's hardware inventory with an empty identifier, or should that component be omitted from the returned inventory?

#### Owner

Feature owner

#### Answer

Keep every known component represented even when its serial is unreadable, with an empty identifier. The inventory must make component presence and counts clear: if three NICs are installed but only two serials can be read, it must not report only two NICs.

#### Impact

Preserves component presence and counts independently of serial availability, preventing unreadable identifiers from appearing as missing hardware.

#### Decision (D5)

Represent each known in-scope hardware component even if its identifier is empty, and do not undercount components based on the number of readable serials.

---

### R2.Q2: Backend-gap documentation audience

The PRD will require each backend's coverage and known gaps to be documented. Should this documentation be internal for operators/developers, or should backend limitations also be exposed to API/UI/CLI users?

#### Owner

Feature owner

#### Answer

Backend-specific gap documentation must be user-visible and addressed to Cloud Provider Admins. It must clearly state which hardware information is unavailable when a backend is selected, for example: “If you choose this inventory backend, these hardware identifiers will not be available.”

#### Impact

Ensures Cloud Provider Admins can understand backend-specific inventory limitations before choosing or operating that backend.

#### Decision (D6)

Document each backend's unavailable hardware information in user-visible documentation addressed to Cloud Provider Admins, explaining that selecting that backend means those identifiers will not be available.

---

## Remaining Gaps

- Whether identifiers are raw or obfuscated; the same representation across personas is an assumption. This remains an explicit open question in the PRD at the user's direction.
