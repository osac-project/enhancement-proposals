# BareMetal Instance UI

| Field     | Value                                                           |
|-----------|-----------------------------------------------------------------|
| Author(s) | rawagner@redhat.com                                             |
| Jira      | https://redhat.atlassian.net/browse/OSAC-1319                   |
| Date      | 2026-07-07                                                      |

## Problem Statement

Tenant Users and Tenant Admins have no web console for discovering, provisioning, or managing bare metal instances. Without a UI, the only path to request and manage bare metal hardware is through the gRPC or REST API directly, which is not viable for the typical Tenant User persona. This blocks adoption of the BareMetalInstance service for any tenant who relies on click-ops workflows — the same audience that currently uses the console to order virtual machines and clusters.

## In Scope

- A "Bare Metal" section in the tenant navigation sidebar, accessible to Tenant Users and Tenant Admins.
- A bare metal catalog item browser within the existing Catalog page, showing available `BareMetalInstanceCatalogItem` offerings (title, Markdown-rendered description).
- A bare metal instance list page showing all provisioned instances with name, catalog item, lifecycle state, and age.
- A create form where tenants select a catalog item, provide an SSH public key (optional) and user data (optional, max 64 KB), and an optional OS image. The form can be launched from the catalog item browser (with the catalog item pre-selected) or from the instance list.
- A bare metal instance detail page showing lifecycle state and conditions; with controls to toggle power (Always on ↔ Halted), restart, and delete the instance.
- Instance lifecycle actions (power toggle, restart, delete) available directly on the instance list page (inline row actions), without requiring navigation to the detail page.
- Milestone 0.1.

## Out of Scope

- Cloud Provider Admin flows: creating, editing, or deleting `BareMetalInstanceTemplate` or global `BareMetalInstanceCatalogItem` resources.
- Tenant Admin catalog item CRUD: creating, editing, or deleting tenant-scoped `BareMetalInstanceCatalogItem` resources via the UI.

## User Stories

### Tenant User — Catalog browsing

- As a Tenant User, I want to browse available bare metal catalog items from the Catalog page so that I can compare hardware offerings and choose the one that matches my workload requirements.
- As a Tenant User, I want to open a catalog item detail drawer and start the provisioning form directly from there, with the catalog item already selected, so that I can move from browsing to provisioning in one step.

### Tenant User — Provisioning

- As a Tenant User, I want to provision a bare metal instance by selecting a catalog item, providing an SSH public key, and optionally specifying user data and OS image, so that the system sets up the hardware with my configuration at first boot.
- As a Tenant User, I want input validation on the SSH public key field (OpenSSH format) and a size guard on the user data field (max 64 KB) so that I receive clear feedback before submission rather than a server error.

### Tenant User — Lifecycle monitoring

- As a Tenant User, I want to see a list of my bare metal instances with their current lifecycle state (Provisioning, Running, Failed, Deleting) so that I can monitor which instances are available and which need attention.
- As a Tenant User, I want the list and detail views to reflect the latest instance state without requiring a manual page refresh so that I am not working with stale information during long provisioning operations.
- As a Tenant User, I want to open an instance detail page and see the current state, conditions, and spec (catalog item, SSH key and user data presence, image) so that I have a complete view of what was provisioned and its current status.
- As a Tenant User, I want to see condition details on a failed instance so that I understand why provisioning failed.

### Tenant User — Instance management

- As a Tenant User, I want to start and stop an instance from both the instance list and the detail page so that I can manage power state without navigating away from the list. The control is disabled while the instance is provisioning or deleting.
- As a Tenant User, I want to restart a running instance from both the instance list and the detail page so that I can trigger a restart quickly. The restart control is only available when the instance is in Running state.
- As a Tenant User, I want to delete an instance via a confirmation dialog, accessible from both the instance list and the detail page, so that I can release hardware without leaving the list view. The delete control is disabled while the instance is already deleting.

## Dependencies

- **BareMetalInstance public API (fulfillment-service):** Provides the `GET`, `POST`, `PATCH`, and `DELETE` endpoints for `BareMetalInstance` and the `GET` endpoints for `BareMetalInstanceCatalogItem`. The API must be deployed and reachable before the UI screens are functional. Defined in the [BareMetal Instance API EP](/enhancements/OSAC-1118-baremetal-instance-api).
