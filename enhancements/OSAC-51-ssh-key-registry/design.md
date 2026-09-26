---
title: ssh-key-registry
authors:
  - clobrano@redhat.com
creation-date: 2026-09-08
last-updated: 2026-09-25
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-51
  - https://redhat.atlassian.net/browse/OSAC-4510
prd:
  - "prd.md"
see-also:
  - N/A
replaces:
  - N/A
superseded-by:
  - N/A
---

# Public SSH Key Registry

## Summary

Use the existing tenant-scoped Secret resource to register named SSH public keys. A Secret with type SECRET_TYPE_SSH_PUBLIC_KEY stores the key in data["public_key"]. ComputeInstanceSpec and BareMetalInstanceSpec each gain an immutable SecretLocalReference named ssh_key. The instance services resolve the reference within the tenant, and the controllers pass the resolved key to the existing initial access-configuration paths. See [PRD](prd.md) for detailed requirements.

## Motivation

Today, every ComputeInstance and BareMetalInstance creation requires the user to paste the full SSH public key string into `spec.ssh_public_key`. There is no way to name, store, or reuse a key. This is error-prone (a single mistyped character silently derails VM or bare metal access) and diverges from the register-once-reference-by-name model used by AWS EC2 key pairs, GCP, and GitHub.

The existing Secret resource provides the tenant boundary, authorization, storage, lifecycle, and reference patterns needed for this feature. The SSH public key type adds the key-specific validation and data contract without introducing another resource model.

### Goals

- Let tenant users register named SSH public keys for reuse.
- Let tenant users select a registered key when creating a ComputeInstance or BareMetalInstance.
- Validate public keys and provide clear errors for invalid key material.
- Apply tenant isolation and authorization consistently.
- Inject the selected key during the instance's initial access configuration.
- Support key management and instance selection through the API and CLI.

### Non-Goals

- Adding an ssh_key reference field to Cluster in this milestone.
- Providing a separate SshKey resource, database table, storage model, or lifecycle API.
- Providing a separate update or rename operation for registered key names.
- Storing private keys, attaching multiple keys to one instance, or providing key rotation.
- Catalog or template SSH key defaults.
- External secret-manager synchronization or secret-manager operator integration.

## Proposal

Four areas change:

1. **Existing Secret resource**: Add SECRET_TYPE_SSH_PUBLIC_KEY. The Secret data contract uses data["public_key"] for one OpenSSH public key. The normal Secret API, CLI, authorization, tenancy, storage, and lifecycle behavior applies.

2. **ComputeInstance field change**: Add an immutable SecretLocalReference named ssh_key to ComputeInstanceSpec. The reference is tenant-scoped. The former inline ssh_public_key field is removed from the active contract and its field number and name remain reserved.

3. **BareMetalInstance field change**: Add an immutable SecretLocalReference named ssh_key to BareMetalInstanceSpec using the same reference and resolution model as ComputeInstance. The former inline ssh_public_key field is removed from the active contract and its field number and name remain reserved.

4. **CLI extension**: The existing Secret command family supports key registration and lifecycle operations. The ComputeInstance and BareMetalInstance create commands accept --ssh-key and set the corresponding SecretLocalReference by name.

The ComputeInstance controller passes the resolved public key to the existing osac-operator initial guest configuration input. The BareMetalInstance controller passes it to the existing bare metal provisioning input. No separate SSH-key service or downstream operator schema is introduced.

### Workflow Description

#### Registering an SSH key

**Actor**: Tenant Admin or Tenant User.

1. The user creates a Secret with type SECRET_TYPE_SSH_PUBLIC_KEY and data["public_key"] containing an OpenSSH public key.
2. Secret validation requires a non-empty, parseable OpenSSH public key. An optional OpenSSH comment is retained.
3. The Secret is stored under the tenant-scoped name and is available to authorized users in that tenant.

#### Creating a ComputeInstance with a registered key

1. The user submits ComputeInstanceSpec.ssh_key with the registered Secret name.
2. The service resolves the name in the request tenant and verifies the Secret type and non-empty public_key entry.
3. The service stores the canonical Secret reference. The reference cannot be changed after creation.
4. During reconciliation, the controller resolves the Secret and passes the public key to the existing initial guest configuration path.
5. Unsupported guest configurations, including Windows or incompatible first-boot data formats, are rejected before provisioning.

#### Creating a BareMetalInstance with a registered key

1. The user submits BareMetalInstanceSpec.ssh_key with the registered Secret name.
2. The service performs the same tenant-scoped lookup and validation as ComputeInstance.
3. The service stores the canonical immutable Secret reference.
4. During reconciliation, the controller resolves the Secret and passes the public key to the existing initial host provisioning path.

#### Managing a registered key

Secret creation, retrieval, listing, updating, and deletion follow the generic Secret lifecycle and authorization rules. SSH public key injection is an initial configuration operation and does not change access on an already provisioned instance.

### API Extensions

No dedicated SSH-key gRPC service is added.

The existing Secret API gains the SSH public key type and validates data["public_key"]. The existing Secret CLI supports registration from a public-key file and the normal Secret get and delete operations.

ComputeInstances and BareMetalInstances gain the ssh_key field described above. Their create commands accept --ssh-key and resolve the name within the authenticated tenant.

The instance services reject missing, unauthorized, wrong-type, or empty-data references. They canonicalize the reference identity and enforce immutability after creation.

## UX Alignment

The user-facing workflow is registration through the Secret command family followed by selection with --ssh-key during ComputeInstance or BareMetalInstance creation. The API exposes the same model through Secret data and SecretLocalReference fields. No dedicated SSH-key UI or command family is required by this design.

### Implementation Details/Notes/Constraints

#### Secret Type and Validation

The Secret type enumeration includes SECRET_TYPE_SSH_PUBLIC_KEY. A Secret of this type requires a non-empty data["public_key"] entry that parses as one OpenSSH authorized-keys public key. Validation uses the existing OpenSSH validation behavior and preserves an optional trailing comment.

The key remains in the generic Secret data map. There is no SSH-key-specific database table or migration.

#### Instance Field Additions

ComputeInstanceSpec and BareMetalInstanceSpec each add an immutable SecretLocalReference field named ssh_key. The former inline field number and the name ssh_public_key remain reserved in each schema.

The reference contains the Secret identity, not the key material. It is resolved in the resource tenant and cannot be changed after creation.

#### Server and Controller Resolution

At request validation time, each instance service resolves the reference within the authenticated tenant, verifies SECRET_TYPE_SSH_PUBLIC_KEY and data["public_key"], and stores the canonical reference identity.

At reconciliation time, each controller obtains the Secret through the normal Secret client. Missing, unauthorized, wrong-type, and empty-data conditions are classified as reference-resolution failures. The ComputeInstance controller supplies the raw key to the existing guest configuration input. The BareMetalInstance controller supplies it to the existing host provisioning input.

#### Logging and Redaction

Secret request and response logging recursively redacts Secret data, including nested Secret messages and map values, while leaving the original protobuf messages unchanged for normal request processing.

### Security Considerations

Secret authorization and tenant isolation apply to registration and reference resolution. A reference is resolved using the resource tenant, so a Secret from another tenant cannot be selected. Private keys are not accepted.

### Failure Handling and Recovery

| Failure Mode | System Behavior |
|---|---|
| Invalid or empty public key | Secret validation returns InvalidArgument |
| Missing or unauthorized reference | Instance creation or reconciliation returns a reference-resolution failure |
| Wrong Secret type or empty public_key data | The reference is rejected |
| Unsupported ComputeInstance guest configuration | The request is rejected before provisioning |
| Attempt to change ssh_key | The update is rejected because the reference is immutable |
| Secret unavailable during reconciliation | The controller follows its normal failure and retry behavior |

A Secret follows the generic Secret lifecycle. Existing provisioned instances are unaffected by the initial-only nature of SSH-key injection.

### RBAC / Tenancy

Secret operations use the existing tenant-scoped authorization model. Tenant Admin and Tenant User access follows the normal Secret policy. The instance services resolve Secret references within the authenticated tenant and reject cross-tenant references.

### Observability and Monitoring

Existing Secret and instance service metrics and controller conditions apply. Logs may include the tenant-scoped Secret name and failure reason, but never the public_key value.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| A referenced Secret is unavailable during instance preparation | Return a typed reference-resolution failure and follow normal controller retry behavior |
| Public-key data appears in request or response logs | Apply recursive Secret redaction |
| Older clients send the removed inline field | Reserve the field number and name in both protobuf contracts |

### Drawbacks

The generic Secret model is shared with other Secret types, so users and support tooling must understand the SSH public key type and public_key data entry. The benefit is one consistent lifecycle, tenancy, authorization, and reference model for both instance types.

## Alternatives Considered

### Dedicated SSH-key resource

A separate resource would duplicate storage, authorization, tenancy, lifecycle, logging, and CLI behavior.

### Inline key material on each instance

Inline key material repeats validation and exposure points and prevents reuse across instances.

### Copying the key into the instance resource

Copying the key would create multiple sources of truth. The instance stores an immutable Secret reference instead.

## Test Plan

### Unit Tests

- Secret type and public_key validation, including malformed keys and comments.
- Tenant-scoped Secret lookup and cross-tenant rejection.
- Wrong-type and empty-data reference failures.
- Canonical reference identity and ssh_key immutability for both instance types.
- Unsupported ComputeInstance guest configuration.
- Recursive Secret log redaction with unchanged source messages.

### Integration Tests

- Secret create, list, get, update, and delete through the generic interfaces.
- ComputeInstance creation with a valid Secret reference.
- BareMetalInstance creation with a valid Secret reference.
- Controller resolution and typed failures for missing or invalid references.
- Tenant Admin and Tenant User access following Secret authorization policy.

### E2E Tests

- Register a tenant key, create a ComputeInstance using the named key, and verify initial SSH access.
- Register a tenant key, create a BareMetalInstance using the named key, and verify initial SSH access.
- Verify tenant isolation and immutable references.

## Graduation Criteria

- Generic Secret lifecycle operations work for the SSH public key type.
- Tenant isolation and reference immutability are verified.
- ComputeInstance and BareMetalInstance initial access configuration is verified end to end.
- Invalid, missing, wrong-type, and unsupported references produce clear failures.
- Secret data is absent from request and response logs.

## Upgrade / Downgrade Strategy

The removed inline ssh_public_key fields remain reserved as field 7 on ComputeInstanceSpec and field 2 on BareMetalInstanceSpec. The Secret type and instance reference fields are additive API changes.

The instance API and controllers must be deployed with compatible versions so that ssh_key references can be resolved before provisioning. Downgrade follows the standard deployment procedure and must account for resources using the new fields.

## Version Skew Strategy

Deploy the API services and instance controllers as a compatible set. The downstream guest and host provisioning operators continue to receive the resolved public key through their existing inputs.

### Deployment Verification

Verify that the API services and controllers are running the same compatible release, then verify Secret registration and one ComputeInstance and BareMetalInstance provisioning flow using a registered key.

## Support Procedures

For reference-resolution failures, collect the tenant-scoped Secret name, instance identity, controller condition, and typed failure reason. Do not request or print the public_key value. Verify the Secret type, data entry, tenant, and lifecycle state through the normal Secret interfaces.

## Infrastructure Needed

None.

---

## Provenance

Updated from the OSAC-51 requirements and the current OSAC resource and provisioning contracts.
