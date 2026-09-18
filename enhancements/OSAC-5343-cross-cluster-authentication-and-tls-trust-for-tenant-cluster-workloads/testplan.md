# Test plan — OSAC-1644 / OSAC-5343

## Overview

- **Feature:** Cross-cluster TLS trust for fulfillment-service clients
- **Implementation epic:** [OSAC-5343](https://redhat.atlassian.net/browse/OSAC-5343)
- **Source requirements:** [PRD](prd.md), FR-1 through FR-5 derived in the
  design workflow context
- **Total test cases:** 15
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
| Controller integration | New 'osac-operator/internal/controller/fulfillment_trust_controller_test.go' using the existing envtest setup | Reconciliation, conditions, AAP job state, hash comparison, ConfigMap event fan-out, and feedback-condition disposition. |
| Helm rendering | Existing 'osac-csi-driver/charts/csi-driver/tests/controller_fulfillment_test.yaml' plus new operator and installer Helm unit suites | Mounted ConfigMaps, read-only paths, CA-file flags, no production bypass, and hook curl arguments. |
| AAP integration | New OSAC AAP trust-sync role test with a disposable kubeconfig target | Server-side apply, annotations, Deployment hash patch, and successful/failed rollout behavior. |
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

##### Expected Results

- Both HTTPS token exchange and gRPC handshake succeed only with the fixture
  CA and matching DNS names.
- The clients retain the existing credential request and Volume API behavior.

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
  owner-reference annotations, a guest-cluster reference, a fixture kubeconfig,
  and management 'ca-bundle/bundle.pem'.
- The fake AAP provider records launch data and reports completion.

##### Steps

1. Reconcile the ClusterOrder until the trust job reaches success.
2. Inspect its AAP variables and status.

##### Expected Results

- The launch data contains the exact bundle bytes, SHA-256 hash, tenant
  namespace, and guest kubeconfig without emitting those sensitive values to
  logs.
- The request targets only 'osac-fulfillment-ca' and carries the tenant and
  owner-reference annotations.
- The ClusterOrder has the current
  'FulfillmentTrustReady=True,Reason=TrustBundleSynchronized' condition,
  bundle hash, and bounded trust-job record.

#### TC-FR2-02: AAP trust synchronization is idempotent and least-privilege

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-2 | IC-3, IC-4 | critical | automated |

##### Preconditions

- A disposable API target has the configured tenant namespace and a CSI
  Deployment bearing 'osac.openshift.io/fulfillment-trust-client=true'.
- The new AAP trust-sync test receives the fixture bundle, hash, tenant, and
  admin kubeconfig.

##### Steps

1. Run the trust-sync template twice with the same inputs.
2. Read the target ConfigMap and CSI Deployment after each run.

##### Expected Results

- Exactly one 'osac-fulfillment-ca' ConfigMap exists with
  'data.bundle.pem' equal to the fixture bundle and all three required
  annotations: tenant, owner reference, and bundle hash.
- The second run produces no semantic ConfigMap change.
- The CSI pod template has the expected hash annotation and becomes
  Available; the template writes no other ConfigMap or Deployment.

#### TC-FR2-03: Management bundle update converges tenant trust and CSI

| Story / AC | Interface Change | Priority | Automation |
|---|---|---|---|
| Pre-decomposition; FR-1, FR-2 | IC-3, IC-7 | critical | automated |

##### Preconditions

- The envtest controller begins with a completed trust job for bundle hash A.
- The AAP integration target contains a tenant ConfigMap and CSI Deployment
  at hash A. A new overlapping bundle with hash B contains old and new roots.

##### Steps

1. Update management 'ca-bundle/bundle.pem' from hash A to hash B.
2. Deliver the ConfigMap watch event, complete the AAP job, and inspect the
   target ConfigMap and Deployment.

##### Expected Results

- Every eligible ClusterOrder is enqueued once for hash B; an unchanged hash
  does not launch another job.
- The target ConfigMap data and hash annotation become B before the CSI
  template hash becomes B.
- The CSI Deployment rolls to Available and the condition becomes True only
  after that rollout completes.

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
| Total test cases | 15 |
| Critical | 12 |
| High | 3 |
| Automated | 15 |
| Manual | 0 |
| Requirements with test cases | 5 / 5 |
| Interface changes with test cases | 7 / 7 |
