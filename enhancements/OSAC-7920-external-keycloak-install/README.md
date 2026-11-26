---
title: external-keycloak-install
authors:
  - obochan@redhat.com
creation-date: 2026-11-18
last-updated: 2026-11-19
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
credentials": the osac chart gains documented values for the UI backend
credential Secret plus an explicit operator-managed mode, a pre-install
hook verifies the Secret exists before any workload starts, and the
external services guide is corrected to match.

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
cannot start. The chart should catch the missing Secret before any
workload starts and name it, instead of letting a pod crash hours later in
a stage the guide calls "accept and rehearse".

### User Stories

* As a platform administrator, I want to install OSAC against an external
  Keycloak by following the external services guide, so that I can meet my
  organization's requirement to run identity outside the cluster.
* As a platform administrator, I want `helm install` to fail with a message
  that names the missing Secret when I declare operator-managed UI
  credentials but have not created the Secret, so that I can fix the
  problem in minutes instead of debugging a crashed pod after the install
  reports success.
* As a support engineer, I want the install to validate its credential
  wiring up front, so that I can rule out configuration gaps quickly when a
  customer's UI will not start.
* As an OSAC developer, I want a CI job that installs the chart with
  `keycloak.enabled: false` and external credential values, so that this
  path cannot silently regress again.

### Goals

* A fresh install with `keycloak.enabled: false` and external credentials
  reaches a working UI. Secrets the operator declares as operator-managed
  are verified by a pre-install hook — present, in the right namespace,
  with the right keys — before any workload starts.
* The `ui.auth.serviceAccount.credentialsSecret` and
  `ui.auth.serviceAccount.credentialsManagedBy` values are surfaced in the
  `osac` chart values and schema, so they are documented, validated, and
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

1. **Surface the UI backend credential values.** Add
   `ui.auth.serviceAccount.credentialsSecret` and
   `ui.auth.serviceAccount.credentialsManagedBy` to the `osac` chart's
   `values.yaml` and `values.schema.json`. `credentialsSecret` defaults to
   `osac-ui-backend-credentials` to match the subchart. The Secret-name
   value already exists in the subchart; the parent chart just never
   exposed or documented it. This follows the Enclave Wizard pipeline:
   schema change first, then the plugin and Wizard tasks pick it up.

2. **Add an explicit operator-managed mode.** `credentialsManagedBy`
   accepts `chart` (default) or `operator`. `chart` is today's behavior:
   the bundled Keycloak's hooks create the Secret. `operator` is the
   declaration that the operator creates the Secret named by
   `credentialsSecret` themselves. The mode lives in the `osac` release's
   own values on purpose: Helm does not share values between releases, so
   a check in the `osac` chart cannot read the infra release's
   `keycloak.enabled` flag. The operator's declaration replaces that
   cross-release knowledge.

3. **Verify the Secret before workloads start.** Two checks, at different
   moments:
   - *Render time* (the chart's existing preflight catalog,
     `files/preflight/catalog.yaml`): mode `operator` with an empty
     `credentialsSecret` is a blocking error. This is a values-shape
     check; render time cannot read the cluster.
   - *Pre-install hook* (a job in the `osac` release, hook-weight ahead of
     the workloads): when the mode is `operator`, verify the named Secret
     exists in the release namespace and carries both keys, `client-id`
     and `client-secret`. A hook runs inside the cluster, so it is not
     bound by the `helm lookup` limit. Missing Secret or missing key
     fails the install with a message naming all three.

4. **Keep the operator-created path.** An operator who follows the guide
   creates `osac-ui-backend-credentials` (keys `client-id: osac-ui-backend`,
   `client-secret: <the value assigned to the realm client in guide section
   5.3>`) in the `osac` namespace before the `osac` release install, keeps
   the default Secret name, and sets
   `ui.auth.serviceAccount.credentialsManagedBy: operator`. Same contract
   as `fulfillment-controller-credentials` today, now with a declaration
   the chart can act on.

5. **Fix the guide.** Correct section 5.2: row 10 and the line claiming the
   UI-backend Secret is conditional; add the Secret and the
   `credentialsManagedBy` setting to the section's YAML example and
   checklist; add the Secret to the stage-3 gate in the walkthrough so it
   exists before the phase-2 install, not discovered by a crashing pod in
   stage 5.

The reason for each choice: exposing the existing subchart value is the
smallest chart change that makes the contract visible; the explicit mode
makes an invisible assumption (who creates this Secret) into a declared,
schema-validated value instead of a guess the chart cannot make; the hook
check converts a late, confusing failure into an early, named one; and
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
   `keycloak.enabled: false` on the infra release, the issuer, IdP, and UI
   values from guide section 5.2, and
   `ui.auth.serviceAccount.credentialsManagedBy: operator`. The default
   Secret name stays.
4. If step 2 was skipped, the pre-install hook fails with a message like:
   `ui.auth.serviceAccount.credentialsManagedBy is "operator" but Secret
   "osac-ui-backend-credentials" not found in namespace "osac" (expected
   keys: client-id, client-secret) — create it before install`. The
   release never reaches the workloads.
5. With the Secrets in place, the install succeeds, the UI deployment
   starts, and login works against the external issuer.

**Error handling:** the hook failure is the guard for the declared path.
One case stays outside it: an operator who runs an external Keycloak but
leaves `credentialsManagedBy` at the default `chart` makes no declaration,
so no check fires and the failure returns to the pod level. That is the
documented limit — the chart cannot see the infra release's flag — and the
guide's stage-3 gate and the e2e journey are what cover it.

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
* Section 5.2 example YAML: leave the default name in place, add
  `ui.auth.serviceAccount.credentialsManagedBy: operator` to the example,
  and note that the operator creates the Secret in the `osac` namespace
  with keys `client-id` / `client-secret` before the phase-2 install.
* The walkthrough's stage-3 gate: add `osac-ui-backend-credentials` to the
  list of Secrets that must exist before stage 4.
* The line after the YAML ("UI-backend and CSI-driver Secrets follow the
  same shape if your..."): reword to drop the UI-backend from the
  conditional and keep only the CSI-driver in it.
* Section 5.3 already assigns the `osac-ui-backend` client its secret in
  the realm seed, so no change is needed there; the guide just never told
  the reader to materialize that value as a cluster Secret.

One constraint worth stating: `helm lookup` during first install returns
nothing, so a render-time check cannot verify Secret existence on a fresh
cluster — that is why the existence check is a pre-install hook, which runs
inside the cluster, and the render-time catalog check only validates the
values shape. The hook reads the Secret's keys but never its values; no
credential material enters logs or the release.

Two more implementation notes:

* The osac chart already has a preflight engine
  (`templates/preflight/report.yaml` plus `files/preflight/catalog.yaml`)
  that fails the render with a combined message listing every blocking
  problem. The values-shape check belongs in that catalog, not in a new
  mechanism.
* The cross-release point matters for reviewers: `keycloak.enabled` lives
  on the `osac-infra` release and the consumers live on the `osac` release.
  Helm does not share values between releases, so any check keyed on the
  flag would have to live in the infra chart, where the UI Secret is not
  consumed. The `credentialsManagedBy` declaration in the `osac` release
  is what makes the check possible where the failure happens.

### Risks and Mitigations

* **Risk: the checks block installs that worked before.** They are
  opt-in: both fire only when `credentialsManagedBy: operator` is set, and
  existing installs that never set it see no change. An existing
  external-Keycloak install that adopts the value gains a guard, not a
  barrier — the hook passes as soon as the Secret it already creates is in
  place. Mitigation for the failure itself: the error message names the
  Secret, namespace, and keys, and the failure happens before any workload
  is touched.
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
* **A values-only render check keyed on the infra release's
  `keycloak.enabled`.** Fail the render when the flag is off and the value
  still names the default Secret. Rejected twice over: Helm does not share
  values between releases, so the `osac` chart cannot read the flag; and a
  values-only rule cannot distinguish an operator-created Secret under the
  default name from a missing one, so it would reject the exact install
  path this proposal documents. The explicit `credentialsManagedBy`
  declaration plus the existence hook exist because this simpler shape
  does not work.
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
  `credentialsManagedBy: operator` and an empty `credentialsSecret` — the
  preflight catalog fails with the named error. Render with the mode at
  the default `chart` — no check renders, no behavior change. Render the
  hook template in both modes — the job exists only for `operator`.
* **Component integration (hook):** run the pre-install hook against a
  kind cluster: Secret present with both keys passes; Secret missing, and
  Secret present with a missing key, both fail with the message naming
  Secret, namespace, and keys. The hook must not log Secret values — the
  test asserts on that too.
* **Contract (values/schema):** schema validation accepts both new values
  with the right types, rejects a `credentialsManagedBy` outside the enum,
  and rejects a non-string `credentialsSecret`.
* **E2E (the journey that has never run):** a fresh-install job that
  deploys the infra release with `keycloak.enabled: false`, creates the
  three Secrets, sets `credentialsManagedBy: operator`, seeds nothing
  in-cluster for Keycloak, installs the `osac` release, and asserts the UI
  deployment becomes ready and can retrieve a token from the external
  issuer. This can run against the validation lab (Edge-04) or the
  test-infra cluster; it is also the run that would have caught the
  original gap, so it should exist before the guide's provenance note can
  be removed.

Test plan owners: chart render tests, the hook integration test, and
schema tests are `[DEV]` work in the installer task; the e2e journey is
`[QE]` work with its own ticket, blocked by the installer task.

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
  — the pre-install hook's message names the Secret — but only when the
  operator declared `credentialsManagedBy: operator`; an undeclared
  external install keeps the old pod-level symptom. Support scripts that
  grep deployments for missing-secret events keep working for clusters
  installed before the change.
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
