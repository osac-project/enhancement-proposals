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

### API Changes

#### ClusterSpec — new fields

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

#### ClusterTemplate — no changes

ClusterTemplate is not modified by this proposal. Templates continue to define
default node sets and are published from Ansible roles via the existing periodic
job.

### Implementation Details/Notes/Constraints

The new `ClusterSpec` fields must flow through the full stack:

1. **Proto → Server**: New fields added to `ClusterSpec` proto. Server
   validates values (e.g., CIDR format) and applies defaults when not provided.
2. **Server → Controller**: Controller maps new proto fields to the
   ClusterOrder CR spec. The CR schema needs new fields to carry them.
3. **Controller → Operator → AAP**: Operator reads new CR fields and passes
   them to the AAP provisioning job. The `hosted_cluster` Ansible role is
   updated to use these values instead of hardcoded defaults.

CIDRs use plain string notation in CIDR format (e.g., `10.132.0.0/14`),
consistent with the existing `VirtualNetwork` and `Subnet` proto conventions
and Kubernetes API conventions.

### Risks and Mitigations

- **Invalid CIDR values**: Tenants may provide overlapping or malformed CIDRs.
  Mitigated by server-side CIDR validation, consistent with VirtualNetwork
  and Subnet validation.
- **Backward compatibility**: Existing clusters use `template_parameters`.
  Mitigated by retaining `template_parameters` — the new fields take
  precedence when set, but the old path continues to work.

### Drawbacks

- Adding explicit fields to the proto increases the API surface. Each new
  field requires changes across multiple repos (proto, server, CLI, CR,
  operator, AAP). However, this is the same trade-off already accepted for
  VMaaS and the benefit of discoverability and type safety outweighs it.


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
