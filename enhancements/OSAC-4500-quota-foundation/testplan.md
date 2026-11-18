---
title: OSAC-4500 Quota Foundation Test Plan
last-updated: 2026-11-11
---

# Test Plan — OSAC-4500 Quota Foundation

Tests for the [Quota Foundation design](design.md).

## Unit Tests

- Each annotated resource's price, including what OSAC creates for it.
- The larger-of rule before, while and after OSAC creates resources.
- The limit order: override, default, 0.
- A resource with no quota annotations fails a test, unless it is on the list of resources that use nothing.

## Integration Tests

- A create or update over a project or tenant limit fails and writes nothing.
- Two parallel creates for the last vCPU: one succeeds.
- Requests run at READ COMMITTED.
- A cluster create and a VM create on the same subnet at once both finish.
- A crossed threshold writes one warning.

## E2E Tests

- A cluster create counts its hosts, and the hosts don't count twice once they exist.
