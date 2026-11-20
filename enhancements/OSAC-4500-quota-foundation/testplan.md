---
title: OSAC-4500 Quota Foundation Test Plan
last-updated: 2026-11-18
---

# Test Plan — OSAC-4500 Quota Foundation

Tests for the [Quota Foundation design](design.md).

Each case names its tier so the coverage report can count it. Priorities are
proposed and need the feature owner's confirmation.

## Unit

#### TC-U-01: Each annotated resource's price

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit

Each annotated resource's price is computed, including the resources OSAC
creates for it.

#### TC-U-02: The larger-of rule

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit

The larger-of rule holds before, while, and after OSAC creates resources.

#### TC-U-03: Limit order

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit

The limit order is override, then default, then 0.

#### TC-U-04: A resource without quota annotations

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit

A resource with no quota annotations fails a test, unless it is on the list of
resources that use nothing.

## Component integration

#### TC-I-01: Over-limit writes are rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration

A create or update over a project or tenant limit fails and writes nothing.

#### TC-I-02: Last vCPU race

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration

Two parallel creates for the last vCPU: one succeeds.

#### TC-I-03: Isolation level

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration

Requests run at READ COMMITTED.

#### TC-I-04: Concurrent cluster and VM creation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration

A cluster create and a VM create on the same subnet at once both finish.

#### TC-I-05: Threshold warning

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration

A crossed threshold writes one warning.

## E2E

#### TC-E-01: Cluster hosts are counted once

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E

A cluster create counts its hosts, and the hosts do not count twice once they
exist.
