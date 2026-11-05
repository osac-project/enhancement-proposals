# Clarification Log — OSAC-5073

## Status

- Rounds completed: 3
- Open gaps: 1 (listed under Remaining Gaps)
- Exit criteria met: Yes

The Jira text of OSAC-5073 was not readable in this session (no Jira access). The requirement sources
are the author's decisions of 2026-11-05 and the earlier PRD for this issue (EP PR #329, removed in
EP PR #346). The questions below record the author's answers to the open points of that PRD and its
review.

## Round 1 — Scope and approach

### R1.Q1: Vendor and fabric scope

The earlier PRD covered one storage vendor. Should this PRD cover one vendor, or any storage system and
any Fabric Manager?

#### Answer

Any storage system that serves IP storage, and any Fabric Manager that implements the networking
contract. Storage vendor names appear only as examples.

#### Impact

The PRD names no vendor. Fibre Channel storage is out of scope because it is not IP.

#### Decision (D1)

Storage connectivity is storage-vendor agnostic and Fabric-Manager agnostic.

---

### R1.Q2: Path to storage

Should tenant workloads reach storage through a new network path (a storage VLAN or second NIC), or
through the outbound SNAT that a VirtualNetwork's NATGateway already provides?

#### Answer

Through the existing NATGateway SNAT. It is the simplest path and needs no new networking resource.

#### Impact

No new networking resource, capability, or manager task. A dedicated storage network stays with OSAC-6121
and a later phase of OSAC-5073.

#### Decision (D2)

Workloads on a tenant VirtualNetwork reach storage through SNAT by its NATGateway. No new Fabric Manager
capability and no new contract task.

---

### R1.Q3: Where the admin lists storage addresses

The earlier PRD added a new storage CIDR setting. Is a new setting needed?

#### Answer

No. The admin lists storage ranges (data endpoints, VIP ranges, and any storage management endpoint
reachable from tenant networks) in the existing excluded ranges installation setting. Its overlap checks
already exist.

#### Impact

No new setting. The excluded ranges setting is documented as the place for storage ranges.

#### Decision (D3)

Storage ranges go in the existing excluded ranges installation setting. No new storage CIDR field.

---

### R1.Q4: Workloads on a VirtualNetwork without a NATGateway

Should OSAC refuse to create a workload that needs storage on a VirtualNetwork without a NATGateway?

#### Answer

No new gate. Document that a workload needs a READY NATGateway on its VirtualNetwork to reach storage.
Default VirtualNetworks already get one, and Cluster creation already requires one.

#### Impact

The requirement is documentation, plus the existing defaults and the existing Cluster gate.

#### Decision (D4)

Document the NATGateway requirement; add no creation gate.

---

### R1.Q5: Document set

Should the PRD and the design be separate pull requests?

#### Answer

One pull request with both documents, under OSAC-5073.

#### Impact

The PRD and the design are reviewed together.

#### Decision (D5)

One EP pull request holds the PRD and the design for OSAC-5073.

---

## Round 2 — Review of the first draft (2026-11-05)

The author answered these points on 2026-11-05 after reading the first draft of the PRD and the design.

### R2.Q1: Startup check of existing Cluster networks

The first draft extended the fulfillment service startup check to compare excluded ranges with every
Cluster's pod and service networks. Should a rollout fail when a new range overlaps an existing Cluster?

#### Answer

No. The startup check keeps skipping Cluster pod and service networks, as today. The design documents
that before adding a storage range in a later rollout, the admin checks that no existing Cluster's pod or
service network overlaps it, because such a Cluster would silently lose storage.

#### Impact

The startup check change (first-draft IC-2) and its test cases are removed; the documentation interface
change becomes IC-2. FR-4 covers only the existing checks and the documented admin check.

#### Decision (D6)

No startup check of Cluster networks. The admin check of existing Clusters is documented.

---

### R2.Q2: Storage beyond the NAT

Who owns the path after the NATGateway and storage-side access rules, such as keeping address-based rules
in step with NAT addresses?

#### Answer

Assume the NATGateway exists and works. OSAC networking does not manage storage networking; storage is
outside the managed fabric, after the NAT.

#### Impact

OSAC networking's responsibility ends at the NATGateway's SNAT. Routing to storage and storage-side access
control are provider and storage concerns outside this EP. The open question on access-rule ownership,
the PRD risk on stale access rules, and the access-rule test steps are removed. The provider
prerequisites become assumptions outside OSAC networking.

#### Decision (D7)

The path after the NAT and storage-side access control are outside OSAC networking.

---

### R2.Q3: The other two missing CaaS checks

Should the change also add the CaaS design's checks of pod and service networks against the Cluster's
VirtualNetwork CIDR and against ExternalIPPool CIDRs?

#### Answer

No, to keep backward compatibility.

#### Impact

The design lists both as known gaps that are deliberately not added. The excluded-range check at Cluster
create (IC-1) stayed at the time; D10 later drops it too.

#### Decision (D8)

Do not add the other two CaaS checks.

---

### R2.Q4: PRD level of detail

How technical should the PRD be?

#### Answer

The PRD should be non-technical, and the design should contain all the details.

#### Impact

The PRD uses user and business terms only. API names, settings, error codes, commands, and component
names moved to the design.

#### Decision (D9)

The PRD is non-technical; the design holds every technical detail.

---

## Round 3 — Backward compatibility (2026-11-05)

### R3.Q1: The Cluster network check against excluded ranges

The second draft kept one code change (IC-1): a Cluster create or update is rejected when its pod or
service CIDR overlaps a range in the excluded ranges setting. Should that check stay?

#### Answer

No. Drop IC-1. The EP makes no code change; it is documentation only, to keep backward compatibility.

The installation guide tells Netris users to put `10.0.0.0/8` in the excluded ranges setting
(`docs/guides/installation/customer-install-guide.md` in the osac repository, Netris notes). When a Cluster
sets no pod or service CIDR and its ClusterTemplate gives none, the AAP role uses pod `10.132.0.0/14` and
service `172.31.0.0/16`. The default pod network lies inside `10.0.0.0/8`, so the check would reject every
default Cluster create on Netris. Excluded ranges hold more than storage, and only storage ranges need to
stay outside Cluster networks.

#### Impact

- PRD FR-3 becomes a documentation requirement: cluster internal networks must not cover storage; the admin
  and the catalog author choose them, and nothing enforces it.
- The design removes IC-1 from the interface changes and the implementation details; the only interface
  change is IC-2, documentation, which keeps its ID.
- The FR-3 code test cases are removed and replaced by a documentation review (TC-FR3-01).
- The design's known gaps list all three CaaS-design Cluster CIDR checks (against excluded ranges, the
  VirtualNetwork CIDR, and ExternalIPPool CIDRs) as not implemented and deliberately not added.
- The design records that the existing ExternalIPPool-versus-Cluster check assumes wrong defaults
  (`10.128.0.0/14` and `172.30.0.0/16`); this EP does not fix it.

#### Decision (D10)

No Cluster network check. The EP is documentation only; FR-3 is guidance.

---

## Remaining Gaps

- The Jira text of OSAC-5073 was unread while drafting. It targets shared VAST Global VIP Pool connectivity
  with tenant isolation; this document covers only the first phase (near-term connectivity through tenant
  SNAT). A reviewer should confirm that phase boundary adds no requirement.
