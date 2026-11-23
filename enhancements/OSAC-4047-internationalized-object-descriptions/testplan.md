# Testplan — OSAC-4047

## Overview

- **Feature:** OSAC-4047 — Internationalized Object Descriptions
- **Total test cases:** 59 (58 requirement-tier + 1 E2E journey)
- **Requirements covered:** 18 of 18 (FR-1…FR-14, NFR-1…NFR-4)
- **Interface changes covered:** 13 of 13 (IC-1…IC-13)

Tier and owner assignments follow the repo integration-testing policy.
The infrastructure table below names the owning suite, command, and
dependency boundary; each test case also carries an explicit `Owner`
column.

## Test Infrastructure and Evidence

| Tier | Owner | Suite / proposed location | Command | Real dependencies | Faked or omitted |
|---|---|---|---|---|---|
| Unit / server-database | [DEV] | `fulfillment-service/internal/servers` | `cd fulfillment-service && ginkgo run --timeout 20m internal/servers` | In-process servers and a real PostgreSQL testcontainer | Tenancy, attribution, and external clients are controlled doubles where declared by the suite |
| Unit / validation | [DEV] | `fulfillment-service/internal/validation` | `cd fulfillment-service && ginkgo run --timeout 10m internal/validation` | Real protovalidate contracts and request interceptor | No database or deployed service |
| Unit / migration | [DEV] | `fulfillment-service/internal/database/migrations` (must be created) | `cd fulfillment-service && ginkgo run --timeout 20m internal/database/migrations` | Real PostgreSQL migration harness | No deployed service, operator, or provider |
| Component integration | [DEV] | `fulfillment-service/it` | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; focused rerun: `cd fulfillment-service && ginkgo run it` | Deployed Fulfillment, PostgreSQL, authenticated APIs, Kubernetes, and checkout CLI | Provider networking is disabled; no provider provisioning is claimed |
| Console component | [DEV] | `osac-ui/libs/ui-components` | `cd osac-ui && pnpm --filter @osac/ui-components exec vitest run` | Real React DOM, Testing Library, and sanitizer output | No browser, network, backend, or deployed console |
| E2E | [QE] | `tests/e2e/core/test_internationalized_descriptions.py` (must be created) | `pytest -q tests/e2e/core/test_internationalized_descriptions.py` | Deployed OSAC, Fulfillment, PostgreSQL, console, and CLI | Requires the standard E2E deployment and credentials; no provider-backed workload is required |

Execution status: **not executed — design phase**. The migration suite and E2E file are
required implementation deliverables at the named paths. Implementation stories must record
the executed command, working directory, result, and any skipped or unavailable prerequisite.

Per-case ownership is explicit in the `Owner` column. Cases marked
`automated (unit, servers suite)`, `automated (unit, migration test)`,
`automated (integration, it/ suite)`, and `automated (Vitest, component)`
are `[DEV]` work; E2E journeys are `[QE]` work.

## Test Cases

### FR-1: Atomic create with documentation

#### TC-FR1-01: Create with embedded description links object and document

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-2, IC-3 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A tenant and project exist; the caller can create the object type.

##### Steps

1. Send `Create` for an object with a content-only
   `DocumentSpec description` containing two variants (`en-US`,
   `es-ES`) and an omitted optional `fallback`.

##### Expected Results

- The real Create interceptor accepts the owner-less embedded
  `DocumentSpec`; the server, not the client, stamps the owner.
- Response is the created object; `metadata.description` holds a
  document id; a `Documents/Get` for that id returns the document with
  `spec.fallback = "en-US"` (English default per FR-8), both variants,
  the server-stamped typed owner branch for the created object, and
  tenant/project/name auto-populated from the object.

#### TC-FR1-02: Document validation failure persists neither object nor document

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-3, IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- The embedded `DocumentSpec` contains an invalid language tag
  (`english`).

##### Steps

1. Send `Create` with the invalid embedded `DocumentSpec`.
2. Query the object and document by name/id.

##### Expected Results

- Create returns `InvalidArgument` naming `language tag "english"`;
  neither an object row nor a document row exists.

#### TC-FR1-03: Create without description creates no document

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-2 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Send `Create` without the `description` field.

##### Expected Results

- The object is created; `metadata.description` is unset; no document
  row exists for the object's name.

### FR-2: Per-language variant updates

#### TC-FR2-01: Adding one variant leaves other variants untouched

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A document exists with `en-US` and `es-ES` variants.

##### Steps

1. Send `Documents/Update` with mask path
   `spec.variants["fr-FR"]` and only the French variant in the payload.

##### Expected Results

- The response document contains `en-US`, `es-ES` (byte-identical to
  before), and the new `fr-FR`; `metadata.version` incremented once.

#### TC-FR2-02: Explicit mask deletion removes exactly one variant

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A document exists with `en-US` (fallback), `es-ES`, `fr-FR`.

##### Steps

1. Send `Documents/Update` with mask path `spec.variants["fr-FR"]` and
   no French variant in the payload.

##### Expected Results

- `fr-FR` is deleted; `en-US` and `es-ES` remain; the standalone
   object Get shows two variants.

#### TC-FR2-03: Omission without a mask path never deletes

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Send `Documents/Update` replacing `spec` with a payload listing only
   `en-US`, with mask path `spec.fallback` (not naming variants).

##### Expected Results

- All previously stored variants remain (map untouched); only the
  masked field changes.

#### TC-FR2-04: Single-language document is accepted

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | medium | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with exactly one variant (`de-CH`) and
   `fallback: "de-CH"`.

##### Expected Results

- Create succeeds; no minimum language count is enforced beyond the
  one-variant floor.

### FR-3: Standalone documents capability and read visibility

#### TC-FR3-01: Documents service provides full CRUD

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-1 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Start two `Documents/Create` requests for the same undocumented
   project at the same time.
2. Using the winning document, Get, List, Update, and Delete it through
   the `Documents` service methods.

##### Expected Results

- Exactly one create succeeds, stamps the typed owner branch, and links
  the project's `metadata.description` to the new document id.
- The losing create returns `AlreadyExists`; only one document row
  exists for the project.
- The remaining operations succeed; `Signal` returns `UNIMPLEMENTED`;
  List honors `offset`/`limit`/`filter` like other services.

#### TC-FR3-02: Tenant isolation on document reads

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- Tenant A and tenant B each own one document.

##### Steps

1. As a tenant-A user, call `Documents/List` and `Documents/Get` for
   tenant B's document id.

##### Expected Results

- List returns only tenant A's document; Get for tenant B's id returns
  `NotFound`.

#### TC-FR3-03: Platform-scoped documents follow catalog visibility

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A cluster template (platform-scoped) with a linked document.

##### Steps

1. As a tenant user, Get the document linked to the shared template.
2. As a tenant admin, attempt `Documents/Update` on it.

##### Expected Results

- The tenant user reads the document (shared visibility); the tenant
  admin's update returns `PermissionDenied` (platform-admin-only
  writes, matching template update rules).

#### TC-FR3-04: Document reads follow owner visibility

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- The caller can read Project A but not Project B.
- One document is linked to a Cluster in Project A, and one to a Cluster
  in Project B.
- The Project B document has the lower id, so it would occupy the first
  slot if pagination ran before visibility filtering.

##### Steps

1. As the caller, call `Documents/List` with `limit=1`.
2. Call `Documents/Get` for the Project B document.

##### Expected Results

- List returns the Project A document; the hidden Project B document
  does not consume the one-page slot.
- Get for the Project B document returns `NotFound`.

### FR-4: Documentation permission equals object update permission

#### TC-FR4-01: Project manager edits; project viewer cannot

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A project with a linked document; one manager and one viewer member.

##### Steps

1. As the manager, update the project's document.
2. As the viewer, attempt the same update.

##### Expected Results

- The manager's update succeeds; the viewer's update returns
  `PermissionDenied`.

#### TC-FR4-02: No description-only grant exists

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a custom role granting only read methods; bind a user; have
   them attempt `Documents/Update`.

##### Expected Results

- The update returns `PermissionDenied`; no role permission can name
  document mutation without the corresponding object-update grant set.

#### TC-FR4-03: Owner reference is immutable

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-13 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A cluster with a linked document; the caller can update the cluster.

##### Steps

1. Send `Documents/Update` with update-mask path `cluster.id`, attempting
   to change the owner.
2. Send `Documents/Update` without an update mask, carrying a changed
   `compute_instance` owner.
3. Get the document.

##### Expected Results

- The masked update returns `InvalidArgument`.
- The no-mask update succeeds, but the server restores the stored owner;
  the response and subsequent Get still show the original `cluster`
  owner and id.

### FR-5: Migration to und-tagged documents and field removal

#### TC-FR5-01: Every migrated description becomes an und document

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-10 | critical | automated (integration, migration test) | [DEV] |

##### Preconditions

- Pre-migration database rows with non-empty `title`/`description` on
  each of the 15 inventoried object types.

##### Steps

1. Run the backfill migration.
2. For each object type, Get one migrated object with `describe=true`.

##### Expected Results

- Each object's `metadata.description` resolves to a document whose
  only variant is keyed `und` and `spec.fallback = "und"`. For
  Markdown-documented sources the variant content is byte-identical
  to the original; for plain-text sources it is the CommonMark-escaped
  form (render-equality is asserted in TC-FR5-02).

#### TC-FR5-02: Plain-text sources render identically after migration

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-10 | critical | automated (unit, migration test) | [DEV] |

##### Preconditions

- A StorageTier row whose description is `# Warning: not a heading`
  and a ClusterTemplate row with genuine Markdown `_italic_`.

##### Steps

1. Run the migration; render both documents' `und` content.

##### Expected Results

- The StorageTier content renders as the literal text
  `# Warning: not a heading` (escaped); the template content renders
  `italic` emphasized — verbatim copy, no escaping.

#### TC-FR5-03: Removed fields absent from the public API

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-9 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get a migrated object through the public API.

##### Expected Results

- The response JSON contains no `title`/`description` string on the
  object's spec; the generated public types have no such fields.

#### TC-FR5-04: Grandfathered over-limit document accepts within-limit additions

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7, IC-10 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A migrated document whose `und` content exceeds 65,536 bytes.

##### Steps

1. Get the document (works).
2. Add a new `en-US` variant of 1,000 bytes via mask path.

##### Expected Results

- Get returns the over-limit content unchanged; the addition succeeds
  (only introduced content is limit-checked).

#### TC-FR5-05: und variant surfaces via fallback for any preference

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4, IC-10 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A migrated object (only an `und` variant, fallback `und`).

##### Steps

1. Get with `describe=true` and `Accept-Language: fr-FR`.

##### Expected Results

- The `und` variant is served with `served.reason = "FALLBACK"` and
  `served.tag = "und"`.

### FR-6: Preferred-language selection

#### TC-FR6-01: Exact match serves the requested variant

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get with `describe=true` and `Accept-Language: es-ES` on a document
   with `en-US` and `es-ES`.

##### Expected Results

- The `es-ES` variant is served; `served = {tag: "es-ES", reason:
  "MATCH"}`.

#### TC-FR6-02: Range truncation matches less-specific variant

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A document with only `fr`.

##### Steps

1. Get with `Accept-Language: fr-CA`.

##### Expected Results

- The `fr` variant is served with `reason: "MATCH"` (progressive
  truncation of the requested range).

#### TC-FR6-03: Quality values order the preference

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get with `Accept-Language: de;q=0.3, es;q=0.8` on a document with
   `de` and `es` variants.

##### Expected Results

- The `es` variant is served (highest weight first; no iteration past
  the top range).

#### TC-FR6-04: Both transports deliver the canonical metadata key

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-5 | high | automated (integration, it/ suite) | [DEV] |

##### Steps

1. Through the REST gateway, GET an object with `Accept-Language` and
   the describe flag.
2. Through the Connect proxy, issue the same call.

##### Expected Results

- Both paths serve the same variant; the server observed metadata key
  `accept-language` on both (verified by served-language outcome and a
  unit-level assertion on the canonical key).

### FR-7: Fallback and exclusions

#### TC-FR7-01: Missing language serves the single fallback with indication

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get with `Accept-Language: fr-FR` on a document with `en-US`,
   `es-ES`, fallback `en-US`.

##### Expected Results

- The `en-US` variant is served; `served = {tag: "en-US", reason:
  "FALLBACK"}`; the `es-ES` variant is not consulted (no list
  cascading).

#### TC-FR7-02: Explicitly excluded fallback yields no description

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get with `Accept-Language: fr, en;q=0` on the same document.
2. Get with `Accept-Language: fr, EN-US;q=0`.
3. Get with `Accept-Language: fr, EN;q=0`.

##### Expected Results

- Each object is returned with no description payload;
  `served.reason = "NONE"`; no error.
- The mixed-case `EN-US` exclusion is recognized as `en-US`.
- The broader `EN` exclusion also excludes the `en-US` fallback.

#### TC-FR7-03: Malformed header degrades to fallback

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | medium | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get with `Accept-Language: garbage;;; q=broken`.

##### Expected Results

- Unreadable entries are skipped; the fallback variant is served with
  `reason: "FALLBACK"`; the call succeeds.

### FR-8: Fallback integrity

#### TC-FR8-01: Fallback defaults to an English variant when omitted

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with `en-GB` and `es-ES`, omitting the optional
   `fallback`.

##### Expected Results

- The stored document has `spec.fallback = "en-GB"` (English-language
  default; persisted, not computed per read).

#### TC-FR8-02: No English variant requires an explicit fallback

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with only `ja` and `ko`, no `fallback`.

##### Expected Results

- Create returns `InvalidArgument` with a message requiring a fallback
  language; nothing is persisted.

#### TC-FR8-03: Dangling fallback rejected

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with `fallback: "pt-BR"` and variants `en`, `es`.

##### Expected Results

- Create returns `InvalidArgument` naming the dangling fallback.

#### TC-FR8-04: Fallback variant deletion requires same-update replacement

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Attempt to delete the `en-US` variant (the fallback) via mask path
   alone.
2. Attempt again, also setting `spec.fallback = "es-ES"` in the same
   update.

##### Expected Results

- The first update returns `InvalidArgument`; the second succeeds and
  the document's fallback is `es-ES` with the `en-US` variant gone.

#### TC-FR8-05: Deleting the last remaining variant is rejected

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6, IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A document with a single `en-US` variant that is also the fallback.

##### Steps

1. Attempt to delete `en-US` via mask path (no other variants exist).
2. Delete the document through `Documents/Delete` instead; Get the
   owning object with `describe=true`.

##### Expected Results

- The variant deletion returns `InvalidArgument` (no valid end state:
  one-variant floor and fallback integrity); the document deletion
  succeeds; the object returns with no description and
  `served.reason = "NONE"`.

### FR-9: Opt-in retrieval

#### TC-FR9-01: Without the flag, responses are unchanged

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get and List objects with documented descriptions, without the
   describe flag.

##### Expected Results

- Responses match the target preview-schema baseline: legacy
  `title`/`description` fields absent (removed by IC-9),
  `metadata.description` present on documented objects, and no
  `description`/`descriptions`/`served` fields (proto3 JSON omits
  unset optionals; no document queries issued without the flag).

#### TC-FR9-02: With the flag, Get and List carry documentation

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. List three objects (two documented) with the describe flag and an
   `Accept-Language`.

##### Expected Results

- Get returns `description` + `served`; List's `descriptions` map has
   exactly two entries keyed by the objects' `metadata.description`
   ids; the undocumented object contributes no entry.

### FR-10: Cascade deletion

#### TC-FR10-01: Object deletion removes its document

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-8 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Delete a documented object (no finalizers).

##### Expected Results

- The Delete response returns the object; a subsequent
  `Documents/Get` for the linked id returns `NotFound`; both the
  object and document rows moved to their archived tables in one
  transaction.

#### TC-FR10-02: Soft-deleted objects keep documentation until final

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-8 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- An object type whose deletion is finalizer-gated.

##### Steps

1. Delete the object; while finalizers are pending, Get it with
   `describe=true`.

##### Expected Results

- The description is still served; after the finalizer clears and
   deletion completes, the document is gone.

#### TC-FR10-03: Standalone delete clears the link and allows replacement

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-8, IC-4 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Delete a document through the standalone service while its object
   remains.
2. Get the object with `describe=true`.
3. Create a replacement document for the same object through
   `Documents/Create`.

##### Expected Results

- The first Get returns the object normally with no description and
  `served.reason = "NONE"`.
- The owner's `metadata.description` link is unset after deletion.
- The replacement Create succeeds and links the new document id.

### FR-11: CLI support

#### TC-FR11-01: describe renders Markdown and served language

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-11 | high | automated (integration, it/ suite) | [DEV] |

##### Steps

1. Run `osac describe cluster <name>` for a documented cluster with
   the language preference set.

##### Expected Results

- The description section renders the served variant's Markdown
  through glamour and prints the served language and match/fallback
  reason.

#### TC-FR11-02: Document resource commands, structured output, and edit round-trip

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-11 | high | automated (integration, it/ suite) | [DEV] |

##### Steps

1. Run `osac get documents`, `osac get document <name> -o yaml`, and
   `osac edit document <name>` (add one variant).
2. Run `osac get <object> --descriptions -o json` and without the
   flag.

##### Expected Results

- All commands succeed; the edited variant appears; the flagged JSON
   output contains the Markdown source and `served` as structured data
   (unrendered); the unflagged output matches the target
   preview-schema baseline (legacy fields removed, `metadata.
   description` present on documented objects, no description
   payload).

#### TC-FR11-03: Editor block deletion and stale-edit protection

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-6, IC-11 | critical | automated (integration, it/ suite) | [DEV] |

##### Preconditions

- A document with `en-US` (fallback) and `es-ES` variants.

##### Steps

1. `osac edit document <name>`: remove the `es-ES` block from the YAML
   and save.
2. Repeat with a concurrent change: edit, then before saving, update
   the document through the API; then save.

##### Expected Results

- Step 1 deletes the `es-ES` variant (full-view diff semantics);
   `en-US` remains.
- Step 2 fails with `Aborted` (stale `metadata.version`, `lock=true`
   sent by the CLI); nothing is overwritten; a retry after re-fetch
   succeeds.

### FR-12: Console surfaces

#### TC-FR12-01: Detail page renders description with fallback indication

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | high | automated (Vitest, component) | [DEV] |

##### Steps

1. Render the catalog-item detail page with a document whose served
   variant is a fallback.

##### Expected Results

- The Markdown renders inside PatternFly Content; a visible indication
   names the served language and that the preferred one is unavailable.

#### TC-FR12-02: Variant management in create and edit flows

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | high | automated (Vitest, component) | [DEV] |

##### Steps

1. In the create flow, add two language variants with titles and
   content; submit.
2. In the edit flow, add a third variant.

##### Expected Results

- The create request carries the embedded document; the edit sends a
   per-language update; the UI shows all variants.

#### TC-FR12-03: List views show plain-text summaries

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | medium | automated (Vitest, component) | [DEV] |

##### Steps

1. Render a list page with documented objects whose content contains
   Markdown syntax (`#`, `**`).

##### Expected Results

- Rows show plain-text summaries (syntax stripped, truncated), not
   rendered or raw Markdown.

### FR-13: Content format

#### TC-FR13-01: Content round-trips as authored

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-3 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with content containing unusual but valid
   CommonMark; Get it back.

##### Expected Results

- The stored and returned `content` is byte-identical to the input;
   no normalization, reflow, or sanitization at rest.

#### TC-FR13-02: Titles render as plain text

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | medium | automated (Vitest, component) | [DEV] |

##### Steps

1. Render a document whose title is `# not a heading **bold**`.

##### Expected Results

- The title displays the literal characters; no Markdown
   interpretation in the title element.

### FR-14: Validation and limits

#### TC-FR14-01: Invalid and unregistered tags rejected with named cause

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create documents with variant keys `en_US`, `english`, and `xx`,
   in turn.

##### Expected Results

- Each returns `InvalidArgument`; messages name the offending value
  (`en_US` — underscore; `english` — not registered; `xx` — unknown
  subtag).

#### TC-FR14-02: Canonical case collisions rejected

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with variants `en-US` and `en-us`.

##### Expected Results

- `InvalidArgument` reporting the duplicate canonical tag `en-US`.

#### TC-FR14-03: Variant-count boundary enforced both sides

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document with 32 variants.
2. Add a 33rd via mask path.

##### Expected Results

- 32 variants are accepted; the 33rd returns `InvalidArgument` citing
  the map pair limit.

#### TC-FR14-04: Per-variant content boundary enforced, never truncated

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | critical | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a variant with exactly 65,536 bytes of content.
2. Create one with 65,537 bytes.

##### Expected Results

- The boundary value is stored intact; 65,537 returns
  `InvalidArgument`; no stored content is ever truncated (verify the
   accepted case is byte-identical).

#### TC-FR14-05: Aggregate document boundary enforced

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a document whose combined keys, titles, content, **and
   fallback** total exactly 1,048,576 bytes (the fallback's bytes
   count toward the aggregate).
2. Add content pushing the total to 1,048,577 via an update.

##### Expected Results

- The boundary total is accepted; the over-boundary update returns
  `InvalidArgument` citing the aggregate limit.

#### TC-FR14-06: Title length and empty documents rejected

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-7 | medium | automated (unit, servers suite) | [DEV] |

##### Steps

1. Create a variant with a 257-character title.
2. Create a document with zero variants.

##### Expected Results

- Both return `InvalidArgument` (title length; empty document).

### NFR-1: Missing translation never fails retrieval

#### TC-NFR1-01: Malformed Accept-Language does not fail the call

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Get objects with `describe=true` and several malformed
   `Accept-Language` values (empty, junk, bad weights).

##### Expected Results

- Every call returns the object (HTTP 200 / OK) with either the
  fallback variant or no description; no 4xx/5xx originates from
  language handling.

#### TC-NFR1-02: Dangling reference does not fail the call

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-8 | high | automated (unit, servers suite) | [DEV] |

##### Preconditions

- A test fixture simulates a legacy/corrupted dangling reference by
  setting an object's `metadata.description` to a nonexistent document.
  Normal standalone deletion is covered by TC-FR10-03.

##### Steps

1. Get the object with `describe=true`.

##### Expected Results

- The object returns normally with `served.reason = "NONE"`.

### NFR-2: Safe rendering

#### TC-NFR2-01: Script content renders inert

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | critical | automated (Vitest, component) | [DEV] |

##### Steps

1. Render content containing `<script>alert(1)</script>` and an
   `onerror`-carrying image tag.

##### Expected Results

- No script element exists in the rendered DOM; the markup appears as
   escaped text or is stripped; no alert fires.

#### TC-NFR2-02: Dangerous URL schemes neutralized

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | critical | automated (Vitest, component) | [DEV] |

##### Steps

1. Render links and images with `javascript:` and `data:` URLs.

##### Expected Results

- Rendered anchors/images carry no `javascript:` or `data:` href/src;
   the URL transform allow-list (http/https/mailto and relatives)
   governs.

#### TC-NFR2-03: Preview policy equals saved-render policy

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-12 | high | automated (Vitest, component) | [DEV] |

##### Steps

1. Render the same malicious payload through the editor preview and
   the saved-description view.

##### Expected Results

- Both outputs are identical (same shared component, same plugin
   list); neither executes content.

### NFR-3: Standards conformance

#### TC-NFR3-01: RFC 4647 lookup examples verified

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-5 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. Run the selection function against the RFC 4647 §3.4 examples
   (progressive truncation chain
   `zh-Hant-CN-x-private1-private2` → … → default) and the §2
   case-insensitivity rule.

##### Expected Results

- Outputs match the RFC's documented results exactly, including
   default selection when nothing matches.

#### TC-NFR3-02: Matching is case-insensitive end to end

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4, IC-5 | medium | automated (unit, servers suite) | [DEV] |

##### Steps

1. Request with `accept-language: ES-es` against a stored `es-ES`.

##### Expected Results

- The `es-ES` variant is served with `reason: "MATCH"`.

### NFR-4: No overhead without the flag

#### TC-NFR4-01: Undescribed retrieval issues no document queries

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-4 | high | automated (unit, servers suite) | [DEV] |

##### Steps

1. List documented objects without the describe flag, with the DAO
   query log captured.

##### Expected Results

- No query touches the `documents` table; response payload contains
   no description fields.

### E2E journeys ([QE], tests/e2e/)

#### TC-E2E-01: The PRD acceptance scenarios through console and CLI

| Interface Change | Priority | Automation | Owner |
|-----------------|----------|------------|-------|
| IC-3, IC-4, IC-6, IC-11, IC-12 | critical | automated (E2E) | [QE] |

##### Steps

1. As an admin, create an object with English documentation; later add
   Spanish.
2. As a Spanish-preferring viewer, view it (console and CLI).
3. As a French-preferring viewer, view it.
4. Delete the object.

##### Expected Results

- Both languages coexist; the Spanish viewer sees Spanish; the French
  viewer sees the English fallback with an indication; deletion
  removes the documentation (PRD acceptance criteria 1–3, 5).

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 59 |
| Critical | 28 |
| High | 25 |
| Medium | 6 |
| Low | 0 |
| Automated | 59 |
| Manual | 0 |
| Requirements with test cases | 18 / 18 |
| Interface changes with test cases | 13 / 13 |

Visual verification of console rendering (layout, truncation
aesthetics, indication prominence) additionally benefits from a manual
pass during Dev Preview; it is not a test-plan row because the
behavioral assertions above are component-testable.
