# Testplan — OSAC-2281

## Overview

- **Feature:** OSAC-2281 — Local DNS Backend Support — BIND Integration
- **Total test cases:** 8 (5 automated, 3 manual)
- **Requirements covered:** 6 of 7; the operator guide is documentation-only.
- **Interface changes covered:** 3 of 3.

Requirement labels below identify the relevant [PRD](prd.md#in-scope)
bullets and [clarification decisions](clarifications.md); the PRD does not
assign requirement numbers. These are planned checks, not execution results.

## Coverage Matrix

See the [OSAC testing policy](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md).
The role suite lives under `tests/unit/`, but runs the actual role and module
over DNS against a protocol double. It does not substitute for testing with
real BIND.

| Row | Behavior | Requirement / interface | Tier and owner | Cases | Suite and command | Real boundary / doubles |
|---|---|---|---|---|---|---|
| M1 | Backend selection, schema validation, defaults and credential placement | CFG / IC-1 | Contract (Helm rendering), [DEV] installer | TC-CFG-01 | From `osac-installer/`, `make helm-deps`, then `helm unittest -f tests/dns_rfc2136_values_test.yaml charts/osac`; branch suite, Helm and helm-unittest required | Real chart and schema; no Kubernetes cluster or job injection |
| M2 | Signed per-record create, convergence, and precise delete | LIFE / IC-2 | Contract (protocol double), [DEV] AAP | TC-LIFE-01 | From `osac-aap/`, `uv run --group development pytest tests/unit/test_dns_rfc2136.py`; branch suite, vendored collections and local DNS sockets required | Real Ansible role, module and client; in-memory DNS endpoint, no BIND or AAP |
| M3 | Fail closed on DNS errors and redact credential and record data | FAIL, SAFE / IC-1, IC-2, IC-3 | Contract (protocol double), [DEV] AAP | TC-FAIL-01, TC-SAFE-01 | Same suite and command as M2 | Real Ansible task/callback output and DNS exchanges; in-memory DNS endpoint, no live AAP or operator events |
| M4 | Unconfirmed publication and failed cleanup preserve the hold and retry | FAIL / IC-3 | Envtest, [DEV] operator regression | TC-FAIL-02 | `make test` from `osac-operator/`; extend the existing `internal/controller/clusterorder_networking_test.go` cases | Real Kubernetes API, etcd and controller; AAP outcomes are recorded doubles; no BIND |
| M5 | Provision, resolve and clean up using deployed CaaS and BIND | LIFE, TENANT / IC-1, IC-2 | E2E (manual), [QE] | TC-LIFE-02 | Follow the manual lab run below using existing cluster CLI/API and `dig`; authorized lab required | Real Fulfillment, operator, AAP jobs, credential injection, BIND, and tenant resolver |
| M6 | Failed deletion is observable and resumes after policy correction | FAIL, SAFE / IC-3 | E2E (manual), [QE] | TC-FAIL-03 | Follow the manual lab run below in the same lab | Same as M5, with a temporary policy change in a disposable zone |
| M7 | No Internet or external DNS provider for record management | LOCAL / IC-2 | E2E (manual), [QE] | TC-LOCAL-01 | Repeat M5 with DNS egress restricted and traffic or policy evidence available | Real role and BIND path; Internet and external DNS providers unavailable to the DNS job |

## Test Case Index

| ID | Scenario | Interface | Priority |
|---|---|---|---|
| TC-CFG-01 | Select the driver and reject invalid values | IC-1 | high |
| TC-LIFE-01 | Create, rerun, replace and remove the exact RRsets | IC-2 | critical |
| TC-LIFE-02 | Resolve tenant endpoints and confirm authoritative cleanup | IC-1, IC-2 | critical |
| TC-FAIL-01 | Refused, invalid or unanswered requests fail closed | IC-2, IC-3 | critical |
| TC-FAIL-02 | Existing controller keeps the cleanup hold across failure | IC-3 | critical |
| TC-FAIL-03 | BIND policy rejection blocks deletion until retry succeeds | IC-3 | critical |
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
ports, transports and algorithms.
**Expected:** Existing backend renders do not require RFC 2136 settings.
Valid RFC 2136 values render non-secret keys in the ConfigMap and the TSIG
value only in the Secret. Invalid settings fail schema validation.

### LIFE: Publish and remove all CaaS endpoint records (D1, D3, D8)

#### TC-LIFE-01: Create, rerun, replace and remove the exact RRsets

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

**Steps:** Create both API records and an ingress wildcard through the
configured role; rerun unchanged, change the address or TTL, delete the
three records, and delete again. Keep an unrelated owner and type in the zone.
**Expected:** Updates carry valid TSIG, an unchanged rerun makes no write,
and changed records reflect their new address or TTL. Both deletion passes
leave the three requested RRsets absent without removing unrelated data.

#### TC-LIFE-02: Resolve tenant endpoints and confirm authoritative cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | critical | manual |

Follow the [manual lab run](#manual-lab-run). Create a cluster with BIND
selected. After it becomes Ready, the authoritative primary returns the API
address for both API names and the ingress address for the exact wildcard.
The tenant resolver returns working API and console names from existing OSAC
URLs. Delete the cluster; all three primary queries then report authoritative
absence, regardless of any cached answers.

### FAIL: Block and retry on DNS failures (D7)

#### TC-FAIL-01: Refused, invalid or unanswered requests fail closed

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | automated |

**Steps:** Run create or delete against the protocol double with a wrong
key, out-of-zone name, no response, or failed prerequisite. Include a
delete where the server returns `REFUSED` to the existence check while the
record still exists. Extend the branch suite with a module-result fixture
that returns without `dns_rc_str` on delete.
**Expected:** The job fails with a sanitized diagnostic that names the
setting or permission to check. Invalid local inputs send no update;
refused deletion does not report success or remove the existing record.
The incomplete result also fails rather than confirming absence.
After correcting the fault, a rerun converges without leaving duplicate
records.

#### TC-FAIL-02: Existing controller keeps the cleanup hold across failure

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

1. In the ClusterOrder Envtest harness, request deletion while AAP reports
   a publish job still running after cancellation is requested. Reconcile,
   then have AAP report the job ended and reconcile again.
2. Repeat with an unanswered launch and no job visible by label. Advance
   past the lost-launch timeout and reconcile before the late job appears.
   Then reconcile with the late job reported as running, and again after
   AAP reports that it ended.
3. After publication has stopped, fail the remove job, advance the retry
   state, and complete the next remove job.

**Expected:** While publication may still write, the controller requeues
without launching removal and retains the DNS finalizer. Only after AAP
confirms the job ended does removal start. A failed remove job still
retains the hold; a successful retry releases it. The harness controls AAP
outcomes and retry timing without real-time polling.

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
```

Use TCP if the primary requires it. Check the authoritative (`aa`) flag;
after deletion require `NXDOMAIN` or `NOERROR` with no requested RRset.
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
  The authorized BIND lab is still needed for M5–M7. Automated BIND E2E
  remains a [PRD follow-up](prd.md#out-of-scope); no follow-up Jira key is
  recorded in the proposal.

### Interface Change Coverage Gaps

All three interfaces have planned cases. Real BIND behavior, live
Secret-to-job injection, and end-to-end recovery are not established by
the component and Envtest suites.

## Summary

| Metric | Count |
|---|---|
| Total test cases | 8 |
| Critical / high | 5 / 3 |
| Automated / manual | 5 / 3 |
| Requirements with test cases | 6 / 7 |
| Interface changes with test cases | 3 / 3 |
