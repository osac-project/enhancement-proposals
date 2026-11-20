# Clarification Log — OSAC-4730

## Status

- Rounds completed: 3
- Open gaps: 0
- Exit criteria met: Yes

## Current-State Findings

- The fulfillment-service has a shared version value. It defaults to
  `unknown`, can read the Go build revision, and is injected explicitly during
  the container build.
- The fulfillment-service container build uses the supplied version to stamp
  both the service and the `osac` CLI binaries. The CLI already has a
  `version` command that prints the client/service version currently embedded
  in the binary.
- The service binary also has a version command for local/service operation.
- The inspected public API and UI paths do not currently provide a
  user-facing inventory of all deployed component versions.
- The UI container currently publishes a version as an OCI image label, but
  the frontend package metadata is `0.0.0`; a runtime-visible frontend version
  source is therefore not yet established.
- The UI already recognizes these role categories: cloud provider admin,
  tenant IdP manager, tenant admin, and tenant user. The current requirement
  is to display versions for all OSAC components while applying persona- and
  role-aware visibility or access restrictions.

## Round 1 — Current implementation, component inventory, and visibility

The existing implementation means the feature can likely reuse the
fulfillment-service’s version value and build injection rather than introduce
an unrelated versioning mechanism. The remaining questions define the
user-facing behavior and security boundary.

### R1.Q1: Component inventory

You stated that all component versions should be shown. Which deployed
components are in the required inventory for the initial release? Should this
include fulfillment-service, osac-ui, osac-operator, osac-aap,
bare-metal-fulfillment-operator, osac-csi-driver, osac-metering, and the
installer/chart release, or a different list? Should the inventory support
components that are not installed in a particular deployment?

#### Answer

The initial inventory is the set of runtime components and service-tier entries
listed in the Component and service-tier inventory below. Shared APIs and
packaging are not separate inventory rows. The list defines what may be
represented; deployed workloads, enabled tiers, and available version values
determine what appears in a particular deployment.

#### Impact

Defines the component rows, completeness criteria, and behavior for absent or
optional components.

#### Decision (D1)

The feature covers the initial component and service-tier inventory listed
below. Runtime inclusion is determined separately by deployment state, enabled
tiers, and available version values.

---

### R1.Q2: Persona-aware UI visibility

The UI has cloud provider admin, tenant IdP manager, tenant admin, and tenant
user roles. Should every authenticated role see the same complete component
inventory, or should visibility vary by role? A proposed policy is:

- Tenant users and tenant admins see the frontend and public-facing service
  versions needed for support and bug reports.
- Tenant IdP managers follow the tenant-admin visibility unless a separate
  operational need is identified.
- Cloud provider admins and cloud infrastructure admins see the complete
  component inventory.

Should tenant admins see the complete inventory, the public-facing subset, or
another defined set?

#### Answer

Persona awareness or access restrictions are desired, but the exact mapping
between personas/roles and visible component versions is not yet decided.

#### Impact

Defines UI visibility, authorization expectations, and the acceptance matrix
for each role.

---

### R1.Q3: CLI scope and audience

Should the CLI’s version command be expanded to retrieve the same complete
component inventory as the UI, or should it continue to report only the local
CLI/service version? If it reports all components, should it require an
authenticated cloud-admin or infrastructure-admin context, or should
authenticated tenant users also be able to run it?

#### Answer

The requirement is to show all component versions, including the existing CLI
surface unless clarified otherwise. The CLI’s complete-inventory behavior and
role/access expectations remain open.

#### Impact

Defines whether the CLI and UI provide equivalent inventories and whether the
CLI needs a distinct authorization or output policy.

---

### R1.Q4: Backend access boundary

Should the backend version information be available only to authenticated
callers, or should any portion be public for unauthenticated health checks or
support tooling? If authenticated-only, should authorization be limited to
specific administrative roles, or should authentication alone permit the
version read with the UI filtering what each role displays?

#### Answer

Persona-aware restrictions are desired. The authenticated-versus-public
boundary and whether authorization is enforced by role or only by login remain
open.

#### Impact

Defines the security posture, API authorization requirement, and whether the
backend must enforce the same visibility policy as the UI.

---

### R1.Q5: Missing, unavailable, and unknown versions

What should users see when a component is not installed, its version cannot be
retrieved, or its build has an unknown version? Should the inventory show an
explicit state such as “not installed” or “unavailable,” omit the component,
or fail the entire inventory? Should the feature display only component and
version, or also operational metadata such as deployment time?

#### Answer

The Jira and reviewed PR material establish an “unavailable” behavior for a
backend that cannot be reached, but they do not define states for every
component or optional components. Operational metadata is not confirmed as
part of the requirement.

#### Impact

Defines resilient UI/CLI behavior, testable error states, and the boundary
between version information and broader deployment diagnostics.

## Round 2 — Deployment inventory and authorization

The service-enablement implementation was reviewed against OSAC-3046 and the
current repository. OSAC-3046 defines four service-tier switches under
`global.services`: CaaS, VMaaS, BMaaS, and MaaS. The fulfillment-service and
REST gateway receive the corresponding enablement values, the public
Capabilities response reports enabled tiers, and the UI already removes
navigation for disabled tiers. The umbrella chart also conditionally deploys
some platform components, while metering is documented as always deployed.

### R2.Q1: Deployment-derived inventory

The version inventory should be derived from what is deployed and enabled.
Fulfillment-service is always the base component for this feature. Disabled or
undeployed optional components should not appear, and a component with no
version should not create a normal inventory row.

#### Answer

The inventory is deployment-derived. Fulfillment-service is required as the
base component. Other components are included only when deployed and enabled.
Absent components, or optional components with no version, are omitted.

#### Impact

The UI and CLI must consume an inventory that can vary by deployment. The
feature must distinguish an absent optional component from a required component
whose version cannot be obtained.

#### Decision (D2)

Show required components even when their version is unavailable. Show optional
components only when they are deployed, enabled, and have an available version;
omit absent optional components.

---

### R2.Q2: Authorization model

Role definitions are changing under OSAC-3058 toward configurable roles and
granular capabilities. Version visibility may therefore need to map to a
permission rather than a fixed list of current role names.

#### Answer

The UI and CLI inventory must be filtered according to the logged-in user’s
permissions. Each version view may need to map to an authorization permission
rather than relying only on the current hardcoded role names.

#### Impact

Authorization must be enforced by the backend for protected version data, and
the UI must not be the only enforcement point. The PRD should avoid binding
the feature permanently to the current role names while OSAC-3058 is changing
the role model.

---

### R2.Q3: CLI inventory

The CLI should show the inventory available to the logged-in user rather than
always showing a fixed administrator-level list.

#### Answer

The CLI displays the component inventory filtered by the permissions of the
logged-in user.

#### Impact

The CLI and UI share the same authorization-filtered inventory semantics. A
user must not gain access to protected component versions by using the CLI
instead of the UI.

#### Decision (D3)

The CLI shows exactly the inventory the logged-in user is authorized to see.

---

### R2.Q4: Public and protected information

The version feature may expose a public subset without authentication, while
the remaining component information is protected.

#### Answer

Public version information may be shown to unauthenticated callers. All
remaining version information must be subject to authorization enforcement.

#### Impact

The requirements must identify the public subset and require backend
authorization for protected rows. The UI may still require login even when a
public version response exists.

#### Decision (D4)

Unauthenticated access is permitted for the explicitly public version subset;
all other version data is authorization-protected.

---

### R2.Q5: Missing versions and operational metadata

Required components and optional deployed components need different missing
version behavior. Deployment timestamps are a separate kind of operational
metadata.

#### Answer

If a required component’s version is missing, show `unavailable`. If an
optional component is not deployed or has no version, omit it. Deployment
timestamps are out of scope.

#### Impact

Acceptance criteria must cover required-component failure separately from
optional-component omission. The version inventory contains component/version
information only, not deployment timestamps.

#### Decision (D5)

Required-component version failures display `unavailable`; the CLI still
displays its embedded local version when no server URL is configured or the
fulfillment-service is unreachable; absent or unversioned optional components
are omitted; deployment timestamps are out of scope.

---

## Component and service-tier inventory

The repository and OSAC-3046 distinguish platform components from service
tiers. This distinction should be preserved in the PRD:

| Item | Classification | Inventory treatment |
|---|---|---|
| fulfillment-service | Required base component | Always expected; show `unavailable` if its required version cannot be obtained |
| osac-ui | Deployable platform component | Include when the UI chart/workload is deployed and versioned |
| osac-operator | Deployable platform component | Include when the operator is deployed and versioned; individual controllers follow enabled tiers |
| osac-aap | Deployable provisioning component | Include when deployed and versioned; AAP capabilities may vary by configured instance groups |
| osac-metering | Platform component | The umbrella chart documents metering as always deployed; include when the workload is present and versioned |
| bare-metal-fulfillment-operator | Optional dependent component | Include only when BMaaS is enabled and the operator is deployed |
| osac-csi-driver / tenant-cluster CSI integration | Optional integration component | Include only when that integration is deployed and exposes a version |
| CaaS | Optional service tier | Include its service/version information only when enabled and deployed; it requires VMaaS or BMaaS |
| VMaaS | Optional service tier | Include only when enabled and deployed |
| BMaaS | Optional service tier | Include only when enabled and deployed; it controls the bare-metal operator dependency |
| MaaS | Optional service-tier signal | Include only if a deployed, versioned MaaS component exists; the current repository has no MaaS gRPC services or operator controller |
| Shared fulfillment APIs (tenants, projects, users, roles, secrets, networking, storage, events, capabilities) | Always-on functionality within fulfillment-service | Do not create separate component rows unless separately deployed/versioned |
| CRD packages and chart packaging | Deployment artifacts, not runtime components | Do not show as separate user-facing component versions unless a later requirement explicitly asks for package/chart versions |

The current deployment defaults enable all four service tiers, but valid
installations may disable tiers. The component list above defines the initial
inventory; the runtime result is still determined by the deployed workloads,
enabled tiers, and available version values.

## Round 3 — Public surface inventory and permission granularity

### R3.Q1: Surface-specific public versions

The public subset needs to account for the fact that the UI and CLI are
different clients. The UI should not present the CLI binary as a deployed
component, while the CLI may report the UI only when the UI is deployed.

#### Answer

The public version information covers fulfillment-service, the UI, and the
CLI. The UI must not show the CLI. The CLI must not show the UI when the UI is
not deployed or has no version; when the UI is deployed and versioned, its
version may be included in the CLI inventory.

#### Impact

The requirements need a surface-specific inventory rather than one identical
list:

- UI: fulfillment-service version and UI version only when the UI is deployed
  and versioned; no CLI row.
- CLI: fulfillment-service and CLI versions always, plus the UI version only
  when UI is deployed and versioned.
- Additional deployed component versions remain subject to authorization.

#### Decision (D6)

Public version visibility is surface-specific. The UI never displays the CLI
version. The CLI always displays the fulfillment-service and CLI versions; it
displays the UI version only when the UI is deployed and versioned.

---

### R3.Q2: Permission granularity

The remaining choice is whether protected component versions use one general
permission or separate permissions. A minimal recommendation is one
`version.read` capability for the protected inventory, with the public
fulfillment-service/UI/CLI subset available without that capability. Separate
component permissions would provide finer disclosure control but increase role
configuration and testing complexity.

#### Answer

Decided in D7: protected component versions use one `version.read` capability.

#### Impact

The PRD cannot yet define the authorization acceptance matrix for protected
component rows or how custom roles created under OSAC-3058 grant access.

#### Decision (D7)

Use one `version.read` capability for protected component versions. The
fulfillment-service/UI/CLI public subset follows the surface-specific public
visibility rules; all other component versions require `version.read`, enforced
by the backend. Public version responses must not expose protected rows to
unauthorized callers.

## Remaining Gaps

None. Clarification exit criteria are met.
