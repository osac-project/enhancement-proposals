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
- Backend and frontend version strings displayed as provided by the build system with no format transformation applied by the UI `[Clarify: R1.Q2]`
- "Unavailable" placeholder shown for the backend version when the backend service is unreachable; frontend version remains visible regardless of backend availability `[Clarify: R1.Q3]`
- About modal accessible only to authenticated users — not visible before login; backend version service authentication is an open question (see below) `[Clarify: R1.Q4]`
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

- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want to view the deployed backend (fulfillment-service) and frontend (osac-ui) version numbers in an About modal accessible from the Masthead so that I can quickly identify which versions are deployed for troubleshooting, environment verification, and bug reporting. `[Clarify: R1.Q1]`
- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want the About modal to display "unavailable" for the backend version when the backend service is unreachable so that I can distinguish between a missing version and a connectivity issue. `[Clarify: R1.Q3]`
- As a Tenant User, Tenant Admin, Cloud Provider Admin, or Cloud Infrastructure Admin, I want to retrieve backend and frontend version information via the OSAC CLI so that I can check deployed versions in scripts and automated workflows without opening the UI. `[Clarify: R1.Q5]`

## Design Reference

OpenShift AI (RHOAI) uses an enriched PatternFly AboutModal that serves as design inspiration for OSAC's version display. The RHOAI About modal includes:

- Product name and description
- Product version with release channel
- API server URL
- User type (e.g., admin vs. regular user)
- "Last updated" timestamp indicating when the current version was deployed
- An installed components table mapping each component to its upstream project and version

The core scope above covers the initial delivery. The stretch goals below capture RHOAI-inspired enhancements that may be pursued in future iterations.

## Stretch Goals

The following items are not required for the initial delivery of this feature but represent valuable enhancements inspired by the RHOAI About modal pattern. Each extends the About modal with richer deployment context.

- **Deployed-at timestamp:** The About modal displays a timestamp showing when the current version was deployed, similar to RHOAI's "Last updated" field. This helps operators confirm that a recent deployment took effect. `[User]`
- **Installed components table:** The About modal includes a table listing all OSAC services and their versions. Known services include fulfillment-service, osac-operator, osac-ui, and osac-aap; the table should accommodate additional services as the platform grows. This gives operators a single view of the full deployment state. `[User]`
- **Release channel:** If OSAC adopts release channels (e.g., stable, preview), the About modal displays the active release channel alongside the version information. `[User]`

## Assumptions

- Released fulfillment-service binaries already contain injected version strings via `.goreleaser.yaml`. The osac-ui build system is assumed to support equivalent version injection.
- Version sub-commands already exist in both the CLI (`fulfillment-service/internal/cmd/cli/version/`) and the service (`fulfillment-service/internal/cmd/service/version/`). These may need to be surfaced or extended to provide version information to the UI and external callers. `[PR review: jhernand]`
- The PatternFly component library is available in the osac-ui frontend project.

## Dependencies

- **Build pipelines:** Both fulfillment-service and osac-ui CI/CD pipelines must be updated to inject version strings during the build process.
- **PatternFly:** The frontend relies on the PatternFly AboutModal component for the version display UI.
- **Backend version service:** The frontend requires a gRPC service (or an extension to an existing service such as capabilities) that exposes the backend version. The corresponding REST method is auto-generated from the gRPC definition. `[PR review: jhernand]`

## Open Questions

### Should the backend version service method require authentication?

- **Owner:** To be determined
- **Impact:** Affects authentication scope and security posture of the version service

Should the gRPC method that returns the backend version require authentication, or be publicly accessible? Unauthenticated access simplifies health checks and monitoring integrations, but exposes deployed version details to unauthenticated callers. `[PR review: jhernand]`
