# Test Plan — OSAC-1030 Organizations and authentication

## Overview

- **Feature:** OSAC-1030 — OSAC organizations and authentication
- **Source:** [README.md](README.md), [ui-design.md](ui-design.md)
- **Total test cases:** 4

#### TC-ORG-01: An organization is created with its identity provider

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers organization creation.

#### TC-ORG-02: A user in another organization is rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no cross-organization rejection test exists.

#### TC-ORG-03: Organization membership grants the documented access

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** no journey covers organization membership.

#### TC-ORG-04: Organization deletion cleans up identity resources

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Gap:** no cleanup test exists.
