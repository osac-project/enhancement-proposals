# Test Plan — OSAC-983 Reliable event distribution

## Overview

- **Feature:** OSAC-983 — Reliable event distribution
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-EV-01: The trigger enqueues an outbox row for every change

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no trigger test exists.

#### TC-EV-02: The publisher emits in serial order and deletes after ack

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`

#### TC-EV-03: A crash after produce re-produces the row safely

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no crash-simulation test exists.

#### TC-EV-04: The topic name is osac.events.<tenant> for boundary names

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no topic-naming test exists.

#### TC-EV-05: The bridge sets Event.id from topic, partition, and offset

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no bridge test exists.
