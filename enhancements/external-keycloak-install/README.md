---
title: external-keycloak-install
authors:
  - obochan@redhat.com
creation-date: 2026-11-18
last-updated: 2026-11-18
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-7920
see-also:
  - "/enhancements/organizations"
---

# External Keycloak Install Support

Make a fresh OSAC install with an external Keycloak work without manual
cluster surgery, and correct the external services guide where it describes
this path incorrectly today.

## Summary

OSAC supports running Keycloak outside the cluster, but only on paper. The
credential machinery that feeds the `osac` release — the hooks and prereq
templates that create `fulfillment-controller-credentials` and
`osac-ui-backend-credentials` — is gated on `keycloak.enabled`, the same flag
that turns off the bundled instance. Setting the flag to `false` for an
external Keycloak therefore removes the Secrets the application still
consumes. The UI deployment references `osac-ui-backend-credentials` with a
hard, non-optional `secretKeyRef`, so a fresh install following the current
guide leaves the UI pod in `CreateContainerConfigError`. This proposal
separates "where Keycloak runs" from "how the application gets its client
credentials": the osac chart gains a documented value for the UI backend
credential Secret, install-time validation fails fast when the flag is off
and no Secret is provided, and the external services guide is corrected to
match.

## Motivation

The external services support guide (OSAC-6102, in the osac mono-repo under
`docs/guides/installation/external-services-support-guide.md`) documents
running PostgreSQL, OpenBao, Keycloak, and Kafka outside the cluster. Its
Keycloak section tells the reader to set `keycloak.enabled: false`, point
every consumer at the external issuer, and create two Secrets by hand:
`fulfillment-controller-credentials` and `vault-credentials`.

That instruction is incomplete. The UI subchart defaults
`auth.serviceAccount.credentialsSecret` to `osac-ui-backend-credentials`, the
`osac` chart's values never override it, and the UI deployment reads that
Secret through a `secretKeyRef` that is not optional
(`osac-ui/charts/ui/templates/deployment.yaml:48-56`). The only templates
that create the Secret —
`osac-installer/charts/osac-infra/templates/osac-ui-backend-credentials-prereqs.yaml`
and the `create-ui-backend-credentials` hook — are wrapped in
`{{- if .Values.keycloak.enabled }}`. With the flag off, nothing creates it.

The guide makes this worse by claiming the opposite. Section 5.2, row 10 of
the values table says the UI-backend Secret is needed "only if your values
add credential entries for them; the shape above does not". The default
values shape does need it, because the subchart default is always live. A
reader who follows the guide exactly gets a broken UI pod and no pointer to
the cause.

The guide's own introduction carries a provenance note: this flow was never
exercised end-to-end in the validation lab. That is how the gap survived
several review rounds. Fixing the documentation alone would leave the same
trap for the next reader, because nothing in the install fails until a pod
cannot start. The chart should catch the missing Secret at render time and
name it, instead of letting a pod crash hours later in a stage the guide
calls "accept and rehearse".

### User Stories

* As a platform administrator, I want to install OSAC against an external
  Keycloak by following the external services guide, so that I can meet my
  organization's requirement to run identity outside the cluster.
* As a platform administrator, I want `helm install` to fail with a message
  that names the missing Secret when I disable the bundled Keycloak without
  providing credentials, so that I can fix my values in minutes instead of
  debugging a crashed pod after the install reports success.
* As a support engineer, I want the install to validate its credential
  wiring up front, so that I can rule out configuration gaps quickly when a
  customer's UI will not start.
* As an OSAC developer, I want a CI job that installs the chart with
  `keycloak.enabled: false` and external credential values, so that this
  path cannot silently regress again.

### Goals

* A fresh install with `keycloak.enabled: false` and external credentials
  reaches a working UI, with every Secret the application consumes either
  created by the operator or rejected at install time with a named error.
* The `ui.auth.serviceAccount.credentialsSecret` value is surfaced in the
  `osac` chart values and schema, so it is documented, validated, and
  rendered by the Enclave Wizard rather than discovered by reading subchart
  defaults.
* The external services guide states correctly which Secrets the operator
  must create, in which namespace, with which keys, and at which stage.
* The same review covers every credential Secret the chart consumes
  unconditionally (UI backend, controller, vault, and any CSI-driver or MCP
  exchange wiring that shares the pattern), so we fix the class of bug, not
  one instance.

### Non-Goals

* Changing how the bundled Keycloak path works. When
  `keycloak.enabled: true`, the existing hooks keep doing what they do.
* Generating client secrets against an external Keycloak from the chart.
  The realm and its clients are the operator's; the chart takes credentials
  as values or Secret references, it does not create them in a Keycloak it
  does not own.
* The PostgreSQL, OpenBao, and Kafka external paths. Their Secrets come from
  different machinery and a spot check found no equivalent gap. If the
  implementation review turns one up, it gets its own ticket.
* New API surface in fulfillment-service or osac-operator. This change is
  installer charts, schema, docs, and tests only.

## Proposal

Split the two jobs that `keycloak.enabled` currently does at once. The flag
keeps its meaning for the bundled operand and its realm machinery. The
application-side credential wiring stops depending on it:

1. **Surface the UI backend credential value.** Add
   `ui.auth.serviceAccount.credentialsSecret` to the `osac` chart's
   `values.yaml` and `values.schema.json`, defaulting to
   `osac-ui-backend-credentials` to match the subchart. The value already
   exists in the subchart; the parent chart just never exposed or documented
   it. This follows the Enclave Wizard pipeline: schema change first, then
   the plugin and Wizard tasks pick it up.

2. **Validate at render time.** When `keycloak.enabled` is `false` and
   `ui.enabled` is `true`, the chart's preflight checks (the
   `preflight/` templates in the osac chart) fail with a message naming the
   expected Secret and namespace, unless the operator has pointed
   `credentialsSecret` at a Secret they own. Helm cannot confirm a Secret
   exists at render time without a lookup, and lookups are unreliable during
   first installs, so the check validates the values shape: it fails when
   the flag is off and the value still names the chart-managed Secret that
   will never be created. It does not attempt to read the cluster.

3. **Keep the operator-created path.** An operator who follows the guide
   creates `osac-ui-backend-credentials` (keys `client-id: osac-ui-backend`,
   `client-secret: <the value assigned to the realm client in guide section
   5.3>`) in the `osac` namespace before the `osac` release install, and
   passes nothing — the default value already points at that name. The
   preflight passes because the value names a Secret that is the operator's
   to create, same contract as `fulfillment-controller-credentials` today.

4. **Fix the guide.** Correct section 5.2: row 10 and the line claiming the
   UI-backend Secret is conditional; add the Secret to the section's YAML
   example and checklist; add it to the stage-3 gate in the walkthrough so
   the Secret exists before the phase-2 install, not discovered by a
   crashing pod in stage 5.

The reason for each choice: exposing an existing subchart value is the
smallest chart change that makes the contract visible; render-time
validation converts a late, confusing failure into an early, named one; and
keeping credential creation with the operator matches the existing pattern
for the controller and vault Secrets, where the chart references Secrets it
does not generate.

### Workflow Description

**platform administrator** is the human installing OSAC against an external
Keycloak, following the external services guide.

1. The administrator stands up the external Keycloak, seeds the realm per
   guide section 5.3, and records the client secrets, including the one
   assigned to the `osac-ui-backend` realm client.
2. In stage 3 of the guide's walkthrough, the administrator creates the
   Secrets in the `osac` namespace: `fulfillment-controller-credentials`,
   `vault-credentials`, and `osac-ui-backend-credentials` (keys `client-id`
   and `client-secret`).
3. In stage 4, the administrator installs the `osac` release with
   `keycloak.enabled: false` on the infra release and the issuer, IdP, and
   UI values from guide section 5.2. No new value is required for the UI
   backend Secret when the default name is used.
4. If step 2 was skipped and the values still point at the default Secret,
   `helm install` fails during preflight with a message like: `keycloak is
   disabled; Secret "osac-ui-backend-credentials" (ui.auth.serviceAccount.credentialsSecret) is not chart-managed — create it in namespace "osac" before install or point the value at a Secret you manage`.
5. With the Secrets in place, the install succeeds, the UI deployment
   starts, and login works against the external issuer.

**Error handling:** the preflight failure is the guard. If an operator
bypasses it by pointing `credentialsSecret` at a nonexistent name, the
failure returns to the pod level — that is the documented, deliberate limit
of render-time validation without cluster lookups.

### API Extensions

None. This proposal adds and modifies Helm values in `osac-installer`
charts and their JSON schema. It adds no CRDs, webhooks, finalizers, or
gRPC services, and it does not change the behavior of any resource owned by
another party. The Enclave Wizard renders the new value automatically from
the schema; no plugin code change is expected beyond picking up the schema,
per the wizard pipeline.

### Implementation Details/Notes/Constraints

Evidence chain, for reviewers who want to walk it themselves:

* `osac-installer/charts/osac-infra/values.yaml:41-42` — `keycloak.enabled`
  defaults to `true`.
* `osac-ui/charts/ui/values.yaml:28` — subchart default
  `auth.serviceAccount.credentialsSecret: "osac-ui-backend-credentials"`.
* `osac-installer/charts/osac/values.yaml:359-378` — the parent chart's
  `ui:` block has no `serviceAccount` key, so the subchart default applies.
* `osac-ui/charts/ui/templates/deployment.yaml:48-56` — the deployment env
  `OIDC_SERVICE_CLIENT_ID` and `OIDC_SERVICE_CLIENT_SECRET` come from
  `secretKeyRef` on that Secret name. The ref is not optional.
* `osac-installer/charts/osac-infra/templates/osac-ui-backend-credentials-prereqs.yaml`
  and `templates/hooks/create-ui-backend-credentials.yaml` — both gated on
  `{{- if .Values.keycloak.enabled }}`. These are the only creators of the
  Secret.
* `osac-installer/charts/osac-infra/files/hooks/create-controller-credentials.sh`
  — the controller Secret has the same gating, but the guide already covers
  it because `service.auth.controllerCredentials` accepts a Secret
  reference; the UI subchart value was the undocumented one.

Values and schema changes land in both `values.yaml` and
`values.schema.json` with type, default, and description, per the wizard
pipeline. Decomposition follows its standard three artifacts: installer
task, Enclave plugin task, Enclave UI task, in that blocking order.

The guide fixes, all in
`docs/guides/installation/external-services-support-guide.md`:

* Section 5.2, row 10: replace the "only if your values add credential
  entries" claim. The UI-backend Secret is required whenever `ui.enabled`
  is true and the bundled Keycloak is off. The CSI-driver Secret stays
  conditional — its wiring only appears when backend `credentialsSecret`
  values are set.
* Section 5.2 example YAML: leave the default name in place, add a comment
  that the operator creates the Secret in the `osac` namespace with keys
  `client-id` / `client-secret` before the phase-2 install.
* The walkthrough's stage-3 gate: add `osac-ui-backend-credentials` to the
  list of Secrets that must exist before stage 4.
* The line after the YAML ("UI-backend and CSI-driver Secrets follow the
  same shape if your..."): reword to drop the UI-backend from the
  conditional and keep only the CSI-driver in it.
* Section 5.3 already assigns the `osac-ui-backend` client its secret in
  the realm seed, so no change is needed there; the guide just never told
  the reader to materialize that value as a cluster Secret.

One constraint worth stating: `helm lookup` during first install returns
nothing, so the preflight check cannot verify Secret existence on a fresh
cluster. The check is therefore about values shape, not cluster state. The
e2e journey below is what covers the real existence.

### Risks and Mitigations

* **Risk: the preflight check blocks installs that worked before.** An
  operator with an existing external-Keycloak install that already creates
  the Secret manually sees no change — the default value names the Secret
  they create. An operator who relied on some other mechanism to create a
  Secret under the default name is also unaffected. Only values that point
  at the chart-managed name while the chart manager is off fail, and that
  combination cannot produce a working install today. Mitigation: the error
  message names the fix, and the failure happens before any workload is
  touched.
* **Risk: schema change breaks the Enclave plugin.** The value is a plain
  string with a default, the simplest control the wizard renders
  (free-text input). Mitigation: the plugin task in decomposition includes
  verification that the field renders and validates.
* **Risk: we fix the UI Secret and miss another one.** The implementation
  sweeps every `secretKeyRef` in the `osac` chart and its subcharts that is
  not optional and not overridable through parent values. Anything found
  gets the same treatment in the same PR or a linked follow-up ticket, so
  the class is closed.

Security review: no new secret material enters values files — the value is
a Secret *name*, and the Secret's contents stay out of the chart. The
existing pattern for the controller Secret already works this way. UX
review: the only user-visible surface is the wizard field and the preflight
error text; the Enclave plugin task covers the first and the error wording
should get a docs pass in the guide PR.

### Drawbacks

The honest argument against: this is a small defect in a young guide, and
the cheapest fix is two lines of documentation. Everything above the doc
fix — schema, preflight, tests — is machinery for a path the validation lab
has never run end to end. If external Keycloak turns out to be rare in
practice, that machinery is maintenance cost with few users, and the
preflight check is one more way for an install to fail that previously
"succeeded" (and broke later).

The answer: the install "succeeding" and then shipping a UI pod that cannot
start is the failure mode we have today, and it is the expensive one — it
surfaces in stage 5 of a five-stage walkthrough, or in a support ticket.
The chart change is a single value plus a conditional check; the cost is
low and the failure it replaces is high. And the fresh-install CI journey
pays for itself regardless of adoption numbers, because it is the first
automated coverage this path has ever had.

## Alternatives (Not Implemented)

* **Documentation only.** Correct the guide and stop. Rejected: nothing
  fails at install time, so the next reader who skips a sentence gets the
  same crashed pod, and the next chart refactor can silently break the path
  again because no test covers it.
* **Render the Secret from literal values.** Have the chart create
  `osac-ui-backend-credentials` from a `clientSecret` value when the
  bundled Keycloak is off. Rejected: it puts secret material into values
  files, which get committed, diffed, and logged. The existing pattern —
  operator creates the Secret, chart references it by name — is better and
  already established for the controller and vault credentials.
* **Make the `secretKeyRef` optional in the UI deployment.** Rejected: an
  optional credential means a UI that starts and cannot authenticate, which
  is a worse failure than a pod that will not start. The failure should
  move earlier, not later.
* **Re-gate the existing hooks on a new `keycloak.external` flag.** The
  hooks read `keycloak-client-secrets` from the `keycloak` namespace, which
  does not exist when Keycloak is external, so they cannot run. Rejected on
  mechanics.

## Open Questions

1. Should the preflight check also cover the `osac-mcp-exchange-credentials`
   Secret? Today it is created only under `keycloak.devFixtures.enabled`,
   which is a dev-only flag, so the bundled path does not create it in
   production either. Tentative answer: no, out of scope, but the
   implementation sweep should confirm nothing consumes it unconditionally.
2. Does the Enclave Wizard need the field at all, given it mainly matters
   when Keycloak is external — is that a profile the wizard renders today?
   If not, the plugin/UI tasks reduce to a schema-only change.

## Test Plan

Following the integration testing policy's tiers:

* **Unit (chart render tests):** render the `osac` chart with
  `keycloak.enabled: false` and default UI values — preflight fails with the
  named error. Render with the flag off and `credentialsSecret` pointed at
  an operator-managed name — preflight passes and the deployment renders
  with that name. Render with the flag on — no behavior change.
* **Contract (values/schema):** schema validation accepts the new value
  with the right type and rejects a non-string.
* **E2E (the journey that has never run):** a fresh-install job that
  deploys the infra release with `keycloak.enabled: false`, creates the
  three Secrets, seeds nothing in-cluster for Keycloak, installs the `osac`
  release, and asserts the UI deployment becomes ready and can retrieve a
  token from the external issuer. This can run against the validation lab
  (Edge-04) or the test-infra cluster; it is also the run that would have
  caught the original gap, so it should exist before the guide's
  provenance note can be removed.

Test plan owners: chart render tests and schema tests are `[DEV]` work in
the installer task; the e2e journey is `[QE]` work with its own ticket,
blocked by the installer task.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected
signal for GA: the fresh-install e2e journey runs in CI, and the external
services guide's provenance note about the untested flow is removed because
the flow is now covered.

## Upgrade / Downgrade Strategy

No migration is required. Existing installs with the bundled Keycloak are
untouched — the default value matches the Secret the hooks already create.
Existing external-Keycloak installs that create the Secret manually under
the default name are also untouched. The only new failure mode is a values
combination that cannot produce a working install today, failing earlier
than it used to.

Downgrade: revert the chart; the value disappears from the schema and the
preflight check goes away. Secrets created by operators persist and keep
working.

## Version Skew Strategy

The change is confined to the `osac` chart's values and templates; the UI
subchart is untouched (its value already exists). No component ordering
matters: installer chart and guide land together in the same mono-repo, and
an older UI image with a newer chart works because the chart change only
adds a value and a check. The guide changes assume the new value exists, so
the docs and chart changes ship in one PR or in PRs merged in the same
cycle.

## Support Procedures

* **Detection:** before this change, the symptom is a UI pod stuck in
  `CreateContainerConfigError` with event `secret "osac-ui-backend-credentials"
  not found` in the `osac` namespace, while the helm release reports success.
  After this change, the same misconfiguration fails during `helm install`
  with a preflight message naming the Secret. Support scripts that grep
  deployments for missing-secret events keep working for clusters installed
  before the change.
* **Remediation:** create the Secret in the `osac` namespace with keys
  `client-id` (`osac-ui-backend`) and `client-secret` (the value assigned
  to that client in the realm seed, guide section 5.3), then re-run the
  install or let the deployment retry. No data is lost; no other component
  is affected.
* **Disabling:** setting `ui.enabled: false` removes the consumer and the
  check. The rest of the install is unaffected.

## Infrastructure Needed

A CI environment able to run the fresh-install journey against an external
Keycloak (a realm reachable from the test cluster, with seeded clients).
The Edge-04 lab or the test-infra cluster can host it; if neither is
suitable, the QE ticket owns requesting the capacity.
