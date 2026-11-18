# Source Decisions and User Direction — OSAC-7894

## User Direction

- Use the BCM and NetBox backend PRDs as structural references.
- Keep the structure close to those PRDs, keep it simple, and use plain language.

## Existing Feature Decisions

The following decisions are explicit in OSAC-7195, rather than new clarification
answers:

- Scope is the first individual-host provisioning, inspection, and
  deprovisioning increment, targeting 0.6.
- Both OSAC DiskImage and BareMetalInstanceType references determine the
  provisioned result through administrator-configured NICo mappings.
- OSAC networking provisioning is disabled. NICo networking lifecycle and policy
  work belongs to OSAC-7351.
- New tenant console workflows are excluded. OSAC administrator and installer
  configuration remains within the delivery scope. The Feature's inclusion of
  Enclave configuration is superseded for this PRD by Revision 2 below.
- Existing drafts and the pilot provide context, not binding requirements or
  architecture. Provider behavior must be verified before support is claimed.

## Revision 1 — 2026-11-18

- Remove all pilot and proof-of-concept references from the PRD.
- Describe the feature's intended outcomes independently of prior work.
- Frame the Problem Statement around making NICo-managed hosts available through
  the existing OSAC workflow.

## Revision 2 — 2026-11-18

- Remove Enclave from the PRD because it is outside the OSAC project's scope.
- Keep OSAC administrator and installer configuration within the PRD scope.
- Any Enclave work can be tracked in the Feature or related Features instead.

## Revision 3 — 2026-11-18

- Keep In Scope focused on the capability this backend adds.
- Consolidate statements about existing references, permissions, errors,
  provisioning status, and tenant isolation into use of the standard BMaaS
  workflow. Apply the same treatment to detailed retry and allocation rules.
- Retain backend configuration, image and hardware mappings, networking-disabled
  operation, automated validation, and documentation as the scope boundaries.
- This simplifies the PRD wording. Detailed validation, readiness, ownership,
  recovery, and tenant-isolation requirements remain source material for design
  and test planning.

## Revision 4 — 2026-11-18

- Remove the Out of Scope bullet grouping bulk host operations, additional
  lifecycle actions, and in-place upgrades.
- Only list exclusions that a reader could reasonably expect this backend
  integration to include. Existing platform limitations do not need repeating.

## Revision 5 — 2026-11-18

- Keep the networking exclusion as a plain scope statement.
- Remove its follow-on tracking sentence and links to Jira and networking
  proposals. Tracking details belong in Jira.

## Revision 6 — 2026-11-18

- Remove the Tenant Admin user story and its heading. It repeats existing
  authorization behavior and introduces no Tenant Admin capability for NICo.
