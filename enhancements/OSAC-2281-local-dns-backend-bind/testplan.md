# Testplan — OSAC-2281

## Overview

- **Feature:** OSAC-2281 — Local DNS Backend Support — BIND Integration
- **Total test cases:** 11 (6 automated, 5 manual)
- **Requirements covered:** 6 of 7; the operator guide is documentation-only.
- **Interface changes covered:** 3 of 3.

Requirement labels below identify the relevant [PRD](prd.md#in-scope)
bullets and [clarification decisions](clarifications.md); the PRD does not
assign requirement numbers. These are planned checks, not execution results.

## Coverage Matrix

See the [OSAC testing policy](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md).
The role suite lives under `tests/unit/`, but runs the actual role and driver
over DNS against a protocol double. It does not substitute for testing with
real BIND.

| Row | Behavior | Requirement / interface | Tier and owner | Cases | Suite and command | Real boundary / doubles |
|---|---|---|---|---|---|---|
| M1 | Backend selection, schema validation, defaults and credential placement | CFG / IC-1 | Contract (Helm rendering), [DEV] installer | TC-CFG-01 | From `osac-installer/`, `make helm-deps`, then `helm unittest -f tests/dns_rfc2136_values_test.yaml charts/osac`. Requires the branch suite, Helm and helm-unittest | Real chart and schema, no Kubernetes cluster or job injection |
| M2 | Signed publication, marker lifecycle, and stale write rejection | LIFE, FAIL / IC-2 | Contract (protocol double), [DEV] AAP | TC-LIFE-01, TC-MARKER-01 | From `osac-aap/`, `uv run --group development pytest tests/unit/test_dns_rfc2136.py` with the extended branch suite | Real role, driver and client against an in-memory DNS endpoint, no BIND or AAP |
| M3 | Fail closed on DNS errors and redact credential and record data | FAIL, SAFE / IC-1, IC-2, IC-3 | Contract (protocol double), [DEV] AAP | TC-FAIL-01, TC-SAFE-01 | Same suite and command as M2 | Real Ansible task/callback output and DNS exchanges against an in-memory DNS endpoint, no live AAP or operator events |
| M4 | Persist the generation and hold the IP until verified cleanup | LIFE, FAIL / IC-2, IC-3 | Envtest, [DEV] operator regression | TC-FAIL-02 | `make test` from `osac-operator/` with extended `internal/controller/clusterorder_networking_test.go` cases | Real Kubernetes API, etcd and controller with doubled AAP results, no BIND |
| M5 | Provision, resolve and clean up using deployed CaaS and BIND | LIFE, TENANT / IC-1, IC-2 | E2E (manual), [QE] | TC-LIFE-02 | Follow the manual lab run below using existing cluster CLI/API and `dig` in an authorized lab | Real Fulfillment, operator, AAP jobs, credential injection, BIND, and tenant resolver |
| M6 | Failed deletion is observable and resumes after policy correction | FAIL, SAFE / IC-3 | E2E (manual), [QE] | TC-FAIL-03 | Follow the manual lab run below in the same lab | Same as M5, with a temporary policy change in a disposable zone |
| M7 | No Internet or external DNS provider for record management | LOCAL / IC-2 | E2E (manual), [QE] | TC-LOCAL-01 | Repeat M5 with DNS egress restricted and traffic or policy evidence available | Real role and BIND path; Internet and external DNS providers unavailable to the DNS job |
| M8 | Revoked marker rejects delayed publication and initialization | FAIL / IC-2, IC-3 | E2E (manual), [QE] | TC-FAIL-04, TC-FAIL-05 | Follow the manual lab run below with controlled job pauses in a disposable zone | Real OSAC, AAP, and BIND with controlled delivery of jobs and results |

## Test Case Index

| ID | Scenario | Interface | Priority |
|---|---|---|---|
| TC-CFG-01 | Select the driver and reject invalid values | IC-1 | high |
| TC-LIFE-01 | Create, rerun, replace and remove the exact RRsets | IC-2 | critical |
| TC-LIFE-02 | Resolve tenant endpoints and confirm authoritative cleanup | IC-1, IC-2 | critical |
| TC-FAIL-01 | Refused, invalid or unanswered requests fail closed | IC-2, IC-3 | critical |
| TC-FAIL-02 | Operator persists generations and holds the IP until verified cleanup | IC-2, IC-3 | critical |
| TC-FAIL-03 | BIND policy rejection blocks deletion until retry succeeds | IC-3 | critical |
| TC-FAIL-04 | BIND rejects delayed publication after the first clean check | IC-2, IC-3 | critical |
| TC-FAIL-05 | BIND rejects late initialization after revocation | IC-2, IC-3 | critical |
| TC-MARKER-01 | Prerequisites protect the marker and replacement records | IC-2 | critical |
| TC-SAFE-01 | Backend output omits key material and record data | IC-1, IC-2, IC-3 | high |
| TC-LOCAL-01 | Publish and remove records using only local DNS | IC-2 | high |

## Test Cases

### CFG: Installation-selected backend and TSIG configuration (D2, D4, D6)

#### TC-CFG-01: Select the driver and reject invalid values

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Steps:** Render defaults, Route 53, noop, and valid and invalid RFC 2136
values. Include missing required fields, invalid server addresses, invalid
ports, transports, and algorithms.
**Expected:** Existing backend renders do not require RFC 2136 settings.
Valid RFC 2136 values render non-secret keys in the ConfigMap and the TSIG
value only in the Secret. Invalid settings fail schema validation.

### LIFE: Publish and remove all CaaS endpoint records (D1, D3, D8)

#### TC-LIFE-01: Create, rerun, replace and remove the exact RRsets

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

**Steps:** Initialize both endpoint markers. Publish both API records and an
ingress wildcard, rerun unchanged, change the address or TTL, then revoke
and remove both endpoints twice. Keep an unrelated owner and type in the zone.
**Expected:** Updates carry valid TSIG. Reruns converge without duplicate
records. Changed records reflect the requested address or TTL. Both cleanup
passes leave the three requested A RRsets absent and the markers revoked.
Unrelated data is untouched.

#### TC-MARKER-01: Prerequisites protect the marker and replacement records

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

1. Inspect each signed update sent to the protocol double. Initialize `N`
   from marker name absence and require `active:N` in the same message
   as each publication. Revoke `N` and delete its RRsets in one message.
2. Try publishing `N` and initializing `N` again after revocation. Activate
   `N+1` from `revoked:N`, publish a different address, and replay cleanup
   and publication for `N`.
3. Revoke and remove `N` before the first initialization, with no marker
   present. Confirm `revoked:N` is created and the endpoint RRsets are
   absent. Also race cleanup against delayed first initialization and
   delayed replacement activation, exercising both arrival orders.
4. Run the ClusterOrder publish tasks with an unlisted base domain.
   Separately, try publishing with missing generation data or through
   a markerless legacy entry point.

**Expected:** Stale requests fail their prerequisites without changing the
marker or records. Neither first initialization nor replacement activation
can undo revocation. Cleanup for `N` leaves `N+1` and its records intact.
The invalid calls send no update. An unlisted base domain must fail the
AAP job, not skip publication and return success.

#### TC-LIFE-02: Resolve tenant endpoints and confirm authoritative cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | critical | manual |

Follow the [manual lab run](#manual-lab-run). Create a cluster with BIND
selected. After it becomes Ready, the authoritative primary returns the API
address for both API names and the ingress address for the exact wildcard.
The tenant resolver returns working API and console names from existing OSAC
URLs. Delete the cluster. All three A queries then report authoritative
absence and both endpoint markers are revoked, regardless of cached answers.

### FAIL: Block and retry on DNS failures (D7)

#### TC-FAIL-01: Refused, invalid or unanswered requests fail closed

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | automated |

**Steps:** Run publication or cleanup against the protocol double with a
wrong key, out-of-zone name, no response, or failed prerequisite. Include
`REFUSED` on the cleanup update and separately on verification after a
successful cleanup update. Supply no transaction response in another run.
**Expected:** The job fails with a sanitized diagnostic that names the
setting or permission to check. Invalid local inputs send no update;
Refused deletion does not report success or remove the existing record.
Refused verification and missing transaction responses also fail.
After correcting the fault, a rerun converges without leaving duplicate
records.

#### TC-FAIL-02: Operator persists generations and holds the IP until verified cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | automated |

1. Hold marker activation unconfirmed and reconcile across an operator
   restart. Confirm the generation is reused and publication starts only
   after activation is confirmed for that generation.
2. Give the controller the failed AAP result for an unlisted base domain
   and confirm ClusterOrder does not become Ready.
3. Request deletion after the first generation is persisted but before
   initialization is dispatched, and confirm cleanup starts and the IP
   stays held until verified revocation and removal.
4. Request deletion with a running publish job or an unanswered launch.
   Advance past the lost-launch timeout and reconcile before a late job
   appears. Cleanup may proceed without proving the publish job ended.
5. Return a timeout, a clean query without transaction confirmation, an
   update success with mismatched verification, and a stale AAP result
   in separate runs. Then return definitive success and verified
   `revoked:N` plus record absence for the current generation.
6. Schedule a replacement at the same name. Confirm no activation of
   `N+1` before the `N` hold is released. Once `N+1` is current, a late
   cleanup result for `N` must not release the replacement's IP.

**Expected:** Each unconfirmed result retains the finalizer and IP. Only
the matching successful revoke-and-remove result with verification releases
the hold. The harness doubles AAP results and cannot establish BIND behavior.

#### TC-FAIL-03: BIND policy rejection blocks deletion until retry succeeds

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | manual |

1. With a Ready cluster, temporarily revoke the TSIG key's update permission
   in the disposable zone, preserving query access. Request cluster deletion.
2. Confirm a rejected cleanup attempt in AAP and query the primary for the
   records. Check that the cluster has not completed deletion.
3. Restore the policy without resubmitting deletion. Observe the next
   scheduled cleanup attempt and query the primary again.

**Expected:** The failed job names the zone-policy setting to check without
printing credentials. Deletion does not complete while rejected records remain.
After policy restoration the next eligible retry removes the records and
deletion completes. Record the failed and successful job IDs and timestamps.

#### TC-FAIL-04: BIND rejects delayed publication after the first clean check

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | manual |

1. In the [BIND lab](#manual-lab-run), activate `N`. Pause its publish
   update before it reaches BIND. Request deletion and let the
   revoke-and-remove transaction commit.
2. Hold back the final verified AAP result from the controller. Query the
   primary and record the first clean A RRset result and `revoked:N`.
   Confirm the finalizer and IP are still held.
3. Deliver the delayed publish with its original generation and a valid
   TSIG signature. Check that BIND rejects the marker prerequisite, not
   authentication, and that the endpoint records remain absent.
4. Allow the verified AAP result to reach the controller. Confirm it
   releases the IP and the primary still reports absence.

#### TC-FAIL-05: BIND rejects late initialization after revocation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | manual |

1. With no marker at a fresh endpoint name, pause initialization for `N`
   before it sends its update. Request deletion and let cleanup install
   `revoked:N` and remove the endpoint RRsets.
2. Confirm the revoked marker and absent records directly on BIND. Resume
   the old initialization. Confirm BIND rejects the name-absence
   prerequisite and the TXT value stays `revoked:N`.
3. Confirm the controller releases the IP only on verified cleanup. Check
   that no publication starts from the late initialization and that the
   revoked marker remains after deletion.

### SAFE: Redact credentials and backend record data (D12)

#### TC-SAFE-01: Backend output omits key material and record data

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3 | high | automated |

**Steps:** Run the role with synthetic key and record data and capture
Ansible stdout and job-event data on success and failure.
**Expected:** No key material, record name, or record address appears in
the driver's output or failure messages. Existing administrator-facing
record/job identifiers are not a driver-output assertion; check on the
deployed path that they contain no credentials (M6).

### LOCAL: Manage records without an external DNS provider (D10)

#### TC-LOCAL-01: Publish and remove records using only local DNS

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | manual |

**Steps:** Repeat the lab lifecycle with the DNS job denied Internet and
external DNS-provider egress while retaining the local primary, local
resolver, and existing cluster control-plane dependencies.
**Expected:** Both publication and removal succeed, and traffic evidence
shows that the record-management calls used the configured primary only.
This is not a test of a fully disconnected CaaS stack.

### TENANT: Keep tenant interfaces unchanged (D5)

TC-LIFE-02 also covers this requirement: use existing UI, CLI, or API
URLs with no DNS provider selection or publication status. The lab
operator verifies resolution from a tenant network, not just the hub.

## Manual Lab Run

Use an authorized disposable BIND zone and an installed OSAC environment
with CaaS and AAP. Use the tenant's normal cluster workflow to create and
delete; record expected API and ingress addresses from the deployment.
From a host allowed to query the primary, substitute the primary address,
port, hosted cluster name, and base domain:

```bash
dig @"$PRIMARY" -p "$PORT" "api.$CLUSTER.$BASE" A +norecurse +noall +comments +answer
dig @"$PRIMARY" -p "$PORT" "api-int.$CLUSTER.$BASE" A +norecurse +noall +comments +answer
dig @"$PRIMARY" -p "$PORT" "*.apps.$CLUSTER.$BASE" A +norecurse +noall +comments +answer
dig @"$PRIMARY" -p "$PORT" "_osac-publish-api.$CLUSTER.$BASE" TXT +norecurse +noall +comments +answer
dig @"$PRIMARY" -p "$PORT" "_osac-publish-ingress.$CLUSTER.$BASE" TXT +norecurse +noall +comments +answer
```

Use TCP if the primary requires it. Check the authoritative (`aa`) flag.
After deletion require the expected `revoked:N` TXT value and `NXDOMAIN`
or `NOERROR` with no requested A RRset.
`REFUSED`, `SERVFAIL`, and no response are failures to obtain evidence.
Query the literal wildcard owner: a concrete application name can have an
explicit record that masks a missing wildcard. Separately check the
advertised cluster URLs using the tenant resolver after creation.

During a failure run, observe ClusterOrder and the AAP job at each eligible
retry. Use the retry time reported by the existing job diagnostics, allowing
one controller poll interval for scheduling, and the lab's normal job
timeout for completion. Record configured intervals and timestamps; a new
tenant deletion request must not be needed. Keep all evidence free of
credential material and restore the lab zone policy when finished.

## Gaps

### Requirement Coverage Gaps

- The BIND configuration and troubleshooting guide is documentation-only.
  Review it against the chart contract and lab procedure.
- No lab run or automated suite was executed for this design draft.
  The authorized BIND lab is still needed for M5–M8, including a way to
  pause jobs and delay the cleanup result. Automated BIND E2E remains a
  [PRD follow-up](prd.md#out-of-scope). No follow-up Jira key is recorded.

### Interface Change Coverage Gaps

All three interfaces have planned cases. Real BIND behavior, live
Secret-to-job injection, and end-to-end recovery are not established by
the component and Envtest suites.

## Summary

| Metric | Count |
|---|---|
| Total test cases | 11 |
| Critical / high | 8 / 3 |
| Automated / manual | 6 / 5 |
| Requirements with test cases | 6 / 7 |
| Interface changes with test cases | 3 / 3 |
