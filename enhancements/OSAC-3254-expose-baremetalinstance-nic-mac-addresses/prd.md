# Expose NIC MAC Addresses in BareMetalInstance Status

| Field     | Value                                                       |
|-----------|-------------------------------------------------------------|
| Author(s) | Adrien Gentil                                               |
| Jira      | [OSAC-3254](https://redhat.atlassian.net/browse/OSAC-3254) |
| Date      | 2026-08-05                                                  |

## Problem Statement

When BMaaS provisions a BareMetalInstance, it assigns a physical host from the inventory. The MAC addresses of that host's network interfaces are not surfaced in the BareMetalInstance status. This blocks Cluster as a Service (CaaS), which provisions bare metal hosts on demand and then waits for an Assisted Installer agent to register from each host. Agents register using the host's MAC address as an identifier, but CaaS has no programmatic way to correlate an agent with the BareMetalInstance that triggered its provisioning. Without this correlation, CaaS cannot automate worker node registration and requires manual intervention per host.

## In Scope

- MAC addresses of all physical network interfaces of the assigned host, sourced from the inventory backend and exposed in BareMetalInstance status once provisioning completes
- Read access to this metadata via the BareMetalInstance API (Get, List), OSAC CLI, and OSAC web console, following existing BMaaS tenant authorization boundaries

## Out of Scope

- IP addresses — assigned via DHCP at runtime and not a property of the inventory
- Full hardware specifications such as CPU, RAM, and disk layout (covered by BareMetalInstanceType)
- CaaS agent correlation workflow that consumes this data (covered by OSAC-2135)

## User Stories

### CaaS (internal OSAC service)

- As an OSAC service (CaaS), I want to read the MAC addresses of the physical network interfaces of a provisioned BareMetalInstance so that I can match it to the Assisted Installer agent that registered from that host.

### Tenant User, Tenant Admin, Cloud Provider Admin, Cloud Infrastructure Admin

- As a {persona}, I want to see the MAC addresses of a BareMetalInstance's physical network interfaces via the CLI and API so that I can identify servers and correlate them across systems.

## Assumptions

- The inventory backend provides the MAC addresses of all physical NICs for every host it assigns to a BareMetalInstance. MAC addresses are a stable hardware property and do not change for the lifetime of a BareMetalInstance.

## Dependencies

- **Bare Metal Inventory Service:** Must provide the MAC addresses of all physical NICs for each host at the time that host is assigned to a BareMetalInstance.

---

## Provenance

Committed: commit @ prd 0.7.1 - b8b3f86, workspace prd/OSAC-3254 @ 112202d (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86","source_repo":"112202d (dirty)","source_repo_branch":"prd/OSAC-3254","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
