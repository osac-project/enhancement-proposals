---
title: per-service-enablement
authors:
  - htayrie@redhat.com
creation-date: 2026-08-26
last-updated: 2026-09-15
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3046
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-3046-per-service-enablement/prd.md"
  - "https://github.com/osac-project/osac/pull/380"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Per-Service Enablement (CaaS/VMaaS/BMaaS/MaaS)

## Summary

This design introduces per-service enablement flags that allow Cloud Provider Admins to select which OSAC services (CaaS, VMaaS, BMaaS, MaaS) are active at installation time via Helm values. Disabled gRPC services are not registered, disabled-service REST calls return HTTP 503 through the gateway, and disabled service controllers are not deployed. The fulfillment-service Capabilities endpoint is extended to advertise enabled services so that clients can adapt their behavior at runtime. See [PRD](prd.md) for detailed requirements.

### Implementation Reconciliation

The current implementation differs from some original design assumptions:

- The authoritative Helm path is `global.services.<service>.enabled`, not
  `services.<service>.enabled`.
- The gRPC server conditionally registers service implementations. The REST
  gateway registers generated handlers for all services; disabled backend calls
  return HTTP 503.
- `fulfillment_disabled_service_requests_total` currently has only the
  `service` label. The startup log reports the enabled list; no disabled-service
  warning log or `method` label is currently emitted.
- HostTypes filtering is supplied by OSAC-4681, which is not in the current
  `main` checkout. The filtering contract below is therefore dependency-gated.
- The operator currently validates the CaaS/compute-controller dependency.
  MaaS has no operator controller; its dependency is enforced by Helm and
  fulfillment-service validation.

## Motivation

OSAC deploys all services unconditionally. A deployment that only needs CaaS still runs BMaaS controllers, registers BMaaS API endpoints, and must satisfy BMaaS-specific compliance controls during audits (e.g., UEFI Secure Boot, TPM 2.0 attestation for bare-metal hosts). This violates NIST SP 800-53 CM-7 (Least Functionality), which requires disabling unnecessary services.

The osac-operator already has per-controller enable flags (`OSAC_ENABLE_CLUSTER_CONTROLLER`, `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER`, etc.) and CI profiles that exercise service-specific configurations (`vmaas-ci`, `caas-ci`, `bmaas-ci`). The current implementation conditionally registers gRPC services, while the REST gateway keeps generated routes registered and returns HTTP 503 when the backend service is disabled. Capabilities provides runtime discovery.

This design closes the gap by adding conditional service registration to the fulfillment-service, extending the Capabilities endpoint, and wiring the Helm chart to propagate a single set of service enablement values across all components.

### Goals

- Reuse the operator's existing per-controller enable flag pattern and the installer's existing component-level `enabled` mechanism rather than introducing a new configuration paradigm.
- Keep configuration changes localized: a single set of Helm values drives all components (fulfillment-service, osac-operator, bare-metal-fulfillment-operator, UI).
- Ensure disabled services produce clear, descriptive errors when accessed — not silent failures or generic "unknown service" messages.
- Support post-installation enablement of additional services via `helm upgrade` without data migration; the affected workloads restart through the normal Helm rollout. [Locked: D4]

### Non-Goals

- Post-installation disablement of services and lifecycle management of existing resources when a service is turned off.
- Compliance scan-profile scoping to enabled services (responsibility of OSAC-3029 and OSAC-3031, which consume the enablement signal this feature provides). [Locked: D3]
- Disabling shared infrastructure (networking, storage, tenants, identity, events). [Locked: D2]


## Proposal

Four service enablement flags — `global.services.caas.enabled`, `global.services.vmaas.enabled`, `global.services.bmaas.enabled`, `global.services.maas.enabled` — are used by the osac-installer Helm chart as the single source of truth. [Locked: D4] The installer propagates these values to the fulfillment-service (as CLI flags), the osac-operator (as environment variables mapped to existing controller flags), and the bare-metal-fulfillment-operator (via the `global.services.bmaas.enabled` dependency condition). All four default to `true`, preserving backward compatibility with existing deployments.

In the fulfillment-service, `services.Flags` groups which services are enabled. The gRPC server conditionally skips registration of services belonging to disabled features. The REST gateway registers generated handlers for all service groups; calls that reach a disabled backend are returned as HTTP 503. A gRPC tap handler maps calls to known-but-disabled services to `codes.Unavailable` with a descriptive message. The Capabilities endpoint is extended with an `enabled_services` field so clients can discover available services without trial and error. [Locked: D3]

HostTypes define the host flavors available for cluster creation (CaaS). Each host type is backed by either BMaaS (bare-metal hosts, identified by having network `interfaces`) or VMaaS (virtual hosts, no `interfaces`). HostTypes is a shared service — always registered — but when a backing service is disabled, its host types are filtered out of List responses so that users only see host types they can actually provision. [Locked: D1]

### Workflow Description

#### Installation with Service Selection

Starting state: A Cloud Provider Admin is installing OSAC and wants only a subset of services.

1. The Cloud Provider Admin edits the Helm values file to set service enablement:

```yaml
global:
  services:
    caas:
      enabled: true
    vmaas:
      enabled: true
    bmaas:
      enabled: false
    maas:
      enabled: false
```

2. The admin runs `helm install osac charts/osac -f values.yaml`.
3. The installer deploys only enabled components:
   - fulfillment-service starts with `--enable-caas`, `--enable-vmaas` — only CaaS and VMaaS gRPC services are registered; disabled REST calls return HTTP 503.
   - osac-operator starts with `OSAC_ENABLE_CLUSTER_CONTROLLER=true`, `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER=true`, `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER=false`.
   - The bare-metal-fulfillment-operator deployment is skipped entirely when `global.services.bmaas.enabled=false`.
4. The admin verifies the deployment by calling the Capabilities endpoint:

```bash
curl --cacert <ca-bundle.pem> \
  https://<public-api-host>/api/fulfillment/v1/capabilities
# Response includes: enabled_services: [caas, vmaas]
```

#### Post-Installation Enablement

Starting state: A running OSAC deployment with CaaS and VMaaS enabled.

1. The admin updates the Helm values file to enable BMaaS:

```yaml
global:
  services:
    bmaas:
      enabled: true
```

2. The admin runs `helm upgrade osac charts/osac -f values.yaml`. [Locked: D4]
3. The fulfillment-service restarts with BMaaS services now registered.
4. The osac-operator restarts with the bare-metal instance controller enabled.
5. The bare-metal-fulfillment-operator deployment is created.
6. The Capabilities endpoint now includes `bmaas` in `enabled_services`.

#### Client Discovery

Starting state: A Tenant User interacting with the OSAC CLI or UI.

1. A client calls `GET /api/fulfillment/v1/capabilities`.
2. The response includes `enabled_services: [caas, vmaas]`.
3. Client-specific hiding or disabling of commands is outside this design's
   current server implementation.

The UI may use the same response to adapt navigation and pages, but that client-side behavior is outside the current server implementation.

#### Inter-Service Dependency Enforcement

Starting state: CaaS enabled, BMaaS disabled, VMaaS enabled.

1. A Tenant User calls `osac get host-types`.
2. The HostTypes service returns only virtual host types (those without network interfaces). Bare-metal host types are filtered out because BMaaS is disabled. [Locked: D1]
3. When creating a cluster, only virtual host types are selectable. Attempting to reference a bare-metal host type in a cluster creation request returns a validation error.

### API Extensions

#### Capabilities proto extension

The `CapabilitiesGetResponse` message is extended with an `enabled_services` field on both the public and private APIs:

```protobuf
message CapabilitiesGetResponse {
  AuthnCapabilities authn = 1;
  repeated string enabled_services = 2;
}
```

The `enabled_services` field contains the lowercase service names that are currently active (e.g., `["caas", "vmaas"]`). This field is populated from the fulfillment-service's startup configuration and is immutable at runtime — changes require a `helm upgrade` and service restart.

No new gRPC services are introduced. No existing resources owned by other teams are modified. The only proto change is the addition of `enabled_services` to the existing `CapabilitiesGetResponse` message.

## UX Alignment

No UX alignment needed — this feature extends the Capabilities response, which has no existing UI type contract.

### Implementation Details/Notes/Constraints

#### Helm Values Structure

New values in `charts/osac/values.yaml`:

```yaml
global:
  services:
    caas:
      enabled: true
    vmaas:
      enabled: true
    bmaas:
      enabled: true
    maas:
      enabled: true
```

All four default to `true` for backward compatibility. The `values.schema.json` is updated with corresponding boolean schema entries with descriptions.

The schema also enforces inter-service dependency constraints:
- CaaS requires at least one of VMaaS or BMaaS to be enabled — CaaS provisions clusters that need compute nodes, which come from either VMaaS or BMaaS.
- MaaS requires CaaS to be enabled — MaaS serves models on clusters provisioned by CaaS.

These constraints are encoded as `if`/`then` rules in `values.schema.json` so that `helm install` and `helm upgrade` fail immediately with a descriptive error when an invalid combination is specified.

The installer propagates these values to each component using the same pattern — individual boolean flags passed as container args or env vars:

| Component | Propagation Mechanism |
|-----------|----------------------|
| fulfillment-service gRPC server | Container args: `--enable-caas`, `--enable-vmaas`, etc. (one flag per enabled service) |
| fulfillment-service REST gateway | Container args: `--enable-caas`, `--enable-vmaas`, etc. (same flags) |
| osac-operator | Env vars: `OSAC_ENABLE_CLUSTER_CONTROLLER`, `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER`, `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER` (already exists) |
| bare-metal-fulfillment-operator | Chart.yaml dependency condition: `global.services.bmaas.enabled` |

```text
                        Helm Values (source of truth)
                ┌──────────────────────────────────────────┐
                │  global:                                 │
                │    services:                             │
                │      caas:  { enabled: true/false }      │
                │      vmaas: { enabled: true/false }      │
                │      bmaas: { enabled: true/false }      │
                │      maas:  { enabled: true/false }      │
                └──────────┬───────────┬───────────┬───────┘
                           │           │           │
          ┌────────────────┘           │           └─────────────────┐
          ▼                            ▼                             ▼
┌──────────────────┐       ┌─────────────────────┐       ┌────────────────────┐
│ fulfillment-     │       │ osac-operator        │       │ bare-metal-        │
│ service          │       │                      │       │ fulfillment-       │
│ (gRPC + REST)    │       │ Env vars (existing): │       │ operator           │
│                  │       │                      │       │                    │
│ CLI args (new):  │       │ OSAC_ENABLE_CLUSTER  │       │ Chart condition:   │
│  --enable-caas   │       │  _CONTROLLER         │       │  dependency =      │
│  --enable-vmaas  │       │ OSAC_ENABLE_COMPUTE  │       │  global.services   │
│  --enable-bmaas  │       │  _INSTANCE_CONTROLLER│       │  .bmaas.enabled    │
│  --enable-maas   │       │ OSAC_ENABLE_BAREMETAL │       │                    │
│                  │       │  _INSTANCE_CONTROLLER│       │ (entire deployment │
│ Controls:        │       │                      │       │  skipped when      │
│  • gRPC service  │       │ Controls:            │       │  false)            │
│    registration  │       │  • Controller        │       └────────────────────┘
│  • REST route    │       │    reconciliation    │
│    registration  │       │    loops             │
│  • HostType      │       └─────────────────────┘
│    filtering     │
│  • Capabilities  │
│    endpoint      │
│  • disabled gRPC │
│    tap handler   │
└──────────────────┘
```

The Helm template for the fulfillment-service deployment passes individual boolean flags, mirroring how the operator subchart passes `OSAC_ENABLE_*_CONTROLLER` env vars:

```yaml
{{- if .Values.global.services.caas.enabled }}
- --enable-caas
{{- end }}
{{- if .Values.global.services.vmaas.enabled }}
- --enable-vmaas
{{- end }}
{{- if .Values.global.services.bmaas.enabled }}
- --enable-bmaas
{{- end }}
{{- if .Values.global.services.maas.enabled }}
- --enable-maas
{{- end }}
```

The same template logic applies to both the gRPC server and REST gateway deployments. [Codebase: osac-operator/charts/operator/templates/deployment.yaml]

#### Fulfillment-Service: Service Flags

The fulfillment-service uses the shared `services.Flags` type for the gRPC and
REST gateway commands: [Codebase: fulfillment-service/internal/services/flags.go]

`RegisterFlags`, `EnableAllIfNoneSet`, `Validate`, and `EnabledServices` are
implemented on this shared type. If no flag is provided, all services remain
enabled for backward compatibility; invalid combinations are rejected before
server initialization.

#### Fulfillment-Service: Conditional gRPC Registration

The `RegisterResourceServers` function receives `services.Flags` via the
`ResourceServerDeps` struct. Registration blocks for each service group are
wrapped in conditionals:

```go
func RegisterResourceServers(ctx context.Context, registrar grpc.ServiceRegistrar, deps ResourceServerDeps) (*ResourceServers, error) {
    result := &ResourceServers{}

    // CaaS services
    if deps.Services.CaaS {
        // ClusterTemplates, ClusterCatalogItems, Clusters, ClusterVersions
        // ... existing registration code ...
    }

    // VMaaS services
    if deps.Services.VMaaS {
        // ComputeInstanceTemplates, ComputeInstanceCatalogItems,
        // ComputeInstances, DiskImages, InstanceTypes, Volumes
        // ... existing registration code ...
    }

    // BMaaS services
    if deps.Services.BMaaS {
        // BareMetalInstanceTemplates, BareMetalInstanceCatalogItems,
        // BareMetalInstances, BareMetalInstanceTypes
        // ... existing registration code ...
    }

    // Shared infrastructure — always registered
    // Tenants, Users, Roles, RoleBindings, Projects,
    // ProjectMemberships, IdentityProviders, Secrets, Hubs,
    // HostTypes, networking, storage
    // ... existing registration code ...

    return result, nil
}
```

**Edge case — ConsoleSessions:** Unlike all other filterable resources,
ConsoleSessions is registered inline in `start_grpc_server_cmd.go` and is
guarded by the VMaaS flag at that site.

**Edge case — ResourceServers nil fields:** `RegisterResourceServers` returns a struct exposing specific servers that other startup code needs (e.g., `PrivateComputeInstancesServer`, `PrivateHubsServer`). When a service is disabled, the corresponding field is `nil`. Callers must handle this or are only relevant when the service is enabled.

#### Fulfillment-Service: REST Gateway Behavior

The REST gateway receives the same `--enable-*` flags as the gRPC server, but
currently registers generated handlers for all service groups. A request to a
disabled service reaches the fulfillment-service backend, where the disabled
service handler returns `codes.Unavailable`; the gateway exposes that failure
as HTTP 503. This differs from the gRPC reflection surface, where disabled
services are absent. [Codebase: fulfillment-service/internal/cmd/service/start/restgateway/start_rest_gateway_cmd.go]

#### Fulfillment-Service: Disabled-Service gRPC Handling

A gRPC tap handler provides descriptive errors when a client calls a disabled service:

```go
var disabledServiceMap = map[string]string{
    "/osac.public.v1.Clusters/":                   "caas",
    "/osac.public.v1.ClusterTemplates/":            "caas",
    "/osac.public.v1.ClusterCatalogItems/":         "caas",
    "/osac.public.v1.ClusterVersions/":             "caas",
    "/osac.public.v1.ComputeInstances/":            "vmaas",
    "/osac.public.v1.ComputeInstanceTemplates/":    "vmaas",
    "/osac.public.v1.ComputeInstanceCatalogItems/": "vmaas",
    "/osac.public.v1.DiskImages/":                  "vmaas",
    "/osac.public.v1.InstanceTypes/":               "vmaas",
    "/osac.public.v1.ConsoleSessions/":             "vmaas",
    "/osac.public.v1.BareMetalInstances/":          "bmaas",
    "/osac.public.v1.BareMetalInstanceTemplates/":  "bmaas",
    "/osac.public.v1.BareMetalInstanceCatalogItems/": "bmaas",
    "/osac.public.v1.BareMetalInstanceTypes/":      "bmaas",
    // Private API equivalents ...
}
```

When a call matches a known-but-disabled service, the handler returns
`codes.Unavailable` with a message such as `"the VMaaS service is not enabled
on this server"`. Calls to genuinely unknown services retain the default
gRPC behavior (`codes.Unimplemented`). [Codebase:
fulfillment-service/internal/cmd/service/start/grpcserver/unknown_service_handler.go]

#### Fulfillment-Service: HostTypes Filtering

HostTypes remain always-registered (shared infrastructure). The filtering
contract is implemented by OSAC-4681: the HostTypes server receives the service
flags, applies the backing-service predicate to List, and returns NotFound from
Get for a filtered host type. OSAC-4681 is not in the current `main` checkout,
so this behavior is dependency-gated rather than available in every deployed
version. [Locked: D1]

The current `main` checkout does not yet pass service flags to HostTypes. The
filtering behavior above belongs to OSAC-4681 and is dependency-gated until
that change is included.

#### Fulfillment-Service: Capabilities Endpoint

The Capabilities server receives `services.Flags` at construction time and
populates `enabled_services` from `EnabledServices()`. Both public and private
Capabilities servers expose the same field.

Both public and private Capabilities servers are updated identically.

#### Operator Controller Flags

The osac-operator already has per-controller enable flags — no new mechanism is needed. The existing Helm values map directly to services:

| Operator Controller Flag | Service | Helm Value |
|-------------------------|---------|------------|
| `OSAC_ENABLE_CLUSTER_CONTROLLER` | CaaS | `operator.controllers.clusterOrder` |
| `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER` | VMaaS | `operator.controllers.computeInstance` |
| `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER` | BMaaS | `operator.controllers.bareMetalInstance` |

Shared controllers (Tenant, Storage, Volume, Networking) remain always-enabled — they are shared infrastructure. [Locked: D2]

The existing `operator.controllers.*` values and their propagation to
`OSAC_ENABLE_*_CONTROLLER` env vars are unchanged. The current operator startup
validation checks the CaaS dependency on at least one compute controller. MaaS
has no operator controller, so its dependency is enforced by the Helm schema
and fulfillment-service validation rather than by the operator. [Codebase:
osac-operator/charts/operator/templates/deployment.yaml]

#### Bare-Metal Fulfillment Operator

The umbrella chart's `global.services.bmaas.enabled` dependency condition gates
the entire bare-metal-fulfillment-operator deployment. When BMaaS is disabled,
the BMF deployment is omitted and its CRD dependency remains installed —
removing CRDs would cascade-delete existing bare-metal resources.

#### UI Behavior

The server exposes `enabled_services` for clients. Client-side navigation and page
behavior, including whether unavailable services are hidden or disabled, is not
implemented by this change and remains a separate UI decision (see Open Questions
§1).

#### MaaS

MaaS has no gRPC services, controllers, or UI surfaces in the codebase today.
The `--enable-maas` flag and corresponding `global.services.maas.enabled` Helm value are
defined and propagated to the Capabilities endpoint. No MaaS operator
controller validation exists because there is no MaaS controller. [Codebase:
fulfillment-service — no MaaS services exist]

### Security Considerations

This feature inherits the existing OSAC security model without modification. Authentication and authorization flows are unchanged — the JWT validation interceptor, OPA policy enforcement, and tenant isolation metadata remain in place for all enabled services.

The security improvement is additive: disabled gRPC services are not registered
and their controllers do not run. REST routes remain registered, but disabled
backend requests return HTTP 503 without a service payload. Disabled gRPC calls
return `codes.Unavailable` from the disabled-service handler.

The Capabilities endpoint remains unauthenticated (consistent with its current behavior — it is matched by `anonymousMethodsRegex`). The `enabled_services` field exposes which services are active, which is intentional: clients need this information to adapt their behavior. This information is not sensitive — an attacker could determine the same by probing each service endpoint.

The `--enable-*` flags are typed booleans — no input parsing is needed beyond what pflag provides. Inter-service dependency validation (`Validate()`) runs at startup to reject invalid combinations before any server initialization. If no flags are set, all services are enabled (backward compatibility).

### Failure Handling and Recovery

**Invalid service combination in Helm values:** If an admin specifies an invalid combination (e.g., CaaS enabled without VMaaS or BMaaS), `helm install`/`helm upgrade` fails immediately with a validation error from `values.schema.json`. No pods are started or restarted.

**Invalid service combination at runtime:** If the fulfillment-service binary is
started with an invalid flag combination outside Helm, its `Validate()` method
rejects the combination before server initialization. The current operator
validation covers the CaaS/compute-controller dependency; MaaS validation is
handled by Helm and fulfillment-service because the operator has no MaaS
controller.

**No `--enable-*` flags provided:** If no service enable flag is provided, the fulfillment-service enables all services via `EnableAllIfNoneSet()` (backward compatibility). The `Validate()` call runs after defaulting, so the all-enabled default passes validation.

**Helm upgrade with new services enabled:** When a `helm upgrade` enables a previously disabled service, the fulfillment-service pod restarts and registers the new service endpoints. No database migration is needed — the database schema includes all tables regardless of enabled services (tables for disabled services are unused but present). The operator pod restarts and begins reconciling the newly enabled controller's resources.

**Version skew during rolling update:** During a `helm upgrade`, there is a brief window where the old fulfillment-service pod (without the new service) and the new pod (with it) may both be running. The gRPC service routing handles this gracefully: requests to the new service that land on the old pod receive `codes.Unavailable`, and the client retries. The Kubernetes readiness probe ensures the new pod is ready before the old one is terminated.

**Client calls a disabled service without checking Capabilities:** The disabled
service gRPC handler returns `codes.Unavailable` with a descriptive message;
genuinely unknown methods remain `codes.Unimplemented`. The REST gateway
surfaces the disabled backend response as HTTP 503.

**HostTypes filtering with no enabled compute services:** If both VMaaS and BMaaS are disabled, the HostTypes `List` returns an empty list. The `Get` method returns `codes.NotFound` for any specific host type. This is correct behavior — there are no usable host types when no compute services are active.

### RBAC / Tenancy

No RBAC or tenancy changes are required. This feature controls which services are deployed and registered, not who can access them. Tenant isolation metadata (`osac.openshift.io/tenant`, `osac.openshift.io/owner-reference`) and OPA policies remain unchanged for all enabled services.

### Observability and Monitoring

**Current structured logging:**

- `fulfillment-service`: At startup, the current log entry is `Service
  enablement` and includes the enabled service list.
- The disabled-service handler does not currently emit a dedicated warning log.
- `osac-operator`: Existing controller startup logging remains unchanged.

**Current Prometheus metric:**

- `fulfillment_disabled_service_requests_total` is a counter with the current
  `service` label only. It counts requests rejected by the disabled-service
  handler. A `method` label is not currently emitted.

No new Kubernetes events or alerts are introduced.

### Risks and Mitigations

**Risk: REST and gRPC disabled-service behavior diverges.** The REST gateway
registers generated handlers for all services, while the gRPC server omits
disabled service registrations.

Mitigation: Keep the user-facing contract explicit and test disabled gRPC calls
for `codes.Unavailable` plus disabled REST calls for HTTP 503.

**Risk: Service-to-feature mapping becomes stale as new services are added.** A developer adding a new gRPC service might not add it to the correct service group.

Mitigation: The disabled-service map and conditional gRPC registration blocks
serve as self-documenting registries. REST handler registration is intentionally
not conditional in the current implementation, so disabled REST behavior must
remain covered by the HTTP 503 contract.

**Risk: HostTypes filtering logic is fragile.** The current discriminator (presence of `interfaces` field) is an implicit convention, not an explicit type marker.

Mitigation: The filtering implementation uses the same `interfaces` field semantics that the existing HostType proto documents. If the discriminator changes in the future (e.g., a new `kind` field), the filtering logic is updated as part of that change.

### Drawbacks

**Multiple flags to coordinate.** Disabling a service requires the shared
`global.services.*` values plus component propagation. The chart derives the
BMF dependency and controller defaults from these values, while explicit
`operator.controllers.*` overrides remain possible. The `values.schema.json`
constraints catch invalid combinations at `helm install`/`helm upgrade` time.

**All-or-nothing API process startup.** The fulfillment-service is a single process serving all gRPC services. Disabling a service still requires restarting the entire process (via `helm upgrade`), not hot-reloading. This is consistent with the current deployment model and the PRD requirement that changes go through `helm upgrade` [Locked: D4], but it means enabling a new service causes brief downtime for all services.

**Database schema includes disabled service tables.** Tables for disabled services are created during migrations but remain unused. This wastes some storage but avoids the complexity and risk of conditional migrations. The trade-off favors simplicity: enabling a service later does not require running migrations, and the unused tables have negligible overhead.

## Alternatives (Not Implemented)

### Alternative 1: Interceptor-Based Gating

Register all gRPC services unconditionally but add a unary/stream interceptor that rejects calls to disabled services with `codes.Unavailable`.

**Pros:** No changes to registration code; single enforcement point.

**Cons:** All server objects and their dependencies (DAOs, attribution logic, hub scheme) are initialized even when disabled. Disabled services appear in gRPC reflection, confusing operators and debugging tools. The interceptor must maintain a service-to-feature mapping that duplicates the registration knowledge.

**Rejected because:** Conditional registration is more visible (disabled services do not appear in reflection), has a smaller runtime footprint (no unused server objects), and the changes are localized to two files. Juan Hernandez's feasibility analysis in the OSAC-3046 Jira comments reaches the same conclusion.

### Alternative 2: Per-Server Checks

Each server implementation inspects a feature flag before handling any request.

**Pros:** Maximum granularity — each server controls its own behavior.

**Cons:** Requires modifying every existing server implementation and every new server added in the future. Violates the principle of keeping changes localized. The same enablement check would be duplicated across 30+ servers.

**Rejected because:** The per-server approach is the most invasive option with the highest maintenance burden. The centralized registration approach achieves the same result with changes in two files.

### Alternative 3: Separate Processes Per Service

Run separate fulfillment-service processes for each service group (e.g., `fulfillment-service-caas`, `fulfillment-service-vmaas`).

**Pros:** True process isolation; disabling a service means not deploying its pod. No conditional registration needed.

**Cons:** Major architectural change. The fulfillment-service shares a single database connection pool, interceptor chain, and authentication configuration across all services. Splitting into separate processes would require duplicating this infrastructure or extracting it into a shared library. Significantly increases deployment complexity and resource usage.

**Rejected because:** Disproportionate to the problem. The current single-process architecture with conditional registration provides sufficient isolation for compliance purposes.

### Alternative 4: `repeated EnabledService enabled_services` (enum-based Capabilities field)

Define an enum `EnabledService` with values `CAAS`, `VMAAS`, `BMAAS`, `MAAS` and use `repeated EnabledService` in the Capabilities response.

**Pros:** Type-safe; proto schema documents the valid values.

**Cons:** Adding a new service requires a proto change and regeneration in all consumers. The `repeated string` approach allows the server to advertise new services without requiring client updates — clients that don't recognize a service name simply ignore it.

**Rejected because:** The `repeated string` approach is more extensible and consistent with how feature discovery works in other systems (e.g., OAuth 2.0 scopes, HTTP feature headers). Service names are stable identifiers (`caas`, `vmaas`, `bmaas`, `maas`) that do not benefit from enum-level type safety.

## Open Questions

### 1. UI Treatment for Disabled Services

Should navigation items for disabled services be completely hidden or shown as grayed-out/disabled?

**Owner:** UX team (osac-ux)
**Impact:** Affects osac-ui implementation. The design currently specifies "hidden entirely" based on the principle that showing unavailable options confuses users, but the UX team may prefer a different treatment.

### 2. Enclave Wizard Alignment [Resolved]

How do Enclave wizard "experiences" relate to the per-service enablement flags? Do experiences drive the Helm values, get replaced by them, or run alongside them?

**Resolution:** Enclave profiles drive the service enablement values. The Enclave plugin's `osacProfilesList` (e.g., `[caas, vmaas]`) is translated into individual `global.services.*.enabled` flags via value-map extension — the plugin sets the corresponding `global.services` values rather than templating entire value files. This aligns with the team decision to modify the Enclave plugin to extend by value map (OSAC-4106).

**Reconciliation with PR [osac-project/osac#380](https://github.com/osac-project/osac/pull/380):** PR #380 introduced a `global.profilesList` convenience layer with Helm helper functions that compute per-controller flags from a list. The implemented `global.services.*.enabled` booleans are the canonical chart interface; `global.profilesList` must map to that interface where both are used.

### 3. AAP Instance Group Enablement

Should AAP instance groups be disabled when their corresponding service is disabled? The installer already has per-instance-group `enabled` flags (`aap.instanceGroups.clusterFulfillment.enabled`, `aap.instanceGroups.networkFulfillment.enabled`).

**Owner:** Infrastructure team
**Impact:** Affects Helm template propagation. If CaaS is disabled, the cluster-fulfillment AAP instance group is unnecessary overhead. However, instance groups have minimal resource cost when idle, so this may be premature optimization.

## Test Plan

### Unit Tests

**fulfillment-service:**

- `EnableAllIfNoneSet` enables all services when no flag is explicitly set, and preserves explicit flags when any are set.
- `Validate` rejects invalid combinations (CaaS without VMaaS/BMaaS, MaaS without CaaS), accepts valid combinations, and passes after `EnableAllIfNoneSet()`.
- `RegisterResourceServers` with each `services.Flags` combination registers only the expected services. Verify by checking which services are registered on the gRPC server (via reflection or the server's `GetServiceInfo()` method).
- Disabled-service gRPC handling returns `codes.Unavailable` with the service name and falls through to `codes.Unimplemented` for genuinely unknown services.
- REST gateway requests to disabled backend services return HTTP 503; generated REST handlers remain registered.
- Capabilities `Get` returns the correct `enabled_services` list for each configuration.
- HostTypes `List` filters bare-metal host types when BMaaS is disabled, virtual host types when VMaaS is disabled, and returns empty when both are disabled.
- HostTypes `Get` returns `codes.NotFound` for a host type that belongs to a disabled service.

**osac-operator:**

- Existing controller enable flag tests already cover the operator side. No new unit tests needed for the operator itself — the change is in the Helm template layer.

### Integration Tests

- Deploy with `global.services.bmaas.enabled=false`. Verify: BMaaS gRPC services return `codes.Unavailable`; BMaaS REST endpoints return HTTP 503; Capabilities response does not include `bmaas`; bare-metal host types do not appear after OSAC-4681 is included; BMF operator pods are not running; CaaS and VMaaS endpoints function normally.
- Deploy with all services enabled (default). Verify: all endpoints function normally; Capabilities response includes all four services.
- `helm upgrade` to enable a previously disabled service. Verify: the newly enabled service's endpoints become available; Capabilities response updates.

### E2E Tests

- Full deployment with selective services. Verify end-to-end: Capabilities discovery → resource creation → provisioning for enabled services only.
- Tenant user experience: catalog only shows items for enabled services; attempting to create a resource for a disabled service via the CLI returns a clear error.
- HostType filtering: with BMaaS disabled, verify that bare-metal host types are not visible and cannot be used in cluster creation.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages: Dev Preview -> Tech Preview -> GA based on production deployment feedback.

Key signals for graduation:
- All CI profiles (`vmaas-ci`, `caas-ci`, `bmaas-ci`, `full-ci`) pass with the new service enablement flags.
- At least one production deployment has been configured with a subset of services.
- No unexpected `codes.Unavailable` errors from disabled-service handling.

## Upgrade / Downgrade Strategy

**Upgrade from pre-enablement to post-enablement:** Existing deployments have no `global.services.*` values set. All four services default to `true`, so the upgrade is transparent — no behavioral change. The Capabilities endpoint begins returning `enabled_services: ["caas", "vmaas", "bmaas", "maas"]`.

**Downgrade from post-enablement to pre-enablement:** The `--enable-*` flags are unknown to the older fulfillment-service binary. The Helm chart from the older version does not include the flags, so this is a clean downgrade with no residual configuration. All services revert to always-on behavior. The Capabilities endpoint no longer returns `enabled_services` (clients that depend on it fall back to assuming all services are available).

No data migration is required in either direction. Database tables for all services are always present.

## Version Skew Strategy

**fulfillment-service and osac-operator:** During a rolling update, the old fulfillment-service pod serves all services (no `--enable-*` flags) while the new pod serves only enabled services. Requests that land on the old pod behave as before; requests on the new pod may return `codes.Unavailable` for disabled services. The Kubernetes Service load-balances between pods, so clients may see inconsistent behavior for disabled services during the brief upgrade window. This is acceptable — the upgrade completes in seconds, and the `codes.Unavailable` response is a correct transient error.

**osac-operator and fulfillment-service:** If the operator disables a controller but the fulfillment-service still serves the corresponding API, resources can be created via the API but will not be reconciled. This is a temporary state during the upgrade window and resolves when all pods are updated.

**CLI and fulfillment-service:** The CLI checks `enabled_services` from the Capabilities endpoint. An older CLI that does not check this field continues to work — calls to disabled services receive `codes.Unavailable`, which the CLI surfaces as an error. A newer CLI against an older server (no `enabled_services` field) assumes all services are available, which matches the older server's behavior.

## Support Procedures

**Detecting misconfiguration:**

- Check the Capabilities endpoint with `curl https://<endpoint>/api/fulfillment/v1/capabilities`. The `enabled_services` field shows which services are active.
- Check the fulfillment-service logs for the startup line: `"Service enablement"`.
- Check the `fulfillment_disabled_service_requests_total` metric. A sustained non-zero rate indicates clients are attempting to use disabled services.
- Check the osac-operator logs for controller enablement (existing log output).
- Check that BMF operator pods are running or absent as expected.

**Disabling/re-enabling services:**

- Update the Helm values file and run `helm upgrade`. The fulfillment-service and operator pods restart with the new configuration.
- No manual cleanup is needed. Enabling a service makes its API endpoints and controllers available immediately.
- Disabling a service (out of scope for this feature) would require consideration of existing resources — this is why post-installation disablement is deferred.

**Consequences of disabling a service:**

- Cluster health: no impact. Shared infrastructure (networking, storage, tenants) remains fully operational.
- Existing workloads: resources provisioned by the disabled service continue to run. The controller that reconciles them is stopped, so no further lifecycle management occurs (no scaling, no updates, no deletion processing). This is analogous to the existing `management-state: unmanaged` behavior.
- New workloads: cannot be created for the disabled service. API calls return `codes.Unavailable`.

## Infrastructure Needed

None. All changes are within existing repositories (osac mono-repo) and CI infrastructure. The existing CI profiles (`vmaas-ci`, `caas-ci`, `bmaas-ci`, `full-ci`) are extended to validate the new service enablement flags.

---

## Provenance

Authored: revise @ design 0.11.1 - f1d6a4b, workspace OSAC-3046-reconcile-implementation @ 1350873 (dirty)
Phases: revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.1","ai_workflows":"f1d6a4b","source_repo":"1350873 (dirty)","source_repo_branch":"OSAC-3046-reconcile-implementation","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
