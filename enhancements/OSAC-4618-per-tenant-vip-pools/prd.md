# Per-Tenant VAST VIP Pools

| Field       | Value   |
|-------------|---------|
| Author(s)   | Will Gordon |
| Jira        | [OSAC-4618](https://redhat.atlassian.net/browse/OSAC-4618) |
| Date        | 2026-09-22 |

## Problem Statement

OSAC currently routes all tenant storage traffic through a single, shared VAST VIP pool. This shared pool has verified isolation failures:

- **Cross-tenant discovery exposure ([OSAC-4857](https://redhat.atlassian.net/browse/OSAC-4857)):** VIP pools scoped to all tenants expose cross-tenant volume metadata during NVMe-TCP discovery. A tenant running standard NVMe discovery against a shared pool's IP can see other tenants' storage targets. VAST confirmed this is expected behavior for all-tenants-scoped pools: global pools require per-tenant client IP ranges for multi-tenancy, which OSAC cannot provide because tenants have their own VPCs with potentially overlapping IPs.
- **Discovery failures:** The shared pool's all-tenants scoping causes NVMe-TCP discovery to fail entirely (VAST returns `err=6 — No such file or directory`), silently blocking block-storage attach for every tenant onboarded through the shared pool.

The global VIP pool approach ([OSAC-5030](https://redhat.atlassian.net/browse/OSAC-5030)) was moved to backlog because it cannot work without client IP ranges that OSAC is unable to use.

Tenants need dedicated VIP pools so their storage traffic is isolated at the network level, eliminating cross-tenant discovery exposure and providing working NVMe-TCP block-storage connectivity.

## In Scope

- Delivery targets the OSAC 0.3 milestone (Dev Preview).
- Cloud Infrastructure Admins can configure a naming prefix on a VAST storage backend so that OSAC discovers pre-created VIP pools by that prefix.
- During tenant storage onboarding, OSAC automatically selects an available (unbound) pool from the discovered set and binds it to the tenant. The tenant's storage workloads then use that pool's VIP for all block-volume operations. No manual pool assignment is required.
- Pool binding is serialized to prevent two concurrent onboarding operations from claiming the same pool. VAST provides no server-side protection against double-bind (no optimistic locking, no conflict detection), so OSAC must enforce single-writer semantics on its own.
- When no unbound pools remain, tenant storage onboarding fails with a clear status indicating that pool capacity is exhausted, directing the Cloud Provider Admin to contact the Cloud Infrastructure Admin to create additional pools.
- Cloud Infrastructure Admins can see how many VIP pools are total, bound, and available on a storage backend so they know when to provision more.
- The bound pool's connection details are persisted so tenant workloads reach the correct VIP without further manual configuration.
- When a tenant's storage is removed, the bound VIP pool is released back to the available set (stretch goal). Release requires cleaning up associated VAST Views first, because VAST rejects ownership changes on pools that still have Views attached.
- Dev/test tooling for creating sample VIP pools on a VAST cluster.

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

### Cloud Provider Admin

- As a Cloud Provider Admin, I want OSAC to automatically bind an available VIP pool to a tenant during storage onboarding so that the tenant's block volumes are isolated without manual pool assignment.
- As a Cloud Provider Admin, I want a clear status failure when no VIP pools are available during tenant storage onboarding so that I can direct the Cloud Infrastructure Admin to provision additional pools rather than troubleshooting an opaque error.
- As a Cloud Provider Admin, I want a released VIP pool to return to the available set when a tenant's storage is removed so that pools are reused across tenant lifecycles without manual VAST intervention (stretch goal).

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my block-storage workloads to connect through a dedicated VIP pool without any action on my part so that my storage traffic is isolated from other tenants and NVMe-TCP discovery works correctly.

## Assumptions

- Cloud Infrastructure Admins have direct access to VAST VMS to pre-create VIP pools. OSAC does not manage pool lifecycle on the VAST cluster.
- Pre-created pools follow a naming convention that OSAC can match by prefix (e.g., `osac-pool-001`, `osac-pool-002`).
- Each tenant requires exactly one VIP pool.
- Pool count is within VAST's supported cluster-wide limits (~500 pools at 4 IPs/pool).
- VAST's lack of server-side double-bind protection (no optimistic locking, no 409 Conflict) is an acceptable risk for Dev Preview given low concurrent onboarding volume, but must be addressed before GA.

## Dependencies

- **VAST VMS API — query pools by prefix:** OSAC must be able to list VIP pools filtered by a naming prefix. Assumed available based on the VAST VMS REST API.
- **VAST VMS API — update pool ownership:** OSAC must be able to bind a pool to a tenant by updating the pool's tenant association. Confirmed working via testing.
- **VAST VMS API — release pool ownership:** OSAC must be able to release a pool by clearing its tenant association. Confirmed working, with a caveat: VAST rejects the operation if the tenant still has Views on the pool. The release flow must clean up Views before releasing the pool.
- **OSAC-4857 (NVMe-TCP discovery isolation):** Per-tenant VIP pools directly mitigate this verified bug. All-tenants-scoped pools cause NVMe-TCP discovery failures; tenant-scoped pools work correctly.
- **OSAC-5073 (Storage network path):** Defines the network data path between workloads and VIP pools. Parallel work; out of scope for this feature but required for end-to-end storage connectivity.
- **OSAC-5322 (Vendor-config mechanism):** Provides the general-purpose mechanism for per-tenant vendor-specific configuration on the Tenant CR. Required for the deferred per-tenant explicit pool name override capability.
