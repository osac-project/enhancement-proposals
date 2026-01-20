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

This enhancement describes the organization model, authentication flows, and admin APIs for OSAC. It provides a multi-tenant experience on top of ACM/OpenShift, supporting managed organizations with clear lifecycle operations. Organizations can contain multiple Projects for additional resource organization and isolation. Each Organization can bring its own IdP (LDAP/AD/OIDC/SAML).

## Summary

This enhancement introduces a comprehensive multi-tenant organization model for OSAC that enables Cloud Provider Admins to create and manage Organizations, each with their own identity providers. Organizations can contain multiple Projects, providing additional isolation and resource organization within an organization. The system provides built-in OSAC authentication for Cloud Provider Admins and Tenant Admins, while allowing Organizations to optionally integrate with external identity providers (LDAP/AD/OIDC/SAML) for their users. The architecture leverages Dex as an identity broker, an OSAC Identity Service for group-to-role mapping resolution, and Authorino for API-level authorization. Each Project maps to an OpenShift Project, and all secret material is stored in OpenShift Secrets, relying on platform-level encryption at rest. Group-to-role mappings are stored in the database (scoped per organization, using group identifiers such as names or paths from the IdP), allowing role assignment through the OSAC API without importing users or groups into a local database.

## Motivation

This enhancement is critical for enabling OSAC to provide a true multi-tenant experience where multiple organizations can operate independently within a single OpenShift cluster managed by ACM. It addresses the need for clear separation of concerns between Cloud Infrastructure Admins (who manage the cluster), Cloud Provider Admins (who manage organizations), and Tenant Admins (who manage their organization's resources and identity).

### User Stories

* As a Cloud Provider Admin, I want to create and manage Organizations through OSAC APIs, so that I can provide isolated multi-tenant services to different customers or business units.

* As a Cloud Provider Admin, I want to manage Tenant Admin accounts (create, reset, disable), so that I can maintain control over organization access while delegating day-to-day management to Tenant Admins.

* As a Cloud Provider Admin, I want to configure an IdP (LDAP/AD/OIDC/SAML) for the *`System`* Organization, so that Cloud Provider Admin users can authenticate using their existing corporate credentials.

* As a Tenant Admin, I want to configure an IdP (LDAP/AD/OIDC/SAML) for my Organization, so that my users can authenticate using their existing corporate credentials.

* As a Cloud Provider Admin or Tenant Admin, I want to test IdP connectivity and view IdP health status, so that I can ensure reliable authentication for my organization's users.

* As a Cloud Provider Admin or Tenant Admin, I want to maintain mappings of IdP groups to OSAC roles through the OSAC API, so that I can manage access control within my organization by assigning roles to groups rather than individual users.

* As a Tenant User, I want to authenticate through my organization's IdP so that I can access OSAC services without managing separate credentials.

* As a Tenant Admin, I want to create and manage Projects within my Organization, so that I can organize resources and provide additional isolation for different teams or workloads.

* As a Tenant User, I want to use Tenant APIs (VMs, Networks, Volumes) within the scope of a Project in my Organization, so that I can provision and manage infrastructure resources in an organized manner.

* As a Cloud Infrastructure Admin, I want OSAC to use OpenShift Secrets for storing sensitive credentials, so that I can leverage platform-level encryption and existing secret management practices.

* As a system operator, I want OSAC to provide one break-glass account per organization (including System organization) with limited privileges to manage IdP configuration, so that I can recover from IdP failures or misconfigurations and restore normal authentication.

### Goals

* Provide a multi-tenant organization model where each Organization operates independently with its own identity provider and group-to-role mappings. Organizations can contain multiple Projects for additional resource organization and isolation.

* Enable Cloud Provider Admins to manage the full lifecycle of Organizations (create, list, update, delete) through well-defined APIs.

* Enable Tenant Admins to manage Projects within their Organization, providing hierarchical resource organization.

* Support flexible identity provider integration, allowing each Organization to use LDAP, Active Directory, OIDC, or SAML.

* Maintain one break-glass account per organization with limited IdP management privileges that remains available regardless of IdP configuration.

* Provide clear role separation: Cloud Infrastructure Admins manage the cluster, Cloud Provider Admins manage organizations, Tenant Admins manage their organization, and Tenant Users consume services.

* Integrate seamlessly with OpenShift, using Projects for isolation and Secrets for credential storage.

### Non-Goals

* Quotas are related to Organizations, but will be addressed in a future enhancement.

* Full design of IdP health monitoring and alerting (identified as a future improvement).

* Direct management of OpenShift Users by OSAC - OSAC never creates OpenShift User objects.

* Support for Cloud Infrastructure Admin authentication through OSAC - Cloud Infrastructure Admins continue to use OpenShift OAuth.

## Proposal

This enhancement introduces a comprehensive organization and authentication system for OSAC built on several key components: Dex as an identity broker, an OSAC Identity Service for identity resolution, an Auth Gateway for token issuance, Authorino for API authorization, and integration with OpenShift for resource isolation and secret storage.

### Dex

Dex is an open-source identity broker (Apache 2.0 license) that connects applications to external identity providers. It supports multiple IdP types including LDAP, Active Directory, OIDC, and SAML. Dex can be configured to support local/break-glass users through its static password connector, which allows storing user credentials directly in Dex's configuration. This enables break-glass accounts to authenticate even when their organization's IdP is unavailable or misconfigured, providing critical access to restore IdP functionality.

### Authorino

Authorino is already used in the OSAC system to validate tokens and enforce fine-grained access policies. Previously, Authorino validated external tokens from identity providers. With this enhancement, Authorino will validate internal OSAC tokens issued by the Auth Gateway. These OSAC tokens contain the user's identity, Organization context, and OSAC roles that have already been resolved by the Identity Service from group-to-role mappings. This enhancement extends the existing Authorino workflow by connecting the new authentication flow (Dex → Identity Service → Auth Gateway) to Authorino's token validation and policy evaluation, ensuring consistent authorization behavior across all OSAC APIs while leveraging existing infrastructure.

### Workflow Description

#### Authentication and Authorization Flow

**Cloud Provider Admin** is a user in the `System` Organization with the `cloud-provider-admin` role, providing full control over all Organizations in OSAC.

**Tenant Admin** is a user scoped to exactly one Organization with the `tenant-admin` role, responsible for managing that organization's IdP, users, groups, roles, and Projects.

**Tenant User** is a regular user within an Organization who authenticates through the organization's IdP and uses Tenant APIs within Projects. Tenant Users have organization-scoped roles assigned via group-to-role mappings.

1. User initiates login
   1. The User calls the OSAC login endpoint, specifying the target Organization:
      - `POST /api/fulfillment/v1/auth/login` with `organization_name` in the request body, OR
      - Organization name can be inferred from custom domain routing (if the organization has configured a custom domain), OR
      - For break-glass users, the organization is determined from their account (each break-glass account is scoped to exactly one organization)
   2. The API Endpoint forwards the request to the Auth Gateway.
   3. The Auth Gateway determines the target Organization using one of the methods above.
   4. The Auth Gateway maps the Organization name to a Dex connector ID (the organization name is used directly as the connector ID, since it is URL-safe and unique).

2. Dex performs authentication via the Organization's IdP
   1. The Auth Gateway proxies the token request to Dex's token endpoint (`/dex/token`), including the connector ID corresponding to the Organization.
   2. Dex looks up the connector configuration for that Organization (dynamically loaded from the database).
   3. If the Organization has a configured IdP, Dex authenticates against that upstream Identity Provider (IdP) using the connector configuration.
   4. If the Organization does not have a configured IdP, Dex authenticates against the organization's break-glass account (stored in Dex Postgres storage).
   5. The User authenticates at the IdP (or with local credentials).
   6. Dex returns tokens to the Auth Gateway, including identity claims (username, group identifiers, etc.).

3. OSAC Identity Service resolves user identity and roles
   1. The Auth Gateway extracts identity claims (including group identifiers) from Dex tokens and calls the OSAC Identity Service with the user's group memberships and Organization context.
   2. The Identity Service looks up group-to-role mappings in the database (scoped to the user's Organization) based on the group identifiers from Dex.
   3. The Identity Service determines the user's effective OSAC roles by aggregating roles from all groups the user belongs to.
   4. The Identity Service returns normalized OSAC identity + roles + Organization context to the Auth Gateway.

4. Auth Gateway issues an OSAC token
   1. The Auth Gateway constructs and returns an OSAC token to the User. It contains Organization context, includes user identity, contains OSAC roles, and is signed by OSAC. The token may also include Project context if the user is accessing resources within a specific Project.

#### Request Flow (Using the OSAC Token)

1. User calls OSAC APIs with their OSAC token
   1. The User makes an API call to `/api/...` with the OSAC token.
   2. The request reaches the API Endpoint, which extracts the token.

2. Authorization via Authorino
   1. The API Endpoint sends the token to Authorino for validation and policy checks.
   2. Authorino validates the token signature and expiry, extracts OSAC identity + roles, and evaluates policies for the target API/action.

3. If permitted, Authorino allows the request to proceed to the appropriate Tenant API.

4. The API call reaches the relevant Tenant API (VMs, Networks, Volumes, etc.), which is scoped to a Project within the Organization.

5. Tenant API performs the actual operation (create/update/delete resources) within the specified Project.

#### Cloud Provider Admin Workflow: Creating an Organization

1. Cloud Provider Admin authenticates using the `System` Organization IdP (or break-glass account if IdP is not configured).

2. Cloud Provider Admin calls `POST /api/fulfillment/v1/organizations` with organization details (name, description, metadata).

3. OSAC creates the Organization, which triggers:
   - Bootstrap RBAC for the organization
   - Creates one break-glass account for the organization (stored in Dex Postgres storage) with limited IdP management privileges
   - Organization is ready to contain Projects (which will map to OpenShift Projects)

4. Cloud Provider Admin can then:
   - Create Tenant Admins via `POST /api/fulfillment/v1/organizations/{name}/tenant_admins` (these are regular admin accounts, not break-glass)
   - Configure IdP for the `System` Organization via `POST /api/fulfillment/v1/organizations/{name}/identity_provider` (as Cloud Provider Admin for `System` org)
   - View organization status and usage via `GET /api/fulfillment/v1/organizations/{name}`

#### Tenant Admin Workflow: Configuring IdP and Role Mappings

1. Tenant Admin authenticates using the organization's IdP (or break-glass account if IdP is not configured).

2. Tenant Admin configures IdP via `POST /api/fulfillment/v1/organizations/{name}/identity_provider` with IdP configuration (type: LDAP/AD/OIDC/SAML, URLs, attribute mappings).

3. Tenant Admin sets IdP credentials via `POST /api/fulfillment/v1/organizations/{name}/identity_provider/credentials` (client secrets, bind passwords stored in OpenShift Secrets).

4. Tenant Admin tests IdP connectivity via `POST /api/fulfillment/v1/organizations/{name}/identity_provider:test`.

5. Once IdP is configured and tested, Tenant Admin can create group-to-role mappings:
   - `POST /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles` to assign OSAC roles to a group (using group identifier from IdP; group identifiers must be URL-escaped in the path)
   - `GET /api/fulfillment/v1/organizations/{name}/groups` to list groups and their role mappings (group information comes from IdP via Dex)
   - `GET /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}` to view details of a specific group and its role mappings (group identifier must be URL-escaped)

6. Users can now authenticate through the IdP, and their group memberships (group identifiers such as names or paths) from the IdP will be used to resolve their OSAC roles via the stored mappings.

#### Tenant Admin Workflow: Creating a Project

1. Tenant Admin authenticates using the organization's IdP (or break-glass account if IdP is not configured).

2. Tenant Admin calls `POST /api/fulfillment/v1/organizations/{name}/projects` with project details (name, description, metadata).

3. OSAC creates the Project within the Organization, which triggers:
   - Creation of an OpenShift Project (e.g., `osac-org-<org-name>-project-<project-name>`)
   - Bootstrap RBAC for the project scoped to the organization
   - Project is ready to contain resources (VMs, Networks, Volumes, etc.)

4. Tenant Admin can then:
   - List projects via `GET /api/fulfillment/v1/organizations/{name}/projects`
   - View project details via `GET /api/fulfillment/v1/organizations/{name}/projects/{name}`
   - Update project metadata via `PATCH /api/fulfillment/v1/organizations/{name}/projects/{name}`
   - Delete project via `DELETE /api/fulfillment/v1/organizations/{name}/projects/{name}` (with proper teardown)

5. Tenant Users can now provision resources within the Project using Tenant APIs.

### API Extensions

This enhancement introduces new API endpoints following the fulfillment API pattern (`/api/fulfillment/v1/{resource}`). The APIs will be defined using Protocol Buffers in the fulfillment-api repository, following the same patterns as existing fulfillment services.

**Authentication APIs** (`/api/fulfillment/v1`):
- `POST /api/fulfillment/v1/auth/login` - Initiate login flow (OAuth2 Resource Owner Password Credentials grant)
  - Content-Type: `application/x-www-form-urlencoded`
  - Request body parameters:
    - `grant_type`: `password` (for username/password authentication)
    - `organization_name`: Organization name (from metadata.name, required, unless inferred from custom domain or user account)
    - `username`: User's username
    - `password`: User's password
    - `scope`: Optional OAuth2 scopes (e.g., `openid profile`)
  - Organization can also be determined from custom domain routing (if configured)
  - For break-glass users, organization is determined from their account (each break-glass account is scoped to exactly one organization)
  - Response: OSAC access token (JWT) containing user identity, Organization context, and OSAC roles
    - `access_token`: OSAC JWT token
    - `token_type`: `Bearer`
    - `expires_in`: Token expiration time in seconds
- `GET /api/fulfillment/v1/auth/validate` - Validate an authentication token
  - Authorization header: `Bearer <token>`
  - Returns validation status (200 if valid, 401 if invalid)
- `GET /api/fulfillment/v1/auth/userinfo` - Get user information (OIDC UserInfo endpoint)
  - Authorization header: `Bearer <token>`
  - Returns user identity, Organization context, and OSAC roles
- `GET /api/fulfillment/v1/auth/permissions` - Get available permissions/roles for the authenticated user
  - Authorization header: `Bearer <token>`
  - Returns list of OSAC roles and permissions for the user

**Cloud Provider Admin APIs** (`/api/fulfillment/v1`):
- Organization CRUD operations:
  - `POST /api/fulfillment/v1/organizations` - Create Organization
  - `GET /api/fulfillment/v1/organizations` - List Organizations
  - `GET /api/fulfillment/v1/organizations/{name}` - Get Organization
  - `PATCH /api/fulfillment/v1/organizations/{name}` - Update Organization
  - `DELETE /api/fulfillment/v1/organizations/{name}` - Delete Organization
- Tenant Admin management (creates accounts in Dex configuration):
  - `POST /api/fulfillment/v1/organizations/{name}/tenant_admins` - Create Tenant Admin account (stored in Dex config)
  - `GET /api/fulfillment/v1/organizations/{name}/tenant_admins` - List Tenant Admins
  - `POST /api/fulfillment/v1/organizations/{name}/tenant_admins/{admin_name}:reset-credentials` - Reset credentials
  - `DELETE /api/fulfillment/v1/organizations/{name}/tenant_admins/{admin_name}` - Disable/remove Tenant Admin
- Group-to-role mapping management for `System` Organization:
  - Only Cloud Provider Admins (authenticated via IdP) can manage System Organization group-to-role mappings
  - System Organization supports system-level roles: `cloud-provider-admin`, `cloud-provider-reader`, `catalog-curator`, and other system-scoped roles
  - Break-glass accounts cannot modify group-to-role mappings (prevents privilege escalation)
  - Same API endpoints as Tenant Admin, but with restricted access: `POST /api/fulfillment/v1/organizations/System/groups/{group_identifier}/roles`, etc.

**Tenant Admin APIs** (`/api/fulfillment/v1`):
- Identity Provider CRUD operations (nested under organization, since each organization has at most one IdP):
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider` - Get IdP for an organization
  - `POST /api/fulfillment/v1/organizations/{name}/identity_provider` - Create/configure IdP
  - `PATCH /api/fulfillment/v1/organizations/{name}/identity_provider` - Update IdP configuration
  - `DELETE /api/fulfillment/v1/organizations/{name}/identity_provider` - Delete/disable IdP
- IdP credentials management:
  - `POST /api/fulfillment/v1/organizations/{name}/identity_provider/credentials` - Create/rotate credentials
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/credentials/status` - Get credential status
- IdP health and events:
  - `POST /api/fulfillment/v1/organizations/{name}/identity_provider:test` - Test IdP connectivity
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/health` - Get IdP health status
  - `GET /api/fulfillment/v1/organizations/{name}/identity_provider/events` - Get IdP events
- Project CRUD operations:
  - `POST /api/fulfillment/v1/organizations/{name}/projects` - Create a Project within the Organization
  - `GET /api/fulfillment/v1/organizations/{name}/projects` - List Projects in the Organization
  - `GET /api/fulfillment/v1/organizations/{name}/projects/{name}` - Get Project details
  - `PATCH /api/fulfillment/v1/organizations/{name}/projects/{name}` - Update Project metadata
  - `DELETE /api/fulfillment/v1/organizations/{name}/projects/{name}` - Delete Project (with teardown)
- Group-to-role mapping management:
  - `POST /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles` - Assign OSAC roles to a group (using group identifier from IdP; must be URL-escaped)
  - `GET /api/fulfillment/v1/organizations/{name}/groups` - List groups and their role mappings (group information retrieved from IdP via Dex)
  - `GET /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}` - Get details of a specific group and its role mappings (group identifier must be URL-escaped)
  - `DELETE /api/fulfillment/v1/organizations/{name}/groups/{group_identifier}/roles` - Remove role assignments from a group (group identifier must be URL-escaped)

### Role Model and Scoping

**System-Level Roles** (assigned only in `System` Organization):
- `cloud-provider-admin`: Full control over all Organizations in OSAC
- `cloud-provider-reader`: Read-only access to all Organizations
- `catalog-curator`: Manages catalog/template resources across organizations
- Additional system-level roles may be defined as needed

**Organization-Level Roles** (assigned in tenant Organizations):
- `tenant-admin`: Full control within a single Organization
- `tenant-reader`: Read-only access within a single Organization
- `tenant-user`: Standard user access within a single Organization
- Additional organization-specific roles may be defined per organization

**Break-Glass Role** (assigned to break-glass accounts):
- `idp-manager`: Limited role that can only manage IdP configuration (view, update, test, view health) for the organization. Cannot create/delete organizations, manage users, assign roles, create projects, or perform any other administrative actions.

**Role Assignment Constraints**:
- System-level roles can only be assigned in the `System` Organization
- Organization-level roles can only be assigned in tenant Organizations
- Break-glass accounts have the `idp-manager` role and cannot be assigned other roles
- Only Cloud Provider Admins (authenticated via IdP) can manage System Organization group-to-role mappings
- Tenant Admins can only assign organization-level roles within their Organization
- Authorization policies enforce these constraints to prevent privilege escalation

### Implementation Details/Notes/Constraints

#### Components

**Dex - Identity Broker**
- Open-source identity broker that connects applications to external identity providers
- Handles authentication flows, not RBAC
- Each Organization maps to a Dex connector with a unique connector ID (the organization name from metadata.name is used directly as the connector ID, since it is URL-safe and unique)
- Connectors are dynamically registered/updated as Organizations are created or their IdP configurations change
- Receives token requests from Auth Gateway via `/dex/token` endpoint with connector ID parameter
- Authenticates against the Organization's configured IdP (LDAP/AD/OIDC/SAML) or local break-glass accounts
- Returns OIDC tokens containing identity claims (username, group identifiers, etc.)
- Authenticates break-glass accounts (one per organization) stored in Dex's Postgres storage backend
- Uses Postgres as storage backend for break-glass accounts (persistent across pod restarts)
- Provides gRPC API (port 5557) for dynamic account management without pod restarts
- IdP configurations are dynamically loaded from the database (stored per Organization) rather than being statically configured in Dex

**OSAC Identity Service**
- Stores group-to-role mappings in the database (scoped per Organization, using group identifiers such as names or paths from IdP)
- Resolves OSAC roles by looking up group identifiers from Dex identity claims against stored mappings
- Group identifiers are strings (group names or paths) returned by the IdP, which may contain slashes (e.g., "/TENANT-nairr-GET"). These are distinct from internal IdP UUIDs and are used as the key for role mappings.
- Aggregates roles from all groups a user belongs to to determine effective OSAC roles
- Does not store users or groups - users and groups remain in their IdP, only mappings are stored
- Produces the "OSAC identity" (user identity + effective roles) used in all authorization decisions

**OSAC API (API Endpoint + Auth Gateway + Authorino)**
- Auth Gateway handles login flows:
  - Acts as a proxy/wrapper around Dex, providing a unified OSAC authentication API
  - Determines target Organization from login request (organization_name parameter, custom domain routing, or user account for break-glass users)
  - Maps Organization name to Dex connector ID (organization name is used directly as the connector ID)
  - Proxies token requests to Dex's token endpoint (`/dex/token`) with the appropriate connector ID
  - Receives tokens from Dex containing identity claims (username, group identifiers, etc.)
  - Extracts identity claims from Dex tokens and consults Identity Service for role resolution
  - Issues OSAC tokens (JWT) containing user identity, Organization context, and OSAC roles
  - Provides additional endpoints: `/auth/validate`, `/auth/userinfo`, `/auth/permissions`
- Authorino validates OSAC tokens and enforces fine-grained access policies based on OSAC roles and Organization context
- Combined unit serves as unified API front end

**OSAC Tenant APIs**
- Implement user-visible resource operations
- Receive requests only after Authorino authorization
- Invoke Fulfillment/Infrastructure layer to realize changes

**OpenShift Integration**
- Each Project within an Organization maps to an OpenShift Project (e.g., `osac-org-<org-name>-project-<project-name>`)
- Per-Project non-secret configuration associated with the OpenShift Project
- Organizations do not directly map to OpenShift Projects; they are logical containers for Projects
- All secret material stored in OpenShift Secrets (IdP bind passwords, OIDC/SAML client secrets, certificates, private keys)
- OSAC relies on OpenShift platform-level encryption at rest
- Non-secret IdP configuration (issuer URLs, attribute mappings, discovery endpoints) and group-to-role mappings reside in Postgres

#### Authentication Boundaries

- Cloud Infrastructure Admins authenticate via OpenShift OAuth
- Cloud Provider Admins, Tenant Admins, and Tenant Users authenticate through OSAC identity stack
- OSAC users do not become OpenShift Users
- OSAC never creates OpenShift User objects

#### Built-in Break-Glass Accounts

- One break-glass account per organization (including `System` Organization)
- Break-glass accounts have the `idp-manager` role with limited privileges: can only manage IdP configuration (view, update, test, view health) for their organization
- Break-glass accounts cannot: create/delete organizations, manage users, assign roles, create projects, or perform any other administrative actions
- Break-glass accounts are stored in OSAC Postgres tables (source of truth) and synchronized to Dex Postgres storage via gRPC API
- Accounts always remain available for break-glass access, regardless of IdP configuration
- Purpose: Recover from IdP failures or misconfigurations to restore normal authentication
- Regular admin accounts (Cloud Provider Admin, Tenant Admin) are separate and authenticate through IdP (or break-glass if IdP is down, but with their normal roles)

#### Dex Configuration Management

Break-glass account management uses Dex's Postgres storage backend with OSAC Postgres as the source of truth.

**Storage Architecture:**
- OSAC Postgres tables store break-glass account metadata and bcrypt-hashed passwords (source of truth, backed up)
- Dex uses Postgres as its storage backend (persistent across pod restarts)
- Accounts synchronized from OSAC to Dex via gRPC API

**Update Flow:**
- When accounts are created/updated/deleted via OSAC API:
  1. OSAC updates its Postgres tables (source of truth)
  2. OSAC service calls Dex gRPC API (`CreatePassword`, `UpdatePassword`, `DeletePassword`)
  3. Changes immediately available for authentication

**Reconciliation:**
- Periodic reconciliation (every 5 minutes) keeps OSAC and Dex storage in sync:
  - Queries OSAC Postgres and Dex `ListPasswords` gRPC method
  - Uses `CreatePassword` for new accounts, `VerifyPassword`+`UpdatePassword` for password changes, `DeletePassword` for removed accounts
- Startup reconciliation ensures consistency when services start
- On restore, OSAC database is restored and reconciliation rebuilds Dex storage from source of truth

### Risks and Mitigations

**Security Risks:**
- Token compromise could allow unauthorized access to organization resources
  - Mitigation: Use short-lived tokens, implement token rotation, use secure token storage
- IdP misconfiguration could expose sensitive data or allow unauthorized access
  - Mitigation: Provide IdP testing endpoints, validate configurations, implement health checks
- Secret storage compromise could expose IdP credentials
  - Mitigation: Leverage OpenShift Secrets with platform-level encryption, implement secret rotation capabilities

**Operational Risks:**
- Dex or Identity Service failure could prevent all authentication
  - Mitigation: Built-in break-glass accounts remain available, implement high availability for critical components
- IdP connectivity issues could prevent user authentication
  - Mitigation: Implement IdP health monitoring, provide fallback mechanisms, alert on failures
- Organization deletion could result in data loss
  - Mitigation: Implement proper lifecycle semantics, provide backup/restore capabilities, require explicit confirmation

**Integration Risks:**
- Version skew between OSAC components and OpenShift could cause issues
  - Mitigation: Define version compatibility matrix, test upgrade scenarios, implement graceful degradation
- Changes to OpenShift Secrets API could break OSAC
  - Mitigation: Monitor OpenShift API changes, implement abstraction layer, test compatibility

### Drawbacks

**Operational Complexity:**
- Introducing Dex, Identity Service, and Authorino adds operational complexity compared to using a single integrated solution like Keycloak
  - Mitigation: Dex is lightweight and stateless, reducing operational burden compared to Keycloak

**IdP Dependency:**
- Organizations become dependent on their IdP availability for user authentication
  - Mitigation: Built-in break-glass accounts remain available, IdP health monitoring helps detect issues early

**Token Management:**
- Users must manage OSAC tokens in addition to IdP credentials
  - Mitigation: Tokens can be stored securely, and SSO flows reduce the need for frequent re-authentication

**OpenShift Coupling:**
- Tight coupling with OpenShift Projects and Secrets means changes to OpenShift could require OSAC updates
  - Mitigation: Use stable OpenShift APIs, implement abstraction layers where possible

## Alternatives (Not Implemented)

### Why Not Keycloak?

Keycloak is a powerful enterprise IAM platform, but it is operationally heavy for OSAC's requirements. It requires a stateful, highly available deployment with a backing database, regular schema migrations, careful clustering, and complex backups. Its multi-tenant model (realms or many external IdPs in a single realm) becomes difficult to manage and scale when each OSAC Organization brings its own IdP. The operational burden would fall directly on the cluster operator and does not align with OSAC's goal of providing a lightweight, easy-to-operate control plane.

OSAC only needs two capabilities: (1) a local identity store for Cloud Provider Admins and Tenant Admins (stored in Dex configuration), and (2) federation to each Organization's IdP. Dex provides exactly these two functions with a small footprint, no database, and simple configuration, while allowing OSAC to fully control role mappings and authorization internally. By storing only group-to-role mappings in the database (not importing users and groups), OSAC avoids reimplementing Keycloak's user management while maintaining full control over role assignment through the OSAC API. This makes Dex a far better fit for OSAC's architecture and operational model than Keycloak.

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

3. Token refresh and rotation policies need to be defined. How long should tokens be valid? What is the refresh mechanism?

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