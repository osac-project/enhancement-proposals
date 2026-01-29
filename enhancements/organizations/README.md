---
title: osac-organizations-and-authentication
authors:
  - Avishay Traeger
creation-date: 2025-12-21
last-updated: 2025-12-21
tracking-link:
  - TBD
see-also:
replaces:
superseded-by:
---

# OSAC Organizations & Authentication

This enhancement describes the organization model, authentication flows, and admin APIs for OSAC. It provides a multi-tenant experience on top of ACM/OpenShift, supporting managed organizations with clear lifecycle operations. Organizations can contain multiple Projects for additional resource organization and isolation. Each Organization must configure an external identity provider (LDAP/AD/OIDC/SAML) for user authentication, with built-in break-glass accounts available for emergency access.

## Summary

This enhancement introduces a comprehensive multi-tenant organization model for OSAC that enables Cloud Provider Admins to create and manage Organizations, each with their own identity providers. Organizations can contain multiple Projects (with support for nested Projects) for additional resource organization and isolation. Each Organization must configure an external identity provider (LDAP/AD/OIDC/SAML) for user authentication. The system provides built-in OSAC break-glass accounts with limited privileges (IdP and role management only) for emergency access when the IdP is unavailable. Full admin roles (Cloud Provider Admin, Tenant Admin) are defined in the IdP. The architecture follows the Sovereign Gateway Pattern, integrating with Keycloak (managed by the user) for identity management and native role assignment, Gateway API with Kuadrant (which includes Authorino for authorization and Limitador for rate limiting) for declarative, infrastructure-level API protection, and integration with OpenShift for resource isolation. The OSAC Console and CLI authenticate directly with Keycloak using standard OIDC Authorization Code flows. Keycloak Protocol Mappers normalize upstream IdP claims into the standard OSAC Token schema. Kuadrant operates at the Gateway layer via AuthPolicy resources, validating Keycloak-issued tokens and enforcing authorization policies before requests reach the Fulfillment Service. Roles are managed natively in Keycloak and included in tokens, eliminating the need for separate role mapping storage. Authorino provides extensible authorization policies supporting RBAC (initially), with the ability to extend to OPA for advanced policies, SpiceDB for ReBAC, and integration with external systems (e.g., cost-management/billing) for future policy decisions.

## Motivation

This enhancement is critical for enabling OSAC to provide a true multi-tenant experience where multiple organizations can operate independently within a single OpenShift cluster managed by ACM. It addresses the need for clear separation of concerns between Cloud Infrastructure Admins (who manage the cluster), Cloud Provider Admins (who manage organizations), and Tenant Admins (who manage their organization's resources and identity).

### User Stories

* As a Cloud Provider Admin, I want to create and manage Organizations through OSAC APIs, so that I can provide isolated multi-tenant services to different customers or business units.

* As a Cloud Provider Admin, I want to configure an IdP (LDAP/AD/OIDC/SAML) for the *`System`* Organization, so that Cloud Provider Admin users can authenticate using their existing corporate credentials.


* As a Cloud Provider Admin, I want OSAC to provide one break-glass account per organization (including `System` organization) with limited privileges to manage IdP configuration and assign roles, so that I can recover from IdP failures or misconfigurations and restore normal authentication, including setting up role mappings for other users.

* As a Tenant Admin, I want to configure an IdP (LDAP/AD/OIDC/SAML) for my Organization, so that my users can authenticate using their existing corporate credentials.

* As a Cloud Provider Admin or Tenant Admin, I want to test IdP connectivity and view IdP health status, so that I can ensure reliable authentication for my organization's users.

* As a Cloud Provider Admin or Tenant Admin, I want to manage roles and assign them to groups or users, so that I can control access to resources within my organization.

* As a Tenant User, I want to authenticate through my organization's IdP so that I can access OSAC services without managing separate credentials.

* As a Tenant Admin, I want to create and manage Projects within my Organization, so that I can organize resources and provide additional isolation for different teams or workloads.

* As a Tenant Admin, I want to create nested Projects within my Organization, so that I can organize resources hierarchically (e.g., department/project, team/subproject) for better resource organization and isolation.

* As a Tenant User, I want to use Tenant APIs (VMs, Networks, Volumes) within the scope of a Project in my Organization, so that I can provision and manage infrastructure resources in an organized manner.


### Goals

* Provide a multi-tenant organization model where each Organization operates independently with its own identity provider and role configuration. Organizations can contain multiple Projects (with support for nested Projects) for additional resource organization and isolation.

* Enable Cloud Provider Admins to manage the full lifecycle of Organizations (create, list, update, delete) through well-defined APIs.

* Enable Tenant Admins to manage Projects within their Organization, providing hierarchical resource organization.

* Support flexible identity provider integration, allowing each Organization to use LDAP, Active Directory, OIDC, or SAML.

* Maintain one break-glass account per organization with limited privileges (IdP management and role assignment) that remains available regardless of IdP configuration.

* Provide clear role separation: Cloud Infrastructure Admins manage the cluster, Cloud Provider Admins manage organizations, Tenant Admins manage their organization, and Tenant Users consume services.

* Integrate seamlessly with OpenShift, using Projects for isolation.

### Non-Goals

* Quotas are related to Organizations, but will be addressed in a future enhancement.

* Full design of IdP health monitoring and alerting (identified as a future improvement).

* Direct management of OpenShift Users by OSAC - OSAC never creates OpenShift User objects.

* Support for Cloud Infrastructure Admin authentication through OSAC - Cloud Infrastructure Admins continue to use OpenShift OAuth.

## Proposal

This enhancement introduces a comprehensive organization and authentication system for OSAC following the Sovereign Gateway Pattern, built on several key components: Gateway API with Envoy Proxy for request routing, Keycloak (managed by the user) for identity management and native role assignment, Kuadrant (via AuthPolicy) for declarative, infrastructure-level API protection including authentication and authorization, and integration with OpenShift for resource isolation.

### Keycloak

Keycloak is an open-source identity and access management platform that connects applications to external identity providers. It supports multiple IdP types including LDAP, Active Directory, OIDC, and SAML. The Keycloak instance itself is managed by the user (installation, upgrade, backup, etc.). OSAC integrates with the user's Keycloak instance by creating and managing realms via Keycloak Admin API. OSAC creates a Keycloak realm for each Organization. Each Organization must configure an external IdP for user authentication within their Keycloak realm. Keycloak's built-in user storage is used for break-glass accounts, which allows defining break-glass account credentials directly in Keycloak's database. This enables break-glass accounts to authenticate even when their organization's IdP is unavailable or misconfigured, providing critical access to restore IdP functionality. Each OSAC Organization maps to a Keycloak realm, providing complete isolation and independent IdP configuration per organization.

The OSAC Console and CLI authenticate directly with Keycloak using standard OIDC Authorization Code flows. Users are redirected to Keycloak, which handles the authentication flow with the organization's configured Identity Provider. Upstream Identity Provider claims (groups, roles) are mapped into the standard OSAC Token schema using Keycloak Protocol Mappers, ensuring the OSAC platform receives a normalized token without requiring code changes. Keycloak issues OIDC tokens directly to clients; OSAC does not wrap or proxy these tokens.

### Kuadrant

Kuadrant is an open source API security platform that provides comprehensive API protection including authentication, authorization, and rate limiting. Kuadrant integrates Authorino for fine-grained authorization policies and Limitador for rate limiting. This enhancement uses Kuadrant to protect OSAC APIs at the infrastructure layer via Gateway API and AuthPolicy resources:

- **Authorino**: Validates Keycloak-issued OIDC tokens and enforces authorization policies at the Gateway layer before requests reach the Fulfillment Service. Authorino validates token signatures using Keycloak's public keys (retrieved from Keycloak's JWKS endpoint), extracts identity claims and OSAC roles from tokens, and evaluates authorization policies. Initially, Authorino will use RBAC policies based on OSAC roles from Keycloak tokens. Authorino's extensible architecture supports:
  - OPA (Open Policy Agent) for advanced policy evaluation and complex authorization logic
  - SpiceDB for Relationship-Based Access Control (ReBAC) when hierarchical permissions are needed
  - External authorization services for integration with cost-management/billing systems to deny access based on quota or billing status
  - Custom policy extensions as requirements evolve

- **Limitador**: Provides rate limiting capabilities to protect OSAC APIs from abuse and ensure fair resource usage across organizations and projects.

Kuadrant operates at the Gateway layer (Envoy Proxy) via AuthPolicy resources. When a request arrives at the OSAC Gateway, Kuadrant intercepts it before it reaches the Fulfillment Service. Authorino validates the Keycloak token signature and claims, then injects verified user context into HTTP headers (e.g., `X-Remote-User`, `X-Organization`, `X-Roles`) that the Fulfillment Service consumes. This declarative, infrastructure-level enforcement ensures consistent authorization behavior across all OSAC APIs while providing extensibility for future policy requirements.

### Workflow Description

#### Authentication and Authorization Flow

**Cloud Provider Admin** is a user in the `System` Organization with the `cloud-provider-admin` role, providing full control over all Organizations in OSAC.

**Tenant Admin** is a user scoped to exactly one Organization with the `tenant-admin` role, responsible for managing that organization's IdP, users, groups, roles, and Projects.

**Break-Glass Account** is a built-in OSAC user with limited privileges (`idp-manager` role) that can manage IdP configuration and roles. These accounts are stored in Keycloak (single source of truth) and are used for initial IdP configuration during organization bootstrap, as well as for emergency access when the IdP is unavailable. Full admin roles (Cloud Provider Admin, Tenant Admin) are defined in the IdP and have a superset of capabilities beyond the break-glass accounts.

**Tenant User** is a regular user within an Organization who authenticates through the organization's IdP and uses Tenant APIs within Projects. Tenant Users have organization-scoped roles assigned via Keycloak's native role management.

1. User initiates authentication
   1. User visits OSAC Console URL (e.g., `console.org-a.osac.redhat.com`).
   2. Console detects the organization context from the domain or routing configuration and redirects the browser to Keycloak with the query parameter `kc_idp_hint=org-a-idp`.
   3. Keycloak skips the login selection screen and forwards the user directly to their corporate IdP (Okta/AD/etc.) based on the realm configuration.
   4. User authenticates at the corporate IdP.
   5. Upon successful authentication, Keycloak issues OIDC tokens (Access Token, ID Token, Refresh Token) directly to the user's browser/client.
   6. Keycloak Protocol Mappers normalize upstream IdP claims (groups, roles) into the standard OSAC Token schema, ensuring the platform receives consistent token structure without requiring code changes.

2. User calls OSAC APIs with Keycloak-issued tokens
   1. The User makes an API call to `/api/...` with the Keycloak Access Token in the Authorization header.
   2. The request hits the OSAC Gateway (Envoy Proxy).

3. Authorization via Kuadrant at Gateway Layer
   1. Kuadrant (via AuthPolicy) intercepts the request at the infrastructure layer before it reaches the Fulfillment Service.
   2. Authorino validates the Keycloak token signature using Keycloak's public keys (retrieved from Keycloak's JWKS endpoint), extracts identity claims and OSAC roles from the token, and evaluates authorization policies for the target API/action. Initially, policies use RBAC based on roles, but can be extended to use OPA, SpiceDB, or external authorization services.
   3. If the access token has expired or is invalid, the request is rejected with a 401 Unauthorized response at the Gateway layer.
   4. Limitador enforces rate limiting based on organization, project, and user context.
   5. If permitted and within rate limits, Authorino injects verified user context into HTTP headers (e.g., `X-Remote-User`, `X-Organization`, `X-Roles`) and allows the request to proceed to the Fulfillment Service.

4. Fulfillment Service processes the request
   1. The Fulfillment Service receives a clean request with verified User Context injected in HTTP Headers.
   2. The Fulfillment Service performs the actual operation (create/update/delete resources) within the specified Project, using the verified context from headers rather than parsing tokens.

#### Token Refresh Flow

When an access token expires, users obtain a new access token using standard OIDC refresh token flow:

1. User calls Keycloak's standard token endpoint (`/realms/{realm}/protocol/openid-connect/token`) with `grant_type=refresh_token` and the refresh token.
2. Keycloak validates the refresh token and issues a new access token.
3. User uses the new access token for subsequent API calls.

This flow uses standard OIDC protocol endpoints; OSAC does not provide custom token refresh endpoints.

#### Cloud Provider Admin Workflow: Creating an Organization

1. Cloud Provider Admin authenticates using the `System` Organization IdP.

2. Cloud Provider Admin calls `POST /api/fulfillment/v1/organizations` with organization details (name, description, metadata).

3. OSAC creates the Organization, which triggers:
   - Creation of a Keycloak realm for the organization (via Keycloak Admin API)
   - Creation of standard OSAC roles in the Keycloak realm (tenant-admin, tenant-reader, tenant-user, idp-manager)
   - Creation of a break-glass account for the organization directly in Keycloak (via Keycloak Admin API) - Keycloak is the single source of truth for break-glass accounts
   - Creation of a "default" Project in the Organization

4. The organization creation response includes the break-glass account credentials (username and initial password).

5. Cloud Provider Admin securely sends the break-glass account credentials to the organization's idp-manager persona.

6. The idp-manager persona uses the break-glass account to configure the IdP for the organization via `POST /api/fulfillment/v1/organizations/{name}/identity_provider`. During emergencies, Platform Ops team accesses break-glass accounts via the Keycloak Console directly (internally protected) rather than through OSAC APIs.

7. The idp-manager persona (or Tenant Admin) can query IdP status via OSAC API:
   - `GET /api/fulfillment/v1/organizations/{name}/identity_provider` to get IdP configuration (read from Keycloak)
   - `POST /api/fulfillment/v1/organizations/{name}/identity_provider:test` to test IdP connectivity
   - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/health` to get IdP health status

8. The idp-manager persona can then assign roles (including the `tenant-admin` role) to users in the IdP via Keycloak role management APIs.

#### Tenant Admin Workflow: Configuring IdP and Roles

1. Tenant Admin authenticates using the organization's IdP.

2. Tenant Admin manages role assignments via OSAC APIs. OSAC validates that the user is authorized to make role changes, then makes the changes in Keycloak using Keycloak Admin API:
   - `POST /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles` to assign roles to a group
   - `GET /api/fulfillment/v1/organizations/{name}/groups` to list groups and their assigned roles
   - `GET /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}` to view details of a specific group and its assigned roles
   - `DELETE /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles/{role_name}` to remove role assignments from a group
   - `GET /api/fulfillment/v1/organizations/{name}/roles` to list available roles in the realm

3. Users authenticate through the IdP, and their group memberships from the IdP are synced to Keycloak groups. Roles assigned to those groups in Keycloak are automatically included in tokens.

#### Tenant Admin Workflow: Creating a Project

1. Tenant Admin authenticates using the organization's IdP (or break-glass account for emergency access if IdP is temporarily unavailable).

2. Tenant Admin calls `POST /api/fulfillment/v1/organizations/{name}/projects` with project details (name, description, metadata, optional parent_project for nested projects).

3. OSAC creates the Project within the Organization, which triggers:
   - Creation of an OpenShift Project (e.g., `osac-org-<org-name>-project-<project-name>`)
   - If a parent project is specified, the project is created as a nested project with appropriate hierarchical permissions
   - Project is ready to contain resources (VMs, Networks, Volumes, etc.) or child projects

4. Tenant Admin can then:
   - List projects via `GET /api/fulfillment/v1/organizations/{name}/projects` (with optional filter for parent project)
   - View project details via `GET /api/fulfillment/v1/organizations/{name}/projects/{name}` (includes parent project information for nested projects)
   - Update project metadata via `PATCH /api/fulfillment/v1/organizations/{name}/projects/{name}`
   - Delete project via `DELETE /api/fulfillment/v1/organizations/{name}/projects/{name}` (with proper teardown, including nested projects if any)
   - List nested projects via `GET /api/fulfillment/v1/organizations/{name}/projects/{parent_name}/projects`

5. Tenant Users can now provision resources within the Project (or nested Project) using Tenant APIs.

### API Extensions

This enhancement introduces new API endpoints following the fulfillment API pattern (`/api/fulfillment/v1/{resource}`). The APIs will be defined using Protocol Buffers in the fulfillment-api repository, following the same patterns as existing fulfillment services.

**Authentication**: Authentication is handled natively by the OIDC Protocol and Keycloak's standard endpoints. The OSAC Console and CLI authenticate directly with Keycloak using standard OIDC Authorization Code flows. Users obtain tokens from Keycloak's standard endpoints (`/realms/{realm}/protocol/openid-connect/token`, `/realms/{realm}/protocol/openid-connect/userinfo`, `/realms/{realm}/protocol/openid-connect/certs`). OSAC does not provide custom authentication endpoints; all authentication flows use standard OIDC protocol endpoints provided by Keycloak.

**Cloud Provider Admin APIs** (`/api/fulfillment/v1`):
- Organization CRUD operations:
  - `POST /api/fulfillment/v1/organizations` - Create Organization
  - `GET /api/fulfillment/v1/organizations` - List Organizations
  - `GET /api/fulfillment/v1/organizations/{name}` - Get Organization
  - `PATCH /api/fulfillment/v1/organizations/{name}` - Update Organization
  - `DELETE /api/fulfillment/v1/organizations/{name}` - Delete Organization
- Tenant Admin role assignment (assigns roles to users in the IdP):
  - Tenant Admins are users defined in the IdP with the `tenant-admin` role assigned via Keycloak
  - Role assignment is managed through Keycloak role management APIs (see Tenant Admin APIs section)
  - No separate "Tenant Admin account" creation is needed - users from the IdP are assigned roles in Keycloak
- Role management for `System` Organization:
  - Only Cloud Provider Admins (authenticated via IdP) and break-glass accounts can manage System Organization roles in Keycloak
  - System Organization supports system-level roles: `cloud-provider-admin`, `cloud-provider-reader`
  - Same API endpoints as Tenant Admin, but with restricted access: `GET /api/fulfillment/v1/organizations/System/roles`, etc.

**Tenant Admin APIs** (`/api/fulfillment/v1`):
- Identity Provider query and testing (IdP is configured in Keycloak by the user, OSAC provides read-only access):
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider` - Get IdP configuration for an organization (reads from Keycloak)
  - `POST /api/fulfillment/v1/organizations/{name}/identity_provider:test` - Test IdP connectivity (proxies to Keycloak)
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/health` - Get IdP health status (reads from Keycloak)
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/events` - Get IdP events (reads from Keycloak)
- Project CRUD operations:
  - `POST /api/fulfillment/v1/organizations/{name}/projects` - Create a Project within the Organization (supports nested projects via `parent_project` field)
  - `GET /api/fulfillment/v1/organizations/{name}/projects` - List Projects in the Organization (supports filtering by parent project)
  - `GET /api/fulfillment/v1/organizations/{name}/projects/{name}` - Get Project details (includes parent project information for nested projects)
  - `PATCH /api/fulfillment/v1/organizations/{name}/projects/{name}` - Update Project metadata
  - `DELETE /api/fulfillment/v1/organizations/{name}/projects/{name}` - Delete Project (with proper teardown, including nested projects)
  - `GET /api/fulfillment/v1/organizations/{name}/projects/{parent_name}/projects` - List nested Projects under a parent Project
- Role assignment management (roles are pre-created in Keycloak realms):
  - `GET /api/fulfillment/v1/organizations/{name}/roles` - List available roles in Keycloak realm
  - `GET /api/fulfillment/v1/organizations/{name}/roles/{name}` - Get role details
  - `POST /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles` - Assign roles to a group (group identifier from IdP; must be URL-escaped)
  - `GET /api/fulfillment/v1/organizations/{name}/groups` - List groups and their assigned roles (group information retrieved from IdP via Keycloak)
  - `GET /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}` - Get details of a specific group and its assigned roles (group identifier must be URL-escaped)
  - `DELETE /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles/{role_name}` - Remove role assignment from a group (group identifier must be URL-escaped)

### Role Model and Scoping

**System-Level Roles** (assigned only in `System` Organization):
- `cloud-provider-admin`: Full control over all Organizations in OSAC
- `cloud-provider-reader`: Read-only access to all Organizations

**Organization-Level Roles** (assigned in tenant Organizations):
- `tenant-admin`: Full control within a single Organization
- `tenant-reader`: Read-only access within a single Organization
- `tenant-user`: Standard user access within a single Organization

**Break-Glass Role** (assigned to break-glass accounts):
- `idp-manager`: Limited role that can manage IdP configuration (view, update, test, view health) and assign roles to groups/users in Keycloak for the organization. Cannot create/delete organizations, manage users (except for role assignment), create projects, or perform any other administrative actions.

**Role Assignment Constraints**:
- System-level roles can only be assigned in the `System` Organization
- Organization-level roles can only be assigned in tenant Organizations
- Break-glass accounts have the `idp-manager` role and cannot be assigned other roles
- Cloud Provider Admins (authenticated via IdP) and break-glass accounts can manage System Organization roles in Keycloak
- Tenant Admins and break-glass accounts can manage organization-level roles in Keycloak within their Organization
- Authorization policies enforce these constraints to prevent privilege escalation

### Implementation Details/Notes/Constraints

#### Components

**Keycloak - Identity Broker**
- Open-source identity and access management platform that connects applications to external identity providers
- Handles authentication flows, not RBAC
- Keycloak instance is managed by the user (installation, upgrade, backup, etc.) - users deploy and operate their own Keycloak instance
- OSAC integrates with Keycloak by creating and managing realms via Keycloak Admin API
- OSAC creates a Keycloak realm for each Organization (the organization name from metadata.name is used as the realm name, since it is URL-safe and unique)
- Users configure IdP settings in Keycloak realms (OSAC can also configure IdPs via Keycloak Admin API)
- OSAC Console and CLI authenticate directly with Keycloak using standard OIDC Authorization Code flows, calling Keycloak's standard endpoints (`/realms/{realm_name}/protocol/openid-connect/token`, `/realms/{realm_name}/protocol/openid-connect/userinfo`, `/realms/{realm_name}/protocol/openid-connect/certs`)
- Keycloak authenticates against the Organization's configured external IdP (LDAP/AD/OIDC/SAML) - IdP is required for each organization
- Keycloak Protocol Mappers normalize upstream IdP claims (groups, roles) into the standard OSAC Token schema
- Keycloak issues OIDC tokens directly to clients containing identity claims (username, group identifiers, roles, etc.)
- Break-glass accounts (one per organization) are stored in Keycloak's built-in user storage for emergency access when IdP is unavailable
- Users manage Keycloak's storage backend (typically Postgres) - OSAC does not manage Keycloak infrastructure
- Keycloak provides Admin REST API for managing users, roles, and IdP configurations
- Users configure IdP settings in Keycloak directly - OSAC reads configuration via Keycloak Admin API or from tokens

**Keycloak Role Management**
- Standard OSAC roles are pre-created in Keycloak realms when organizations are created
- IdP groups are synced to Keycloak groups (via LDAP/AD group mappers or OIDC group claims)
- Roles are assigned to Keycloak groups (or directly to users) using Keycloak's Admin REST API
- Keycloak automatically includes roles in tokens based on group memberships and role assignments
- Roles appear in token claims: `realm_access.roles` for realm roles, or `resource_access.{client}.roles` for client roles
- No separate role mapping storage is needed - Keycloak is the source of truth for roles

**OSAC Gateway (Envoy Proxy)**
- Receives all incoming API requests at the infrastructure layer
- Routes requests to appropriate Fulfillment Services based on Gateway API routing rules
- Integrates with Kuadrant (via AuthPolicy) for declarative authentication and authorization enforcement

**OSAC Fulfillment Service**
- Receives requests only after Kuadrant authorization at the Gateway layer
- Consumes verified user context from HTTP headers injected by Authorino (e.g., `X-Remote-User`, `X-Organization`, `X-Roles`)
- Implements business logic for Organization and Project management
- Invokes Infrastructure layer to realize changes (e.g., OpenShift Project creation)
- Does not handle authentication or token validation; these concerns are handled at the Gateway layer by Kuadrant

**Kuadrant (Authorino + Limitador)**
- Operates at the Gateway layer via AuthPolicy resources
- Authorino validates Keycloak-issued OIDC tokens and enforces authorization policies:
  - Validates token signature using Keycloak's public keys (retrieved from Keycloak's JWKS endpoint)
  - Extracts identity claims and OSAC roles from tokens
  - Evaluates authorization policies (initially RBAC based on roles, with extensibility for OPA, SpiceDB, and external authorization services)
  - Injects verified user context into HTTP headers before forwarding requests to Fulfillment Service
- Limitador enforces rate limiting based on organization, project, and user context
- Combined unit serves as unified API protection layer at the infrastructure level, enforcing declarative security policies

**OSAC Tenant APIs**
- Implement user-visible resource operations
- Receive requests only after Kuadrant authorization
- Invoke Fulfillment/Infrastructure layer to realize changes

**OpenShift Integration**
- Each Project within an Organization maps to an OpenShift Project (e.g., `osac-org-<org-name>-project-<project-name>`)
- Project names are unique within an Organization, so the OpenShift Project name format is sufficient for all projects (including nested projects)
- Organizations do not directly map to OpenShift Projects; they are logical containers for Projects

#### Authentication Boundaries

- Cloud Infrastructure Admins authenticate via OpenShift OAuth
- Cloud Provider Admins, Tenant Admins, and Tenant Users authenticate through OSAC identity stack
- OSAC users do not become OpenShift Users
- OSAC never creates OpenShift User objects

#### Built-in Break-Glass Accounts

- One break-glass account per organization (including `System` Organization)
- Break-glass accounts are the only built-in OSAC users - they have the `idp-manager` role with limited privileges: can manage IdP configuration (view, update, test, view health) and assign roles to groups/users in Keycloak for their organization
- Break-glass accounts cannot: create/delete organizations, manage users (except for role assignment), create projects, or perform any other administrative actions
- Break-glass accounts are stored in Keycloak (single source of truth) - created directly in the Keycloak master realm or organization-specific realm via the Keycloak Admin API
- Accounts always remain available for break-glass access, regardless of IdP configuration
- Purpose: Initial IdP configuration during organization bootstrap, and recovery from IdP failures or misconfigurations to restore normal authentication, including the ability to configure IdP and set up role mappings for other users
- Platform Ops team accesses break-glass accounts via the Keycloak Console directly (internally protected) during emergencies, rather than through a custom OSAC API
- Full admin roles (Cloud Provider Admin, Tenant Admin) are defined in the IdP and have a superset of capabilities beyond break-glass accounts. These users authenticate through the IdP and receive their admin roles from Keycloak based on IdP group memberships or direct role assignments.

#### Keycloak Configuration Management

Break-glass account management uses Keycloak as the single source of truth.

**Storage Architecture:**
- Keycloak's storage backend (managed by the user, typically Postgres) is the single source of truth for break-glass accounts and realm configuration
- Regular user accounts are stored in the external IdP, not in Keycloak
- Break-glass accounts are created and managed directly in Keycloak via Keycloak Admin REST API

**Break-Glass Account Creation:**
- When an Organization is created, OSAC automatically creates a break-glass account:
  1. OSAC generates a random password for the break-glass account
  2. OSAC creates the user directly in Keycloak via Admin REST API (`POST /admin/realms/{realm}/users`) with the generated password
  3. OSAC assigns the `idp-manager` role to the account in Keycloak
  4. The initial password is returned in the organization creation response to the Cloud Provider Admin (since the password is hashed in Keycloak storage, it cannot be retrieved later). The Cloud Provider Admin is responsible for securely communicating it to the appropriate personnel.
  5. The break-glass account is immediately available for authentication

**Break-Glass Account Access:**
- Platform Ops team accesses break-glass accounts via the Keycloak Console directly (internally protected) during emergencies
- Break-glass accounts can also be accessed via Keycloak Admin REST API for programmatic management
- OSAC does not provide custom APIs for break-glass account access; all access is through Keycloak's native interfaces

**Realm and IdP Management:**
- Realms are created and managed by OSAC via Keycloak Admin REST API (one realm per Organization)
- Identity providers can be configured by users in Keycloak, or by OSAC via Keycloak Admin API
- OSAC reads IdP configuration from Keycloak via Admin REST API or from token claims
- The Keycloak instance itself (installation, upgrade, backup, etc.) is managed by the user

#### Authorization Policy Extensibility

Kuadrant's Authorino component provides extensible authorization capabilities to support evolving policy requirements:

**Initial Implementation (RBAC):**
- Authorization policies use role-based access control (RBAC) based on OSAC roles from Keycloak tokens
- Policies evaluate user roles, organization context, and project context to permit or deny API requests

**Future Extensibility:**
- **OPA Integration**: Authorino can integrate with Open Policy Agent (OPA) for advanced policy evaluation, complex authorization logic, and policy-as-code workflows
- **SpiceDB Integration**: Authorino can integrate with SpiceDB for Relationship-Based Access Control (ReBAC), enabling hierarchical permissions and relationship-based authorization decisions
- **External Authorization Services**: Authorino supports external authorization services, enabling integration with:
  - Cost-management/billing systems to deny access based on quota exhaustion or billing status
  - Compliance systems for policy-based access control
  - Custom authorization logic as requirements evolve
- **Rate Limiting**: Limitador provides rate limiting capabilities that can be configured per organization, project, user, or API endpoint

This extensibility ensures OSAC can adapt to future authorization requirements without requiring architectural changes.

### Risks and Mitigations

**Security Risks:**
- Token compromise could allow unauthorized access to organization resources
  - Mitigation: Use short-lived tokens, implement token rotation, use secure token storage
- IdP misconfiguration could expose sensitive data or allow unauthorized access
  - Mitigation: Provide IdP testing endpoints, validate configurations, implement health checks
- Secret storage compromise could expose IdP credentials
  - Mitigation: Implement secure secret storage in the database, implement secret rotation capabilities
- Bypassing the Gateway could allow unauthorized access to Fulfillment Services
  - Mitigation: Network policies enforce that the Fulfillment Service can ONLY receive traffic from the Gateway/Envoy, preventing direct access to the application Pods. All requests must flow through the Gateway where Kuadrant enforces authentication and authorization at the infrastructure layer.

**Operational Risks:**
- Keycloak failure could prevent all authentication
  - Mitigation: Built-in break-glass accounts remain available, users should implement high availability for their Keycloak instance
- IdP connectivity issues could prevent user authentication
  - Mitigation: Implement IdP health monitoring, provide fallback mechanisms, alert on failures
- Organization deletion could result in data loss
  - Mitigation: Implement proper lifecycle semantics, provide backup/restore capabilities, require explicit confirmation

**Integration Risks:**
- Version skew between OSAC components and OpenShift could cause issues
  - Mitigation: Define version compatibility matrix, test upgrade scenarios, implement graceful degradation

### Drawbacks

**Operational Complexity:**
- Introducing Keycloak, Kuadrant (Authorino + Limitador), and OpenShift integration adds operational complexity
  - Mitigation: Users manage their own Keycloak instance, providing flexibility in deployment and operations. Kuadrant provides unified API protection with extensible authorization policies. Users are responsible for Keycloak high availability.

**IdP Dependency:**
- Organizations become dependent on their IdP availability for user authentication
  - Mitigation: Built-in break-glass accounts remain available, IdP health monitoring helps detect issues early

**Token Management:**
- Users must manage Keycloak-issued tokens in addition to IdP credentials
  - Mitigation: Tokens can be stored securely, and SSO flows reduce the need for frequent re-authentication

**OpenShift Coupling:**
- Tight coupling with OpenShift Projects means changes to OpenShift could require OSAC updates
  - Mitigation: Use stable OpenShift APIs, implement abstraction layers where possible

## Alternatives (Not Implemented)

### Dex in place of Keycloak

Dex is an open-source identity broker (Apache 2.0 license) that connects applications to external identity providers. While Dex is lightweight and supports multiple IdP types (LDAP, Active Directory, OIDC, SAML), it lacks the mature API and auditing capabilities that Keycloak provides.

Dex requires manual configuration management and does not have a Kubernetes operator for declarative management. Each Organization would map to a Dex connector, but connector configurations must be managed programmatically via Dex's gRPC API or configuration files, requiring custom reconciliation logic. Dex's multi-tenant model using connectors is less mature than Keycloak's realm-based isolation.

Keycloak was chosen over Dex because:
- Realm-based multi-tenancy provides better isolation and management for each OSAC Organization
- Mature Admin REST API for integration and dynamic account/IdP management
- Built-in secure auditing capabilities including event logging, admin event tracking, and security event recording, which Dex lacks
- Users can manage Keycloak according to their own operational requirements and preferences
- OSAC integrates with Keycloak as a consumer, avoiding the need to manage identity infrastructure

While Dex could provide the same core functionality (local identity store and IdP federation), Keycloak's mature API, realm-based isolation, and auditing capabilities make it a better fit for OSAC's integration requirements. By having users manage Keycloak themselves, OSAC avoids operational complexity while still benefiting from Keycloak's features.

### Alternative: Direct OpenShift User Integration

An alternative approach would be to create OpenShift Users for each OSAC user and rely on OpenShift OAuth for all authentication. However, this would:
- Mix Cloud Infrastructure Admin concerns with Organization concerns
- Make it difficult to implement organization-scoped authorization
- Require managing OpenShift Users, which is not the intended use case
- Prevent clean separation between Cloud Infrastructure Admins and Tenant Users

The proposed approach maintains clear separation of concerns and allows OSAC to implement its own authorization model independent of OpenShift RBAC.

## Open Questions

1. IdP health monitoring and alerting implementation details are deferred to a future improvement. Should this be a separate enhancement or part of a monitoring enhancement?

2. Organization and Project lifecycle semantics (especially deletion) need further definition. What happens to resources when an organization or project is deleted? What is the teardown process? Should project deletion be blocked if it contains resources?


## Test Plan

TBD

## Graduation Criteria

TBD

## Upgrade / Downgrade Strategy

N/A

## Version Skew Strategy

N/A

## Support Procedures

TBD

## Infrastructure Needed

N/A
