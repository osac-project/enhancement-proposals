---
title: quota-management
authors:
  - Lars Kellogg-Stedman <lars@redhat.com>
reviewers:
approvers:
api-approvers:
creation-date: 2025-09-11
last-updated: 2025-09-11
tracking-link:
see-also:
replaces:
superseded-by:
---

# Quota management

## Summary

We need to implement a quota mechanism for resources allocated by the Open Sovereign AI Cloud solution (OSAC). This proposal defines a generic approval workflow and quota service interface that enables service providers to integrate with their choice of quota management system.

## Motivation

Service providers establish upper limits on the resources tenants can consume for multiple reasons:

- They "sell" chunks of resources (storage, memory, etc) and want to limit tenants to only consume their allocated resources.

- They want to ensure that a tenant cannot accidentally or maliciously consume excessive resources and prevent other tenants from using the service.

### User Stories

- As a service provider, I want to create, modify, and delete resource quotas for a tenant organizations.
- As a service provider, I want to view quota limits and usage for tenant organizations.
- As a tenant, I want to be able to view the resource quota limits and utilization that apply to my organization.
- As a tenant, I want to know when an operation fails due to quota enforcement.

### Goals

TBD.

### Non-Goals

This work is specifically about creating an API and implementation logic for supporting quotas. It does not include any user interface components.

## Proposal

We propose to implement a generic approval workflow in the fulfillment API and to introduce the OSAC Quota Service as a loosely coupled component. When resources are requested via the fulfillment API, they will initially have an `approval_status` of `"pending"`. The OSAC Quota Service will watch for resources in this state, and for each resource will query the fulfillment service for resource usage information and either set the status to `"approved"` or `"denied"` with an appropriate reason.

The OSAC Quota Service will expose an API that can be used to create, modify, list, and get details for quotas. Write operations (create, modify) will require administrative privileges. Read operations (list, get) will permit a tenant to see quotas associated with their organization and will permit an administrator to see values for all tenants.

Quota limits will be stored as sets of arbitrary key/value pairs, in order to support quotas for new resource types in the future without requiring code changes to the quota service.

There are several advantages to this model:

- The generic approval workflow can be used for things other than quota management. For example, a service provider may require a manual approval workflow for certain types of requests.

- The OSAC Quota Service is designed to allow integration with various external systems through its API, allowing service providers to use their existing resource allocation tools (such as ColdFront, custom billing systems, or manual administrative processes) as the authoritative source for quota information.

### Workflow Description

An example workflow may look something like this:

1. A **tenant** requests a new cluster using the fulfillment API.

2. The cluster request is recorded in the fulfillment service with `approval_status` set to `"pending"`, so the fulfillment service takes no further action at this time.

3. The OSAC Quota Service detects the request in `"pending"` state and determines what resources the cluster will consume (e.g., 1 cluster, 8 nodes of various types). It checks its internal usage ledger for the tenant's current usage and compares against their quota limits.

4. The OSAC Quota Service makes an approval decision:
   - **If quotas are satisfied**: Sets `approval_status` to `"approved"` and updates its internal usage ledger to record the newly approved resources. The fulfillment service detects the approval and passes the request to the operator to create the cluster.
   - **If quotas are exceeded**: Sets `approval_status` to `"denied"` and `approval_reason` to explain why (e.g., "Would exceed your quota for nodes.h100 by 3 nodes"). No usage is recorded since the request was denied.

5. **When resources are deleted**: The OSAC Quota Service watches for deletion events and updates its usage ledger to reflect that resources have been freed, making quota available for future requests.

### API Extensions

- This will require all resources that can be requested using the fulfillment API to support new metadata attributes:
  - **`approval_status`** (string): The approval state of the request. Possible values:
    - `"pending"` - Request is awaiting approval (default for new requests)
    - `"approved"` - Request has been approved and can proceed
    - `"denied"` - Request has been denied and will not be fulfilled
  - **`approval_reason`** (string, optional): Human-readable explanation for the approval decision. Required when status is `"denied"`. Examples: "Would exceed your quota by 3 nodes", "Insufficient resources available", "Requested resource class not available in selected region"
- The fulfillment service should record but not otherwise act on requests in `"pending"` or `"denied"` state. Only `"approved"` requests should be processed.
- Changing the `approval_status` and `approval_reason` attributes is a privileged operation and should only be available to fulfillment service administrators
- The fulfillment service may optionally provide APIs for enumerating resources (clusters, compute instances) and their resource consumption to enable the quota service to perform optional reconciliation checks (see Usage Tracking and Reconciliation below)
- The fulfillment service may need to provide an API for resolving requests into measurable resource requirements (see Resource Resolution below for discussion of approaches)

### OSAC Quota Service

The OSAC Quota Service is an independent component that implements the following responsibilities:

- **Watch for pending requests**: Monitor the fulfillment API for resources in `"pending"` approval state
- **Resolve resource requirements**: Determine what measurable resources a request will consume (see Resource Resolution below for approaches)
- **Track resource usage**: Maintain a persistent internal ledger of approved resource consumption by recording approvals and watching for deletions
- **Make approval decisions**: Evaluate whether a request should be approved by comparing the requested resources against the tenant's quota limits and current usage from the persistent ledger
- **Update request status**: Set the `approval_status` to `"approved"` or `"denied"` and provide an `approval_reason` when denying
- **Reconcile usage state** (optional): Optionally reconcile its usage ledger against the fulfillment service's actual resources as a defensive consistency check (see Usage Tracking and Reconciliation below)

The quota service exposes its own API for quota management:

- **Administrative operations** (create, modify, delete quotas): Require administrative privileges
- **Read operations** (list, get quota details): Permit tenants to view their own quotas; administrators can view all quotas

Quota limits are stored as sets of arbitrary key/value pairs to support new resource types without requiring code changes.

### Resource Resolution

A critical component of quota enforcement is determining what measurable resources a request will consume. For example, when a tenant requests a cluster, the system needs to determine:

- How many clusters this will add (typically 1)
- How many nodes will be required (depends on cluster size, control plane nodes, worker nodes)
- What types of nodes (depends on requested resource classes: GPU models like h100/a100, CPU sizes like large/xlarge, etc.)
- What additional resources (if applicable)

**Resolution Mechanism - Two Approaches:**

There are two possible approaches for how the quota service determines resource requirements:

#### Option 1: Resolution API

The fulfillment service provides a dedicated resolution API that accepts a pending request and returns the set of measurable resources it will consume.

**Example Request/Response:**

Given a cluster request specifying:
- 3 control plane nodes (resource class: "large")
- 5 worker nodes (resource class: "h100")

The resolution API returns:
```json
{
  "clusters": 1,
  "nodes.large": 3,
  "nodes.h100": 5
}
```

**Workflow:**
1. Quota service detects a request with `approval_status` of `"pending"`
2. Calls fulfillment service's resolution API
3. Receives calculated resource requirements
4. Checks tenant's quota limits and current usage from internal ledger
5. Sets `approval_status` to `"approved"` or `"denied"` with appropriate `approval_reason`
6. If approved, updates internal usage ledger to record the new resource consumption

**Pros:**
- **Clear separation of concerns**: Fulfillment service owns all resource calculation logic
- **Handles complexity**: If template parameters, defaults, or other factors affect resource consumption, the logic stays in one place
- **Future-proof**: New resource types or calculation rules don't require quota service changes
- **Consistency**: Same calculation logic used for resolution and actual provisioning

**Cons:**
- **Additional API**: Requires implementing and maintaining a new API endpoint
- **Extra call**: Adds latency to the approval workflow
- **Potential duplication**: If resource requirements are already explicit in the request spec

#### Option 2: Direct Resource Inspection

The quota service directly reads the request object (e.g., cluster's `spec.node_sets`) and calculates resource requirements itself.

**Example:**

Reading cluster spec directly:
```json
{
  "spec": {
    "template": "my-template",
    "node_sets": {
      "control-plane": {"host_class": "large", "size": 3},
      "workers": {"host_class": "h100", "size": 5}
    }
  }
}
```

Quota service calculates:
```json
{
  "clusters": 1,
  "nodes.large": 3,
  "nodes.h100": 5
}
```

**Workflow:**
1. Quota service detects a request with `approval_status` of `"pending"`
2. Reads the request object directly from fulfillment API
3. Calculates resource requirements from spec fields
4. Checks tenant's quota limits and current usage from internal ledger
5. Sets `approval_status` to `"approved"` or `"denied"` with appropriate `approval_reason`
6. If approved, updates internal usage ledger to record the new resource consumption

**Pros:**
- **Simpler architecture**: No additional API needed
- **Direct access**: Data already available in the request object
- **Lower latency**: No extra API call
- **Transparent**: Resource requirements visible directly in the spec

**Cons:**
- **Tight coupling**: Quota service must understand fulfillment service's data model
- **Maintenance burden**: Changes to how resources are specified require quota service updates
- **Template complexity**: If templates provide defaults or parameters affect sizing, quota service must duplicate that logic
- **Consistency risk**: Resource calculation logic could diverge between quota checking and actual provisioning

#### Recommended Approach

**Option 1 (Resolution API)** is recommended if:
- Template parameters or defaults can affect resource consumption
- Resource calculation involves complex logic or business rules
- The system prioritizes maintainability and clear service boundaries

**Option 2 (Direct Inspection)** is recommended if:
- Resource requirements are always fully explicit in the request spec
- Templates are purely declarative without defaults or parameter substitution
- The system prioritizes simplicity and performance

**Open Question:** Does the cluster template mechanism allow defaults or parameter-based resource sizing? This will determine which approach is more appropriate.

### Implementation details/notes/constraints

The OSAC Quota Service will be implemented as a standalone service that:

- Maintains its own persistent database for:
  - Quota limits (per tenant, per resource type)
  - Usage ledger (current resource consumption per tenant)
- Exposes an API for managing quotas (create, read, update, delete)
- Watches the fulfillment API for:
  - Pending resource requests (to approve/deny)
  - Resource deletions (to update the persistent usage ledger)
- Makes approval decisions based on quota limits and current usage from the persistent ledger
- Updates request status in the fulfillment API

The quota service is designed to receive quota data from various sources. Service providers can populate quotas through:

- Direct API calls to the quota service
- External systems that push quota updates via the API
- Custom integrations specific to their deployment environment

### Usage Tracking and Reconciliation

The OSAC Quota Service is a persistent service that maintains a database with both quota limits and a usage ledger that tracks resource consumption for each tenant. Since the quota service persists its state, it does not need to query the fulfillment service for current usage on every approval decision.

**Usage Tracking Workflow:**

1. **On Approval**: When the quota service approves a request, it persists the resource consumption in its database:
   - Tenant: `org-123`
   - Resources: `{"clusters": 1, "nodes.h100": 5, "nodes.large": 3}`
   - Total usage for tenant is updated and persisted

2. **On Deletion**: The quota service watches for resource deletion events from the fulfillment API and decrements the usage in its database:
   - When a cluster is deleted, the quota service subtracts its resource consumption from the tenant's usage
   - This frees up quota for future requests

Since the quota service is persistent and maintains authoritative state about approved resources, **reconciliation is not required for normal operation**. However, implementations may optionally choose to perform periodic reconciliation as a defensive measure to detect inconsistencies.

**Optional Reconciliation** (if implemented):

If the fulfillment service provides resource enumeration APIs, the quota service may optionally perform periodic reconciliation (e.g., on startup or scheduled intervals):
- Lists all clusters and compute instances for each tenant
- Calculates actual resource usage
- Compares against its internal ledger
- Corrects any discrepancies (e.g., from bugs, missed events, or manual interventions)

This defensive reconciliation is **not required** but may provide additional confidence in system consistency.

**Design Benefits:**
- **Fast approval decisions**: No need to query fulfillment service for current usage
- **Persistent state**: Quota service maintains authoritative record of approved consumption
- **Resilience**: Service restarts do not lose usage state
- **Accuracy**: Single source of truth for what was approved

### Quota Data Sources

While the OSAC Quota Service itself is generic, different deployments may have different authoritative sources for quota information.

**MOC Deployment with ColdFront:**

In the Massachusetts Open Cloud (MOC) deployment, [ColdFront](https://coldfront.readthedocs.io/en/stable/) serves as the authoritative source for quota allocations. ColdFront is a resource allocation management tool that operates using a push model.

The integration works as follows:

1. Administrators create and manage resource allocations in ColdFront
2. ColdFront uses a service-specific plugin to push quota information to the OSAC Quota Service API
3. The OSAC Quota Service stores these quotas and uses them to make approval decisions
4. When fulfillment requests arrive, the OSAC Quota Service approves or denies them based on the quota data received from ColdFront

ColdFront already has plugins for other cloud platforms:
- OpenShift plugin: creates namespaces and populates them with ResourceQuota objects
- OpenStack plugin: creates quotas using OpenStack service quota APIs

The OSAC plugin would follow a similar pattern, pushing allocation data to the OSAC Quota Service.

**Additional Resources:**
* [What is NERC's ColdFront?](https://nerc-project.github.io/nerc-docs/get-started/allocation/coldfront/) - Information about ColdFront and how it manages resource allocations
* [coldfront-plugin-cloud](https://github.com/nerc-project/coldfront-plugin-cloud) - Example MOC-developed ColdFront plugin for OpenStack and OpenShift

### Risks and Mitigations

N/A

### Drawbacks

N/A

## Alternatives (Not Implemented)

We could implement quota support directly in the fulfillment service, but we were concerned that this solution would bind the fulfillment service too tightly to specific quota management requirements. By implementing the OSAC Quota Service as a separate component with its own API, we enable service providers to integrate with their existing resource allocation tools (like ColdFront at the MOC) while also supporting other quota sources and approval workflows.

## Open Questions [optional]

- **Resource Resolution Approach**: Should the quota service use a Resolution API (Option 1) or Direct Resource Inspection (Option 2)? This decision depends on whether cluster templates support defaults or parameter-based resource sizing. See the Resource Resolution section for detailed comparison of both approaches.

- Need discussion with MOC/commercial on the concept of "unit" aka service unit aka SU (@hpdempsey)

- When we talk about quotas on the number of nodes, this applies to all nodes regardless of whether they are in a cluster or how they are being used (e.g., standalone compute instances vs cluster nodes). The quota system tracks node consumption by resource class, not by how the nodes are organized. (@mhrivnak)

- I would add that while the OSAC Quota Service is a generic component, the ways to populate quota data into it (like the MOC's ColdFront plugin) can and should be tailored to each deployment context. It's especially worth clarifying that we are building a flexible quota service that can integrate with various external quota sources. (@mhrivnak)

## Test Plan

TBD

## Graduation Criteria

TBD

## Support Procedures

TBD

## Infrastructure Needed [optional]

N/A
