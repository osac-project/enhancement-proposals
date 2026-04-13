---
title: cluster-as-a-service
authors:
  - Elad Tabak
creation-date: 2026-03-31
last-updated: 2026-04-13
tracking-link:
  - https://redhat.atlassian.net/browse/MGMT-23417
see-also:
  - "/enhancements/vmaas"
  - "/enhancements/bare-metal-fulfillment"
replaces:
superseded-by:
---

# Cluster-as-a-Service


## Summary

This document defines the tenant-facing API contract for the Cluster-as-a-Service
capability. It specifies the Cluster and ClusterTemplate resources, their
endpoints, request/response formats, status semantics, and lifecycle workflows
(create, scale nodes, delete). Clusters are provisioned as HyperShift
HostedClusters on bare-metal hosts managed through HostPools, following the
existing O-SAC fulfillment workflow.


## Motivation

The Cluster-as-a-Service (CaaS) capability already exists in O-SAC, enabling
on-demand OpenShift clusters within a multi-tenant environment. However, the
tenant-facing API has not been formally defined. This proposal specifies the
explicit API contract — the Cluster and ClusterTemplate resources, their
endpoints, lifecycle workflows, and status semantics — so that tenants can
create and manage clusters through a well-defined, self-service interface
without requiring deep infrastructure knowledge.

### User Stories

- As a provider, I want to define cluster templates that my tenants will be
  able to use
- As a tenant, I want to list pre-defined cluster templates with their
  available parameters and host classes
- As a tenant, I want to create an OpenShift cluster based on a pre-defined
  template
- As a tenant, I want to scale the number of nodes in my cluster by adjusting
  node set sizes
- As a tenant, I want to access my cluster via kubeconfig and web console
- As a tenant, I want to retrieve the admin password for my cluster
- As a tenant, I want to delete my cluster and have all associated resources
  cleaned up

### Goals

- Provide a self-service API for tenants to create, manage, and operate
  OpenShift clusters with minimal operational overhead
- Support a catalog of pre-defined cluster templates
- Enable node scaling by allowing tenants to modify node set sizes
- Provide credential access (kubeconfig, admin password, console URL)
- Align with the existing O-SAC fulfillment workflow used by VMaaS

### Non-Goals

The following are explicitly out of scope for this proposal:

- Implementing multi-region cluster placement
- Implementing cluster auto-scaling based on workload demand
- Cluster version upgrades (will be addressed in a separate proposal)
- Advanced networking features such as VPNs, peering, or custom network
  topologies
- Storage provisioning beyond the default StorageClass
- Cluster add-ons management (monitoring, logging, etc.)


## Proposal

The process of fulfilling cluster requests is based on two primary APIs:

* **Cluster**: Represents a provisioned OpenShift cluster that a tenant can
  create and manage. Tenants can only see the clusters they created.
* **ClusterTemplate**: Defined by the provider, this is a pre-configured
  blueprint for clusters. Each template is identified by a unique template ID
  and includes a set of parameters (some required, some optional) that tenants
  can specify when creating a cluster, as well as initial node set definitions.
  Templates are available to all tenants to use; they cannot edit them.

To request a new Cluster, tenants must provide:

* The ID of the desired ClusterTemplate
* Any required or optional parameters for that template
* Optionally, custom node requests specifying host classes and node counts
  (defaults are provided by the template)

The cluster fulfillment process aligns with the existing O-SAC fulfillment
workflows. To support this, the following O-SAC components will be enhanced or
updated:

* **Fulfillment Service**: Defines and exposes the APIs for managing Cluster
  and ClusterTemplate resources.
* **Fulfillment CLI**: Provides tenants with command-line access to the
  Fulfillment Service APIs.
* **O-SAC Operator**: Monitors and reconciles ClusterOrder custom resources
  within the system.
* **O-SAC AAP (Ansible Automation Platform)**: Executes automation tasks (via
  Ansible playbooks) to reconcile ClusterOrder resources, including
  interactions with HyperShift for cluster lifecycle management and ESI for
  bare-metal host allocation.

### Workflow Description

#### Cluster creation

1. The tenant initiates the creation of a new Cluster using the Fulfillment
   CLI. The tenant must provide:
    - The ID of the desired ClusterTemplate
    - All required and any optional parameters for the template
    - Optionally, custom node requests specifying the host class and number of
      nodes for each node set

2. The Fulfillment Service receives this request and performs validation to
   ensure:
    - The specified template exists and is available
    - All required parameters are provided and valid
    - The requested host classes exist

3. Upon successful validation, the Fulfillment Service creates a new
   ClusterOrder custom resource (CR) in the appropriate Hub and namespace.

4. The O-SAC Operator detects the new ClusterOrder CR and begins the
   reconciliation process.

5. The Operator, using Ansible Automation Platform (AAP), automates the
   following steps:
    - Creates a HostPool to allocate the required bare-metal hosts (see
      [Bare Metal Fulfillment](/enhancements/bare-metal-fulfillment) for details)
    - Creates a HyperShift HostedCluster with the allocated hosts as worker
      nodes
    - Configures the cluster according to the template parameters
    - Performs any additional operations required by the selected template

6. The Operator continuously monitors the cluster's status and updates the
   ClusterOrder CR status to reflect the current state, including `api_url`
   and `console_url` when the cluster is ready.

7. The tenant can check the cluster's status at any time using the Fulfillment
   CLI or API, and can access the cluster via the provided API URL and console
   URL.

#### Node scaling

When a tenant requests a change to the node set sizes, the following workflow
is executed:

1. The tenant updates the node set sizes for an existing cluster using the
   Fulfillment CLI or API.

2. The Fulfillment Service validates the update:
    - The host class for existing node sets cannot be changed
    - New node sets can be added
    - At least one node set must remain

3. The Fulfillment Service updates the ClusterOrder CR with the new node
   requests.

4. The Operator detects the configuration change and triggers a
   re-provisioning cycle via AAP.

5. AAP adjusts the HostPool allocation and HyperShift NodePool sizes to match
   the requested node counts.

6. The cluster status is updated to reflect the new node allocation once
   complete.

#### Cluster deletion

When a tenant requests the deletion of a Cluster, the following workflow is
executed:

1. The tenant initiates the deletion of a Cluster using the Fulfillment CLI or
   API by specifying its identifier.

2. The Fulfillment Service receives the deletion request and performs
   validation to ensure:
    - The specified Cluster resource exists
    - The tenant has permission to delete the resource

3. Upon successful validation, the Fulfillment Service deletes the ClusterOrder
   custom resource (CR) from the appropriate namespace.

4. The O-SAC Operator detects the deletion via Kubernetes finalizers: a
   `deletionTimestamp` is set on the ClusterOrder CR, and the Operator begins
   the cleanup process while the finalizer prevents garbage collection.

5. The Operator, using AAP, automates the following steps:
    - Deletes the HyperShift HostedCluster resource
    - Deletes the associated HostPool, releasing all allocated bare-metal
      hosts back to the provider's inventory
    - Performs any additional cleanup operations required by the selected
      cluster template

6. Once cleanup completes successfully, the Operator removes the finalizer,
   allowing Kubernetes to garbage-collect the CR. If the deletion fails, the
   cluster remains in a Deleting state with the finalizer intact to prevent
   orphaned infrastructure.

7. The tenant can confirm the deletion and cleanup via the Fulfillment CLI or
   API.

This workflow ensures that all resources associated with the Cluster are
properly deprovisioned and that no orphaned resources remain.

#### Cluster template management

Cluster templates are centrally managed by the provider using a GitOps
approach. All templates are stored in a version-controlled repository, which
acts as the single source of truth. At regular intervals, an automated job in
Ansible Automation Platform (AAP) synchronizes the latest templates from this
repository to the Fulfillment Service. As a result, any changes to the
templates are automatically and consistently reflected in the Fulfillment
Service. This process ensures that tenants always have access to the most
current catalog of available cluster templates.

### API Extensions

#### Cluster

Tenants do not create Cluster resources directly. Instead, they create a
cluster order via the Fulfillment CLI, which triggers the system to create and
manage the underlying Cluster resource. The Clusters API (`POST /api/fulfillment/v1/clusters`)
is a server-internal operation not exposed to tenants.

The following example shows a Cluster resource as it appears in the system after
creation, with two node sets:

```json
POST /api/fulfillment/v1/clusters (server-internal)

{
  "spec": {
    "template": "hosted_cluster",
    "template_parameters": {
      "cluster_version": {
        "value": "4.16"
      }
    },
    "node_sets": {
      "compute": {
        "host_class": "acme_1tb",
        "size": 3
      },
      "gpu": {
        "host_class": "acme_1tb_h100",
        "size": 2
      }
    }
  }
}
```

Tenants can check the cluster's status via the Fulfillment CLI or the
`GET /api/fulfillment/v1/clusters/{id}` endpoint:

```json
{
  "@type": "type.googleapis.com/fulfillment.v1.Cluster",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "metadata": {
    "creation_timestamp": "2026-03-31T10:00:00.000000Z",
    "creators": [
      "tenant-user"
    ]
  },
  "spec": {
    "template": "hosted_cluster",
    "template_parameters": {
      "cluster_version": {
        "value": "4.16"
      }
    },
    "node_sets": {
      "compute": {
        "host_class": "acme_1tb",
        "size": 3
      },
      "gpu": {
        "host_class": "acme_1tb_h100",
        "size": 2
      }
    }
  },
  "status": {
    "state": "CLUSTER_STATE_READY",
    "api_url": "https://api.mycluster.example.com:6443",
    "console_url": "https://console.mycluster.example.com",
    "conditions": [
      {
        "type": "CLUSTER_CONDITION_TYPE_READY",
        "status": "CONDITION_STATUS_TRUE",
        "last_transition_time": "2026-03-31T10:30:00.000000Z",
        "message": "The cluster is ready to use"
      },
      {
        "type": "CLUSTER_CONDITION_TYPE_PROGRESSING",
        "status": "CONDITION_STATUS_FALSE",
        "last_transition_time": "2026-03-31T10:30:00.000000Z"
      },
      {
        "type": "CLUSTER_CONDITION_TYPE_FAILED",
        "status": "CONDITION_STATUS_FALSE",
        "last_transition_time": "2026-03-31T10:00:00.000000Z"
      },
      {
        "type": "CLUSTER_CONDITION_TYPE_DEGRADED",
        "status": "CONDITION_STATUS_FALSE",
        "last_transition_time": "2026-03-31T10:00:00.000000Z"
      }
    ],
    "node_sets": {
      "compute": {
        "host_class": "acme_1tb",
        "size": 3
      },
      "gpu": {
        "host_class": "acme_1tb_h100",
        "size": 2
      }
    }
  }
}
```

The cluster can be in one of the following states:

- **Progressing** (`CLUSTER_STATE_PROGRESSING`): The cluster is being created
  or updated.
- **Ready** (`CLUSTER_STATE_READY`): The cluster control plane is operational
  and accessible via the API URL and console URL. Check the DEGRADED condition
  to determine if all requested nodes are available.
- **Failed** (`CLUSTER_STATE_FAILED`): The cluster creation or update has
  failed.
- **Deleting** (`CLUSTER_STATE_DELETING`): The cluster is being deleted.
  Resources are being cleaned up (HostedCluster, HostPool, bare-metal hosts).

The conditions provide additional detail:

- **Progressing** (`CLUSTER_CONDITION_TYPE_PROGRESSING`): The cluster is not
  yet fully ready.
- **Ready** (`CLUSTER_CONDITION_TYPE_READY`): The cluster is ready to use.
- **Failed** (`CLUSTER_CONDITION_TYPE_FAILED`): The cluster is unusable.
- **Degraded** (`CLUSTER_CONDITION_TYPE_DEGRADED`): The cluster is operational
  but not at full capacity (e.g., some requested worker nodes could not be
  allocated). A cluster can be in READY state with DEGRADED condition TRUE if
  the control plane is functional but the worker node count is below the
  requested size.

Tenants can retrieve cluster credentials using the Fulfillment CLI or API:

- **GetKubeconfig**: Returns the admin kubeconfig for the cluster, allowing
  direct access via `oc`, `kubectl`, or other Kubernetes-compatible tools.
- **GetPassword**: Returns the admin password for the cluster console.

#### ClusterTemplate

Cluster templates are implemented as Ansible roles, following the same pattern
as [VMaaS templates](/enhancements/vmaas). Each role defines the cluster
configuration, including default node sets and available parameters.

A periodic job will publish the Ansible roles as cluster templates to the
Fulfillment Service. The following is the API format used for this publication:

```json
{
  "object": {
    "id": "hosted_cluster",
    "title": "Hosted OpenShift Cluster",
    "description": "Provisions a HyperShift HostedCluster on bare-metal hosts.",
    "parameters": [
      {
        "name": "cluster_version",
        "title": "OpenShift Version",
        "description": "The version of OpenShift to install",
        "required": true,
        "type": "type.googleapis.com/google.protobuf.StringValue"
      }
    ],
    "node_sets": {
      "compute": {
        "host_class": "acme_1tb",
        "size": 3
      }
    }
  }
}
```

The template's `node_sets` define the **default** node set configuration. Each
node set specifies the default `host_class` and initial `size`. Tenants can
override the `size` (and optionally add new node sets) when creating a cluster
by including `node_sets` in the cluster creation request. If the tenant does not
specify `node_sets`, the template defaults are used.

### Implementation Details/Notes/Constraints

This proposal is built upon HyperShift, which provides hosted control planes
for multi-tenant OpenShift cluster provisioning. By using HyperShift, each
tenant's cluster gets its own dedicated control plane hosted on the hub cluster,
while worker nodes run on bare-metal hosts allocated via HostPools.

The key architectural decisions are:

- **Hosted control planes**: Each cluster's control plane runs as pods on the
  hub cluster, providing strong isolation between tenants without requiring
  dedicated control plane hardware.
- **Bare-metal worker nodes**: Worker nodes are provisioned on dedicated
  bare-metal hosts via the HostPool mechanism described in the
  [Bare Metal Fulfillment](/enhancements/bare-metal-fulfillment) proposal.
  This provides tenants with full hardware access for their workloads.
- **Node sets**: Clusters support multiple node sets, each with a different
  host class. This allows tenants to mix hardware types (e.g., GPU and
  non-GPU nodes) within a single cluster.
- **Credential access**: Tenants access their clusters through the API URL
  (OpenShift API server) and console URL (OpenShift web console). The Fulfillment
  Service provides endpoints for retrieving the kubeconfig and admin password.
- **Networking**: Cluster networking integrates with HostPool network
  attachments. When a HostPool is created for a cluster, the bare-metal hosts
  are configured with the network attachments specified in the HostPool's
  network configuration. This includes connectivity for the cluster's control
  plane to worker node communication, as well as any tenant-facing network
  access. See the [Bare Metal Fulfillment](/enhancements/bare-metal-fulfillment)
  and [Networking](/enhancements/networking) proposals for details on network
  attachment configuration.

### Risks and Mitigations

TBD

### Drawbacks

#### Cluster creation time

Cluster creation is inherently slower than VM creation due to multi-node
bare-metal provisioning and HyperShift control plane setup. Tenants should
expect creation times on the order of minutes rather than seconds.

#### Bare metal availability

Clusters cannot be created without available hosts matching the requested host
classes. If the system cannot allocate the required number of nodes, the cluster
will be marked as degraded, and the details will be reported in the `DEGRADED`
condition.

#### Node set constraints

Node scaling is limited to changing the node count within existing host classes
or adding new node sets. The host class of an existing node set cannot be
changed after creation. At least one node set must remain at all times.


## Alternatives (Not Implemented)


## Open Questions [optional]


## Test Plan

TBD

## Graduation Criteria

TBD

### Removing a deprecated feature

N/A

## Upgrade / Downgrade Strategy

N/A

## Version Skew Strategy

N/A

## Support Procedures

TBD

## Infrastructure Needed [optional]

N/A
