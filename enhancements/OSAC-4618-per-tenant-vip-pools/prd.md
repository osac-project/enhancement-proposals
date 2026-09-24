# Per-Tenant VAST VIP Pools

| Field       | Value   |
|-------------|---------|
| Feature     | Per-Tenant VAST VIP Pools |
| Jira        | [OSAC-4618](https://redhat.atlassian.net/browse/OSAC-4618) |
| Epic        | [OSAC-4617](https://redhat.atlassian.net/browse/OSAC-4617) — Storage Infrastructure |
| Author(s)   | Will Gordon |
| Date        | 2026-09-22 |

## Problem Statement

OSAC currently routes all tenant storage traffic through a single, shared VAST VIP pool. This shared pool has verified isolation failures:

- **Verified ([OSAC-4857](https://redhat.atlassian.net/browse/OSAC-4857)):** All-Tenants-scoped VIP pools break NVMe-TCP block discovery — discovery fails with `err=6` because Global VIP Pools require per-tenant Client IP ranges, which OSAC cannot use (tenant VPCs have overlapping IPs).
- **Team-reported: Discovery failures.** The shared pool's all-tenants scoping causes NVMe-TCP discovery to fail entirely (VAST returns `err=6 — No such file or directory`), silently blocking block-storage attach for every tenant onboarded through the shared pool.

The global VIP pool approach ([OSAC-5030](https://redhat.atlassian.net/browse/OSAC-5030)) was moved to backlog because it cannot work without client IP ranges that OSAC is unable to use.

Tenants need dedicated VIP pools scoped to a single tenant by VAST, eliminating cross-tenant discovery exposure and providing working NVMe-TCP block-storage connectivity. Network path enforcement between workloads and VIP pools ([OSAC-5073](https://redhat.atlassian.net/browse/OSAC-5073)) is parallel work required for end-to-end connectivity but is not the isolation mechanism — pool-level tenant scoping in VAST is.

## In Scope

- Delivery targets the OSAC 0.3 milestone (Dev Preview).
- Cloud Infrastructure Admins can configure a naming prefix on a VAST storage backend so that OSAC discovers pre-created VIP pools by that prefix.
- During tenant storage onboarding, OSAC automatically selects an available pool from the discovered set and binds it to the tenant. A pool is available when it is unbound and has no attached VAST Views; VAST rejects ownership changes on pools with lingering Views. The tenant's storage workloads then use that pool's VIP for all block-volume operations. No manual pool assignment is required.
- Pool binding must be reliable and idempotent: a retried or resumed onboarding operation must reuse the same pool rather than claiming a second one. The mechanism is deferred to the design EP.
- For Dev Preview, onboarding operations are processed one at a time to prevent two operations from claiming the same pool (see Assumptions for the underlying VAST constraint). GA will support concurrent onboarding with production-grade safeguards.
- When no unbound pools remain, tenant storage onboarding fails with a clear status indicating that pool capacity is exhausted, directing the Cloud Provider Admin to contact the Cloud Infrastructure Admin to create additional pools.
- Cloud Infrastructure Admins can see how many VIP pools are total, bound, and available on a storage backend so they know when to provision more.
- The bound pool's connection details are persisted so tenant workloads reach the correct VIP without further manual configuration.
- When a tenant's storage is removed, the bound VIP pool is released back to the available set (stretch goal). Release requires cleaning up associated VAST Views first, because VAST rejects ownership changes on pools that still have Views attached.
- **Enablement:** Separate non-production tooling for creating sample VIP pools on a VAST cluster, outside the OSAC runtime and lifecycle API, to support development and testing workflows.
- **Cleanup:** Remove unused configuration from the superseded supernet-carving approach that is no longer used under the discover-bind-release model.

## Out of Scope

- OSAC creating or deleting VIP pools on VAST. Cloud Infrastructure Admins pre-create pools directly in VAST VMS; OSAC only discovers and binds them.
- IP address allocation or supernet management. The earlier supernet-carving approach was superseded by the discover-bind-release model.
- File or object storage protocols. This work is restricted to NVMe-TCP block volumes.
- Network path definition between workloads and VIP pools ([OSAC-5073](https://redhat.atlassian.net/browse/OSAC-5073)). Storage network routing is parallel work.
- UI changes for VIP pool management.
- Non-VAST storage backends.
- Per-tenant explicit pool name override during onboarding. This is deferred to the vendor-config mechanism ([OSAC-5322](https://redhat.atlassian.net/browse/OSAC-5322)), which provides a general-purpose approach for per-tenant, vendor-specific configuration.
- Real-time detection of configuration drift on the VAST side (e.g., an admin renaming a pool in the VAST GUI).

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure a naming prefix on a VAST storage backend so that OSAC discovers the VIP pools I pre-created in VAST VMS, without requiring me to register each pool individually.
- As a Cloud Infrastructure Admin, I want to see how many VIP pools are total, bound, and available on a storage backend so that I know when to create more pools before onboarding capacity is exhausted.
- As a Cloud Infrastructure Admin, I want to use provided non-production tooling (outside the OSAC runtime) to create sample VIP pools on a VAST cluster so that I can validate the discover-bind-release workflow without manual VAST VMS setup.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want OSAC to automatically bind an available VIP pool to a tenant during storage onboarding so that the tenant's block volumes are isolated without manual pool assignment.
- As a Cloud Provider Admin, I want a clear status failure when no VIP pools are available during tenant storage onboarding so that I can direct the Cloud Infrastructure Admin to provision additional pools rather than troubleshooting an opaque error.
- As a Cloud Provider Admin, I want a released VIP pool to return to the available set when a tenant's storage is removed so that pools are reused across tenant lifecycles without manual VAST intervention (stretch goal).

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my block-storage workloads to connect through a dedicated VIP pool without any action on my part so that my storage traffic is isolated from other tenants and NVMe-TCP discovery works correctly.

## Assumptions

- Cloud Infrastructure Admins have direct access to VAST VMS to pre-create VIP pools. OSAC does not manage pool lifecycle on the VAST cluster.
- Pre-created pools follow a naming convention that OSAC can match by prefix. The default naming prefix is `osac-pool-` (e.g., `osac-pool-001`, `osac-pool-002`); Cloud Infrastructure Admins may configure a different prefix per storage backend.
- Each tenant requires exactly one VIP pool.
- Pool count is within VAST's supported cluster-wide limits (~500 pools at 4 IPs/pool).
- VAST provides no server-side protection against concurrent pool binding (no optimistic locking, no 409 Conflict). Two simultaneous bind requests both succeed — last-write-wins. For Dev Preview, this is mitigated by processing onboarding operations one at a time (low concurrent volume is expected). Duplicate bindings are not accepted at any milestone — the serialization guarantee prevents them. Production-grade concurrent-safe binding must be implemented before GA; the mechanism is deferred to the design EP.

## Resolved Questions

These questions were investigated during requirements analysis. Answers are incorporated into the PRD; evidence pointers are preserved here for implementers.

- **P1.Q1: Release via tenant_id=null — Confirmed.** VAST accepts the release (200 OK). Caveat: VAST rejects with 400 if Views remain — "tenant can be modified only if there are no view associated with current tenant". Release flow must clean up Views first.
- **P1.Q2: Concurrent binding (double-bind) — No server-side protection.** See Assumptions for the constraint and mitigation approach.

## Dependencies

- **VAST VMS API — query pools by prefix:** OSAC must be able to list VIP pools filtered by a naming prefix. Assumed available based on the VAST VMS REST API.
- **VAST VMS API — update pool ownership:** OSAC must be able to bind a pool to a tenant by updating the pool's tenant association. Confirmed working via testing.
- **VAST VMS API — release pool ownership:** OSAC must be able to release a pool by clearing its tenant association. Confirmed working, with a caveat: VAST rejects the operation if the tenant still has Views on the pool. The release flow must clean up Views before releasing the pool.
- **OSAC-4857 (NVMe-TCP discovery isolation):** Per-tenant VIP pools directly mitigate this verified bug. All-tenants-scoped pools cause NVMe-TCP discovery failures; tenant-scoped pools work correctly.
- **OSAC-5073 (Storage network path):** Defines the network data path between workloads and VIP pools. Parallel work; out of scope for this feature but required for end-to-end storage connectivity.
- **OSAC-5322 (Vendor-config mechanism):** Provides the general-purpose mechanism for per-tenant vendor-specific configuration on the Tenant CR. Required for the deferred per-tenant explicit pool name override capability.
