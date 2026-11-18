# Local DNS Backend Support — BIND Integration

| Field       | Value   |
|-------------|---------|
| Author(s)   | Manuel Lorenzo |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2281 |
| Date        | 2026-11-17 |

## Problem Statement

Every CaaS cluster needs DNS names for its API, its internal API, and its
applications before it is usable. Today OSAC can manage those names only in
AWS Route 53, which requires a cloud account and internet access; otherwise
the Cloud Infrastructure Admin must create three records by hand for every
new cluster and remove them after every deletion. Cluster names are assigned
by OSAC at creation time, so the records cannot be prepared in advance, and
cluster creation waits until someone adds them. Sovereign, government,
enterprise, and air-gapped datacenters that run their own DNS servers, such
as BIND, therefore cannot offer self-service clusters without manual work
for each cluster, and stale records accumulate when deletions are missed.

## In Scope

- CaaS cluster endpoint names (API, internal API, and wildcard application
  names) created in a datacenter-hosted DNS server when a cluster is
  created, and removed when the cluster is deleted, through OSAC's
  existing pluggable DNS backend model
- BIND as the validated and documented DNS server. Other DNS servers that
  accept standard dynamic DNS updates (RFC 2136) authenticated with a TSIG
  key may be configured, but are not validated
- One DNS backend per OSAC deployment, selected and configured by the Cloud
  Infrastructure Admin through the installation values: the DNS server
  address, the DNS zone, and the TSIG key OSAC signs with (its name, its
  algorithm, and its secret, which is supplied as a protected credential)
- Authenticated record changes only: OSAC always signs its changes with the
  configured TSIG key, and the key is required
- Failure handling: when the DNS server rejects a change (for example, a
  wrong key, a zone the key may not update, or a record outside the zone) or
  does not answer, cluster creation does not report ready and cluster
  deletion does not report complete. The Cloud Infrastructure Admin sees a
  message that names the setting to check, and OSAC retries. A deletion is
  never reported complete while the cluster's records remain in the DNS
  server's zone
- DNS management without external dependencies: managing cluster DNS
  records requires network access only to the configured datacenter DNS
  server, with no internet or external DNS provider
- Credential protection: the TSIG secret is supplied as a protected
  credential and never appears in job output, logs, error messages, or
  events. The DNS backend's own job output and failure messages also do not
  reveal record names or addresses; administrator-facing cluster failure
  events keep naming the affected record, as in the existing CaaS
  diagnostics
- An unchanged tenant experience: Tenant Admins and Tenant Users see their
  cluster's API and console addresses resolve once the cluster is ready, in
  the UI, CLI, and API, exactly as with the other DNS backends
- Cloud Infrastructure Admin documentation covering the OSAC settings, the
  BIND setup (zone, TSIG key, and update permission limited to that zone),
  making the zone resolvable, network access from the management cluster,
  and troubleshooting by error message
- A documented manual validation in a lab with a real BIND server: a
  cluster's API, internal API, and application names resolve after
  creation, and after the cluster is deleted its records are gone from the
  DNS server's zone. The deletion check queries the DNS server directly,
  because other resolvers may return cached answers until their TTL expires

## Out of Scope

- DNS names for VM hostnames — covered by OSAC-6156
- Selecting or approving DNS backends per region; a deployment uses one DNS
  backend
- A tenant-facing DNS resource or API, and a tenant-visible DNS publication
  status — tenant-facing DNS is a separate proposal
- Validating DNS servers other than BIND, such as PowerDNS or CoreDNS
- Changing the DNS backend while clusters exist, and migrating records
  between DNS backends
- Configuring delegation or forwarding so that clients can resolve the
  cluster zone — the Cloud Infrastructure Admin owns this in their DNS
  infrastructure
- Enclave Wizard behavior specific to this backend, such as showing its
  settings only when it is selected — an Enclave follow-up
- Automated end-to-end tests against a BIND server — tracked separately,
  because they need a CI lab with a BIND server

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure my datacenter's BIND
  server as the DNS backend for my OSAC deployment, so that the API, internal
  API, and application names of every CaaS cluster are created and removed
  within my datacenter without per-cluster manual records.
- As a Cloud Infrastructure Admin in an air-gapped datacenter, I want cluster
  DNS names to be managed using only my local DNS server, so that cluster
  DNS record management has no internet or external DNS-provider
  dependency.
- As a Cloud Infrastructure Admin, I want a cluster creation or deletion to
  stop with a message naming the setting to fix when my DNS server rejects
  OSAC's change or cannot be reached, so that I can correct the
  configuration and no cluster is reported ready without working names, or
  deleted while its records remain.
- As a Cloud Infrastructure Admin, I want a guide that covers both the OSAC
  settings and the BIND-side setup, so that I can prepare the zone, the TSIG
  key, and its update permission without trial and error.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my cluster's API and console
  addresses to resolve once the cluster is ready, without knowing which DNS
  backend the provider uses, so that I can connect to the cluster as soon as
  OSAC reports it ready.

## Assumptions

- The Cloud Infrastructure Admin makes the cluster DNS zone resolvable for
  tenants' networks, the cluster nodes, and the management cluster, through
  delegation from the parent zone or forwarding
- The management cluster can reach the configured DNS server over the
  network
- The DNS administrator creates the zone and the TSIG key in BIND and grants
  that key permission to update records in the zone before clusters are
  created

## Dependencies

- **Pluggable DNS backend model (OSAC-1050):** this Feature adds a DNS
  backend to the existing model that CaaS uses for its endpoint names; it
  depends on that model and does not change it.
- **Lab with a BIND server:** required for the manual validation of cluster
  creation and deletion.
- **Enclave team:** owns any Wizard behavior specific to this backend.
- **CI lab with a BIND server:** required by the separately tracked automated
  end-to-end tests.

---

## Provenance

Authored: draft @ prd 0.11.5 - 922de34, workspace main @ f0a8211
Final: respond @ prd 0.11.5 - 7653641, workspace main @ f0a8211

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7653641","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
