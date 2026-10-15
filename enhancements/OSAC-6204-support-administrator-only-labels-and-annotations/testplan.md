# OSAC-6204 — Administrator-only metadata test plan

## Overview

- **Source:** [PRD](prd.md), its co-located clarifications, and [design draft](design.md).
- **Status:** Planned behavioral coverage; no implementation tests were executed during drafting or this revision.
- **Coverage:** 26 cases, five of five In Scope bullets, and nine of nine interface changes. Twenty-four cases are planned for automation; two are manual documentation reviews. Browser execution and exhaustive deployed fixtures still require the work recorded under G-1 and G-2.
- **Target:** 0.4 Tech Preview. The networking metadata contract question must be resolved before delivery.

The PRD uses In Scope bullets rather than FR/NFR identifiers. IS-1 through IS-5 below are local traceability anchors to those exact bullets, not new requirements. Implementation details such as selected-map replacement, reserved-entry preservation, rejection before resource writes, and filter projection are testable design mechanisms for those requirements.

## Requirements and interface coverage

| Anchor | PRD In Scope requirement | Primary cases | Design interface coverage |
|---|---|---|---|
| IS-1 | Administrators with existing permissions read/add/change/remove reserved metadata through private API, console, and CLI on all metadata-bearing resources | TC-IS1-01–06, TC-IS1-08–09 | IC-1, IC-2, IC-3, IC-7, IC-9 |
| IS-2 | Tenant API responses and console omit reserved keys | TC-IS2-01–06 | IC-1, IC-2, IC-5, IC-6, IC-7, IC-9 |
| IS-3 | Forbidden input observable in tenant requests fails the whole request clearly; omission preserves reserved entries [D7] | TC-IS3-01–02, TC-IS3-04–06 | IC-1, IC-3, IC-4, IC-7, IC-9 |
| IS-4 | Ordinary metadata keeps its existing behavior | TC-IS4-01–05 | IC-1, IC-2, IC-3, IC-4, IC-5, IC-6, IC-9 |
| IS-5 | Document exact reserved prefix and matching behavior | TC-IS5-01–02 | IC-1, IC-10 |

Under D6 and D7, the backend preserves omitted reserved entries and rejects supplied reserved entries or accepted explicit protected mask targets. Existing clients perform no new reserved-key validation. If a removal target is discarded during local map editing, the request may succeed and apply ordinary edits while retaining reserved entries. D7 supersedes the earlier named-client error requirement. Private API calls retain existing complete-map behavior under existing authorization.

Request locking remains optional: `lock` omitted/false skips the version comparison; `lock=true` checks the supplied version. Reserved-key protection applies to both modes. Database row locking and transaction atomicity remain in use in either mode.

Cases can provide evidence for several bullets; their primary anchor determines numbering only. The case metadata below lists every tested interface change from the design's API Extensions table.

Retired IDs: TC-IS1-07, TC-IS3-03, TC-IS3-07, and TC-IS3-08. IC-8 is retired because CLI behavior is unchanged; CLI cases verify backend enforcement through existing requests. IDs are not reused.

## Shared fixtures and oracles

Use an administrator account with existing platform-admin authorization, plus Tenant Admin and Tenant User accounts with their existing roles. Include a second tenant for isolation controls and the existing restricted private CSI identity. Preserve existing method/object authorization for each account; metadata rules depend on the API view. Exercise the administrator through private and public APIs, and run public tenant cases as both tenant personas where the method is authorized for ordinary use. [D8]

Seed valid stored dependencies for every object type. Use ordinary keys such as `example.org/environment` and reserved keys such as `admin.osac.openshift.io/tracking-id` in both maps, with unique marker values to detect disclosure. Include empty strings, multiple entries, and objects without protected entries. Do not rely on external provider provisioning to test a metadata edit; explicitly record seeded lifecycle/readiness states and the fact that no provider provisioning boundary is exercised.

Before each rejected or concurrent request, obtain an authorized private snapshot of the complete stored object, maps, and metadata.version. Afterward compare the complete object and relevant side-effect tables; checking only the public response cannot detect loss or partial writes. Pair public tenant reads with private administrator reads. Capture errors without copying protected values into logs or test reports.

Reserved-key public input returns InvalidArgument with “Label or annotation is reserved for use by the system.” Verify the status/message through existing gRPC, REST, Connect, CLI, and console error mappings. Existing authorization and other errors keep their current behavior; this status does not replace unrelated permission errors.

### Persistent resource inventory

| Family | Types requiring authorized private Get/List/Update coverage for both maps |
|---|---|
| Add-ons | AddOnOperator |
| Clusters | Cluster, ClusterTemplate, ClusterCatalogItem, ClusterVersion |
| Compute | ComputeInstance, ComputeInstanceTemplate, ComputeInstanceCatalogItem, InstanceType, DiskImage |
| Bare metal | BareMetalInstance, BareMetalInstanceTemplate, BareMetalInstanceCatalogItem, BareMetalInstanceType |
| Networking | NetworkClass, VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway, FabricDomain |
| Storage | StorageBackend, StorageTier, Volume |
| Platform / identity | Hub, Tenant, User, IdentityProvider, Project, ProjectMembership, Role, RoleBinding, Secret |

Total: 35 persistent types. Only Hub, NetworkClass, and StorageBackend are private-only. The other 32 include Volume and FabricDomain with public CRUD; include their existing public methods in input, response, preservation, and query coverage under existing permissions. Use only existing public event payloads. Test every private Update. SelfSubjectAccessReview is the additional ephemeral Metadata-bearing message, covered by TC-IS2-06 without persistent CRUD. Inventory completeness is an explicit assertion.

## Execution and evidence matrix

Commands below describe implementation-phase execution; none was run to validate this draft. Paths are relative to the workspace. Proposed files and runners are clearly identified. Real database, broker, authorization, gateway, proxy, and browser boundaries require their respective evidence; unit doubles do not substitute for them.

| Tier / owner | Suite and proposed additions | Working directory / execution | Real versus mocked dependencies; gaps |
|---|---|---|---|
| Unit / DEV | Existing fulfillment auth, validation, mapper, mask/filter, and CLI tests; add reserved predicate, raw-input/explicit-path rejection, map selection/merge, and existing-client compatibility coverage | `osac/fulfillment-service`: `ginkgo run -r internal` (use workspace-local GOCACHE/GOTMPDIR; heavy suites sequentially) | Policy/parser/transport fixtures and test doubles. This broad command also reaches the component suites below; report their real dependencies separately. |
| Component integration / DEV | Existing `internal/servers/servers_suite_test.go` and server tests; add full candidate, networking metadata compatibility and lifecycle restrictions, inventory, concurrency, and rejection without resource writes | `osac/fulfillment-service`: `ginkgo run --timeout 10m internal/servers` | Real PostgreSQL from database.Container; in-process RPC and mocked tenancy/attribution. This does not establish deployed Keycloak, REST, proxy, or provider behavior. |
| Events component integration / DEV | Existing `internal/servers/events_server_test.go`; add nested projection and filter privacy cases | `osac/fulfillment-service`: same server-suite command, executed once for the combined suite | Real Kafka via Kafka.Container, bufconn RPC, and mocked tenancy. Record broker startup/subscription readiness. Deployed identity coverage requires the next tier. |
| Deployed Fulfillment integration / DEV | Extend `it/it_labels_test.go` and `it/it_annotations_test.go`; proposed `it/it_metadata_inventory_test.go` and `it/it_metadata_transport_test.go` | `osac/fulfillment-service`: `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` | Real deployed API, PostgreSQL, Keycloak, REST gateway, and CLI. Seed metadata fixtures; this does not prove infrastructure-provider provisioning. G-2: all 35 valid fixtures, an authorized administrator, both tenant accounts, and restricted-client coverage must be added. |
| UI unit / DEV | Existing Vitest suites/mock Connect transport; add editor, all-type registry, tenant rendering/search, and error retention cases | `osac/osac-ui`: `pnpm test` | Mock transport/session data. Does not prove deployed proxy/API redaction or real login mapping. |
| Proxy unit / DEV | Existing bridge/middleware tests; cover map/mask/lock forwarding and InvalidArgument/concurrency error preservation | `osac/osac-ui/proxy`: `go test ./bridge ./middleware` with workspace-local Go cache/temp | Transport/schema fixtures. Real Connect forwarding remains a deployed browser/API assertion. |
| Deployed browser E2E / QE | Proposed maintained metadata journey suite under the mono-repo cross-component E2E structure `osac/tests/e2e/core/`; editor, all-resource registry, administrator and tenant accounts, network response privacy, and stale/error behavior | **Runner/command must be added as part of G-1.** Existing `pnpm playwright` in `osac/osac-ui` provides scratch live-cluster investigation, not a maintained metadata suite. | Real browser, console, proxy, API, and Keycloak. A tracked login-only spec does not supply metadata coverage; current package scripts/configuration do not establish this runner. No test command is invented here. |
| Documentation / DEV | API schema/reference, CLI help, admin and tenant guides | Manual review of TC-IS5-01 and TC-IS5-02 | Compare documented examples with the implemented contract and transport evidence. |

Remote integration or E2E execution must follow `~/.codex/skills/remote-integration-tests/SKILL.md`, including fresh-cluster, detached-run, resource-limit, routing, result-recovery, and cleanup requirements. This revision does not initiate an execution environment.

## Test Cases

### IS-1: Administrator metadata management

#### TC-IS1-01: Authorized private calls manage every persistent metadata type

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-7 | critical | automated |

**Tier:** Component integration; deployed Fulfillment

##### Preconditions

For each of the 35 persistent types, seed valid dependencies and an object with ordinary entries in both maps. The administrator account has existing platform-admin authority.

##### Steps

1. For each type and map, use the authorized administrator to Create with a reserved entry where supported, then Get/List through its private service.
2. Read the full map, change a reserved value and add a second reserved key, then remove each by omission from a replacement map. Select the edited map with the existing update_mask. Repeat with lock omitted/false and with lock=true plus the current version.
3. Compare ordinary entries, reserved values, identifier, and version after each mutation using an authorized private read.

##### Expected Results

- Every supported Create/Update succeeds for the authorized caller and both maps; private Get/List include exact reserved keys and values.
- All 35 persistent types have private Update coverage, including private-only types. Clients retain untouched entries and fields.

#### TC-IS1-02: Administrator map replacement, empty values, and deletion by omission

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-3 | high | automated |

**Tier:** Unit; component integration

##### Preconditions

An administrator reads a private object with two ordinary and two reserved entries in each map, plus an unrelated mutable field.

##### Steps

1. Select metadata.labels and submit a complete edited map with a reserved value changed, another key omitted, and a retained empty-string value. Leave annotations unselected.
2. Select both maps and replace their contents; separately select a map with an empty or omitted map payload to clear it.
3. Repeat with an allowed non-metadata field in the existing mask, and compare existing unmasked replacement on types that support it.
4. For an ordinary key supported by the existing native per-key path grammar, verify its previous update behavior remains intact.

##### Expected Results

- A selected private administrator map equals the submitted map: omitted ordinary and reserved entries are deleted; an empty string is stored as a value.
- A selected empty/omitted map clears completely. Unselected maps and fields remain intact. Allowed mixed field changes apply atomically.
- Existing unmasked/per-key behavior is retained where supported; no new request field or implied-mask convention is introduced.

#### TC-IS1-03: Networking metadata reuses supported Update behavior

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | critical | automated |

**Tier:** Component integration; deployed Fulfillment

##### Preconditions

Fixtures cover NetworkClass, VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway, and FabricDomain in valid stored states. Record existing metadata operations, operational/default-label checks, and immutable-field restrictions. The first eight have no public Update; FabricDomain has public/private Update under existing permissions.

##### Steps

1. Using the authorized administrator, set, change, and remove reserved entries through private Update on all nine services using fetched replacement maps and existing map-level masks. Repeat with lock omitted/false and with lock=true plus the current version.
2. Exercise supported ordinary and mixed ordinary/reserved map edits, retaining untouched operational labels. ExternalIP, ExternalIPAttachment, and NATGateway use a nonempty ordinary mask.
3. Attempt each recorded forbidden field/default-label change together with a reserved edit. Also omit the mandatory mask on the three lifecycle services.
4. Verify public Update remains absent for the first eight services. Exercise an authorized ordinary public FabricDomain Update and verify that stored reserved entries survive; retain its existing resource validators and controller status behavior.

##### Expected Results

- All nine private services accept the required reserved metadata edits under existing method/object permissions and resource rules; editing metadata needs no new reserved-only mode.
- Supported ordinary and mixed map updates remain supported. Unselected spec/status and lifecycle state remain unchanged.
- Forbidden field/default-label changes and missing mandatory masks retain their existing errors; no subset or version change is saved.
- The first eight services gain no public Update. Existing public FabricDomain Update remains available under existing permissions and public metadata protection; its type/virtual-network immutability and status/server-list restrictions remain enforced. Controller status operations remain supported.

#### TC-IS1-04: REST uses existing whole-map PATCH masks

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

**Tier:** Gateway unit; deployed Fulfillment

##### Preconditions

A mutable private object has multiple entries in both maps and a known version. Use the existing generated gateway and default query parser.

##### Steps

1. PATCH an edited labels map containing qualified keys, first with update_mask=metadata.labels, then without an explicit mask to exercise the body-derived mask. Repeat with lock omitted/false and with lock=true plus the current version.
2. With an explicit labels mask, send an empty map, then an omitted map, to clear labels. Repeat for annotations and for both selected maps.
3. Compare REST results with native gRPC map-level requests and verify unselected maps/fields through private reads.

##### Expected Results

- Qualified keys remain map entries and reach the service unchanged; body-derived masks select complete maps, not per-key paths.
- Administrator replacement/clearing agrees with native gRPC. Explicit masks retain selection; unselected fields remain intact. Stale versions are rejected only when lock=true; unlocked updates require no version precondition.
- No custom query parser or additional mask representation is required. Tenant map preservation is checked separately by TC-IS4-01.

#### TC-IS1-05: CLI private metadata operations retain existing requests

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | high | automated |

**Tier:** CLI unit; deployed Fulfillment

##### Preconditions

The existing CLI has private administrator credentials against a server implementing this feature and resolves all inventory types through existing names/aliases.

##### Steps

1. For all types, use the authorized administrator to label/annotate a fetched private map using key=value and key- to set, change, and remove reserved entries.
2. Combine several edits, including an empty value and removal of an already-absent key; include untouched ordinary/reserved entries in the fixture.
3. Inspect protocol-unit requests and structured/human output after the deployed command.

##### Expected Results

- The existing request contains the fetched object with the intended map edits. Request construction and mask/lock defaults remain unchanged; no new metadata field, mask, or version precondition is forced.
- Untouched map entries and unrelated fields remain intact; key- deletes by omission and an empty string remains a value. Authorized absent-key removal is a no-op.
- Authorized private reads show reserved values for every type. Alias/registry completeness failures cannot silently omit a type.

#### TC-IS1-06: Console registry and editor cover all persistent types under existing permissions

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-7, IC-9 | critical | automated |

**Tier:** UI unit; deployed browser E2E

##### Preconditions

The administrator can sign in to the deployed console using existing credentials. Valid fixtures exist for all 35 types; private schema/proxy support matches the API.

##### Steps

1. Open /admin/metadata as the administrator and enumerate every type, including private-only types and types without a dedicated detail page.
2. For each type, use both map editors to add, change, and remove a reserved entry while retaining untouched ordinary/reserved entries.
3. Inspect Connect/proxy forwarding of full selected maps, the existing mask, and any supplied lock/version options; follow detail-page links and reload through the API. Verify this feature does not force lock=true.

##### Expected Results

- The authorized administrator can perform the required actions; registry completeness is checked against all 35 types.
- Editors display complete private maps and submit their edited replacements using existing update options, with no mandatory version checking. Untouched entries and unselected maps/fields remain intact.
- Connect/proxy/API persistence and existing detail-page links reach the same shared editor.

#### TC-IS1-08: Existing authorization and original API view define behavior

| Interface Change | Priority | Automation |
|---|---|---|
| IC-7 | critical | automated |

**Tier:** Auth unit; deployed Fulfillment

##### Preconditions

Accounts cover the administrator, Tenant Admin, Tenant User, and the restricted private CSI client. Record their existing allowed methods, object scope, and tenant visibility as the baseline.

##### Steps

1. Exercise allowed and disallowed private methods for each account and compare authorization with the baseline.
2. As the administrator, read and edit reserved entries through allowed private methods; repeat reads and reserved Create/Update input through corresponding public methods where they exist.
3. Verify the original public view survives in-process delegation to private handlers. Read a Volume through an allowed private CSI method as a control.

##### Expected Results

- Existing method/object and tenant/project authorization is unchanged for every account. Private access remains governed by existing permissions; tenant identities gain no private methods.
- Authorized private calls retain complete metadata, including allowed CSI Volume reads. No new is_admin decision or Subject field is required.
- Public calls return the same filtered view for every caller, including administrators, even when a public handler delegates to private code.
- Public reserved Create/Update requests from the administrator return InvalidArgument and apply no changes or side effects. Private method access never bypasses a public call's reserved-key restriction.

#### TC-IS1-09: Optional version checks retain existing update semantics

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-9 | high | automated |

**Tier:** Component integration; deployed Fulfillment; CLI/UI unit

##### Preconditions

An administrator reads a complete map at version v; a second authorized update changes an otherwise untouched entry and advances the row to v+1.

##### Steps

1. Submit the edited stale map with its ordinary map-level mask, metadata.version=v, and lock=true through gRPC, REST, and Connect requests.
2. Read the complete private object after each rejection and inspect CLI/editor state.
3. Repeat the API request with lock=false and with lock omitted, using a stale or omitted version. Compare the result with existing selected-map replacement semantics.
4. Reload the full current map/version, retain the concurrent entry, and resubmit the intended edit with lock=true.
5. Inspect CLI/UI protocol fixtures: preserve existing lock defaults and any existing caller opt-in option, without adding a mandatory version precondition.

##### Expected Results

- With lock=true, a stale operation returns Aborted, changes nothing, and retains the current map/version. Clients receiving that error report failure and retain unsaved edits for reload/resubmission.
- With lock omitted/false, version mismatch alone does not reject the request. A valid replacement succeeds under existing semantics and can overwrite a concurrent change in the selected private map.
- A fresh-version locked replacement succeeds without losing the other administrator entry. Client defaults and existing opt-in options remain unchanged.

### IS-2: Tenant visibility

#### TC-IS2-01: Every public object response omits reserved entries

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-5 | critical | automated |

**Tier:** Projection unit; deployed Fulfillment

##### Preconditions

For each of the 32 public persistent metadata-bearing types, including Volume and FabricDomain, seed both maps with ordinary and reserved entries. Include nested Metadata and authorized private-service controls.

##### Steps

1. Get and List as both tenant personas; perform allowed ordinary Create/Update that returns an object containing stored reserved metadata.
2. Repeat public reads with administrator credentials and inspect nested response objects.
3. Compare public responses produced through existing public mappers with authorized private responses and the stored source; inspect whether projection mutated that source.

##### Expected Results

- No reserved key or value appears in public object responses; ordinary entries, authorized resource scope, and versions retain their established shape.
- Administrators using public RPCs get the same projection. Nested actual Metadata messages are projected recursively, while unrelated payload maps are unchanged.
- Projection uses detached responses; private responses, stored objects, and in-process private objects retain their full maps under existing authorization.

#### TC-IS2-02: Event payload and filter projection preserve privacy

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-6 | critical | automated |

**Tier:** Events component integration; deployed Fulfillment

##### Preconditions

Real Kafka-backed EventsServer coverage is available. Public watches are ready before publication; seed an object with both map kinds and register a watcher with existing private Watch permission.

##### Steps

1. Publish a create/update event containing reserved entries, nested Metadata, and a known ordinary filter match.
2. Consume through public tenant, public administrator, and authorized private watches; compare event identifiers, timestamps, and visible entries. Verify public mapping runs before predicate evaluation.
3. Change a reserved value without changing ordinary matching entries and repeat; allow at most 30 seconds after publication in the test harness.

##### Expected Results

- All public events omit reserved entries before the public event filter runs; authorized private events retain them under existing permissions.
- Ordinary matching behavior, identifiers, and timestamps remain unchanged. No stored or publisher object is mutated by projection.
- The 30-second bound is a bounded test wait, not a new product delivery SLA; publication/subscription readiness failures are diagnosed separately.

#### TC-IS2-03: List and watch filters cannot probe protected key existence

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

**Tier:** Filter unit; component integration; deployed Fulfillment

##### Preconditions

Prepare otherwise identical objects with the target reserved key present and absent, plus ordinary metadata matches and nonmatches.

##### Steps

1. Submit accepted CEL syntaxes that explicitly reference a reserved label or annotation, including membership, indexing, and mixed ordinary/reserved expressions.
2. Repeat for List and event-filter entry points with the reserved key present and absent.
3. Exercise already-supported whole-map predicates against the projected map and compare List items and totals.

##### Expected Results

- Every explicit protected-key reference returns InvalidArgument uniformly before item/count SQL or subscription filtering, independent of stored existence.
- Already-supported whole-map predicates evaluate only visible metadata and return matching counts; unsupported syntax retains its existing error rather than gaining a new query operator.
- Ordinary literal-key predicates retain the existing indexed query path.

#### TC-IS2-04: Tenant console display, search, and network responses contain no reserved values

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-9 | critical | automated |

**Tier:** UI unit; deployed browser E2E

##### Preconditions

Tenant Admin and Tenant User sessions have access to objects with unique reserved marker values and ordinary catalog/search metadata.

##### Steps

1. Open available catalog and resource detail views and search using ordinary keys and reserved marker values.
2. Inspect console network response bodies, rendered text, accessible labels, and structured CLI output for the same public objects.
3. Compare ordinary result membership with API projected results.

##### Expected Results

- Reserved keys and marker values are absent from tenant API/Connect response bodies, UI display/search results, and CLI structured/human output.
- Ordinary search and display behavior remains consistent with the existing authorized public view. Hiding a field in the frontend alone does not satisfy this case.

#### TC-IS2-05: Private clients keep existing metadata access and method restrictions

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-7 | critical | automated |

**Tier:** Auth/projection unit; deployed Fulfillment

##### Preconditions

The existing CSI identity has universal tenant visibility and private Volume Create/Get/Delete/List permission, without Update. Seed valid Volume dependencies and fixtures across two tenants.

##### Steps

1. Get/List Volumes containing reserved entries through the CSI identity's allowed private methods.
2. Create a valid Volume with reserved entries using its existing private Create permission; attempt Update and another method outside its allowlist.
3. Compare the same allowed reads using an authorized administrator and compare stored maps after rejected methods.

##### Expected Results

- CSI private Get/List responses retain complete maps, including reserved values. Valid private Create retains existing metadata behavior; it is not rejected by a new metadata permission check.
- Update and other disallowed methods remain denied without changing stored objects. Administrator private reads retain the same reserved values. No method allowlist or tenant scope is widened by this feature.

#### TC-IS2-06: Ephemeral review Metadata uses the same boundary without persistent CRUD

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-5 | high | automated |

**Tier:** Projection/input unit; component integration

##### Preconditions

SelfSubjectAccessReview is an ephemeral message carrying Metadata, not one of the 35 persistent objects.

##### Steps

1. Submit a review request with ordinary metadata through each supported external view.
2. Exercise response projection with a review response fixture containing reserved entries, including a nested review message.
3. Submit a review carrying a reserved map entry through each supported public/private view under existing method permissions; check that the public handler validates before delegation.

##### Expected Results

- Ordinary review behavior remains unchanged. Public outputs omit reserved entries wherever Metadata occurs; allowed private review calls retain existing complete-map behavior.
- Public reserved input returns InvalidArgument before review processing, with the shared reserved-for-system message. Private method authorization remains unchanged. The test does not invent Get/List/Update or persistence for the ephemeral review.

### IS-3: Atomic rejection of tenant mutations

#### TC-IS3-01: Tenant Create with mixed metadata fails as a whole

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-4, IC-7 | critical | automated |

**Tier:** Input unit; deployed Fulfillment

##### Preconditions

Both tenant personas have valid create permissions on representative mutable services and valid referenced dependencies. Complete existing account setup before the case; record object count and resource dependency/provisioning side effects.

##### Steps

1. Create with an ordinary entry plus a reserved label; repeat with a reserved annotation and both maps.
2. Repeat across the supported Create inventory, including requests where reserved entries are nested in actual Metadata. Verify the public handler rejects original input before mapping/delegation or resource preparation.
3. Inspect the public error, authorized private inventory, and transaction-side-effect tables.

##### Expected Results

- Every forbidden request returns InvalidArgument and creates no object, ordinary metadata, version, reference, or provisioning side effect.
- The error identifies the protected-target rule without revealing stored reserved values. Ordinary create requests remain covered by compatibility cases.

#### TC-IS3-02: Tenant Update cannot add or overwrite a reserved entry

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4, IC-7 | critical | automated |

**Tier:** Input/candidate unit; deployed Fulfillment

##### Preconditions

A tenant-visible object has ordinary metadata and stored reserved entries; take a complete authorized private snapshot including version.

##### Steps

1. Update with mixed ordinary changes and a reserved entry that adds a key, changes a value, or supplies the same stored value.
2. Repeat with the reserved supplied entry outside the ordinary mask and in each map. Verify rejection before mapping/delegation; allowed controls reach GenericServer's shared candidate path before resource preparation/validation.
3. Read the full private object after each attempt.
4. Repeat with lock omitted/false and with lock=true plus the current version.

##### Expected Results

- All attempts return InvalidArgument based on raw supplied protected input, including unchanged values and entries outside the ordinary mask.
- The entire stored object and version equal the pre-request snapshot; no ordinary subset is committed.

#### TC-IS3-04: Existing explicit mask paths cannot bypass protected targets

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | high | automated |

**Tier:** Input/mask unit; REST/gRPC component integration

##### Preconditions

Existing clients call public Update with ordinary update_mask; capture complete private snapshots for otherwise identical objects with a reserved key present and absent.

##### Steps

1. Exercise any existing mask syntax the server accepts that explicitly identifies a reserved key, including native gRPC paths, with its value omitted.
2. Submit REST/Connect encodings with invalid quoted/slash-containing FieldMask forms.
3. Submit a valid ordinary whole-map replacement omitting hidden keys as a separate control.

##### Expected Results

- Accepted explicit protected paths return InvalidArgument before mutation, regardless of key existence; ordinary changes and versions remain unchanged.
- Malformed encodings retain their validation/decoding errors with no mutation; these are separate from reserved-key input validation.
- The valid omission control succeeds for ordinary edits and preserves hidden entries. No new qualified per-key grammar is added.

#### TC-IS3-05: Existing CLI receives backend rejection or omission preservation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | critical | automated |

**Tier:** CLI unit; deployed Fulfillment

##### Preconditions

Tenant CLI credentials can edit ordinary metadata; reserved entries are hidden by Get. Capture the full object/version and record Update invocations.

##### Steps

1. Run label with an ordinary set plus reserved key- removal; repeat for annotate and an absent reserved key.
2. Run a mixed ordinary/reserved set command, including a reserved entry with an unchanged value.
3. Inspect outgoing requests, exit status, stderr, and the complete private stored object after each command.

##### Expected Results

- A removal represented only by map omission succeeds under existing CLI behavior. The backend retains the exact stored reserved portion and applies the ordinary edit; no reserved key is deleted, regardless of stored existence.
- Mixed ordinary/reserved set commands reach the backend with the reserved entry, return InvalidArgument through existing CLI error handling, and leave the entire stored object/version unchanged.
- The CLI adds no reserved-key validation or special removal target. Public output remains filtered in both cases.

#### TC-IS3-06: REST and Connect enforce input rejection and omission preservation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4, IC-9 | critical | automated |

**Tier:** UI/proxy unit; deployed Fulfillment; deployed browser E2E

##### Preconditions

A tenant has pending ordinary edits and an object with reserved entries. Capture its full private snapshot; transport fixtures can submit reserved entries directly to the backend.

##### Steps

1. Send mixed ordinary/reserved map entries through REST and Connect/proxy, including requests crafted outside normal tenant controls.
2. Drive the editor error component with the returned server error and inspect retained edits and request forwarding.
3. Submit a tenant replacement containing only ordinary entries, omitting reserved entries, then read the full private object.

##### Expected Results

- Supplied reserved entries cause InvalidArgument with existing transport mappings and no object/version/side-effect changes. Neither transport strips them and retries the ordinary subset.
- The editor displays the backend error and retains unsaved changes. No client-side reserved-key validator is required.
- Ordinary replacement succeeds and keeps stored reserved entries. Omission is not an explicit-removal request and does not produce a reserved-key error.

### IS-4: Ordinary metadata compatibility

#### TC-IS4-01: Every tenant replacement preserves stored reserved entries

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | critical | automated |

**Tier:** Candidate unit; deployed Fulfillment

##### Preconditions

A tenant-visible mutable object contains multiple ordinary/reserved entries in both maps. Capture the complete private object and its version. Record each public wrapper's baseline unmasked map behavior; include ComputeInstance's nonempty-map merge.

##### Steps

1. Replace metadata.labels, metadata.annotations, and parent metadata with existing accepted masks. Separately exercise supported no-mask paths with nonempty, empty, and omitted maps.
2. Send ordinary edits, empty selected maps, and omitted selected maps; verify an unselected map remains unchanged.
3. Run an older CLI fixture that deletes an unseen reserved key locally before submitting its ordinary map, including a mixed ordinary change.
4. Repeat accepted forms with lock omitted/false and with lock=true plus the current version; compare complete private maps/versions with the baseline ordinary replacement behavior.

##### Expected Results

- Every successful tenant update restores all reserved entries from the locked current row, including parent-map and unmasked replacements.
- Selected-map replacement removes omitted ordinary keys; empty/omitted selected maps clear only ordinary entries. Unselected maps remain intact for masked updates.
- Public unmasked updates retain each handler's baseline behavior. For ComputeInstance, a nonempty submitted map retains omitted ordinary keys through the existing copy/merge path; empty-map clearing follows existing behavior. Reserved entries always come from the latest locked row.
- The older client receives success for the valid ordinary request and reports no local reserved-removal error; stored reserved entries remain unchanged. The server does not infer an explicit removal from omission.
- Raw reserved entries still fail atomically under TC-IS3-02; merging does not silently accept a supplied forbidden key.

#### TC-IS4-02: Namespace boundaries and ordinary operational metadata

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-5 | high | automated |

**Tier:** Predicate/validation unit; deployed Fulfillment

##### Preconditions

Use valid ordinary keys including osac.openshift.io/tenant and osac.openshift.io/owner-reference where the existing API permits them, plus near-prefix strings accepted by existing syntax validation.

##### Steps

1. Evaluate admin.osac.openshift.io/key, child.admin.osac.openshift.io/key, and a.b.admin.osac.openshift.io/key. Seed them through an authorized private write and inspect public response visibility in both maps.
2. Exercise ordinary handling and visibility for fakeadmin.osac.openshift.io/key, admin.osac.openshift.io.example/key, the slashless key admin.osac.openshift.io, and existing operational keys. Check uppercase DNS prefixes, key-name segments, and label values against existing validation; retain arbitrary annotation string values.
3. Verify values, including empty strings, retain their established validation/storage behavior.

##### Expected Results

- The base DNS namespace and every dot-delimited subdomain are reserved and omitted from public responses. Match case-sensitively without normalization; similarly named domains and slashless keys remain ordinary.
- Operational isolation/lifecycle keys are not reclassified as reserved. Existing validation and resource-specific ownership restrictions still apply to ordinary keys.
- Uppercase DNS prefixes/key-name segments and uppercase label values remain invalid; annotation values remain arbitrary strings. This feature adds no broader syntax acceptance.

#### TC-IS4-03: Concurrent tenant updates preserve the latest reserved metadata

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | critical | automated |

**Tier:** Real-PostgreSQL component integration; deployed Fulfillment

##### Preconditions

A tenant reads its visible maps/version v; an administrator adds, changes, or removes a reserved entry and commits before the tenant Update acquires the row.

##### Steps

1. Submit the stale ordinary replacement with its map-level mask and lock=true; inspect the row.
2. Repeat with lock=false and with lock omitted, controlling row-acquisition order and using a stale or omitted request version. Include empty-map, parent-metadata, and unmasked forms where those forms are supported.
3. Compare ordinary edits and the complete latest reserved portion through an authorized private read.

##### Expected Results

- The stale locked request returns Aborted and changes nothing.
- An allowed unlocked update retains exactly the latest reserved portion from the locked stored row: additions and new values survive, and an administrator removal is not resurrected.
- Ordinary replacement/deletion retains its baseline behavior; tenant snapshots or pre-lock reads are never the source of restored reserved entries.

#### TC-IS4-04: Ordinary filtering, totals, and watches retain existing behavior

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-6 | high | automated |

**Tier:** Filter unit; Kafka/PostgreSQL component integration; deployed Fulfillment

##### Preconditions

Objects have ordinary match/nonmatch metadata and hidden reserved entries; existing accepted filter expressions and baseline counts are recorded.

##### Steps

1. Run existing ordinary literal-key and supported whole-map List filters and compare items/total.
2. Publish matching and nonmatching events and observe tenant watches using the same ordinary predicates.
3. Repeat after changing only a reserved entry.

##### Expected Results

- Ordinary literal-key results, counts, and watch membership match the existing baseline; SQL keeps the indexed literal-key path.
- Whole-map predicates observe the documented visible projection. Reserved-only changes do not alter an ordinary predicate result or expose a protected entry.

#### TC-IS4-05: Ordinary clients and service mutation boundaries remain compatible

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-9 | high | automated |

**Tier:** CLI/UI unit; deployed Fulfillment

##### Preconditions

Use existing and older CLI fixtures against feature-enabled servers, ordinary client fixtures against legacy servers, existing ordinary console controls, public networking services, and private networking fixtures with recorded allowed metadata operations.

##### Steps

1. Perform established ordinary label/annotation operations through existing clients; inspect request construction and existing mask/lock defaults.
2. Repeat ordinary console editing on mutable public resources and inspect filtered responses.
3. Verify public Update remains absent for NetworkClass, VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway. Exercise existing public Volume CRUD and FabricDomain Update with authorized callers and verify public metadata protection.
4. Replay supported private networking metadata updates with existing masks and full-map requests, retaining system/default labels.

##### Expected Results

- Supported ordinary operations remain available using unchanged CLI requests and existing optional lock behavior. Backend candidate handling preserves unrelated fields under the existing update semantics.
- The new server preserves reserved entries on tenant updates. Ordinary older-server operations remain supported. Reserved writes use the existing request contract without metadata-support discovery.
- The eight named services gain no public Update. Volume and FabricDomain keep their existing public methods and authorization. Existing private networking metadata, operational-label, immutable-field, and lifecycle-mask rules remain enforced.

### IS-5: Prefix and behavior documentation

#### TC-IS5-01: Documentation defines the namespace and subdomain matching

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-10 | medium | manual |

**Tier:** Documentation review

##### Preconditions

API reference, administrator guide, and tenant guide drafts accompany the implementation.

##### Steps

1. Review the reserved namespace and examples in each guide.
2. Compare examples with the predicate tests, including subdomain, case/syntax handling, ordinary operational keys, and empty-value semantics.

##### Expected Results

- Every guide names admin.osac.openshift.io/ and explains case-sensitive matching of the base DNS namespace and all subdomains, including examples that reject similar non-subdomain names. No configurable namespace variants are introduced.
- Examples agree with executable contract cases and preserve the distinction between reserved matching and existing syntax validation.

#### TC-IS5-02: Documentation covers personas, map semantics, errors, and compatibility

| Interface Change | Priority | Automation |
|---|---|---|
| IC-10 | medium | manual |

**Tier:** Documentation review

##### Preconditions

Guide examples, CLI help, and API schema are available for the proposed implementation.

##### Steps

1. Review the administrator journey and both tenant expectations across API, CLI, and console.
2. Check native gRPC, existing REST PATCH/query masks, and Connect examples for complete selected maps, omission-based deletion, empty maps/values, the feature-enabled server requirement, and stale versions.
3. Check the all-resource inventory, backend-only enforcement, public raw-input rejection, public omission preservation, unchanged private behavior, and older-server limitations.

##### Expected Results

- Guides describe administrator actions under existing permissions on all persistent types and private-only types, public privacy, and whole-request rejection for observable forbidden public input. The error is InvalidArgument with “Label or annotation is reserved for use by the system.” Existing method/object authorization and other errors are unchanged; permitted private clients retain complete metadata with no new metadata role check.
- Examples make update masks optional except where an existing service requires one, and keep existing lock behavior. Selected maps use replacement semantics; public reserved omissions are preserved. Unmasked public requests retain existing wrapper behavior, including ordinary-map merging where present. A discarded reserved removal target may yield success with ordinary edits applied and reserved entries unchanged; no client check or inferred removal error is promised.
- Guides state that privacy requires a server implementing this feature; older servers keep their existing visibility rules. Support guidance excludes in-place upgrades, describes unchanged optional body logging, and omits protected values from examples/support captures. Feature-specific validation messages contain only methods and supplied key names; no new global log-redaction guarantee is claimed.

## Coverage summary and remaining work

- **26 cases:** 16 critical, 8 high, 2 medium, 0 low.
- **Automation:** 24 planned automated cases and two manual documentation cases. A case spanning tiers requires evidence at every listed relevant boundary.
- **Requirement coverage:** 5/5 local In Scope anchors mapped; no PRD scope bullet is omitted.
- **Interface coverage:** 9/9 design interface IDs mapped. The table below provides an independent index.

| Interface | Cases |
|---|---|
| IC-1 | TC-IS1-01, TC-IS1-02, TC-IS2-01, TC-IS2-06, TC-IS3-01, TC-IS4-02, TC-IS5-01 |
| IC-2 | TC-IS1-01, TC-IS1-03, TC-IS1-05, TC-IS1-06, TC-IS2-01, TC-IS4-05 |
| IC-3 | TC-IS1-02, TC-IS1-03, TC-IS1-04, TC-IS1-05, TC-IS1-09, TC-IS3-02, TC-IS3-04, TC-IS3-05, TC-IS3-06, TC-IS4-01, TC-IS4-03 |
| IC-4 | TC-IS3-01, TC-IS3-02, TC-IS3-04, TC-IS3-05, TC-IS3-06, TC-IS4-01, TC-IS4-03 |
| IC-5 | TC-IS2-01, TC-IS2-02, TC-IS2-04, TC-IS2-05, TC-IS2-06, TC-IS4-02, TC-IS4-04 |
| IC-6 | TC-IS2-02, TC-IS2-03, TC-IS4-04 |
| IC-7 | TC-IS1-01, TC-IS1-06, TC-IS1-08, TC-IS2-05, TC-IS3-01, TC-IS3-02 |
| IC-9 | TC-IS1-06, TC-IS1-09, TC-IS2-04, TC-IS3-06, TC-IS4-05 |
| IC-10 | TC-IS5-01, TC-IS5-02 |

### Execution gaps

| Gap | Required work / owner | Affected coverage | Ticket status and closure evidence |
|---|---|---|---|
| G-1 | QE with console maintainers: establish a maintained browser runner, correct discovery/configuration, add deployed metadata journeys, and document the execution command | TC-IS1-06, TC-IS2-04, TC-IS3-06; browser portions of stale/error cases | Work belongs to OSAC-6204; no separate follow-up ticket has been created. Close with committed suite/runner, reproducible command, deployed administrator and tenant results, and saved failure artifacts. |
| G-2 | Fulfillment DEV with QE: create valid inventory fixtures and deployed identity credentials/seed setup for all 35 persistent types, both maps, the authorized administrator, both tenant personas, and restricted CSI identity | TC-IS1-01, TC-IS1-03, TC-IS1-05, TC-IS1-08, TC-IS2-01, TC-IS2-05, TC-IS3-01 and exhaustive regression matrix | Work belongs to OSAC-6204; no separate follow-up ticket has been created. Close with executable fixtures, explicit seeded lifecycle states, inventory completeness assertions, and real deployed transport/auth evidence. |

The networking contract question concerns the eight types listed in the accepted metadata-immutability document and their existing private updates. TC-IS1-03 and TC-IS4-05 verify current masks and resource validation, plus FabricDomain's existing public/private methods. Preserve supported ordinary operations and existing API availability. G-1/G-2 remain delivery prerequisites for the full resource/interface scope.

### Acceptance evidence

Completion requires real results for the exhaustive inventory and required boundary suites, not only a case count or mocked success. Record the executed command/cwd, commit, suite/tier, account setup, real dependencies and doubles, result artifacts, and any remaining gap with its owner. Rejected reserved requests must leave the complete object/version and side effects unchanged; tenant response/filter evidence must contain no protected values. The authorized administrator must demonstrate the required API, CLI, and deployed console actions. Ordinary compatibility cases and the documentation reviews must pass before milestone graduation.
