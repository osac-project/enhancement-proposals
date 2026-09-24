# Test plan — OSAC-1644 / OSAC-5343

## Overview

- **Feature:** Cross-cluster TLS trust for fulfillment-service clients
- **Implementation epic:** [OSAC-5343](https://redhat.atlassian.net/browse/OSAC-5343)
- **Source requirements:** [PRD](prd.md), FR-1 through FR-5 derived in the
  design workflow context
- **Total test cases:** 16
- **Requirements covered:** 5 of 5
- **Interface changes covered:** 7 of 7

No implementation stories have been decomposed yet. Accordingly, the
requirement and interface-change mappings in this plan are the authoritative
pre-decomposition traceability; implementation stories must retain these cases
and add their Story and acceptance-criterion identifiers.

## Test Strategy

| Level | Location or harness | What it proves |
|---|---|---|
| Unit | 'osac-operator/cmd/main_test.go' and 'osac-csi-driver/cmd/osac-csi-driver/main_test.go' | CA-file validation, CertPool construction, and verified gRPC/token client configuration reject bad input before a connection. |
| Controller integration | New 'osac-operator/internal/controller/fulfillment_trust_controller_test.go' using the existing envtest setup | Reconciliation, conditions, AAP job state, source/target hash comparison, ConfigMap event fan-out, target-drift requeue, observer credential rotation, deletion fencing, and feedback-condition disposition. |
| Helm rendering | Existing 'osac-csi-driver/charts/csi-driver/tests/controller_fulfillment_test.yaml' plus new operator and installer Helm unit suites | Mounted ConfigMaps, read-only paths, CA-file flags, admission-controller bootstrap/readiness, no production bypass, and hook curl arguments. |
| AAP integration | New OSAC AAP trust-sync role test with a disposable namespace-scoped credential target | Server-side apply, expected-bundle publication and admission, Deployment hash patch, admission denial, and successful/failed rollout behavior. |
| E2E | Existing pytest workflows under 'tests/e2e' | A user-observable verified path through CaaS, VMaaS, BMaaS, tenant CSI, installer hooks, metering, and AAP publishing. |

The TLS fixtures use a test root CA, a serving certificate whose DNS SAN is the
configured endpoint, and a different-root/different-SAN certificate for
negative cases. They never reuse production CA keys or credentials.

## Test Cases

### FR-1: Every OSAC-deployed fulfillment-service client trusts the management CA and verifies the service certificate and hostname.

#### TC-FR1-01: Operator accepts a CA-signed fulfillment endpoint

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1 | IC-1, IC-2 | critical | automated |

##### Preconditions

- A TLS gRPC test server serves 'fulfillment.test.example:8001' with a DNS SAN
  for that name and a certificate signed by the fixture root CA.
- A temporary CA file contains that root and the operator is configured with
  that DNS endpoint and its CA-file flag.

##### Steps

1. Run the operator connection test in 'osac-operator/cmd/main_test.go'.
2. Trigger a feedback call through the configured gRPC connection.

##### Expected Results

- TLS connects with RootCAs set from the CA file and verification enabled.
- The server receives the feedback RPC for 'fulfillment.test.example'; a
  connection to any other server is not accepted.

#### TC-FR1-02: CSI verifies both fulfillment gRPC and OAuth token HTTPS

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1 | IC-4 | critical | automated |

##### Preconditions

- A fixture CA signs both a fulfillment gRPC server and the configured OIDC
  token endpoint.
- A temporary CSI credential file and the matching CA file are available.

##### Steps

1. Extend 'TestDialFulfillment' and 'TestNewClientCredentialsTokenSource' in
   'osac-csi-driver/cmd/osac-csi-driver/main_test.go' to pass the CA file.
2. Request a token and issue a fulfillment Volume API request.
3. Configure an HTTP issuer URL, then an HTTPS fixture whose token endpoint
   redirects to a recording endpoint.
4. Configure an HTTPS issuer whose discovery metadata supplies an `http://`
   token endpoint backed by a recording endpoint.

##### Expected Results

- Both HTTPS token exchange and gRPC handshake succeed only with the fixture
  CA and matching DNS names.
- The clients retain the existing credential request and Volume API behavior.
- The HTTP issuer is rejected before a token request. The redirect is rejected,
  and the recording target receives neither OAuth client credentials nor a
  bearer token.
- The discovered HTTP token endpoint is rejected before a request, and its
  recording endpoint receives neither OAuth client credentials nor a bearer
  token.

#### TC-FR1-03: Metering and AAP template publishing retain verified TLS

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1 | IC-6 | high | automated |

##### Preconditions

- Metering mounts management 'ca-bundle/bundle.pem'.
- The publish-templates test role has an HTTPS mock endpoint signed by the
  fixture CA instead of its current HTTP-only mock.

##### Steps

1. Run the metering connection test with 'TLS_CA_CERT' set to the mounted
   bundle path.
2. Extend the publish-templates role test at
   'osac-aap/collections/ansible_collections/osac/service/roles/publish_templates/tests/test.yml'
   with 'publish_templates_validate_certs=true'.

##### Expected Results

- Metering connects with the mounted CA.
- The AAP role posts and patches its fixture templates through verified HTTPS;
  it fails when the supplied CA does not sign the mock server.

#### TC-FR1-04: Missing, malformed, or wrong CA fails closed

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1, FR-3 | IC-1, IC-2, IC-4 | critical | automated |

##### Preconditions

- Empty, malformed, and different-root CA files are available with the same
  TLS fixture used by the positive cases.

##### Steps

1. Start the operator and CSI client configuration with each invalid file.
2. Start them with a valid CA file but a serving certificate signed by a
   different root, then with a valid chain but a different DNS SAN.

##### Expected Results

- Empty and malformed files fail configuration before any dial.
- Wrong-root and wrong-SAN handshakes fail; the test server receives no
  fulfillment RPC or token request after TLS rejection.
- Neither client enables a plaintext or verification-disabled fallback.

### FR-2: A newly provisioned tenant cluster receives the management CA without manual trust-store setup.

#### TC-FR2-01: Trust reconciliation creates the attributed tenant ConfigMap

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-2 | IC-3 | critical | automated |

##### Preconditions

- The new controller envtest suite has a ready ClusterOrder with tenant and
  owner-reference annotations, a guest-cluster reference, a protected
  namespace-scoped AAP credential reference, a separate protected observer
  credential bound to a read-only target Role, and management
  'ca-bundle/bundle.pem'.
- The fake AAP provider records launch data and reports completion.

##### Steps

1. Reconcile the ClusterOrder until the trust job reaches success.
2. Inspect its AAP variables and status.
3. Delete or alter the tenant ConfigMap, then alter a selected CSI template
   hash, and deliver the target-observer events.
4. Create a CSI controller candidate without the trust-client label and
   reconcile; then replace it with the supported labelled chart version.
5. Rotate the observer credential reference, then attempt a ConfigMap or
   Deployment write using the observer identity.

##### Expected Results

- The launch data contains the exact bundle bytes, SHA-256 hash, tenant
  namespace, and a protected credential reference, but no raw kubeconfig or
  'admin_kubeconfig'. Launch parameters, job events, callbacks, status, and
  failure context contain no kubeconfig value.
- The request targets only 'osac-fulfillment-ca' and carries the tenant and
  owner-reference annotations.
- The ClusterOrder has the current
  'FulfillmentTrustReady=True,Reason=TrustBundleSynchronized' condition,
  bundle hash, and bounded trust-job record.
- Each observed target drift re-runs the same-hash trust synchronization with
  the existing inputs and restores the ConfigMap and CSI rollout before the
  condition returns to True.
- A selected CSI Deployment becomes trust-ready only after its observed
  generation equals its generation; updated, ready, and available replicas
  equal the desired count; unavailable replicas are zero; and no ready Pod is
  owned by an earlier ReplicaSet.
- The unlabelled CSI candidate produces
  'FulfillmentTrustReady=False,Reason=CSIClientUpgradeRequired'; the condition
  returns to True only after the supported labelled controller is Available.
  An empty namespace remains the distinct successful no-client case.
- The observer reconnects with its replacement credential and receives only
  ConfigMap and Deployment get/list/watch access in the tenant namespace; its
  attempted writes are denied and it is never included in AAP launch data.

#### TC-FR2-02: AAP trust synchronization is idempotent and least-privilege

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-2 | IC-3, IC-4 | critical | automated |

##### Preconditions

- A disposable API target has the configured tenant namespace, an
  installer-owned expected-bundle admission controller whose Deployment and
  webhook are Ready and whose protected store is initialized, and a CSI
  Deployment bearing 'osac.openshift.io/fulfillment-trust-client=true'.
- The expected-bundle store contains the active record for the fixture bundle,
  hash, tenant, owner reference, and ConfigMap name; the AAP identity cannot
  read or write that store. The reconciler publisher credential is distinct and
  can create, renew, and revoke only records scoped to this ClusterOrder.
- The new AAP trust-sync test receives the fixture bundle, hash, tenant, and a
  protected namespace-scoped credential reference.

##### Steps

1. Assert that tenant bootstrap withholds the trust-sync Role until the
   admission Deployment, webhook, and store are Ready. After readiness, use the
   reconciler publisher credential to create the active record and attempt a
   ConfigMap or Deployment write with that credential.
2. Run the trust-sync template twice with the same inputs.
3. Read the target ConfigMap and CSI Deployment after each run.
4. Using the same ServiceAccount, try to apply altered bundle bytes, a
   mismatched hash, an extra ConfigMap data key, and an extra ConfigMap
   annotation.
5. Using the same ServiceAccount, try to patch an unlabeled Deployment, add the
   trust-client label to it, or change a non-CA field on the labelled
   Deployment.
6. Replace the active expected-bundle record with an expired record, then with
   an otherwise matching record scoped to another ClusterOrder UID or tenant;
   attempt the trust-sync apply for each record.
7. As the trust-sync ServiceAccount, attempt `get` on an unrelated ConfigMap.

##### Expected Results

- Exactly one 'osac-fulfillment-ca' ConfigMap exists with
  'data.bundle.pem' equal to the fixture bundle and all three required
  annotations: tenant, owner reference, and bundle hash.
- Before admission readiness, no trust-sync Role is bound and no launch occurs.
  The publisher can create the scoped record after readiness but Kubernetes
  denies its ConfigMap and Deployment writes.
- The second run produces no semantic ConfigMap change.
- The CSI pod template has the expected hash annotation and becomes
  Available; the template writes no other ConfigMap or Deployment.
- The admission controller denies every altered bundle, mismatched hash, and
  extra ConfigMap field; the original ConfigMap remains byte-for-byte equal to
  the expected bundle with exactly the three declared annotations.
- The admission controller denies every unlabeled-Deployment and unrelated
  labelled-Deployment change, and neither Deployment changes. This proves the
  object and field boundaries are enforced independently of the template
  selector.
- The expired and wrong-scope record attempts fail before mutation; the
  reconciler records `FulfillmentTrustReady=False,Reason=TrustBundleApplyFailed`
  and neither the ConfigMap nor Deployment changes.
- Kubernetes denies `get` on the unrelated ConfigMap, while the trust-sync
  template can still get and patch only `osac-fulfillment-ca`.

#### TC-FR2-03: Management bundle update converges tenant trust and CSI

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1, FR-2 | IC-3, IC-7 | critical | automated |

##### Preconditions

- The envtest controller begins with a completed, target-verified trust job for
  bundle hash A.
- The AAP integration targets contain tenant ConfigMaps and CSI Deployments at
  hash A. A new overlapping bundle with hash B contains old and new roots, and
  the serving certificate initially chains to root A.
- Operator and metering test clients are running at hash A and expose their
  observed management-bundle hash only after a verified fulfillment probe.

##### Steps

1. Update management 'ca-bundle/bundle.pem' from hash A to the overlapping
   hash B.
2. Deliver the ConfigMap watch event to the operator, metering, and trust
   reconciler; complete the AAP jobs and inspect every target ConfigMap and
   Deployment.
3. Verify that operator and metering each build a new client, complete a
   verified root-B probe, atomically report observed hash B, and stop using the
   hash-A client for new fulfillment connections.
4. Switch the serving certificate to root B only after every target reports
   the verified hash B and has completed its rollout and both management
   clients report verified hash B.
5. Independently simulate a target CSI rollout failure and a management-client
   reload or verified-probe failure; attempt to remove root A in each case.
6. Recover each failure, wait for every target and both management clients to
   be verified at B, then remove root A from the management bundle and complete
   the final trust sync.

##### Expected Results

- Hash B produces one effective trust-sync job per target. Repeated watch or
  reconcile delivery produces no duplicate ConfigMap update or CSI Deployment
  rollout side effect; an unchanged, verified target does not launch another
  apply job.
- The target ConfigMap data and hash annotation become B before the CSI
  template hash becomes B.
- Before the root-B serving certificate is selected, every CSI Deployment has
  `observedGeneration` equal to its generation; updated, ready, and available
  replicas equal desired replicas; unavailable replicas are zero; and no ready
  Pod belongs to an earlier owned ReplicaSet. The condition becomes True only
  after that complete rollout.
- Operator and metering report observed hash B only after their replacement
  clients complete verified probes. A reload or probe failure retains the last
  working client, leaves hash B not ready, and blocks both root-B selection and
  root-A removal.
- The root-B serving certificate succeeds only after all targets have the
  overlapping bundle. On the injected rollout failure, that target's ConfigMap
  contains B while old Pods can retain root A; its False condition blocks root-A
  removal. After recovery, every target verifies the root-B certificate; only
  then is root A removed and every target converges on the final root-B bundle.

#### TC-FR2-04: ClusterOrder deletion fences in-flight trust synchronization

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-2 | IC-3 | critical | automated |

##### Preconditions

- The controller integration harness can run a launched trust-sync job with an
  active expected-bundle record paused immediately before either target write.
- The admission-controller test double serializes record revocation with
  admission, and the fake AAP provider records cancellation requests.

##### Steps

1. In the first subcase, pause immediately before the ConfigMap apply, set the
   ClusterOrder deletion timestamp, and reconcile it.
2. Assert the record is atomically revoked, release the job, and verify its
   ConfigMap request is denied and its Deployment patch is not issued.
3. In the second subcase, begin with an already matching ConfigMap, pause
   immediately before the Deployment patch, set the deletion timestamp, revoke
   the record through reconciliation, and release the job.
4. Inspect the AAP cancellation requests, target objects, ClusterOrder status,
   and finalizer list for both subcases.

##### Expected Results

- The reconciler requests AAP cancellation after revoking the record; admission
  rejects the ConfigMap write in the first subcase and the Deployment write in
  the second. Neither the ConfigMap nor Deployment changes in either subcase.
- No new trust job launches or record renewal occurs for the deleting object.
  Cleanup failure is surfaced for support but adds no finalizer or deletion
  block.

### FR-3: Production fulfillment-service connections do not bypass TLS verification.

#### TC-FR3-01: Production chart rendering has CA mounts and no bypass

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-3 | IC-1, IC-4, IC-6 | critical | automated |

##### Preconditions

- Production operator, CSI, and installer values specify a fulfillment endpoint
  and the required CA ConfigMap references.

##### Steps

1. Extend the existing CSI chart suite
   'charts/csi-driver/tests/controller_fulfillment_test.yaml'.
2. Add equivalent Helm unit suites for the operator Deployment and installer
   fulfillment wait/local-storage Jobs, then render all three with production
   values.

##### Expected Results

- Operator and CSI containers select only 'bundle.pem' through a read-only
  ConfigMap volume and pass their documented CA-file argument.
- No production argument or value is '--grpc-insecure' or
  'insecureSkipVerify'.
- Fulfillment hook commands use curl '--cacert' and contain neither '-k' nor
  '--insecure'.

#### TC-FR3-02: Production configuration rejects incomplete trust wiring

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-3 | IC-1, IC-4 | critical | automated |

##### Preconditions

- Chart test fixtures omit a ConfigMap name, key, or CA file while retaining a
  fulfillment endpoint.

##### Steps

1. Render the operator and CSI charts for each incomplete combination.
2. Run the binaries with an unreadable referenced CA file.

##### Expected Results

- Rendering or startup fails with a configuration error naming the missing
  contract value.
- No workload starts with fulfillment traffic configured but without a
  verifiable CA source.

### FR-4: An explicit, isolated TLS-verification override is available only for supported tests.

#### TC-FR4-01: Named test overlay is the sole bypass path

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-4 | IC-5 | high | automated |

##### Preconditions

- Production values and one named fixture overlay for an intentionally
  self-signed TLS test endpoint are present.

##### Steps

1. Render each production chart.
2. Render the named test overlay and run the test that consumes it.

##### Expected Results

- Production rendering contains no verification-bypass flag or value.
- Only the named fixture render contains '--grpc-insecure', and the bypass
  test cannot be selected by normal installer values.

### FR-5: CaaS, VMaaS, BMaaS, AAP publishing, metering, tenant CSI, and installer Helm hooks are validated.

#### TC-FR5-01: CaaS creates a trust-ready tenant cluster

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-5 | IC-1, IC-2, IC-3, IC-7 | critical | automated |

##### Preconditions

- The CaaS E2E environment has fulfillment service signed by the management
  fixture CA and the trust reconciler enabled.

##### Steps

1. Extend 'tests/e2e/caas/sanity/test_cluster_create.py' to create a cluster.
2. Wait for ClusterOrder Ready and FulfillmentTrustReady.

##### Expected Results

- The ClusterOrder reports
  'FulfillmentTrustReady=True,Reason=TrustBundleSynchronized'.
- The management bundle hash equals the tenant ConfigMap and CSI Deployment
  annotation hash, and feedback reaches fulfillment without a TLS error.

#### TC-FR5-02: VMaaS feedback uses verified TLS

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-5 | IC-1, IC-2 | critical | automated |

##### Preconditions

- VMaaS E2E installer values mount the management CA and use the fixture DNS
  fulfillment endpoint.

##### Steps

1. Extend 'tests/e2e/vmaas/regression/test_compute_instance_creation.py'.
2. Create a ComputeInstance and wait for its expected observed status.

##### Expected Results

- The feedback update succeeds through a certificate-verified connection.
- Replacing the server certificate with the wrong-SAN fixture makes the
  feedback attempt fail rather than recording a false success.

#### TC-FR5-03: BMaaS feedback uses verified TLS

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-5 | IC-1, IC-2 | critical | automated |

##### Preconditions

- BMaaS E2E installer values mount the management CA and use the fixture DNS
  fulfillment endpoint.

##### Steps

1. Extend 'tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py'.
2. Create a BareMetalInstance and wait for its feedback and ready status.

##### Expected Results

- Fulfillment receives the feedback over verified TLS.
- A CA or DNS mismatch fails the update without allowing an insecure retry.

#### TC-FR5-04: Tenant CSI uses the synchronized bundle

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-5 | IC-3, IC-4, IC-7 | critical | automated |

##### Preconditions

- A CaaS tenant has a current 'osac-fulfillment-ca' ConfigMap,
  FulfillmentTrustReady=True, and a CSI controller configured to use it.

##### Steps

1. Extend 'tests/e2e/storage/test_caas_cluster_storage.py' to inspect the
   ConfigMap and CSI Deployment hash before requesting storage.
2. Create a PVC through the OSAC CSI driver and wait for the Volume API result.

##### Expected Results

- The CSI controller uses the tenant ConfigMap hash matching the management
  bundle and completes its verified fulfillment call.
- The PVC reaches its expected bound/provisioned result without any
  verification-bypass setting.

#### TC-FR5-05: Installer hooks, metering, and AAP publishing are verified end to end

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-5 | IC-6 | high | automated |

##### Preconditions

- A supported installer integration environment has a management bundle and a
  fulfillment certificate signed by that bundle.

##### Steps

1. Install or upgrade with the local-storage hook enabled.
2. Run the metering connection and AAP publish-template workflows against the
   TLS fixture.
3. Inspect the completed hook Job Pod specification and results.

##### Expected Results

- Hook Jobs complete their HTTPS requests with the mounted CA file.
- Metering and AAP template publishing complete with certificate validation
  enabled.
- No workload specification or job log contains a fulfillment TLS bypass.

## Gaps

There are no uncovered PRD functional or non-functional requirements. The
operator-to-AAP TLS setting and guest-kubeconfig route verification are
explicitly out of scope in the design and therefore have no cases here.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 16 |
| Critical | 13 |
| High | 3 |
| Automated | 16 |
| Manual | 0 |
| Requirements with test cases | 5 / 5 |
| Interface changes with test cases | 7 / 7 |
