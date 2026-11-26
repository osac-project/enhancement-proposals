# OSAC UI Plugin Support

| Field       | Value |
|-------------|-------|
| Author(s)   | Rastislav Wagner |
| Jira        | [OSAC-8220](https://redhat.atlassian.net/browse/OSAC-8220) |
| Date        | 2026-11-25 |

## Problem Statement

Teams that build user interfaces independently have no supported way to contribute a page inside OSAC UI. As a result, users must switch consoles to reach those capabilities, while teams either move page code into OSAC UI or require a host rebuild for compatible page updates. OSAC needs a cross-service extension capability so users can open contributed pages in the console and Cloud Infrastructure Admins can control which plugins are available.

## In Scope

- The initial reference plugin contributes one page and a navigation entry. The plugin capability is cross-service and supports pages for any persona. [Jira: OSAC-8220, Clarify: R1.Q1, R2.Q2]
- Each extension controls which roles can access its page. An extension may be limited to selected roles or available to all roles; users without access cannot open the page from navigation or a direct link. [Jira: OSAC-8220, Clarify: R1.Q2, R4.Q1]
- A Cloud Infrastructure Admin manages whether deployed plugins are enabled or disabled through deployment configuration. Once a plugin is deployed and enabled/configured, OSAC UI starts loading it; no separate approval step is required. [Jira: OSAC-8220, Clarify: R3.Q1]
- A compatible update to a remote page can be deployed without rebuilding OSAC UI. The plugin API may change, and this increment provides no compatibility guarantee. [Jira: OSAC-8220, Clarify: R1.Q3]
- If a plugin or an individual extension cannot load, OSAC UI displays an error message at a placement determined by that extension. Built-in pages and other successfully loaded extensions from the same plugin remain available. [Jira: OSAC-8220, Clarify: R1.Q4, R2.Q4]
- The OSAC UI proxy forwards the current user's token to an extension's BFF so the BFF can perform authentication and authorization checks. [Clarify: R1.Q5]
- Documentation explains how to build, register, enable, disable, and version plugins; the current route and navigation behavior; and the rules for trusting remote bundles. It states that deployment and enable/configuration are sufficient for OSAC UI to load a plugin without separate approval, and that the plugin API may change without a compatibility guarantee. [Jira: OSAC-8220, Clarify: R1.Q3, R3.Q1]
- Automated integration coverage verifies page loading, extension-specific access, load-failure isolation, and that requests proxied to an extension's BFF include the current user's token. [Jira: OSAC-8220, Clarify: R1.Q2, R1.Q5, R2.Q4]

## Out of Scope

- A full AI Grid Console migration or delivery of its product pages.
- A plugin marketplace.
- Backend API or identity changes specific to individual plugins.

## User Stories

### Cloud Provider Admin / Tenant Admin / Tenant User

- As a Cloud Provider Admin, Tenant Admin, or Tenant User, I want to open an enabled plugin page that is available to my role from OSAC navigation or a direct link so that I can use the extension in OSAC UI without switching consoles. [Jira: OSAC-8220, Clarify: R4.Q1]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to enable or disable a deployed UI plugin through configuration so that I can control which extensions OSAC UI loads. [Jira: OSAC-8220, Clarify: R3.Q1]

## Dependencies

- **Independent UI teams:** Provide the independently built reference plugin page and its associated backend, if it uses one.

---

## Provenance

Authored: revise @ prd 0.11.5 - cd88680, workspace plugins @ 0b03fe65e
Phases: draft, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"0b03fe65e","source_repo_branch":"plugins","commits_behind_main":0,"commits_ahead_main":204,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
