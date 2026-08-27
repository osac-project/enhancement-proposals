---
title: per-service-enablement
authors:
  - htayrie@redhat.com
creation-date: 2026-08-26
last-updated: 2026-08-27
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3046
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-3046-per-service-enablement/prd.md"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Per-Service Enablement (CaaS/VMaaS/BMaaS/MaaS)

## Summary

This design introduces per-service enablement flags that allow Cloud Provider Admins to select which OSAC services (CaaS, VMaaS, BMaaS, MaaS) are active at installation time via Helm values. Disabled services are fully excluded from the deployment — no gRPC/REST API endpoints, no operator controllers, no UI surfaces. The fulfillment-service Capabilities endpoint is extended to advertise enabled services so that clients (CLI, UI) can adapt their behavior at runtime. See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC deploys all services unconditionally. A deployment that only needs CaaS still runs BMaaS controllers, registers BMaaS API endpoints, and must satisfy BMaaS-specific compliance controls during audits (e.g., UEFI Secure Boot, TPM 2.0 attestation for bare-metal hosts). This violates NIST SP 800-53 CM-7 (Least Functionality), which requires disabling unnecessary services.

The osac-operator already has per-controller enable flags (`OSAC_ENABLE_CLUSTER_CONTROLLER`, `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER`, etc.) and CI profiles that exercise service-specific configurations (`vmaas-ci`, `caas-ci`, `bmaas-ci`). The fulfillment-service, however, registers all gRPC services and REST handlers unconditionally. There is no mechanism for the Helm chart to control which API endpoints are active, and no way for clients to discover which services are available at runtime.

This design closes the gap by adding conditional service registration to the fulfillment-service, extending the Capabilities endpoint, and wiring the Helm chart to propagate a single set of service enablement values across all components.

### Goals

- Reuse the operator's existing per-controller enable flag pattern and the installer's existing component-level `enabled` mechanism rather than introducing a new configuration paradigm.
- Keep configuration changes localized: a single set of Helm values drives all components (fulfillment-service, osac-operator, bare-metal-fulfillment-operator, UI).
- Ensure disabled services produce clear, descriptive errors when accessed — not silent failures or generic "unknown service" messages.
- Support post-installation enablement of additional services via `helm upgrade` without data migration or downtime. [Locked: D4]

### Non-Goals

- Post-installation disablement of services and lifecycle management of existing resources when a service is turned off.
- Compliance scan-profile scoping to enabled services (responsibility of OSAC-3029 and OSAC-3031, which consume the enablement signal this feature provides). [Locked: D3]
- Disabling shared infrastructure (networking, storage, tenants, identity, events). [Locked: D2]


## Proposal

Four service enablement flags — `services.caas.enabled`, `services.vmaas.enabled`, `services.bmaas.enabled`, `services.maas.enabled` — are added to the osac-installer Helm chart as the single source of truth. [Locked: D4] The installer propagates these values to the fulfillment-service (as CLI flags), the osac-operator (as environment variables mapped to existing controller flags), and the bare-metal-fulfillment-operator (via the existing `bmf.enabled` condition). All four default to `true`, preserving backward compatibility with existing deployments.

In the fulfillment-service, a new `serviceFlags` struct groups which services are enabled. The gRPC server and REST gateway conditionally skip registration of services belonging to disabled features. A custom `grpc.UnknownServiceHandler` maps calls to known-but-disabled services to `codes.Unavailable` with a descriptive message. The Capabilities endpoint is extended with an `enabled_services` field so clients can discover available services without trial and error. [Locked: D3]

HostTypes define the host flavors available for cluster creation (CaaS). Each host type is backed by either BMaaS (bare-metal hosts, identified by having network `interfaces`) or VMaaS (virtual hosts, no `interfaces`). HostTypes is a shared service — always registered — but when a backing service is disabled, its host types are filtered out of List responses so that users only see host types they can actually provision. [Locked: D1]

### Workflow Description

#### Installation with Service Selection

Starting state: A Cloud Provider Admin is installing OSAC and wants only a subset of services.

1. The Cloud Provider Admin edits the Helm values file to set service enablement:

```yaml
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
   - fulfillment-service starts with `--enable-caas`, `--enable-vmaas` — only CaaS and VMaaS API endpoints are registered.
   - osac-operator starts with `OSAC_ENABLE_CLUSTER_CONTROLLER=true`, `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER=true`, `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER=false`.
   - The bare-metal-fulfillment-operator deployment is skipped entirely (`bmf.enabled=false`).
4. The admin verifies the deployment by calling the Capabilities endpoint:

```bash
osac get capabilities
# Response includes: enabled_services: [caas, vmaas]
```

#### Post-Installation Enablement

Starting state: A running OSAC deployment with CaaS and VMaaS enabled.

1. The admin updates the Helm values file to enable BMaaS:

```yaml
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

1. The CLI calls `GET /api/fulfillment/v1/capabilities`.
2. The response includes `enabled_services: [caas, vmaas]`.
3. The CLI hides BMaaS and MaaS commands from help output and tab completion.
4. If the user explicitly invokes a disabled service command, the CLI returns a clear error: "BMaaS is not enabled on this server."

For the UI, the same Capabilities response drives which navigation items and pages are rendered (see Implementation Details).

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
| bare-metal-fulfillment-operator | Chart.yaml condition: `bmf.enabled` set from `services.bmaas.enabled` |

```text
                        Helm Values (source of truth)
                ┌──────────────────────────────────────────┐
                │  services:                               │
                │    caas:  { enabled: true/false }        │
                │    vmaas: { enabled: true/false }        │
                │    bmaas: { enabled: true/false }        │
                │    maas:  { enabled: true/false }        │
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
│  --enable-caas   │       │  _CONTROLLER         │       │  bmf.enabled =     │
│  --enable-vmaas  │       │ OSAC_ENABLE_COMPUTE  │       │  services.bmaas    │
│  --enable-bmaas  │       │  _INSTANCE_CONTROLLER│       │  .enabled          │
│  --enable-maas   │       │ OSAC_ENABLE_BAREMETAL │       │                    │
│                  │       │  _INSTANCE_CONTROLLER│       │ (entire deployment │
│ Controls:        │       │                      │       │  skipped when      │
│  • gRPC service  │       │ Controls:            │       │  false)            │
│    registration  │       │  • Controller        │       └────────────────────┘
│  • REST handler  │       │    reconciliation    │
│    registration  │       │    loops             │
│  • HostType      │       └─────────────────────┘
│    filtering     │
│  • Capabilities  │
│    endpoint      │
│  • Unknown-      │
│    ServiceHandler│
└──────────────────┘
```

The Helm template for the fulfillment-service deployment passes individual boolean flags, mirroring how the operator subchart passes `OSAC_ENABLE_*_CONTROLLER` env vars:

```yaml
{{- if .Values.services.caas.enabled }}
- --enable-caas
{{- end }}
{{- if .Values.services.vmaas.enabled }}
- --enable-vmaas
{{- end }}
{{- if .Values.services.bmaas.enabled }}
- --enable-bmaas
{{- end }}
{{- if .Values.services.maas.enabled }}
- --enable-maas
{{- end }}
```

The same template logic applies to both the gRPC server and REST gateway deployments. [Codebase: osac-operator/charts/operator/templates/deployment.yaml]

#### Fulfillment-Service: Service Flags

Individual boolean flags are added to the gRPC server and REST gateway cobra commands, mirroring the operator's `controllerFlags` struct and `registerControllerFlags()` pattern: [Codebase: osac-operator/cmd/main.go]

```go
type serviceFlags struct {
    CaaS  bool
    VMaaS bool
    BMaaS bool
    MaaS  bool
}

func registerServiceFlags(flags *pflag.FlagSet) *serviceFlags {
    f := &serviceFlags{}
    flags.BoolVar(&f.CaaS, "enable-caas", false, "Enable CaaS (cluster) services")
    flags.BoolVar(&f.VMaaS, "enable-vmaas", false, "Enable VMaaS (compute instance) services")
    flags.BoolVar(&f.BMaaS, "enable-bmaas", false, "Enable BMaaS (bare metal) services")
    flags.BoolVar(&f.MaaS, "enable-maas", false, "Enable MaaS (model serving) services")
    return f
}

func (f *serviceFlags) enableAllIfNoneSet() {
    if !f.CaaS && !f.VMaaS && !f.BMaaS && !f.MaaS {
        f.CaaS = true
        f.VMaaS = true
        f.BMaaS = true
        f.MaaS = true
    }
}
```

If no `--enable-*` flag is provided, all services are enabled — matching the operator's `enableAllIfNoneSet()` pattern for backward compatibility. [Codebase: osac-operator/cmd/main.go]

#### Fulfillment-Service: Conditional gRPC Registration

The `RegisterResourceServers` function receives `serviceFlags` via the `ResourceServerDeps` struct. Registration blocks for each service group are wrapped in conditionals:

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

**Edge case — ConsoleSessions:** Unlike all other filterable resources, ConsoleSessions is registered inline in `start_grpc_server_cmd.go` (exempt from the central registration function). Its registration is wrapped in a `serviceFlags.VMaaS` check at the inline site separately.

**Edge case — ResourceServers nil fields:** `RegisterResourceServers` returns a struct exposing specific servers that other startup code needs (e.g., `PrivateComputeInstancesServer`, `PrivateHubsServer`). When a service is disabled, the corresponding field is `nil`. Callers must handle this or are only relevant when the service is enabled.

#### Fulfillment-Service: Conditional REST Gateway Registration

The REST gateway's `registerHandlers()` method receives `serviceFlags` and applies the same conditional logic:

```go
func (c *runnerContext) registerHandlers() []handlerRegistrar {
    var handlers []handlerRegistrar

    // Shared infrastructure — always registered
    handlers = append(handlers, publicGw.RegisterCapabilitiesHandler)
    // ... other shared handlers ...

    // CaaS handlers
    if c.services.CaaS {
        handlers = append(handlers,
            publicGw.RegisterClusterTemplatesHandler,
            publicGw.RegisterClusterCatalogItemsHandler,
            publicGw.RegisterClustersHandler,
            publicGw.RegisterClusterVersionsHandler,
            // ... private CaaS handlers ...
        )
    }

    // VMaaS handlers
    if c.services.VMaaS {
        // ... VMaaS handlers ...
    }

    // BMaaS handlers
    if c.services.BMaaS {
        // ... BMaaS handlers ...
    }

    return handlers
}
```

The REST gateway and gRPC server receive the same `--enable-*` flags, ensuring consistency. [Codebase: fulfillment-service/internal/cmd/service/start/restgateway/start_rest_gateway_cmd.go]

#### Fulfillment-Service: UnknownServiceHandler

A custom `grpc.UnknownServiceHandler` is set on the gRPC server to provide descriptive errors when a client calls a disabled service:

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

When a call matches a known-but-disabled service, the handler returns `codes.Unavailable` with a message like `"the vmaas service is not enabled on this server"`. Calls to genuinely unknown services fall through to the default gRPC behavior (`codes.Unimplemented`). The grpc-go library (v1.83.0, already in use) supports `grpc.UnknownServiceHandler`. [Codebase: fulfillment-service/internal/cmd/service/start/grpcserver/start_grpc_server_cmd.go]

#### Fulfillment-Service: HostTypes Filtering

HostTypes remain always-registered (shared infrastructure) but apply server-side filtering based on enabled services. [Locked: D1]

The filtering logic is added to the HostTypes private server's `List` method. The existing `GenericServer` delegates to the DAO's `List` with a CEL filter expression. The HostTypes server adds an implicit filter predicate based on `serviceFlags`:

- When BMaaS is disabled: exclude host types where `interfaces` is non-empty (bare-metal host types).
- When VMaaS is disabled: exclude host types where `interfaces` is empty (virtual host types).
- When both are disabled: return an empty list.
- When both are enabled: no filtering (current behavior).

This filter is applied in addition to any user-provided filter, ensuring that disabled-service host types never appear in results regardless of the client's query. The `Get` method applies the same check: if a requested host type belongs to a disabled service, the server returns `codes.NotFound`.

The `serviceFlags` is passed to the HostTypes server builder via a new `SetServiceFlags` method on the builder chain.

#### Fulfillment-Service: Capabilities Endpoint

The Capabilities server receives `serviceFlags` at construction time. The `Get` method populates the new `enabled_services` field:

```go
func (s *CapabilitiesServer) Get(ctx context.Context, req *publicv1.CapabilitiesGetRequest) (*publicv1.CapabilitiesGetResponse, error) {
    services := make([]string, 0, 4)
    if s.services.CaaS {
        services = append(services, "caas")
    }
    if s.services.VMaaS {
        services = append(services, "vmaas")
    }
    if s.services.BMaaS {
        services = append(services, "bmaas")
    }
    if s.services.MaaS {
        services = append(services, "maas")
    }
    return &publicv1.CapabilitiesGetResponse{
        Authn:           s.buildAuthnCapabilities(),
        EnabledServices: services,
    }, nil
}
```

Both public and private Capabilities servers are updated identically.

#### Operator Controller Flags

The osac-operator already has per-controller enable flags — no new mechanism is needed. The existing Helm values map directly to services:

| Operator Controller Flag | Service | Helm Value |
|-------------------------|---------|------------|
| `OSAC_ENABLE_CLUSTER_CONTROLLER` | CaaS | `operator.controllers.clusterOrder` |
| `OSAC_ENABLE_COMPUTE_INSTANCE_CONTROLLER` | VMaaS | `operator.controllers.computeInstance` |
| `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER` | BMaaS | `operator.controllers.bareMetalInstance` |

Shared controllers (Tenant, Storage, Volume, Networking) remain always-enabled — they are shared infrastructure. [Locked: D2]

The existing `operator.controllers.*` values and their propagation to `OSAC_ENABLE_*_CONTROLLER` env vars are unchanged. [Codebase: osac-operator/charts/operator/templates/deployment.yaml]

#### Bare-Metal Fulfillment Operator

The existing `bmf.enabled` Chart.yaml condition gates the entire bare-metal-fulfillment-operator deployment — no new mechanism is needed. When BMaaS is disabled, the admin sets `bmf.enabled: false` alongside `service.services.bmaas: false` and `operator.controllers.bareMetalInstance: false`. No BMF pods are deployed. CRDs (`bare-metal-fulfillment-operator-crds` subchart) remain installed — removing CRDs would cascade-delete any existing bare-metal resources, which is destructive.

#### UI Behavior

The osac-ui web console consumes the Capabilities endpoint's `enabled_services` field to determine which navigation items and pages to render. The specific UX treatment (hidden vs. grayed-out) is pending a UX team decision (see Open Questions §1). The UI fetches capabilities on initial load and caches the result for the session duration.

#### MaaS

MaaS has no gRPC services, controllers, or UI surfaces in the codebase today. The `--enable-maas` flag and corresponding `service.services.maas` Helm value are defined and propagated to the Capabilities endpoint so the infrastructure is ready when MaaS services are added. No other component changes are needed for MaaS. [Codebase: fulfillment-service — no MaaS services exist]

### Security Considerations

This feature inherits the existing OSAC security model without modification. Authentication and authorization flows are unchanged — the JWT validation interceptor, OPA policy enforcement, and tenant isolation metadata remain in place for all enabled services.

The security improvement is additive: disabled services have no attack surface because their endpoints are not registered and their controllers do not run. A request to a disabled service's endpoint returns `codes.Unavailable` from the `UnknownServiceHandler`, which does not expose any internal state.

The Capabilities endpoint remains unauthenticated (consistent with its current behavior — it is matched by `anonymousMethodsRegex`). The `enabled_services` field exposes which services are active, which is intentional: clients need this information to adapt their behavior. This information is not sensitive — an attacker could determine the same by probing each service endpoint.

The `--enable-*` flags are typed booleans — no input parsing or validation is needed beyond what pflag provides. If no flags are set, all services are enabled (backward compatibility).

### Failure Handling and Recovery

**Invalid service combination in Helm values:** If an admin specifies an invalid combination (e.g., CaaS enabled without VMaaS or BMaaS), `helm install`/`helm upgrade` fails immediately with a validation error from `values.schema.json`. No pods are started or restarted.

**No `--enable-*` flags provided:** If no service enable flag is provided, the fulfillment-service enables all services via `enableAllIfNoneSet()` (backward compatibility). This matches the operator's behavior.

**Helm upgrade with new services enabled:** When a `helm upgrade` enables a previously disabled service, the fulfillment-service pod restarts and registers the new service endpoints. No database migration is needed — the database schema includes all tables regardless of enabled services (tables for disabled services are unused but present). The operator pod restarts and begins reconciling the newly enabled controller's resources.

**Version skew during rolling update:** During a `helm upgrade`, there is a brief window where the old fulfillment-service pod (without the new service) and the new pod (with it) may both be running. The gRPC service routing handles this gracefully: requests to the new service that land on the old pod receive `codes.Unavailable`, and the client retries. The Kubernetes readiness probe ensures the new pod is ready before the old one is terminated.

**Client calls a disabled service without checking Capabilities:** The `UnknownServiceHandler` returns `codes.Unavailable` with a descriptive message identifying which service is disabled. The gRPC status code `Unavailable` is appropriate — it signals a transient condition (the service could be enabled via `helm upgrade`), unlike `Unimplemented` which implies the service does not exist.

**HostTypes filtering with no enabled compute services:** If both VMaaS and BMaaS are disabled, the HostTypes `List` returns an empty list. The `Get` method returns `codes.NotFound` for any specific host type. This is correct behavior — there are no usable host types when no compute services are active.

### RBAC / Tenancy

No RBAC or tenancy changes are required. This feature controls which services are deployed and registered, not who can access them. Tenant isolation metadata (`osac.openshift.io/tenant`, `osac.openshift.io/owner-reference`) and OPA policies remain unchanged for all enabled services.

### Observability and Monitoring

**New structured log events:**

- `fulfillment-service`: At startup, log which services are enabled and disabled at `INFO` level: `"service enablement configured" services_enabled=["caas","vmaas"] services_disabled=["bmaas","maas"]`
- `fulfillment-service`: When the `UnknownServiceHandler` rejects a call to a disabled service, log at `WARN` level: `"request to disabled service" service="bmaas" method="/osac.public.v1.BareMetalInstances/List"`
- `osac-operator`: Already logs which controllers are enabled at startup via existing flag logging.

**New Prometheus metric:**

- `fulfillment_disabled_service_requests_total` (counter, labels: `service`, `method`): Counts requests to disabled services handled by the `UnknownServiceHandler`. A sustained non-zero rate indicates client misconfiguration.

No new Kubernetes events or alerts are introduced.

### Risks and Mitigations

**Risk: REST gateway handler list diverges from gRPC registration.** The REST gateway and gRPC server maintain independent registration lists. A developer adding a new service could update one but not the other.

Mitigation: Add a test that verifies the REST gateway handler list is consistent with the gRPC server's registered services for each enabled/disabled configuration. This test compares the set of registered handler prefixes against the expected set for the given `serviceFlags`.

**Risk: Service-to-feature mapping becomes stale as new services are added.** A developer adding a new gRPC service might not add it to the correct service group.

Mitigation: The `disabledServiceMap` (used by the `UnknownServiceHandler`) and the conditional registration blocks serve as self-documenting registries. A new service that is not placed in any conditional block is always-on (shared infrastructure), which is the safe default. The test added for REST/gRPC consistency also catches services that are missing from both.

**Risk: HostTypes filtering logic is fragile.** The current discriminator (presence of `interfaces` field) is an implicit convention, not an explicit type marker.

Mitigation: The filtering implementation uses the same `interfaces` field semantics that the existing HostType proto documents. If the discriminator changes in the future (e.g., a new `kind` field), the filtering logic is updated as part of that change.

### Drawbacks

**Multiple flags to coordinate.** Disabling a service requires setting flags across multiple components (e.g., `service.services.bmaas`, `operator.controllers.bareMetalInstance`, and `bmf.enabled` for BMaaS). An admin could disable one but miss the others. The `values.schema.json` constraints (see Helm Values Structure) catch invalid combinations at `helm install`/`helm upgrade` time, preventing the most dangerous misconfigurations. CI profiles demonstrate the correct combinations, and documentation must list which flags to set together for each service.

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

### 2. Enclave Wizard Alignment

How do Enclave wizard "experiences" relate to the per-service enablement flags? Do experiences drive the Helm values, get replaced by them, or run alongside them?

**Owner:** Enclave team
**Impact:** Affects the Helm values structure and the Enclave wizard pipeline. The current design defines `services.*.enabled` as standalone Helm values with no dependency on experiences. If experiences should drive these values, the Helm template logic needs adjustment.

### 3. AAP Instance Group Enablement

Should AAP instance groups be disabled when their corresponding service is disabled? The installer already has per-instance-group `enabled` flags (`aap.instanceGroups.clusterFulfillment.enabled`, `aap.instanceGroups.networkFulfillment.enabled`).

**Owner:** Infrastructure team
**Impact:** Affects Helm template propagation. If CaaS is disabled, the cluster-fulfillment AAP instance group is unnecessary overhead. However, instance groups have minimal resource cost when idle, so this may be premature optimization.

## Test Plan

### Unit Tests

**fulfillment-service:**

- `enableAllIfNoneSet` enables all services when no flag is explicitly set, and preserves explicit flags when any are set.
- `RegisterResourceServers` with each `serviceFlags` combination registers only the expected services. Verify by checking which services are registered on the gRPC server (via reflection or the server's `GetServiceInfo()` method).
- `UnknownServiceHandler` returns `codes.Unavailable` with the correct service name for calls to known-but-disabled services, and falls through to `codes.Unimplemented` for genuinely unknown services.
- REST gateway `registerHandlers` returns the expected handler set for each `serviceFlags` combination.
- Capabilities `Get` returns the correct `enabled_services` list for each configuration.
- HostTypes `List` filters bare-metal host types when BMaaS is disabled, virtual host types when VMaaS is disabled, and returns empty when both are disabled.
- HostTypes `Get` returns `codes.NotFound` for a host type that belongs to a disabled service.

**osac-operator:**

- Existing controller enable flag tests already cover the operator side. No new unit tests needed for the operator itself — the change is in the Helm template layer.

### Integration Tests

- Deploy with `services.bmaas.enabled=false`. Verify: BMaaS gRPC services return `codes.Unavailable`; BMaaS REST endpoints return HTTP 503; Capabilities response does not include `bmaas`; bare-metal host types do not appear in HostTypes list; BMF operator pods are not running; CaaS and VMaaS endpoints function normally.
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
- No `codes.Unavailable` errors from the `UnknownServiceHandler` that indicate client-side bugs rather than intentional disabled-service access.

## Upgrade / Downgrade Strategy

**Upgrade from pre-enablement to post-enablement:** Existing deployments have no `services.*` values set. All four services default to `true`, so the upgrade is transparent — no behavioral change. The Capabilities endpoint begins returning `enabled_services: ["caas", "vmaas", "bmaas", "maas"]`.

**Downgrade from post-enablement to pre-enablement:** The `--enable-*` flags are unknown to the older fulfillment-service binary. The Helm chart from the older version does not include the flags, so this is a clean downgrade with no residual configuration. All services revert to always-on behavior. The Capabilities endpoint no longer returns `enabled_services` (clients that depend on it fall back to assuming all services are available).

No data migration is required in either direction. Database tables for all services are always present.

## Version Skew Strategy

**fulfillment-service and osac-operator:** During a rolling update, the old fulfillment-service pod serves all services (no `--enable-*` flags) while the new pod serves only enabled services. Requests that land on the old pod behave as before; requests on the new pod may return `codes.Unavailable` for disabled services. The Kubernetes Service load-balances between pods, so clients may see inconsistent behavior for disabled services during the brief upgrade window. This is acceptable — the upgrade completes in seconds, and the `codes.Unavailable` response is a correct transient error.

**osac-operator and fulfillment-service:** If the operator disables a controller but the fulfillment-service still serves the corresponding API, resources can be created via the API but will not be reconciled. This is a temporary state during the upgrade window and resolves when all pods are updated.

**CLI and fulfillment-service:** The CLI checks `enabled_services` from the Capabilities endpoint. An older CLI that does not check this field continues to work — calls to disabled services receive `codes.Unavailable`, which the CLI surfaces as an error. A newer CLI against an older server (no `enabled_services` field) assumes all services are available, which matches the older server's behavior.

## Support Procedures

**Detecting misconfiguration:**

- Check the Capabilities endpoint: `osac get capabilities` (or `curl https://<endpoint>/api/fulfillment/v1/capabilities`). The `enabled_services` field shows which services are active.
- Check the fulfillment-service logs for the startup line: `"service enablement configured"`.
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
