# Version Information Display in OSAC

| Field       | Value   |
|-------------|---------|
| Author(s)   | To be determined |
| Jira        | [OSAC-4730](https://redhat.atlassian.net/browse/OSAC-4730) |
| Date        | 2026-09-01 |

## Problem Statement

OSAC operators and users currently have no way to identify which versions of the backend (fulfillment-service) and frontend (osac-ui) are deployed without accessing the command line or inspecting deployment artifacts directly. This makes troubleshooting harder — support engineers cannot confirm deployed versions without technical access, operators cannot quickly validate that an upgrade succeeded, and users cannot include version information in bug reports. Without built-in version visibility, establishing basic deployment context requires additional back-and-forth during every support interaction.

## In Scope

- Version display in an About modal accessible from the application Masthead, following the PatternFly AboutModal pattern, consistent with Red Hat product UX conventions `[Clarify: R1.Q1]`
- Backend and frontend version strings displayed exactly as generated, with no transformation applied by the UI `[Clarify: R1.Q2]`
- "Unavailable" placeholder shown for the backend version when the backend service is unreachable; frontend version remains visible regardless of backend availability `[Clarify: R1.Q3]`
- About modal accessible only to authenticated users — not visible before login `[Clarify: R1.Q4]`
- CLI command to retrieve both backend and frontend version information `[Clarify: R1.Q5]`
- Automatic version updates on deployment — no manual configuration required

## Out of Scope

- Version compatibility validation between the frontend and backend components
- Version history or changelog display
- Version-based feature gating or conditional behavior
- Pre-login version display on the login screen `[Clarify: R1.Q4]`

## User Stories

All four OSAC personas interact with version information in the same way — the About modal and CLI display identical content regardless of role.

### Tenant User / Tenant Admin / Cloud Provider Admin / Cloud Infrastructure Admin

- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want to view the deployed backend and frontend version numbers in an About modal accessible from the Masthead so that I can quickly identify which versions are deployed for troubleshooting, environment verification, and bug reporting. `[Clarify: R1.Q1]`
- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want the About modal to display "unavailable" for the backend version when the backend service is unreachable so that I can distinguish between a missing version and a connectivity issue. `[Clarify: R1.Q3]`
- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want to retrieve backend and frontend version information via the OSAC CLI so that I can check deployed versions in scripts and automated workflows without opening the UI. `[Clarify: R1.Q5]`

## Assumptions

- The build systems for fulfillment-service and osac-ui support injecting version strings at build time.
- An existing OSAC CLI tool exists that can be extended with a version subcommand.
- The PatternFly component library is available in the osac-ui frontend project.

## Dependencies

- **Automatic version updates:** Version information must update automatically when new versions are deployed — no manual configuration required.
- **PatternFly:** The frontend relies on the PatternFly AboutModal component for the version display UI.
- **Backend version availability:** The UI must display the backend version without requiring the user to have CLI access.

## Open Questions

### Should version information be visible to unauthenticated users?

- **Owner:** To be determined
- **Impact:** Affects whether version details are exposed before login and whether external monitoring tools can access version information without credentials

The current scope restricts version display to authenticated users. Allowing unauthenticated access would simplify health checks and monitoring integrations, but would expose deployed version details to anyone who can reach the application.
