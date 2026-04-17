---
title: cluster-as-a-service
authors:
  - Elad Tabak
creation-date: 2026-03-31
last-updated: 2026-04-16
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
the tenant-facing API by adding explicit typed fields to the `ClusterSpec`
protobuf message, following the same approach already taken for VMaaS.


## Motivation

Today, key cluster parameters are either buried in the opaque
`template_parameters` map or hardcoded in Ansible roles. Tenants cannot
discover or control these without knowledge of the underlying templates:

1. **`template_parameters`**: `pull_secret` and `ssh_public_key` are passed as
   untyped `Any` values. Tenants must know the parameter names and types by
   inspecting template definitions.
2. **Hardcoded in Ansible roles**: `release_image` (OCP version),
   pod network CIDR, and service network CIDR are baked into the playbooks.
   Tenants cannot customize these at all.

The VMaaS API has already moved parameters from `template_parameters` to
explicit `ComputeInstanceSpec` fields (`cores`, `memory_gib`, `boot_disk`,
etc.). The CaaS API should follow the same pattern.

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

- Promoting template-specific parameters (e.g., GitHub OAuth settings) to
  `ClusterSpec` — these remain in `template_parameters`
- Exposing provider-managed settings (base domain, availability policies,
  platform type) as tenant-configurable fields
- Changing the cluster creation workflow or operator reconciliation logic —
  this proposal only changes how configuration is passed through the API
- Removing the `template_parameters` field — it is retained for backward
  compatibility and template-specific extensions


## Proposal

Add five explicit fields to `ClusterSpec`. All are optional with sensible
defaults, so existing behavior is preserved.

**Before** (current state):

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
// pod CIDR (10.128.0.0/14) hardcoded in hosted_cluster role
// service CIDR (172.30.0.0/16) hardcoded in hosted_cluster role
```

**After** (proposed):

```json
{
  "spec": {
    "template": "hosted_cluster",
    "pull_secret": "...",
    "ssh_public_key": "ssh-ed25519 ...",
    "release_image": "quay.io/openshift-release-dev/ocp-release:4.17.0-multi",
    "network": {
      "pod_cidr": "10.128.0.0/14",
      "service_cidr": "172.30.0.0/16"
    }
  }
}
```

### Workflow Description

The cluster creation, scaling, and deletion workflows are unchanged. The only
difference is in cluster creation step 1:

**Before:** Tenant passes credentials via `--template-parameter pull_secret=...`
and cannot control OCP version or networking CIDRs.

**After:** Tenant uses explicit CLI flags:

```
osac create cluster \
  --template hosted_cluster \
  --pull-secret <pull-secret> \
  --ssh-public-key "ssh-ed25519 ..." \
  --release-image "quay.io/.../ocp-release:4.17.0-multi" \
  --pod-cidr "10.128.0.0/14" \
  --service-cidr "172.30.0.0/16"
```

All flags are optional. If omitted, the system uses provider defaults (for
credentials) or template/role defaults (for release image and CIDRs).

### API Extensions

New fields added to the `ClusterSpec` protobuf message (public and private):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pull_secret` | string | No | Provider default | Credentials for authenticating to image repositories. Write-only: redacted in GET responses |
| `ssh_public_key` | string | No | Provider default | SSH public key installed on cluster worker nodes |
| `release_image` | string | No | Template default | OCP release image URL. Controls the OpenShift version |
| `network` | `ClusterNetwork` | No | See below | Cluster networking configuration |

The `ClusterNetwork` message groups networking fields together for cleaner
organization as the API grows:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pod_cidr` | string | No | `10.128.0.0/14` | CIDR for the cluster's pod network |
| `service_cidr` | string | No | `172.30.0.0/16` | CIDR for the cluster's service network |

CIDRs use plain string notation (e.g., `10.128.0.0/14`), consistent with the
existing `VirtualNetwork` and `Subnet` proto conventions.

### Implementation Details/Notes/Constraints

The new fields must flow through the full stack:

1. **Proto → Server**: New fields added to `ClusterSpec` proto. Server
   validates values (e.g., CIDR format) and applies defaults. Templates can
   override the system defaults for any field (e.g., a template can set a
   specific `release_image`).
2. **Server → Controller**: Controller maps new proto fields to ClusterOrder
   CR spec. The CR schema needs corresponding new fields.
3. **Controller → Operator → AAP**: Operator reads new CR fields and passes
   them to the AAP provisioning job. The `hosted_cluster` Ansible role uses
   these values instead of hardcoded defaults.

### Risks and Mitigations

- **Invalid CIDR values**: Tenants may provide overlapping or malformed CIDRs.
  Mitigated by server-side CIDR validation, consistent with VirtualNetwork
  and Subnet validation.
- **Backward compatibility**: Existing clusters use `template_parameters`.
  Mitigated by retaining `template_parameters` — the new fields take
  precedence when set, but the old path continues to work.

### Drawbacks

Adding explicit fields to the proto increases the API surface. Each new field
requires changes across multiple repos (proto, server, CLI, CR, operator,
AAP). However, this is the same trade-off already accepted for VMaaS and the
benefit of discoverability and type safety outweighs it.


## Alternatives (Not Implemented)

Keep using `template_parameters` for all configuration. Rejected because it
provides no type safety, no discoverability, and is inconsistent with the
VMaaS API which has already moved to explicit fields.


## Open Questions [optional]

None.


## Test Plan

TBD

## Graduation Criteria

TBD

### Removing a deprecated feature

N/A

## Upgrade / Downgrade Strategy

N/A — new fields are optional and additive. Existing clusters continue to
work via `template_parameters`.

## Version Skew Strategy

N/A — new fields are optional. Older clients that don't set them get defaults.

## Support Procedures

TBD

## Infrastructure Needed [optional]

N/A
