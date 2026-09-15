# OSAC-1610: NetBox Inventory Backend — Open Questions

This document captures open questions for the NetBox inventory backend implementation.

## Schema Bootstrapping

**Question:** Should the operator auto-create missing custom fields (`osac_instance_id`, `osac_labels`) via POST to `/api/extras/custom-fields/`, or require admin pre-creation?

**Owner:** Architecture decision

**Current design:** Admin pre-creates custom fields; operator validates at startup and fails fast if missing.

**Alternative:** Hybrid flow — a one-time `--bootstrap-schema` CLI mode (or Helm pre-install hook) that creates the fields with elevated permissions, separate from the runtime operator token which only needs device read/write.

**Consideration:** Custom field definitions in NetBox are global to the Device object type (visible on ALL devices in the NetBox instance, not just OSAC-managed ones), so schema modifications carry a wide blast radius. Auto-creation at runtime would also require elevated API token permissions (`extras.customfield.add`), violating least-privilege for the normal operating mode.

**Expected Resolution:**

- Keep admin pre-creation as default; optionally add a `--bootstrap-schema` mode for automated deployments that runs with a separate elevated token and exits after schema setup.

---

## Concurrent Multi-Instance Safety

**Question:** When multiple OSAC operator instances (e.g., different enclaves or HA replicas) share the same NetBox, is ETag-based optimistic locking sufficient, or is an external mutex required?

**Owner:** Implementation task

**Current design:** ETag-based optimistic locking (`If-Match` header on PATCH; 412 Precondition Failed on conflict) provides first-writer-wins semantics for AssignHost and UnassignHost. A 412 response triggers the existing race-loss path (return nil, nil; caller retries with a different device).

**Alternative:** External distributed lock (e.g., Redis advisory lock, database-level locking) for device assignment operations.

**Recommendation:** ETags are lightweight and sufficient for device-level operations. A 412 response is consistent with the existing race-loss contract. An external mutex adds infrastructure complexity (Redis dependency, lock expiry, deadlock risk) without meaningful benefit over optimistic locking for this use case. Reserve external locking for operations that cannot tolerate retry (none identified so far).

---

## NetBox Version Compatibility — CRITICAL: Minor Versions Have Breaking Changes

**Question:** Which specific NetBox versions will be supported? **NetBox does NOT follow semantic versioning** — minor version updates (e.g., 4.6 → 4.7) introduce breaking API changes.

**Owner:** Implementation task; Cloud Infrastructure Admin (testing feedback)

**Critical Breaking Changes in Minor Versions (Real Examples):**

**NetBox 4.7.0 (minor update from 4.6)** contains major API breaks:

- Selection custom field return format changed: `"value"` → `{"value": "x", "label": "X"}`
- Infrastructure dependencies: PostgreSQL 14 dropped (requires 15+), Redis 5.x dropped (requires 6.0+)
- Django upgraded to 6.1 (may affect plugins and integrations)
- Custom field filtering API syntax changed
- Service `protocol`/`ports` fields replaced by `port_mappings` array

**NetBox 4.0.0 (major)** changed:

- `device_role` → `role` field rename
- Token authentication format (v1 → v2)

Decision impacts:

- HTTP client implementation must handle selection field format variations
- Custom field filtering varies by version
- PostgreSQL/Redis version constraints must match target NetBox version
- CI test matrix must cover supported version range (e.g., NetBox 4.3-4.7)
- Documentation must specify exact supported versions

**Expected Resolution:**

- Target specific point releases (e.g., "NetBox 4.3 through 4.7") NOT just "4.x"
- E2E tests run against multiple versions to catch breaking changes
- Implementation maintains version-specific API handling where needed
- Document compatibility matrix clearly (e.g., OSAC 1.0 supports NetBox 4.3-4.7)
