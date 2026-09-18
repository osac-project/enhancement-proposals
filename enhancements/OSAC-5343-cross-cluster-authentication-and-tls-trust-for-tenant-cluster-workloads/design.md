---
title: cross-cluster-tls-trust-for-fulfillment-service-clients
authors:
  - derez@redhat.com
creation-date: 2026-09-16
last-updated: 2026-09-16
tracking-link: https://redhat.atlassian.net/browse/OSAC-5343
prd: prd.md
see-also: N/A
replaces: N/A
superseded-by: N/A
---

# Cross-cluster TLS trust for fulfillment-service clients

## Summary

[OSAC-5343](https://redhat.atlassian.net/browse/OSAC-5343) makes the
installer-managed cert-manager and trust-manager bundle the verified trust
source for fulfillment-service clients across management and tenant clusters.
It removes production verification bypasses and distributes the management
trust bundle to OSAC-managed tenant workloads. It covers the operator, CSI,
metering, AAP template-publishing, and installer-hook paths without changing
fulfillment APIs or credential lifecycle. See [PRD](prd.md) for detailed
requirements.

## Motivation

The installer already creates the cert-manager CA named 'default-ca' and
trust-manager publishes its 'ca.crt' as the 'bundle.pem' key of the
'ca-bundle' ConfigMap. That source is available in management namespaces but
not in tenant clusters. Meanwhile, the operator is deployed with
'--grpc-insecure', the tenant CSI driver has no management CA mount, and some
installer hooks use curl with verification disabled. These paths encrypt
traffic but do not authenticate the fulfillment-service endpoint.

This proposal uses the existing CA rather than creating another certificate
authority or a tenant trust-manager installation. The implementation must also
propagate a changed bundle, because a one-time copy leaves a running tenant
client trusting a stale issuer after a CA rotation. The implementation epic is
[OSAC-5343](https://redhat.atlassian.net/browse/OSAC-5343); the PRD remains
tracked by [OSAC-1644](https://redhat.atlassian.net/browse/OSAC-1644).

### Goals

- Reuse the installer-owned 'ca-bundle/bundle.pem' as the sole management CA
  input for fulfillment-service trust.
- Use the established ClusterOrder, AAP, and status-condition patterns without
  adding a fulfillment API, proto, or new user-facing CRD.
- Keep trust material local to OSAC workloads, with tenant and owner-reference
  annotations on every tenant-side resource created by this feature.
- Make CA bundle revisions converge idempotently for both new and existing
  tenant clusters.
- Keep verification bypasses isolated to named test fixtures and absent from
  rendered production manifests.

### Non-Goals

- Issuing certificates, changing the existing cert-manager or trust-manager
  installation, or integrating an external CA.
- Mutual TLS, Keycloak client or credential lifecycle, and Kubernetes
  service-account-token remediation.
- A cluster-wide tenant operating-system trust-store update.
- Changing the TLS behavior of the operator-to-AAP client or the
  guest-cluster kubeconfig route. Those are separate trust relationships, not
  fulfillment-service client traffic.
- Backfilling an unsupported tenant cluster that cannot be reached through its
  ClusterOrder guest-cluster kubeconfig.

## Proposal

The implementation introduces a 'FulfillmentTrustReconciler' in
'osac-operator'. It watches the installer-managed management ConfigMap and
managed ClusterOrders. For every non-deleting ClusterOrder that has a tenant
annotation and a guest-cluster reference, it uses the existing guest kubeconfig
retrieval path and launches one explicit AAP template:
'osac-sync-tenant-fulfillment-trust'. The AAP template server-side applies the
tenant ConfigMap and, if the CSI controller Deployment is present, changes its
pod-template bundle-hash annotation so Kubernetes performs a rollout.

This is deliberately a dedicated reconciler rather than part of the storage
controller. Trust is needed by the tenant CSI client but must not depend on
StorageClasses, a storage backend, or a tenant's storage configuration. The
shared deployment contract below makes the tenant target namespace explicit:
the CSI Helm chart and the AAP template receive the same
'fulfillmentTrust.tenantNamespace' value, whose default is 'osac-csi'.

### Changes per repository

| Repository | Change |
|---|---|
| osac-installer | Retain the existing cert-manager Issuer, Certificate, and trust-manager Bundle. Mount its ConfigMap in fulfillment clients and hooks; remove fulfillment curl verification bypasses. Supply the management source and tenant namespace values to the operator and CSI charts. |
| osac-operator | Add the reconciler, ClusterOrder condition and observed status fields, ConfigMap watch, AAP template configuration, and explicit feedback disposition. Use a CA file for the operator's fulfillment gRPC connection instead of emitting its insecure argument. |
| osac-aap | Add the trust synchronization template. It applies the ConfigMap with the guest kubeconfig, updates the CSI Deployment template hash by label, and waits for its rollout when the Deployment exists. |
| osac-csi-driver | Add a CA ConfigMap volume and a required CA-file argument when a fulfillment endpoint is configured. Use that CA for both fulfillment gRPC and its OAuth token HTTP client. |
| osac-metering | No implementation change expected; retain the existing mounted CA and validate it by regression test. |
| fulfillment-service | No API, proto, database, certificate, or Keycloak contract change. The served endpoint must continue to use a DNS name present in its certificate SANs. |
| tests/e2e | Add regression coverage to the existing CaaS, VMaaS, BMaaS, storage, installer, and AAP paths. |

### Workflow Description

#### Actors and starting state

- A Cloud Infrastructure Admin installs OSAC. The installer creates
  'default-ca', and trust-manager writes 'ca-bundle/bundle.pem' in the
  configured OSAC namespace.
- A Cloud Provider Admin provisions a tenant cluster through a ClusterOrder.
  The ClusterOrder has 'osac.openshift.io/tenant', an owner identity, and a
  populated guest-cluster reference once its control plane is reachable.
- A Tenant Admin uses the OSAC-managed CSI controller in the tenant cluster.
  The controller must call fulfillment service with normal chain and hostname
  verification.

#### Initial synchronization

1. The installer mounts 'ca-bundle/bundle.pem' read-only into management
   operator Pods and fulfillment-related hook Jobs. The operator and hook use
   the configured DNS endpoint and CA file; the hook uses curl '--cacert'.
2. On a ClusterOrder event, the FulfillmentTrustReconciler ignores an object
   without a tenant annotation, guest-cluster reference, or reachable
   kubeconfig. It sets a false condition where appropriate and requeues with
   the standard provisioning backoff.
3. The reconciler reads 'ca-bundle/bundle.pem', validates that it adds at
   least one certificate to a new x509 CertPool, and calculates a SHA-256 hash
   over the exact byte sequence. It never logs the PEM.
4. If the observed hash is already current and the prior AAP job completed,
   reconciliation ends. Otherwise the reconciler launches
   'osac-sync-tenant-fulfillment-trust' with the ClusterOrder identity, tenant
   value, guest kubeconfig, tenant namespace, bundle data, and bundle hash.
5. AAP uses server-side apply with field manager
   'osac-aap-fulfillment-trust' to create or update one ConfigMap named
   'osac-fulfillment-ca'. It preserves no user-owned bundle fields; an apply
   conflict is a failure rather than a forced ownership takeover.
6. AAP lists CSI controller Deployments by the new chart label
   'osac.openshift.io/fulfillment-trust-client=true'. For each match, it sets
   the pod-template annotation
   'osac.openshift.io/fulfillment-ca-sha256=<hash>' and waits for the
   Deployment to become Available. No matching Deployment is a successful
   synchronization: a subsequent CSI install consumes the ConfigMap.
7. The reconciler records the job and bundle hash, then sets
   'FulfillmentTrustReady=True'. The tenant CSI Pod mounts the ConfigMap and
   uses its 'bundle.pem' for gRPC and token HTTPS verification.

~~~mermaid
sequenceDiagram
    participant CM as trust-manager ca-bundle
    participant R as FulfillmentTrustReconciler
    participant AAP as AAP trust-sync template
    participant TC as Tenant cluster
    participant CSI as CSI controller
    participant FS as Fulfillment service

    CM->>R: ConfigMap event, bundle.pem revision
    R->>R: validate PEM and calculate SHA-256
    R->>AAP: kubeconfig, tenant, PEM, hash
    AAP->>TC: server-side apply osac-fulfillment-ca
    AAP->>CSI: patch pod-template hash and wait
    AAP-->>R: job success
    R->>R: set FulfillmentTrustReady=True
    CSI->>FS: verified TLS gRPC and OAuth HTTPS
~~~

#### CA bundle rotation

Ordinary fulfillment-service leaf-certificate renewal needs no tenant action:
the issuing trust root and the bundle hash are unchanged. Cross-cluster
synchronization occurs only when the management 'ca-bundle/bundle.pem' content
changes, such as when its issuing CA is replaced.

A ConfigMap update event for the configured management source enqueues all
eligible ClusterOrders. This is intentionally an infrequent fan-out; the
reconciler does not poll. Each target AAP job is idempotent and keyed by the
new SHA-256 value. The AAP apply updates the tenant ConfigMap before it patches
the CSI pod template, so every restarted CSI Pod sees the new file.

The current Bundle has one 'default-ca' source, so overlap must be made
explicit. Before rotating that root, the management CA procedure copies the
current public root to a temporary 'default-ca-previous' Secret in the same
cert-manager source namespace and configures it as a second 'ca-bundle' source.
It then issues the new root and waits until every
'FulfillmentTrustReady' condition reports the new bundle hash before switching
the fulfillment-service leaf certificate. Only after all clients have
converged may the procedure remove the temporary source and Secret. A failed
target remains on its prior tenant ConfigMap and reports a false condition; it
must be repaired before the old root is removed. This resolves the prior
one-time-copy lifecycle gap without a tenant cert-manager dependency.

#### Deletion

The tenant ConfigMap is owned operationally by the tenant cluster and is
discarded when that cluster is removed. The trust reconciler launches no
best-effort delete job and adds no finalizer: a missing guest kubeconfig must
not block ClusterOrder deletion. It ignores ClusterOrders with a deletion
timestamp and clears no fulfillment condition remotely.

### API Extensions

There is no fulfillment REST, gRPC, proto, or database API change. This is an
additive change to the ClusterOrder CRD's observed status and to internal chart
and AAP contracts.

| ID | Internal contract |
|---|---|
| IC-1 | Operator chart selects and mounts the management CA ConfigMap. |
| IC-2 | Operator gRPC configuration requires a valid CA file and preserves hostname verification. |
| IC-3 | ClusterOrder records trust synchronization through its condition, bundle hash, and job history. |
| IC-4 | CSI mounts the tenant ConfigMap and uses its CA for fulfillment gRPC and OAuth HTTPS. |
| IC-5 | A named test overlay, not production values, is the only rendered verification bypass. |
| IC-6 | Installer hooks, metering, and AAP template publishing retain their verified CA contracts. |
| IC-7 | A management bundle revision re-synchronizes tenant ConfigMaps and rolls matching CSI controllers. |

~~~go
const ClusterOrderConditionFulfillmentTrustReady ClusterOrderConditionType =
    "FulfillmentTrustReady"

type ClusterOrderStatus struct {
    // Existing fields omitted.
    FulfillmentTrustBundleHash string
    FulfillmentTrustJobs       []JobStatus
}
~~~

'FulfillmentTrustBundleHash' and 'FulfillmentTrustJobs' are controller-owned
observed state, never desired state. The job list uses the existing bounded
JobStatus history and identifies the target by the bundle hash. The condition
has these values:

| State | Reason | Meaning |
|---|---|---|
| False | TrustBundleUnavailable | Management ConfigMap, key, or PEM validation failed. |
| False | KubeconfigNotAvailable | The guest API cannot yet be reached. |
| False | TrustBundleApplyFailed | AAP could not apply the ConfigMap or complete a CSI rollout. |
| True | TrustBundleSynchronized | The current hash was applied and all matching CSI Deployments are Available. |

The API implementation adds the condition constant to the ClusterOrder API and
the generated CRD. It also adds it to
'clusterOrderUnsurfacedConditions' in the feedback controller and to that
controller's mapping-completeness test. It must not be mapped to an unrelated
fulfillment condition: fulfillment has no matching private condition type, and
the authoritative user-visible state is the ClusterOrder condition.

The chart contracts are:

~~~yaml
# operator values supplied by the installer
fulfillment:
  tls:
    caBundle:
      namespace: osac
      configMap: ca-bundle
      key: bundle.pem
tenantTrust:
  tenantNamespace: osac-csi
  csiDeploymentSelector: osac.openshift.io/fulfillment-trust-client=true

# CSI values supplied by the tenant installation
controller:
  fulfillment:
    tls:
      caBundle:
        configMap: osac-fulfillment-ca
        key: bundle.pem
~~~

When 'fulfillment.endpoint' is set, the CSI and operator templates require the
specified ConfigMap and key, mount the selected item read-only, and pass
'--fulfillment-ca-file'. The binaries reject a missing, unreadable, empty, or
invalid PEM file before making a fulfillment connection. They construct TLS
with RootCAs set to the parsed pool, minimum TLS 1.2, and normal DNS hostname
verification. They do not fall back to the system pool, plaintext, or disabled
verification.

Production charts remove the 'insecureSkipVerify' value and never emit
'--grpc-insecure'. A named test overlay may emit that flag only alongside the
test fixture that requires it; the overlay is not part of shipped production
values and a chart-render test verifies the distinction. The unrelated
operator-to-AAP setting remains out of this proposal's scope.

No matching temporary UI API resource exists. UX alignment is therefore not
applicable: the feature adds no UI-visible resource or field.

### Implementation Details/Notes/Constraints

The reconciler follows the existing controller lifecycle:

1. Read the ClusterOrder, management ConfigMap, and guest-cluster kubeconfig.
2. Return a false condition and a bounded requeue for unavailable dependencies.
3. Compare the source SHA-256 to
   'status.fulfillmentTrustBundleHash' and find the corresponding latest
   trust-sync JobStatus.
4. Trigger or poll the explicit AAP template by using the same provisioning
   lifecycle helpers that track other ClusterOrder jobs.
5. Persist the job transition and condition through the status subresource.

The management ConfigMap watch maps to eligible ClusterOrders by listing only
objects that have both the tenant annotation and a ClusterReference. The
reconciler also indexes ClusterOrders by this eligibility predicate. A normal
ClusterOrder update enqueues only that object; a CA update is the only
all-target event.

The AAP launch data is structured under 'osac_job_vars' and contains the
ClusterOrder resource, 'admin_kubeconfig', and a
'fulfillment_trust' object with 'tenant_namespace', 'config_map_name',
'bundle_pem', and 'bundle_sha256'. Tasks that handle the kubeconfig use
'no_log: true'. The CA is public material but is also omitted from logs to keep
job output small and avoid accidental disclosure of deployment metadata.

The applied resource has one data item and required attribution:

~~~yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: osac-fulfillment-ca
  namespace: osac-csi
  annotations:
    osac.openshift.io/tenant: <clusterorder-tenant>
    osac.openshift.io/owner-reference: <clusterorder-uid>
    osac.openshift.io/fulfillment-ca-sha256: <sha256>
data:
  bundle.pem: <exact management bundle bytes>
~~~

The CSI chart labels its controller Deployment with
'osac.openshift.io/fulfillment-trust-client=true'. The trust template uses that
label rather than a Helm release name, so the same contract works for supported
tenant installation names. It patches only the template annotation, not the
Deployment selector or pod labels. The ConfigMap projection is eventually
updated by Kubernetes; the rollout is required because the Go clients load
their root pool at process start.

Metering already supplies 'TLS_CA_CERT' from the management bundle and AAP
template publishing already defaults certificate validation to true. Their
implementation impact is regression coverage. Installer fulfillment wait and
local-storage hook Jobs mount 'service.certs.caBundle.configMap' and replace
'curl -k' with curl '--cacert' pointing to the mounted 'bundle.pem'.

### Security Considerations

The bundle is public CA material, not a credential, but distributing it is
still constrained to an OSAC workload namespace. The trust AAP template has
write access only to the named tenant ConfigMap and patch access only to
Deployments carrying the trust-client label. Tenant CSI service accounts get
read access through the projected volume and no ConfigMap write permission.

Every new tenant ConfigMap has
'osac.openshift.io/tenant' and 'osac.openshift.io/owner-reference'
annotations. The reconciliation list and AAP target are derived from the
ClusterOrder; no tenant input can select another tenant's namespace or
ClusterOrder. Server-side apply conflicts fail closed rather than overwriting
an independently managed ConfigMap.

CA parsing uses the exact mounted PEM. Invalid PEM, a mismatched issuer, or a
DNS name absent from the service certificate's SAN fails the connection. No
production client can opt out through published chart values. Existing OAuth
client credentials remain in their existing Secrets, are not part of the AAP
trust payload, and must not be logged.

### Failure Handling and Recovery

| Failure | Controller and AAP behavior | Recovery and user-visible state |
|---|---|---|
| Source ConfigMap, key, or valid PEM absent | Do not launch AAP; set False with TrustBundleUnavailable. | Correct the installer source; its update event reconciles targets. CSI is never configured to use an unverified fallback. |
| Guest kubeconfig unavailable | Set False with KubeconfigNotAvailable and requeue with provisioning backoff. | A later ClusterOrder or HostedControlPlane update resumes synchronization. |
| AAP API, apply, conflict, or rollout fails | Record the terminal JobStatus and set False with TrustBundleApplyFailed. The next reconciler retry uses the same hash and is safe to repeat. | The ClusterOrder identifies the failure. Existing CSI continues with its last trusted bundle; a new CSI Pod remains Pending until its ConfigMap exists. |
| Reconciler restarts during a job | Read the latest bounded trust JobStatus and poll rather than launch a duplicate job. | Status converges after the controller returns; no manual cleanup is required. |
| Serving certificate changes before bundle convergence | Handshake failures expose the affected client in logs and readiness. | Follow the overlapping-root rotation procedure; do not remove the old root until every target reports the new hash. |
| CSI Deployment absent | Apply the ConfigMap successfully and do not wait for a rollout. | Later CSI installation mounts the current bundle; condition is True. |

### RBAC / Tenancy

No tenant-facing fulfillment roles or authorization policies change. The
operator needs read/watch access to the configured management ConfigMap,
read access to the existing guest kubeconfig Secret and HostedControlPlane, and
status update/patch for ClusterOrders. The AAP ServiceAccount used with the
guest kubeconfig needs ConfigMap get/create/patch and Deployment get/list/patch
in only the configured tenant namespace. The installer must not grant a
cluster-wide ConfigMap write role for this feature.

The fulfillment trust ConfigMap is single-tenant and owner-attributed. The
reconciler does not list or copy arbitrary tenant ConfigMaps, and tenants
cannot use it to discover another tenant's bundle or credentials.

### Observability and Monitoring

The reconciler adds these Kubernetes Events on ClusterOrder:

| Type | Reason | When |
|---|---|---|
| Normal | FulfillmentTrustSynchronized | The source hash was applied and matching CSI Deployments are Available. |
| Warning | TrustBundleUnavailable | The source ConfigMap, key, or PEM cannot be used. |
| Warning | FulfillmentTrustSyncFailed | AAP apply or rollout failed. |

It exports a counter named
'osac_fulfillment_trust_sync_total' with labels 'result' and 'reason', and a
gauge named 'osac_fulfillment_trust_bundle_targets' with label 'state'. An
alert should fire when a False FulfillmentTrustReady condition remains for more
than 15 minutes after a ClusterOrder is Ready, or when a bundle update produces
any failed target. Structured logs include ClusterOrder namespace/name/UID,
tenant, source ConfigMap reference, and bundle hash; they exclude PEM,
kubeconfig, token, and client-secret values.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| A CA rotation fans out to many tenant clusters. | Fan-out occurs only on a ConfigMap revision, jobs are idempotent by hash, and a rate-limited work queue bounds API and AAP load. The management rotation procedure stages the old root as a second Bundle source. |
| A CSI Pod reads an old projected file after a ConfigMap update. | Patch the pod-template hash only after server-side apply; wait for its rollout before reporting the condition True. |
| The tenant CSI namespace differs from the hard-coded post-install namespace. | Make one installer-supplied 'fulfillmentTrust.tenantNamespace' contract shared by the CSI chart and AAP template. |
| A new condition is silently lost from feedback processing. | Add it explicitly to the unsurfaced condition set and retain the mapping-completeness tripwire test. |
| A tenant or another controller owns the target ConfigMap. | Do not force server-side apply ownership; fail the condition and require the owner conflict to be resolved. |
| A deployment relies on a production verification bypass. | Rendering fails without a CA reference; published production values contain no bypass, and migration is verified by chart tests. |

### Drawbacks

This proposal adds a cross-cluster reconciliation path, an AAP job for each
bundle revision, and a CSI controller restart during CA rotation. That is more
operational machinery than a one-time ConfigMap copy. It is justified because
the copy must stay correct over the lifetime of the tenant cluster and because
restarting the client is necessary to replace its in-memory root pool. The
workload-local design also deliberately does not make arbitrary tenant
workloads trust the management CA.

## Alternatives (Not Implemented)

### One-time post-install ConfigMap copy

This has the smallest initial implementation but leaves every tenant stale
after the management CA changes. It is rejected because it cannot support a
safe overlapping-root rotation.

### Install trust-manager in every tenant cluster

A tenant Bundle would provide automatic ConfigMap updates but cannot directly
source the management cluster Secret or ConfigMap. It also adds a new tenant
operator dependency. The existing AAP connection can apply the narrow
workload-local resource without that dependency.

### Add the CA to the tenant operating-system trust store

This would make all tenant workloads trust the management CA, including
workloads outside OSAC's fulfillment-service scope. It is rejected to preserve
the least-trust boundary.

### Embed a CA copy in each consuming chart

Separate copies make rotation coordination and source ownership ambiguous.
They are rejected in favor of the one named management source and one named
tenant workload ConfigMap.

### Retain insecure verification in production

This preserves convenience for self-signed test endpoints but does not
authenticate the peer and violates the PRD. Test-specific overlays provide the
necessary fixture escape hatch without making it a production deployment
option.

### Do nothing

Existing management and tenant clients remain inconsistent, and clients that
disable verification retain the on-path certificate-substitution risk. It does
not meet the PRD.

## Test Plan

Detailed requirement-to-interface test cases are in
[testplan.md](testplan.md). Unit coverage exercises CA parsing, status
transitions, hash comparison, and feedback disposition; integration coverage
uses envtest, a TLS test endpoint, rendered Helm charts, and the AAP trust
template; E2E coverage follows the existing pytest CaaS, VMaaS, BMaaS, and
storage paths. The plan explicitly tests malformed PEM, hostname mismatch,
test-only bypass isolation, idempotent apply, and CA rotation.

## Graduation Criteria

Graduation criteria will be finalized when the feature is targeted at a
release. The expected path is Dev Preview, then Tech Preview, then GA. Before
advancing, all production manifests must render with verified TLS only; all
test-plan critical cases must be automated and passing; and a two-root
overlapping CA rotation must converge every supported tenant target with no
failed FulfillmentTrustReady condition.

## Upgrade / Downgrade Strategy

On upgrade, installer values supply the management source and tenant namespace,
then the reconciler creates or refreshes the tenant ConfigMap for reachable
existing ClusterOrders. CSI Pods roll one Deployment at a time according to
their normal Deployment strategy. A tenant remains on its prior trusted bundle
until its update succeeds; it is never switched to an unverified transport.

Downgrade after a failed rollout requires keeping a bundle that trusts the
current fulfillment leaf certificate. The previous CSI version may not
understand the ConfigMap contract, so operators must not remove an old root
until the serving certificate has been rolled back or all clients again trust
the retained root. The ConfigMap is additive and can be removed manually only
after the tenant CSI workload no longer references it.

## Version Skew Strategy

New installer and CSI chart versions tolerate a missing tenant ConfigMap only
by leaving the CSI Pod Pending; they never start an insecure client. A new
operator with an old CSI chart applies the ConfigMap but finds no
trust-client-labelled Deployment and reports synchronization success. An old
operator with a new CSI chart does not supply the ConfigMap, so the CSI Pod
remains Pending; supported deployment order is installer/operator first, then
the CSI chart. The rotation procedure retains both roots long enough for
mixed-version clients.

## Support Procedures

Support personnel inspect the ClusterOrder's FulfillmentTrustReady condition,
the corresponding trust-sync AAP job, and the tenant ConfigMap hash annotation.
They compare that hash to the management 'ca-bundle' hash and inspect CSI
Deployment rollout status. Logs and events identify the failure reason without
printing CA, kubeconfig, or credential content.

To stop new synchronization temporarily, scale the FulfillmentTrustReconciler
to zero. Existing clients continue using their last mounted trusted bundle;
new or updated tenant CSI clients may remain Pending. Restoring the reconciler
is safe because jobs are hash-keyed and ConfigMap applies are idempotent. Do
not disable certificate verification as a support action.

## Infrastructure Needed

No new project repository or shared infrastructure is required. The existing
kind-based controller test setup, AAP integration harness, Helm rendering
tests, and OSAC E2E environments need TLS test certificates and a
rotation-capable management bundle fixture.
