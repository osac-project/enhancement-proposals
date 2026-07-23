# BCM Backend Integration for BMaaS

| Field | Value |
|-------|-------|
| Author(s) | Menny Aboush |
| Jira | https://redhat.atlassian.net/browse/OSAC-1339 |
| Date | 2026-07-21 |

## Problem Statement

OSAC provisions bare metal hosts through a pluggable backend interface. Customers managing NVIDIA GPU clusters use BCM as their infrastructure management platform and cannot fulfill BareMetalInstance requests through OSAC without a BCM backend. Adding BCM also validates that the pluggable architecture works with additional inventory sources, reducing the risk that future integrations will require interface changes. BCM is transparent to tenants; only Cloud Infrastructure Admin and Cloud Provider Admin personas are affected.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure BCM as the inventory backend so that OSAC can discover and provision bare metal hosts from my BCM-managed infrastructure.
- As a Cloud Infrastructure Admin, I want to register bare metal hosts in BCM so that OSAC can discover and match them to tenant requests.
- As a Cloud Infrastructure Admin, I want clear error messages when BCM is unreachable so that I can diagnose connectivity issues without inspecting internal logs.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want BCM-backed BareMetalInstance requests to be fulfilled without exposing BCM details to other users so that the provisioning backend is an infrastructure concern, not a user concern.

### All Users

- As any user, I want BareMetalInstance lifecycle states (provisioning, ready, deprovisioning, deleted) to accurately reflect the actual state so that I can monitor provisioning progress.

## In Scope

- BareMetalInstance provisioning and deprovisioning completes end-to-end against BCM infrastructure, including clear status visibility during host preparation.
- BCM backend is selectable via operator configuration.
- Lifecycle states (provisioning, ready, deprovisioning, deleted) accurately reflect the actual state at each stage.
- E2E tests validate the full BareMetalInstance lifecycle in CI.
- Power management of bare metal hosts during provisioning and deprovisioning. BCM serves as the inventory source; provisioning and power control are handled independently.

## Out of Scope

- **Sysinfo-based hardware auto-classification.** Host type matching uses admin-assigned labels. Auto-detection from BCM sysinfo is out of scope.
- **CaaS/BMaaS coordination.** CaaS will consume BCM nodes through the BMaaS API in the near future, so the BCM pool will be handled by BMaaS only.
- **UI/Enclave changes.** Enclave configuration UI is tracked separately under OSAC-2229.
- **Multi-backend deployments.** Each deployment uses one inventory backend.
- **Status reporting back to BCM.** OSAC writes only the assignment identifier to BCM. Provisioning status, health, and lifecycle events are not reported back to BCM.
- **Health checks on assigned nodes.** OSAC does not periodically verify that assigned nodes still exist in BCM. If a node is removed from BCM while assigned, OSAC does not immediately detect the failure.

## Requirements

### Functional Requirements

**FR-1:** A Cloud Infrastructure Admin can select BCM as the inventory backend so that the system discovers available bare metal hosts and provisions them without requiring changes to tenant-facing workflows.

**FR-2:** A Cloud Infrastructure Admin configures the BCM backend through operator configuration, including connection details and credentials. No secret material is stored in the configuration itself.

**FR-3:** The BCM backend authenticates to BCM using mutual TLS (mTLS) with credentials managed as Kubernetes Secrets.

**FR-4:** The system discovers available bare metal hosts from BCM, excluding hosts already assigned to other instances.

**FR-5:** When a host is assigned to a BareMetalInstance, the system records an assignment identifier in BCM. No tenant-identifying data is stored in BCM.

**FR-6:** The system prepares a selected host for provisioning. If the process does not succeed, the BareMetalInstance transitions to a failed status and the host is released back to the available pool.

**FR-7:** A user can create a BareMetalInstance and observe it transition through provisioning, ready, deprovisioning, and deleted states with clear status messages at each stage.

**FR-8:** When a BareMetalInstance is deleted, the system deprovisions the host, releases it back to the available pool, and cleans up all associated resources.

**FR-9:** When BCM is unreachable, the system retries with backoff and surfaces a clear error message identifying the failing component.

**FR-10:** E2E tests validate the full BareMetalInstance lifecycle in CI without requiring a real BCM instance.
### Non-Functional Requirements

**NFR-1: Minimum BCM version.**
The BCM backend requires BCM version 10.25.03 or later to ensure compatibility with required metadata storage capabilities.

**NFR-2: Tenant isolation.**
Only the assignment identifier is stored in BCM. No tenant-identifying data is written to BCM. BCM is transparent to Tenant Admins and Tenant Users. A BCM admin who needs tenant context can query the fulfillment-service API using the instance ID.

**NFR-3: Networking independence.**
Networking is independent of the inventory backend. The existing OSAC networking stack handles all network operations. BCM has no networking role.

**NFR-4: Documentation.**
Documentation describes how to configure OSAC to use the BCM backend, including any required BCM prerequisites.
## Acceptance Criteria

- [ ] A Cloud Infrastructure Admin can configure the operator with `type: bcm`, provide BCM endpoint and mTLS credentials, and the system connects to BCM successfully.
- [ ] A Cloud Infrastructure Admin can provision a BareMetalInstance and the system selects an available host from BCM inventory matching the requested host type.
- [ ] During host preparation, the BareMetalInstance status shows a clear message indicating the host is being readied.
- [ ] When host preparation fails, the assignment identifier is cleared from BCM and the host is released back to BCM's available pool.
- [ ] A provisioned BareMetalInstance transitions through provisioning, ready, deprovisioning, and deleted states with accurate status messages.
- [ ] When a BareMetalInstance is deleted, the assignment identifier is cleared from BCM and the host is released back to BCM's available pool for reuse.
- [ ] When BCM is unreachable, the BareMetalInstance status shows a clear error identifying BCM as the failing component.
- [ ] No tenant-identifying data appears in BCM — only the assignment identifier is stored.
- [ ] BCM is transparent to tenants — Tenant Users and Tenant Admins see no difference between BCM-backed and other instances.
- [ ] E2E tests covering the full BareMetalInstance lifecycle pass in CI.
- [ ] When a host is assigned, the system writes the assignment identifier to the host's metadata in BCM.
- [ ] Documentation describes how to configure OSAC to use the BCM backend.

## Assumptions

- Cloud Infrastructure Admins pre-register bare metal hosts in BCM before OSAC operates against them (Day-0 prerequisite).
- Each deployment uses a single inventory backend.
- The pluggable backend interface (OSAC-1032) can accommodate a new inventory backend with host preparation delays.

## Dependencies

- **Pluggable backend interface (OSAC-1032)** — the BCM backend registers against the existing inventory interface.
- **BCM 10.25.03+** — minimum version providing required metadata storage capabilities.

## Risks

- **BMH readiness delay.** Host preparation takes approximately 2-5 minutes after assignment. Provisioning may stall if preparation exceeds the expected time. Mitigation: clear status messaging during preparation and configurable retry behavior.
- **Node removed from BCM while assigned.** If a BCM admin removes a node from BCM while it is assigned to a BareMetalInstance, the BareMetalInstance does not immediately detect the failure. This is a known limitation; periodic health checks are a future enhancement.
