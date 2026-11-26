# Test Plan — OSAC-1330 Type-safe resource references

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 9

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-REF-01: Reference messages round-trip in protobuf and JSON

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1044-1049](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1044-L1049)
- **Dependencies:** Generated message types and local codecs only.
- **Gap:** Reference interceptor tests verify discovery and mutation. The binary-and-JSON round-trip matrix was not found in canonical proto and reference test sources.

**Preconditions.** Construct full and local reference fixtures with a synthetic ID/name and supported scope fields.

1. Serialize and deserialize each in binary and protobuf JSON.
2. Compare presence, values and scope with the originals.

**Expected results.** Each round trip preserves all populated values and optional presence.

#### TC-REF-02: Interceptor discovery finds a nested attachment and repeated references

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1050-1054](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1050-L1054)
- **Dependencies:** Synthetic protobuf request fixture; no server or registration lookup.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Discovers all reference field patterns in a complex message` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L676)).
- **Selector:** Ginkgo focus `Discovers all reference field patterns in a complex message` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Use the synthetic request with target, local target, attachment subnet, security groups and repeated other targets.

1. Discover references from the request.
2. Count occurrences grouped by the three reflected types.

**Expected results.** Discovery returns one full, two local and two other local references.

#### TC-REF-03: An unresolved reference returns InvalidArgument with its field path

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1055-1057](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1055-L1057)
- **Dependencies:** In-process interceptor with synthetic request and controlled lookup; no database.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Returns InvalidArgument with BadRequest FieldViolation for not-found reference` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L1881)).
- **Selector:** Ginkgo focus `Returns InvalidArgument with BadRequest FieldViolation for not-found reference` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Configure the lookup fixture to return not found for the supplied target.

1. Call the interceptor for the fixture Create.
2. Read the gRPC code and structured field violation.

**Expected results.** InvalidArgument carries one BadRequest violation at object.spec.target and the handler is not invoked.

#### TC-REF-04: Name-only reference resolution fills in the ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1058-1064](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1058-L1064)
- **Dependencies:** In-process interceptor with synthetic reference and stub lookup.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Auto-populates id when resolved by name` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L1269)).
- **Selector:** Ginkgo focus `Auto-populates id when resolved by name` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Use the suite name-only full-reference fixture and matching lookup result.

1. Pass the request through the interceptor.
2. Inspect the object reaching the downstream handler.

**Expected results.** The reference contains the resolved ID and retains the correct name.

#### TC-REF-05: Kind resolves both Subnet reference forms against PostgreSQL

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 1069-1085](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1069-L1085)
- **Dependencies:** Real deployed fulfillment, registered interceptor and PostgreSQL in Kind; fixture NetworkClass; provider omitted.
- **Gap:** Canonical network integration and interceptor unit cases were searched. The exact two-form matrix plus persisted path checks was not verified in a single Kind selector.

**Preconditions.** Create one fixture VirtualNetwork prod-net with a known ID.

1. Create Subnets with the network named and identified separately.
2. Get both and List by nested virtual_network.name.

**Expected results.** Each stored reference contains the same canonical ID and name and List returns both results.

#### TC-REF-06: Multiple unresolved references share one structured BadRequest

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1055-1057](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1055-L1057)
- **Dependencies:** In-process interceptor, synthetic message and two controlled lookup failures; no database.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Aggregates multiple reference errors in a single BadRequest` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L1931)).
- **Selector:** Ginkgo focus `Aggregates multiple reference errors in a single BadRequest` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Use a fixture request with unresolved full target and local target.

1. Call the interceptor with both references.
2. Inspect the structured BadRequest.

**Expected results.** One InvalidArgument response contains a single structured BadRequest with two field violations. The downstream handler is not invoked.

#### TC-REF-07: ID-only reference resolution fills in the name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1058-1064](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1058-L1064)
- **Dependencies:** In-process interceptor and stub lookup; no database.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Auto-populates name when resolved by id` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L1311)).
- **Selector:** Ginkgo focus `Auto-populates name when resolved by id` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Use the suite's ID-only reference fixture.

1. Pass the request through the interceptor with a known matching result.
2. Inspect the ID and name in the handler request.

**Expected results.** Both the original ID and resolved name are present.

#### TC-REF-08: A mismatched ID and name produce InvalidArgument

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 1058-1064](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L1058-L1064)
- **Dependencies:** In-process interceptor and controlled synthetic lookup; no real objects.
- **Execution:** `fulfillment-service/internal/references/reference_validator_test.go`
- **Evidence:** `Returns InvalidArgument for id/name mismatch` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/references/reference_validator_test.go#L2069)).
- **Selector:** Ginkgo focus `Returns InvalidArgument for id/name mismatch` in `fulfillment-service/internal/references`. Source reviewed, test not run.

**Preconditions.** Use the suite's reference fixture with distinct ID/name selections.

1. Pass the request through the interceptor.
2. Read the code and diagnostic.

**Expected results.** InvalidArgument describes the inconsistent reference.

#### TC-REF-09: Migrated Create and Update requests discover each typed field path

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 873-884](https://github.com/osac-project/enhancement-proposals/blob/84a28b6b9865f71684304e9fd1e1665835807bfc/enhancements/OSAC-1330-type-safe-resource-references/design.md#L873-L884)
- **Dependencies:** Generated public/private messages and local descriptor walk; no service or database.
- **Gap:** Canonical synthetic discovery specs do not exhaust the registered production paths across networking, compute, IP management, cluster/bare metal and IAM.

**Preconditions.** Build Create and applicable Update cases from the five migration rows. Include VirtualNetwork spec.network_class, Subnet/SecurityGroup spec.virtual_network, compute spec.template, spec.catalog_item, spec.instance_type and nested subnet/security_groups, IP spec.pool and spec.target oneofs, Cluster/BareMetal templates and catalogs, and RoleBinding/ProjectMembership role/user/project paths.

1. Walk each request's nested, repeated and oneof fields through the interceptor.
2. Compare each reflected path and type to its migration row.

**Expected results.** Every migrated typed path is found once for its intended variant, including the selected oneof alternative, and unrelated fields remain untouched.
