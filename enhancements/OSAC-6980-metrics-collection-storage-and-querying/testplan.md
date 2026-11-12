# Testplan — OSAC-6980

## Overview

- **Feature:** OSAC-6980 — Metrics Collection, Storage and Querying
- **Total test cases:** 65
- **Requirements covered:** 8 of 8 active requirements (R1, R2, R4–R8) and all six PRD NFRs; R3 is retired
- **Acceptance criteria covered:** 19 of 19, one case per criterion
- **Interface changes covered:** 9 of 9 active interface changes (IC-1–IC-7, IC-9, IC-10)
- **Tier and owner:** Unit, Component integration, and Contract cases on changed code are `[DEV]`; deployed cross-component journeys are `[QE]` (see Tier and Owner Coverage)

## Test Cases

### R1: ServiceMonitors + RBAC wiring for all OSAC control plane components

#### TC-R1-01: All 10 ServiceMonitor targets show UP after deployment

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- OSAC installed with `observability.enabled: true` on an OpenShift cluster. User-workload monitoring is not enabled.
- The ten OSAC metric-emitting components are running. OpenShift AI and its operator are not covered by this Feature and no target is expected for them.

##### Steps

1. Query the platform Prometheus API: `GET /api/v1/query?query=up{managed_by="osac"}`.
2. Wait up to 90 seconds for all targets to be scraped.
3. Inspect the result set for all 10 expected job labels: `fulfillment-grpc-server`, `fulfillment-rest-gateway`, `fulfillment-controller`, `fulfillment-event-publisher`, `fulfillment-console-proxy`, `osac-operator`, `bmf-operator`, `osac-metering`, `echo-adapter`, `m360-adapter`.

##### Expected Results

- The query returns 10 series.
- Each series has value `1.0`.
- No series has value `0.0`.

---

#### TC-R1-02: Operator HTTPS endpoint scraping with bearer token and CA verification succeeds

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- `osac-operator` and `bmf-operator` are running with their metrics Service bound on 8443 and annotated `service.beta.openshift.io/serving-cert-secret-name`.
- ServiceMonitors for both operators are deployed with `scheme: https`, `bearerTokenFile`, and `tlsConfig.caFile: /etc/prometheus/configmaps/service-ca-bundle/service-ca.crt`. No ServiceMonitor sets `insecureSkipVerify`.
- `ClusterRoleBinding` for `prometheus-k8s` to `<operator>-metrics-reader` ClusterRole is applied.

##### Steps

1. Query `up{job="osac-operator-metrics"}` against the platform Prometheus API.
2. Query `up{job="bmf-operator-controller-manager-metrics-service"}` against the platform Prometheus API.
3. Render the two ServiceMonitors with `helm template` and search for `insecureSkipVerify`.

##### Expected Results

- Both queries return a single series with value `1.0`.
- Neither series carries a `scrape_error` or certificate-verification error.
- Step 3 finds no `insecureSkipVerify` key in either rendered ServiceMonitor.
- With `observability.enabled: true` the operator binds 8443 even when `global.fulfillmentTrust.enabled` is false, which is what makes the scrape possible on a cluster without mTLS trust configured.

---

#### TC-R1-03: ServiceMonitor deployment with `observability.enabled: false` produces no resources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Helm chart rendered with `observability.enabled: false`.

##### Steps

1. Run `helm template osac osac-installer/charts/osac --set observability.enabled=false`.
2. Search rendered output for `kind: ServiceMonitor`.

##### Expected Results

- The rendered manifest contains zero `ServiceMonitor` resources.
- The `osac-metering` chart renders no ServiceMonitor, because the installer leaves `serviceMonitor.enabled` at its default `false`.

---

#### TC-R1-04: A Cloud Provider Admin queries at least one series from each control-plane component

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-4 | critical | automated |

##### Preconditions

- OSAC deployed with `observability.enabled: true`.
- A Keycloak Cloud Provider Admin token.

##### Steps

1. Pick one series family per component — for example a fulfillment gRPC counter, an `osac-operator` reconcile counter, a `bmf-operator` reconcile counter, a metering-service counter, and an adapter counter.
2. Query each through `Route/thanos-query-admin`, filtering on the component's `job` label.

##### Expected Results

- All five families return at least one series with `cluster="management"` and `managed_by="osac"`.
- No component requires a separate endpoint or credential: all five are served by the same admin Route and the same query interface.

---

### R2: VM workload + cluster metrics from CMO aggregated into platform store

#### TC-R2-01: KubeVirt VM metrics available in Thanos Query after CMO remote-write

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3, IC-4 | critical | automated |

##### Preconditions

- `cluster-monitoring-config` applied with the `osac` CMO `remoteWrite` entry pointing to Thanos Receive over HTTPS.
- At least one KubeVirt VMI is running in the cluster.
- Thanos Receive, Store Gateway, and Query are running.

##### Steps

1. Wait 2 minutes after applying `cluster-monitoring-config`.
2. Query the Thanos Query admin endpoint: `GET /api/v1/query?query=kubevirt_vmi_phase_count`.
3. Inspect the result.

##### Expected Results

- The query returns at least one series with label `phase` set to a valid VMI phase string (e.g., `Running`).
- The series has a numeric value greater than 0.
- Every series carries `cluster="management"` and `managed_by="osac"`.
- Per-VM KubeVirt series carry their native `namespace` label equal to the owning tenant's `ClusterOrder` namespace, so no label has to be added to attribute them.

---

#### TC-R2-02: HyperShift cluster metrics available in Thanos Query

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3, IC-4 | high | automated |

##### Preconditions

- `cluster-monitoring-config` applied with the `osac` CMO `remoteWrite` entry.
- At least one HyperShift HostedCluster exists.

##### Steps

1. Query the Thanos Query admin endpoint: `GET /api/v1/query?query=hypershift_hostedclusters`.
2. Query `GET /api/v1/query?query=up{job=~"kube-apiserver|kube-controller-manager"},cluster="management"` and inspect the `namespace` label values.

##### Expected Results

- The `hypershift_hostedclusters` query returns at least one series.
- The series value equals the number of active HostedClusters in the cluster.
- The hosted control-plane series carry `cluster="management"` and a `namespace` label equal to the order's HCP namespace (`<working namespace>-<hostedClusterName>`), which is what the tenant predicate matches on.

---

#### TC-R2-03: OSAC-provisioned cluster metrics reach the platform store under its certificate identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9, IC-10, IC-4 | high | automated |

##### Preconditions

- One cluster provisioned through OSAC is running and has remote-write configured by the provisioning flow (IC-10).
- The IC-9 remote-write Route is deployed and the managed cluster holds a client certificate whose common name is `status.clusterReference.hostedClusterName`.
- The guest cluster's CMO `externalLabels` deliberately set `cluster: not-the-real-name` to prove the proxy is authoritative.

##### Steps

1. Wait up to 5 minutes after provisioning completes.
2. Query the admin endpoint: `GET /api/v1/query?query=up{cluster="<hostedClusterName>",managed_by="osac"}`.
3. Query `GET /api/v1/query?query=node_cpu_seconds_total{cluster="<hostedClusterName>"}`.
4. Query `GET /api/v1/query?query=up{cluster="not-the-real-name"}`.
5. Inspect the `namespace` label on the returned series.

##### Expected Results

- Steps 2 and 3 return series from the managed cluster with `cluster` equal to the certificate common name and `managed_by="osac"`.
- Step 4 returns an empty result: the guest-asserted value was overwritten by the write proxy.
- Guest node series carry no `namespace` external label; nothing is stamped on the guest side, and no series from this cluster carries a tenant namespace that was not already present in the guest's own scrape.
- No management-cluster series carries this `cluster` value.

---

#### TC-R2-04: Imported ACM HUB cluster metrics reach the platform store after import

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9, IC-10, IC-4 | high | automated |

##### Preconditions

- An externally managed cluster is registered in ACM and imported into OSAC through OSAC-6488.
- The ACM policy delivering the IC-10 configuration is bound to the imported cluster.
- The cluster holds a valid client certificate for the IC-9 Route whose common name is the imported cluster's OSAC resource name.

##### Steps

1. Complete the import through OSAC-6488.
2. Wait up to 10 minutes for the ACM policy to apply.
3. Query the admin endpoint: `GET /api/v1/query?query=up{managed_by="osac"}` and inspect the `cluster` label values.

##### Expected Results

- The imported cluster appears with `managed_by="osac"` and its imported resource name in the `cluster` label.
- Node and control-plane metrics from the imported cluster are queryable through the admin endpoint.
- Series from the imported cluster carry no `namespace` external label, because the cluster is not tenant-owned and cannot be attributed to one organization.
- A cluster registered in ACM but not imported through OSAC-6488 does not appear in the result.

---

#### TC-R2-05: A revoked certificate serial is rejected and a reissued certificate for the same name is accepted

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9, IC-10 | high | automated |

##### Preconditions

- A provisioned guest cluster is writing to Thanos through IC-9 under its issued client certificate.
- The certificate's serial number has been captured from the issued `Secret` in `osac-observability`.
- `ConfigMap/osac-metrics-write-revocation` in `osac-observability` exists and its `revoked` key is empty.
- A copy of the guest's client certificate and key is held outside the guest for the post-revocation write.

##### Steps

1. Delete the `ClusterOrder` as its owner.
2. Wait for the `ClusterOrderReconciler` finalizer to complete; confirm the `Certificate` is gone and the guest's `osac` remote-write entry is removed.
3. Read `ConfigMap/osac-metrics-write-revocation` and confirm the captured serial is present in `revoked`.
4. Attempt a remote write through IC-9 using the held copy of the revoked certificate.
5. Create a new `ClusterOrder` whose `status.clusterReference.hostedClusterName` equals the deleted cluster's name, and let the reconciler issue a new certificate.
6. Query `up{cluster="<that name>", managed_by="osac"}` through the admin endpoint.

##### Expected Results

- Step 3 shows the old serial in the `revoked` key, one serial per line.
- Step 4 returns HTTP 401 and no sample from that request appears in Thanos.
- Step 5 succeeds with a new serial, and the new certificate's writes are accepted.
- Step 6 shows series under the reused name from the new certificate only.
- The revoked serial remains listed after the new certificate is issued, so a later replay of the old credential is still rejected.
- If the issued `Secret` was already deleted when the finalizer ran, no serial is appended and the old certificate stops writing only at `certificateDuration`; that path is the documented backstop, not a failure of this test.

---

#### TC-R2-06: A valid certificate whose common name is `management` is rejected and stores nothing

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | automated |

##### Preconditions

- The IC-9 Route and write proxy are deployed.
- The test holds a client certificate and key signed by `Issuer/osac-metrics-write-ca`, not expired, whose serial is absent from `ConfigMap/osac-metrics-write-revocation` key `revoked`, with common name `management`. No guest cluster holds this certificate.
- Tenant-a's namespace is known and a tenant-a token is available.

##### Steps

1. Send a remote-write request to IC-9 with the `management` certificate, carrying one sample whose `cluster` label is `management` and whose `namespace` label is tenant-a's namespace.
2. Query the admin endpoint: `GET /api/v1/query?query=up{cluster="management"}` and compare the result set before and after step 1.
3. From tenant-a, query the metric name sent in step 1 through the tenant Route.
4. Repeat step 1 with a certificate signed by the same issuer whose common name is an ordinary guest cluster name.

##### Expected Results

- Step 1 returns HTTP 401.
- Step 2 shows no new series; no sample from the request is stored.
- Step 3 returns an empty result, so the forged `namespace` never reaches tenant-a's management branch.
- Step 4 is accepted, proving the rejection applies to the common name `management` and not to certificates that are merely new to the proxy.
- The proxy makes no inventory lookup: it rejects on the common name alone, and a certificate it has never seen for an ordinary name is accepted.

---

#### TC-R2-07: The OSAC-6488 import contract refuses `management` and any live cluster name — owned with OSAC-6488

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | manual |

##### Preconditions

- The OSAC-6488 import policy is implemented.
- Two candidate imported resource names are available: the literal `management`, and one equal to a live `status.clusterReference.hostedClusterName`.

##### Steps

1. Attempt to import a cluster whose imported resource name is `management`.
2. Attempt to import a cluster whose imported resource name equals the live `hostedClusterName`.
3. Inspect the `Certificate` objects and issued `Secret` objects in `osac-observability`.

##### Expected Results

- Both import attempts are refused by the import contract before any certificate is issued.
- Step 3 finds no `Certificate` and no issued `Secret` for either name.
- Neither name appears in a guest remote-write configuration delivered by the ACM policy.
- This case is owned with OSAC-6488: this design specifies the policy body and OSAC-6980 adds no import controller of its own.

---

### R3: NVIDIA GPU health metrics — retired

GPU metrics, including DCGM Exporter collection, are out of scope for OSAC-6980 and moved to OSAC-7246 (GPU Metrics Collection and Querying). The two former R3 test cases and the installer warning they exercised are removed. No test cases are assigned to R3.

---

### R4: Shelf product signals queryable via OSAC schema; no upstream changes

#### TC-R4-01: KubeVirt signals appear in Thanos without any change to KubeVirt resources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | high | automated |

##### Preconditions

- CMO remote-write to Thanos Receive is configured.
- No modification to KubeVirt Operator deployment or configuration has been made by OSAC.

##### Steps

1. List all OSAC-managed Kubernetes resources in the `kubevirt` namespace: `kubectl get all -n kubevirt`.
2. Query Thanos Query admin endpoint for `kubevirt_vmi_cpu_usage_seconds_total`.

##### Expected Results

- No OSAC-managed resources (ServiceMonitors, ConfigMaps, RBAC) exist in the `kubevirt` namespace.
- The PromQL query returns at least one series with `job="kubevirt"` or equivalent CMO job label.

---

#### TC-R4-02: Workload metric families are absent from the store for every role

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-10, IC-4, IC-5 | critical | automated |

##### Preconditions

- The `cluster-monitoring-config` from IC-1 is applied with its `writeRelabelConfigs` allowlist rules intact.
- The cluster is collecting cAdvisor, kube-state-metrics, KServe, and vLLM families locally, so `container_*`, `kube_pod_*`, `kube_service_info`, `kube_deployment_*`, and `vllm:*` exist in the platform Prometheus before remote-write.
- A tenant namespace holds one `PersistentVolumeClaim` that is bound and mounted by a running pod, and one that is bound but mounted by no pod.
- At least one OSAC-provisioned guest cluster has IC-10 applied and is writing.
- Thanos holds at least one scrape interval of remote-written data.

##### Steps

1. Confirm the allowlist rules are present in the applied configuration: `kubectl -n openshift-monitoring get configmap cluster-monitoring-config -o yaml`.
2. Through the admin endpoint, query the workload families in a **tenant** namespace: `container_cpu_usage_seconds_total`, `kube_pod_info`, `kube_service_info`, `kube_deployment_spec_replicas`, `vllm:num_requests_running`.
3. Through the admin endpoint, query `container_cpu_usage_seconds_total` and `kube_pod_info` in an OSAC platform namespace, and `kube_service_info` and `kube_deployment_spec_replicas` in that same namespace.
4. Through the admin endpoint, query `kube_persistentvolumeclaim_status_phase`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, `kube_node_info`, and `kube_persistentvolume_info` in the tenant namespace and with `cluster="management"`.
5. Query the guest cluster's series through the admin endpoint: `kube_pod_spec_volumes_persistentvolumeclaims_info`, `kube_persistentvolumeclaim_status_phase`, `kube_pod_info`, `container_cpu_usage_seconds_total`, and `kube_node_info{cluster="<hostedClusterName>"}`.
6. Query the platform Prometheus API directly for the metric names in step 2, to prove the sources exist.
7. Repeat steps 2 and 4 with a tenant token on the tenant Route.

##### Expected Results

- The applied ConfigMap carries the two `replace` stamps and the two `drop` rules from IC-1, and the platform-namespace list is the one rendered from `observability.collection.platformNamespaces`.
- The platform Prometheus returns series for every name in step 2, so an empty answer from Thanos is the allowlist and not a broken collector.
- `container_*`, `kube_pod_info` (outside the platform namespaces), `kube_service_info`, `kube_deployment_*`, and `vllm:*` return no series from a tenant namespace.
- `container_*` and `kube_pod_info` **do** return series from a platform namespace; `kube_service_info` and `kube_deployment_*` return none even there, because the allowlist names only `kube_pod_*` and `container_*` for that exemption.
- `kube_persistentvolumeclaim_status_phase` and `kube_pod_spec_volumes_persistentvolumeclaims_info` return rows on the management path, including the tenant namespace; the mount series names only the claim mounted by a running pod, so the unmounted claim has a phase row and no mount row.
- `kube_node_info` and `kube_persistentvolume_info` are stored for `cluster="management"`.
- On the guest, the node family is present and the claim, mount, pod, and container families are absent.
- The tenant Route returns the same emptiness for workload families, and no tenant sees the platform namespaces' `kube_pod_*` or `container_*` series.

---

#### TC-R4-03: A guest cluster's own relabel configuration cannot re-enable an excluded family

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9, IC-10 | critical | automated |

##### Preconditions

- One OSAC-provisioned guest cluster has its IC-10 ConfigMap edited to remove `writeRelabelConfigs` entirely (simulating a tenant-administered cluster that rewrites its own configuration).
- The platform Prometheus on the guest is collecting `kube_deployment_spec_replicas`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, and `container_cpu_usage_seconds_total`.

##### Steps

1. Confirm the guest's applied ConfigMap no longer contains the `kube_` allowlist or the `container_*` drop.
2. Send a synthetic remote-write batch containing `kube_deployment_spec_replicas`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, `container_cpu_usage_seconds_total`, `kube_node_info`, and `node_cpu_seconds_total` to the IC-9 Route with that cluster's client certificate.
3. Query the admin endpoint for all five names filtered to that cluster's `cluster` value.

##### Expected Results

- `node_cpu_seconds_total` and `kube_node_info` are stored and returned for that cluster: the guest allowlist keeps the node family.
- `kube_deployment_spec_replicas`, `kube_pod_spec_volumes_persistentvolumeclaims_info`, and `container_cpu_usage_seconds_total` are absent from the store, even though a claim-mount series is kept on the management path.
- The write proxy rejected or dropped those series even though the guest-side relabel rule was missing, proving the exclusion is enforced at the trust boundary and not only on the guest.

---

#### TC-R4-04: The cluster-monitoring-config job preserves unrelated keys and never enables UWM

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-10 | high | automated |

##### Preconditions

- The management cluster's `openshift-monitoring/cluster-monitoring-config` already contains an unrelated key (`prometheusOperator: {nodeSelector: {...}}`) and, on a second test cluster, a pre-existing `enableUserWorkload: true`.
- Observability is installed on both.

##### Steps

1. On the first cluster, read the ConfigMap after the post-install Job completes.
2. On the second cluster, read the ConfigMap after the Job completes.
3. Run the disable path (`observability.enabled: false`) and read the ConfigMap again on both.

##### Expected Results

- The unrelated `prometheusOperator` key is unchanged and byte-identical.
- `prometheusK8s.externalLabels` contains `cluster: management` and `managed_by: osac`, and `remoteWrite` contains exactly one entry named `osac`.
- The second cluster still has `enableUserWorkload: true` on the first install, and no `userWorkload` remote-write entry exists on either cluster.
- After disable, only the `osac` entry and the two external labels are gone; every other key, including `enableUserWorkload`, remains.
- With a pre-existing differently named `remoteWrite` entry targeting the Thanos Receive URL, the Job fails with the documented fixed error string and changes nothing.

---

### R5: Long-term storage with one configurable retention duration

#### TC-R5-01: The retention duration and the internal resolution ladder render into the Compactor flags

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Preconditions

- Helm chart rendered with `observability.thanos.retention: 365d` and the `observability.thanos.resolution` defaults.

##### Steps

1. Run `helm template` and extract the Thanos Compactor Deployment/StatefulSet.
2. Inspect the container args for `--retention.*` flags.
3. Re-render with `retention: 90d` and all three resolutions set to `90d`.
4. Re-render with `retention: 90d` and the resolutions left at `365d`.
5. Re-render with `retention: 365d` and `resolution.raw: 30d`.
6. Re-render with `retention: 365d` and `resolution.raw: 730d`.
7. Re-render with `retention: 365d` and `resolution.raw: 0d`.

##### Expected Results

- The rendered Compactor args contain `--retention.resolution-raw=365d`, `--retention.resolution-5m=365d`, and `--retention.resolution-1h=365d`: all three equal the configured window.
- Step 3 renders all three as `90d`: the window moves and every resolution moves with it.
- Steps 4, 5, and 6 fail rendering rather than produce a ladder that is longer or shorter than the window: a shorter resolution discards in-window data, and a longer one returns samples past the window. Step 7 fails too, because `0d` means "keep forever" and would return samples past the window.
- A query inside the window therefore answers at raw resolution for its whole length; there is no age past which an in-window query returns downsampled points.
- There is exactly one retention duration and no per-role retention key: the values schema exposes no `retention` field under `tenant` or `admin`.

---

#### TC-R5-02: A query inside the window returns data and a query wholly past it returns an empty successful response

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7, IC-4, IC-5 | critical | automated |

##### Preconditions

- Thanos hold series that are wholly inside the configured retention window and series wholly outside it (seed the object store, or set a short `retention` in a test environment).
- A Tenant Admin, a Tenant User, a Cloud Provider Admin, and a Cloud Infrastructure Admin credential are available.

##### Steps

1. Issue a range query wholly inside the window for a series the caller may see, once per role.
2. Issue the same query shifted wholly past the configured retention duration, once per role.
3. Compare the two responses for each role.

##### Expected Results

- Step 1 returns `200` with data for every role, and the data is identical for the Tenant Admin and the Tenant User over the same project and range (see TC-R7-25).
- The sample spacing of an in-window range query equals the scrape interval at both ends of the window — a query near the oldest retained day returns raw points, not 5-minute or 1-hour downsample points.
- Step 2 returns `200` with an empty `data.result` for every role — not an error and not a partial series — so the boundary is a data guarantee, not a status-code one.
- The window is the same for every role: a query that returns data for the Tenant Admin at time T also returns data for the Cloud Provider Admin at T.

---

### R6: Prometheus-compatible HTTP API (PromQL) query interface

#### TC-R6-01: Admin endpoint responds to PromQL instant query

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- `Route/thanos-query-admin` is running and accessible.
- Valid Keycloak Cloud Provider Admin token is available.

##### Steps

1. Send `GET /api/v1/query?query=up` with `Authorization: Bearer <admin-token>` to the admin Thanos Query Route.

##### Expected Results

- HTTP 200 response.
- Response body JSON has `status: "success"`.
- `data.resultType` equals `"vector"`.
- `data.result` is a non-empty array.

---

#### TC-R6-02: Unauthenticated request to admin endpoint is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- `Route/thanos-query-admin` is running.

##### Steps

1. Send `GET /api/v1/query?query=up` to the admin Thanos Query Route with no Authorization header.

##### Expected Results

- HTTP 401 response.
- Response body contains `error` field indicating authentication is required.

---

#### TC-R6-03: Tenant endpoint responds to PromQL instant query

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- The `authorizer` is running behind `Route/thanos-query-tenant`.
- A tenant user authenticated through the organization's registered identity provider holds a token whose `organization` claim maps to `osac-tenant-a`.
- Thanos holds `osac-tenant-a`'s VM series, its owned cluster's guest series, and its HCP-namespace series.

##### Steps

1. Send `GET /api/v1/query?query=up` with `Authorization: Bearer <tenant-token>` to the tenant Route.
2. Inspect the `cluster` and `namespace` labels across the result set.

##### Expected Results

- HTTP 200 response.
- Every returned series matches one of the two authorized branches: `cluster="management"` with `namespace` in `osac-tenant-a`'s namespace set, or `cluster` equal to one of `osac-tenant-a`'s `hostedClusterName` values.
- No series from another organization's namespace or cluster appears in the result.

---

#### TC-R6-04: Cloud Infrastructure Admin authenticates through OpenShift OAuth

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-7 | high | automated |

##### Preconditions

- `Route/thanos-query-admin` (Keycloak) and `Route/thanos-query-admin-openshift` (OpenShift OAuth) both front the Thanos Query service.
- A Cloud Infrastructure Admin holds an OpenShift OAuth token and is a member of the group configured in `observability.admin.openshiftGroup`.
- A Cloud Provider Admin holds a Keycloak token carrying the `cloud-provider-admin` realm role and is not a member of the OpenShift group.
- Cluster and node metrics from at least two clusters are in Thanos.

##### Steps

1. Send `GET /api/v1/query?query=up{managed_by="osac"}` with the OpenShift OAuth token to `Route/thanos-query-admin-openshift`.
2. Send the same query with the Keycloak admin token to the same OpenShift OAuth Route.
3. Send the same query with the OpenShift OAuth token to `Route/thanos-query-admin`.

##### Expected Results

- Step 1 returns HTTP 200 with `status: "success"`, and the result includes node and control-plane series from every cluster, not only the management cluster.
- Step 2 is rejected with HTTP 401 or 403: a Keycloak token is not valid on the OpenShift OAuth Route.
- Step 3 is rejected with HTTP 401 or 403: an OpenShift OAuth token is not valid on the Keycloak Route.
- A user authenticating through OpenShift OAuth who is not in the configured group is rejected on the OpenShift OAuth Route.

---

#### TC-R6-05: A Cloud Infrastructure Admin queries the management cluster and every covered cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-7 | critical | automated |

##### Preconditions

- The management cluster, at least one OSAC-provisioned cluster, and at least one cluster imported through OSAC-6488 are remote-writing.
- A Cloud Infrastructure Admin OpenShift OAuth token in the configured group.

##### Steps

1. Query node and control-plane families — `node_cpu_seconds_total`, `kube_node_info`, `apiserver_request_total` — with `count by (cluster) (…)` through `Route/thanos-query-admin-openshift`.
2. Compare the returned `cluster` values with the covered-cluster inventory.

##### Expected Results

- The result contains `management` and a value for every provisioned and imported cluster; no covered cluster is missing.
- The imported cluster's series are returned to the Cloud Infrastructure Admin even though no tenant owns it.
- No configuration, lifecycle, ownership, or cluster-management detail about the imported cluster is exposed — only its metric series.

---

### R7: Tenant-isolated query enforced by query interface

#### TC-R7-01: Tenant token cannot retrieve metrics from a different namespace

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- `authorizer` running behind the tenant Route.
- Metrics with `namespace="osac-tenant-b"` exist in Thanos, and `cluster="management"`.
- Tenant token's `organization` claim maps to `osac-tenant-a`.

##### Steps

1. Send `GET /api/v1/query?query=up{namespace="osac-tenant-b"}` with `Authorization: Bearer <tenant-a-token>` to the tenant Route.
2. Send `GET /api/v1/query?query=up{cluster="management",namespace="osac-tenant-b"}` with the same token.

##### Expected Results

- Both responses are HTTP 200 with `data.result` as an empty array `[]`.
- No series with `namespace="osac-tenant-b"` appears in either result.

---

#### TC-R7-02: Tenant token cannot omit the selector to query all metrics

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- `authorizer` running behind the tenant Route.
- Metrics from at least two organizations exist in Thanos.
- Tenant token's `organization` claim maps to `osac-tenant-a`.

##### Steps

1. Send `GET /api/v1/query?query=up` (no selector) with `Authorization: Bearer <tenant-a-token>` to the tenant Route.
2. Send `GET /api/v1/query?query=count(count by (cluster) (up))` with the same token.

##### Expected Results

- HTTP 200 response.
- Every series in `data.result` matches `osac-tenant-a`'s branch-1 or branch-2 predicate.
- No series from another organization's namespace or cluster appears.
- Step 2 returns only `osac-tenant-a`'s cluster values plus `management`.

---

#### TC-R7-03: Admin token retrieves metrics from all namespaces

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- `Route/thanos-query-admin` running.
- Metrics from multiple tenants' namespaces exist in Thanos.
- Valid Cloud Provider Admin token available.

##### Steps

1. Send `GET /api/v1/query?query=up` with `Authorization: Bearer <admin-token>` to the admin Thanos Query Route.
2. Inspect `namespace` and `cluster` label values across the result set.

##### Expected Results

- The result set contains series from at least two distinct `namespace` values corresponding to different tenant namespaces.
- The result set contains series from at least two distinct `cluster` values.

---

#### TC-R7-04: Series, label, and metadata enumeration return no other tenant's data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- `authorizer` exposing `/api/v1/series`, `/api/v1/labels`, `/api/v1/label/*/values`, and a filtered `/api/v1/metadata`.
- Metrics for `osac-tenant-a` and `osac-tenant-b` exist in Thanos, on different clusters and different namespaces.
- Tenant token's `organization` claim maps to `osac-tenant-a`.

##### Steps

1. Send `GET /api/v1/series?match[]=up` with the tenant-a token.
2. Send `GET /api/v1/labels`.
3. Send `GET /api/v1/label/namespace/values`.
4. Send `GET /api/v1/label/cluster/values`.
5. Send `GET /api/v1/metadata`.

##### Expected Results

- The series response contains only series matching tenant-a's predicate.
- The label-names response contains no label name introduced only by tenant-b series.
- The `namespace` label-values response contains `osac-tenant-a`'s namespaces and no `osac-tenant-b` namespace.
- The `cluster` label-values response contains only tenant-a's cluster values plus `management`.
- The metadata response contains no metric family that exists only for tenant-b.

---

#### TC-R7-05: Tenant query against a platform-wide metric name returns only owned series

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A platform-wide metric name (`node_cpu_seconds_total`) exists in Thanos from the management cluster and from tenant-a's owned guest cluster.
- Tenant-a and tenant-b VMs both generate series under names that exist platform-wide.

##### Steps

1. Send `GET /api/v1/query?query=node_cpu_seconds_total` with the tenant-a token.
2. Send `GET /api/v1/query?query=count(count by (cluster) (node_cpu_seconds_total))` with the tenant-a token.
3. Send `GET /api/v1/query?query=inbound_unary_request_count` with the tenant-a token, or any other OSAC control-plane family.

##### Expected Results

- Every returned series in step 1 carries either tenant-a's guest cluster value or `cluster="management"` with tenant-a's namespace; management-cluster node series carry no tenant namespace and are therefore not returned.
- The cluster-count query returns at most tenant-a's cluster values.
- Step 3 returns HTTP 200 with an empty `data.result`: the injected predicate cannot match a control-plane series, which lives in the `osac` namespace on the management cluster.

---

#### TC-R7-06: Token from an unregistered identity provider is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A test OIDC identity provider exists that is not registered for any OSAC organization.
- Its users can obtain a token from Keycloak brokering.

##### Steps

1. Obtain a token through the unregistered provider.
2. Send `GET /api/v1/query?query=up` to the tenant Route with that token.

##### Expected Results

- The request is rejected with HTTP 401, the same status as a request with no token: the token carries no `organization` claim.
- No series is returned.

---

#### TC-R7-07: Removing an organization's identity provider registration stops its access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Organization `osac-tenant-a` has a registered identity provider and an active token from it.
- Metrics for `osac-tenant-a` exist in Thanos.

##### Steps

1. Remove the identity provider registration from the organization in Keycloak.
2. Attempt to obtain a new token through that provider and query the tenant Route.
3. Retry with the previously issued, not-yet-expired token.

##### Expected Results

- The new authentication attempt fails, so no new token is issued.
- The previously issued token is rejected at the tenant Route within one token lifetime.
- No series is returned in either case.

---

#### TC-R7-08: Cloud Provider Admin can query a named tenant's metrics across clusters

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Tenant `osac-tenant-b` has VM and cluster metrics stored from at least two clusters.
- Valid Cloud Provider Admin token is available.

##### Steps

1. Send `GET /api/v1/query?query=up{namespace="osac-tenant-b"}` with the admin token.
2. Send `GET /api/v1/query?query=count by (cluster) (up{namespace="osac-tenant-b"})`.
3. Send `GET /api/v1/query?query=count by (cluster) (up{cluster=~"<tenant-b's cluster values>"})`.
4. Send `GET /api/v1/query?query=kube_persistentvolumeclaim_status_phase{namespace="osac-tenant-b"}`.

##### Expected Results

- Series for `osac-tenant-b` are returned from the admin endpoint, and no series from any other tenant's namespace or cluster appears in any step.
- Step 2 returns rows for each cluster where the tenant has VM resources.
- Step 3 returns rows for each of the tenant's covered clusters, including the one with no VM series, which is only reachable through the `cluster` predicate.
- Step 4 returns the volume object series — claim phase, capacity, and in-use state — for the volumes backing tenant-b's VMs.

---

#### TC-R7-09: Tenant sees its own cluster's node and control-plane series and no other organization's

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-1, IC-9, IC-10 | critical | automated |

##### Preconditions

- Organization `osac-tenant-a` owns an OSAC-provisioned cluster whose `hostedClusterName` is `order-aaaaa`; organization `osac-tenant-b` owns `order-bbbbb`.
- Both guests remote-write through IC-9, so their series carry `cluster` equal to their certificate common name and no `namespace` external label.
- The management cluster remote-writes through IC-1 with `cluster="management"` and no `namespace` external label, and scrapes both HCP namespaces.
- A KubeVirt VM belonging to tenant-b runs in `osac-tenant-b`'s namespace.

##### Steps

1. Send `GET /api/v1/query?query=node_cpu_seconds_total` with the tenant-a token.
2. Send `GET /api/v1/query?query=count by (cluster) (up)` with the tenant-a token.
3. Send `GET /api/v1/query?query=up{cluster="order-bbbbb"}` with the tenant-a token.
4. Send `GET /api/v1/query?query=up{job=~"kube-apiserver|kube-controller-manager"}` with the tenant-a token.
5. Send `GET /api/v1/query?query=count by (node) (kubevirt_vmi_info)` with the tenant-a token.
6. Send `GET /api/v1/query?query=up{cluster="management"}` with the tenant-a token.

##### Expected Results

- Step 1 returns node series for `order-aaaaa` only. Management-cluster node series are excluded because they carry no tenant namespace.
- Step 2 returns exactly `order-aaaaa` and `management`.
- Step 3 returns HTTP 200 with an empty `data.result`.
- Step 4 returns tenant-a's own HCP namespace series, matched through the `namespace` branch, and none from `osac-tenant-b`'s HCP namespace.
- Step 5 returns only the VMs in `osac-tenant-a`'s namespace: the injected `namespace` matcher proves KubeVirt series are attributed natively without any collect-time label.
- Step 6 returns HTTP 200 with an empty `data.result`: management-cluster series that carry no tenant namespace are structurally out of reach.
- A Cloud Provider Admin querying `count by (cluster) (up)` in the same window sees all three clusters and both tenants' VMs, confirming the tenant result is an enforcement effect and not missing data.

---

#### TC-R7-10: A guest cannot claim another organization's cluster identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9, IC-10, IC-5 | critical | automated |

##### Preconditions

- Organization `osac-tenant-a` owns `order-aaaaa`; organization `osac-tenant-b` owns `order-bbbbb`.
- Tenant-a's guest cluster is tenant-administered: its `cluster-monitoring-config` is edited to set `externalLabels.cluster: order-bbbbb` and to add `externalLabels.namespace: osac-tenant-b`.
- Tenant-a's certificate common name remains `order-aaaaa`.

##### Steps

1. Wait one scrape interval for the guest to remote-write with the forged labels.
2. Query the admin endpoint: `GET /api/v1/query?query=up{cluster="order-aaaaa"}` and inspect the `namespace` label.
3. Query with tenant-b's token: `GET /api/v1/query?query=up{cluster="order-bbbbb"}` and `GET /api/v1/query?query=up{namespace="osac-tenant-b"}`.

##### Expected Results

- The series are stored under `cluster="order-aaaaa"`, the certificate common name.
- `managed_by` is `osac`; the forged value is gone.
- `namespace` remains exactly what the guest scraped — the proxy does not delete or rewrite it, and the forged value is present on guest series.
- Step 3 returns no series from tenant-a's cluster, because guest series are authorized by `cluster` and `order-aaaaa` is not in tenant-b's predicate.
- No series is stored under `cluster="order-bbbbb"` originating from tenant-a.

---

#### TC-R7-11: A duplicated cluster identifier fails closed for both organizations

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-9 | high | automated |

##### Preconditions

- Two `ClusterOrder` resources in different namespaces reach the same `status.clusterReference.hostedClusterName` value (created directly for the test, since the API generates unique names).
- Both clusters have remote-written series.
- Tokens for both owning organizations are available.

##### Steps

1. Query `GET /api/v1/query?query=up` with tenant-a's token.
2. Query `GET /api/v1/query?query=up` with tenant-b's token.
3. Query `GET /api/v1/query?query=up` with a Cloud Provider Admin token.

##### Expected Results

- Steps 1 and 2 both return HTTP 200 with an empty result for the duplicated cluster identifier — the same body a caller gets for a series that does not exist. The identifier is removed from every scope, so no organization receives it.
- Neither organization receives the other's series, and neither status code reveals that the other organization exists (NFR-1).
- The collision is logged with both orders so the provider can resolve it, and the authorizer's log is the only place it is observable.
- Step 3 returns HTTP 200 and the admin view remains complete; a collision degrades tenant access only.
- The authorizer logs the duplicated identifier and the two namespaces.

---

#### TC-R7-12: A matrix-selector query returns only the caller's guest clusters

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- Organizations tenant-a and tenant-b each own at least one provisioned or imported cluster, and both are remote-writing node series.
- The management cluster's own node series are stored with `cluster="management"`.
- Tokens for both organizations are available.

##### Steps

1. Query the tenant Route with tenant-a's token: `GET /api/v1/query?query=rate(node_cpu_seconds_total[5m])`.
2. Query `GET /api/v1/query?query=count by (cluster) (node_cpu_seconds_total)` with the same token.
3. Repeat both queries with tenant-b's token.
4. Repeat both queries with a Cloud Provider Admin token on the admin Route.

##### Expected Results

- Step 1 returns series whose `cluster` values are exactly tenant-a's `hostedClusterName` values.
- Step 2 returns one series per cluster tenant-a owns, and no `management` value.
- Step 3 returns tenant-b's clusters only; no series from tenant-a or the management cluster.
- Step 4 returns every cluster including `management`, proving the admin path is unfiltered.
- The rewrite duplicates the enclosing `rate` call per branch rather than placing an `or` inside a single selector; the result is the union of the two branches and not an empty set.

---

#### TC-R7-13: `count by (node)` over KubeVirt VMI info returns only the caller's VMs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-1 | critical | automated |

##### Preconditions

- tenant-a's namespace and tenant-b's namespace each run at least one KubeVirt VMI, and neither organization's VMs share a node with the other's.
- Both namespaces are scraped by the management cluster's CMO.

##### Steps

1. Query the tenant Route with tenant-a's token: `GET /api/v1/query?query=count by (node) (kubevirt_vmi_info)`.
2. Query the same expression with tenant-b's token.
3. Query the same expression with a Cloud Provider Admin token on the admin Route.
4. Record the node names from step 1 and check those nodes' `kubevirt_vmi_info` series for foreign `namespace` values.

##### Expected Results

- Step 1 returns one series per node hosting tenant-a's VMs, with counts summing to tenant-a's VM count.
- Step 2 returns only nodes hosting tenant-b's VMs.
- Step 3 returns the union of both, proving the expression itself is not altered for admins.
- Step 4 finds no series in tenant-a's result whose `namespace` label belongs to tenant-b.
- The aggregation stays outside the rewritten branches; the authorizer does not move `count by (node)` inside the selector.

---

#### TC-R7-14: The `histogram_quantile` query form returns only the caller's hosted control plane

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- tenant-a owns at least one cluster whose hosted control plane is scraped by the management CMO in its HCP namespace.
- A second organization owns at least one cluster whose hosted control plane is scraped on the same management cluster.
- Both control planes emit `apiserver_request_duration_seconds_bucket`.

##### Steps

1. Send this query with tenant-a's token:

   ```promql
   histogram_quantile(0.99,
     sum by (le) (rate(apiserver_request_duration_seconds_bucket[5m])))
   ```

2. Send the same query with tenant-b's token.
3. Send the same query with a Cloud Provider Admin token.
4. Compare the returned bucket counts with `count by (cluster, namespace) (apiserver_request_duration_seconds_bucket)` on the admin Route.

##### Expected Results

- Step 1 returns a non-null quantile and its inputs come only from tenant-a's HCP namespace series.
- Step 2 returns a non-null quantile derived only from tenant-b's control plane.
- Steps 1 and 2 are not the same value unless the two control planes happen to be identical.
- Step 3 returns the quantile across every control plane.
- Step 4's restricted series count for tenant-a matches the bucket population implied by step 1, proving only the inner `rate` was lifted and the outer `histogram_quantile` and `sum` were preserved.

---

#### TC-R7-15: A selector that names another organization's cluster returns an empty result

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- tenant-b owns a cluster with a known `hostedClusterName`.
- tenant-a's token is available.

##### Steps

1. Query with tenant-a's token: `GET /api/v1/query?query=node_cpu_seconds_total{cluster="<tenant-b-cluster>"}`.
2. Query with tenant-a's token: `GET /api/v1/query?query=up{cluster=~"management|<tenant-b-cluster>"}`.
3. Query with tenant-a's token: `GET /api/v1/query?query=node_cpu_seconds_total{cluster!="<tenant-a-cluster>"}`.

##### Expected Results

- All three requests return HTTP 200 with an empty result set; none returns an error.
- The caller's own matchers are preserved and ANDed with the authorization branch, so a foreign `cluster` value narrows to nothing rather than replacing the branch.
- Step 3 does not return the management cluster's node series or tenant-b's series despite the negation.

---

#### TC-R7-16: An organization with no `ClusterOrder` matches no series with an empty `namespace`

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A tenant token exists for an organization that owns no `ClusterOrder` and no imported cluster.
- The store contains series with an empty `namespace` label, as several platform exporters emit.

##### Steps

1. Query the tenant Route with that token: `GET /api/v1/query?query={__name__=~".+"}`.
2. Query `GET /api/v1/query?query=up`.
3. Query with a Cloud Provider Admin token: `GET /api/v1/query?query=count by (namespace) (up)`.

##### Expected Results

- Steps 1 and 2 return HTTP 200 with an empty result set — not an error, and not the empty-`namespace` series.
- The namespace alternation contains only real namespace values; no empty string is joined into it, and no `=~""` branch is emitted.
- Step 3 shows that the empty-`namespace` series do exist in the store, so the empty result in step 1 is enforcement rather than absent data.

---

#### TC-R7-17: A `hostedClusterName` of `management` fails closed for that organization

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-9 | high | automated |

##### Preconditions

- A `ClusterOrder` is created directly with `status.clusterReference.hostedClusterName: management` in an organization's namespace, since the API generates other names.
- That organization's token is available.

##### Steps

1. Query the tenant Route with that organization's token: `GET /api/v1/query?query=up`.
2. Query `GET /api/v1/query?query=count by (cluster) (node_cpu_seconds_total)` with the same token.
3. Query `GET /api/v1/query?query=up` with a Cloud Provider Admin token.

##### Expected Results

- Steps 1 and 2 return HTTP 200 with an empty `data.result` for that organization: the value is removed from every scope, so no series is selected under `cluster="management"` and the caller cannot tell from the response that a conflicting name exists.
- No response to that organization contains series with `cluster="management"`.
- Step 3 returns HTTP 200 and the admin view is unaffected; the removal is scoped to the affected organization.
- The authorizer logs the rejected `hostedClusterName` with both order namespaces.

---

#### TC-R7-18: A Tenant Admin sees every VM, volume, and cluster in the organization

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-9, IC-10 | critical | automated |

##### Preconditions

- Organization `osac-tenant-a` owns three projects — the default project `""` and two named projects `team-x` and `team-y.nested` — with VMs and volumes in each and two owned clusters, one per named project.
- A Tenant Admin token carrying the `tenant-admin` realm role and the `organization` claim.

##### Steps

1. Query `count by (namespace) (kubevirt_vmi_info)` and `count by (namespace) (kube_persistentvolumeclaim_status_phase)` with the Tenant Admin token.
2. Query `count by (cluster) (node_cpu_seconds_total)` and `count by (cluster) (up{job=~"kube-apiserver|kube-controller-manager"})`.
3. Compare each result with the organization's resources in fulfillment.

##### Expected Results

- Step 1 returns every VM and volume family of the organization across all three projects, with no project matcher applied: organization scope is the namespace, and the namespace is the organization.
- Step 2 returns both owned clusters and their hosted control planes.
- Nothing from another organization appears, so this positive case is the mirror of TC-R7-09.

---

#### TC-R7-19: A Tenant Admin sees nothing for the management cluster's nodes or for imported clusters

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-1, IC-4 | critical | automated |

##### Preconditions

- The management cluster remote-writes node and control-plane series with `cluster="management"` and no tenant namespace.
- An imported cluster's series are stored under its imported resource name.
- A Tenant Admin token for `osac-tenant-a`.

##### Steps

1. Query `node_cpu_seconds_total` and `up{job=~"kube-apiserver|kube-controller-manager"}` with the Tenant Admin token.
2. Query `up{cluster="<imported cluster name>"}` with the same token.
3. Query the same expressions with a Cloud Infrastructure Admin token.

##### Expected Results

- Steps 1 and 2 return HTTP 200 with empty results: the management cluster and imported clusters have no organization and no project, so neither tenant role sees them.
- Step 3 returns the series, proving the tenant result is an authorization effect and not missing data.

---

#### TC-R7-20: A Tenant User sees the VMs, volumes, and clusters of the projects they belong to

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-9, IC-10 | critical | automated |

##### Preconditions

- Organization `osac-tenant-a` has projects `team-x` (VM `vm-x1`, volume `vol-x1`, cluster `order-xxxxx`), the descendant `team-x.frontend` (VM `vm-x2`), the sibling `team-xy` (VM `vm-xy1`), and `team-y` (VM `vm-y1`, cluster `order-yyyyy`).
- Each resource carries its project in `osac.openshift.io/project`.
- A Tenant User token whose `ProjectMembership` rows name `team-x` only, and that does not carry the `tenant-admin` realm role.

##### Steps

1. Query `kubevirt_vmi_info` with the Tenant User token.
2. Query `kube_persistentvolumeclaim_status_phase`.
3. Query `count by (cluster) (node_cpu_seconds_total)` and `up{job=~"kube-apiserver|kube-controller-manager"}`.

##### Expected Results

- Steps 1 and 2 return `vm-x1`, `vm-x2`, and `vol-x1`, matched through the `name`/`vmi` and `persistentvolumeclaim` resource matcher for the project-attributed families. A membership on `team-x` covers `team-x` and the descendant `team-x.frontend`.
- `vm-xy1` is absent: a descendant is a name that starts with `team-x.`, so `team-xy` is a different project, not a child of `team-x`.
- Step 3 returns `order-xxxxx` and its hosted control plane only.
- The default project `""` is also in scope, so a resource with no project annotation that belongs to the tenant appears; `team-y` never does.

---

#### TC-R7-21: A Tenant User sees nothing for another project's resource or cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-9, IC-10 | critical | automated |

##### Preconditions

- Same fixture as TC-R7-20; `vm-y1` and `vol-y1` are annotated `osac.openshift.io/project: team-y`, `vm-xy1` is annotated `osac.openshift.io/project: team-xy`, and `order-yyyyy` carries the `team-y` annotation.
- Tenant User token with membership in `team-x` only.

##### Steps

1. Query `kubevirt_vmi_info{name="vm-y1"}` and `kube_persistentvolumeclaim_status_phase{persistentvolumeclaim="vol-y1"}`.
2. Query `up{cluster="order-yyyyy"}` and `up{namespace="<team-y hosted control plane namespace>"}`.
3. Query `kubevirt_vmi_info{name="vm-xy1"}`, then `kubevirt_vmi_info` with no matcher.

##### Expected Results

- Steps 1 and 2 return HTTP 200 with empty results, byte-identical to the same queries for a resource that does not exist.
- The `vm-xy1` query is also empty: `team-xy` shares a prefix with `team-x` but is not its descendant, and the dot is what separates the two.
- Step 3's unnamed selector returns `vm-x1` and `vm-x2` only — it is expanded over the cached family catalogue and still bounded by the project matcher.
- A Tenant Admin of the same organization sees all of it, distinguishing project scope from organization scope.

---

#### TC-R7-22: Hosted control plane series reach the owning Tenant Admin and the project's Tenant User

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-1 | critical | automated |

##### Preconditions

- `osac-tenant-a` owns `order-xxxxx`; its `ClusterOrder` carries `osac.openshift.io/project: team-x`.
- A Tenant Admin token for `osac-tenant-a`, a Tenant User token with membership in `team-x`, and a Tenant User token with membership in `team-y` only.

##### Steps

1. Query `up{job=~"kube-apiserver|kube-controller-manager|openshift-apiserver"}` and `apiserver_request_total` with each of the three tokens.
2. Query the same with both admin tokens.

##### Expected Results

- The Tenant Admin and the `team-x` Tenant User both receive the hosted control plane series for `order-xxxxx`.
- The `team-y` Tenant User receives an empty result.
- The admin tokens also receive the series: the class is not admin-only, which is the distinction from the *Platform pod and container* class.
- A hosted control plane series is never classified as a platform pod/container series.

---

#### TC-R7-23: Denial and nonexistence are identical, for data and for listings

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | critical | automated |

##### Preconditions

- Organization `osac-tenant-b` has series that `osac-tenant-a` may not see.
- A Tenant User token for `osac-tenant-a` and a Tenant Admin token for `osac-tenant-a`.

##### Steps

1. Query `up{namespace="osac-tenant-b"}`, `up{cluster="order-bbbbb"}`, and `up{name="vm-that-does-not-exist"}` with the tenant-a token.
2. Call `/api/v1/labels`, `/api/v1/label/cluster/values`, and `/api/v1/series?match[]=up{namespace="osac-tenant-b"}` with the same token, and the nonexistent-resource equivalents.
3. Compare status code, headers that carry meaning (not `Date`), and body between each denied and nonexistent pair.

##### Expected Results

- Every request returns HTTP 200 with `data.result: []` (or an empty list for listings).
- Each denied/nonexistent pair is identical in status and body, so the interface is not an existence oracle for either data or enumeration.
- No listing reveals a metric name, label name, label value, or series that belongs only to tenant-b.

---

#### TC-R7-24: An empty project is the default project; only a genuinely unresolvable owner returns an empty response

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A `ComputeInstance` whose `osac.openshift.io/project` annotation is removed and a `ClusterOrder` with no project annotation, both in organization `osac-tenant-a`.
- A `hostedClusterName` that collides with another organization's.
- A `ProjectMembership` lookup that fails with a cold cache.

##### Steps

1. Query the removed-annotation `ComputeInstance`'s series and the unannotated `ClusterOrder`'s series with a Tenant User token that has no `ProjectMembership` rows, and again with the Tenant Admin token.
2. Query the colliding cluster's series with a Tenant User token.
3. With a cold membership cache, query a default-project series and a `team-x` series.
4. Query a series the caller may not see and a series that does not exist with the same token.
5. Compare the step 2 and step 4 responses.

##### Expected Results

- Step 1 returns both resources' series to every user of the organization, including the token with no membership rows: an absent or empty annotation is the default project, not an unresolved owner.
- Step 2 is HTTP 200 with an empty result, identical to both step 4 responses.
- Step 3 returns the default-project series and an empty result for `team-x`, so a cold cache degrades to the default project and never to `5xx`.
- No response is `5xx` and none carries an error field naming the owner or the collision.
- The authorizer logs a named project outside the caller's scope at most once per subject per cache window, without changing the response; it does not log an absent annotation, because that resource is visible to the caller.

---

#### TC-R7-25: The same project and time range return the same data to the Tenant Admin and a Tenant User

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- VM, volume, and cluster series exist for project `team-x` in organization `osac-tenant-a`.
- A Tenant Admin token and a Tenant User token with membership in `team-x`.

##### Steps

1. Issue the same range query over the same time range with both tokens, scoped to `team-x`'s resources by explicit matchers.
2. Compare the returned matrices.

##### Expected Results

- Both responses contain the same series, the same labels, and the same sample timestamps and values.
- The Tenant Admin's unfiltered query is a superset; the project-scoped query is identical for both callers, so the boundary does not degrade data quality.

---

#### TC-R7-26: The default project is visible to every user of the organization without a grant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Organization `osac-tenant-a` has a VM whose project annotation is absent (default project) and a VM annotated `osac.openshift.io/project: team-x`.
- A Tenant User token with no `ProjectMembership` rows at all, and a Tenant User token in organization `osac-tenant-b`.

##### Steps

1. Query `kubevirt_vmi_info` with the no-membership Tenant User token.
2. Query `team-x`'s VM with the no-membership token.
3. Query the unannotated VM with the `osac-tenant-b` token.

##### Expected Results

- Step 1 returns the default-project VM: membership in the tenant is what admits a caller to the default project, and no grant row is needed.
- Step 2 returns an empty result, so the default project's grant does not widen to named projects.
- Step 3 returns an empty result: the default project is per organization, and the organization namespace matcher still applies to an unannotated resource.

---

#### TC-R7-27: An unconstrained selector under project scope returns only the caller's resources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-1 | critical | automated |

##### Preconditions

- Organization `osac-tenant-a` has project `team-x` (VM `vm-x1`, volume `vol-x1`, cluster `order-xxxxx`) and project `team-y` (VM `vm-y1`, volume `vol-y1`, cluster `order-yyyyy`), each annotated with its project.
- `team-x` also holds a VM with no project annotation, which is in the default project.
- A Tenant User token with membership in `team-x` and no `tenant-admin` role.
- `kube_service_info` is not stored (the IC-1 allowlist does not name it). `kube_node_status_capacity` for the management cluster is stored under `cluster="management"` with an empty `namespace`; the same family is also stored for `order-xxxxx`'s guest cluster under that cluster's `cluster` label.

##### Steps

1. Query `GET /api/v1/query?query={__name__=~".+"}` with the Tenant User token.
2. Query `kube_service_info` with the Tenant User token, the Tenant Admin token, and a Cloud Provider Admin token.
3. Query `kube_node_status_capacity{cluster="management"}` with the Tenant User token, the Tenant Admin token, and a Cloud Provider Admin token.
4. Query `kube_node_status_capacity{cluster="order-xxxxx"}` with the Tenant User token and the Tenant Admin token, and the same query with `cluster="order-yyyyy"` using the Tenant User token.
5. Group the step 1 result by `__name__` and classify every family.

##### Expected Results

- Step 1 returns the series of `vm-x1`, `vol-x1`, the default-project VM, and `order-xxxxx`'s guest and hosted-control-plane series, and no series of `team-y` or of any other project.
- Every family in step 1 is attributable (it carries the resource matcher on the tenant-namespace branch), or lands in the caller's hosted-control-plane or working namespace, or carries one of the caller's guest `cluster` values. A family that is none of those is absent from the tenant-namespace branch rather than returned unfiltered.
- Step 2 is an empty body for every role, because the family has no ingest path at all — this is not an authorization answer.
- Step 3 is empty for both tenant roles but non-empty on the admin Route: the management cluster's series are stored but cluster-scoped, carrying no tenant namespace, so neither tenant scope reaches them.
- Step 4 is non-empty for both tenant roles: the guest branch matches `cluster="order-xxxxx"`, which is one of the caller's projects' clusters, and the guest path keeps `kube_node_*`. A query for `cluster="order-yyyyy"` is empty for the Tenant User even though it names a stored value.
- No response in this case carries an error, and no response reveals the name `team-y` or any of its resources.

---

#### TC-R7-28: The cluster and compute-instance reconcilers stamp the project annotation on create and on update

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A unit-test harness for `ClusterOrderReconciler` and the compute-instance reconciler, using a fake or envtest client.
- A `ClusterOrder` and a `ComputeInstance` whose `metadata.project` is `team-x`.

##### Steps

1. Reconcile the `ClusterOrder` and read the object's annotations.
2. Change `metadata.project` to `team-y`, reconcile again, and read the annotations.
3. Repeat steps 1 and 2 for the `ComputeInstance`.
4. Reconcile an object that carries no project annotation and whose `metadata.project` is non-empty, as an object created before this change would.
5. Reconcile an object whose `metadata.project` is empty.

##### Expected Results

- Step 1 stamps `osac.openshift.io/project: team-x` alongside the tenant annotation, on create.
- Step 2 rewrites the annotation to `team-y` on the existing object: the update path writes the annotation map, it does not skip it.
- Step 3 behaves identically for `ComputeInstance`.
- Step 4 backfills the annotation from `metadata.project` on the next reconcile, so no object has to be recreated.
- Step 5 leaves the project annotation absent or empty, which the authorizer treats as the default project; it never writes a placeholder value that would name a project.

---

### R8: Basic pipeline health visible

#### TC-R8-01: Thanos Receive health metric is queryable via admin endpoint

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Thanos Receive running with its own ServiceMonitor in `osac-observability`.
- The `osac-observability` namespace is labeled `openshift.io/cluster-monitoring: "true"`, so the platform Prometheus scrapes it.

##### Steps

1. Query admin Thanos Query endpoint: `GET /api/v1/query?query=thanos_receive_write_queue_length`.

##### Expected Results

- HTTP 200 response with at least one series returned.
- Series value is a non-negative integer.

---

#### TC-R8-02: Scrape success rate for OSAC components is queryable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- All 10 ServiceMonitor targets are deployed and scraped by the platform Prometheus.

##### Steps

1. Query admin Thanos Query endpoint: `GET /api/v1/query?query=sum by (job) (up{managed_by="osac"}) / count by (job) (up{managed_by="osac"})`.
2. Count the number of series with value `1.0` and with value `0.0`.

##### Expected Results

- All 10 job series return value `1.0`.
- Zero series return value `0.0`.

---

#### TC-R8-03: A cluster whose write path is broken is detectable by sample age

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-9, IC-5 | high | automated |

##### Preconditions

- Three covered clusters are storing series; one of them has its IC-9 client certificate deleted so its writes are rejected with 401.
- The infrastructure collection interval is 30 s.
- An admin token.

##### Steps

1. Wait until the affected cluster's newest stored sample is older than one infrastructure interval.
2. Query the admin endpoint: `GET /api/v1/query?query=time() - max by (cluster) (timestamp(last_over_time(up{managed_by="osac"}[1h]))) > 30`.
3. Query `GET /api/v1/query?query=rate(prometheus_remote_storage_failed_samples_total[5m])` on the affected cluster's platform Prometheus.

##### Expected Results

- Step 2 returns one series, for the affected cluster only: its newest sample inside the hour is older than one interval, so it is stopped. The two healthy clusters do not appear.
- No inventory comparison is needed: sample age alone names the cluster, and a cluster absent from the result either is reporting or has no sample at all in the hour.
- Step 3 shows remote-storage failures on the affected cluster, confirming the write path, not the scrape path, is the fault — which is why detection cannot rely on an ingested counter.

---

#### TC-R8-04: Tenant queries fail closed when the authorizer cannot read inventory

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- The `authorizer` has a running inventory and is serving tenant-a.
- RBAC for the authorizer's `ClusterOrder` list is temporarily removed, or the API server is made unreachable for the authorizer only.

##### Steps

1. Restart the `authorizer` so it cannot complete an initial list.
2. Query the tenant Route with tenant-a's token.
3. Query `Route/thanos-query-admin` with an admin token.
4. Restore RBAC and wait one 30-second cycle.

##### Expected Results

- Step 2 returns HTTP 503; no series is served from an empty or guessed inventory.
- Step 3 returns HTTP 200 unchanged.
- Step 4 restores tenant queries without a restart.

---

#### TC-R8-05: A stopped collector is visible as stopped and its recent data is absent

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-1, IC-7 | critical | automated |

##### Preconditions

- Two provisioned clusters, `order-aaaaa` and `order-bbbbb`, both remote-writing to Thanos Receive.
- Both clusters' platform Prometheus and CMO are healthy; `order-bbbbb` has `openshift.io/cluster-monitoring: "true"` and a working remote-write.
- The collection interval for the infrastructure class is 30 s (IC-7 `osacControlPlane`/`infrastructure` values).
- A Cloud Infrastructure Admin token and the admin Route.

##### Steps

1. Record `T0`, then scale the `order-bbbbb` platform Prometheus StatefulSet to zero replicas (the collector — not the guest cluster — stops).
2. Wait until `now − T0 > 2 × 30 s`.
3. Query the first pipeline-health question: `GET /api/v1/query?query=time() - max by (cluster) (timestamp(last_over_time(up{managed_by="osac"}[1h]))) > 30`.
4. Query the second pipeline-health question for the stopped cluster over the last two minutes: `GET /api/v1/query_range?query=node_cpu_seconds_total{cluster="order-bbbbb"}` with `start=now-2m&end=now&step=30s`.
5. Repeat steps 3 and 4 for the healthy cluster `order-aaaaa`.
6. Restore the collector.

##### Expected Results

- Step 3 reports `order-bbbbb` as stopped — its newest sample inside the hour is older than one interval — and does not report `order-aaaaa`.
- Step 4 returns HTTP 200 with no samples in the window for the stopped cluster: the recent-data question is answered by absence of data, not by a `5xx`.
- Step 5 shows the healthy cluster present in both signals, including samples with timestamps inside the two-minute window.
- The stopped cluster's historical series before `T0` remain queryable, so only recent data is missing; the interface stays available throughout, per NFR-3.

---

#### TC-R8-06: A watch that succeeds and then fails past the grace period returns 503 for every caller

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- The `authorizer` has completed at least one successful inventory list and is serving organizations `osac-tenant-a` and `osac-tenant-b`.
- Its inventory watch can be broken without restarting the process — for example by removing the list/watch permission for its service account, or by making the API server unreachable for that pod only.

##### Steps

1. Query the tenant Route with a token for `osac-tenant-a` and with a token for `osac-tenant-b` while the inventory is healthy, and record both bodies.
2. Break the watch. Within 30 seconds, repeat both queries.
3. Keep the watch broken beyond 30 seconds and repeat both queries.
4. Restore the watch and repeat both queries.

##### Expected Results

- Step 1 returns HTTP 200 with each caller's own data.
- Step 2 returns HTTP 200 with the same bodies as step 1 for each caller: the last good list is served during its one-refresh-interval grace period.
- Step 3 returns HTTP 503 for both callers, with identical bodies and no series. The failure is caller-invariant: it does not depend on what either caller asked for, and it does not reveal anything about either organization's series.
- Step 4 returns HTTP 200 again for both callers, without an authorizer restart and without a 503 once the list succeeds.
- The two admin Routes return HTTP 200 throughout, so an inventory outage degrades tenant access only.

---

### NFR-1: Authorization is not an existence oracle

No separate case is needed: the oracle property is asserted inside the cases that already exercise the boundary, by comparing a denied response with the same request for a resource that does not exist — status code **and** body. Data queries: TC-R7-01, TC-R7-02, TC-R7-05, TC-R7-12 through TC-R7-17, TC-R7-23. Enumeration endpoints: TC-R7-04, TC-R7-23. Workload-class boundary: TC-R4-02, TC-R4-03. A change that turns an empty result into an error or a distinguishable body fails those cases.

---

### NFR-2: Failure contract

#### TC-NFR2-01: Authentication errors, empty results, and unresolved owners are distinguishable exactly as NFR-2 says

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | critical | automated |

##### Preconditions

- Credentials for a Cloud Provider Admin, a Tenant Admin, and a Tenant User, plus one token from an identity provider not registered for any organization.
- A series that exists, a series that does not exist, a `ClusterOrder` whose `osac.openshift.io/project` annotation has been removed, a `hostedClusterName` that collides with another organization's, and a project-membership lookup that fails with a cold cache (fulfillment API stub or network policy).

##### Steps

1. Send each request below without a token, and once more with the unregistered-provider token, to the tenant and admin Routes.
2. As an authenticated Tenant Admin, ask for another organization's series.
3. As an authenticated Tenant User, ask for a series whose owner cannot be resolved — the `hostedClusterName` collides with another organization's.
4. Ask for a series that does not exist.
5. As an authenticated Tenant User, ask for the removed-annotation `ClusterOrder`'s series, then repeat the default-project and a named-project query with a cold membership cache.
6. Compare the status code, `Content-Type`, and body of steps 2, 3, and 4.

##### Expected Results

- Step 1 returns `401` with an authentication error; no empty-200 disguise and no `403` for a missing claim that would distinguish "unregistered provider" from "no token".
- Steps 2, 3, and 4 all return `200`; their bodies are identical (`data.result: []`), so a caller cannot tell denial, nonexistence, and an unresolvable cluster identity apart.
- Step 5 returns the removed-annotation `ClusterOrder`'s series, and the cold cache returns the default-project series and an empty body only for the named project: an absent annotation is the default project, and a cold cache degrades to it rather than failing.
- No step 2–5 response is `5xx`. The one availability case that may be `503` — the inventory has never listed — is TC-R8-04, and it is identical for every caller.

---

### NFR-3: Availability is per cluster — fair use bounds one tenant's load

#### TC-NFR3-01: Per-organization concurrency limit prevents one tenant from exhausting the query layer

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-7 | medium | automated |

##### Preconditions

- Fair-use limits configured with `observability.tenant.limits` defaults.
- Two organizations, tenant-a and tenant-b, have tokens.

##### Steps

1. From tenant-a, issue queries beyond the configured `maxConcurrentQueries`.
2. While tenant-a is saturated, issue a single query from tenant-b.
3. Check the status codes returned to tenant-a.
4. Repeat the same over-limit query with a Cloud Provider Admin and a Cloud Infrastructure Admin token.

##### Expected Results

- Tenant-a receives HTTP 429 with a `Retry-After` header once over the configured concurrency.
- Tenant-b's query returns HTTP 200 with its own series, unaffected by tenant-a's load.
- Step 4 succeeds: the admin Routes are not subject to the tenant limits, which is the distinction the PRD's fair-use requirement draws.
- The admin Routes are unaffected by tenant-a's load.

---

#### TC-NFR3-02: Time-range and timeout limits are enforced per organization

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-7 | medium | automated |

##### Preconditions

- Fair-use limits configured with `observability.tenant.limits.maxQueryRange=24h` and `queryTimeout=2m`.
- Tenant-a token available, plus one admin token.

##### Steps

1. Request a range query spanning 30 days.
2. Request a query that would run longer than the configured timeout.
3. Repeat steps 1 and 2 with the admin token.

##### Expected Results

- The 30-day range query is rejected with HTTP 422 and an error naming the maximum range; it carries no `Retry-After`, because the range is deterministic.
- The long-running query is aborted with HTTP 504.
- Step 3 succeeds, so the limit is a tenant limit, not a Route-wide one.
- Neither request degrades the admin endpoint.

---

#### TC-NFR3-03: One covered cluster stops reporting and the interface stays available

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-9, IC-10 | critical | automated |

##### Preconditions

- At least two covered clusters remote-write: cluster A will be stopped (fault injection: stop its collector or delete its remote-write configuration) and cluster B stays healthy.

##### Steps

1. Stop the collector on cluster A for longer than one collection interval.
2. Query the pipeline-health signals for both clusters — `time() - max by (cluster) (timestamp(last_over_time(up{managed_by="osac"}[1h]))) > <infrastructure interval in seconds>` — and a query for each cluster's recent data.
3. Continue querying cluster B's series, a management-cluster series, and an unrelated tenant's series.
4. Restart cluster A's collector.

##### Expected Results

- Step 2 returns cluster A from the stopped-cluster query and nothing for cluster B; cluster A's recent-data query returns no samples in the interval, while cluster B's returns data. No `ClusterOrder` or import inventory is read to answer the question.
- Step 3 returns `200` with data throughout; only cluster A's series is missing, and no query fails because of cluster A.
- After the restart, cluster A's series reappear within one collection interval (NFR-4) and the stopped signal clears.

---

### NFR-4: Freshness

#### TC-NFR4-01: A metric emitted by a running resource becomes queryable within the interval that covers its class

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2, IC-7, IC-10 | high | automated |

##### Preconditions

- `observability.collection.osacControlPlane` and `observability.collection.infrastructure` set to distinguishable values.
- A running VM, a running covered cluster, and synchronized clocks between the emitter and the test driver.

##### Steps

1. Start a resource that emits a known series and record the emit time T0.
2. Poll the admin Route every second until the series appears and record T1.
3. Repeat for a management-cluster control-plane series (`osacControlPlane`, the ServiceMonitor `interval`) and for a guest node series (`infrastructure`, CMO's `scrapeInterval`).
4. Double `observability.collection.infrastructure` and repeat step 2 for a VM series, a volume series, and a guest node series.

##### Expected Results

- `T1 − T0` is at most the interval of the key that covers the class — `osacControlPlane` or `infrastructure` — plus one remote-write hop.
- Step 4 moves `T1` by the same amount for every class covered by `infrastructure`, because they share CMO's single `scrapeInterval`. The test does not require a separate interval for a class that shares it: an independent interval per class is deferred, and the check is against `infrastructure` or `osacControlPlane`.
- The `osacControlPlane` class is unaffected by step 4, since it is a ServiceMonitor interval and not CMO's scrape interval.
- The test states the interval values it used, so the bound is arithmetic rather than a fixed string.

---

### NFR-5: Compatibility

#### TC-NFR5-01: A standard Prometheus client executes the five supported endpoints unmodified

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | critical | automated |

##### Preconditions

- A tenant token and both admin tokens.
- An unmodified standard Prometheus client (`promtool query …` or the official Go `api` package) with only the server URL pointed at the Route.

##### Steps

1. Run an instant query, a range query, a label-name listing, a label-value listing, and a series listing against the tenant Route.
2. Repeat against `thanos-query-admin` (Keycloak) and `thanos-query-admin-openshift` (OpenShift OAuth).

##### Expected Results

- All five calls succeed and parse with no custom path, header, or response handling; the client needs no modification of any kind.
- Responses are Prometheus JSON and range results are step-aligned.
- Step 2 returns the same shapes on both admin Routes.

---

#### TC-NFR5-02: An endpoint outside the supported subset returns an explicit not-supported error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | high | automated |

##### Preconditions

- A tenant token and both admin tokens.

##### Steps

1. Call `/api/v1/metadata`, `/api/v1/targets`, `/api/v1/rules`, `/api/v1/alerts`, `/api/v1/status/runtimeinfo`, `/api/v1/admin/tsdb/snapshot`, and `/api/v1/stores` on the tenant Route.
2. Repeat on both admin Routes.

##### Expected Results

- Every request returns HTTP 501 with a Prometheus-format error body naming the endpoint unsupported.
- No request is proxied to Thanos and none returns partial data.
- Step 2 behaves identically: the allowlist is the same on all three front doors.

---

### NFR-6: Capacity

#### TC-SCALE-01: Pipeline sustains the documented 503,000-series ceiling and reports it

**Acceptance:** 503,000 distinct active series ingest for one hour with `thanos_receive_write_queue_length` below 1000, no remote-write failures, components within their limits, and the admin series-count query reporting the same total.

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-6, IC-9 | high | manual |

##### Preconditions

- A synthetic remote-write generator produces 503,000 active series at a representative scrape interval.
- Thanos components are sized per the design's sizing table.

##### Steps

1. Run the generator for 1 hour.
2. Monitor `thanos_receive_write_queue_length`, `prometheus_remote_storage_failed_samples_total`, and S3 upload success.
3. Count distinct series at the end of the run.
4. Query the capacity signal on the admin Route: `GET /api/v1/query?query=prometheus_tsdb_head_series{cluster="management"}`.

##### Expected Results

- Distinct active series reaches at least 503,000.
- `thanos_receive_write_queue_length` stays below 1000 throughout.
- No remote-write failures accumulate.
- Thanos Receive and Compactor memory stay below their limits.
- Step 4 returns the same series count the generator produced, within one scrape interval: capacity is reported through the pipeline-health signal rather than absorbed, and nothing is dropped or downsampled to stay under the ceiling.

---

#### TC-SCALE-02: Queries succeed at the supported ceiling and stay within resource limits

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4, IC-5 | medium | manual |

##### Preconditions

- The 503,000-series load from TC-SCALE-01 is being ingested.
- Admin and tenant tokens are available.

##### Steps

1. While the load generator runs, issue an instant query, a 24-hour range query scoped to one resource, and a tenant range query scoped to one project — on the admin Route and on the tenant Route.
2. Record Thanos Query CPU and memory during the queries.

##### Expected Results

- Every query returns HTTP 200 with the correct scope and no `504`; none exceeds the configured `queryTimeout`.
- Thanos Query CPU and memory stay below their configured limits.
- This is a resource and correctness check, not a latency gate: no response-time threshold is asserted, because the PRD sets none and the design sets none either.

---

## Acceptance Criteria Traceability

One case per PRD acceptance criterion. Tiers and owners follow
`docs/INTEGRATION-TESTING.md`: Unit, Envtest, Component integration, and Contract
on changed implementation code belong to `[DEV]`; deployed cross-component user
journeys belong to `[QE]`.

| AC | PRD criterion (abbreviated) | Case(s) | Tier | Owner |
|----|-----------------------------|---------|------|-------|
| AC-1 | CPA queries ≥1 series from each of the five control-plane components | TC-R1-04 | E2E | `[QE]` |
| AC-2 | CPA queries one named tenant and receives that tenant's series only | TC-R7-08 | E2E | `[QE]` |
| AC-3 | CIA queries node, hypervisor, and control-plane for management and every covered cluster, including imported | TC-R6-05 | E2E | `[QE]` |
| AC-4 | Tenant Admin queries every VM, backing volume, and owned cluster in the organization | TC-R7-18 | Component integration | `[DEV]` |
| AC-5 | Tenant Admin query returns nothing for management nodes and imported clusters | TC-R7-19 | Component integration | `[DEV]` |
| AC-6 | Tenant User queries the VMs, volumes, and clusters of their projects | TC-R7-20 | Component integration | `[DEV]` |
| AC-7 | Tenant User query returns nothing for another project's resource or cluster | TC-R7-21 | Component integration | `[DEV]` |
| AC-8 | Hosted control plane returned to the owning organization's Tenant Admin and the owning project's Tenant User, not only admins | TC-R7-22 | Component integration | `[DEV]` |
| AC-9 | Another organization's series is an empty success, including metric-name, label-value, and series listings | TC-R7-04, TC-R7-23 | Contract | `[DEV]` |
| AC-10 | Denied and nonexistent return the same status and empty body | TC-R7-23 | Contract | `[DEV]` |
| AC-11 | An unresolvable owner returns the same empty success as an unauthorized query; an empty project is not an unresolvable owner | TC-R7-24 | Component integration | `[DEV]` |
| AC-12 | Unregistered identity provider is rejected; rejection persists after registration removal | TC-R7-06, TC-R7-07 | E2E | `[QE]` |
| AC-13 | Tenant concurrency and time-range breaches are rejected while the same admin query succeeds | TC-NFR3-01, TC-NFR3-02 | E2E | `[QE]` |
| AC-14 | Inside the window returns data; wholly past it returns empty success | TC-R5-02 | E2E | `[QE]` |
| AC-15 | Same project and time range return the same data to the Tenant Admin and a Tenant User | TC-R7-25 | Component integration | `[DEV]` |
| AC-16 | A tenant workload series returns nothing for every role | TC-R4-02, TC-R4-03 | Component integration | `[DEV]` |
| AC-17 | A stopped collector shows its cluster stopped and returns no recent data; a healthy cluster shows the opposite | TC-R8-05 | E2E | `[QE]` |
| AC-18 | A standard Prometheus client runs an instant query, a range query, a label listing, and a series listing unmodified | TC-NFR5-01 | Contract | `[DEV]` |
| AC-19 | An endpoint outside the subset returns an explicit not-supported error | TC-NFR5-02 | Contract | `[DEV]` |

## Tier and Owner Coverage

Every case is classified once. The groups are the tier and owner assigned in
each case's table; a case with several assertions stays in the tier that can
execute all of them.

| Tier | Owner | Cases | Count |
|------|-------|-------|-------|
| Unit | `[DEV]` | TC-R1-03, TC-R4-04, TC-R5-01, TC-R7-16, TC-R7-17, TC-R7-26, TC-R7-28 | 7 |
| Component integration | `[DEV]` | TC-R1-01, TC-R1-02, TC-R2-05, TC-R2-06, TC-R4-02, TC-R4-03, TC-R7-10, TC-R7-11, TC-R7-18, TC-R7-19, TC-R7-20, TC-R7-21, TC-R7-22, TC-R7-24, TC-R7-25, TC-R7-27, TC-R8-04, TC-R8-06 | 18 |
| Contract | `[DEV]` | TC-R2-07, TC-R6-01, TC-R6-02, TC-R6-03, TC-R7-01, TC-R7-02, TC-R7-03, TC-R7-04, TC-R7-05, TC-R7-12, TC-R7-13, TC-R7-14, TC-R7-15, TC-R7-23, TC-NFR2-01, TC-NFR5-01, TC-NFR5-02 | 17 |
| E2E | `[QE]` | TC-R1-04, TC-R2-01, TC-R2-02, TC-R2-03, TC-R2-04, TC-R4-01, TC-R5-02, TC-R6-04, TC-R6-05, TC-R7-06, TC-R7-07, TC-R7-08, TC-R7-09, TC-R8-01, TC-R8-02, TC-R8-03, TC-R8-05, TC-NFR3-01, TC-NFR3-02, TC-NFR3-03, TC-NFR4-01, TC-SCALE-01, TC-SCALE-02 | 23 |

## Gaps

### Requirement Coverage Gaps

- **R1, R2, R4, R5, R6, R7, R8:** covered.
- **R3 (GPU):** retired with the PRD's move of GPU metrics to OSAC-7246. No coverage is expected in this Feature.
- **NFR-1 (authorization is not an existence oracle):** covered by TC-R7-01 through TC-R7-05, TC-R7-09 through TC-R7-17, and TC-R7-23 through TC-R7-28, with the enumeration half carried by TC-R7-04 and TC-R7-23 and the workload-class boundary by TC-R4-02 and TC-R4-03. The project-scope half is TC-R7-20, TC-R7-21, TC-R7-26, TC-R7-27, and TC-R7-28.
- **NFR-2 (failure contract):** covered by TC-NFR2-01, which separates the authentication error from the empty success and from the unresolved owner, and by TC-R7-06 and TC-R7-07 for the identity-provider half and TC-R7-24 for owner resolution and the default-project rule. TC-R8-04 accepts a `503` for the inventory-never-listed state and TC-R8-06 for a watch that fails past its 30-second grace period; both are caller-invariant.
- **NFR-3 (availability is per cluster, fair use bounds one tenant's load):** covered by TC-NFR3-01 and TC-NFR3-02 for per-tenant concurrency and time range with an admin control that still succeeds, TC-NFR3-03 for one cluster stopping while the interface stays up, and TC-R8-05 for the stopped-collector fault. The PRD states no availability percentage, so no measurement window is a coverage gap; a sustained availability probe remains OSAC-6990 work.
- **NFR-4 (freshness):** covered by TC-NFR4-01, which bounds the emit-to-query interval by the class interval plus one hop and shows the bound moves when the interval changes. The per-class interval values themselves are IC-7 configuration, rendered by the chart-render unit tests in the design's Test Plan section.
- **NFR-5 (compatibility):** covered by TC-NFR5-01 for the five supported endpoints through a standard client and TC-NFR5-02 for the explicit not-supported error on all three Routes.
- **NFR-6 (capacity):** covered by TC-SCALE-01 and TC-SCALE-02, with the reporting half of the requirement carried by the pipeline-health cases TC-R8-01, TC-R8-02, and TC-R8-03 — reaching capacity is visible as those signals degrade, never as silent series loss.
- **Design risk R9 (cluster identifier collision):** covered by TC-R7-11 for the `ClusterOrder` path and TC-R7-17 for `management`. The imported-cluster half of the mitigation — refusing an import whose name equals a live `hostedClusterName` or the literal `management` — is TC-R2-07, which is owned with OSAC-6488 because this design implements no import controller.

### Interface Change Coverage Gaps

All 9 active interface changes (IC-1–IC-7, IC-9, IC-10) are exercised by at least one test case.

- IC-1 (`cluster-monitoring-config`): covered by TC-R2-01, TC-R2-02, TC-R2-03, TC-R2-04, TC-R4-01, TC-R4-02, TC-R4-04, TC-R8-05, and TC-NFR4-01.
- IC-2 (ServiceMonitors): covered by TC-R1-01, TC-R1-02, TC-R1-03, TC-R1-04.
- IC-3 (Thanos Receive endpoint): covered by TC-R2-01, TC-R4-01, TC-NFR5-01, TC-SCALE-01.
- IC-4 (Thanos Query admin): covered by TC-R4-02, TC-R6-01, TC-R6-02, TC-R6-04, TC-R6-05, TC-R7-03, TC-R7-08, TC-R8-01, TC-R8-02, TC-R8-03, TC-R8-05, TC-NFR2-01, TC-NFR5-02, TC-SCALE-02.
- IC-5 (tenant Route and authorizer): covered by TC-R4-02, TC-R6-03, TC-R7-01 through TC-R7-28, TC-R8-03, TC-R8-04, TC-R8-06, TC-NFR2-01, TC-NFR3-01, TC-NFR3-02, TC-NFR3-03, TC-NFR4-01, TC-NFR5-01, TC-NFR5-02, TC-SCALE-02.
- IC-6 (External S3 object store): covered by TC-NFR5-01 and TC-SCALE-01.
- IC-7 (installer values): covered by TC-R5-01, TC-R6-04, TC-R8-05, and TC-NFR4-01. Chart schema rendering and the retention/resolution flags are covered by the unit tests listed in the design's Test Plan section.
- IC-9 (guest remote-write Route and write proxy): covered by TC-R2-03, TC-R2-04, TC-R2-05, TC-R2-06, TC-R2-07, TC-R4-03, TC-R7-09, TC-R7-10, TC-R7-11, TC-R7-17, TC-R7-22, TC-R8-03, TC-NFR5-01. Certificate issuance and renewal through `Issuer/osac-metrics-write-ca` is exercised by the integration test in the design's Test Plan section.
- IC-10 (guest remote-write configuration): covered by TC-R2-03, TC-R2-04, TC-R2-05, TC-R4-02, TC-R4-03, TC-R4-04, TC-R7-09, TC-R7-10, TC-R7-22.

### Follow-ups

- **Real per-unit series counts.** The series-count table in the design's *Supported scale* section is a planning guess: the per-node, per-hosted-control-plane, and per-volume figures have no scrape behind them. A follow-up captures the observed per-unit counts from the first deployment and replaces the table and the derived totals. No case in this plan treats any figure in that table as a pass/fail gate, and the capacity cases above assert the pipeline's behaviour and reporting, not the arithmetic.

### Open Design Questions Affecting Coverage

None. Tenant attribution is settled by locked decision 6 (no collect-time tenant label) and by the certificate-bound `cluster` label, so every case in this plan is written against a closed design rather than an open question.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 65 |
| Critical | 32 |
| High | 29 |
| Medium | 4 |
| Low | 0 |
| Automated | 62 |
| Manual | 3 (TC-R2-07, TC-SCALE-01, TC-SCALE-02) |
| Requirements with test cases | 8 / 8 active (R3 retired) |
| PRD acceptance criteria with a case | 19 / 19 |
| PRD NFRs with a case | 6 / 6 |
| Interface changes with test cases | 9 / 9 active |
| Unit / Component integration / Contract (`[DEV]`) | 7 / 18 / 17 |
| E2E (`[QE]`) | 23 |
