---
title: cross-cluster-tls-trust-for-fulfillment-service-clients
authors:
  - derez@redhat.com
creation-date: 2026-09-16
last-updated: 2026-09-22
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
source for fulfillment-service clients across management and newly provisioned
tenant clusters. It removes production verification bypasses and distributes
the management trust bundle to OSAC-managed tenant workloads. It covers the
operator, CSI, metering, AAP template-publishing, and installer-hook paths
without changing fulfillment APIs or credential lifecycle. See [PRD](prd.md)
for detailed requirements.

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
- Make CA bundle revisions converge idempotently for tenant clusters
  provisioned after this capability is enabled.
- Keep verification bypasses isolated to named test fixtures and absent from
  rendered production manifests.

### Non-Goals

- Issuing certificates, changing the existing cert-manager or trust-manager
  installation, or integrating an external CA.
- Mutual TLS and Kubernetes service-account-token remediation.
- A cluster-wide tenant operating-system trust-store update.
- Changing the TLS behavior of the operator-to-AAP client or the
  guest-cluster kubeconfig route. Those are separate trust relationships, not
  fulfillment-service client traffic.
- Backfilling or upgrading a tenant cluster that predates this capability.
- Keycloak client creation, credential Secret propagation, rotation, or
  revocation; those remain the OSAC-4197 lifecycle responsibility.

## Proposal

The implementation introduces a 'FulfillmentTrustReconciler' in
'osac-operator'. It watches the installer-managed management ConfigMap and
managed ClusterOrders. For every non-deleting ClusterOrder that has a tenant
annotation and a guest-cluster reference, it resolves the protected,
namespace-scoped target credential and launches one explicit AAP template:
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
| osac-installer | Retain the existing cert-manager Issuer, Certificate, and trust-manager Bundle. Mount its ConfigMap in fulfillment clients and hooks; remove fulfillment curl verification bypasses. Supply the management source and tenant namespace values to the operator and CSI charts. Bootstrap the tenant trust-admission controller, its protected store, and its credentials before binding trust-sync permissions. |
| osac-operator | Add the reconciler, ClusterOrder condition and observed status fields, ConfigMap watch, expected-bundle publication to the tenant admission controller, AAP template configuration, and explicit feedback disposition. Use a CA file for the operator's fulfillment gRPC connection instead of emitting its insecure argument, and rebuild that client when the management bundle revision changes. |
| osac-aap | Add the trust synchronization template. It uses a protected namespace-scoped credential to apply the ConfigMap through the tenant admission controller, updates the CSI Deployment template hash by label, and waits for its complete rollout when the Deployment exists. |
| osac-csi-driver | Consume the supplied CA ConfigMap through its existing controller chart and require a CA-file argument when a fulfillment endpoint is configured. Use that CA for both fulfillment gRPC and its OAuth token HTTP client; this does not deploy CSI or propagate its credential Secret. |
| osac-metering | Retain the existing mounted CA, rebuild its fulfillment client when the management bundle revision changes, and report the observed bundle hash only after a verified connection. |
| fulfillment-service | No API, proto, database, certificate, or Keycloak contract change. The served endpoint must continue to use a DNS name present in its certificate SANs. |
| tests/e2e | Add regression coverage to the existing CaaS, VMaaS, BMaaS, storage, installer, and AAP paths. |

### Workflow Description

#### Actors and starting state

- A Cloud Infrastructure Admin installs OSAC. The installer creates
  'default-ca', and trust-manager writes 'ca-bundle/bundle.pem' in the
  configured OSAC namespace.
- The target deployment contains no tenant clusters that predate this
  capability. This proposal provisions trust only for ClusterOrders created
  after the capability is enabled; it does not backfill a pre-existing tenant
  cluster.
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
4. A matching observed hash and completed prior AAP job are only a launch
   optimization, not proof that the tenant is current. A read-only target
   observer verifies the named ConfigMap, its data and hash annotation, and
   the selected CSI Deployments' template hashes and complete-rollout state. It
   watches those target objects and requeues the owning ClusterOrder on a
   delete or relevant change. If verification finds drift, the reconciler
   launches 'osac-sync-tenant-fulfillment-trust' again with the existing
   ClusterOrder identity, tenant value, protected credential reference, tenant
   namespace, bundle data, and bundle hash.
5. AAP uses server-side apply with field manager
   'osac-aap-fulfillment-trust' to create or update one ConfigMap named
   'osac-fulfillment-ca'. The admission controller accepts that apply only when
   its content matches the reconciler-published expected bundle for this
   ClusterOrder. It preserves no user-owned bundle fields; an apply conflict is
   a failure rather than a forced ownership takeover.
6. AAP first lists CSI controller candidates using the existing chart identity
   labels 'app.kubernetes.io/name=csi-driver' and
   'app.kubernetes.io/component=controller'. It then selects candidates with
   the new chart label 'osac.openshift.io/fulfillment-trust-client=true'. For
   each selected Deployment, it sets the pod-template annotation
   'osac.openshift.io/fulfillment-ca-sha256=<hash>' and waits for a complete
   rollout: its observed generation equals its generation, updated, ready, and
   available replicas equal desired replicas, unavailable replicas are zero,
   and no ready Pod belongs to an older owned ReplicaSet. If no candidate
   Deployment exists, synchronization succeeds only after the ConfigMap is
   verified; a subsequent CSI install consumes the ConfigMap. A
   candidate without the trust-client label is an unsupported legacy client;
   AAP does not patch it and the reconciler keeps FulfillmentTrustReady False
   until a supported labelled client is installed or it is separately verified.
7. The reconciler records the job and bundle hash, then sets
   'FulfillmentTrustReady=True'. The tenant CSI Pod mounts the ConfigMap and
   uses its 'bundle.pem' for gRPC and token HTTPS verification.

OSAC-4197 supplies the tenant-scoped Keycloak client credentials that the
existing fulfillment consumers use. One such client is reused by that tenant's
clusters. This proposal only consumes that existing OAuth credential path over
verified TLS: it neither creates nor copies the Keycloak client or its Secret.
The protected AAP credential described below is a separate Kubernetes identity
used only to synchronize public CA material.

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
    R->>AAP: protected credential ref, tenant, PEM, hash
    AAP->>TC: server-side apply osac-fulfillment-ca
    AAP->>CSI: patch pod-template hash and wait
    AAP-->>R: job success
    R->>R: verify target state; set FulfillmentTrustReady=True
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
the fulfillment-service leaf certificate. The operator and metering components
also watch the management ConfigMap revision. On a valid revision each builds a
new root pool and fulfillment client, performs a verified fulfillment
connection, atomically swaps the client, and records the observed bundle hash;
on a parse or connection failure it retains the previously working client and
reports the new hash as not ready. The rotation gate requires both management
components to report the new observed hash and successful verification as well
as every tenant condition before it switches the leaf certificate or removes a
root. Only after all clients have converged may the procedure remove the
temporary source and Secret. If the ConfigMap apply succeeds but the CSI rollout
fails, the tenant ConfigMap contains the overlap bundle while existing Pods can
retain their old in-memory pool and newly started Pods can read the new file.
The condition remains False; the retry verifies that ConfigMap and completes
the same-hash rollout. The old root must remain in the bundle until this mixed
state has recovered and every target is verified. This resolves the prior
one-time-copy lifecycle gap without a tenant cert-manager dependency.

#### Deletion

The tenant ConfigMap is owned operationally by the tenant cluster and is
discarded when that cluster is removed. When a ClusterOrder receives a deletion
timestamp, the reconciler launches no new job. It first atomically revokes each
active expected-bundle record for that ClusterOrder through the protected
control channel, then requests cancellation of its active AAP job and records
the cancellation. The admission controller serializes record revocation and
admission, so a ConfigMap or Deployment request that reaches admission after
revocation is rejected. The AAP template checks that its job is not cancelled
and that its record remains active immediately before the ConfigMap apply and
again before the Deployment patch; it stops on either failure.

This invalidation is bounded and adds no finalizer: a missing guest kubeconfig
must not block ClusterOrder deletion. If the protected channel cannot be
reached, the reconciler cancels the AAP job in its control plane, does not renew
the short-lived record, and reports the cleanup error for support. It ignores
the deleting ClusterOrder thereafter and clears no fulfillment condition
remotely.

### API Extensions

There is no fulfillment REST, gRPC, proto, or database API change. This is an
additive change to the ClusterOrder CRD's observed status and to internal chart
and AAP contracts.

This resolves the PRD's R1.Q5 status decision for this implementation: the
controller exposes one operational ClusterOrder condition for Kubernetes
observation and feedback processing, but introduces no user-facing UI, CLI
command, or readiness gate. The condition is not a fulfillment API change.

| ID | Internal contract |
|---|---|
| IC-1 | Operator chart selects and mounts the management CA ConfigMap. |
| IC-2 | Operator gRPC configuration requires a valid CA file and preserves hostname verification. |
| IC-3 | ClusterOrder records trust synchronization through its condition, bundle hash, and job history. |
| IC-4 | CSI mounts the tenant ConfigMap and uses its CA for fulfillment gRPC and OAuth HTTPS. |
| IC-5 | A named test overlay, not production values, is the only rendered verification bypass. |
| IC-6 | Installer hooks, metering, and AAP template publishing retain their verified CA contracts. |
| IC-7 | A management bundle revision and tenant drift re-synchronize tenant ConfigMaps and roll matching CSI controllers. |

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
| False | CSIClientUpgradeRequired | A CSI controller candidate exists but lacks the required trust-client label. |
| True | TrustBundleSynchronized | The current hash is verified in the tenant ConfigMap and either no CSI controller exists or every selected CSI Deployment has completed the defined rollout. |

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
verification. The CSI OAuth issuer and discovered token endpoint must be
absolute HTTPS URLs; an HTTP endpoint is rejected before a request. Its token
HTTP client rejects every redirect, so it never forwards client credentials or
an obtained token to a redirect target, including one on the same host.

Production charts remove the 'insecureSkipVerify' value and never emit
'--grpc-insecure'. A named test overlay may emit that flag only alongside the
test fixture that requires it; the overlay is not part of shipped production
values and a chart-render test verifies the distinction. The unrelated
operator-to-AAP setting remains out of this proposal's scope.

No matching temporary UI API resource exists. UX alignment is therefore not
applicable: the feature adds no UI-visible resource or field.

### Implementation Details/Notes/Constraints

The reconciler follows the existing controller lifecycle:

1. Read the ClusterOrder, management ConfigMap, protected AAP target-credential
   reference, protected observer-credential reference, and target-observer
   state.
2. Return a false condition and a bounded requeue for unavailable dependencies.
3. Compare the source SHA-256 to
   'status.fulfillmentTrustBundleHash', find the corresponding latest
   trust-sync JobStatus, and compare the observed tenant ConfigMap and CSI
   state to the desired hash and complete-rollout predicate.
4. Skip a launch only when source and observed target state both match. On
   target drift, trigger or poll the explicit AAP template by using the same
   provisioning lifecycle helpers that track other ClusterOrder jobs.
5. Persist the job transition and condition through the status subresource.

The management ConfigMap watch maps to eligible ClusterOrders by listing only
objects that have both the tenant annotation and a ClusterReference. The
reconciler also indexes ClusterOrders by this eligibility predicate. A normal
ClusterOrder update enqueues only that object; a CA update is the only
all-target event. For each reachable target, a read-only observer watches the
named ConfigMap and CSI controller candidates in the configured namespace and
maps their delete, hash, label, generation, ReplicaSet, or readiness changes
back to that ClusterOrder. It authenticates with a dedicated protected,
per-ClusterOrder observer credential. The tenant installation binds that
principal to a Role in only the configured tenant namespace with ConfigMap
`get`, `list`, and `watch` restricted by `resourceNames` to
'osac-fulfillment-ca', plus Deployment `get`, `list`, and `watch`; it has no
write verb. The ConfigMap watch uses a
`metadata.name=osac-fulfillment-ca` field selector, and the Deployment watch
uses the trust-client label selector. The observer is
re-established when its credential reference changes. It uses that credential
only through the read-only client; the raw kubeconfig is never retained or
placed in launch data.

The AAP launch data is structured under 'osac_job_vars' and contains the
ClusterOrder resource, a non-secret 'trust_kubeconfig_credential_ref', and a
'fulfillment_trust' object with 'tenant_namespace', 'config_map_name',
'bundle_pem', and 'bundle_sha256'. It never contains 'admin_kubeconfig' or any
raw kubeconfig. AAP resolves the reference to a protected per-ClusterOrder
credential and injects its file only into the job runtime; it is excluded from
launch parameters, job events, callbacks, status, and failure context. The CA
is public material but is also omitted from logs to keep job output small and
avoid accidental disclosure of deployment metadata.

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

A rollout is complete only when `status.observedGeneration` equals the
Deployment generation; `updatedReplicas`, `readyReplicas`, and
`availableReplicas` all equal the desired replica count; `unavailableReplicas`
is zero; and no ready Pod belongs to an owned ReplicaSet from an earlier
Deployment revision. `Deployment Available=True` alone is insufficient. The
reconciler sets FulfillmentTrustReady=True and the CA-rotation procedure may
switch the serving certificate only after this predicate succeeds.

The CSI chart labels its controller Deployment with
'osac.openshift.io/fulfillment-trust-client=true'. The trust template uses that
label rather than a Helm release name, so the same contract works for supported
tenant installation names. It also recognizes a controller candidate through
the existing chart identity labels, preventing an older unlabeled CSI
Deployment from being mistaken for no client. It patches only the template
annotation, not the Deployment selector or pod labels. The ConfigMap projection
is eventually updated by Kubernetes; the rollout is required because the Go
clients load their root pool at process start.

Metering already supplies 'TLS_CA_CERT' from the management bundle and AAP
template publishing already defaults certificate validation to true. Their
implementation impact is regression coverage. Installer fulfillment wait and
local-storage hook Jobs mount 'service.certs.caBundle.configMap' and replace
'curl -k' with curl '--cacert' pointing to the mounted 'bundle.pem'.

### Security Considerations

The bundle is public CA material, not a credential, but distributing it is
still constrained to an OSAC workload namespace. The tenant installation
creates a dedicated 'osac-fulfillment-trust-sync' ServiceAccount and a
protected per-ClusterOrder AAP credential for that principal; it is not the
existing cluster-admin installation kubeconfig. Its namespaced Role grants
ConfigMap `create` in the configured tenant namespace as a separate rule, and
grants ConfigMap `get` and `patch` only with
`resourceNames: ["osac-fulfillment-ca"]`; Kubernetes cannot scope `create` by
resource name. It grants the minimum Deployment get/list/patch verbs in the
configured tenant namespace. Tenant CSI service accounts get read access
through the projected volume and no ConfigMap write permission.

Kubernetes RBAC cannot make the Deployment patch grant label-scoped. Before
that Role is bound, the installer tenant-bootstrap phase deploys
'osac-fulfillment-trust-admission', its validating webhook, and its protected
expected-bundle store. The bootstrap waits for the Deployment and webhook to be
Ready and verifies the store is initialized before it binds the trust-sync
Role. It also creates a distinct protected per-ClusterOrder publisher
credential for FulfillmentTrustReconciler. The publisher authenticates to the
controller's protected control channel and is authorized only to create, renew,
and revoke expiring records scoped to its ClusterOrder UID and tenant
namespace; it has no ConfigMap or Deployment permission. The reconciler uses
that publisher credential, not the AAP credential, before each launch to write
the exact-bundle record keyed by ClusterOrder UID, namespace, ConfigMap name,
and SHA-256. The trust-sync ServiceAccount cannot create, alter, or read the
record. Publisher and observer credential rotation is driven by their protected
references and forces the reconciler to re-establish the corresponding client.

The controller admits a request from 'osac-fulfillment-trust-sync' only when
it creates or updates the named 'osac-fulfillment-ca' ConfigMap with an active
matching expected-bundle record. It computes the SHA-256 of `data.bundle.pem`,
requires it to equal both the expected bytes and the
'osac.openshift.io/fulfillment-ca-sha256' annotation, and permits only that
data key and these annotations: tenant, owner reference, and bundle hash. It
denies altered content, a mismatched hash, any extra data or annotation field,
and all other ConfigMap changes. For Deployments, it admits a patch only when
the existing object bears 'osac.openshift.io/fulfillment-trust-client=true' and
the sole change is the fulfillment CA template annotation. It denies a patch
to an unlabeled Deployment, a label addition, and every unrelated Deployment
change. The AAP template also checks these constraints, but that is defense in
depth rather than the authorization boundary.

Every new tenant ConfigMap has
'osac.openshift.io/tenant' and 'osac.openshift.io/owner-reference'
annotations. The reconciliation list and AAP target are derived from the
ClusterOrder; no tenant input can select another tenant's namespace or
ClusterOrder. Server-side apply conflicts fail closed rather than overwriting
an independently managed ConfigMap.

CA parsing uses the exact mounted PEM. Invalid PEM, a mismatched issuer, or a
DNS name absent from the service certificate's SAN fails the connection. No
production client can opt out through published chart values. OSAC-4197-owned,
tenant-scoped OAuth client credentials remain in their existing CSI Secret,
are not part of the AAP trust payload, and must not be logged. This proposal
does not change the Secret's lifecycle or propagation.

### Failure Handling and Recovery

| Failure | Controller and AAP behavior | Recovery and user-visible state |
|---|---|---|
| Source ConfigMap, key, or valid PEM absent | Do not launch AAP; set False with TrustBundleUnavailable. | Correct the installer source; its update event reconciles targets. CSI is never configured to use an unverified fallback. |
| Guest kubeconfig unavailable | Set False with KubeconfigNotAvailable and requeue with provisioning backoff. | A later ClusterOrder or HostedControlPlane update resumes synchronization. |
| Expected-bundle record unavailable, expired, or mismatched | Do not apply the tenant ConfigMap; record the failed JobStatus and set False with TrustBundleApplyFailed. | Reconcile publishes a fresh expected record and retries the same source hash; the AAP identity cannot bypass the admission controller. |
| ClusterOrder deletion begins during a trust-sync job | Atomically revoke its expected record, request AAP cancellation, and reject any later ConfigMap or Deployment admission request. | No new job launches or target writes occur after the deletion fence. Cleanup failure never blocks deletion; the short-lived record is not renewed. |
| AAP API, ConfigMap apply, conflict, or admission check fails | Record the terminal JobStatus and set False with TrustBundleApplyFailed. The next reconciler retry uses the same hash and is safe to repeat. | The ClusterOrder identifies the failure. If apply did not succeed, the prior ConfigMap remains in place; a new CSI Pod remains Pending when no ConfigMap exists. |
| CSI rollout fails after the ConfigMap apply | Record the terminal JobStatus and set False with TrustBundleApplyFailed. The retry verifies the new ConfigMap and repeats the annotation patch and rollout for the same hash. | The tenant ConfigMap already contains the new bundle. Existing Pods can retain the old in-memory pool, while newly started Pods can read the new file. Keep both roots and do not change the serving certificate or remove the old root until every target is verified. |
| Reconciler restarts during a job | Read the latest bounded trust JobStatus and poll rather than launch a duplicate job. | Status converges after the controller returns; no manual cleanup is required. |
| Serving certificate changes before bundle convergence | Handshake failures expose the affected client in logs and readiness. | Follow the overlapping-root rotation procedure; do not remove the old root until every target reports the new hash. |
| CSI Deployment absent | Apply the ConfigMap successfully and do not wait for a rollout. | Later CSI installation mounts the current bundle; condition is True. |
| CSI Deployment candidate lacks trust-client label | Do not patch the Deployment; set False with CSIClientUpgradeRequired. | Install a supported labelled CSI controller or explicitly verify and label the client, then target observation requeues synchronization. |

### RBAC / Tenancy

No tenant-facing fulfillment-service role or authorization policy changes. The
operator needs read/watch access to the configured management ConfigMap, read
access to the protected target-credential reference and HostedControlPlane, and
status update/patch for ClusterOrders. The AAP ServiceAccount is
'osac-fulfillment-trust-sync', authenticated through its protected
namespace-scoped credential; it needs a separate ConfigMap create rule plus
ConfigMap get/patch restricted by `resourceNames` to
'osac-fulfillment-ca', and Deployment get/list/patch in only the configured
tenant namespace. The admission policy defined above enforces the object and
field boundaries that RBAC cannot. The installer must not grant a cluster-wide
ConfigMap write role or use a cluster-admin kubeconfig for this feature.

The separate `osac-fulfillment-trust-observer` principal receives a protected
per-ClusterOrder credential and a RoleBinding only in the configured tenant
namespace. Its Role grants ConfigMap get/list/watch only for
'osac-fulfillment-ca' and Deployment get/list/watch for target observation,
and grants no create, update, patch, delete, Secret, or expected-bundle-store
access. The protected publisher credential used by the reconciler is limited to
the admission controller's record-control API; it is not usable as a Kubernetes
workload credential.

The fulfillment trust ConfigMap is single-tenant and owner-attributed. The
reconciler does not list or copy arbitrary tenant ConfigMaps, and tenants
cannot use it to discover another tenant's bundle or credentials.

### Observability and Monitoring

The reconciler adds these Kubernetes Events on ClusterOrder:

| Type | Reason | When |
|---|---|---|
| Normal | FulfillmentTrustSynchronized | The source hash is verified in the tenant ConfigMap and every selected CSI Deployment is Available, or no CSI controller exists. |
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
| A CA rotation fans out to many tenant clusters. | Fan-out occurs only on a ConfigMap revision, jobs are idempotent by hash, and a rate-limited work queue bounds API and AAP load. The management rotation procedure stages the old root as a second Bundle source and gates certificate changes on both management-client and tenant observed hashes. |
| A CSI Pod reads an old projected file after a ConfigMap update. | Patch the pod-template hash only after server-side apply; wait for its rollout before reporting the condition True. A failed rollout is a mixed state: retain both roots and retry before the old root is removed. |
| The trust-sync Job misuses a namespace-wide Deployment patch grant. | A tenant admission policy validates the ServiceAccount, existing trust-client label, and annotation-only patch; its denial path is covered by the AAP integration test. |
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

At this capability's rollout, the target deployment contains no tenant
clusters, so there is no tenant-cluster upgrade, backfill, or downgrade path.
The installer, operator, AAP template, and CSI chart must be deployed in their
compatible versions before the first tenant ClusterOrder is provisioned. For
tenant clusters created after that point, ordinary CA rotation follows the
overlapping-root procedure above; it is not a migration of a pre-existing
cluster. No client is switched to an unverified transport.

## Version Skew Strategy

The target rollout does not support a pre-existing tenant cluster with an older
CSI chart. Before the first tenant ClusterOrder is provisioned, the installer,
operator, AAP template, and CSI chart must be compatible. If an unsupported
legacy CSI controller is nevertheless observed, it is never treated as
success: the reconciler reports CSIClientUpgradeRequired and does not patch the
Deployment. New CSI versions tolerate a missing tenant ConfigMap only by
leaving the Pod Pending; they never start an insecure client. The rotation
procedure retains both roots long enough for supported workloads to converge.

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

No new project repository or shared infrastructure is required. The installer
adds the tenant-scoped admission-controller Deployment, webhook, protected
expected-bundle store, and credential bootstrap described above. The existing
kind-based controller test setup, AAP integration harness, Helm rendering
tests, and OSAC E2E environments need TLS test certificates, a
rotation-capable management bundle fixture, and an admission-controller test
double.
