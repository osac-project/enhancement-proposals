# Testplan — OSAC-5734

## Overview

- **Feature:** OSAC-5731 — OSAC MCP Server for infrastructure provisioning
- **Total test cases:** 58
- **Requirements covered:** 25 of 25
- **Interface changes covered:** 14 of 14

Host confirmation is the per-write gate. Write tools are split so each tool
has one MCP annotation tuple. There is no durable MCP plan,
`execute_plan_step`, execution grant, or Secret-handoff API. Missing Secret
values use existing `/secrets/create`.

## Test Infrastructure

Kind MCP integration tests rebuild and extend
`fulfillment-service/it/it_mcp_server_test.go` on `main`. New `it_mcp_*.go`
files copy that file's pattern:

- Kind suite connections: `tool.InternalView().AdminConn()`,
  `tool.ExternalView().UserConn()`, `tool.UserTokenSource()`, `tool.CaPool()`
- Streamable HTTP client: `mcp.StreamableClientTransport` and `mcp.NewClient`
- Bearer forwarding of `tool.UserTokenSource()` on each MCP HTTP request
- Shared helper `callMCPTool` for typed tool invocation

Proposed `tests/e2e/mcp/` files use the same tool names and envelopes. Catalog
CIDRs, offering IDs, and other fixture values come from objects the Kind suite
creates at runtime, not from this testplan.

Tool errors use the JSON envelope in design.md §4.3. Assert both `category`
and `grpc_code` from that table (`authorization`/`PermissionDenied`,
`invalid_request`/`InvalidArgument`, `authentication`/`Unauthenticated`,
`conflict`/`Aborted`, `rate_limited`/`ResourceExhausted`, and the rest).
Successful writes and later outcomes match the mutation-acceptance and
normalized-outcome JSON examples in the same section.

## Test Cases

### FR-1: Complete resource journeys

#### TC-FR1-01: Complete deployed networking, ComputeInstance, Cluster, and BareMetalInstance journeys

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** No runnable command; proposed path: `tests/e2e/mcp/test_complete_journeys.py`. Working directory: `$REPO_ROOT`.
- **Boundary:** Deployed MCP, Keycloak, Fulfillment, PostgreSQL, operators, and configured providers run for real.

##### Steps

1. For each named family, sign in, discover eligible offerings and prerequisites, and create any supported missing prerequisite through a typed write tool.
2. Invoke each subsequent typed write tool in dependency order after host confirmation.
3. End the session, start a new authenticated session, and call `get_resource_outcome` for every created resource.

##### Expected Results

- Each write tool payload names the exact action, target, and settings before the matching public RPC runs.
- Each successful write returns one resource type, UUID, and version; the provider contains exactly one corresponding resource.
- The later session returns current public state without transport-session state.

#### TC-FR1-02: Retrieve created resources after MCP transport and pod replacement

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; proposed `fulfillment-service/it/it_mcp_restart_test.go`.
- **Boundary:** Deployed Fulfillment and PostgreSQL are real. MCP pod restart is real. Providers may be omitted.

##### Steps

1. Create a resource through a typed write tool.
2. Terminate the MCP connection and serving pod and reconnect through the replacement pod.
3. Call `get_resource` and `get_resource_outcome`.

##### Expected Results

- The replacement pod returns the same Fulfillment resource UUID and public state from PostgreSQL.
- No second create RPC runs.
- Outcome mapping does not depend on the previous MCP process.

### FR-2: Networking lifecycle

#### TC-FR2-01: Provision and remove the full supported networking resource set

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_networking_journey.py`.
- **Boundary:** MCP, OAuth, Fulfillment, networking controllers, and the configured network manager run for real.

##### Steps

1. Discover eligible network choices. Create VirtualNetwork, Subnet, and
   SecurityGroup through `create_network_resource`. Create ExternalIP,
   ExternalIPAttachment, and NATGateway through `expose_network_resource`.
2. Poll each public resource through `get_resource_outcome`.
3. Delete in dependency-safe order using `delete_network_resource`.

##### Expected Results

- Only typed networking actions appear; no arbitrary service or method.
- Each created resource reaches the public state exposed by its Fulfillment API.
- Deletes remove only the named targets.

#### TC-FR2-02: Reject an unsupported in-place network edit

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | medium | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** existing Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_networking_test.go`.
- **Boundary:** Real Fulfillment networking records; external provider omitted.

##### Steps

1. Create a VirtualNetwork with a dependent Subnet through `create_network_resource`. Request an in-place CIDR edit.
2. Inspect the error details.
3. Retrieve the original VirtualNetwork and Subnet.

##### Expected Results

- The edit returns `invalid_request` / `InvalidArgument` with reason
  `unsupported_in_place`; no update RPC is dispatched.
- Error details may name create/delete replacements; no resource is silently replaced.
- Original IDs, versions, and the dependent relationship are unchanged.

### FR-3: ComputeInstance lifecycle

#### TC-FR3-01: Create, update, and retrieve a ComputeInstance outcome

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_compute_instance_journey.py`.
- **Boundary:** Deployed VMaaS path is real.

##### Steps

1. Discover eligible offering, image, instance type, storage, Project, Subnet, SecurityGroup, and Secret reference.
2. Create, then update with returned `metadata.version` and `lock=true`.
3. Start a new session and retrieve `get_resource_outcome`.

##### Expected Results

- Discovery never returns Secret bytes.
- Create and update envelopes match design.md §4.3 mutation acceptance JSON:
  `resource.type` is `ComputeInstance`, plus `resource.id`, `resource.version`,
  and `next_action`.
- The update increments `resource.version`.
- Later `get_resource_outcome` matches the §4.3 normalized-outcome JSON:
  UUID, `lifecycle_state`, public `conditions`, address `facts`, `unknowns`,
  and `next_actions`.

#### TC-FR3-02: Start, stop, restart, and delete a ComputeInstance through explicit actions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_compute_instance_journey.py`.
- **Boundary:** Real run-strategy and restart-trigger behavior.

##### Steps

1. For a running ComputeInstance, invoke `set_compute_instance_power` stop then start, then `restart_compute_instance`.
2. Invoke `delete_compute_instance` for the current version.
3. Retrieve public Get after deletion.

##### Expected Results

- Stop/start update `run_strategy`; restart updates the restart trigger; no new Start/Stop/Restart RPC exists.
- Each action produces one public transition for the same UUID.
- After delete, public Get returns `NotFound`.

### FR-4: CaaS lifecycle

#### TC-FR4-01: Create, update, delete, and later inspect a Cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_cluster_journey.py`.
- **Boundary:** Deployed CaaS provider is real.

##### Steps

1. Discover offering, version, networking, Project, and pull-Secret reference.
2. Create, update, reconnect, and poll `get_resource_outcome`.
3. Delete through `delete_cluster`.

##### Expected Results

- Inputs include no Secret value.
- Later outcome returns UUID, public state, endpoints, node-set summaries, Secret references, unknowns, and next actions.
- Delete uses `destructiveHint` and does not run until the host confirms the tool.

### FR-5: BMaaS lifecycle

#### TC-FR5-01: Create, update, and later inspect a BareMetalInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_bare_metal_journey.py`.
- **Boundary:** Real hardware path; [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) where applicable.

##### Steps

1. Discover offerings, hardware, Project, networking, and Secret references.
2. Create and update through `create_bare_metal_instance` and `update_bare_metal_instance`.
3. Reconnect and retrieve the outcome.

##### Expected Results

- The instance matches the selected offering and prerequisites with one provider allocation.
- The update uses optimistic locking.
- Later outcome reports public state, addresses, and non-sensitive hardware facts.

#### TC-FR5-02: Start, stop, restart, and delete a BareMetalInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_bare_metal_journey.py`.
- **Boundary:** Real BMC/provider path.

##### Steps

1. Invoke `set_bare_metal_instance_power` stop then start, then `restart_bare_metal_instance`.
2. Delete through `delete_bare_metal_instance`.

##### Expected Results

- Power actions update existing `run_strategy` or restart trigger.
- Delete removes the named target after host confirmation.

### FR-6: Volume lifecycle

#### TC-FR6-01: Exercise the public Volume API boundary without claiming a storage backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_volume_test.go`.
- **Boundary:** Public Volume API is real; CSI/vendor I/O omitted.

##### Steps

1. Create a Volume through `create_volume`.
2. Apply a metadata-only update and attempt a spec-field update.
3. Delete the Volume through `delete_volume`.

##### Expected Results

- Create returns one Volume UUID.
- Metadata update uses `lock=true`; spec-field update returns `invalid_request`.
- Delete removes only that Volume. This does not prove vendor attach/mount/I/O.

#### TC-FR6-02: Prove a real-backend Volume create, consume, I/O, and cleanup journey

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_volume_journey.py`.
- **Boundary:** Real backend, CSI, mount, I/O. Blocked by [OSAC-4845](https://redhat.atlassian.net/browse/OSAC-4845) and design Open Question 9.2.

##### Steps

1. Create a Volume through MCP.
2. Attach/consume, mount, and perform I/O through the accepted OSAC workflow.
3. Delete and confirm cleanup.

##### Expected Results

- Exactly one backend volume matches the Fulfillment UUID, size, and tier.
- Mount and I/O succeed on the real path.
- Cleanup removes the Volume. Do not report pass while 9.2/OSAC-4845 is unresolved.

### FR-7: Prerequisite handling

#### TC-FR7-01: Discover only authorized Projects, offerings, Secret references, and prerequisites

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_discovery_test.go`.
- **Boundary:** Real auth and public list APIs.

##### Steps

1. Sign in as a tenant caller and invoke `list_resources` for Projects, offerings, networking, and Secrets.
2. Repeat as a second tenant.
3. Inspect Secret list items.

##### Expected Results

- Each caller sees only authorized items.
- Secret items contain metadata and references, never bytes.

#### TC-FR7-02: Create a supported missing prerequisite within the caller's existing role

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_prerequisite_test.go`.

##### Steps

1. As an authorized caller, create a missing Project or networking prerequisite, then create the dependent resource using the returned UUID.
2. Repeat as a caller who cannot create the prerequisite.

##### Expected Results

- The authorized path creates both resources through existing public APIs.
- The unauthorized attempt returns `authorization` and creates neither resource.

### FR-8: Project and catalog administration

#### TC-FR8-01: Create and update a Project with optimistic locking

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_project_test.go`.
- **Boundary:** Project Update remains unregistered until `lock=true` is proven.

##### Steps

1. As a tenant administrator, create a Project through `create_project`.
2. Assert the public Project Update wrapper passes `lock=true`. Register
   `update_project` only if that assertion holds.
3. Update against the current version.
4. Retry with a stale version and as an ordinary member.

##### Expected Results

- Create succeeds.
- Update remains unregistered if `lock=true` is not proven.
- When registered, current-version update succeeds.
- Stale version fails with `conflict` / `Aborted`; unauthorized caller gets
  `authorization` / `PermissionDenied`.

#### TC-FR8-02: Manage supported catalog offerings and confirm publication in the host

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_catalog_test.go`.

##### Steps

1. Create and update through `create_catalog_offering` and `update_catalog_offering`.
2. Invoke `publish_catalog_offering` and assert `destructiveHint` is set.
3. Repeat an administration action as an unauthorized caller.

##### Expected Results

- Only the three supported offering families appear in the schema.
- Publish is a distinct `publish_catalog_offering` tool; unauthorized callers get
  `authorization` / `PermissionDenied`.

### FR-9: Secret-value handling

#### TC-FR9-01: Enter a missing Secret value in existing OSAC UI and resume with its reference

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** Manual until a committed browser E2E harness exists. Proposed
  record: `tests/e2e/mcp/host-certification/secret-create-resume.md`.
- **Boundary:** Existing `/secrets/create`, MCP discovery, and Fulfillment Secrets APIs.

##### Steps

1. From MCP, attempt a write that requires a missing Secret and capture the guidance pointing at `/secrets/create`.
2. Create the Secret in the existing UI as the same user.
3. Resume with `list_resources` / `get_resource` and complete the write using the reference.

##### Expected Results

- MCP traffic and tool args contain no Secret bytes.
- The write uses only `SecretLocalReference`.
- No MCP-specific handoff URL is required.

###### Pass/fail checklist

- Pass: missing-Secret guidance names existing `/secrets/create`.
- Pass: after UI create, resume uses a Secret reference, not bytes.
- Fail: any Secret value appears in MCP tool args, results, or logs.
- Fail: an MCP-specific handoff URL is required.

#### TC-FR9-02: MCP never accepts or returns Secret bytes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`; MCP package schema and redaction tests.

##### Steps

1. Enumerate write-tool schemas and attempt payloads that include Secret-like fields.
2. Invoke `list_resources` / `get_resource` for Secrets.
3. Inspect captured tool content.

##### Expected Results

- Secret-value fields are rejected with `invalid_request` / `InvalidArgument`.
- List/get return metadata and references only.
- `Secrets/Get` is not registered.

### FR-10: Supported host surfaces

Host certification is blocked by Open Question 9.3. Each case is E2E / [QE],
manual, and uses a released host against a deployed private endpoint. Generic
clients cannot substitute. Secret gaps use existing `/secrets/create`.

Shared pass/fail checklist for TC-FR10-01–06 (and TC-NFR3-01 per surface):

- Pass: sign-in uses that surface's registered public PKCE client and exact
  callback; token audience is `osac-api`.
- Pass: `check_connection` succeeds and creates no resource.
- Pass: the host prompt is the write gate; rejecting the tool performs no
  mutation.
- Pass: one confirmed typed write creates exactly one Fulfillment resource.
- Pass: a later session `get_resource_outcome` returns that UUID and public
  state.
- Pass: the tool list is the allowlisted registry.
- Fail: an OSAC plan-approval or Secret-handoff URL is required.
- Fail: Claude Desktop Chat or a cloud-brokered agent is required.

#### TC-FR10-01: Certify a deployment journey from Cursor editor

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-13 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/cursor-editor.md`.

##### Steps

1. Copy OSAC URL, client, and trust values from `/connect/mcp`.
2. Add the server using Cursor's current remote MCP documentation and complete PKCE.
3. Run `check_connection` and one host-confirmed typed write.
4. Reopen the editor and call `get_resource_outcome`.

##### Expected Results

- Cursor editor uses its registered public client and exact callback.
- Rejecting the write tool performs no mutation.
- Later session returns the Fulfillment resource outcome.
- Shared host-certification checklist passes for Cursor editor.

#### TC-FR10-02: Certify a deployment journey from Cursor CLI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/cursor-cli.md`.

##### Steps

1. Copy OSAC values from `/connect/mcp`.
2. Add the server using Cursor CLI's current MCP documentation and sign in.
3. Run `check_connection` and one host-confirmed typed write.
4. Start a fresh CLI process and retrieve the resource outcome.

##### Expected Results

- Token audience is `osac-api`.
- Host prompt, not an OSAC review URL, is the write gate.
- Shared host-certification checklist passes for Cursor CLI.

#### TC-FR10-03: Certify a deployment journey from Codex CLI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-13 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/codex-cli.md`.

##### Steps

1. Copy OSAC values from `/connect/mcp`.
2. Add the server using Codex CLI's current MCP documentation and sign in.
3. Run `check_connection` and one typed write after host confirmation.
4. Restart Codex CLI and retrieve the later outcome.

##### Expected Results

- Tool list is the allowlisted registry.
- Restarted CLI returns the durable resource ID from Fulfillment.
- Shared host-certification checklist passes for Codex CLI.

#### TC-FR10-04: Certify a deployment journey from Codex app or IDE

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-11 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/codex-app-ide.md`.

##### Steps

1. Copy OSAC values from `/connect/mcp`.
2. Add the server using Codex app/IDE current MCP documentation.
3. Complete `check_connection` and one host-confirmed write.
4. Reopen the app/IDE and retrieve the resource.

##### Expected Results

- Callback and client ID match that surface.
- No OSAC plan-approval page is required.
- Shared host-certification checklist passes for Codex app/IDE.

#### TC-FR10-05: Certify a deployment journey from Claude Code CLI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/claude-code-cli.md`.

##### Steps

1. Copy OSAC values from `/connect/mcp`.
2. Add the server using Claude Code CLI's current MCP documentation and sign in.
3. Run `check_connection` and one host-confirmed typed write.
4. Start another CLI session and retrieve the outcome.

##### Expected Results

- Local private-endpoint connection succeeds.
- Rejecting the write tool performs no mutation.
- Shared host-certification checklist passes for Claude Code CLI.

#### TC-FR10-06: Certify a deployment journey from Claude Desktop Code

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/claude-desktop-code.md`.

##### Steps

1. Copy OSAC values from `/connect/mcp`.
2. Add the server using Claude Desktop Code's current MCP documentation and complete local OAuth.
3. Run `check_connection` and one host-confirmed write.
4. Restart Desktop Code and retrieve the outcome.

##### Expected Results

- Exact local callback is used.
- Claude Desktop Chat and cloud brokers are not required.
- Shared host-certification checklist passes for Claude Desktop Code.

### FR-11: UI onboarding

#### TC-FR11-01: Copy OSAC endpoint values and link official host MCP docs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `pnpm test` from `osac-ui`.

##### Steps

1. Render `/connect/mcp` with runtime metadata.
2. Inspect `publicURL`, per-host client and callback, CA fingerprint when
   configured, `check_connection`, and host MCP documentation links.

##### Expected Results

- Copyable OSAC values are present for the six named local surfaces.
- Official Cursor, Codex, and Claude remote MCP documentation is linked.
- The page is not a complete host-product tutorial.
- No write-approval or Secret-handoff MCP page is advertised.

### FR-12: Read-only connection check

#### TC-FR12-01: Verify access without creating a resource

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_connection_test.go`.

##### Steps

1. Record resource counts.
2. Invoke `check_connection`.
3. Re-count resources.

##### Expected Results

- Connection succeeds and names caller, version, and capabilities.
- Resource counts are unchanged.

#### TC-FR12-02: Distinguish trust, authentication, authorization, protocol, and service failures

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_connection_errors_test.go`.

##### Steps

1. Invoke connection with untrusted CA, missing token, unauthorized caller, unsupported revision, and Fulfillment down.

##### Expected Results

- Categories and `grpc_code` values are `tls_trust`/`FailedPrecondition`,
  `authentication`/`Unauthenticated`, `authorization`/`PermissionDenied`,
  `protocol_incompatible`/`FailedPrecondition`, and
  `service_unavailable`/`Unavailable` respectively.
- No resource is created.

### FR-13: Sequential write review and per-write confirmation

#### TC-FR13-01: Show each write's arguments and confirm writes separately in the host

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_sequential_writes_test.go`.
- **Boundary:** Each write-tool invocation stands in for a host confirmation.

##### Steps

1. Invoke three dependent typed writes, calling `get_resource` between them.
2. Skip the second write and attempt the third.
3. Complete the second then the third.

##### Expected Results

- Each mutating tool is a separate call with visible typed arguments; no plan-wide execute API exists.
- The third write fails or is not valid until its prerequisite exists.
- Skipping a tool leaves no corresponding resource.
- The server does not persist or return a complete uncalled sequence before the first write.

#### TC-FR13-02: Uninvoked or other-subject writes do not mutate

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_authz_write_test.go`.

##### Steps

1. Do not invoke the write tool after discovery.
2. Invoke the write as a different subject.
3. Invoke the write as the authorized creator.

##### Expected Results

- No invocation means zero mutations.
- Other-subject call returns `authorization` / `PermissionDenied`.
- Authorized call creates exactly one resource.

#### TC-FR13-03: Changed settings require a new confirmed tool call

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; proposed `fulfillment-service/it/it_mcp_changed_args_test.go`.

##### Steps

1. Create a resource with payload A.
2. Send an update with different settings and current `metadata.version`.

##### Expected Results

- The second call is a distinct RPC with the new payload.
- The first call cannot apply the new settings.
- Host confirmation applies per call.

### FR-14: Higher-impact confirmation

#### TC-FR14-01: Deletion tools advertise `destructiveHint`

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`.

##### Steps

1. Inspect `delete_compute_instance`, `delete_cluster`,
   `delete_bare_metal_instance`, `delete_volume`, `delete_network_resource`,
   and `delete_catalog_offering`.
2. Invoke delete in integration after host-confirm stand-in.

##### Expected Results

- Those tools set `destructiveHint` true, `idempotentHint` false, and are not
  `readOnlyHint`.
- Delete RPCs run only when the tool is invoked.

#### TC-FR14-02: Public-exposure actions advertise `destructiveHint`

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV] plus component integration for the RPC.
- **Execution:** MCP package tests and Kind fulfillment suite.

##### Steps

1. Inspect `expose_network_resource`.
2. Invoke the action as the caller.

##### Expected Results

- `destructiveHint` is set.
- One attachment mutation occurs only when the tool is invoked.

#### TC-FR14-03: Offering publication advertises `destructiveHint`

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV] plus catalog integration.

##### Steps

1. Inspect `publish_catalog_offering`.
2. Invoke publish as a provider administrator and as an unauthorized caller.

##### Expected Results

- Publish is destructive-hinted.
- Unauthorized publish returns `authorization`.

#### TC-FR14-04: Each write tool has one honest annotation tuple

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`.

##### Steps

1. List all registered tools and their `readOnlyHint`, `destructiveHint`,
   `idempotentHint`, and `openWorldHint` values.
2. Confirm no tool schema combines create with delete, publish, public
   exposure, or restart.

##### Expected Results

- Annotation tuples match design.md §4.1.
- Create tools set `destructiveHint` false and `idempotentHint` false.
- `set_*_power` tools set `idempotentHint` true.
- `openWorldHint` is true on every Fulfillment-backed tool.

### FR-15: Permission-blocked prerequisite

#### TC-FR15-01: Stop when the caller cannot create a required prerequisite

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_permission_block_test.go`.

##### Steps

1. Sign in as a caller allowed to create a ComputeInstance but not its Subnet.
2. Request the missing Subnet through MCP.
3. Inspect identity used and database.

##### Expected Results

- Response is `authorization` naming the Subnet.
- No service identity, Subnet, or ComputeInstance is created.

### FR-16: Partial failure

#### TC-FR16-01: Stop after a definite failure without rollback or retry

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_partial_failure_test.go`.

##### Steps

1. Succeed write one.
2. Inject a definite failure on write two.
3. Do not invoke write three; inspect resources.

##### Expected Results

- Resource one remains; write two failed once; write three mutation count is zero.
- No automatic rollback or retry.

### FR-17: Uncertain create outcome

#### TC-FR17-01: After a lost create response, Get instead of retrying create

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_lost_response_test.go`.

##### Steps

1. Create and drop the RPC response after Fulfillment commits.
2. Call `get_resource` / list for the created identity.
3. Do not send a second create.

##### Expected Results

- At most one resource exists.
- The client is directed to outcome/get, not a blind create retry.

#### TC-FR17-02: Report unknown create outcome and do not retry

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_unknown_outcome_test.go`.

##### Steps

1. Inject an outcome in which commit success cannot be established.
2. Map `unknown_outcome`.
3. Confirm no second create RPC.

##### Expected Results

- Category is `unknown_outcome` with `grpc_code` `Unknown`.
- Create handler is not invoked a second time.

### FR-18: Actual outcome report

#### TC-FR18-01: Map every resource family to a concrete normalized outcome

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`.

##### Steps

1. Supply public Get responses for each family.
2. Supply missing and private-only evidence.
3. Serialize tool results.

##### Expected Results

- Mapping matches the design.md §4.3 family table.
- Serialized outcome matches the §4.3 normalized-outcome JSON shape
  (`resource`, `lifecycle_state`, `conditions`, `timing`, `facts`, `unknowns`,
  `next_actions`).
- Missing or private data is named in `unknowns`.

#### TC-FR18-02: Keep request acceptance distinct from later readiness or failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_later_session_outcomes.py`.

##### Steps

1. Capture the create tool result immediately.
2. Poll `get_resource_outcome` until ready or failed.

##### Expected Results

- Immediate result is not mapped as ready.
- Later outcome shows actual public state.

### FR-19: Write audit and provisioning correlation

#### TC-FR19-01: Inspect tenant-scoped creator and MCP origin on existing resources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_origin_audit_test.go`.

##### Steps

1. Create a resource through MCP as tenant A, then update it as the same
   caller.
2. List as tenant-A admin, as a regular user, and as tenant B.
3. Inspect unrestricted MCP logs for tool name and hashed `sub`.
4. Correlate resource ID and time to the Fulfillment RPC diagnostic for that
   public method.

##### Expected Results

- On create, resource creator and tenant match the caller.
- On update, the actor is the Fulfillment RPC authenticated subject, not a
  change to `metadata.creator`.
- Hashing the caller's JWT `sub` matches the MCP log field.
- Tenant B does not see tenant A's resource.
- Logs include MCP tool origin without Secret bytes or tokens.
- No `MCPWriteRecords` API is required.

#### TC-FR19-02: Correlate a write through Fulfillment to deployed provisioning work

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_write_correlation.py`.

##### Steps

1. Create a resource through MCP.
2. Follow Fulfillment ID to the downstream CR and provider/AAP work.

##### Expected Results

- Correlation uses existing diagnostics.
- No general Observability MCP tool is exposed.

### NFR-1: Authorization and tenant isolation

#### TC-NFR1-01: Execute discovery and mutation as the signed-in caller

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- **Tier / owner:** Contract / [DEV].
- **Execution:** proposed `fulfillment-service/test/contract/mcp_auth/`.

##### Steps

1. Capture the bearer token on public Fulfillment RPCs from MCP.
2. Repeat with a second caller.

##### Expected Results

- Each RPC uses that caller's token, not a service identity.

#### TC-NFR1-02: Prevent cross-tenant access through MCP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_tenant_isolation_test.go`.

##### Steps

1. Create a resource in tenant A.
2. List/get from tenant B.

##### Expected Results

- Tenant B cannot read or mutate tenant A's resource.

#### TC-NFR1-03: MCP has no privileged service identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_no_service_identity_test.go`.

##### Steps

1. Invoke a write without a caller token.
2. Invoke with a token that is not `aud=osac-api`.

##### Expected Results

- Both fail authentication or audience checks.
- No public resource RPC runs as a workload identity.

#### TC-NFR1-04: Reconcile separate least-privilege public OAuth clients

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-13 | high | automated |

##### Preconditions

- **Tier / owner:** Contract / [DEV].
- **Execution:** proposed `osac-installer/tests/contract/mcp_keycloak/`.

##### Steps

1. Reconcile Cursor, Codex, and Claude public PKCE clients.
2. Inspect scopes, callbacks, and absence of client secrets.

##### Expected Results

- Three distinct public clients with exact callbacks and PKCE S256.

### NFR-2: Sensitive-data confidentiality

#### TC-NFR2-01: Redact secrets, credentials, and tokens from observable surfaces

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`.

##### Steps

1. Run writes with canary token/secret values in disallowed fields and logs.

##### Expected Results

- Canaries do not appear in tool content, traces, or logs.

#### TC-NFR2-02: Omit Secrets/Get and expose Secret metadata only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].

##### Steps

1. Enumerate the tool registry.
2. Call Secret list/get tools.

##### Expected Results

- `Secrets/Get` is absent.
- Results are reference-only.

### NFR-3: Host interoperability

#### TC-NFR3-01: Complete the six-surface OAuth, private-trust, and protocol matrix

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-13 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/host-certification/`.
- **Boundary:** Open Question 9.3 blocks scheduling.

##### Steps

1. For each of the six surfaces, sign in, run `check_connection`, and complete one host-confirmed write.

##### Expected Results

- Same tool names, schemas, host-prompt gate, and outcome shape.
- No OSAC approval URL is required.
- Shared host-certification checklist passes on all six surfaces.

#### TC-NFR3-02: Exclude unsupported cloud and Claude Desktop Chat connection modes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `pnpm test` from `osac-ui`.

##### Steps

1. Render setup metadata.
2. Search for cloud-brokered agent, Claude Desktop Chat, DCR, CIMD, trust bypass.

##### Expected Results

- Only the six named local surfaces are listed.

### NFR-4: Operability

#### TC-NFR4-01: Install the supported MCP endpoint and report truthful health

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-11 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_install_and_health.py`.

##### Steps

1. Install with `global.mcp` enabled.
2. Query `/livez`, `/readyz`, PRM, and the public MCP endpoint.

##### Expected Results

- One public URL, clients, Service, and probes exist only when enabled.
- `/readyz` fails when a required dependency is down.

#### TC-NFR4-02: Serve the same Fulfillment state from two MCP replicas

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/test_replicas_and_drain.py`.

##### Steps

1. Create a resource through replica A.
2. Terminate replica A and read `get_resource_outcome` through replica B.
3. Rolling update with `maxUnavailable: 0`.

##### Expected Results

- Replica B reads the same Fulfillment resource.
- No pod-local MCP workflow state exists.

#### TC-NFR4-03: Enforce request-size, concurrency, and rate limits before mutation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** proposed `fulfillment-service/it/it_mcp_limits_test.go`.

##### Steps

1. Send oversized bodies and over-limit write rates.
2. Send concurrent requests above the configured concurrency bound.
3. Route one subject's over-limit traffic across replicas.
4. From two subjects in the same tenant, send traffic that stays under each
   per-subject limit while the combined rate exceeds the tenant limit, routed
   across replicas.

##### Expected Results

- Size, concurrency, and rate rejection occur before the resource RPC.
- The per-subject quota is the aggregate across replicas.
- The per-tenant quota is enforced even when no single subject exceeds their
  own limit.

#### TC-NFR4-04: Keep supported actions, onboarding, failures, and correlation documentation executable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | medium | automated |

##### Preconditions

- **Tier / owner:** Contract / [DEV].
- **Execution:** proposed `tests/contract/mcp/test_documentation_contract.py`.

##### Steps

1. Compare docs to the runtime registry.
2. Check host setup, Secret create in existing UI, host confirmation, and error categories.

##### Expected Results

- Documented tools exist in the registry and conversely.

### NFR-5: Verification

#### TC-NFR5-01: Gate implementation on authorization, sequential-write, failure, and later-status suites

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite. First PR rebuilds the existing
  `fulfillment-service/it/it_mcp_server_test.go` HTTP-client pattern
  (SDK session, caller token, allowlisted tools) rather than introducing a
  new harness.

##### Steps

1. Run authorization denial, sequential writes, partial failure, lost-response, unknown outcome, and later get.

##### Expected Results

- Named cases exist and pass in the deployed harness.
- New cases follow the existing `it_mcp_server_test.go` client setup.

#### TC-NFR5-02: Gate support on deployed resource-family, host, and later-session evidence

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- **Execution:** proposed `tests/e2e/mcp/`.
- **Boundary:** Volume blocked by Open Question 9.2; hosts by 9.3.

##### Steps

1. Execute deployed family journeys, later-session, and six host records.

##### Expected Results

- Missing evidence is not converted to pass.

#### TC-NFR5-03: Keep write tools unregistered until the development-only flag is set

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- **Execution:** Kind fulfillment suite; extend `it_mcp_server_test.go`.

##### Steps

1. Start MCP with the default configuration and list tools, then invoke a
   typed write.
2. Restart with the development-only write flag and retry the same write.

##### Expected Results

- Default configuration omits mutating tools and performs no Fulfillment
  write RPC.
- The flag registers write tools; a host-confirmed call may mutate.

### NFR-6: Existing-capability boundary

#### TC-NFR6-01: Publish only typed allowlisted tools and actions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- **Execution:** `ginkgo run -r internal` from `fulfillment-service`.

##### Steps

1. Enumerate tools and annotation tuples from design.md §4.1.
2. Submit arbitrary service/method/payload inputs.

##### Expected Results

- Only documented tools convert to public RPCs.
- Arbitrary dispatch returns `invalid_request`.

#### TC-NFR6-02: Reject unsupported lifecycle operations without silent replacement

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].

##### Steps

1. Request networking Update, FabricDomain, identity admin, console, SSH, and in-guest management.
2. Request an in-place network CIDR edit.

##### Expected Results

- Unsupported operations return `unsupported_in_place` or `invalid_request`.
- No implicit delete.

## Planning Evidence Matrix

Working-directory convention: repository-root commands use `$REPO_ROOT`;
`ginkgo run -r internal` uses `$REPO_ROOT/fulfillment-service`; `pnpm` uses
`$REPO_ROOT/osac-ui`.

| Component / behavior and boundary | Requirements / ICs | Test case IDs | Tier / owner | Existing or proposed path and command | Prerequisites | Real dependencies | Simulated or omitted dependencies | Unresolved gap |
|---|---|---|---|---|---|---|---|---|
| MCP registry, schemas, outcomes, redaction | FR-18; NFR-2; NFR-6; IC-3, IC-5 | TC-FR18-01, TC-NFR2-01, TC-NFR2-02, TC-NFR6-01, TC-NFR6-02 | Unit / [DEV] | `ginkgo run -r internal` from `fulfillment-service/` | Go toolchain | MCP package | Public clients mocked | MCP package not on `main` |
| First-PR MCP HTTP client journey | FR-3; NFR-1, NFR-5; IC-3, IC-5 | TC-NFR5-01, TC-NFR5-03 | Component integration / [DEV] | Rebuild `fulfillment-service/it/it_mcp_server_test.go`; Kind fulfillment suite | Kind `osac-dev` | SDK client, Fulfillment, token | Providers omitted; writes gated off by default | Rebuild onto `main`; do not merge OSAC-4388 |
| Sequential writes, authz, partial/unknown failure | FR-13, FR-15, FR-16, FR-17; IC-4, IC-6, IC-7 | TC-FR13-01, TC-FR13-02, TC-FR13-03, TC-FR15-01, TC-FR16-01, TC-FR17-01, TC-FR17-02 | Component integration / [DEV] | proposed `it_mcp_sequential_writes_test.go` and related `it_mcp_*.go` | Kind | Fulfillment, PostgreSQL | Providers omitted | Proposed files |
| Typed write tools | FR-2, FR-6, FR-7, FR-8, FR-14; IC-5 | TC-FR2-02, TC-FR6-01, TC-FR7-01, TC-FR7-02, TC-FR8-01, TC-FR8-02, TC-FR14-04 | Component integration / [DEV] | proposed family `it_mcp_*.go` | Kind | Public APIs | Providers omitted | Proposed files |
| Tool annotations | FR-14; IC-5, IC-6 | TC-FR14-01, TC-FR14-02, TC-FR14-03, TC-FR14-04 | Unit / [DEV] | MCP package tests | Go toolchain | Registry | None | Proposed files |
| Tenant isolation and caller token | NFR-1; IC-1, IC-3, IC-7 | TC-NFR1-01, TC-NFR1-02, TC-NFR1-03 | Contract + component / [DEV] | proposed `mcp_auth/` and `it_mcp_tenant_isolation_test.go` | Two tenants | Auth, Fulfillment | Providers omitted | No contract harness Jira |
| Secret bytes excluded; existing UI create | FR-9; NFR-2; IC-8 | TC-FR9-01, TC-FR9-02 | E2E (manual) + unit | proposed secret-resume record; schema tests | Live UI for TC-FR9-01 | Existing Secret wizard | Handoff API omitted on purpose | No UI E2E harness; TC-FR9-01 is manual |
| Setup page | FR-11; NFR-3; IC-10 | TC-FR11-01, TC-NFR3-02 | Unit / [DEV] | `pnpm test` from `osac-ui/` | pnpm | React | Runtime metadata simulated | Proposed page |
| Installer, health, replicas, limits | NFR-4; IC-11, IC-12 | TC-NFR4-01, TC-NFR4-02, TC-NFR4-03 | E2E + component | proposed `tests/e2e/mcp/` and `it_mcp_limits_test.go` | MCP chart | Cluster, Keycloak | Handler controlled for counts | No MCP install profile |
| Host certification | FR-10; NFR-3; IC-13 | TC-FR10-01–06, TC-NFR3-01 | E2E / [QE] | proposed `tests/e2e/mcp/host-certification/` | Released hosts | Real OAuth + write | Generic client forbidden | Open Question 9.3 |
| Deployed family journeys | FR-1–FR-6; NFR-5 | TC-FR1-01, TC-FR2-01, TC-FR3-01, TC-FR3-02, TC-FR4-01, TC-FR5-01, TC-FR5-02, TC-FR6-02, TC-NFR5-02 | E2E / [QE] | proposed `tests/e2e/mcp/` | Providers | Full stack | None | Volume: OSAC-4845 / OQ 9.2 |
| Correlation | FR-19; IC-9 | TC-FR19-01, TC-FR19-02 | Component + E2E | proposed origin audit + `test_write_correlation.py` | Operator access | Fulfillment + provider | No write-record API | Provider gaps OSAC-4843/4850 |

## Gaps

### Requirement Coverage Gaps

All 25 PRD requirements have behavioral test cases.

- **FR-6 / NFR-5 — Volume real-backend:** TC-FR6-02 blocked by [OSAC-4845](https://redhat.atlassian.net/browse/OSAC-4845) and Open Question 9.2.
- **FR-9 — UI E2E:** TC-FR9-01 is manual until a browser harness exists. No owning Jira.
- **FR-10 / NFR-3 — six hosts:** Open Question 9.3. No owning Jira.
- **NFR-1 — Keycloak/token contracts:** proposed contract harnesses have no owning Jira.
- **NFR-4 — production sizing:** Open Question 9.1.
- **Provider-backed E2E:** [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843), [OSAC-4850](https://redhat.atlassian.net/browse/OSAC-4850).

### Interface Change Coverage Gaps

All 14 ICs have planned cases. Execution gaps remain for IC-1/11/13/14 (hosts/OQ 9.3), IC-8 (browser Secret create), IC-11/12 (MCP install profile), IC-3/5 Volume real backend.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 58 |
| Critical | 43 |
| High | 13 |
| Medium | 2 |
| Low | 0 |
| Automated | 50 |
| Manual | 8 |
| Requirements with test cases | 25 / 25 |
| Interface changes with test cases | 14 / 14 |
