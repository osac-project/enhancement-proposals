# Internationalized Object Descriptions

| Field       | Value |
|-------------|-------|
| Author(s)   | Shirel Bar Lev |
| Jira        | [OSAC-4047](https://redhat.atlassian.net/browse/OSAC-4047) |
| Date        | 2026-11-12 |

## 1. Problem Statement

OSAC object documentation (`title` and `description` fields) is stored as
single plain-text strings with no internationalization support. A global
audience uses OSAC, but an author who writes a description in one language
forces every viewer to read it in that language — a viewer cannot see the
description in their own language, and an author cannot provide
translations. The situation is also inconsistent: some object types have
title and description fields, others have none. Without this work, OSAC
cannot serve multilingual tenants, and the per-object-type inconsistency
remains permanent.

## 2. Goals and Non-Goals

### 2.1 Goals

- Users can document any OSAC object in multiple languages, and each
  viewer sees the documentation in their preferred language.
- Every object type offers the same documentation capability, replacing
  today's inconsistent mix of plain-string fields.
- Viewers always receive useful documentation: their preferred language
  when available, otherwise a clearly indicated fallback.
- Existing plain-string descriptions keep working, appearing as
  single-language documents after migration.

### 2.2 Non-Goals

- Machine or server-side translation — the system stores translations
  users provide; it does not produce them. [Clarify: R2.Q4]
- Translation of system-generated content such as status messages and
  errors — only user-authored documentation is multilingual. [Clarify:
  R2.Q4]
- Translation of the console UI itself (UI chrome) — a separate concern
  from object documentation. [Clarify: R2.Q4]

## 3. Requirements

### 3.1 Functional Requirements

#### Authoring

- **FR-1:** Users who can update an object can provide documentation for
  it in one or more languages when creating the object; the object and its
  documentation are created together or not at all.
- **FR-2:** Users can add, replace, or delete a single language variant of
  an object's documentation without resending or affecting the other
  languages; deleting a language requires an explicit action (omitting it
  from an update does not delete it). Authors provide only the languages
  they choose — no minimum set of languages is required. [Clarify: R1.Q5]
- **FR-3:** Users can manage documentation independently of the objects it
  describes, via a standalone documents capability (create, view, list,
  update, delete).
- **FR-4:** Editing an object's documentation requires the same permission
  as updating the object itself; no separate documentation-only or
  translation-specific permission is introduced. [Clarify: R2.Q1]
- **FR-5:** Users can document every OSAC object type, and the existing
  plain-string title/description fields are replaced by documents — after
  migration no object type keeps its old plain-string fields. [Clarify:
  R1.Q1]

#### Language selection

- **FR-6:** Each viewer sees an object's documentation in their preferred
  language, expressed with standard language-preference semantics
  (equivalent to `Accept-Language`, including quality values and
  precedence).
- **FR-7:** When the viewer's preferred language is not available, they
  see the document's single fallback language, and the response identifies
  which language was actually served and why (match or fallback), so the
  console can indicate "French unavailable — showing {fallback}". No
  cascading through the rest of the viewer's preference list. [Clarify:
  R1.Q4]
- **FR-8:** Every document has a valid fallback language. When the author
  does not choose one, it defaults to English if an English variant
  exists; otherwise the author must name one. A fallback pointing at a
  language that does not exist in the document is rejected, and the
  fallback variant cannot be deleted unless the same update names a valid fallback variant
  replacement. Authors may explicitly choose a non-English fallback.
  [Clarify: R1.Q4]

#### Retrieval and lifecycle

- **FR-9:** Users receive documentation only when they explicitly request
  it (for example, a flag on the view/list request); by default object
  retrieval omits documentation. This applies to the API, CLI, and console.
  [Clarify: R1.Q2]
- **FR-10:** Deleting an object also deletes its documentation; the
  documentation never outlives its object.

#### Interfaces

- **FR-11:** CLI users can view and manage object documentation: request
  descriptions on view and list operations, add or edit language variants,
  and see which language was served.
- **FR-12:** Console users see rendered documentation on the surfaces that
  show titles and descriptions today (catalog items, instance types,
  storage tiers and backends, identity providers, projects, roles), with
  per-user language selection and fallback indication, and can manage
  language variants in the create and edit flows. [Clarify: R1.Q3]

#### Format and validation

- **FR-13:** Documentation content is written in Markdown (CommonMark
  dialect) and stored as authored; titles are plain text. [Clarify: R2.Q2]
- **FR-14:** Users get clear errors when input is invalid: malformed or
  unregistered language tags (e.g., `en_US`, `english`), oversized content,
  a fallback naming a missing language, or an empty document. Limits: 1–32
  languages per document, at most 65,536 bytes of content per language,
  at most 1,048,576 bytes per document, and titles of at most 256
  characters. Over-limit input is rejected, never truncated. [Clarify:
  R2.Q2]

### 3.2 Non-Functional Requirements

- **NFR-1:** A missing translation never fails object retrieval — the
  viewer always receives the object with fallback documentation. [Clarify:
  R1.Q4]
- **NFR-2:** Console rendering of user-authored documentation is safe:
  documentation cannot execute scripts, embed raw HTML, or carry dangerous
  link schemes when displayed, and previews use the same safety policy as
  saved descriptions. [Clarify: R2.Q2]
- **NFR-3:** Language-preference matching follows the published
  language-tag standards (RFC 5646 for tags, RFC 4647 for matching), so
  clients behave predictably across the API, CLI, and console.
- **NFR-4:** Users who do not request documentation experience object
  retrieval unchanged from today — no documentation payload and no added
  retrieval overhead. [Clarify: R1.Q2]

## 4. Acceptance Criteria

- [ ] An author creates an object with an English description and later
  adds a Spanish variant; both languages coexist on the object. [Clarify:
  R2.Q3]
- [ ] A Spanish-preferring viewer who requests documentation sees the
  Spanish variant. [Clarify: R2.Q3]
- [ ] A French-preferring viewer sees the English fallback, with an
  indication that French is unavailable. [Clarify: R2.Q3]
- [ ] After migration, an existing object's plain-string description
  appears as a single-language document, on every object type that had
  description fields. [Clarify: R2.Q3]
- [ ] Deleting an object removes its documentation. [Clarify: R2.Q3]

## 5. Dependencies

- The `osac-ui` implementation is owned by the UI team; the console work
  in FR-12 is delivered in coordination with (or handed to) them. [Clarify:
  R1.Q3]
- The documentation API and service capabilities must be available before
  the CLI and console work that consumes them.

## 6. Risks

### 6.1 Unsafe rendering of user-authored Markdown

Documentation is entered by users and displayed in other users' browsers;
a rendering flaw would let one user attack viewers.

- **Owner:** OSAC-Core
- **Mitigation:** Allow-list rendering policy (no raw HTML or scripts,
  restricted link schemes), identical policy for previews and saved
  descriptions, and rendering-security acceptance tests. [Clarify: R2.Q2]

### 6.2 Migration breadth across every object type

Replacing plain-string fields on all object types touches a large surface;
a failed migration could lose or corrupt existing descriptions.

- **Owner:** OSAC-Core
- **Mitigation:** Migration is an acceptance criterion (single-language
  documents verified per object type after migration). [Clarify: R2.Q3]

---

## Provenance

Authored: draft @ prd - unknown (shared workflow recipes unavailable), workspace OSAC-2800 @ 9b2ee397ab
Final: draft @ prd - unknown (shared workflow recipes unavailable), workspace OSAC-2800 @ 9b2ee397ab
Phases: draft

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","ai_workflows":"unknown (shared workflow recipes unavailable)","source_repo":"9b2ee397ab","source_repo_branch":"OSAC-2800","phases":["draft"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
