# Clarification Log — OSAC-8220

## Status

- Rounds completed: 4
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Decisions clarified by the requester

### R1.Q1: Persona coverage

Does the initial plugin capability apply to a specific persona, or can extensions add pages regardless of persona?

#### Answer

The extension mechanism is not persona-specific. The first implementation should allow pages to be added regardless of persona.

#### Impact

The PRD must describe persona-agnostic extension support and must not exclude Tenant Admin or Tenant User from the capability.

#### Decision (D1)

The first increment supports adding extension pages regardless of persona.

---

### R1.Q2: Page access control

Who controls which users can access a particular contributed page?

#### Answer

Access to a particular page is controlled by its specific extension.

#### Impact

The PRD should describe access as extension-specific rather than as a single host-wide persona rule.

#### Decision (D2)

Each specific extension controls access to its page.

---

### R1.Q3: Plugin API compatibility

Does the first increment promise compatibility for plugin API changes?

#### Answer

No. The plugin API may change, and the first increment does not provide plugin API compatibility guarantees.

#### Impact

The PRD must state that plugin API compatibility is not guaranteed and must not imply a stable compatibility contract.

#### Decision (D3)

The plugin API may change without a compatibility guarantee in the first increment.

---

### R1.Q4: Plugin and extension load failures

What should users see when a whole plugin or one of its extensions cannot be loaded?

#### Answer

Show an error message. The exact placement depends on the specific extension.

#### Impact

The PRD should require an error message for either failure level while allowing placement to vary by extension.

#### Decision (D4)

A plugin or individual extension load failure displays an error message, placed according to the specific extension.

---

### R1.Q5: Extension BFF authentication and authorization

What support is required when an extension uses a backend-for-frontend (BFF)?

#### Answer

The OSAC UI proxy should forward the user's token to the extension's BFF so the BFF can perform authentication and authorization checks.

#### Impact

The PRD must include extension BFF support and token forwarding for the BFF's user checks.

#### Decision (D5)

The OSAC UI proxy forwards the user's token to an extension's BFF for authentication and authorization checks.

---

## Round 2 — Audience, scope, and failure behavior

### R2.Q1: Persona stories for the first increment

The extension mechanism can add pages regardless of persona, but the ticket identifies one reference page. Which canonical personas should appear as affected users in the first-increment PRD: all four personas as supported audiences, or only the personas served by the reference page/workflow?

#### Answer

Only the personas directly served by the reference page/workflow should appear as affected users. The ticket identifies the Cloud Provider Admin as the user who opens the contributed page; the general plugin capability remains available for pages targeting any persona.

#### Impact

The first-increment PRD should describe only the reference page's user audience and the Cloud Infrastructure Admin's configuration workflow. It should not imply a tenant-specific reference page.

#### Decision (D6)

Persona-specific user stories cover only audiences served by the first reference workflow; the extension capability remains persona-agnostic. The page-audience interpretation is refined by D11 to include a shared story for Cloud Provider Admin, Tenant Admin, and Tenant User.

---

### R2.Q2: OSAC service scope and reference workflow

Which OSAC service(s) and user workflow should the one-page reference plugin represent? Should the 0.6 scope name BMaaS, CaaS, VMaaS, MaaS, or Enclave, or describe the plugin capability as cross-service UI support?

#### Answer

The plugin capability is cross-service. The first reference workflow is an authorized user opening an enabled contributed page from navigation or a direct link, without targeting a specific OSAC service.

#### Impact

The PRD describes a cross-service UI capability and uses page loading as the reference workflow rather than assigning the plugin framework to one OSAC service.

#### Decision (D7)

OSAC-8220 is scoped as a cross-service UI capability; its first reference page does not target a specific OSAC service.

---

### R2.Q3: Plugin approval and trust

The ticket refers to approved and trusted plugins and says a Cloud Infrastructure Admin enables or disables them through configuration. Who designates a plugin as approved/trusted, and is the Cloud Infrastructure Admin responsible for maintaining that decision through deployment configuration?

#### Answer

At the time of this answer, the Cloud Infrastructure Admin was identified as approving and configuring plugins. The requester later clarified in R3.Q1 that no separate approval is required.

#### Impact

The earlier interpretation of approval as a separate action is superseded. The Cloud Infrastructure Admin controls deployment configuration; deployment and enable/configuration are sufficient for OSAC UI to load a plugin.

#### Decision (D8)

The Cloud Infrastructure Admin controls plugin deployment configuration, including enablement. This decision's separate approval step is superseded by D10.

---

### R2.Q4: Failure isolation among extensions

If one extension from a plugin cannot load but another extension from the same plugin can, should the other extension remain available while the failed extension displays its error, or should the whole plugin be treated as failed?

#### Answer

Keep sibling extensions available when one extension fails to load; show the error for the failed extension.

#### Impact

The PRD requires failure isolation at the individual extension level as well as across built-in pages.

#### Decision (D9)

A failed extension displays its error while other successfully loaded extensions from the same plugin remain available.

---

## Round 3 — Plugin loading gate

### R3.Q1: Separate approval step

After a plugin is deployed and enabled/configured, is any additional explicit approval required before OSAC UI loads it?

#### Answer

No. Deployment and enable/configuration are sufficient for OSAC UI to start loading the plugin. No further explicit approval step is required.

#### Impact

The Cloud Infrastructure Admin manages deployment configuration and enablement. The PRD must not include a separate plugin approval action or gate.

#### Decision (D10)

OSAC UI starts loading a plugin once it is deployed and enabled/configured; no further explicit approval is required. This supersedes the separate approval step recorded in D8.

---

## Round 4 — Page audience and extension access

### R4.Q1: Shared page audience

Should the Cloud Provider Admin page-opening story also apply to Tenant Admin and Tenant User, and can extension access vary by role?

#### Answer

The page-opening capability is shared by Cloud Provider Admin, Tenant Admin, and Tenant User. Depending on the specific extension, access may be limited to selected roles or available to all roles.

#### Impact

The PRD uses one shared page-opening story for these three personas and states that each extension determines which roles can access its page.

#### Decision (D11)

Cloud Provider Admin, Tenant Admin, and Tenant User share the page-opening capability. An extension may be available to selected roles or all roles.

---

## Remaining Gaps

No clarification gaps remain that block drafting. The PRD should carry forward decisions D1–D5 and D7–D11; D6's page-audience interpretation is refined by D11.
