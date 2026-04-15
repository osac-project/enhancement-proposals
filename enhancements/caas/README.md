---
title: cluster-as-a-service
authors:
  - Elad Tabak
creation-date: 2026-03-31
last-updated: 2026-04-15
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

This proposal moves cluster configuration out of Ansible templates and into
the tenant-facing API. Today, key cluster parameters are either buried in the
opaque `template_parameters` map (`pull_secret`, `ssh_public_key`) or hardcoded
in Ansible roles (`release_image`, networking CIDRs). Tenants cannot discover
or control these without knowledge of the underlying templates.

This proposal defines explicit typed fields in the `ClusterSpec` protobuf
message for all tenant-configurable cluster parameters, following the same
approach already taken for VMaaS (where `vm_cpu_cores`, `vm_memory`, etc. were
promoted from `template_parameters` to explicit `ComputeInstanceSpec` fields).

This document also formally defines the tenant-facing API contract for the
Cluster-as-a-Service capability, including lifecycle workflows (create, scale
nodes, delete) and status semantics.


## Motivation

Currently, creating a cluster requires passing configuration through two
different mechanisms that are not visible in the API:

1. **`template_parameters`**: An opaque `map<string, Any>` where `pull_secret`
   and `ssh_public_key` are passed as untyped values. Tenants must know the
   parameter names and types by inspecting the template definition.
2. **Hardcoded values in Ansible roles**: `release_image` (OCP version),
   `cluster_network_cidr`, and `service_network_cidr` are baked into the
   playbooks. Tenants have no way to customize these at all.

The VMaaS API has already been updated to move parameters from
`template_parameters` to explicit `ComputeInstanceSpec` fields (`cores`,
`memory_gib`, `boot_disk`, etc.). The CaaS API should follow the same pattern.

By defining explicit `ClusterSpec` fields, the API becomes self-documenting,
the CLI can offer dedicated flags (e.g., `--pull-secret`, `--release-image`,
`--cluster-network-cidr`), and tenants gain control over configuration that is
currently hidden in templates or hardcoded.

### User Stories

- As a tenant, I want to specify my own pull secret when creating a cluster
  so I can use my private image registries
- As a tenant, I want to provide my SSH public key so I can access worker
  nodes for debugging
- As a tenant, I want to choose the OpenShift version for my cluster
- As a tenant, I want to configure cluster and service network CIDRs to avoid
  conflicts with my existing infrastructure
- As a tenant, I want to discover available cluster configuration options from
  the API without inspecting template internals

### Goals

- Define explicit `ClusterSpec` fields for all tenant-configurable cluster
  parameters, replacing the opaque `template_parameters` mechanism
- Allow tenants to control OCP version, credentials, and networking
  configuration through the API and CLI
- Provide sensible defaults so that all new fields are optional
- Align with the approach already taken for VMaaS (`ComputeInstanceSpec`
  explicit fields)

### Non-Goals

The following are explicitly out of scope for this proposal:

- Promoting template-specific parameters (e.g., GitHub OAuth settings) to
  `ClusterSpec` — these remain in `template_parameters`
- Exposing provider-managed settings (base domain, availability policies,
  platform type) as tenant-configurable fields
- Changing the cluster creation workflow or operator reconciliation logic —
  this proposal only changes how configuration is passed through the API
- Removing the `template_parameters` field — it is retained for backward
  compatibility and template-specific extensions


## Proposal

The CaaS capability already exists with two primary resources — **Cluster**
and **ClusterTemplate** — along with working lifecycle workflows (create,
scale, delete). This proposal changes how cluster configuration flows through
the system.

### Current state

Today, cluster configuration reaches the provisioning layer through two
mechanisms:

1. **`template_parameters`**: An opaque `map<string, Any>` on `ClusterSpec`.
   Tenants pass `pull_secret` and `ssh_public_key` here, but the field names
   and types are not visible in the proto definition.

2. **Hardcoded values in Ansible roles**: `release_image` is set in each
   template's `defaults/main.yaml`. `cluster_network_cidr` and
   `service_network_cidr` are hardcoded in the `hosted_cluster` service role.
   Tenants cannot override these.

```json
{
  "spec": {
    "template": "hosted_cluster",
    "template_parameters": {
      "pull_secret": { "@type": "...StringValue", "value": "..." },
      "ssh_public_key": { "@type": "...StringValue", "value": "ssh-ed25519 ..." }
    }
  }
}
// release_image hardcoded in template defaults/main.yaml
// cluster_network_cidr (10.132.0.0/14) hardcoded in hosted_cluster role
// service_network_cidr (172.31.0.0/16) hardcoded in hosted_cluster role
```

### Proposed change

Add five explicit fields to `ClusterSpec`. All are optional with sensible
defaults, so existing behavior is preserved:

```json
{
  "spec": {
    "template": "hosted_cluster",
    "pull_secret": "...",
    "ssh_public_key": "ssh-ed25519 ...",
    "release_image": "quay.io/openshift-release-dev/ocp-release:4.17.0-multi",
    "cluster_network_cidr": "10.132.0.0/14",
    "service_network_cidr": "172.31.0.0/16"
  }
}
```

The changes span multiple components:

* **Fulfillment Service (proto)**: Add the five fields to `ClusterSpec` in
  both public and private proto definitions.
* **Fulfillment Service (server)**: Validate new fields and pass them through
  to the ClusterOrder CR.
* **Fulfillment CLI**: Add dedicated flags (`--pull-secret`,
  `--ssh-public-key`, `--release-image`, `--cluster-network-cidr`,
  `--service-network-cidr`) to the `create cluster` command.
* **Fulfillment Service (controller)**: Map new proto fields to ClusterOrder
  CR spec fields.
* **O-SAC Operator**: Read new fields from ClusterOrder CR and pass them to
  AAP.
* **O-SAC AAP**: Update `hosted_cluster` role to use new CR fields instead
  of hardcoded values and `templateParameters`.

### Workflow changes

The cluster creation, scaling, and deletion workflows remain unchanged. The
only difference is in step 1 of cluster creation:

**Before:** The tenant passes credentials via
`--template-parameter pull_secret=...` and cannot control OCP version or
networking CIDRs.

**After:** The tenant uses explicit flags:

```
fulfillment-cli create cluster \
  --template hosted_cluster \
  --pull-secret <pull-secret> \
  --ssh-public-key "ssh-ed25519 ..." \
  --release-image "quay.io/.../ocp-release:4.17.0-multi" \
  --cluster-network-cidr "10.132.0.0/14" \
  --service-network-cidr "172.31.0.0/16"
```

All flags are optional. If omitted, the system uses provider defaults (for
credentials) or template/role defaults (for release image and CIDRs).

#### Unchanged workflows

Node scaling, cluster deletion, and cluster template management workflows are
not affected by this proposal. They continue to work as currently implemented.
The only change is that the new explicit fields flow through the same pipeline
as the existing `template_parameters` — from `ClusterSpec` to ClusterOrder CR
to the Ansible provisioning roles.

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
    "pull_secret": "<pull-secret-contents>",
    "ssh_public_key": "ssh-ed25519 AAAA...",
    "release_image": "quay.io/openshift-release-dev/ocp-release:4.17.0-multi",
    "cluster_network_cidr": "10.132.0.0/14",
    "service_network_cidr": "172.31.0.0/16",
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
    "pull_secret": "<pull-secret-contents>",
    "ssh_public_key": "ssh-ed25519 AAAA...",
    "release_image": "quay.io/openshift-release-dev/ocp-release:4.17.0-multi",
    "cluster_network_cidr": "10.132.0.0/14",
    "service_network_cidr": "172.31.0.0/16",
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
Deletion is indicated by the presence of a `deletion_timestamp` in the cluster
metadata rather than a separate state. While the cluster is being deleted,
resources are cleaned up (HostedCluster, HostPool, bare-metal hosts) and the
finalizer prevents garbage collection until cleanup completes.

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

#### ClusterSpec changes

The following fields are promoted from `template_parameters` or hardcoded
values to explicit `ClusterSpec` fields. This gives tenants direct control over
cluster configuration without relying on template internals.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pull_secret` | string | No | Provider default | Credentials for authenticating to image repositories. If not provided, defaults are used from the provider's configuration. |
| `ssh_public_key` | string | No | Provider default | SSH public key installed into `authorized_keys` on cluster worker nodes. If not provided, defaults are used from the provider's configuration. |
| `release_image` | string | No | Template default | OCP release image URL (e.g., `quay.io/openshift-release-dev/ocp-release:4.17.0-multi`). Controls the OpenShift version. If not provided, the template default is used. |
| `cluster_network_cidr` | string | No | `10.132.0.0/14` | CIDR range for the cluster's pod network. Tenants may need to customize this to avoid conflicts with existing infrastructure. |
| `service_network_cidr` | string | No | `172.31.0.0/16` | CIDR range for the cluster's service network. Tenants may need to customize this to avoid conflicts with existing infrastructure. |

Existing fields that remain unchanged:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template` | string | Yes | Reference to the cluster template (immutable after creation) |
| `template_parameters` | map | No | Generic parameters (retained for backward compatibility) |
| `node_sets` | map | No | Desired node sets (defaults from template if not specified) |

#### ClusterTemplate

Cluster templates are implemented as Ansible roles, following the same pattern
as [VMaaS templates](/enhancements/vmaas). Each role defines the cluster
configuration, including default node sets.

A periodic job will publish the Ansible roles as cluster templates to the
Fulfillment Service. The following is the API format used for this publication:

```json
{
  "object": {
    "id": "hosted_cluster",
    "title": "Hosted OpenShift Cluster",
    "description": "Provisions a HyperShift HostedCluster on bare-metal hosts.",
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
