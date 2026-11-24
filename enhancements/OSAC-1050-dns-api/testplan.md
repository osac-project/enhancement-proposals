# Test Plan — OSAC-1050 DNS API

## Overview

- **Design:** [Public design](README.md)
- **Total test cases:** 7

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The proposal shows the earlier Route 53 role name. The [current dispatcher default](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-aap/collections/ansible_collections/dns/api/roles/dns/defaults/main.yaml#L1) is `dns.route53.dns`. The unchanged-configuration test checks behavior at that default.

## Test Cases

#### TC-DNS-01: Dispatch selects the configured role

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Gap:** No matching dns_class dispatcher or per-driver assertions were verified in the public OSAC AAP role and CaaS test suites.

**Preconditions.** Supply two named driver doubles and select the second with dns_class.

1. Dispatch Create and Delete using identical record fixtures.
2. Capture each selected role and its record input.

**Expected results.** Only the configured role receives both operations with the original name, type and values.

#### TC-DNS-02: Unknown dns_class fails dispatch

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Gap:** No matching dns_class dispatcher or per-driver assertions were verified in the public OSAC AAP role and CaaS test suites.

**Preconditions.** Use a synthetic unregistered role value and an otherwise valid A record.

1. Dispatch Create with the fixture value.
2. Inspect the task result and driver call counts.

**Expected results.** The task reports the unsupported selection and neither known driver is invoked.

#### TC-DNS-03: Cluster lifecycle uses the configured DNS backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real test cluster, OSAC and AAP, selected DNS driver and a CI-owned zone. No external customer infrastructure or service doubles.
- **Gap:** The public AAP role and CaaS suites do not establish selected-driver create and delete DNS assertions.

**Preconditions.** Use an isolated cluster and two fixture zones. Configure the selected driver for one of them.

1. Provision the fixture cluster and resolve its API and ingress records.
2. Delete the cluster and query the authoritative zones again.

**Expected results.** The configured zone has the expected mappings during provisioning and no fixture records after delete. The other zone is unchanged.

#### TC-DNS-04: A driver error leaves the DNS task unsuccessful

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — provisioning workflow](README.md#cluster-provisioning-creates-dns-records)
- **Gap:** No matching dns_class dispatcher or per-driver assertions were verified in the public OSAC AAP role and CaaS test suites.

**Preconditions.** Use a driver double that returns a deterministic update failure.

1. Run the dispatcher task.
2. Inspect its result before recording provisioning completion.

**Expected results.** The DNS task reports the driver failure and does not return a successful record result.

#### TC-DNS-05: Each supported driver creates and removes IPv4 and IPv6 records

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real dispatcher and selected DNS driver against a dedicated CI-owned fixture zone and authoritative DNS query. No DNS or provider double.
- **Gap:** No matching dns_class dispatcher or per-driver assertions were verified in the public OSAC AAP role and CaaS test suites.

**Preconditions.** Provide a dedicated CI-owned zone per supported driver and unique ordinary and wildcard names.

1. Create A and AAAA records using documentation-range IPv4 and IPv6 fixture addresses. Query the ordinary names and names matching the wildcard.
2. Delete each record and query again.

**Expected results.** Each query returns the exact type and address while present, and each fixture answer disappears after delete.

#### TC-DNS-06: Existing Route 53 config works without adding dns_class

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Route 53 compatibility](README.md#upgrade--downgrade-strategy)
- **Dependencies:** Real dispatcher and selected DNS driver against a dedicated CI-owned fixture zone and authoritative DNS query. No DNS or provider double.
- **Gap:** No matching dns_class dispatcher or per-driver assertions were verified in the public OSAC AAP role and CaaS test suites.

**Preconditions.** Use a pre-dispatch Route 53 fixture configuration with no dns_class setting and a dedicated CI-owned zone.

1. Apply the unchanged configuration with the dispatcher version.
2. Create and delete an A record and read the authoritative answer at each stage.

**Expected results.** Routing defaults to `dns.route53.dns`. The fixture address appears on create and disappears on delete without adding a configuration override.

#### TC-DNS-07: CaaS DNS publish and removal task definitions select the configured driver

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — dispatcher role](README.md#new-role-osacservicedns-dispatcher)
- **Dependencies:** Real checked-in role definitions and YAML parsing. No Ansible role execution, resolver or provider.
- **Execution:** `osac-aap/tests/unit/test_cluster_endpoints_contract.py`
- **Evidence:** `test_dns_tasks_enforce_supported_domain_and_record_conventions` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-aap/tests/unit/test_cluster_endpoints_contract.py#L114)).
- **Selector:** `uv run --group development pytest tests/unit/test_cluster_endpoints_contract.py::test_dns_tasks_enforce_supported_domain_and_record_conventions` from `osac-aap` in OSAC.

**Preconditions.** Load the four CaaS API and ingress publish/removal task definitions as YAML.

1. Find the role include in each task and inspect its variable and record convention.

**Expected results.** All four definitions use the configured dns_class role and the hosted-cluster base domain. API tasks use the api-int name; ingress tasks use the wildcard under apps.
