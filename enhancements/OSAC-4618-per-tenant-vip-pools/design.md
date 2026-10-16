---
title: per-tenant-vip-pools
authors:
  - Will Gordon
creation-date: 2026-09-25
last-updated: 2026-09-25
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4618
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1111-storage-backend"
  - "https://redhat.atlassian.net/browse/OSAC-5322"
  - "https://redhat.atlassian.net/browse/OSAC-4857"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Per-Tenant VAST VIP Pools

## Summary

This enhancement implements a discover-bind model for per-tenant VAST VIP pools. Cloud Infrastructure Admins pre-create named VIP pools in VAST VMS. During tenant storage onboarding, OSAC discovers pools by a configurable naming prefix, binds an unbound pool to the tenant via the VAST API, persists the binding in the Hub Secret, and injects pool identity into CSI StorageClass parameters so tenant NVMe-TCP traffic routes through a dedicated VIP. See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC currently routes all tenant storage traffic through a single shared VAST VIP pool. This causes verified isolation failures:

- **OSAC-4857:** All-Tenants-scoped VIP pools break NVMe-TCP block discovery (`err=6`) because Global VIP Pools require per-tenant Client IP ranges that OSAC cannot use (overlapping tenant VPC IPs).
- **Discovery failures:** The shared pool's all-tenants scoping causes NVMe-TCP discovery to fail entirely, blocking block-storage attach for every tenant.

The earlier supernet-carving approach (OSAC creating pools from an IP block) was superseded. The global VIP pool approach (OSAC-5030) cannot work without Client IP ranges. The discover-bind model shifts pool creation to the Cloud Infrastructure Admin and limits OSAC to discovery and binding at onboarding time.

### Goals

- **G1:** Implement a discover-bind lifecycle in the Ansible onboarding playbook: discover pools by prefix, bind deterministically (alphabetically first available), handle partial-failure safely.
- **G2:** Extend the StorageBackend CRD with `vip_pool_naming_prefix`, validated during reconciliation, with a deletion finalizer to prevent orphaned bindings.

> **Relationship to OSAC-1111 (StorageBackend):** The [OSAC-1111 design](/enhancements/OSAC-1111-storage-backend/design.md) established StorageBackend as a DB-backed entity in the fulfillment-service with no Kubernetes CRD or reconciler. This enhancement does not replace that model. The fulfillment-service DB remains the authoritative source of truth for StorageBackend identity, credentials, and lifecycle state. The osac-operator mirrors a subset of VIP-pool-related fields onto a Kubernetes CRD (`vip_pool_naming_prefix` in spec, `status.vipPools` counters, and the `vip-pool-bound` finalizer) solely to enable controller-based reconciliation and status reporting. The fulfillment-service continues to own the core StorageBackend lifecycle (CRUD, credentials, state machine); the CRD is a projection of operator-managed state, not a competing authority.
- **G3:** Persist binding details (`vip_pool_name`, `vip_pool_fqdn`, `ip_ranges`) in the Hub Secret for operator consumption.
- **G4:** Surface pool utilization (total/bound/available) on StorageBackend status for admin monitoring.
- **G5:** Remove dead code from the superseded supernet-carving approach.
- **G6:** Provide dev/test tooling (`hack/create-vip-pools.yaml`) for creating sample pools.

### Non-Goals

- Automated pool creation or deletion on VAST. OSAC discovers and binds only; Cloud Infrastructure Admins manage pool lifecycle in VAST VMS.
- Pool release or VAST View cleanup on tenant teardown (deferred to post-Dev Preview per decision D3).
- Per-tenant explicit pool name override (deferred to OSAC-5322 vendor-config mechanism).
- Drift detection or reconciliation of pool state against VAST (post-Dev Preview).
- Prometheus metrics for pool utilization (post-Dev Preview; status fields only for Dev Preview).
- File/object storage protocols -- restricted to NVMe-TCP block volumes.

## Proposal

Six components participate in the per-tenant VIP pool lifecycle:

| Phase | Component | Responsibility |
|-------|-----------|----------------|
| Configure | StorageBackend CRD | Stores `vip_pool_naming_prefix` per backend |
| Discover | Ansible `setup.yaml` | Queries `GET /api/vippools/`, filters by prefix and unbound state |
| Bind | Ansible `setup.yaml` | PATCHes `tenant_id` on selected pool via `vastdata.vms.vippools` module |
| Persist | Ansible `setup.yaml` | Writes pool identity and IP ranges to Hub Secret |
| Inject | Operator `applyVipPool()` | Reads Hub Secret, injects `vip_pool_name` into CSI StorageClass params |
| Observe | Operator reconciler | Populates `status.vipPools` counts on StorageBackend |

A seventh change removes dead code from the superseded supernet-carving approach.

```
StorageBackend CR            VAST VMS (external)
  vip_pool_naming_prefix -->  GET /api/vippools/
                              | returns pool list
                              v
                        Ansible setup.yaml
                          DISCOVER (filter by prefix + unbound)
                          BIND (PATCH tenant_id on selected pool)
                          READ (ip_ranges, domain_name from response)
                              |
                              v
                        Hub Secret (vast-tenant-config-<tenant>)
                          vip_pool_name, vip_pool_fqdn,
                          ip_ranges, vast_tenant_id
                              |
                              v
                        Operator (applyVipPool)
                          reads Hub Secret -> injects into
                          CSI StorageClass params
                              |
                              v
                        VAST CSI Node Plugin (tenant cluster)
                          NVMe-TCP discovery via per-tenant VIP
```

**Concurrency model (Dev Preview):** Onboarding operations are serialized globally -- one AAP job at a time across all StorageBackends. VAST has no server-side double-bind protection (no ETags, no 409 Conflict -- Last-Write-Wins), so OSAC must serialize binds. Global sequential execution is sufficient for Dev Preview. Production-grade hardening (optimistic concurrency or distributed lock) is required before GA.

### Workflow Description

**Cloud Infrastructure Admin** pre-creates VIP pools in VAST VMS with a naming convention OSAC can discover (e.g. `osac-pool-`). They set `vip_pool_naming_prefix` on the StorageBackend CR and monitor `status.vipPools` for capacity.

**Cloud Provider Admin** triggers tenant storage onboarding. The storage controller passes the naming prefix as an AAP job extra-var. Ansible discovers pools, binds one, and persists the result. The admin sees binding success/failure via `VipPoolBound` condition on the Tenant CR. On `VipPoolExhausted`, they escalate to the Infrastructure Admin to create more pools.

**Tenant Admin / Tenant User** experience is unchanged. They create PVCs; the CSI driver reads the bound pool's connection details from the Hub Secret. VIP pool binding is invisible to tenants.

**Happy path (Example 1):**

1. Ansible queries `GET /api/vippools/`, filters by prefix, sorts matching pools by name.
2. Checks whether any pool matching the prefix is already bound to this tenant (`tenant_id` matches target). If so, reuses it and skips to step 5 (idempotent retry).
3. Selects the alphabetically first unbound pool (e.g., `osac-pool-002`), binds via `PATCH tenant_id`.
4. Writes `vip_pool_name`, `vip_pool_fqdn`, `ip_ranges` to Hub Secret.
5. Operator detects Hub Secret change, injects pool identity into CSI StorageClass.
6. Tenant PVCs provision through the dedicated VIP pool.

**Pool exhaustion (Example 2):** All matching pools are bound. Ansible fails with `VipPoolExhausted`. Tenant CR condition shows `"0/N VIP pools with prefix 'osac-pool-' are available."` Infrastructure Admin creates more pools; Cloud Provider Admin retries onboarding.

**VAST API failure (Example 5):** VAST VMS unreachable during discovery or binding. Tenant CR condition shows `VastApiUnavailable`. No partial state is left -- safe to retry after VAST recovers.

**Bind timeout with unreachable verification (Example 6):** If the VAST bind PATCH is sent but VAST becomes unreachable before the response is received, the pool may be bound at VAST while no Hub Secret is created. **Identification:** The pool shows `tenant_id` set (bound) in VAST VMS, but no corresponding `vast-tenant-config-<tenant>` Hub Secret exists on the hub cluster. **Recovery:** Re-run the tenant onboarding job -- the idempotent retry detects the pool is already bound to the target tenant, re-persists the Hub Secret, and completes normally. If the tenant is being deleted rather than onboarded, manually unbind the pool in VAST VMS (`PATCH tenant_id: null` on the pool) to release it.

### API Extensions

**StorageBackend CRD -- new spec fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vip_pool_naming_prefix` | string | _(none)_ | Prefix for pool discovery. When set, enables discover-bind for per-tenant VIP pools. When omitted, discover-bind is not activated and shared-pool behavior is retained. Validated non-empty when present. |

**StorageBackend CRD -- new status fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status.vipPools.total` | int | Pools matching prefix (any state) |
| `status.vipPools.bound` | int | Pools with `tenant_id` set |
| `status.vipPools.available` | int | Pools with no `tenant_id` |

**StorageBackend CRD -- finalizer:** `osac.redhat.com/vip-pool-bound` added when `vip_pool_naming_prefix` is set. Blocks deletion while pools matching the prefix are bound to tenants.

**Hub Secret -- new fields:**

| Field | Format | Description |
|-------|--------|-------------|
| `ip_ranges` | `"start-end,start-end"` | Comma-separated dash-delimited IP ranges from the bound pool |
| `vip_pool_bound` | `"true"/"false"` | Whether OSAC bound this pool via discover-bind |

**Tenant CR -- new condition:** `VipPoolBound` (True/False) with reasons: `VipPoolBound`, `VipPoolExhausted`, `VipPoolsNotFound`, `VastApiUnavailable`.

No new OSAC-facing gRPC APIs are introduced.

## UX Alignment

Not applicable. No matching `@temp-api` file exists in `osac-ux/libs/ui-components/src/api/v1/` for VIP pools. VIP pool configuration is an infrastructure-admin concern with no UI surface in Dev Preview.

### Implementation Details/Notes/Constraints

**VAST VMS REST API interactions:**

| Operation | Endpoint | Method | Dev Preview |
|-----------|----------|--------|-------------|
| Discovery | `/api/vippools/` | GET | Yes |
| Binding | `/api/vippools/<id>/` | PATCH (`tenant_id: <int>`) | Yes |
| Release | `/api/vippools/<id>/` | PATCH (`tenant_id: null`) | No (deferred) |

Discovery uses client-side prefix filtering via Jinja2 `startswith` (not regex) because: (a) `vastdata.vms.vippools` has no list capability, (b) server-side prefix filtering is unconfirmed, (c) `startswith` avoids regex-special character issues. `ansible.builtin.uri` is used directly.

**Ansible discover-bind flow (replaces supernet-carving block in `setup.yaml`):**

1. **Discover:** `GET /api/vippools/` -> filter by prefix via `selectattr('name', 'startswith', prefix)` -> sort by name.
2. **Error check:** Zero prefix matches -> `fail` with `VipPoolsNotFound`. All matched pools bound -> `fail` with `VipPoolExhausted`.
3. **Check existing binding:** Before selecting a new pool, check if a pool matching the prefix is already bound to this tenant (`tenant_id` matches target). If so, reuse it and skip to step 6. This ensures idempotency: a retry after a partial failure (e.g., Hub Secret write failed) reuses the already-bound pool rather than binding a second one.
4. **Bind:** `vastdata.vms.vippools` module with `state: present`, setting `tenant_id`. Selection is deterministic: alphabetically first available pool.
5. **Verify on failure:** If bind fails, re-query pool state. If pool is now bound to this tenant (PATCH succeeded despite timeout), adopt and continue. Otherwise fail with diagnostic.
6. **Transform & persist:** Convert VAST `ip_ranges` (array-of-arrays) to Hub Secret format (comma-separated dash-delimited string). Fail if `ip_ranges` is empty.

**Operator changes (`vast_vendor_provisioner.go`):**

- Read `ip_ranges` from Hub Secret; include in CSI params if the VAST CSI driver consumes it. Log warning if empty -- `vip_pool_name` is the critical field.
- Populate `status.vipPools` on StorageBackend during reconciliation by querying VAST.
- Manage `vip-pool-bound` finalizer on StorageBackend CRs that have `vip_pool_naming_prefix` set.

**Prefix validation (operator reconciliation):**

- Reject empty string (matches every pool including infrastructure pools).
- Reject whitespace-only.
- If unset, skip discover-bind entirely and retain shared-pool behavior. The Ansible role default (`osac-pool-`) does not apply to this CRD path; an omitted prefix opts out of per-tenant VIP pools.
- No character restrictions -- prefix is used as literal `startswith`, not regex.

**IP ranges transformation:**

VAST returns: `[["10.100.1.1","10.100.1.4"]]`. Hub Secret stores: `"10.100.1.1-10.100.1.4"`. Performed in Ansible via `map('join', '-') | join(',')`.

**Dead code removal:** Supernet-carving variables (`vast_storage_vip_pool_supernet`, `_slice_size`, `_gw_ip`, `_gw_ipv6`) in `defaults/main.yaml`, the supernet arithmetic block in `setup.yaml`, and the corresponding ConfigMap example vars (`VAST_VIP_POOL_SUPERNET`, `_SLICE_SIZE`, `_GW_IP`, `_GW_IPV6`) are all exclusively consumed by the superseded code path.

**Dev/test tooling:** `hack/create-vip-pools.yaml` creates sample pools on a VAST cluster with configurable prefix, count, and IP ranges. Not a product feature. Naming convention: `<prefix><NNN>` (zero-padded).

### Security Considerations

- **Tenant isolation:** Each tenant gets a dedicated VIP pool scoped by `tenant_id` in VAST. NVMe-TCP discovery returns only volumes accessible through that pool, eliminating cross-tenant discovery exposure (mitigates OSAC-4857).
- **No new credentials:** VIP pool binding uses existing VAST admin credentials stored in StorageBackend's `credentials.secretRef`.
- **Hub Secret scope:** Created on the hub cluster, never leaves it. Tenant clusters receive only CSI StorageClass parameters (pool name, FQDN), not raw credentials.
- **Last-Write-Wins risk:** VAST lacks concurrency protection. A race could silently reassign a pool. Dev Preview mitigates with global serialization. This is a security-critical gap that must be closed before GA (see Risks and Mitigations).

### Failure Handling and Recovery

| Failure Mode | What Happens | Recovery | User Observes |
|-------------|-------------|----------|--------------|
| No pools match prefix | Ansible `fail` with diagnostic | Fix prefix on StorageBackend or create pools in VAST | `VipPoolBound: False`, reason `VipPoolsNotFound` |
| All pools bound | Ansible `fail` with count | Create more pools in VAST VMS | `VipPoolBound: False`, reason `VipPoolExhausted` |
| VAST VMS unreachable | `ansible.builtin.uri` timeout/error | Wait for VAST recovery, retry onboarding | `VipPoolBound: False`, reason `VastApiUnavailable` |
| Bind PATCH timeout | Re-query pool. If bound to this tenant, adopt. If not, fail. | Retry onboarding (idempotent) | Condition updated based on re-query result |
| Orphaned pool (Tenant CR deleted mid-onboarding) | Pool bound on VAST, no Hub Secret | Operator logs warning. Admin manually unbinds in VAST VMS. | Warning in operator logs |
| Hub Secret write fails after successful bind | Pool bound, no consumer | Retry detects pool already bound to target tenant, re-persists Secret | Retry succeeds without binding a second pool |

**Idempotency:** A retried onboarding detects that a pool is already bound to the target tenant and re-persists the Hub Secret rather than binding a second pool.

### RBAC / Tenancy

No RBAC changes. The existing permission model applies:

- **Cloud Infrastructure Admin:** Pre-creates pools in VAST VMS (outside OSAC). Sets `vip_pool_naming_prefix` on StorageBackend CR.
- **Cloud Provider Admin:** Triggers tenant onboarding. Sees pool utilization in StorageBackend status. Sees binding success/failure in Tenant CR conditions.
- **Tenant Admin / Tenant User:** No visibility into pool binding. PVCs provision automatically through the bound pool. VIP pool details are not exposed to tenant-scoped APIs.

### Observability and Monitoring

**Dev Preview (status fields only -- no Prometheus):**

- **StorageBackend status:** `status.vipPools.total`, `.bound`, `.available` -- updated during operator reconciliation by querying VAST.
- **Tenant CR condition:** `VipPoolBound` with status True/False and reason codes.
- **K8s events:** Every VIP pool operation (discover, bind, failure) emits a K8s event on the Tenant CR with operation type, pool count, status/reason, and a non-sensitive pool identifier (pool name). IP ranges and VAST API response bodies are NOT included in K8s events or operator logs because IP ranges can reveal internal network topology.
- **AAP job logs:** The onboarding playbook logs each step -- discovery count, available count, selected pool, bind result, Secret persistence.

**Post-Dev Preview:** Prometheus metrics for pool utilization gauges, proactive low-capacity alerts (`available < 2`), and orphaned pool detection alerts.

### Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| VAST Last-Write-Wins allows silent pool reassignment | High | Dev Preview: global AAP job serialization. GA: optimistic concurrency or distributed lock. |
| Pool exhaustion blocks tenant onboarding | Medium | `status.vipPools.available` lets admins monitor capacity. `VipPoolExhausted` condition provides clear error. |
| Orphaned pools from interrupted onboarding | Low | Operator logs warnings for pools bound to non-existent OSAC tenants. Admin resolves manually for Dev Preview. |
| VAST VMS API unavailability blocks onboarding | Medium | Existing VAST credential/endpoint health monitoring applies. Clear `VastApiUnavailable` condition for diagnosis. |
| Client-side filtering at scale (>500 pools) | Low | VAST supports ~500 pools per cluster. GET response <100KB at capacity. If server-side `?name__startswith=` is confirmed, prefer it. |

### Drawbacks

- **Manual pool management:** Cloud Infrastructure Admins must pre-create pools in VAST VMS and manually release them after tenant teardown (Dev Preview). This adds operational burden compared to fully automated pool lifecycle.
- **Serialization limits throughput:** Global AAP job serialization means one tenant onboards at a time. Acceptable for Dev Preview's low concurrency but must be replaced before GA.
- **No drift detection:** If a pool is manually unbound in VAST while a tenant references it, OSAC does not detect the inconsistency until the next PVC provision fails.

## Alternatives (Not Implemented)

| Alternative | Why Rejected |
|-------------|-------------|
| **Supernet carving** (OSAC creates pools from an IP block) | Superseded. Required OSAC to manage IP allocation arithmetic and pool creation -- complex, error-prone, and unnecessary when admins pre-create pools. |
| **Global VIP pool** (OSAC-5030: all tenants share one pool) | Cannot work. Global pools require per-tenant Client IP ranges; OSAC cannot use these due to overlapping tenant VPC IPs (OSAC-4857). |
| **`vip_pool_strategy` enum** (GLOBAL / DISCOVER_BIND modes) | Dropped as unnecessary complexity. Since the global pool approach cannot work (OSAC-4857), there is no useful second mode. Discover-bind is the only viable strategy, so the presence of `vip_pool_naming_prefix` on the StorageBackend CR is sufficient to activate it -- no strategy selector needed. |
| **OSAC creates pools on-demand** | Out of scope per PRD. Cloud Infrastructure Admins own pool lifecycle. OSAC should not need VAST admin-level pool creation credentials. |
| **Per-tenant explicit pool name** | Deferred to OSAC-5322. Requires the vendor-config mechanism on Tenant CR, which is not yet available. |

## Open Questions [optional]

| # | Question | Owner | Impact |
|---|----------|-------|--------|
| OQ-1 | Does VAST support server-side prefix filtering (`?name__startswith=`)? | Implementer | If yes, reduces payload size for large pool inventories. Client-side filtering works regardless. |
| OQ-2 | Does the VAST CSI driver consume `ip_ranges` from StorageClass parameters, or only `vip_pool_name`? | Implementer | Determines whether `ip_ranges` in CSI params is functional or informational. |
| OQ-3 | Should `schema_version` be added to the Hub Secret for Dev Preview? | Team | Recommended for producer/consumer version detection during rolling upgrades, but not strictly required for single-version Dev Preview. |

## Test Plan

### Unit Tests

- Prefix validation: reject empty, whitespace-only; accept valid prefixes including special characters.
- Pool filtering logic: `startswith` prefix match, `tenant_id == null` available filter.
- Deterministic selection: alphabetically first available pool chosen.
- IP ranges transformation: VAST array-of-arrays format to comma-separated dash-delimited string.
- Hub Secret field population: all expected fields present after binding.
- Status counter calculation: total/bound/available counts from pool list.
- Finalizer management: added when `vip_pool_naming_prefix` is set, removed when all pools released.

### Integration Tests

- Discover-bind lifecycle against a mocked VAST API: discovery, binding, Hub Secret creation.
- Pool exhaustion: all pools bound -> `VipPoolExhausted` condition set on Tenant CR.
- No matching prefix: zero pools match -> `VipPoolsNotFound` condition set.
- Bind timeout recovery: simulate PATCH timeout, verify re-query and adoption.
- Idempotent retry: re-run onboarding for already-bound tenant -> no second binding.
- StorageBackend deletion with bound pools -> finalizer blocks deletion.
- Operator reconciliation updates `status.vipPools` counts.

### E2E Tests

- Full onboarding flow: create StorageBackend with `vip_pool_naming_prefix`, create VIP pools in VAST, onboard tenant, verify `VipPoolBound: True` condition and Hub Secret populated.
- PVC provisioning through bound pool: tenant creates PVC, pod mounts volume, NVMe-TCP traffic routes through dedicated VIP.
- Sequential onboarding of multiple tenants: each gets a distinct pool.
- Pool exhaustion scenario: onboard N+1 tenants with N pools, verify Nth+1 fails with `VipPoolExhausted`.

## Graduation Criteria

**Dev Preview (0.3):**

- Discover-bind lifecycle functional with serialized onboarding.
- StorageBackend status reports pool utilization.
- Tenant CR `VipPoolBound` condition reflects binding state.
- Dead code from supernet-carving removed.
- Manual pool release documented for Cloud Infrastructure Admins.

**GA (future):**

- Concurrency hardening: replace global serialization with optimistic concurrency or distributed lock.
- Automated pool release on tenant teardown (View cleanup + `tenant_id: null`).
- Prometheus metrics for pool utilization with low-capacity alerts.
- Drift detection: operator validates pool state against VAST periodically.
- `schema_version` on Hub Secret for rolling upgrade safety.

## Upgrade / Downgrade Strategy

**Upgrade:** Backends without `vip_pool_naming_prefix` continue using shared-pool behavior. The operator must tolerate missing Hub Secret fields during rolling upgrades: treat absent `ip_ranges` as empty and absent `vip_pool_bound` as `"false"`.

**Downgrade:** If an N+1 cluster with `vip_pool_naming_prefix` set is rolled back to N, the operator ignores the unrecognized `vip_pool_naming_prefix` field. Already-bound pools remain bound on VAST (no release occurs). The Hub Secret's `ip_ranges` and `vip_pool_bound` fields are ignored by the older operator. StorageBackend status may lose the `vipPools` sub-resource on downgrade. Manual cleanup of bound pools in VAST VMS may be needed.

## Version Skew Strategy

- **Operator ahead of Ansible:** The operator tolerates missing `ip_ranges`/`vip_pool_bound` in Hub Secrets written by an older Ansible role. It reads `vip_pool_name` (existing field) as the primary connection parameter.
- **Ansible ahead of operator:** The Ansible role writes `ip_ranges` and `vip_pool_bound` to the Hub Secret. An older operator ignores unrecognized fields. CSI StorageClass creation uses only `vip_pool_name` and `vip_pool_fqdn` (existing contract).
- **CRD version skew:** The new `vip_pool_naming_prefix` spec field is optional. An older operator seeing this field ignores it (standard Kubernetes CRD forward-compatibility). A newer operator against a StorageBackend CR without this field skips discover-bind (no prefix means no per-tenant pools).

**CRD rollout order (deployment requirement):** The updated CRD schema defining `vip_pool_naming_prefix` **must** be installed before the operator version that reads it. If the operator starts before the CRD is updated, it cannot read or watch the new field, and Kubernetes API server validation may reject StorageBackend resources that set it. Conversely, installing the CRD first is safe: older operators use server-side apply or strategic-merge-patch when writing StorageBackend objects, which preserves unknown fields — they do not prune `vip_pool_naming_prefix` because they never replace the full spec object. Standard OLM bundle ordering (CRD → Deployment) satisfies this requirement. Manual (non-OLM) installations must apply the CRD manifest before rolling out the operator Deployment.

## Support Procedures

**Symptom: Tenant PVCs stuck in Pending, VIP pool binding suspected.**

1. **Check Tenant CR condition:**
   ```bash
   oc get tenant <name> -o jsonpath='{.status.conditions}' | jq '.[] | select(.type=="VipPoolBound")'
   ```
   - `reason: VipPoolsNotFound` -- verify `vip_pool_naming_prefix` on StorageBackend, verify pools exist in VAST VMS.
   - `reason: VipPoolExhausted` -- create more pools in VAST VMS.
   - `reason: VastApiUnavailable` -- check VAST VMS health and network path from hub cluster.
   - `reason: VipPoolBound`, `status: True` -- binding succeeded; problem is elsewhere (CSI, network, VAST data path).

2. **Check Hub Secret:**
   ```bash
   oc get secret vast-tenant-config-<tenant> -n <hub-ns> -o json | jq -r '.data | to_entries[] | "\(.key): \(.value | @base64d)"'
   ```
   Verify `vip_pool_name` and `vip_pool_fqdn` are populated.

3. **Check VAST pool state:**
   ```bash
   curl -s https://<vast-endpoint>/api/latest/vippools/ | jq '.[] | select(.name | startswith("<prefix>"))'
   ```
   Verify the pool bound to this tenant has the correct `tenant_id` and `enabled: true`.

4. **Check AAP job logs:** Search for `vippool` or `VIP pool` in the storage onboarding job log to trace discovery, selection, and binding steps.

> **Sensitive data policy:** K8s events on the Tenant CR and operator logs intentionally omit IP ranges, VAST API response bodies, and other network-topology-revealing data. Only pool names, operation types, and counts are included. If IP ranges are needed for diagnosis, inspect the Hub Secret directly (step 2 above) — it is hub-cluster-scoped and access-controlled. Do not add IP ranges or raw API responses to K8s events, log messages, or condition messages.

**Disabling the feature:** Remove the `vip_pool_naming_prefix` field from the StorageBackend CR. New tenant onboardings revert to shared-pool behavior. Existing bindings are unaffected -- already-bound pools remain bound on VAST.

## Infrastructure Needed [optional]

- **Dev/test tooling:** `hack/create-vip-pools.yaml` playbook for creating/deleting sample VIP pools on VAST clusters. Parameters: `pool_count`, `naming_prefix`, `ip_start`, `ips_per_pool`, `subnet_cidr`.
- **VAST VMS access for integration tests:** A test VAST cluster (or mock API) that supports `GET /api/vippools/` and `PATCH /api/vippools/<id>/` for discover-bind testing.
