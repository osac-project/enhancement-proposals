---
title: OSAC-4500 Quota Foundation Test Plan
last-updated: 2026-11-24
---

# Test Plan — OSAC-4500 Quota Foundation

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 18

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Quota pricing and limit resolution

#### TC-U-01: The registry prices stored resource usage by project

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota annotations](design.md#quota-annotations-declare-the-price)
- **Dependencies:** Real PostgreSQL test container and the usage counter. The harness inserts
  synthetic resource rows and omits the API server, admission and provider.
- **Execution:** `fulfillment-service/internal/quotausage/counter_test.go`
- **Evidence:** `TestQuotaUsage / counts each dimension per project, priced by the registry` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/quotausage/counter_test.go)).
- **Selector:** `go test ./internal/quotausage -run '^(TestQuotaUsage)$' -ginkgo.focus='counts each dimension per project, priced by the registry'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Seed the registry-priced fixture for tenants `acme` and `other`, with acme’s
default and `team` projects, linked children and uncreated requests.

1. Count acme usage and compare the full per-project maps.
2. Count usage for the other tenant.

**Expected results.** The default project reports 8 vCPUs, 32 GiB memory, 3 volumes, 300 fast and 50 slow
GiB, 2 ExternalIPs and one image. Team reports 8 vCPUs, 32 GiB memory, 4 A100 GPUs, one control
plane, three metal-1tb hosts, two ExternalIPs, one NATGateway and one VirtualNetwork. The other
tenant reports only its own 6 vCPUs and 24 GiB memory.

#### TC-U-02: A cluster counts the larger of requested and countable hosts

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Larger-of
  rule](design.md#quota-counts-the-larger-of-what-is-asked-for-and-what-exists)
- **Dependencies:** Real PostgreSQL test container and the usage counter. The harness inserts
  synthetic resource rows and omits the API server, admission and provider.
- **Execution:** `fulfillment-service/internal/quotausage/counter_test.go`
- **Evidence:** `TestQuotaUsage / counts the larger of the parent's ask and its countable children` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/quotausage/counter_test.go)).
- **Selector:** `go test ./internal/quotausage -run '^(TestQuotaUsage)$' -ginkgo.focus='counts the larger of the parent'"'"'s ask and its countable children'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use a `metal-1tb` node set in the PostgreSQL parent-counting fixture with
requests for 3, 1 or 0 hosts and zero or two stored children.

1. Count before any children, with two children under a request for three, and with two children
   over a request for one.
2. Remove the node set while leaving the host rows and count again.

**Expected results.** Total and parent excess are (3,3), (3,1), (2,0), and (2,0) after the removal fixture,
respectively. Existing hosts continue to count on their own.

#### TC-U-03: An override replaces a default and a stored zero default resolves

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Limit resolution](design.md#limits)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/quota_servers_test.go`
- **Evidence:** `TestServers / resolves the limits and counts the usage + resolves a default of zero, which the stored document omits` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/quota_servers_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='resolves the limits and counts the usage|resolves a default of zero, which the stored document omits'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use tenant default 10 and tenant override 5 for `compute.vcpus`, one stored VM
requesting a 6-vCPU type, plus the separate zero-default test with one DiskImage.

1. Read QuotaUsage for the fixture with the tenant override.
2. Query the DiskImage fixture with the `images.count` zero default whose stored JSON omits the value.

**Expected results.** The override yields limit 5 and usage 6. A configured zero default yields limit 0 and
usage 1.

#### TC-U-04: The quota registry rejects unlisted kinds and prices an exempt Subnet at zero

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Quota invariants](design.md#rules-that-always-hold)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `proto/quota/quota_test.go`
- **Evidence:** `TestKindsRejectsUnlistedKind + TestPriceKindThatUsesNothing` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/proto/quota/quota_test.go)).
- **Selector:** `go test ./quota -run '^(TestKindsRejectsUnlistedKind|TestPriceKindThatUsesNothing)$'` from `proto` in osac. Not run for this backfill.

**Preconditions.** Use a synthetic resource descriptor named `RatedResource` and a real Subnet
proto, a kind on the quota exemption list.

1. Build the registry with no quota annotation on RatedResource.
2. Add the fixture’s `test.count` annotation and load it again.
3. Price an empty Subnet.

**Expected results.** The first registry load rejects RatedResource by name. The annotated descriptor loads
successfully. The Subnet price has zero dimensions and zero planned creates.

#### TC-U-05: The request pricer quotes annotated resources and their planned children

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Full request
  pricing](design.md#the-check-computes-the-full-price-after-the-fill-in)
- **Dependencies:** Real registry and pricer with in-memory type lookups and prepared protos. No
  server request fill-in, database or provider.
- **Execution:** `proto/quota/quota_test.go`
- **Evidence:** `TestPriceComputeInstance + TestPriceCluster + TestPriceBareMetalInstance + TestPriceVolume + TestPriceSimpleKinds` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/proto/quota/quota_test.go)).
- **Selector:** `go test ./quota -run '^(TestPriceComputeInstance|TestPriceCluster|TestPriceBareMetalInstance|TestPriceVolume|TestPriceSimpleKinds)$'` from `proto` in osac. Not run for this backfill.

**Preconditions.** Use the source fixtures for a VM with 8 vCPUs, 32 GiB memory, two A100 GPUs and
three disks, a cluster requesting three hosts, a standalone host, a 500 GiB fast Volume, and the
four simple metered kinds.

1. Price the VM, cluster and host with their automatic children configured.
2. Price the standalone Volume, ExternalIP, NATGateway, VirtualNetwork and DiskImage.

**Expected results.** The VM quote has 8 vCPUs, 32 GiB memory, two A100 GPUs, 150 fast GiB, 200 archive GiB,
three planned Volumes and one planned ExternalIP. The cluster quote has one control plane, three
hosts and two addresses. The standalone host adds one host and its requested address. The Volume
quotes one volume and 500 fast GiB. Each simple kind quotes one of its own dimension and plans no
children.

#### TC-U-07: VM request pricing takes the larger of requested and running sizes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Larger-of
  rule](design.md#quota-counts-the-larger-of-what-is-asked-for-and-what-exists)
- **Dependencies:** Real pricer and in-memory type lookup. No fulfilled DB rows, request admission
  or provider.
- **Execution:** `proto/quota/quota_test.go`
- **Evidence:** `TestPriceLargerOf` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/proto/quota/quota_test.go)).
- **Selector:** `go test ./quota -run '^(TestPriceLargerOf)$'` from `proto` in osac. Not run for this backfill.

**Preconditions.** Use type lookup fixtures small (2 vCPUs, 4 GiB) and large (6 vCPUs, 16 GiB).

1. Price a large request with no running type.
2. Price a request to shrink to small while still running large, then when both types are small.
3. Price a request to grow to large while still running small.

**Expected results.** vCPU and memory tuples are (6,16), (6,16), (2,4) and (6,16) respectively.

#### TC-U-06: A counted dimension with no default or override resolves to zero

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Limit resolution](design.md#limits)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Gap:** The explicit stored-zero default is covered. An isolated no-default/no-override case with
  a counted dimension is unresolved.

**Preconditions.** Seed one DiskImage and remove both tenant override and default for `images.count`.

1. Read QuotaUsage for the tenant.
2. Compare the counted dimension with a second read after adding a default of 2.

**Expected results.** The first report shows limit 0 and usage 1. The second shows limit 2 and usage 1.

## Quota enforcement and warnings

#### TC-I-01: Quota rejects over-limit creates and updates without writes

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota API](design.md#api-extensions) and [Design — Quota
  invariants](design.md#rules-that-always-hold)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Use the
  actual checked write transaction.
- **Gap:** Quota table, usage API and limit resolution specs exercise their own boundaries.
  Enforcement and its no-write assertions are unresolved.

**Preconditions.** Use separate tenant- and project-binding fixtures. Set the binding limit to
4 vCPUs and the other limit to 10. Seed usage 3 at the binding scope and prepare a request that
adds 2 vCPUs.

1. Submit a checked VM Create, an expanding Update and a dry-run Create in the applicable fixtures.
2. Read the persisted resources, usage and outbox after each rejected request.

**Expected results.** Each operation returns FailedPrecondition with ErrorInfo reason `QUOTA_EXCEEDED` and
details naming limit 4, usage 3 and delta 2. Requests leave resource and outbox rows unchanged.

#### TC-I-02: Two requests cannot claim the last vCPU

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota invariants](design.md#rules-that-always-hold) and [Design — Tenant
  lock](design.md#one-request-per-tenant-at-a-time)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Use two
  real concurrent PostgreSQL transactions.
- **Gap:** The existing default-limit insert race tests uniqueness on another API. The last-vCPU
  admission race is unresolved.

**Preconditions.** Set tenant capacity 3 vCPUs, existing usage 2, and two filled-in 1-vCPU requests
for different resources.

1. Release both Creates concurrently in separate transactions.
2. Read both results and recount committed usage.

**Expected results.** Exactly one Create succeeds, the other returns FailedPrecondition with
`QUOTA_EXCEEDED`, and committed usage is 3 vCPUs.

#### TC-I-03: Checked quota writes use READ COMMITTED

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Isolation and tenant lock](design.md#one-request-per-tenant-at-a-time)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Use the
  real lock and PostgreSQL snapshot semantics.
- **Gap:** No equivalent test was identified for isolation and post-lock visibility on the admission
  path.

**Preconditions.** Use the checked-request harness with PostgreSQL and instrument the connection
used to acquire the tenant lock and count.

1. Start a checked write and query `SHOW transaction_isolation` in its transaction.
2. Have a competing transaction commit a resource before the checked request acquires the same
   tenant lock, then record the counted usage.

**Expected results.** Isolation reports `read committed` and the post-lock count includes the committed resource.

#### TC-I-04: Concurrent cluster and VM creates share a subnet without deadlock

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Lock ordering](design.md#one-request-per-tenant-at-a-time)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Use real
  PostgreSQL locks. Provider provisioning is omitted.
- **Gap:** Resource-specific lock order specs do not exercise these two checked Creates and their
  shared quota lock. The combined race is unresolved.

**Preconditions.** Provide one tenant, project, subnet and sufficient quota for a cluster and VM.
Give both requests that subnet.

1. Release Clusters/Create and ComputeInstances/Create concurrently.
2. Wait at most 30 seconds for both, then read the stored resources.

**Expected results.** Both calls succeed within 30 seconds, with one persisted resource of each kind using
the intended subnet.

#### TC-I-05: Crossing a threshold on a checked write enqueues one warning

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Warning crossings](design.md#warnings)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. The
  notifications delivery service is omitted because the assertion is on the outbox.
- **Gap:** Threshold CRUD and outbox table tests do not exercise warning generation in checked
  writes. The crossing and repeat assertions are unresolved.

**Preconditions.** Set a 10-vCPU limit and threshold 80%. Seed usage 7 and supply a 1-vCPU Create
request.

1. Submit the Create and inspect committed `quota_outbox` rows.
2. Submit another allowed 1-vCPU Create from usage 8 and inspect the outbox again.

**Expected results.** The first write and one 80% warning commit together. The second does not enqueue
another warning for the same threshold.

#### TC-I-10: Limit and threshold changes enqueue warnings on crossing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Warning crossings](design.md#warnings)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. Use the
  real quota outbox and no notifications provider.
- **Gap:** The current mutation tests assert returned values or rejection. Re-evaluation and outbox
  writes after limit or threshold mutation are unresolved.

**Preconditions.** Use two independent tenants with usage 4 vCPUs, limit 10 and threshold 80%.

1. Lower one tenant’s limit to 5.
2. On the other tenant lower its threshold from 80% to 40%.
3. Inspect committed outbox rows and repeat each update.

**Expected results.** Each first mutation produces exactly one warning for its dimension and scope.
Repeating the same value adds no warning.

## QuotaUsage and threshold APIs

#### TC-I-06: QuotaUsage reports tenant and project limits and usage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota API](design.md#api-extensions) and [Design — Limit
  resolution](design.md#limits)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/quota_servers_test.go`
- **Evidence:** `TestServers / resolves the limits and counts the usage + resolves a project's limit through its nearest ancestor` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/quota_servers_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='resolves the limits and counts the usage|resolves a project'"'"'s limit through its nearest ancestor'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use the quota server fixture with project `team`, its virtual-network limit 3,
the tenant default 2 and one network. Include a nested `team.web` project for the inheritance spec.

1. Call QuotaUsage/Get for the tenant and read the tenant and team rows.
2. Call it again for the inheritance fixture with one network in `team.web` and no local project limit.

**Expected results.** Tenant network limit/usage is 2/1 and team is 3/1 in the first fixture. In the
inheritance fixture team.web reports 3/1 from its nearest ancestor.

#### TC-I-07: QuotaUsage exposes headroom and over-limit state

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota API](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Gap:** The design requests these observables. The current public API reports limit and usage and
  reserves the names `room` and `over_limit`. No equivalent response-field assertion is possible
  until the contract is reconciled.

**Preconditions.** Set tenant vCPU limit 5 and usage 6. Set team network limit 3 and usage 1.

1. Call QuotaUsage/Get and inspect both dimensions.
2. Compare the API headroom and over-limit indicator against the known usage and limit.

**Expected results.** The tenant vCPU dimension has the over-limit indicator set. The team network dimension
has the indicator unset and headroom 2.

#### TC-I-08: Threshold Update rejects clearing percent and accepts an in-range change

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota API](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/quota_servers_test.go`
- **Evidence:** `TestServers / refuses an update whose mask clears the percent` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/quota_servers_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='refuses an update whose mask clears the percent'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Create a project `team` vCPU limit of 4 and a threshold of 80%.

1. Update the threshold with mask `spec.percent` and no percent.
2. Retry with that mask and percent 60.

**Expected results.** The first Update returns InvalidArgument. The second succeeds and returns 60%.

#### TC-I-09: Threshold Create rejects missing limits and invalid percents

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Quota API](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/quota_servers_test.go`
- **Evidence:** `TestServers / refuses a threshold on a scope with no limit of the dimension + refuses a threshold without a percent, or with one out of bounds` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/quota_servers_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='refuses a threshold on a scope with no limit of the dimension|refuses a threshold without a percent, or with one out of bounds'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use project `team` and dimension `compute.vcpus` before and after creating its
limit of 4.

1. Create an 80% threshold before the limit exists.
2. Add the limit and try omitted percent, 0 and 101 in separate Creates.

**Expected results.** The first Create returns FailedPrecondition. Each invalid percent returns InvalidArgument.

## Deployed resource counting

#### TC-E-01: Cluster host usage stays constant while its three hosts provision

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Parent and child
  counting](design.md#quota-counts-the-larger-of-what-is-asked-for-and-what-exists)
- **Dependencies:** Requires real deployed fulfillment, quota API, hub, CaaS/BMaaS controllers and a
  configured host provider. Capacity fixtures must make the provisioning phases observable.
- **Gap:** The PostgreSQL counter table tests requested and persisted child counts. A deployed
  cluster create plus QuotaUsage journey is unresolved.

**Preconditions.** Deploy CaaS and BMaaS with quota enabled. Use an isolated tenant/project with
capacity for exactly three `metal-1tb` hosts and no earlier host usage.

1. Create a cluster with a three-host node set.
2. Read QuotaUsage immediately after the accepted request, during partial provisioning, and after
   three linked BareMetalInstances exist.

**Expected results.** The scoped host dimension increases from 0 to 3 on acceptance and stays at 3 in every
sampled state.
