---
title: Netris CA support for AAP execution environments
authors:
  - etabak@redhat.com
creation-date: 2026-10-08
last-updated: 2026-10-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5971
  - https://redhat.atlassian.net/browse/OSAC-5972
---

# Netris CA support for AAP execution environments

## Problem

Customers using a private or self-signed Netris CA cannot keep TLS verification
enabled in OSAC-managed AAP jobs without rebuilding the execution environment
image or disabling certificate validation.

## User outcomes

- Configure a customer-owned, same-namespace CA ConfigMap by name without
  uploading certificate contents to OSAC.
- Run Netris-calling OSAC jobs with the configured CA and HTTPS validation.
- Keep deployments without a custom CA on the system trust store.
- Rotate or roll back the CA declaratively without changing the image.
- Fail closed for missing, unauthorized, invalid, or overridden CA input.

## Scope and success criteria

The design covers installer values and validation, AAP execution-pod
propagation, protected Netris launch inputs, and integration tests. The
supported installation flow must execute representative networking,
cluster-fulfillment, and BMaaS operations against a private-CA Netris endpoint,
reject protected-input overrides, and complete documented CA rotation and
rollback.
