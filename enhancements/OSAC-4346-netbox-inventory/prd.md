# NetBox Inventory Backend for Bare Metal as a Service

| Field       | Value   |
|-------------|---------|
| Author(s)   | Menny Aboush |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4346 |
| Date        | 2026-09-06 |

## Problem Statement

A sovereign-cloud operator runs NetBox as their authoritative source of truth for physical infrastructure — devices, their capabilities, power management addresses, and availability. Today, OSAC cannot allocate bare-metal hosts directly from that NetBox inventory, forcing the operator to maintain a separate inventory system as a second source of truth. This creates data inconsistency, operational burden during host lifecycle changes (adding, decommissioning, updating capability metadata), and risk of misalignment between the operator's primary system and OSAC's view.

## In Scope

- Cloud Infrastructure Admin can configure NetBox as the inventory backend (endpoint URL, credential Secret reference, optional CA certificate) so the system discovers and provisions available hosts without requiring changes to tenant-facing workflows.
- Configuration failures or unreachable backends result in clear error messages visible to Cloud Infrastructure Admin.
- Invalid credentials result in clear error messages without exposing the credential value.
- NetBox authentication uses API token stored in Vault via the OSAC Secret Resource.
- TLS certificates are validated for secure endpoints; self-signed certificates are supported via optional CA certificate configuration.
- BareMetalInstance provisioning and deprovisioning completes end-to-end against NetBox inventory, with accurate status messages at each stage.
- When host preparation fails, the host is released back to NetBox's available pool.
- Tenant Users can request bare-metal hosts by label selector and OSAC transparently allocates them from NetBox without exposing NetBox details to the user.
- Host assignment is safe for parallel requests — only one BareMetalInstance can claim each host.
- Tenant Users see "No hosts available" rather than backend-specific errors.
- No tenant-identifying data appears in NetBox; only the assignment identifier is recorded.
- NetBox is transparent to tenants in normal operation — allocation/deallocation workflows are identical to other backends.
- Power management and host readiness are handled independently of inventory selection.

## Out of Scope

- **OS provisioning and image selection** — NetBox supplies hardware inventory only. OSAC's existing OS provisioning pipeline is orthogonal to this integration.
- **NetBox device management** — adding, removing, or editing devices in NetBox is not an OSAC responsibility. The operator manages their NetBox inventory independently.
- **OSAC UI backend selection** — displaying backend selection in the UI console is tracked separately. (Admin configuration of the inventory backend is in-scope.)
- **Multi-backend deployments in a single cluster** — each deployment uses one inventory backend.
- **Status reporting back to NetBox** — OSAC does not write provisioning status or lifecycle events back to NetBox. Only the assignment identifier is recorded.
- **Health checks on assigned nodes** — OSAC does not periodically verify that assigned nodes still exist in NetBox. If a node is removed from NetBox while assigned, OSAC does not immediately detect the failure.
- **Admin host-listing / inventory visibility in the OSAC API** — surfacing which hosts are available/claimed across backends is addressed separately.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure NetBox as the inventory backend so that OSAC discovers and provisions bare metal hosts from my NetBox infrastructure.

- As a Cloud Infrastructure Admin, I want bare metal hosts to be selected according to the capability labels I have defined in my infrastructure so that tenant requests are matched to appropriate hosts.

- As a Cloud Infrastructure Admin, I want clear error messages when the inventory backend is unreachable so that I can diagnose connectivity issues without inspecting internal logs.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want BareMetalInstance requests to be fulfilled without exposing the inventory backend to other users so that the backend is an infrastructure concern, not a user concern.

### Tenant Admin / Tenant User

- As a Tenant User, I want to request a bare-metal host by specifying required capabilities and have OSAC allocate it transparently.

- As a Tenant User, I want BareMetalInstance lifecycle states to accurately reflect provisioning progress so that I can monitor host preparation.

- As a Tenant User, I want to deallocate a bare-metal host so it becomes available for future allocations.

## Assumptions

- Cloud Infrastructure Admins pre-register bare metal hosts in NetBox before OSAC operates against them (Day-0 prerequisite).
- Each deployment uses a single inventory backend.
- The operator has populated NetBox hosts with labels or attributes sufficient to distinguish host pools for allocation.
- NetBox API is reachable from the OSAC control plane.
- OSAC tracks host assignments in NetBox to prevent double-allocation. The specific storage mechanism (native field, custom field, tag, etc.) is a design-time decision.

## Dependencies

- **Pluggable inventory backend system (OSAC-1032)** — the platform's ability to select different inventory backends (NetBox, OpenStack, Metal3, etc.) at deployment time.
- **Host readiness and power management** — independent of inventory selection; existing platform mechanisms are used.
- **Label-selector contract** — consistent across all inventory backends so tenant requests work the same way regardless of the backend in use.
- **BareMetalInstance API** — tenant-facing API remains unchanged; NetBox integration is transparent to users.
