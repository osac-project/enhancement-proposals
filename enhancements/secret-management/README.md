---
title: secret-management
authors:
  - TBD
creation-date: 2026-01-12
last-updated: 2026-01-12
tracking-link:
  - TBD
see-also:
  - None
replaces:
  - None
superseded-by:
  - None
---

# Secret Management

## Summary

This proposal introduces a comprehensive secret management system for the fulfillment service.
Currently, sensitive data such as kubeconfigs and credentials are stored as plain strings in the
API and persisted as plain text in the PostgreSQL database. This proposal addresses this security
concern by integrating with external secret management systems, using URI-based references to
secrets rather than storing actual values, and providing a flexible mechanism for identifying
secret fields through custom protobuf options.

A key aspect of this design is that secret stores are first-class managed objects within the
fulfillment service. Administrators can create, retrieve, update, and delete `SecretStore` objects
through the API, similar to how they manage `Hub` objects. Each secret store has an identifier,
name, and a specification containing the configuration needed to connect to the backend (type,
hostnames, ports, etc.). The credentials required to authenticate with the secret store backends
are provided to the fulfillment service through command-line options, enabling secure bootstrapping
in Kubernetes environments where these values come from Kubernetes secrets.

## Motivation

Storing secrets in plain text poses significant security risks, including exposure through database
breaches, backup leaks, and unauthorized access. Modern cloud-native applications should leverage
dedicated secret management solutions that provide encryption at rest, access control, audit
logging, and secret rotation capabilities.

The fulfillment service manages sensitive credentials for hub clusters (kubeconfigs), bare metal
management systems, and various integrations. As the O-SAC platform scales, the number of secrets
grows dynamically, making environment variables unsuitable for this use case. A robust, scalable
secret management system is essential for production deployments.

### User Stories

* As a provider, I want sensitive credentials to be stored securely in an external secret store so
  that a database compromise does not expose all secrets.
* As a provider, I want to choose which secret management backend to use (Kubernetes secrets,
  HashiCorp Vault, etc.) so that I can integrate with my existing infrastructure.
* As a provider, I want to manage multiple secret stores through the API so that I can organize
  secrets across different backends or environments.
* As a provider, I want to create, update, and delete secret store configurations through the CLI
  and API so that I can dynamically manage my secret infrastructure.
* As a provider, I want to provide secret store credentials (tokens, passwords) securely through
  command-line options so that they are not stored in the database.
* As a tenant, I want transparent secret fields to automatically handle storage and retrieval so
  that I can work with secret values directly without managing references.
* As a tenant, I want non-transparent secret fields to accept references to externally managed
  secrets so that I can integrate with my own secret management workflows.
* As a security auditor, I want to be able to audit secret access and ensure secrets are not stored
  in plain text in the database.
* As an operator, I want secrets to be automatically resolved at runtime so that applications
  receive the actual values without additional configuration.
* As a developer, I want a clear mechanism to identify which fields contain sensitive data so that
  the system handles them appropriately throughout the data lifecycle.

### Goals

* Introduce `SecretStore` as a first-class managed object that administrators can create, retrieve,
  update, and delete through the API.
* Integrate the fulfillment service with external secret management systems (Kubernetes secrets,
  HashiCorp Vault, and potentially others).
* Define custom protobuf options to mark fields as secrets and control their transparency behavior.
* Store URI-based references to secrets in the database instead of actual secret values.
* Support transparent secret fields (system manages storage/retrieval automatically) and
  non-transparent fields (user provides secret references).
* Create a `SecretResolver` interface in Go that abstracts secret operations (resolve, create, delete).
* Support secure bootstrapping of secret store credentials through command-line options.
* Ensure backward compatibility with existing deployments through a migration path.

### Non-Goals

* Implementing secret rotation is outside the scope of this initial proposal; it may be addressed in
  a future enhancement.
* Building a custom secret storage backend; we will leverage existing solutions.
* Encrypting the entire database; we focus specifically on secret fields.
* Providing a user interface for secret management beyond the existing CLI and API.

## Proposal

The implementation relies on several key components:

* **SecretStore Object**: A first-class managed object representing an external secret management
  backend. Administrators create and manage these through the API, similar to Hub objects.
* **Custom Protobuf Options**: Two protobuf options control secret behavior:
  - `(osac.field).secret = true` marks a field as containing sensitive data
  - `(osac.field).transparent = true` indicates the system should automatically store and resolve
    the secret, making the secret management invisible to the user
* **Secret Reference URIs**: A URI scheme to reference secrets stored in external systems, using the
  format `<secret-store-name>:///<path>` where the secret store name identifies the configured
  `SecretStore` object.
* **SecretResolver Interface**: A Go interface that provides methods to resolve, create, and delete
  secrets across different backends.
* **Credential Bootstrapping**: Secret store credentials (tokens, passwords) are provided via
  command-line options, not stored in the database.
* **Transparency Model**: Fields marked as transparent automatically store values and resolve
  references; non-transparent fields expect and return secret references directly.

### Workflow Description

#### Secret Store Management

Administrators manage secret stores through the fulfillment CLI and API:

1. The administrator creates a new `SecretStore` object by specifying the store type (kubernetes,
   vault, etc.) and configuration properties (hostnames, ports, namespaces, etc.) through the
   fulfillment CLI or API.
2. The fulfillment service validates the configuration and stores the `SecretStore` object in the
   database.
3. When the fulfillment service starts, it reads secret store credentials from command-line options
   (e.g., `--secret-store-property my-vault.token=s.xxxxx`) and associates them with the
   corresponding `SecretStore` objects in memory.
4. The administrator can list, update, or delete secret stores as needed. Deleting a secret store
   that is still referenced by secrets will fail with an error.

#### Transparent Secret Fields

For fields marked with both `(osac.field).secret = true` and `(osac.field).transparent = true`, the
secret management is invisible to the user. The user provides the actual secret value, and receives
the actual value when retrieving the object.

**On Create/Update**:

1. The tenant submits a request containing the actual secret value (e.g., a kubeconfig) through the
   fulfillment CLI or API.
2. The fulfillment service identifies the field as a transparent secret based on both protobuf
   options.
3. The service looks up the default `SecretStore` object configured for transparent secrets.
4. The service generates a unique identifier for the secret and calls the `SecretResolver.Create()`
   method to store the value in the external secret store.
5. The secret reference URI (e.g., `my-k8s-store:///osac-secrets/hub-abc123/kubeconfig`) replaces
   the actual value internally.
6. The reference URI is stored in the PostgreSQL database (the user never sees this).

**On Retrieve**:

1. The fulfillment service loads the object from the database containing the secret reference URI.
2. The service identifies the field as a transparent secret.
3. The service calls `SecretResolver.Resolve()` to retrieve the actual value.
4. The resolved secret value is returned to the user (not the reference URI).

#### Non-Transparent Secret Fields

For fields marked with `(osac.field).secret = true` but without `(osac.field).transparent = true`
(or with `transparent = false`), the user works directly with secret references. The user provides
a reference URI, and receives the reference URI when retrieving the object.

**On Create/Update**:

1. The tenant submits a request containing a secret reference URI (e.g.,
   `my-vault:///secret/data/myapp/credentials`), where `my-vault` is the name of a configured
   `SecretStore` object.
2. The fulfillment service identifies the field as a non-transparent secret.
3. The service validates that the referenced `SecretStore` exists.
4. The service optionally validates that the referenced secret exists by calling
   `SecretResolver.Resolve()`.
5. The reference URI is stored in the PostgreSQL database as-is.

**On Retrieve**:

1. The fulfillment service loads the object from the database.
2. The service identifies the field as a non-transparent secret.
3. The reference URI is returned to the user as-is (no resolution).

**At Runtime** (when the service needs the actual value):

1. The service calls `SecretResolver.Resolve()` to retrieve the actual value using the credentials
   associated with that secret store.
2. The resolved value is used for the operation (e.g., connecting to a hub cluster).

#### Secret Resolution at Runtime

When the fulfillment service needs to use a secret value internally (e.g., to connect to a hub
cluster), it resolves the secret regardless of whether the field is transparent or not:

1. The fulfillment service loads an object from the database containing secret reference URIs.
2. For each secret field, the service parses the URI to extract the secret store name (scheme).
3. The service looks up the `SecretStore` object by name and retrieves its configuration.
4. The appropriate `SecretResolver` implementation is selected based on the secret store's type.
5. The resolver uses the secret store configuration and associated credentials to retrieve the
   actual secret value from the external store.
6. The resolved value is used for the operation.

#### Secret Deletion

1. When an object containing secrets is deleted, the fulfillment service iterates over secret fields.
2. For each transparent secret field, the service calls `SecretResolver.Delete()` to remove the
   secret from the external store (since the system created it).
3. For non-transparent secret fields, the reference is simply removed from the database; the actual
   secret in the external store is not deleted (since the user manages it externally).

### API Extensions

#### SecretStore Object

The `SecretStore` is a first-class managed object that administrators create and manage through the
API. Each secret store has an identifier, name, and a specification containing the configuration
needed to connect to the backend.

```protobuf
message SecretStore {
  // Unique identifier for the secret store.
  string id = 1;

  // Human-readable name for the secret store. This name is used in secret
  // reference URIs as the scheme component.
  string name = 2;

  // Specification containing the secret store configuration.
  SecretStoreSpec spec = 3;

  // Current status of the secret store.
  SecretStoreStatus status = 4;
}

message SecretStoreSpec {
  // The type of secret store backend (e.g., "kubernetes", "vault").
  string type = 1;

  // Key-value pairs containing backend-specific configuration.
  // For Kubernetes: namespace, kubeconfig_context, etc.
  // For Vault: address, mount_path, auth_method, role, namespace, etc.
  map<string, string> properties = 2;
}

message SecretStoreStatus {
  // Whether the secret store is currently reachable.
  bool available = 1;

  // Last time the secret store was successfully accessed.
  google.protobuf.Timestamp last_checked = 2;

  // Error message if the secret store is unavailable.
  string error = 3;
}
```

Example JSON for creating a Kubernetes secret store:

```json
{
  "object": {
    "name": "my-k8s-store",
    "spec": {
      "type": "kubernetes",
      "properties": {
        "namespace": "osac-secrets",
        "kubeconfig_context": "my-cluster"
      }
    }
  }
}
```

Example JSON for creating a Vault secret store:

```json
{
  "object": {
    "name": "my-vault",
    "spec": {
      "type": "vault",
      "properties": {
        "address": "https://vault.example.com:8200",
        "mount_path": "secret",
        "auth_method": "kubernetes",
        "role": "fulfillment-service",
        "namespace": "admin"
      }
    }
  }
}
```

#### Custom Protobuf Options

A new `.proto` file will define the custom field options for marking secrets and controlling their
transparency:

```protobuf
syntax = "proto3";

package osac;

import "google/protobuf/descriptor.proto";

option go_package = "github.com/innabox/fulfillment-service/api/osac";

// FieldOptions extends the standard protobuf field options.
message FieldOptions {
  // Indicates that this field contains sensitive data that should be stored
  // in an external secret management system.
  bool secret = 1;

  // When true, the secret management is transparent to the user:
  // - On create/update: user provides the actual value, system stores it
  // - On retrieve: system resolves the secret and returns the actual value
  // When false (default), the user works with secret reference URIs directly:
  // - On create/update: user provides a reference URI
  // - On retrieve: user receives the reference URI (not resolved)
  // This option only has effect when secret = true.
  bool transparent = 2;
}

extend google.protobuf.FieldOptions {
  FieldOptions field = 50000;  // Extension number in the reserved range
}
```

Usage in message definitions:

```protobuf
message Hub {
  string id = 1;
  string name = 2;

  // The kubeconfig for accessing this hub cluster.
  // This is a transparent secret: users provide the actual kubeconfig value,
  // and the system handles storage/retrieval automatically.
  string kubeconfig = 3 [(osac.field).secret = true, (osac.field).transparent = true];
}

message BareMetalCredentials {
  string endpoint = 1;
  string username = 2;

  // Transparent secret: user provides the actual password.
  string password = 3 [(osac.field).secret = true, (osac.field).transparent = true];

  // Non-transparent secret: user provides a reference URI to an existing secret.
  // Example value: "my-vault:///secret/data/baremetal/api-key"
  string api_key_ref = 4 [(osac.field).secret = true];
}
```

The transparency model provides flexibility:

- **Transparent secrets** are ideal for simple use cases where the user just wants to provide a
  value and not worry about secret management. The system handles everything automatically.
- **Non-transparent secrets** are ideal for advanced use cases where the user wants to manage
  secrets externally (e.g., in their own Vault instance) and just provide references to the
  fulfillment service.

#### Secret Reference URI Format

Secret references use standard URI syntax where the scheme identifies the `SecretStore` object by
name, and the path identifies the secret within that store:

```
<secret-store-name>:///<path>
```

The host component is intentionally empty (hence the triple slash `///`) because connection details
are stored in the `SecretStore` object, not in the URI. This design separates the logical reference
from the physical location.

**Examples with Kubernetes Secret Store**:

Given a `SecretStore` named `my-k8s-store` of type `kubernetes`:

```
my-k8s-store:///osac-secrets/hub-abc123/kubeconfig
```

Components:
- `scheme`: `my-k8s-store` (the name of the SecretStore object)
- `path`: `osac-secrets/hub-abc123/kubeconfig` interpreted as `<namespace>/<secret-name>/<key>`

**Examples with Vault Secret Store**:

Given a `SecretStore` named `my-vault` of type `vault`:

```
my-vault:///secret/data/osac/hub-abc123
my-vault:///secret/data/osac/hub-abc123#kubeconfig
```

Components:
- `scheme`: `my-vault` (the name of the SecretStore object)
- `path`: The path to the secret within Vault
- `fragment`: Optional key within the secret data

This design allows the same logical secret reference to work even if the underlying secret store
configuration changes (e.g., Vault address changes), as long as the `SecretStore` object is updated
accordingly.

### Implementation Details/Notes/Constraints

#### Credential Bootstrapping

Secret stores need credentials (tokens, passwords, API keys) to authenticate with their backends.
These credentials are sensitive and must not be stored in the database. Instead, they are provided
to the fulfillment service through command-line options at startup:

**Command-line options**:

```
--secret-store-property <store-name>.<key>=<value>
--secret-store-property-file <path>
```

Examples:

```bash
# Provide individual properties
fulfillment-service \
  --secret-store-property my-vault.token=s.xxxxxxxxxxxxxx \
  --secret-store-property my-k8s-store.kubeconfig=/path/to/kubeconfig

# Or load from a properties file
fulfillment-service \
  --secret-store-property-file /etc/fulfillment/secret-stores.properties
```

**Properties file format**:

```properties
# Secret store credentials
my-vault.token=s.xxxxxxxxxxxxxx
my-vault.role_id=xxxxx-xxxxx-xxxxx
my-vault.secret_id=xxxxx-xxxxx-xxxxx
my-k8s-store.kubeconfig=/var/run/secrets/kubeconfig
```

**Kubernetes deployment**:

In a typical Kubernetes deployment, these values come from Kubernetes secrets mounted as environment
variables or files:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fulfillment-service
spec:
  template:
    spec:
      containers:
      - name: fulfillment-service
        args:
        - --secret-store-property-file
        - /etc/fulfillment/secret-stores.properties
        volumeMounts:
        - name: secret-store-credentials
          mountPath: /etc/fulfillment
          readOnly: true
      volumes:
      - name: secret-store-credentials
        secret:
          secretName: fulfillment-secret-store-credentials
```

#### SecretResolver Interface

The `SecretResolver` interface in Go provides a unified abstraction for secret operations. Each
implementation receives its configuration from the `SecretStore` object and credentials from the
bootstrapped properties:

```go
package secrets

import "context"

// SecretStoreConfig contains the configuration for a secret store, combining
// the persisted SecretStore spec with runtime credentials.
type SecretStoreConfig struct {
    // Name is the name of the secret store.
    Name string

    // Type is the backend type (e.g., "kubernetes", "vault").
    Type string

    // Properties contains the configuration from SecretStoreSpec.properties.
    Properties map[string]string

    // Credentials contains sensitive values from command-line options.
    // These are never persisted to the database.
    Credentials map[string]string
}

// SecretRef represents a parsed secret reference URI.
type SecretRef struct {
    // StoreName is the name of the SecretStore (from the URI scheme).
    StoreName string

    // Path is the path to the secret within the store.
    Path string

    // Key is the optional specific key within the secret.
    Key string
}

// SecretResolver defines operations for managing secrets in external stores.
type SecretResolver interface {
    // Resolve retrieves the actual secret value from the external store.
    // The ref parameter is the URI reference to the secret.
    // Returns the secret value as a byte slice.
    Resolve(ctx context.Context, ref string) ([]byte, error)

    // Create stores a new secret in the external store and returns its reference URI.
    // The path and key parameters define where to store the secret within this store.
    // The value parameter contains the secret data to store.
    // Returns the URI reference to the stored secret.
    Create(ctx context.Context, path, key string, value []byte) (string, error)

    // Delete removes a secret from the external store.
    // The ref parameter is the URI reference to the secret.
    // Returns an error if the deletion fails; returns nil if the secret does not exist.
    Delete(ctx context.Context, ref string) error

    // Exists checks whether a secret exists in the external store.
    // The ref parameter is the URI reference to the secret.
    Exists(ctx context.Context, ref string) (bool, error)
}

// SecretResolverFactory creates SecretResolver instances for a specific backend type.
type SecretResolverFactory interface {
    // Type returns the backend type this factory handles (e.g., "kubernetes", "vault").
    Type() string

    // Create creates a new SecretResolver instance with the given configuration.
    Create(config SecretStoreConfig) (SecretResolver, error)
}
```

#### Secret Store Manager

The `SecretStoreManager` coordinates secret stores and their resolvers:

```go
package secrets

// SecretStoreManager manages multiple secret stores and their resolvers.
type SecretStoreManager interface {
    // RegisterFactory registers a factory for a backend type.
    RegisterFactory(factory SecretResolverFactory)

    // LoadCredentials loads credentials from command-line options.
    LoadCredentials(properties map[string]string)

    // AddStore adds or updates a secret store configuration.
    AddStore(store *SecretStore) error

    // RemoveStore removes a secret store. Fails if secrets still reference it.
    RemoveStore(name string) error

    // GetResolver returns the resolver for a secret store by name.
    GetResolver(name string) (SecretResolver, error)

    // ResolveURI parses a URI and resolves the secret using the appropriate resolver.
    ResolveURI(ctx context.Context, uri string) ([]byte, error)

    // GetDefaultStore returns the name of the default store for transparent secrets.
    GetDefaultStore() string

    // CreateSecret stores a secret in the default store and returns its reference URI.
    // Used for transparent secret fields.
    CreateSecret(ctx context.Context, path, key string, value []byte) (string, error)

    // DeleteSecret removes a secret from its store.
    // Used when deleting objects with transparent secret fields.
    DeleteSecret(ctx context.Context, uri string) error
}
```

#### Kubernetes Secret Resolver

The Kubernetes resolver implementation will:

- Use the Kubernetes client-go library to interact with the Kubernetes API.
- Support both in-cluster and out-of-cluster configurations.
- Read the kubeconfig path from `SecretStoreConfig.Credentials["kubeconfig"]` if provided.
- Read the target namespace from `SecretStoreConfig.Properties["namespace"]`.
- Use labels to track secrets created by the fulfillment service for cleanup purposes.

Supported properties:
- `namespace`: Default namespace for storing secrets (default: `osac-secrets`)
- `kubeconfig_context`: Specific context to use from kubeconfig

Supported credentials:
- `kubeconfig`: Path to kubeconfig file for out-of-cluster access

#### Vault Resolver

The Vault resolver implementation will:

- Use the official HashiCorp Vault Go client.
- Support various authentication methods (Kubernetes auth, AppRole, token).
- Read connection details from `SecretStoreConfig.Properties`.
- Read authentication credentials from `SecretStoreConfig.Credentials`.
- Use the KV v2 secrets engine by default.
- Handle Vault namespaces for enterprise deployments.

Supported properties:
- `address`: Vault server address (required)
- `mount_path`: KV secrets engine mount path (default: `secret`)
- `auth_method`: Authentication method (`token`, `kubernetes`, `approle`)
- `role`: Role name for Kubernetes or AppRole auth
- `namespace`: Vault namespace for enterprise deployments

Supported credentials:
- `token`: Vault token for token auth
- `role_id`: Role ID for AppRole auth
- `secret_id`: Secret ID for AppRole auth

#### Transparency Determination

The system determines how to handle a secret field based on the protobuf options at compile time,
not by inspecting the value at runtime:

1. If `(osac.field).secret = true` and `(osac.field).transparent = true`: the field is a
   transparent secret. The system expects the actual value on input and returns the actual value
   on output.
2. If `(osac.field).secret = true` and `transparent` is not set or is `false`: the field is a
   non-transparent secret. The system expects a reference URI on input and returns the reference
   URI on output.

This compile-time determination makes the API contract clear and predictable for users.

#### Database Schema

The `SecretStore` objects are stored in the database like other managed objects. The schema will
include:

- `id`: Unique identifier (UUID)
- `name`: Unique name used in secret reference URIs
- `spec`: JSON column containing the SecretStoreSpec (type and properties)
- `status`: JSON column containing the SecretStoreStatus

Secret fields in other objects (Hub, etc.) will contain URI strings referencing secret stores
instead of actual secret values. A migration utility will be provided to convert existing plain-text
secrets to URI references.

#### Configuration

The fulfillment service accepts the following configuration related to secret management:

**Command-line options**:

```
--default-secret-store <store-name>     Default store for transparent secret fields
--secret-store-property <name>.<key>=<value>   Set a credential property
--secret-store-property-file <path>     Load credential properties from file
```

**Example startup**:

```bash
fulfillment-service \
  --default-secret-store my-k8s-store \
  --secret-store-property my-vault.token=s.xxxxxx \
  --secret-store-property my-k8s-store.kubeconfig=/var/run/secrets/kubeconfig
```

The `--default-secret-store` option specifies which `SecretStore` to use when storing secrets for
transparent secret fields. This store must be created through the API before starting the service
with this option.

The secret store configurations (type, address, namespace, etc.) are stored in `SecretStore` objects
managed through the API. Only the sensitive credentials are provided via command-line options.

### Risks and Mitigations

**Risk**: External secret store unavailability could impact service operations.
**Mitigation**: Implement circuit breakers, retries with exponential backoff, and consider caching
resolved secrets with appropriate TTLs. Provide clear error messages and operational runbooks.

**Risk**: Migration of existing plain-text secrets could cause service disruption.
**Mitigation**: Provide a migration tool that can run while the service is operational, processing
secrets in batches. Support a dual-read mode during migration where both plain-text and URI
references are accepted.

**Risk**: Misconfigured secret references could lead to runtime failures.
**Mitigation**: Validate secret references during object creation/update. Provide a dry-run mode
that validates references without storing them.

**Risk**: Orphaned secrets in external stores if deletion fails.
**Mitigation**: Implement a garbage collection mechanism that periodically scans for orphaned
secrets. Use finalizers on Kubernetes secrets to ensure proper cleanup.

**Risk**: Secret store credential management at service startup adds operational complexity.
**Mitigation**: Provide clear documentation and examples for Kubernetes deployments. The credentials
are typically sourced from Kubernetes secrets, which integrates well with existing secret management
practices. Provide health checks that validate secret store connectivity at startup.

**Risk**: Deleting or misconfiguring a `SecretStore` object could break secret resolution.
**Mitigation**: Prevent deletion of secret stores that are still referenced by secrets. Validate
secret store configuration changes before applying them. Provide a dry-run mode for configuration
changes.

### Drawbacks

* Adds operational complexity by requiring an external secret management system.
* Introduces latency for secret resolution, as values must be fetched from external stores.
* Requires careful handling of secret backend failures to avoid cascading service disruptions.
* Migration from plain-text storage requires coordination and testing.

## Alternatives (Not Implemented)

**Database-Level Encryption**: Instead of external secret stores, we could encrypt secret fields at
the database level using PostgreSQL's pgcrypto extension or application-level encryption. This was
rejected because it doesn't provide the same level of access control, audit logging, and secret
rotation capabilities as dedicated secret management systems.

**Environment Variables**: Using environment variables for secrets is a common pattern but doesn't
scale for a dynamic set of secrets. The fulfillment service manages credentials for potentially
hundreds of hubs and integrations, making environment variables impractical.

**Sealed Secrets**: Bitnami Sealed Secrets allow encrypting secrets that can only be decrypted by
the controller running in the cluster. While useful for GitOps workflows, this approach is tightly
coupled to Kubernetes and doesn't provide the flexibility needed for multi-backend support.

**Single Backend Only**: Supporting only Kubernetes secrets would simplify implementation but would
limit flexibility for organizations with existing Vault or other secret management infrastructure.
The pluggable architecture allows for future extensibility.

**Hardcoded Secret Store Configuration**: Instead of making `SecretStore` a managed object, we
could hardcode secret store configurations in the service's configuration file. This was rejected
because it doesn't allow dynamic management of secret stores through the API, requires service
restarts to add or modify stores, and doesn't follow the pattern established by other managed
objects like Hub.

**Store Credentials in SecretStore Objects**: We considered storing secret store credentials
(tokens, passwords) directly in the `SecretStore` objects in the database. This was rejected
because it creates a bootstrapping problem (where do you store the credentials for the secret store
that stores your credentials?) and reduces security by persisting sensitive credentials. The
command-line option approach keeps credentials out of the database and integrates well with
Kubernetes secret management.

**Runtime Mode Detection**: Instead of using the `transparent` protobuf option, we considered
detecting the mode at runtime by inspecting the value format (e.g., if it looks like a URI, treat
it as a reference; otherwise, treat it as a value to store). This was rejected because it makes
the API contract ambiguous and could lead to unexpected behavior if a user's actual secret value
happens to look like a URI. The compile-time `transparent` option makes the contract explicit and
predictable.

## Open Questions [optional]

1. Should we support secret versioning to enable rollback of credential changes?
2. How should we handle secrets during backup and restore operations?
3. Should the system support automatic secret rotation, and if so, how would rotation events be
   propagated to dependent components?
4. What is the appropriate TTL for cached secret values, balancing performance with security?
5. Should `SecretStore` objects be tenant-scoped or global? Currently proposed as global
   (admin-only), but some use cases might benefit from tenant-specific stores.
6. How should we handle secret store credential rotation (e.g., Vault token expiration)?

## Test Plan

Testing will cover the following areas:

* **Unit Tests**: Test each `SecretResolver` implementation with mock backends. Test URI parsing
  logic. Test the `SecretStoreManager` and factory pattern.
* **Transparency Tests**: Test transparent secret fields (value in, value out). Test non-transparent
  secret fields (reference in, reference out). Test that transparent secrets are deleted when the
  parent object is deleted. Test that non-transparent secrets are not deleted.
* **SecretStore CRUD Tests**: Test creation, retrieval, update, and deletion of `SecretStore`
  objects. Test validation of secret store configurations. Test prevention of deleting stores with
  active references.
* **Credential Bootstrapping Tests**: Test loading credentials from command-line options. Test
  loading credentials from property files. Test behavior when required credentials are missing.
* **Integration Tests**: Test against real Kubernetes clusters using kind or similar tools. Test
  against a real Vault instance in a test environment. Test with multiple secret stores configured.
* **Migration Tests**: Test the migration tool with various secret configurations. Verify that
  migrated secrets are correctly resolved.
* **Failure Mode Tests**: Test behavior when the secret backend is unavailable. Test retry and
  circuit breaker logic. Test behavior when credentials expire.

## Graduation Criteria

**Alpha**:
- `SecretStore` CRUD operations implemented in the API
- Kubernetes secret resolver implementation complete
- Credential bootstrapping via command-line options working
- Basic integration with fulfillment service
- Migration tool available
- Documentation for operators

**Beta**:
- Vault resolver implementation complete
- Multiple secret stores tested in parallel
- Performance testing completed
- Operational runbooks published
- Used in at least one production-like environment

**GA**:
- All identified issues resolved
- Comprehensive documentation including Kubernetes deployment examples
- Support procedures established
- Secret store health monitoring implemented
- Successfully running in production

### Removing a deprecated feature

The plain-text secret storage will be deprecated once the new system reaches GA. A migration period
of at least two releases will be provided before removing support for plain-text secrets.

## Upgrade / Downgrade Strategy

**Upgrade**:
1. Deploy the new fulfillment service version with secret management support.
2. Configure the secret backend(s).
3. Run the migration tool to convert existing plain-text secrets.
4. Verify that all secrets are correctly resolved.

**Downgrade**:
Downgrading after migration requires extracting secrets from the external store and converting URI
references back to plain-text values. A reverse migration tool will be provided for emergency
rollback scenarios, though this is not recommended for security reasons.

## Version Skew Strategy

During rolling updates, both old and new versions of the fulfillment service may be running
simultaneously. The new version will support both plain-text secrets and URI references, ensuring
that objects created by the old version continue to work. Once all instances are updated and
migration is complete, the legacy plain-text path can be removed.

## Support Procedures

**Symptom**: Secret resolution failures appearing in logs.
**Diagnosis**: Check connectivity to the secret backend. Verify authentication credentials.
Inspect the secret reference URI for correctness.
**Remediation**: Restore connectivity to the secret backend. Update credentials if expired.
Correct malformed URIs using the CLI or API.

**Symptom**: Orphaned secrets accumulating in external store.
**Diagnosis**: Run the garbage collection tool in dry-run mode to identify orphaned secrets.
**Remediation**: Run the garbage collection tool in delete mode after verifying the orphaned
secrets are safe to remove.

## Infrastructure Needed [optional]

* Development and test instances of HashiCorp Vault.
* CI/CD pipelines updated to include secret management in integration tests.
* Documentation updates in the O-SAC docs repository.
