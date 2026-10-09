---
title: cluster-upgrade-caas
authors:
  - vemporop@redhat.com
creation-date: 2026-09-22
last-updated: 2026-10-06
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1415
prd:
  - "prd.md"
see-also:
  - "../OSAC-1269-cluster-version-api/design.md"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Cluster Upgrade — CaaS

## Summary

This design enables tenants to upgrade HyperShift Hosted Control Plane (HCP) clusters through OSAC. Phase 1 supports independent, sequential control-plane and node-pool upgrades, with progress and history. Later phases add a cancellation window, upgrade channels and risk review, and operational visibility. See the [PRD](prd.md) for requirements and the [Phase 1 design](design-phase1.md) for the first phase's technical decisions.

## Motivation

OSAC provisions HCP clusters but has no supported way to upgrade them. Direct changes to HyperShift resources do not persist because OSAC reconciles the cluster's desired state. Upgrades therefore need to be expressed through the OSAC `Cluster` resource.

### Goals

- Let tenants initiate and monitor control-plane and node-pool upgrades through the API, CLI, and UI.
- Validate target versions and prevent concurrent upgrades.
- Surface control-plane and node-pool upgrade progress and history on the `Cluster` resource in Phase 1.
- Add upgrade graph integration, risk review, a cancellation window, and attention-state visibility (including fleet-level) in later phases.

### Non-Goals

- Rollback or downgrade.
- Cancel an upgrade after HyperShift has started it.
- SNO or non-HCP clusters.
- Platform-initiated upgrades.

## Proposal

Tenants request an upgrade by changing the desired control-plane or node-pool version on `Cluster`. OSAC validates the request and applies the selected release image to the existing HyperShift resource. HyperShift performs the upgrade, and OSAC reports its progress on `Cluster`.

### Phase 1 — Independent upgrades

The control plane and each node pool can be upgraded separately, one operation at a time. OSAC validates version eligibility and skew, reports progress and history for both targets, and supports upgrades through the API, CLI, and UI. OSAC records each terminal control-plane or node-pool attempt in history using AAP and HyperShift feedback. The [Phase 1 design](design-phase1.md) specifies the API and component behavior.

### Phase 2 — Channels and risk acknowledgment

Phase 2 adds upgrade channel management and conditional-update risk review, and explicit acknowledgment. Its API and behavior belong in a Phase 2 design.

### Phase 3+ — Operational polish

Later phases address the cancellation window, per-cluster attention states for version divergence and end-of-life support, and fleet-level visibility. Their decisions belong in their respective phase designs.

---

## Provenance

Authored: draft @ design 0.11.1 - f1d6a4b, workspace main @ b14c881c5 (dirty)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ 9c26507ef

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"9c26507ef","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
