# Test Plan — OSAC-41 Cluster as a Service

## Overview

- **Feature:** OSAC-41 — Cluster as a Service
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-CAAS-01: A cluster is created and becomes ready

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`

#### TC-CAAS-02: Deletion reports feedback and completes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py`

#### TC-CAAS-03: A NAT gateway is gated on the networking precondition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/caas/sanity/test_cluster_nat_gateway_gate.py`

#### TC-CAAS-04: Cluster reconciliation survives a provider failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no failure-injection test exists.
