# Testplan — OSAC-3046

## Overview

- **Feature:** OSAC-3046 — Per-Service Enablement (CaaS/VMaaS/BMaaS/MaaS)
- **Total test cases:** 20
- **Requirements covered:** 8 of 8

## Execution Strategy

Each `helm upgrade` triggers a pod rollout (2-5 minutes). To minimize rollout cycles, test cases should be grouped by deployment state during execution:

**State 0 — Helm validation (no deployment needed):**
TC-FR1-03, TC-FR1-04

**State 1 — BMaaS+MaaS disabled** (`services.bmaas.enabled=false`, `services.maas.enabled=false`):
TC-FR1-01, TC-FR2-01, TC-FR2-02, TC-FR2-03, TC-FR2-04, TC-FR2-05, TC-FR4-01, TC-FR5-01, TC-FR5-04, TC-NFR1-01, TC-NFR3-01

**State 2 — Upgrade to enable BMaaS** (`helm upgrade` with `services.bmaas.enabled=true`):
TC-FR3-01

**State 3 — All services enabled (default values)**:
TC-FR1-02, TC-FR2-04, TC-FR4-02, TC-FR4-03, TC-NFR2-01

**State 4 — VMaaS disabled** (`services.vmaas.enabled=false`):
TC-FR5-02

This reduces execution from 20 individual rollouts to 4 deployment states plus a pre-deployment Helm validation step.

## Test Cases

### FR-1: Cloud Provider Admins select which services are active at installation time via Helm values

#### TC-FR1-01: Install with selective services via Helm values

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-1, AC-2 | critical | automated |

##### Preconditions

- A Kind cluster with OSAC prerequisites installed
- A Helm values file with `services.bmaas.enabled: false` and `services.maas.enabled: false`

##### Steps

1. Run `helm install osac charts/osac -f values.yaml` with selective service values
2. Inspect the rendered fulfillment-service deployment manifest

##### Expected Results

- The fulfillment-service container args include `--enable-caas` and `--enable-vmaas` but not `--enable-bmaas` or `--enable-maas`
- The operator deployment env vars set `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER=false`
- The BMF operator deployment is absent from the rendered manifests

#### TC-FR1-02: Default installation enables all services

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-1 | critical | automated |

##### Preconditions

- A Kind cluster with OSAC prerequisites installed
- Default Helm values (no `services.*` overrides)

##### Steps

1. Run `helm install osac charts/osac` with default values
2. Inspect the rendered fulfillment-service deployment manifest

##### Expected Results

- The fulfillment-service container args include `--enable-caas`, `--enable-vmaas`, `--enable-bmaas`, and `--enable-maas`
- All operator controller env vars are set to `true`
- The BMF operator deployment is present

#### TC-FR1-03: Invalid combination — CaaS without VMaaS or BMaaS — rejected

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-2 | critical | automated |

##### Preconditions

- Helm chart source with `values.schema.json` containing inter-service dependency constraints

##### Steps

1. Run `helm template osac charts/osac --set services.caas.enabled=true --set services.vmaas.enabled=false --set services.bmaas.enabled=false`

##### Expected Results

- The command fails with a schema validation error indicating CaaS requires at least one of VMaaS or BMaaS

#### TC-FR1-04: Invalid combination — MaaS without CaaS — rejected

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-2 | critical | automated |

##### Preconditions

- Helm chart source with `values.schema.json` containing inter-service dependency constraints

##### Steps

1. Run `helm template osac charts/osac --set services.maas.enabled=true --set services.caas.enabled=false`

##### Expected Results

- The command fails with a schema validation error indicating MaaS requires CaaS

### FR-2: Disabled services are not accessible — no API endpoints, no UI surfaces, no provisioning capability

#### TC-FR2-01: Disabled service gRPC endpoint returns Unavailable

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-1, AC-2 | critical | automated |

##### Preconditions

- Fulfillment-service running with `--enable-caas` and `--enable-vmaas` only (BMaaS disabled)

##### Steps

1. Call `BareMetalInstances.List` via gRPC

##### Expected Results

- The response status code is `codes.Unavailable`
- The error message contains `"the bmaas service is not enabled on this server"`

#### TC-FR2-02: Disabled service absent from gRPC reflection

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-5 | high | automated |

##### Preconditions

- Fulfillment-service running with BMaaS disabled

##### Steps

1. Query gRPC reflection for the list of registered services

##### Expected Results

- `osac.public.v1.BareMetalInstances`, `osac.public.v1.BareMetalInstanceTemplates`, `osac.public.v1.BareMetalInstanceCatalogItems`, and `osac.public.v1.BareMetalInstanceTypes` are absent from the reflection response
- `osac.public.v1.Clusters` and `osac.public.v1.ComputeInstances` are present

#### TC-FR2-03: Disabled service REST endpoint not registered

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-1 | high | automated |

##### Preconditions

- Fulfillment-service running with BMaaS disabled

##### Steps

1. Send `GET /api/fulfillment/v1/bare-metal-instances` via HTTP

##### Expected Results

- The HTTP request receives no valid response for the BMaaS resource path — the REST gateway has no registered handler for it, so the mux returns its default unmatched-route response (not a BMaaS-specific payload)
- CaaS and VMaaS REST endpoints remain accessible and return valid responses

#### TC-FR2-04: Shared infrastructure always available regardless of service flags

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-2 | critical | automated |

##### Preconditions

- Fulfillment-service running with some services disabled (tested under State 1: BMaaS+MaaS disabled, and State 3: all enabled)

##### Steps

1. Call `Tenants.List` via gRPC
2. Call `VirtualNetworks.List` via gRPC
3. Call `StorageTiers.List` via gRPC

##### Expected Results

- All three calls return `codes.OK` (possibly with empty lists)
- None return `codes.Unavailable` or `codes.Unimplemented`

#### TC-FR2-05: Operator controllers for disabled services do not run

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-4 | high | automated |

##### Preconditions

- OSAC deployed with `services.bmaas.enabled: false`

##### Steps

1. Check the osac-operator pod's environment variables
2. Check for running BMF operator pods in the deployment namespace

##### Expected Results

- The osac-operator pod's `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER` env var is `false`
- No BMF operator pods are running in the namespace

### FR-3: Post-installation enablement of additional services via helm upgrade

#### TC-FR3-01: Enable a previously disabled service via helm upgrade

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.05 | AC-6 | critical | automated |

##### Preconditions

- OSAC deployed with `services.bmaas.enabled: false`
- BMaaS gRPC endpoints currently return `codes.Unavailable`

##### Steps

1. Update Helm values to set `services.bmaas.enabled: true`
2. Run `helm upgrade osac charts/osac -f values.yaml`
3. Wait for pod rollout to complete
4. Call `BareMetalInstances.List` via gRPC

##### Expected Results

- The gRPC call returns `codes.OK` (not `codes.Unavailable`)
- The osac-operator pod now has `OSAC_ENABLE_BAREMETAL_INSTANCE_CONTROLLER=true`
- BMF operator pods are now running

### FR-4: The Capabilities endpoint advertises which services are currently enabled

#### TC-FR4-01: Capabilities returns enabled services list

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-3, AC-4 | critical | automated |

##### Preconditions

- Fulfillment-service running with `--enable-caas` and `--enable-vmaas` only

##### Steps

1. Call `GET /api/fulfillment/v1/capabilities` (public endpoint)
2. Call the private Capabilities endpoint

##### Expected Results

- Both responses include `enabled_services: ["caas", "vmaas"]`
- Neither response includes `"bmaas"` or `"maas"`

#### TC-FR4-02: Capabilities returns all services when all enabled

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-5 | high | automated |

##### Preconditions

- Fulfillment-service running with all services enabled (default)

##### Steps

1. Call `GET /api/fulfillment/v1/capabilities`

##### Expected Results

- The response includes `enabled_services: ["caas", "vmaas", "bmaas", "maas"]`

#### TC-FR4-03: Capabilities endpoint remains unauthenticated

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-6 | high | automated |

##### Preconditions

- Fulfillment-service running

##### Steps

1. Call `GET /api/fulfillment/v1/capabilities` without any authentication token

##### Expected Results

- The response status is 200 OK with a valid `CapabilitiesGetResponse`
- No authentication error is returned

### FR-5: When a service is disabled, dependent resource types in other services are blocked

#### TC-FR5-01: Bare-metal host types filtered when BMaaS disabled

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.01 | AC-1 | critical | automated |

##### Preconditions

- Fulfillment-service running with BMaaS disabled and CaaS + VMaaS enabled
- Seed host types include both bare-metal (with `interfaces`) and virtual (without `interfaces`) types

##### Steps

1. Call `HostTypes.List` via gRPC

##### Expected Results

- The response contains only host types with empty `interfaces` (virtual types)
- No host type in the response has a non-empty `interfaces` field

#### TC-FR5-02: Virtual host types filtered when VMaaS disabled

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.01 | AC-2 | critical | automated |

##### Preconditions

- Fulfillment-service running with VMaaS disabled and CaaS + BMaaS enabled
- Seed host types include both bare-metal and virtual types

##### Steps

1. Call `HostTypes.List` via gRPC

##### Expected Results

- The response contains only host types with non-empty `interfaces` (bare-metal types)
- No host type in the response has an empty `interfaces` field

#### TC-FR5-03: Empty host types when both compute services disabled

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.01 | AC-3 | high | unit only |

##### Preconditions

- `serviceFlags` with both BMaaS and VMaaS disabled (unit test — this combination is not deployable via Helm because CaaS requires VMaaS or BMaaS)

##### Steps

1. Call `HostTypes.List` via the unit test harness

##### Expected Results

- The response contains an empty list of host types

#### TC-FR5-04: Get specific host type returns NotFound for disabled service

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.01 | AC-5 | high | automated |

##### Preconditions

- Fulfillment-service running with BMaaS disabled
- A bare-metal host type with known ID exists in the database

##### Steps

1. Call `HostTypes.Get` with the bare-metal host type's ID

##### Expected Results

- The response status code is `codes.NotFound`

### NFR-1: Shared infrastructure always-on

#### TC-NFR1-01: HostTypes service registered regardless of service flags

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.01 | AC-4 | high | automated |

##### Preconditions

- Fulfillment-service running with BMaaS and MaaS disabled (State 1 configuration)

##### Steps

1. Call `HostTypes.List` via gRPC

##### Expected Results

- The call returns `codes.OK` (not `codes.Unavailable` or `codes.Unimplemented`)
- The HostTypes service is accessible even though one of its backing compute services (BMaaS) is disabled
- The response contains only virtual host types (bare-metal types filtered out)

### NFR-2: Backward compatibility — all services enabled by default

#### TC-NFR2-01: No flags means all services enabled

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.01 | AC-3 | critical | automated |

##### Preconditions

- Fulfillment-service started without any `--enable-*` flags

##### Steps

1. Call `Clusters.List` via gRPC (CaaS)
2. Call `ComputeInstances.List` via gRPC (VMaaS)
3. Call `BareMetalInstances.List` via gRPC (BMaaS)
4. Call `GET /api/fulfillment/v1/capabilities`

##### Expected Results

- All three List calls return `codes.OK`
- The Capabilities response includes `enabled_services: ["caas", "vmaas", "bmaas", "maas"]`

### NFR-3: Descriptive error messages for disabled service access

#### TC-NFR3-01: UnknownServiceHandler returns descriptive error

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.04 | AC-2 | high | automated |

##### Preconditions

- Fulfillment-service running with VMaaS disabled

##### Steps

1. Call `ComputeInstances.List` via gRPC

##### Expected Results

- The response status code is `codes.Unavailable` (not `codes.Unimplemented`)
- The error message is `"the vmaas service is not enabled on this server"`

## Gaps

- **Story 1.04, AC-4** (`fulfillment_disabled_service_requests_total` Prometheus metric): Verified by unit tests only — metric increment is an internal implementation detail, not a behavioral scenario observable from outside the system.
- **Story 1.04, AC-5** (startup log listing enabled/disabled services): Verified by unit tests only — log output is an operational detail, not a user-facing behavioral outcome.
- **TC-FR5-03** (Story 3.01, AC-3 — empty host types when both compute services disabled): Unit-test-only. The `values.schema.json` constraint requires CaaS to have at least one of VMaaS or BMaaS enabled, so both-disabled is not a deployable Helm configuration. The filtering logic is verified at the unit test level with `serviceFlags` set directly.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 20 |
| Critical | 10 |
| High | 8 |
| Medium | 0 |
| Low | 0 |
| Automated (E2E) | 18 |
| Unit only | 1 |
| Manual | 0 |
| Requirements with test cases | 8 / 8 |
| Requirements without test cases | 0 |
