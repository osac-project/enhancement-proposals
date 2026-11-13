# Clarification Log — OSAC-4047

## Status

- Rounds completed: 2
- Open gaps: none — proto field naming inconsistencies (`fallback` vs.
  `Default`, variant `description` vs. `content`) are deferred to the
  design phase as naming choices, not requirement gaps
- Exit criteria met: Yes

### Exit criteria check

- Functional requirements enumerable: Yes — coverage (D1), retrieval
  opt-in (D2), UI (D3), per-language updates (D4), fallback behavior
  (D5), authorization (D8), limits and validation (D9)
- Target users/personas identified: Yes — authors are users with
  object-update permission (admins for catalog objects, project managers
  for projects); viewers are any users with read access, with per-viewer
  language selection
- Scope boundaries clear: Yes — goals per D1/D2/D3; non-goals per D7
- No unresolved contradictions: Yes — the issue's open question resolved
  by D2; fallback semantics resolved by D5; remaining naming
  inconsistencies are design-phase choices
- Key assumptions confirmed: Yes — current description behavior (single
  free-text string, no i18n) verified by research
- Non-functional requirements enumerable: Yes — D9's specific limits,
  validation, and rendering-safety constraints
- Dependencies identified: Yes — `osac-ui` implementation owned by the
  UI team (D3); data migration of existing fields (D1); RFC 5646/4647
  and Accept-Language semantics as normative references

## Round 1 — Scope, consumers, and default behavior

### R1.Q1: Object type coverage and migration of existing description fields

Which object types are in scope for `metadata.description` — literally every
API object type? And what happens to the existing plain-string
`title`/`description` fields on types that already have them?

#### Answer

All objects, including the objects that already have plain-string
`title`/`description` fields, will be migrated to `Document` objects. In the
end all existing objects will use `Document` objects for descriptions.

#### Impact

The PRD scope must include migration of existing plain-string description
fields into `Document` objects (data migration, not just new-field support).
"All object types" is the coverage boundary.

#### Decision (D1)

All API object types get `metadata.description` backed by `Document`
objects; existing plain-string `title`/`description` fields are migrated to
`Document` objects and no object type retains its old plain-string fields.

---

### R1.Q2: Default fetch behavior for Get/List descriptions

Should Get and List return descriptions by default, or only when the user
explicitly requests them (e.g., a `describe` flag)? The issue leans toward
"not by default" for performance, but flagged it as an open question.

#### Answer

Users should see the description only with an extra flag — descriptions are
not returned by default.

#### Impact

Resolves the issue's open question. The PRD specifies opt-in description
retrieval for Get and List; the default behavior omits descriptions.

#### Decision (D2)

Descriptions are fetched only on explicit request (e.g., a `describe`
flag); Get and List do not include descriptions by default.

---

### R1.Q3: Interface coverage — console (osac-ui) exposure

Who are the primary consumers of descriptions — console users, CLI users,
API consumers? Is console exposure part of this feature's value or separate
UI-team work?

#### Answer

(Research result, chai persona, verified against the current `osac-ui`
source in-tree.)

Descriptions and titles are displayed in the UI today, but concentrated in
**catalog and infrastructure-definition objects, not provisioned
instances**:

- **Shown today:**
  - Catalog items (cluster, VM, bare metal): top-level `description` shown
    below the detail-page heading; also an input in the shared create/edit
    form. Not shown in list tables/cards.
  - VM instance types: `spec.description` shown under the name in list
    rows/cards and on detail pages.
  - Bare-metal instance types: `spec.description` on detail pages
    (explicit Description row) and in provisioning options.
  - Storage tiers and storage backends: `spec.description` as an explicit
    Description field on detail pages.
  - Identity providers: `spec.title` as display name in lists;
    `spec.title` and `spec.description` in the create/edit wizard and
    review step.
  - Projects: `spec.title` used as display name (list Name column, detail
    heading/breadcrumbs); description not rendered.
  - Roles: referenced role's `spec.title` shown in role bindings.
- **Not shown:** clusters, VMs/compute instances, volumes, virtual
  networks, bare-metal instances, disk images, tenants, external IPs/IP
  pools, security groups, secrets (no object description/title rendered in
  the inspected list/detail views).

#### Impact

The PRD includes UI deliverables: rendering descriptions from `Document`
objects (with language selection) and managing language variants in the
create/edit flows on the surfaces identified above. Per project convention,
`osac-ui` implementation is owned by the UI team, so UI work is in scope as
a deliverable coordinated with (or handed to) the UI team rather than
backend-PR side changes.

#### Decision (D3)

UI work is in scope for OSAC-4047: the console renders and manages
multilingual descriptions from `Document` objects, starting with the
existing description/title surfaces (catalog items, instance types,
storage tiers/backends, identity providers, projects, roles).

---

### R1.Q4: Existing behavior for descriptions in foreign languages

How do description fields currently behave — plain free text? Any existing
i18n, translation, or language-tagging support?

#### Answer

(Research result, chai persona, verified against current proto/CLI sources.)

- Descriptions today are single free-text strings, not multilingual
  documents. Non-English text (Spanish, French, including accented
  characters) works because the fields are UTF-8 protobuf strings — no
  language tag required.
- Some fields are plain strings (e.g., `Project.spec.description` is an
  `optional string`); some explicitly support Markdown (e.g.,
  `ClusterTemplate.description`).
- Editing an existing object's description is an ordinary field update —
  the Projects update API supports selecting `spec.description` with an
  update mask; the CLI `edit` flow edits the object as YAML/JSON and sends
  it back. There is no notion of "adding a translation."
- No built-in translation, language-tagged variants, or variant selection
  exists today. `Document` objects, BCP 47 tags, `Accept-Language`
  selection, and fallback behavior are all proposed by OSAC-4047, not
  existing behavior.

#### Impact

Establishes the baseline: today a user gets exactly one description string
in whichever language they typed, and every viewer sees that same string.
The new capability's value is multiple language variants per object with
per-viewer selection. The original user-facing question — what a viewer
experiences when their requested language has no variant (silent fallback
vs. indication vs. error), and whether a fallback language is required at
create time — remains open for the user to decide, now informed by this
baseline.

##### Follow-up: fallback behavior decision (recommendation research)

Chai research recommended: serve the fallback variant (never error, never
mislabel), RFC 4647 lookup/best-match across the preference list,
observable fallback via selection metadata, valid-fallback rules with
English default, and errors kept exceptional. Precedents: OpenShift and
ACM consoles fall back to English for UI strings; Quay has no multilingual
descriptions; RFC 4647/9110 leave no-match behavior to the application.

The user decided to adopt the recommendation **except** the
best-match/lookup refinement: there is a single fallback only — if the
requested language is not available, the server goes directly to the
fallback language.

#### Decision (D5)

Fallback behavior for missing language variants:

- If the requested language has no variant, serve the document's single
  fallback language. No cascading through the rest of the viewer's
  preference list.
- The fallback is observable: the response identifies the language
  actually served and why (match vs. fallback), so the UI can indicate
  "French unavailable — showing {fallback}."
- A document must always have a valid fallback: if omitted at create,
  default to `en-US` only if that variant exists; otherwise the author
  must name one. A nonexistent fallback is rejected; the fallback variant
  cannot be deleted unless the same update supplies a valid replacement.
- English is the product default, but tenant authors may explicitly choose
  a non-English fallback.
- A missing translation never fails the underlying object Get/List;
  explicit language exclusions are honored.

---

---

### R1.Q5: Partial vs. full replacement on document update

When updating a document, can a user add or replace a single language
variant without resending the whole variants map, or is update always full
replacement?

#### Answer

Partial update: a user sends just the new variant (e.g., French) and it is
added alongside the untouched existing variants.

#### Impact

The PRD's update capability is per-language: adding or replacing one
variant must not require resending the others and must not risk clobbering
concurrent edits to them. Omission of a variant in an update must not
delete it, so the API needs an explicit way to delete a variant.

#### Decision (D4)

Document updates are partial/per-language: sending a single language
variant adds or replaces only that variant; other variants are left
untouched. Variant deletion requires an explicit operation (omission does
not delete).

---

## Round 2 — Authorization, limits, acceptance, non-goals

### R2.Q1: Authorization — who may edit a document

Is editing an object's description governed by the same permissions as
editing the object itself, or separately controllable (e.g., a translator
who can add Spanish variants but cannot touch the object's spec)?

#### Answer

(Research result, chai persona, verified against the current
`osac-project/osac` implementation — `authz.rego`, authorization
interceptor, generic update handler.)

Today, description/title edits use the object's normal `Update`
authorization — there is no separate field-level permission:

- **Authorization is method-level:** the caller must be allowed the
  object's `Update` operation (e.g., `Projects/Update`) plus applicable
  tenant/project scoping. The `update_mask` selects what changes; it does
  not grant permission.
- **Who can edit, per object type:**
  - Projects (`spec.title`/`spec.description`): the project's managers,
    tenant-admins, or platform admins. Viewers cannot.
  - Cluster templates (`title`/`description`): platform admins only —
    tenant-admins get read-only access.
  - Instance types (`spec.description`): platform admins.
  - Storage tiers (`spec.description`): platform admins via the private
    `StorageTiers/Update` API (public API is read-only).
  - Identity providers (`spec.title`/`spec.description`): tenant-admin or
    `tenant-idp-manager` within the tenant, plus platform admins — the
    same grant as configuration changes, not a weaker "edit text" grant.
- **Role permissions are service/method-granular, not field-granular:**
  `RoleSpec.permissions` names services and methods; there is no
  description-only or field-path grant today. Reader roles don't confer
  update access; `metadata.creator` is informational, not an
  only-creator-may-edit rule.
- Field validation/immutability still applies after authorization, but for
  the mutable description/title fields there is no additional
  description-specific authorization check.

**Bottom line:** "can update this object here" already includes "can
update its mutable description/title."

The open decision: keep this model for `Document` edits (same permission
as the linked object), or introduce a separate translation-oriented grant.

The user chose to keep the current model.

#### Impact

The PRD's authorization requirement for Document edits is the existing
object-update permission; no new field-level or translation-specific
grant is introduced.

#### Decision (D8)

Editing an object's linked document requires the same permission as
updating the object itself (method-level authorization plus tenant/project
scoping, exactly as object updates work today). No separate
description-only or translation role is added.

---

### R2.Q2: Limits and validation

Should the PRD set limits — max variants per document, max content size
per variant, Markdown as the required format, BCP 47 tag validation at
submission, rejection of a fallback pointing at a nonexistent variant — or
leave these as design-phase decisions?

#### Answer

(Recommendation research, chai persona, checked against RFC 5646/IANA,
Kubernetes/Quay/Strapi/Sanity precedents, and current OSAC validation
code.)

Proposed OSAC policy (starting points, deliberately chosen — no industry
standard exists for these numbers):

- **Variant count:** 1–32 variants per document; an object without
  documentation omits the reference rather than creating an empty
  document. Ceiling can be raised later.
- **Content size:** at most 65,536 UTF-8 bytes of Markdown per variant —
  reject over-limit input, never truncate. (64 KiB matches an existing
  OSAC precedent: bare-metal inline user data is byte-limited at 64 KiB
  across backend, Secret validator, and console.)
- **Aggregate budget:** at most 1,048,576 UTF-8 bytes across the whole
  document (keys, titles, content, fallback) — prevents 32 × 64 KiB
  payloads. Separate from request/response size limits.
- **Title:** at most 256 Unicode code points, plain text, single line. A
  variant may be title-only or content-only, but not both-blank.
- **Markdown:** `content` is Markdown (CommonMark dialect, extensions
  listed explicitly); store original Markdown, never pre-rendered or
  destructively sanitized text. Rendering contract: disable raw
  HTML/scripts/executable components; allow-list elements, attributes,
  and URL schemes (reject `javascript:`, `data:`); sanitize after any
  plugins; same policy for previews and saved descriptions (react-markdown
  + rehype-sanitize guidance).
- **Language-tag validation on every write:** validate RFC 5646 syntax
  *and* registered subtags (`english` is syntactically valid but
  unregistered — reject it, suggest `en`); reject `en_US`, whitespace,
  empty keys, and `*`; canonicalize case, reject collisions
  (`en-US` + `en-us`); 255-byte tag ceiling as an application safeguard.
  Go pitfall noted: `golang.org/x/text/language` accepts underscores, so
  strict syntax must be prechecked.
- **Fallback integrity:** reject a fallback that does not identify an
  existing variant after canonicalization (no language-matching excuses);
  require a persisted nonempty fallback; validate the complete merged
  document, not just the partial update; fit OSAC's existing
  post-update-mask validation pattern.
- **Comparable systems:** Kubernetes has aggregate byte budgets (256 KiB
  annotations, 1 MiB ConfigMap/Secret data) but no language-count limit;
  Quay has a single Markdown description string; Strapi uses configurable
  locales from a predefined list; Sanity distinguishes document size
  (32 MB) from request size (4 MB). No common "32 languages / 64 KiB"
  standard — these are OSAC starting points.
- **Current OSAC state:** names have proto length/pattern rules;
  annotations have no explicit budget; existing title/description strings
  are unannotated (`ProjectSpec.description`'s "Maximum length: 1024
  characters" is a comment, not an enforced rule); 64 KiB user-data limit
  is the one concrete per-string precedent.
- **Acceptance tests should include** exact-limit and limit-plus-one
  inputs, multibyte text, the 33rd variant, canonical-key collisions,
  `english`, `en_US`, dangling fallback, fallback removal/replacement, and
  console rendering of script/HTML/unsafe-link payloads. API validation
  and rendering safety are both acceptance criteria.

#### Impact

Determines which input-validation and limit requirements appear in the
PRD vs. being deferred to design. If adopted, the PRD names the limits as
product requirements with the specific values, plus Markdown storage and
safe-rendering requirements on the console.

#### Decision (D9)

Adopt the recommended limits and validation as PRD requirements:

- 1–32 variants per document; no empty documents (omit the reference
  instead).
- At most 65,536 UTF-8 bytes of Markdown content per variant; at most
  1,048,576 UTF-8 bytes aggregate per document; over-limit input is
  rejected, never truncated. Titles at most 256 Unicode code points,
  plain text, single line; a variant may be title-only or content-only
  but not both-blank. Numbers are starting points, tunable with
  justification.
- `content` is Markdown (CommonMark dialect, extensions listed
  explicitly); original Markdown is stored. Console rendering disables
  raw HTML/scripts/executable components and allow-lists elements,
  attributes, and URL schemes (rejecting `javascript:`, `data:`), with
  the same policy for previews and saved descriptions.
- Language tags are validated on every write: RFC 5646 syntax and
  registered subtags (reject `english`, `en_US`, whitespace, empty, `*`);
  case canonicalized with collision rejection; 255-byte tag ceiling.
- Fallback must identify an existing variant after canonicalization; the
  complete merged document is validated on every write.
- API validation and safe rendering are both acceptance criteria, with
  tests for exact-limit/limit-plus-one, the 33rd variant, canonical-key
  collisions, invalid tags, dangling fallback, fallback
  removal/replacement, and malicious rendering payloads.

---

### R2.Q3: Acceptance criteria — what "done" looks like

The issue has no Definition of Done. Proposed user-observable acceptance
criteria: (a) an author creates an object with an English description,
later adds Spanish; (b) a Spanish-preferring viewer sees Spanish when
descriptions are requested; (c) a French-preferring viewer sees the
English fallback with an indication; (d) existing objects' plain-string
descriptions appear as single-variant Documents after migration; (e)
deleting the object deletes its document.

#### Answer

The proposed criteria match the user's intent.

#### Impact

The PRD defines user-observable acceptance criteria based on scenarios
(a)–(e); CLI- and UI-specific scenarios may be added during drafting as
elaborations of these.

#### Decision (D6)

Acceptance criteria for OSAC-4047 are the user-observable scenarios:
author adds a language over time; viewer sees their language when
requested; viewer sees an indicated fallback when their language is
missing; migrated objects appear as single-variant Documents; object
deletion cascades to its document.

---

### R2.Q4: Non-goals

Should the PRD explicitly declare out of scope: machine/server-side
translation, translation of system-generated content (status messages,
errors), and translation of the UI itself (console chrome)?

#### Answer

Yes — add these as non-goals.

#### Impact

The PRD's non-goals section lists: machine/server-side translation (the
system stores translations, it does not produce them); translation of
system-generated content; and translation of the console UI itself.

#### Decision (D7)

Non-goals for OSAC-4047: no machine/server-side translation; no
translation of system-generated content (status, errors); no translation
of the UI chrome itself.

---

## Remaining Gaps

- R2.Q1 (authorization model) — awaiting research result
- R2.Q2 (limits and validation) — awaiting recommendation research
