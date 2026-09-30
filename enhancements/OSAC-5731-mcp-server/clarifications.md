# Clarification Log — OSAC-5731

## Status

- Rounds completed: 14
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Initial scope and supported hosts

### R1.Q1: Resource journeys

Beyond the ComputeInstance PoC, which infrastructure journeys must the first delivery support: clusters, bare metal, tenant networking, or something else?

#### Answer

The user said yes to everything that makes sense, explicitly naming bare metal, clusters, and networking, among other applicable resources.

#### Impact

The PRD must not equate this Feature with the VM PoC. It needs an explicit inventory of resource journeys and an agreed meaning of “applicable” before each journey can have testable requirements.

#### Decision (D1)

The Feature covers infrastructure journeys beyond ComputeInstance, including bare metal, clusters, networking, and other applicable OSAC resources. It is not a VM-only Feature.

---

### R1.Q2: Meaning of manage

For the selected resources, which actions must be supported: discovery, creation, status, update, start/stop, and deletion?

#### Answer

The user wants all of those actions wherever they make sense for the resource.

#### Impact

The PRD needs a resource-by-action inventory. It should not assume that every action is meaningful for every resource, or that the four PoC tools are the final product surface.

#### Decision (D2)

Support all applicable lifecycle actions for each selected resource, rather than limiting the Feature to the PoC's create, read, and delete actions. The applicable action set still needs definition per resource.

---

### R1.Q3: Missing prerequisites

May a request require catalog offerings, networking, and storage to exist already, or must users be able to create missing tenant prerequisites through MCP?

#### Answer

Users should be able to create missing prerequisites. OSAC and Keycloak tenant permissions should restrict actions that a user is not allowed to perform.

#### Impact

The PRD must cover an authorized user's path to create needed prerequisites, as well as the experience when permissions prevent an action. It must identify which prerequisites are tenant-manageable and which require another authorized role; it must not assume that the ComputeInstance PoC's pre-seeded environment is the final product experience.

#### Decision (D3)

The supported user journeys include creating missing prerequisites when the caller is authorized. Existing OSAC/Keycloak tenant permissions remain the access boundary; an unauthorized caller must not gain that capability through MCP.

---

### R1.Q4: Initial model hosts

Which model hosts should be officially supported initially? The PoC exercised Codex and Inspector; should Cursor, VS Code, or Claude be included?

#### Answer

Cursor, Codex, and Claude should be supported for starters.

#### Impact

The PRD needs user-observable onboarding and interoperability expectations for these three host families. The exact Claude product and Codex interface still need confirmation.

#### Decision (D4)

Cursor, Codex, and Claude are the initial supported model-host families.

---

## Round 2 — Delivery sequence and prerequisite ownership

### R2.Q1: Resource journeys and rollout

For the first delivery, must VMs, clusters, bare metal, and networking all have complete end-to-end journeys, or should the Feature define a staged rollout? If staged, which journey comes first?

#### Answer

The user wants complete journeys for all four named resource families. They can be implemented as separate tasks in a staged rollout, with networking first.

#### Impact

The PRD must describe the intended outcomes for all four families and identify networking as the first delivery sequence. Task-level staging does not remove the other three families from the Feature's intended scope. This resolves the tension with the source issue's exclusion of immediate parity with *every* OSAC resource type: the four named families are in scope, while the exact set of additional applicable resources still needs confirmation.

#### Decision (D5)

The Feature includes end-to-end networking, VM, cluster, and bare-metal journeys, implemented in stages beginning with networking.

---

### R2.Q2: Existing versus new OSAC actions

Should MCP expose only lifecycle actions OSAC already supports, or does this Feature also require adding missing OSAC capabilities?

#### Answer

Only actions OSAC already supports are in scope.

#### Impact

The PRD should inventory user-facing actions available through OSAC for each resource family and make those accessible through the supported MCP experience where applicable. A missing underlying OSAC capability is not a requirement to build that capability as part of this Feature.

#### Decision (D6)

The Feature exposes applicable existing OSAC capabilities; it does not add new underlying infrastructure-management actions to OSAC.

---

### R2.Q3: Ownership of missing prerequisites

Should authorized tenant users be able to create any missing prerequisite, including catalog offerings, images, and storage tiers, or should some remain admin-published while users create tenant resources such as networks and security groups?

#### Answer

The user asked for a recommendation informed by other cloud MCP servers; no prerequisite-ownership boundary was selected yet.

#### Impact

The PRD needs a role-by-resource boundary. Current OSAC documentation identifies tenant networking as user-creatable; VM catalog offerings, instance types, and storage tiers as provider-administered; and disk images as potentially tenant-scoped. The recommendation is to allow users to create prerequisites they are already authorized to own, while keeping provider-published offerings under their existing admin roles. The assistant should discover and report a missing admin-published prerequisite rather than invent or bypass it. Whether admin-facing MCP management of provider offerings belongs in this Feature remains to be confirmed.

#### Research note — not a decision

Google Cloud requires both permission to call the MCP tool and permission for the underlying resource ([Google Cloud IAM guidance](https://docs.cloud.google.com/mcp/control-mcp-use-iam)). Azure's VM tool may create networking when none is specified ([Azure Compute MCP tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/azure-compute)). AWS states that MCP does not confer additional service permissions ([AWS MCP and IAM](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/security_iam_service-with-iam.html)). These are comparisons, not OSAC requirements.

Later source verification refined the role examples: the current public Fulfillment API exposes catalog-item writes to tenant admins, and platform admins have broader access. The boundary is the current OSAC authorization policy and resource tenancy, not a blanket rule that all catalog items are provider-only.

---

### R2.Q4: Permission-denied prerequisite

When permissions prevent a required prerequisite from being created, should the assistant explain the block and stop, or support a request or approval handoff?

#### Answer

Explain the block and stop.

#### Impact

The PRD should require a clear, actionable explanation of what prerequisite is missing and why the caller cannot create it. It should not imply that an approval workflow exists or silently switch to a more privileged identity.

#### Decision (D7)

If the caller lacks permission to create a required prerequisite, the assistant explains the block and stops; an approval or request handoff is not required.

---

## Round 3 — Roles, adjacent resources, and host variants

### R3.Q1: Tenant versus provider-owned prerequisites

Should tenant users be able to create only prerequisites OSAC already authorizes for their role, while provider-owned offerings remain with an authorized admin?

#### Answer

Yes. The user agrees that MCP should preserve the existing role and ownership boundary.

#### Impact

The PRD must describe access in terms of the caller's existing OSAC permissions, including tenant-admin capabilities where present. It must not assume every catalog write is provider-admin-only, nor grant a regular tenant user an admin shortcut.

#### Decision (D8)

MCP exposes prerequisite operations only when the caller's existing OSAC role and resource tenancy allow them. Provider-owned resources remain under their authorized admin roles; tenant-scoped administrative capabilities remain available to an authorized tenant admin.

---

### R3.Q2: Provider-admin MCP workflows

Should provider admins also be able to use MCP to create and publish provider-managed offerings within this Feature?

#### Answer

Yes.

#### Impact

The PRD needs an admin-facing journey in addition to tenant provisioning. The current public Fulfillment API already defines catalog-item create, update, and delete methods, with writes limited by its authorization policy. The design must still identify the applicable admin role and resource-level restrictions for each type; the MCP must forward the caller's token and cannot elevate it.

#### Decision (D9)

Authorized administrators can manage supported provider-owned offerings through MCP as part of this Feature, using existing OSAC APIs and authorization rather than a privileged MCP identity.

---

### R3.Q3: Volumes and public-address workflows

Should volume and public-IP operations be included among the additional applicable resource journeys?

#### Answer

The user is open to inclusion but asked for a recommendation and rationale; no final scope decision was made.

#### Impact

Current public Fulfillment APIs and method authorization cover Volume lifecycle, ExternalIP allocation, ExternalIPAttachment, and NATGateway operations. ExternalIP and attachment are relevant to VM, cluster, and bare-metal public-address journeys; NATGateway serves network egress. This supports including applicable public-address actions in the networking-first stage. Volumes deserve an explicit storage journey and validation of their relationship to CSI/PVC workflows, rather than treating VM boot-disk selection as proof of general Volume support. The exact first-release acceptance boundary remains open.

#### Research note — not a decision

The current `proto/public` services expose these operations, and `fulfillment-service/internal/auth/policies/authz.rego` permits their public methods for authenticated clients. The `Volume` type comment still describes creation through the private CSI path, while the public service and authorization tests now expose direct Volume operations; the PRD/design should resolve the intended user workflow before promising end-to-end Volume creation.

The later answer in R4.Q1 confirms direct Volume lifecycle as part of a later storage stage. The public-address boundary is still open.

---

### R3.Q4: Model-host setup variants

Is there a meaningful difference between Codex CLI/Desktop or Claude Code/Desktop setup, or can one configuration work in both places?

#### Answer

The user expects the setup to work in both places and asks whether a separate configuration is really necessary. This is not yet a confirmed acceptance boundary for each host surface.

#### Impact

Codex CLI and Desktop share MCP configuration, so one server entry can serve both, although both surfaces should be tested. Claude Code CLI and the Desktop Code tab share configuration, but Claude Desktop Chat uses a separate connector path. In particular, Desktop Chat remote connectors connect from Anthropic's cloud, so a private OSAC endpoint reachable only from the user's machine is insufficient. Cursor requires its own onboarding test. The PRD should distinguish shared configuration from verified connectivity and define whether Claude Desktop Chat is required when OSAC is privately hosted.

#### Research note — not a decision

See [OpenAI's MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp), [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp), [Claude Desktop/Code configuration documentation](https://code.claude.com/docs/en/desktop), and [Claude Desktop custom-connector guidance](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

---

## Round 4 — Storage, local hosts, and write approval

### R4.Q1: Direct Volume lifecycle

Should direct Volume lifecycle be included in this Feature as a later storage stage, subject to validating how it relates to CSI/PVC workflows?

#### Answer

Yes.

#### Impact

The PRD must include a tenant-facing Volume journey in addition to VM boot-disk selection. Its acceptance boundary must account for how direct Volume requests are consumed alongside existing CSI/PVC workflows, without assuming that the current public API alone proves the complete user journey.

#### Decision (D10)

Direct Volume lifecycle is in scope for a later storage stage of this Feature, with the intended user workflow and CSI/PVC interaction to be validated.

---

### R4.Q2: Initial host reachability

Should first delivery require cloud-brokered Claude Desktop Chat to reach a private OSAC endpoint, or start with host surfaces that can connect from the user's local/private-network environment?

#### Answer

Start with whatever can work locally.

#### Impact

The PRD should make locally reachable/private-network connection paths the initial acceptance target for the already selected Cursor, Codex, and Claude host families. Shared configuration does not eliminate per-surface verification. Cloud-brokered Claude Desktop Chat is not an initial acceptance condition for a private endpoint; an approved remote-reachability approach would need separate validation if added later.

#### Decision (D11)

Initial supported host paths are those that can connect to a private OSAC deployment from the user's local environment. Support must be verified on each selected host surface; cloud-brokered Claude Desktop Chat is not required for the initial private-endpoint delivery.

---

### R4.Q3: Confirmation granularity for multi-step writes

For a request that creates several resources, should one approval cover the full proposed plan, or should the user approve each individual write?

#### Answer

The user requested an industry-practice recommendation before choosing a rule. No confirmation policy was locked.

#### Impact

The PRD needs a user-observable approval boundary for each write and clear behavior if a proposed plan changes or partially fails. The recommended baseline is to show the whole proposed sequence, then make each consequential write individually reviewable and deniable before execution. A single approval for multiple writes should count only if the exact approved actions are bound and enforced; conversational assent alone or advisory MCP annotations cannot guarantee that. Avoid redundant prompts when a host already provides sufficient review at execution. The design must determine how this works consistently across supported hosts.

#### Research note — not a decision

The [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) leaves the interaction model to clients but recommends human ability to deny tool invocations and confirmation for sensitive operations. Its annotations are hints, not enforcement; see the [MCP maintainers' explanation](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/). As one product example, [AWS Partner Central's MCP server](https://docs.aws.amazon.com/partner-central/latest/developer-guide/mcp-tools-reference.html) requests approval with proposed action details before a write. This example does not establish a universal per-call rule for all MCP hosts.

---

## Round 5 — Approval and partial execution

### R5.Q1: Individual and plan-wide approval

Should OSAC show the complete plan and require reviewable approval at each write, or also offer a choice to approve all actions in the plan at once?

#### Answer

Yes to the plan preview and per-write approval baseline. The user also suggested offering both “approve each” and “approve all” choices, but phrased the plan-wide option tentatively.

#### Impact

The PRD must let users review the planned actions and deny an individual write. A plan-wide option remains under consideration: it cannot mean an open-ended authorization for the model to add or alter actions. If offered, it must be limited to the exact reviewed actions, and changes must require renewed approval. The design must determine how either approval choice can be enforced across supported model hosts rather than relying on conversational assent or MCP annotations alone.

#### Decision (D12)

The user can review the complete proposed plan, and each individual write must be reviewable and deniable before execution. Whether an additional bounded “approve all actions in this exact plan” choice is required remains open.

The later answer in R7.Q1 resolves the plan-wide option: it is not required.

---

### R5.Q2: Partial failure

If a later step in a multi-resource plan fails after earlier steps succeeded, should the assistant stop and report the created resources, without automatically deleting them?

#### Answer

Yes.

#### Impact

The user must see which steps succeeded, which failed, and which resources remain. The assistant must not silently continue, retry, or roll back earlier changes. Any corrective or cleanup actions need a new user request and the applicable approvals.

#### Decision (D13)

On partial failure, stop and report the outcome and resources already created. Do not automatically roll back or perform further mutations.

---

### R5.Q3: Higher-impact actions

Should deletion, public exposure, and publishing a provider offering each require their own explicit confirmation even if they appear in a larger approved plan?

#### Answer

Yes.

#### Impact

The PRD should distinguish higher-impact actions from ordinary creation. A plan-wide approval option, if added, cannot silently cover these actions; the user must separately confirm the specific target and effect before each is executed.

#### Decision (D14)

Deletion, public exposure, and provider-offering publication require separate explicit confirmation for each action, even when included in an otherwise approved plan.

---

## Round 6 — Approval scope and uncertain outcomes

### R6.Q1: Requiring plan-wide approval

Should “approve this exact plan” be a required choice alongside per-action approval, even though some model hosts may still present their own prompts?

#### Answer

The user is hesitant: “maybe not.” They did not make a definitive decision to include or exclude plan-wide approval.

#### Impact

Per-action approval remains the confirmed baseline. The PRD should not silently require a second, cross-host plan-wide approval mechanism based on a tentative suggestion. The user can decide whether to include it as a required outcome after weighing usability against cross-host enforcement and duplicate prompts.

The later answer in R7.Q1 resolves this question: plan-wide approval is not required.

---

### R6.Q2: Changed approved plan

If an approved plan's actions, targets, or settings change, should execution pause and require new approval before any further write?

#### Answer

Yes.

#### Impact

The user must be shown the changed action and asked to approve it. Earlier approval cannot be treated as permission for a different resource, configuration, or sequence.

#### Decision (D15)

When a proposed or approved plan changes, pause before further mutation and obtain approval for the changed actions.

---

### R6.Q3: Ambiguous timeout and retries

If a write times out and OSAC cannot establish whether it succeeded, should the assistant stop and report uncertainty rather than blindly retrying it?

#### Answer

The user asked for the established practice before choosing a rule. No retry policy was locked.

#### Impact

The user-facing outcome should distinguish a confirmed failure from an unknown result. The recommended behavior is to check for a trustworthy result or resource record, then stop and report uncertainty if the outcome remains unknown. Repeating a non-idempotent create can duplicate infrastructure; a safe retry requires an API guarantee that the repeated request is recognized as the same operation. The exact mechanism belongs in design.

The later answer in R7.Q2 accepts the recommended user-facing behavior.

#### Research note — not a decision

[AWS EC2's idempotency guidance](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html) describes requests that time out even though they may have succeeded, and uses a client token to prevent duplicate resource creation on retry. [Stripe's API guidance](https://docs.stripe.com/api/idempotent_requests) follows the same idempotency-key pattern for connection errors. The current OSAC public `ComputeInstancesCreateRequest` has no explicit idempotency token; this does not by itself establish whether another correlation mechanism exists elsewhere in the request path.

---

## Round 7 — Approval, uncertain creates, and dry-run

### R7.Q1: Plan-wide approval option

Should users review the plan and be able to approve or deny each write, without requiring a separate “approve all” option?

#### Answer

Yes.

#### Impact

The PRD should require plan review and individually reviewable writes, but not a second plan-wide approval choice. The supported host may provide the actual per-write prompt; the experience should avoid redundant confirmation while preserving the user's ability to deny each action. Higher-impact actions still require their own explicit confirmation under D14.

#### Decision (D16)

Plan review and per-write approval are required. A separate “approve all actions in this plan” option is not required.

---

### R7.Q2: Unknown outcome after a timed-out create

If a create times out, should the assistant check whether it succeeded and, if the result remains unknown, report uncertainty and stop without automatically retrying?

#### Answer

Yes.

#### Impact

The PRD should distinguish “confirmed failed” from “outcome unknown,” require a status or resource check where available, and prevent an unverified duplicate create. This does not prohibit a separately approved corrective action after the outcome is understood.

#### Decision (D17)

After an uncertain create, check for a trustworthy outcome. If it remains unknown, report that uncertainty and stop; do not automatically retry.

---

### R7.Q3: Separate dry-run for first delivery

Should the first delivery include a separate no-changes validation of a proposed request, or is reviewing the plan, catalog rules, and selected resources sufficient?

#### Answer

The user agreed that reviewing the plan, catalog rules, and selected resources is sufficient for the first delivery.

#### Impact

The PRD should require a clear review of proposed actions and relevant constraints before writes, but should not require a distinct dry-run operation for the first delivery. This does not claim that preflight review can predict every provisioning outcome.

#### Decision (D18)

A separate dry-run capability is not required for the first delivery; plan, catalog-rule, and selected-resource review is sufficient before submission.

---

## Round 8 — Audit, attribution, and status continuity

### R8.Q1: Audit visibility for MCP writes

Should authorized admins be able to see who initiated each MCP write, the tenant, action, resource, and outcome, without seeing another tenant's activity?

#### Answer

Yes.

#### Impact

The PRD should specify an admin-visible record of model-initiated writes that identifies the authenticated caller, affected tenant and resource, requested action, and outcome. Access to those records must follow existing tenant boundaries. The design can determine how these records are stored and correlated with underlying operations.

#### Decision (D19)

Authorized admins can inspect the caller, tenant, action, resource, and outcome of MCP writes within their permitted scope; they must not gain visibility into another tenant's activity.

---

### R8.Q2: Separately verified agent identity

Must OSAC verify the model or agent's identity separately from the signed-in user, or is the user's identity plus “via MCP” sufficient initially?

#### Answer

The user agreed that the signed-in user's identity plus an MCP-origin indication is sufficient initially.

#### Impact

The PRD should not require a separately authenticated or delegated agent identity for the initial delivery. It should not present a client-provided host name as a verified identity. The caller's existing OSAC permissions remain the authorization boundary.

#### Decision (D20)

Initial attribution requires the authenticated user and an MCP-origin indication, not a separately verified agent identity.

---

### R8.Q3: Status after the original chat ends

Should a user be able to return in a later session and check a resource's actual progress or failure, rather than depend on the original chat staying open?

#### Answer

Yes.

#### Impact

The PRD should require authorized users to retrieve current resource status after reconnecting, including relevant progress or failure information. A create response alone must not be presented as readiness, and status visibility must not depend on a continuously connected chat session.

#### Decision (D21)

Users can return in a later session and check the actual progress or failure of a resource they are authorized to view.

---

## Round 9 — Public-address networking, Volumes, and API scope

### R9.Q1: Public-address and NAT networking

Should the networking journey include external IP allocation and attachment, plus NAT egress where OSAC supports them, with separate confirmation before public exposure?

#### Answer

Yes.

#### Impact

The networking stage must cover the available public-address and egress actions, not only virtual networks, subnets, and security groups. Access remains role-bound, and actions that make a resource publicly reachable require the separate confirmation already agreed in D14.

#### Decision (D22)

External IP allocation and attachment, and NAT egress where OSAC supports them, are included in the networking journey. Public exposure requires separate explicit confirmation.

---

### R9.Q2: OSAC Volume versus PVC workflow

Should the storage journey manage OSAC Volumes, while CSI/PVC remains an integration detail unless OSAC exposes a separate user-facing PVC action?

#### Answer

Yes.

#### Impact

The PRD should define a user-facing Volume lifecycle through OSAC and require validation of its interaction with CSI/PVC consumers. It should not promise a separate Kubernetes PVC-management interface through MCP based solely on the existence of CSI integration.

#### Decision (D23)

The MCP storage journey is the OSAC Volume lifecycle. CSI/PVC is an integration dependency, not a separate MCP journey unless OSAC offers a distinct user-facing PVC action.

---

### R9.Q3: Other public Fulfillment resource families

Beyond networking, VMs, clusters, bare metal, and Volumes—and their catalog and prerequisite actions—is another resource family required as a complete journey for this Feature?

#### Answer

The user asked whether the current public Fulfillment API offers additional resource families before deciding. No scope choice was made yet.

#### Impact

The PRD needs an explicit boundary for deployment-adjacent resources, rather than equating every public endpoint with a Deployment MCP tool. The current public API contract includes Projects and ProjectMemberships, Secrets, and FabricDomains in addition to the already named infrastructure families. It also includes Tenants, Users, IdentityProviders, Roles, and RoleBindings for access administration; ConsoleSessions/ConsoleProxy for interactive access; Events for streaming; and read-only support endpoints. Which of these should become supported MCP journeys remains open.

#### Research note — not a decision

The inventory comes from `proto/public/osac/public/v1/*_service.proto` and the current method policy in `fulfillment-service/internal/auth/policies/authz.rego`. `Project` organizes and isolates resources; `Secret` may hold user data, kubeconfigs, pull credentials, or other sensitive values, and its public `Get` response includes raw data. `FabricDomain` represents east-west fabric isolation and its public service defines lifecycle methods; the current policy does not grant those methods to ordinary tenant users. A public proto method alone does not establish that every role can call it or that its end-to-end journey is production-ready.

The user also asked whether updates are planned. D2 already includes updates wherever applicable, and D6 limits this Feature to existing OSAC actions. The current public contract defines `Update` for ComputeInstances, Clusters, BareMetalInstances, and Volumes, as well as many catalog and administrative resources. VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, ExternalIPAttachments, and NATGateways currently define create/delete but not update. The PRD should not imply in-place edits for those networking resources or that every field of an updatable resource is mutable.

The later answers include Projects in the deployment journey (D24), keep Secret values outside model-facing tools (D25), and do not require an unverified FabricDomain journey (D26).

---

## Round 10 — Projects, secret handling, and fabric networking

### R10.Q1: Project creation and updates

Should authorized administrators be able to create and update Projects through MCP when a deployment needs one, rather than only selecting an existing Project?

#### Answer

Yes.

#### Impact

The PRD should include Project discovery, selection, creation, and update in the authorized deployment journey. Existing project tenancy and access rules continue to apply. Other applicable lifecycle actions remain governed by D2 and the available OSAC API.

#### Decision (D24)

Authorized administrators can create and update Projects needed for deployment through MCP, subject to existing OSAC authorization.

---

### R10.Q2: Secret creation and sensitive values

Should MCP create or update Secrets directly, knowing sensitive values could pass through the model host, or only select existing Secret references? How do other MCP servers handle this?

#### Answer

The user accepted the recommendation to keep plaintext Secret values out of model-facing tools. MCP may discover and select permitted Secret references. If an authorized user needs to provide a missing Secret, they should enter its value through a secure OSAC-controlled interaction outside the model host, then resume the deployment using the resulting reference.

#### Impact

The PRD needs a user-facing way to handle a missing deployment Secret without exposing its value to the model or contradicting D3's requirement to create authorized missing prerequisites. The design should evaluate a secure OSAC-owned handoff, including URL-mode elicitation where supported and a secure-link fallback where needed. It must validate host compatibility and ensure that model-facing Secret discovery and retrieval do not disclose values.

#### Decision (D25)

Model-facing MCP tools may discover and select authorized Secret references, but must not accept or reveal plaintext Secret values. When a required Secret is missing, an authorized user can provide its value through a secure OSAC-controlled interaction outside the model host, then resume the deployment with the resulting reference.

#### Research note — not a decision

[Azure MCP Key Vault tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/azure-key-vault) expose Secret create and retrieval with user consent, while [Azure's tool guidance](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/) labels sensitive tools and calls out sanitization. [AWS's EKS MCP server](https://github.com/awslabs/mcp/blob/main/src/eks-mcp-server/README.md) restricts sensitive-data access by default and advises against creating Kubernetes Secrets through model prompts; [AWS's agent secret-safety guidance](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets-ai-agents.html) favors runtime references that keep plaintext out of model context. A [Google Cloud MCP tool](https://docs.cloud.google.com/bigquery/docs/reference/datatransfer/mcp/tools_list/create_transfer_config) requires Secret Manager for permitted sensitive parameters rather than plaintext. There is no single provider-wide rule to copy. The [MCP elicitation specification](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation) prohibits collecting credentials with in-band forms and supports URL-mode collection outside the MCP client; this is a possible design mechanism, not yet an OSAC requirement. OSAC's public `Secret` type returns raw data on Get, so a generic Secret Get tool would need a deliberate safety boundary.

---

### R10.Q3: FabricDomain relevance

Should authorized platform admins manage FabricDomains through the networking journey? What are they, and does this make sense for the Feature?

#### Answer

The user accepted the recommendation not to require a complete FabricDomain MCP journey in this Feature until OSAC's underlying end-to-end provisioning has been verified.

#### Impact

The PRD should not treat a public API method as proof of a complete networking journey. FabricDomain is specialized platform networking rather than a routine tenant VM-network prerequisite. It can be considered for a later platform-admin journey only after its underlying provisioning, status, and role boundary are verified.

#### Decision (D26)

A complete FabricDomain MCP journey is not required by this Feature unless OSAC's underlying end-to-end provisioning is verified. Its public CRUD contract alone is insufficient to make it a networking-stage acceptance criterion.

#### Research note — not a decision

The public `FabricDomain` contract represents an east-west isolation domain over servers and a VirtualNetwork, with Ethernet, InfiniBand, and NVLink types (`proto/public/osac/public/v1/fabric_domain_type.proto`). Current server validation supports only Ethernet, requires at least one server, exactly one VirtualNetwork, and a capable NetworkClass with a template (`fulfillment-service/internal/servers/private_fabric_domains_server.go`). Its public service has create/update/delete methods, but the current method policy in `fulfillment-service/internal/auth/policies/authz.rego` does not grant them to ordinary tenant users; platform admins have the broad allow rule. This checkout contains API registration, persistence, and validation but no identified operator/provider reconciliation for FabricDomain, so end-to-end provisioning is not established by this review.

---

## Round 11 — Adjacent workflows and stage completion

### R11.Q1: Identity and access administration

Should management of users, identity providers, roles, role bindings, and project memberships remain outside this deployment Feature, while existing permissions still govern MCP actions and authorized admins can manage Projects and catalog offerings?

#### Answer

Yes.

#### Impact

The PRD should treat identity and access administration as an adjacent OSAC capability, not as an additional deployment journey. It must still describe the dependency on existing permissions and the experience when a caller cannot perform an action. Project and catalog-offering management by authorized admins remain included under D24 and D9.

#### Decision (D27)

Dedicated identity and access administration is outside this Deployment MCP Feature. Existing OSAC identity and access rules govern MCP actions; authorized Project and catalog-offering management remain in scope.

---

### R11.Q2: Console sessions, event streaming, and remote SSH

Should console sessions and event streaming remain outside this deployment Feature, while resource status and conditions remain available through MCP?

#### Answer

The user asked whether console sessions mean SSH access and suggested that remote SSH calls might be useful for application deployments as a long-term stretch. They then asked whether a model could use OSAC's actual serial or VNC console and, if so, preferred to leave console and event streaming out of this Feature while treating model-assisted console access as a potential long-term direction. R12.Q1 records the resulting boundary.

#### Impact

The current OSAC console-session API issues tickets for ComputeInstance serial or VNC console access, not SSH command execution (`proto/public/osac/public/v1/console_service.proto`). Application deployment inside the VM is already outside the source Feature's scope. Model-assisted console access would require a separate user experience and safety review; the current console API alone does not make it part of the Deployment MCP journey.

---

### R11.Q3: Meaning of a complete staged journey

Should a resource-family stage count as complete only when an authorized user can discover eligible choices, handle supported prerequisites, perform applicable existing lifecycle actions, and check the actual outcome in a later session, rather than merely having MCP endpoints available?

#### Answer

Yes.

#### Impact

The PRD should define each staged journey through user-observable outcomes across discovery, permitted prerequisite handling, applicable lifecycle actions, and asynchronous follow-up. Acceptance cannot be satisfied by tool exposure alone. The exact resource-by-action inventory is still needed, and the journey remains bounded by actions OSAC already supports (D6).

#### Decision (D28)

Each staged resource journey must work end to end for an authorized user: discover eligible choices, handle supported prerequisites, perform applicable existing lifecycle actions, and retrieve the actual outcome in a later session. Exposing tool endpoints alone is insufficient.

---

## Round 12 — Console-access boundary

### R12.Q1: Model use of the VM console

Given that OSAC's console session provides serial or VNC access rather than SSH, could a model use it? If it could, should console access be a possible long-term direction while both console access and event streaming remain outside this Feature?

#### Answer

Yes to the conditional boundary: the user wants both console access and event streaming out of the current Feature if model use of the console is feasible, with model-assisted console access noted as a potential longer-term direction. A model could use a serial console if a future interface exposed bounded text reads and writes. A vision-capable host could potentially use VNC if a future interface converted frames to images and mediated input. Neither is available through the current Deployment MCP tools.

#### Impact

The PRD should keep current resource status and conditions available, but should not require an interactive guest console or event stream. A future console-access journey could be evaluated separately for usefulness, host support, authorization, approval, audit, and protection of console output and access tickets. This is not a commitment to add SSH or application deployment to the current Feature.

#### Decision (D29)

Interactive serial/VNC console access and event streaming are outside this Deployment MCP Feature. Model-assisted use of OSAC's existing VM console is a potential later capability, not a current acceptance criterion. Resource status and conditions remain in scope.

#### Research note — not a decision

OSAC's public console API exposes serial and VNC session types and a single-use access ticket (`proto/public/osac/public/v1/console_service.proto`); its proxy is a bidirectional byte stream (`proto/public/osac/public/v1/console_proxy_service.proto`). MCP tools can return text or image content ([MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)), but that does not by itself turn OSAC's interactive console stream into a safe model-facing tool.

---

## Round 13 — Host onboarding and first use

### R13.Q1: Initial supported host surfaces

Should initial verification cover the locally running editor or desktop and CLI surfaces of Cursor, Codex, and Claude Code, while cloud-run agents and Claude Desktop's separate Chat connector remain outside the private-endpoint target?

#### Answer

Yes.

#### Impact

The PRD should name the locally connecting host surfaces and require a working connection and deployment journey on each. Shared configuration is helpful but does not replace verification. Cloud-run agents and the separate Claude Desktop Chat connector are not initial private-endpoint acceptance targets under D11.

#### Decision (D30)

Initial supported surfaces include Cursor's local editor and CLI, Codex's local CLI and app/IDE, and Claude Code's local CLI and Desktop Code experience. Each must be verified; cloud-run agents and Claude Desktop Chat are not initial private-endpoint acceptance targets.

---

### R13.Q2: OSAC UI setup experience

Is a discoverable OSAC UI page with copyable host-specific setup steps for the endpoint, certificate trust, sign-in, and verification sufficient initially, without a required one-click installer?

#### Answer

Yes.

#### Impact

The PRD should require a self-service onboarding path that a user can complete from the UI and first-party instructions. It need not require OSAC to edit local model-host configuration automatically. Host-specific instructions need to remain accurate as those products change.

#### Decision (D31)

The initial onboarding experience provides a discoverable OSAC UI entry point and copyable host-specific endpoint, trust, sign-in, and verification guidance. A one-click installer is not required.

---

### R13.Q3: Read-only connection check and failures

Should users be able to verify the connection with a read-only action before a write and receive actionable distinctions among connectivity or trust, login, permission, and server failures?

#### Answer

Yes. For model-host-specific troubleshooting, the user prefers deferring to the host's official documentation where warranted rather than duplicating it in OSAC guidance.

#### Impact

The PRD should require a non-mutating first-use check and actionable explanations for identifiable OSAC-side failure categories. OSAC guidance should link to current official host documentation for host-specific behavior instead of trying to maintain exhaustive instructions for every host error.

#### Decision (D32)

Users can verify MCP access without creating a resource and receive actionable connection, trust, authentication, authorization, and service-failure guidance. Host-specific troubleshooting may defer to official model-host documentation where appropriate.

---

### R13.Q4: Existing OSAC CLI relationship

Should the existing OSAC CLI remain a separate human and script interface, without requiring this Feature to duplicate every MCP action in the CLI or configure model hosts through it?

#### Answer

Yes.

#### Impact

The PRD should distinguish MCP host onboarding and deployment journeys from the existing CLI. The Feature does not need a new CLI setup command or action-for-action CLI parity; existing CLI behavior and documentation remain relevant reference points.

#### Decision (D33)

The OSAC CLI remains a separate human and script interface. This Feature does not require CLI parity with MCP or CLI-driven model-host configuration.

---

## Round 14 — Lifecycle boundaries and operational outcomes

### R14.Q1: Networking changes without in-place update

When someone asks to change an existing network resource, should MCP explain that in-place editing is unavailable and propose a separately reviewed replacement path, without silently deleting anything?

#### Answer

Yes.

#### Impact

The PRD should distinguish an unsupported in-place edit from the available create/delete actions. A user can review a proposed replacement sequence and its dependencies, but no replacement or deletion should be performed implicitly. The sequence must remain limited to actions OSAC actually supports and subject to existing approval rules.

#### Decision (D34)

For network resources without an in-place update operation, explain the limitation and, where OSAC supports the necessary steps, propose a separately reviewed replacement path. Never silently delete or replace the existing resource.

---

### R14.Q2: VM restart as an explicit action

Should VM restart be an explicit action alongside start and stop, once its end-to-end behavior is verified?

#### Answer

Yes.

#### Impact

The VM lifecycle journey should let an authorized user request start, stop, and restart by intent, with outcome checks and applicable write approval. The design must verify that the existing OSAC update behavior fulfills each action; the PRD should not require a new underlying VM-management capability.

#### Decision (D35)

The supported VM lifecycle includes explicit start, stop, and restart actions, conditional on validating their existing OSAC behavior end to end.

---

### R14.Q3: Useful asynchronous failure report

For a provisioning failure, should the response show the resource ID, actual state, available condition reason/message and timing, and clearly distinguish what OSAC knows from what still needs operator investigation?

#### Answer

Yes.

#### Impact

The PRD should require a truthful, useful failure report rather than a generic error or a claim of readiness based on request acceptance. When available to the caller, status details should identify the resource, state, reason, message, and timing. If OSAC lacks enough information to identify the cause, the response must say what is unknown and give an appropriate next investigative step without exposing another tenant's data or secret values.

#### Decision (D36)

Asynchronous outcome reports show the actual resource ID, state, available condition details and timing, and clearly separate established facts from unknowns and next operator investigation.

---

### R14.Q4: Operator traceability across provisioning

Should authorized operators be able to trace an MCP write to its Fulfillment resource and provisioning work through audit records or existing diagnostics, without making this an Observability MCP?

#### Answer

Yes.

#### Impact

This extends D19's admin-visible write attribution into operational support: an authorized operator should be able to follow the request to the resulting resource and provisioning work within their permitted scope. The PRD can require that observable outcome without prescribing a particular identifier or telemetry implementation, and without adding a general-purpose observability interface.

#### Decision (D37)

Authorized operators can correlate an MCP write with its Fulfillment resource and provisioning work through audit records or existing diagnostics, within their permitted scope. This does not turn the Feature into an Observability MCP.

---

## Subsequent override — 2026-09-29

During PR review, the user approved keeping the target release and delivery order out of the PRD. D5 and D10 still include networking, VMs, clusters, bare metal, and Volumes in this Feature. The PRD no longer states which journey comes first or names a release. Jira tracks that planning.

## Subsequent override — 2026-09-30

During design, the user approved restating FR-13 to sequential host confirmation. Each write is deniable in the host before that mutation runs; changed arguments require a new confirmation; conversational agreement is not approval. D12's complete plan-preview MUST and the in-scope "multi-step plan" language are superseded. D16's per-write approval remains. A durable plan object and a plan-wide "approve all" choice are still not required.

## Remaining Gaps

None blocking PRD drafting. The design and implementation must verify the end-to-end behavior and permissions of each selected resource journey; public API methods alone are not evidence of a working journey.

## Research Notes

### Public API inventory — research, not a scope decision

The current `proto/public/osac/public/v1/*_service.proto` contracts define List/Get/Create/Update/Delete for ComputeInstances, Clusters, BareMetalInstances, Volumes, and Projects. VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, ExternalIPAttachments, and NATGateways define List/Get/Create/Delete, but no Update. ComputeInstance catalog items and templates, Cluster catalog items/templates/versions, BareMetalInstance catalog items/templates, HostTypes, InstanceTypes, and DiskImages define List/Get/Create/Update/Delete. StorageTiers, ExternalIPPools, and BareMetalInstanceTypes define List/Get only. This inventory describes public API methods, not verified end-to-end provisioning or permission for every role.

`ComputeInstanceSpec.run_strategy` supports `ALWAYS` and `HALTED` through the public Update method; `restart_requested_at` is a separate declarative restart signal. The API's status provides state, conditions with reasons/messages and transition times, and the VM state-transition time. These contracts can support clear start/stop/restart and progress reporting, subject to end-to-end validation and the caller's existing authorization. No separate Start/Stop RPC is required by the contract.

## Design and Decomposition Handoff — not a product requirement

The user raised the expectation that implementation begin by improving the existing ComputeInstance MCP PoC to a mergeable baseline. That is a sensible first enabling task to evaluate during design/decomposition. Delivery order is tracked in Jira rather than restated in the PRD, and the exact PR/task boundary remains subject to code review and design planning.
