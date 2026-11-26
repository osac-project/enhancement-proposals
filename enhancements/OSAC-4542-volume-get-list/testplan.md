# Test Plan — OSAC-4542 Standalone volume Get and List

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 17

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

The read design predates standalone public write APIs. Read coverage and defensive read-scope assertions use the accepted Volume Get/List boundary.

The original read-only design precedes the public Volume Create, Update and Delete API. The authorization cases here cover Get and List. The descriptor checks cover the generated schema without asserting the serialized wire payload.

## Test Cases

#### TC-VP-01: Get returns fixture public Volume fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Public Get projection](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L244)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Read operations / Gets a volume and exposes only public fields` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L137)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Read operations Gets a volume and exposes only public fields$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the server fixture with private volume public-vol, gold tier and 100 GiB.

1. Call public Get using the private Create ID.
2. Inspect metadata, spec and state.

**Expected results.** ID matches, name is public-vol and tenant is the fixture owner. Spec shows gold, 100 GiB and ReadWriteOnce; state is CREATING.

#### TC-VP-02: Public descriptor excludes internal routing fields recursively

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Descriptor privacy guard](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L247)
- **Dependencies:** Real generated descriptor and reflection. This assertion does no I/O; the parent server suite starts PostgreSQL.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Public schema / Does not expose any internal routing field in any public message` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L631)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Public schema Does not expose any internal routing field in any public message$'` from `fulfillment-service` in OSAC.

**Preconditions.** Load the generated public Volume descriptor through the server suite.

1. Walk reachable message descriptors.
2. Check the forbidden routing field names.

**Expected results.** No descriptor exposes backend, protocol, hub or vendor_volume_id.

#### TC-VP-03: Public state field is accepted by CEL filtering

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Public CEL filtering](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L256)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Read operations / Supports CEL filtering on a public field` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L186)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Read operations Supports CEL filtering on a public field$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed creating fixture filter-vol.

1. Call List filtered by the public CREATING state.
2. Read the response.

**Expected results.** The filter is accepted and returns a nonempty set.

#### TC-VP-04: Public filtering rejects a private-only schema field

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Public CEL field validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L257)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Read operations / Rejects a CEL filter that references a private-only field` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L196)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Read operations Rejects a CEL filter that references a private-only field$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed a synthetic volume in the in-process server fixture.

1. Submit a public-filter request that names an unsupported field on the synthetic fixture.
2. Inspect the returned error.

**Expected results.** The unsupported field is rejected.

#### TC-VP-05: Public read authorization respects tenant permissions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Tenant authorization for Get and List](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L261)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** The server fixtures use injected tenancy logic. The Kind public Volume specs do not exercise a permission matrix across two tenants.

**Preconditions.** Use two synthetic tenants with distinct fixture volumes and clients with the documented read permissions.

1. Get and list volumes through each tenant's own scoped client.
2. Compare the returned fixture IDs to that tenant's allowed dataset.

**Expected results.** Clients with read permissions obtain their own fixture records. Other tenant fixtures are not returned.

#### TC-VP-06: Kind public Get observes a created Volume and its final removal

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Deployed public Get projection and absent ID](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L266)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Execution:** `fulfillment-service/it/it_public_volumes_test.go`
- **Evidence:** `TestIntegration / Public volumes API / Creates, gets, and deletes a volume via the public API` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_public_volumes_test.go#L115)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Public volumes API / Creates, gets, and deletes a volume via the public API` in the service-only phase.

**Preconditions.** Use a seeded tier/backend and public tenant user in Kind.

1. Create, read and delete a fixture Volume through the public API.
2. Read it after cleanup.

**Expected results.** Public Get returns the created Volume values and eventually NotFound after deletion.

#### TC-VP-07: Tenant List returns exactly three visible rows and total three

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Public List items and total](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L244)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Read operations / Lists volumes visible to the caller` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L172)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Read operations Lists volumes visible to the caller$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create three fixture volumes visible to one tenant.

1. Call the public List RPC.
2. Count returned items and compare total and tenant on each item.

**Expected results.** List has three items, total is three and all items have the fixture tenant.

#### TC-VP-08: Generated public Volume descriptor pins the complete nested allowlist

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Exact generated schema](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L251)
- **Dependencies:** Descriptor assertions perform no API or database I/O. The hosting Kind suite still runs its deployed setup and seeds fixtures.
- **Execution:** `fulfillment-service/it/it_public_volumes_test.go`
- **Evidence:** `TestIntegration / Public volumes API / Public Volume response contains exactly the approved field set` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_public_volumes_test.go#L369)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Public volumes API / Public Volume response contains exactly the approved field set` in the service-only phase.

**Preconditions.** Use the generated public protobuf descriptors.

1. Walk the public Volume, Metadata, VolumeSpec and VolumeStatus descriptors.
2. Compare the declared fields to the approved set.

**Expected results.** The root has id, metadata, spec and status. Spec has storage_tier, size_gib and access_mode. Status has state and message. Metadata has creation_timestamp, deletion_timestamp, creator, tenant, name, labels, annotations, version and project.

#### TC-VP-09: Public CEL returns exactly the expected state subset

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Exact public CEL subset](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L256)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** Existing server spec checks only nonempty output; the exact mixed-state subset is unverified.

**Preconditions.** Seed three visible volumes, exactly two CREATING and one AVAILABLE.

1. Filter List by CREATING.
2. Compare the returned IDs and total to the seeded set.

**Expected results.** Only the two CREATING IDs are returned and total is two.

#### TC-VP-10: Kind public reads project a privately created Volume

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private seed, public Get and List](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L266)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** The Kind lifecycle uses public Create and public Get. Public server tests cover private seeding with in-process Get and List. The deployed private Create to public Get and List path is unverified.

**Preconditions.** Create one named Volume via the private API for an isolated fixture tenant.

1. Get it via the authorized public client and list that tenant's volumes.
2. Compare the projected values.

**Expected results.** The public Get and List entries agree on ID, tenant, public spec and state.

#### TC-VP-12: Kind responses omit private routing fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Public wire projection](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L266)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Gap:** Existing Kind allowlist inspects descriptors rather than the serialized service response.

**Preconditions.** Create a synthetic private Volume with internal routing fields populated.

1. Read it through the public gRPC endpoint.
2. Inspect the serialized Get and List response field names.

**Expected results.** Public responses retain only the public projection; internal routing fields do not appear.

#### TC-VP-11: Unsupported private filter names yield the documented status

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Unsupported public filter status](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L257)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** The matched server case checks a generic error only. The exact documented InvalidArgument code is unverified.

**Preconditions.** Use synthetic returned and excluded descriptors with a valid fixture row.

1. Submit a public-filter request using an unsupported schema field in the fixture.
2. Check the gRPC status.

**Expected results.** The unsupported field yields InvalidArgument.

#### TC-VP-13: Public Get returns an error for an absent fixture ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Nonexistent ID](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L260)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Read operations / Returns an error getting a volume that does not exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L165)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Read operations Returns an error getting a volume that does not exist$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the public server fixture with a fresh unassigned ID.

1. Request a Volume with that ID.

**Expected results.** Get returns an error.

#### TC-VP-14: Private Volume server builds without a tier resolver

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Private read-delegate construction](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L263)
- **Dependencies:** Builder assertion performs no database request. The surrounding server suite starts PostgreSQL.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Creation / Can be built without a tier resolver (used by the read-only public delegate)` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L80)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Creation Can be built without a tier resolver \(used by the read-only public delegate\)$'` from `fulfillment-service` in OSAC.

**Preconditions.** Supply the private Volume server builder with fixture logger, attribution and tenancy but omit the resolver.

1. Build the server.

**Expected results.** Build returns a non-nil server without error.

#### TC-VP-15: Private Create requires a configured resolver

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Private Create without resolver](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L263)
- **Dependencies:** Calls the server handler in process. The resolver guard returns before database I/O; the surrounding suite starts PostgreSQL.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Creation / Fails Create if tier resolver is not set` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L90)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Creation Fails Create if tier resolver is not set$'` from `fulfillment-service` in OSAC.

**Preconditions.** Build the private API handler without its tier resolver in the server fixture.

1. Submit a standard named ReadWriteOnce fixture Volume with tier and size.

**Expected results.** Create returns an error identifying the missing tier resolver.

#### TC-VP-16: Deployed VMaaS volume is visible through both public read operations

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [VMaaS public read path](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L271)
- **Dependencies:** Requires deployed VMaaS, fulfillment and an isolated storage provider fixture. Uses synthetic tenant identities.
- **Gap:** The VMaaS storage-tier suite reads generated disk records for linkage and cleanup. The Kind suite exercises public Get but does not establish the deployed VMaaS Get and List path.

**Preconditions.** Use a provisioned VMaaS fixture volume and its authorized tenant client in the deployed test environment.

1. Read the volume through public Get and List, then compare each result to the expected public fixture representation.

**Expected results.** Both operations return the same fixture identity and approved fields within the owning tenant's scope.

#### TC-VP-17: Reader roles can use public Volume Get and List

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Public read authorization](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-4542-volume-get-list/design.md#L261)
- **Dependencies:** In-process authorization evaluator and generated method descriptors with fixture subject claims. No deployed identity provider or Volume service.
- **Execution:** `fulfillment-service/internal/auth/authorization_evaluator_test.go`
- **Evidence:** `TestAuth / OPA Authorization Evaluator / reader role authorization / limits reader roles to reviewed reads and preserves explicit grants` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/auth/authorization_evaluator_test.go#L690)).
- **Selector:** `go test ./internal/auth -run '^TestAuth$' -ginkgo.focus='^OPA Authorization Evaluator reader role authorization limits reader roles to reviewed reads and preserves explicit grants$'` from `fulfillment-service` in OSAC.

**Preconditions.** Build the authorization evaluator with synthetic tenant-reader and cloud-provider-reader subjects.

1. Evaluate their grants for the registered public Volume methods.

**Expected results.** Both roles are allowed to Get and List.
