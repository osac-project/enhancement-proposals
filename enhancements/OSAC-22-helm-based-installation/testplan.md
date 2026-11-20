# Test Plan — OSAC-22 Helm-based installation

## Overview

- **Feature:** OSAC-22 — Helm-based installation
- **Source:** [README.md](README.md)
- **Total test cases:** 3

#### TC-HI-01: A fresh installation deploys every component

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no installer journey covers a fresh install.

#### TC-HI-02: Values validation rejects an inconsistent configuration

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no values-schema test exists.

#### TC-HI-03: An upgrade preserves existing resources

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no upgrade journey exists.
