---
title: netris-ca-support-for-aap-execution-environments
authors:
  - etabak@redhat.com
creation-date: 2026-10-07
last-updated: 2026-10-07
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5971
  - https://redhat.atlassian.net/browse/OSAC-5972
prd: []
see-also:
  - N/A
replaces:
  - N/A
superseded-by:
  - N/A
---

# Netris CA support for AAP execution environments

## Summary

Add a declarative, customer-owned ConfigMap reference for the Netris CA
bundle. The OSAC installer propagates that reference to the AAP configuration
and mounts the bundle as a read-only file in every OSAC-managed execution pod
that runs a Netris call, allowing HTTPS certificate validation to remain
enabled without rebuilding the OSAC execution-environment image. The installer
JSON Schema is also the source for the Enclave Wizard, so the same setting is
available through the supported installation flow without embedding certificate
material in Enclave or OSAC.

The requirements are tracked in [OSAC-5971](https://redhat.atlassian.net/browse/OSAC-5971)
and [OSAC-5972](https://redhat.atlassian.net/browse/OSAC-5972). This proposal
does not have a separate PRD.

## Motivation

OSAC AAP jobs use Netris for network and bare-metal operations. The temporary
`global.networking.netris.validateCerts` setting makes it possible to disable
TLS verification, but it does not provide the CA bundle required when a
customer's Netris controller uses a private or self-signed CA. With validation
enabled, the Ansible execution environment trusts only its existing system
trust store.

The CA is customer configuration and must not be baked into an upstream OSAC
or OSAC AAP image. The supported OSAC path is to mount the CA into the AAP
execution pods created for OSAC-managed container groups. The existing network
configuration and credentials remain environment variables; the CA is a
separate file mount because it has a different owner and rotation lifecycle.

### Goals

- Allow customers to use private, self-signed, or customer-PKI Netris HTTPS
  certificates while keeping `validateCerts: true`.
- Keep the CA bundle outside OSAC images and outside generated network
  credential objects.
- Propagate one consistent endpoint, verification setting, and CA path to all
  Netris-calling AAP jobs.
- Preserve HTTP compatibility for testing and legacy deployments, while
  defining HTTPS with certificate validation as the production path.
- Support CA rotation and rollback through normal declarative configuration
  and AAP job-pod reconciliation.
- Keep a deployment without a custom CA bundle valid for publicly trusted
  Netris certificates.
- Expose the installation-time reference through the installer schema and the
  schema-driven Enclave Wizard flow.

### Non-Goals

- Generating or installing the Netris server certificate.
- Pushing a CA bundle from OSAC into Netris.
- Baking customer CA material into an OSAC or execution-environment image.
- Adding a Secret-based CA contract. A CA certificate chain is trust material,
  not private credential material, for this use case.
- Changing the Netris controller, Netris API, or Netris certificate issuance
  process.
- Making the AAP controller task pod sidecar the supported OSAC fulfillment-job
  integration point.
- Adding custom OSAC UI code or a fulfillment-service API for this
  installation-time setting. Enclave support is schema-driven and does not
  require a custom OSAC page.

## Proposal

The installer exposes an optional customer-owned ConfigMap reference under the
existing Netris networking values. When configured, the AAP configuration
renders a required, read-only ConfigMap volume into each OSAC-managed
container-group pod that can run a Netris-calling job. The Netris Ansible tasks
receive the fixed path through `NETRIS_CA_PATH` and pass it to the Netris
collection as `ca_path`.

The customer configures the Netris endpoint and certificate first, then creates
the corresponding CA bundle ConfigMap in the namespace where the AAP execution
environment runs. OSAC consumes that ConfigMap; it does not create it or
provision the Netris-side certificate.

The proposed public values contract is:

```yaml
global:
  networking:
    netris:
      controllerUrl: https://netris.customer.example
      validateCerts: true
      caBundle:
        configMap: customer-netris-ca-2027
```

The customer-created ConfigMap contains a PEM bundle under the required
`bundle.pem` key. The bundle normally contains the root CA and any required
intermediate CAs, not the Netris leaf certificate or a private key. If the
Netris endpoint uses a publicly trusted certificate, the
`caBundle` block is omitted.

### Workflow Description

The actors are the customer or cloud infrastructure administrator, the Enclave
Wizard, the OSAC installer, AAP config-as-code, an OSAC-managed AAP container
group, the Netris Ansible collection, and the Netris controller.

1. The customer configures the Netris controller to serve HTTPS and obtains
   the CA chain that validates its server certificate.
2. The customer creates a ConfigMap in the AAP namespace, for example:

   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: customer-netris-ca-2027
     annotations:
       osac.openshift.io/tenant: <tenant-identifier>
       osac.openshift.io/owner-reference: <aap-installation-owner>
   immutable: true
   data:
     bundle.pem: |
       -----BEGIN CERTIFICATE-----
       ...
       -----END CERTIFICATE-----
   ```

3. The administrator enters the Netris URL, `validateCerts: true`, and the
   ConfigMap name in the Enclave Wizard, or supplies the equivalent Helm
   values directly. The Wizard emits the same installer values in both cases.
4. The umbrella chart schema validates the values and passes the reference to
   the AAP subchart.
   The AAP configuration stores the reference in its existing namespace-local
   configuration input and renders the managed container-group pod spec.
5. A job assigned to a Netris-calling container group starts in an execution
   pod. The pod mounts the ConfigMap read-only at
   `/etc/netris/ca/bundle.pem` and receives `NETRIS_CA_PATH` pointing to that
   path.
6. Every Netris Ansible request uses the common verification setting and CA
   path. The Netris controller validates the request and returns the result.

The existing Helm-managed network ConfigMap and Secret continue to be injected
with `envFrom`. They provide endpoint-related environment variables, tenant
settings, and credentials. The customer CA ConfigMap is an additional file
mount and does not replace `network-fulfillment-ig`,
`cluster-fulfillment-ig`, or `netris-credentials`.

For a missing ConfigMap or `bundle.pem` entry, Kubernetes prevents the
execution pod from starting and reports `FailedMount`. For an invalid PEM, unknown CA, or
certificate hostname mismatch, the job starts but the Netris TLS request fails.
These failures are intentional and preserve certificate validation rather
than silently falling back to insecure behavior.

The existing OSAC AAP config-as-code inventory in
`osac-aap/collections/ansible_collections/osac/config_as_code/roles/aap/vars/controller.yml`
is the sole source of truth for Netris-calling groups and managed templates.
The implementation must derive the mounted groups and tests from that
inventory rather than maintain a second list. Any deployed BMaaS group that
invokes Netris must be added to the shared inventory first. Every managed job
template assigned to a Netris-calling group is subject to the same launch
policy.

### API Extensions

This enhancement adds no fulfillment-service gRPC methods, CRDs, webhooks,
finalizers, or tenant resources. It adds Helm values and changes the rendered
pod specification used by the OSAC AAP chart and config-as-code.

It changes the behavior of the AAP resources managed by the OSAC AAP chart:
Netris-calling execution pods gain an optional ConfigMap volume and a fixed
CA path. The design does not patch the generated `AutomationController`
resource or already-running pods. AAP and installer maintainers should review
the implementation because the change affects upstream AAP-managed execution
pod behavior.

## UX Alignment

This is an installation-time configuration contract, not a fulfillment-service
API or tenant-runtime UI feature. The Enclave Wizard is nevertheless part of
the supported installer flow. It renders standard controls from the
`osac-installer/charts/osac/values.schema.json` schema; no custom Wizard page
or OSAC UI component is required.

### Enclave Wizard and installer flow

The pipeline is:

```text
osac-installer values.schema.json
        -> Enclave OSAC plugin
        -> Enclave Wizard control
        -> installer values
        -> umbrella Helm chart
        -> AAP subchart/config-as-code
        -> Netris-calling execution pod
```

The installer implementation must add or update the optional
`global.networking.netris.caBundle.configMap` property in `values.yaml`,
`values.schema.json`, and `values-example.yaml`. The property is an optional
string containing only the name of a customer-created, same-namespace
ConfigMap. The schema description must state that the ConfigMap must contain
`bundle.pem`; it must not accept or store PEM contents. The existing Netris URL
and certificate-validation properties must retain their schema descriptions
and production constraints.

The Enclave plugin task consumes this schema change and passes the value
through unchanged. The Enclave Wizard task verifies that the field is rendered
as an optional text input with the schema description and that the generated
installer values contain the ConfigMap name. It does not add certificate-file
upload, secret storage, or custom cross-field UI logic. Syntax and value-shape
validation happen in the Wizard/schema; ConfigMap existence, namespace,
immutability, digest, and permissions are checked by installer deployment
preflight and Kubernetes admission.

The Enclave plugin work is blocked by the installer schema/value work. The
Wizard verification is blocked by the plugin update. Both are required before
the feature is considered available through the supported installation path.

### Implementation Details/Notes/Constraints

#### Installer and chart changes

The implementation spans the umbrella chart and the AAP subchart:

The installer work must also update the operator-facing documentation in
`osac-installer/docs/network-backend.md` and the Helm deployment guide. The
documentation must show the customer-created ConfigMap prerequisite, the
`global.networking.netris.caBundle.configMap` value, the required `bundle.pem`
key, the HTTPS/`validateCerts: true` production path, the Enclave Wizard path,
and CA rotation/rollback. It must explicitly say that the installer does not
create the ConfigMap and that the Enclave Wizard never receives certificate
contents.

Where the installer already has a shared trust-bundle contract, follow the
`bundle.pem` and read-only mount conventions described by
[OSAC-5343](../OSAC-5343-cross-cluster-authentication-and-tls-trust-for-tenant-cluster-workloads/design.md).
This feature differs in ownership: the Netris CA is an external,
customer-provided trust source rather than the installer-managed
cert-manager/trust-manager bundle.

1. Add `global.networking.netris.caBundle.configMap` to the public values,
   example values, and values schema. The CA data key is fixed as `bundle.pem`.
2. Validate the ConfigMap name as Helm input. Omitting the CA block is valid.
   The chart should not contact the Kubernetes API during rendering to verify
   that the object exists.
3. Pass the reference into the AAP subchart for every group in the Netris
   caller inventory and render the existing config-as-code
   `pod_spec_override` input.
4. Use the shared trust-volume helper for the read-only `bundle.pem` mount,
   then set `NETRIS_CA_PATH` for the Netris job configuration. Omit both when
   no bundle is configured.
5. Verify that every group in the Netris caller inventory receives the same
   endpoint, verification, and CA-path configuration.

The installer test set must include schema validation, offline Helm rendering
with and without the optional reference, propagation into the AAP subchart,
and a deployment-preflight failure for a missing or unauthorized reference.
The Enclave test set must verify schema-driven rendering and value pass-through;
it must not introduce a second configuration contract.

The platform administrator creates the customer-owned ConfigMap and registers
its exact namespace/name in the release-scoped OSAC binding used by the AAP
deployment. The required tenant and owner-reference annotations remain useful
metadata, but they are informational and are never used as authorization
evidence. The installer and admission controls authorize only the registered
namespace/name for the matching OSAC release.

The existing `network-fulfillment-ig` ConfigMap and Secret are Helm-managed
environment-variable sources. The optional `netris-credentials` Secret is
also an environment-variable source. The customer Netris CA ConfigMap is
owned by the customer and is mounted separately as trust material. Keeping
these objects separate permits independent CA rotation and avoids changing
the credentials contract.

The protected Netris input contract is implemented by one shared AAP
launch-input helper. The helper recursively normalizes nested or aliased input
names by case-folding and flattening them before comparison. Its protected set
is the controller URL and its `controller_url`/`netris_controller_url`/
`NETRIS_CONTROLLER_URL` aliases, the verification setting and its
`validate_certs`/`netris_validate_certs`/`NETRIS_VALIDATE_CERTS` aliases, and
the CA path and its `ca_path`/`netris_ca_path`/`NETRIS_CA_PATH` aliases. The
`envFrom` renderer and AAP API launch path both call this helper. Kubernetes
pod admission verifies the resulting explicit values and approved references;
it does not reimplement launch-input normalization. The generated ConfigMap
data must omit protected names, and the pod spec must add chart-owned explicit
values after general `envFrom` entries. Render and launch tests must cover
collisions in both the ConfigMap and Secret sources.

#### Ansible behavior

Every Netris `uri` call, including authentication, read, create, update, and
delete operations in the controller and steps collections, must use one
shared task include or module-defaults helper for the chart-owned
`controller_url`, `validate_certs`, and `ca_path` values. This plumbing is
defined once so it cannot drift between callers. The implementation must
confirm the exact Netris collection support for `ca_path`.

The chart-generated controller URL, `NETRIS_VALIDATE_CERTS`, and
`NETRIS_CA_PATH` values are authoritative. Managed job templates must not
expose any of them as user-overridable extra variables. The AAP job templates
must set
`ask_variables_on_launch: false`, the launch role must not grant permission to
edit protected extra variables, and the launch role must route direct API
requests through the shared launch-input helper. Config-as-code must fail
before creating or updating a job template if it cannot enforce this
allowlist. Tests must cover UI and direct API attempts to override TLS
variables or redirect the endpoint; Ansible variable precedence is not a
security boundary.

The production contract requires an HTTPS controller URL. The production
chart rejects an `http://` URL and exposes no HTTP bypass value. HTTP
compatibility is tested only by a separately packaged test fixture that is not
included in the production chart or selectable through production values. Such
a fixture uses synthetic credentials and an isolated endpoint; it is never a
supported production configuration.

#### AAP topology

The supported OSAC path is the external AAP execution pod created for an
OSAC-managed container group. The AAP controller task pod and its persistent
execution-environment sidecar are controller infrastructure and are not a
substitute for mounting the CA into the job pod.

Only OSAC-managed job templates and registered container groups may invoke
Netris. Config-as-code must maintain the template-to-group allowlist, AAP RBAC
must prevent tenant users from editing protected templates or container-group
assignments, and the launch boundary must reject direct API launches that do
not reference an approved managed template. An external container group is
supported only after it is registered in the same inventory and receives the
same pod-spec and protected-input contract.

The managed execution contract is one release-scoped allowlist derived from
that config-as-code inventory. It includes each template's project, inventory,
execution environment, credential bindings, container group, and pinned source
revision. AAP RBAC/API policy, the launch-input helper, Kubernetes admission,
and installer preflight consume this allowlist; they must not create separate
allowlists. Tenant users cannot modify these OSAC-owned dependencies or run a
tenant-controlled project, inventory, execution environment, credential, or
source revision with Netris credentials.

The OSAC AAP chart currently renders the higher-level
`AnsibleAutomationPlatform` resource and does not expose raw child
`AutomationController.spec.extra_volumes` or
`spec.ee_extra_volume_mounts` fields. Directly patching those child fields or
generated job pods is therefore not the integration contract for this feature.

#### CA rotation procedure

Customers should rotate the CA using immutable, versioned ConfigMaps. The
platform administrator must control creation, replacement, and deletion of
these ConfigMaps through namespace RBAC and, where available, admission
policy. A normal namespace writer must not be able to replace the trust root
used by OSAC jobs.

1. Create a new ConfigMap, for example `customer-netris-ca-2027`, containing
   the new root and intermediate chain. During a planned overlap period, the
   bundle can contain both old and new trust anchors if the certificate
   transition requires it.
2. Update `caBundle.configMap` through the normal Helm values and reconcile
   AAP config-as-code.
3. Verify that a newly created execution pod has the new
   `/etc/netris/ca/bundle.pem` content and that a real HTTPS Netris operation
   succeeds with `validateCerts: true`.
4. Remove the old trust anchor only after all relevant Netris server
   certificates and jobs have moved to the new chain.
5. Retain the previous ConfigMap until rollback is no longer required, then
   remove it according to the customer's configuration-management policy.

If the new certificate fails, restore the previous ConfigMap reference and
reconcile. Existing running pods are not changed in place; verification must
be performed with a newly created job pod.

#### CA ConfigMap ownership policy

The platform installation must provide namespace RBAC that grants create,
update, and delete access for the configured CA ConfigMaps only to the
deployment administration role. It must create an `osac-netris-ca-admin`
Role and RoleBinding for that role, with no write permissions granted to
tenant or job-launcher service accounts. A validating admission policy or
webhook named `osac-netris-ca-policy` must require
`immutable: true`, the platform's versioned CA naming convention, and an
allowlist binding the ConfigMap namespace/name to the OSAC release reference.
The policy must set `failurePolicy: Fail`, validate the AAP namespace and
OSAC release binding from release-scoped admission state rather than trusting
caller-supplied annotations, and reject delete-and-recreate substitution of
the active reference by non-administrators. AAP RBAC and API policy must reject
direct launches that do not use an approved managed template. Kubernetes
admission must reject resulting job pods that reference an unapproved
namespace/name, an unapproved `bundle.pem` content digest, or an unapproved
execution dependency. The release binding stores the exact ConfigMap
namespace/name, the SHA-256 digest of `bundle.pem`, and the authorized OSAC
release principal. These controls are platform-admin-owned and cannot be
changed by namespace writers. The
installer deployment preflight must verify the effective Role, RoleBinding,
release binding, and admission policy before accepting a configured `caBundle`;
if they are absent, the configured custom-CA deployment is unsupported. The
active ConfigMap is referenced by its immutable namespace/name, and rotation
creates a new versioned name before the Helm reference changes. Helm rendering
remains offline and does not contact the Kubernetes API.

### Security Considerations

Certificate validation remains enabled by default. A custom CA reference
narrows trust to the supplied chain and does not disable hostname validation.
The Netris server certificate must contain a subject alternative name matching
the configured controller URL.

The CA ConfigMap is mounted read-only in the AAP namespace and is not logged
or copied into job output. No private key is required. The [CA ConfigMap
ownership policy](#ca-configmap-ownership-policy) must prevent a namespace
writer from replacing the trust root used by OSAC jobs. The values schema must
reject malformed references such as an empty ConfigMap name. PEM parsing is a
runtime responsibility of the TLS client; invalid PEM content must fail the
Netris operation rather than being accepted as an empty trust store.

The production chart rejects `validateCerts: false`. A separate, explicitly
selected non-production test profile may retain it for controlled temporary
diagnosis, but it is not a production solution. HTTP is similarly restricted
to the dedicated test fixture.

### Failure Handling and Recovery

| Failure | Expected behavior | Recovery |
|---|---|---|
| Invalid ConfigMap name in Helm values | Helm schema or render validation fails before deployment | Correct the values and render again |
| ConfigMap or `bundle.pem` entry does not exist | Execution pod remains pending with Kubernetes `FailedMount`; no Netris call runs | Create the immutable object in the AAP namespace or correct the reference, then reconcile |
| Invalid PEM content | Netris TLS request fails with a certificate/CA parsing error | Replace the ConfigMap with a valid PEM chain and create a new job pod |
| CA does not sign the Netris certificate | TLS verification fails; the job reports failure | Supply the correct root/intermediate chain |
| Hostname/SAN mismatch | TLS verification fails even when the CA is trusted | Use a controller URL matching the certificate SAN or fix the Netris certificate |
| HTTP endpoint in a production release | Helm validation rejects the deployment | Use HTTPS; test HTTP only with the dedicated non-production fixture |
| HTTP endpoint in the non-production fixture | Certificate validation and CA path are unused; credentials and operations are unprotected | Use HTTPS for production |
| `validateCerts: false` in a production profile | Helm or profile validation rejects the deployment | Use a trusted CA with verification enabled |
| CA rotation breaks new jobs | Newly created jobs fail while old pods may continue with their mounted content | Follow the [CA rotation procedure](#ca-rotation-procedure) |
| Job-level TLS override is supplied | The AAP launch boundary rejects the conflicting extra variable | Remove the override and use the chart-managed values |
| Netris API or network failure | Existing Ansible retry and job failure behavior applies | Inspect AAP job output and Netris health, then retry the idempotent operation |

The chart must not silently change `validateCerts` to false when a CA is
missing or invalid. A failed job or pod mount is safer and more diagnosable
than insecure fallback.

### RBAC / Tenancy

No new OSAC tenant resource is introduced. The ConfigMap is namespace-scoped,
must carry the existing tenant and owner-reference annotations, and must be
created in the AAP execution namespace. Those annotations are informational;
authorization comes from the controller-owned release binding, the exact
namespace/name allowlist, and platform-admin-owned RBAC and admission policy.
The AAP-managed execution pod mounts it through the same-namespace boundary;
cross-tenant references are invalid. The CA is not exposed through the
fulfillment-service API or tenant-facing resource status.

### Observability and Monitoring

No new metrics are required. Existing Kubernetes and AAP signals provide the
necessary evidence:

- Kubernetes pod events show `FailedMount` for a missing ConfigMap or
  `bundle.pem` entry.
- AAP job output shows the Netris TLS or API error without printing CA data.
- The job's existing success or failure status indicates whether the Netris
  operation completed.
- For rotation verification, use the mounted-file and real HTTPS checks in the
  [CA rotation procedure](#ca-rotation-procedure).

### Risks and Mitigations

- **A Netris-calling group is missed.** Maintain the canonical Netris caller
  inventory above, render tests for every row, and run real BMaaS/IPAM
  validation.
- **The customer references the wrong trust chain.** Document root and
  intermediate ordering, SAN requirements, and the failure symptoms.
- **The external ConfigMap lifecycle is mishandled.** Apply the canonical
  [CA ConfigMap ownership policy](#ca-configmap-ownership-policy) and
  [CA rotation procedure](#ca-rotation-procedure).
- **Chart and AAP config-as-code versions are skewed.** Gate the feature on a
  compatible installer/chart/image set and test both configured and omitted
  CA paths.
- **Customers use insecure validation bypass as a permanent solution.** Reject
  `validateCerts=false` in production profiles and document it only in the
  non-production test procedure.
- **The mount is added only to controller infrastructure.** Test the actual
  execution pod produced by each container group, not just the controller task
  pod.

Security review should include the OSAC AAP and installer maintainers because
the design changes trust material handling and AAP pod configuration.

### Drawbacks

Customers must create and maintain one additional ConfigMap and must
coordinate its rotation with the Netris certificate. The implementation also
needs explicit wiring for every Netris-calling container group, which adds
chart and config-as-code complexity. These costs are accepted to avoid baking
customer material into images, modifying cluster-wide trust, or disabling TLS
verification.

## Alternatives (Not Implemented)

1. **Set `validateCerts=false`.** This is the temporary workaround for an
   untrusted test certificate, but it removes server identity verification and
   is not acceptable as the production CA solution.
2. **Bake the customer CA into a derived execution-environment image.** This
   can work operationally, but requires a customer-specific image build and
   rebuild for every CA rotation. It also mixes deployment configuration with
   image content.
3. **Patch `AutomationController.spec.extra_volumes` or the controller
   sidecar.** The current OSAC chart does not expose those fields, and the
   controller task pod is not the execution pod for OSAC fulfillment jobs.
   This does not reliably cover external container-group jobs.
4. **Merge the CA into `network-fulfillment-ig` or its Secret.** Those objects
   are environment-variable and credential inputs managed with a different
   lifecycle. Merging trust material would make ownership and rotation less
   clear.
5. **Use a cluster-wide trust bundle.** This broadens trust for unrelated
   workloads and makes the customer's Netris CA harder to scope and rotate.

## Test Plan

The test plan covers chart rendering, AAP pod-spec rendering, and real Netris
operations. The current validation environment is a dedicated OSAC AAP test
environment; the production-like flow should use a customer-like private CA rather than
the temporary `validateCerts=false` workaround.

### Unit Tests

The unit/render layer covers the schema, values propagation, Ansible task
parameters, and the protected launch-variable allowlist. The scenario matrix
below is the authoritative mapping of behavior to test layer.

### Integration Tests

The integration layer renders the umbrella/AAP charts and exercises Kubernetes
pod mounts, admission controls, and config-as-code reconciliation. It does not
replace the real multi-component operations in the E2E layer.

### E2E Tests

The E2E layer runs the real Netris, networking/IPAM, cluster fulfillment, and
deployed BMaaS/BareMetalHost operations in the dedicated OSAC AAP validation
environment. It must inspect the actual external execution pod and its mounted
file, not only the AAP controller task pod.

| Scenario | Unit/render | Integration | E2E |
|---|---|---|---|
| Omitted CA with public/system trust | Schema and no-bundle render | Pod spec omits volume and path | Public-CA operation succeeds |
| Private CA with HTTPS and validation enabled | Values and Ansible parameter render | Every applicable caller group has the read-only mount and approved ConfigMap identity | Real networking, cluster, and BMaaS operations succeed |
| Missing ConfigMap or `bundle.pem` | Reference validation | Pod admission and `FailedMount` behavior | Job does not reach Netris |
| Wrong CA, invalid PEM, or SAN mismatch | Parameter and failure-contract tests | Controlled TLS fixture fails closed | Real job reports TLS failure |
| HTTP compatibility | Test-fixture render only | Non-production fixture uses synthetic credentials and an isolated endpoint without the CA path | HTTP succeeds only in the fixture; production chart rejects HTTP |
| Disabled TLS verification | Production profile rejects `validateCerts=false` | Test profile accepts it only for controlled diagnosis | No production E2E coverage; the private-CA path is the supported solution |
| TLS or endpoint launch override | Protected-name allowlist tests | AAP API policy rejects uppercase/lowercase aliases and endpoint redirects | UI and direct API launch attempts are rejected |
| Unmanaged template or container group | Managed-template inventory tests | AAP RBAC/API policy rejects unregistered templates and groups; Kubernetes admission rejects resulting pods | Only approved managed jobs can invoke Netris |
| Cross-tenant CA reference | Release-binding and namespace validation; forged annotations are rejected | Admission rejects a foreign namespace/name or release binding | No cross-tenant job is created |
| `envFrom` collision | ConfigMap/Secret render collision tests | Explicit chart-owned values override general `envFrom` entries | A real job uses the rendered endpoint, verification, and CA path |
| CA rotation and rollback | Reference update render | Namespace/name admission and new-pod mount verification | Execute the [CA rotation procedure](#ca-rotation-procedure) and validate the resulting Netris operation |


## Graduation Criteria

- **Dev Preview:** Helm schema and render tests pass for configured and
  omitted CA bundles; AAP pod-spec tests show the mount on every Netris-calling
  group; and missing ConfigMap, bad PEM, unknown CA, and SAN mismatch failures
  are documented.
- **Tech Preview:** A real private-CA HTTPS operation succeeds with
  `validateCerts=true` for networking/IPAM, cluster fulfillment, and the
  deployed BMaaS Netris-calling group. HTTP compatibility and negative TLS
  cases are verified, and the canonical CA rotation procedure is exercised.
- **GA:** The installer and AAP configuration are released as a compatible
  set, customer installation and support documentation is complete, and at
  least one production-like deployment has completed the rotation and
  rollback procedure without requiring `validateCerts=false`.

## Upgrade / Downgrade Strategy

An upgrade without `caBundle` is backward compatible for publicly trusted
Netris endpoints. A configured private CA requires the compatible installer,
AAP config-as-code, and Ansible task versions described above. Follow the [CA
rotation procedure](#ca-rotation-procedure) when changing the reference.

Removing the values reference removes the mount and returns to system trust.
That is safe only after the Netris certificate is publicly trusted or the
customer accepts the resulting connection failure.

A downgrade to a version that does not understand the new values ignores the
CA configuration, so private-CA HTTPS jobs may fail. Restore a compatible
release or a publicly trusted certificate before downgrading.

## Version Skew Strategy

The installer, AAP config-as-code, and Netris Ansible task implementation must
be released as a compatible set. An older task image may receive
`NETRIS_CA_PATH` but fail to consume it, so the feature is not considered
available until the task implementation and pod-spec wiring are both present.

An older installer with a newer image remains compatible for public/system
trust, but it cannot configure the custom CA mount. A newer installer must
continue to render a valid no-bundle configuration for older supported
deployments. Versioned release notes should state the minimum compatible
chart and image versions.

## Support Procedures

When a Netris job fails after enabling a custom CA:

1. Confirm the URL, `validateCerts`, and ConfigMap name in the rendered
   Helm values.
2. Inspect the actual job pod, not only the AAP controller task pod:
   `oc describe pod <job-pod> -n <aap-namespace>`.
3. Check for `FailedMount`, confirm the mounted file exists at
   `/etc/netris/ca/bundle.pem`, and verify that `NETRIS_CA_PATH` points to it.
4. For TLS errors, verify PEM validity, root/intermediate chain, certificate
   SAN, and endpoint DNS resolution.

Support documentation must explain that `validateCerts=false` is available
only in the separately packaged test fixture and that HTTP does not test the
CA path. For CA rotation incidents, use the [CA rotation
procedure](#ca-rotation-procedure).

## Infrastructure Needed

- A customer-like Netris HTTPS endpoint with a private or self-signed CA and
  a certificate whose SAN matches the configured controller URL.
- A dedicated OSAC AAP validation environment with the Netris, networking,
  and BMaaS prerequisites required by the existing test flow.
- A test CA bundle with at least a root and, where applicable, intermediate
  certificate, supplied through a customer-created ConfigMap.
- Access to the OSAC AAP config-as-code definitions and osac-test-infra
  patterns for inspecting container-group job pods and validating the
  networking/IPAM and BMaaS/BareMetalHost flows.
