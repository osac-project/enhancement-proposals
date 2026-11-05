---
title: quota-foundation
authors:
  - ovishlit@redhat.com
creation-date: 2026-11-03
last-updated: 2026-11-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4500
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-5753-event-log-driven-metering"
  - "/enhancements/OSAC-6056-metering-event-contract"
  - "/enhancements/OSAC-1030-organizations"
  - "/enhancements/OSAC-6154-add-actor-attribution-to-fulfillment-events"
  - "/enhancements/OSAC-3784-billing-integration-mvp"
---

# Quota Foundation

| Field       | Value   |
|-------------|---------|
| Author(s)   | Omer Vishlitzky |
| Jira        | [OSAC-4500](https://redhat.atlassian.net/browse/OSAC-4500) |
| PRD         | [PRD](prd.md) |
| Date        | 2026-11-03 |

## Summary

A tenant can hold as many VMs, clusters, bare-metal hosts, volumes, and addresses as it asks for. One tenant can
consume a deployment's shared capacity and block every other tenant. This design adds usage quota inside the
fulfillment service, per tenant and per project; a tenant's quota contains the usage of all its projects:

- **Each resource declares its own holdings.** Proto annotations name the dimensions a resource holds. A registry
  walks the annotations, and the checker is generic; no resource type is hardcoded in it. A new service ships
  annotations and gets enforcement.
- **The check runs inside the request transaction.** One generic hook in the shared CRUD path locks the quota
  rows of the project, each ancestor project, and the tenant, and counts held usage against each cap. An order
  over any cap is rejected before anything is saved.
- **Usage is counted, never stored.** The resource rows are the usage, so no counter can drift and quota state that
  is lost rebuilds by counting rows.

See [PRD](prd.md) for detailed requirements.

## Proposal

### Big picture

```mermaid
flowchart LR
  user["Tenant user"] -->|"create, resize, scale up"| api["Fulfillment API"]
  subgraph svc["Fulfillment service (one database)"]
    api --> hook["Quota check, one generic hook"]
    limits[("quota_limits rows, tenant and project, locked")] --> hook
    rows[("Resource rows, active set")] --> hook
    hook -->|"over limit"| rej["FAILED_PRECONDITION, scope and dimension named"]
    hook -->|"within limits"| save["Save, commit releases the lock"]
    save --> out[("Quota outbox")]
  end
  out --> pub["Quota publisher"]
  pub --> note(["osac.notifications.&lt;tenant&gt;"])
```

| Who | When | What it does |
|---|---|---|
| Tenant user | On create, resize, and scale (a decrease always passes) | Submits the order and sees the result. |
| Quota check | Inside the request transaction | Locks the limit rows of both scopes, counts usage, sums holdings. |
| Controllers | After an order is granted | Create the order's sub-resources; the bypass rule applies to these writes. |
| Tenant onboarding | When a tenant is created | Copies the default limits into the tenant's rows. |
| Quota publisher | Continuously | Drains the quota outbox into the notifications topic. |

### Invariants

What must always hold, and what enforces it. Tests are numbered as in the Test Plan.

| Invariant | Enforced by |
|---|---|
| Usage is counted from rows on demand, never stored | No counter table exists; the recount test (test 10) |
| A resource declares its own holdings in proto annotations; the checker is generic | The registry walk; test 12 |
| New resource types and dimensions are data, with no checker change | The same walk; test 12's test resource |
| The check runs in the request transaction, after validation, before the save | The hook (`PrepareCandidateFunc`) |
| An order fits the quota of its project, each ancestor, and the tenant | The check; tests 4, 18, 21 |
| Quota fails closed: unreadable state blocks the save and rejects the order | The shared request transaction |
| A resource counts once: its own declaration, or its parent's creation edge | The linkage filter; tests 16, 17 |
| A controller creates sub-resources with their linkage set on the creating write | The conformance test (test 16) |
| Linkage is honored only on `creator: system` writes | Immutable-columns trigger; update masks (OSAC-7296); test 20 |
| A family is deleted children-first; between the steps usage reads high, never low | The cleanup path; test 19 |
| One tenant's orders never wait on another tenant's lock | `SELECT ... FOR UPDATE`, tenant scope locked first |
| Orders serialize on the scopes they share: the tenant, an ancestor | The shared envelope requires it; test 4 |
| The `system` and `shared` tenants are never checked | The hook skips them (test 15) |

### Running example

| Who or what | It is |
|---|---|
| Dana | The Cloud Provider Admin. |
| `dev@acme` | A tenant user. |
| `vm-7` | A VM of instance type `small`: 2 vCPUs, 8 GiB. |
| `prod` | A cluster with node set `compute`, workers of bare-metal type `acme-1tb`. |

Acme's tenant limits:

| Dimension | Limit |
|---|---|
| `compute.vcpus` | 10 |
| `compute.memory_gib` | 32 |
| `bare_metal.instances.acme-1tb` | 10 |
| `caas.control_planes` | 5 |
| `network.external_ips` | 20 |

Dana has set a vCPU quota of 8 on each project. The projects oversubscribe, 8 and 8 against the tenant's
10. Both caps apply, so the tenant envelope binds.

| When | What happens |
|---|---|
| 09:00 | Onboarding copies Dana's default limits into acme's rows. |
| 09:00 | System-created default networking: one NAT gateway, one IP. Both count toward usage; the check is skipped. |
| 09:30 | Acme's tenant admin sets a warning threshold at 40 percent of the vCPU dimension. |
| 10:00 | `dev@acme` submits cluster `prod`: node set `compute` of 3 workers, plus two endpoint IPs. |
| 10:00 | Locks tenant then project rows, counts usage, sums holdings: 1 control plane, 3 `acme-1tb`, 2 IPs. |
| 10:00 | Everything is within both caps, so the order commits. |
| 10:00:01 | The controller creates the 3 workers and 2 IPs. Each carries its declared linkage to `prod`. |
| 10:05 | `dev@acme` submits `vm-8` (6 vCPUs) while a script submits `vm-9` (2 vCPUs). Held: 2 vCPUs on `vm-7`. |
| 10:05 | The two orders serialize on the lock. `vm-9` commits first: usage 4, and the threshold event rides along. |
| 10:05 | `vm-8` is rejected by the project scope: vCPUs, project `web`, limit 8, in use 4, requested 6. |
| 10:10 | `dev@acme` scales `compute` from 3 to 5. The check sums the difference: 2 more, held 3, limit 10. |
| 10:15 | `dev@acme` scales the node set from 5 to 12. Rejected: `acme-1tb`, limit 10, in use 5, requested 7. |
| 10:20 | `dev@acme` submits `vm-10` (4 vCPUs) in `web`. It commits: project usage 8, tenant usage 8. |
| 10:25 | `vm-11` (3 vCPUs) in `app` is rejected by the tenant scope: vCPUs, limit 10, in use 8, requested 3. |
| 10:25 | The project scope would allow it: `app` has 8 free. The tenant envelope has 2 left, and 3 exceeds it. |
| 11:00 | Dana lowers the tenant vCPU limit from 10 to 2. `vm-7`, `vm-9`, and `vm-10` keep running. |
| 11:00 | New VM orders are rejected, and the tenant view shows usage 8 against limit 2, per project and overall. |
| 11:30 | `dev@acme` deletes `vm-9`. Usage drops to 6 when the delete commits. |
| 12:00 | `dev@acme` submits cluster `staging`. The order commits and holds its full amount from submission. |
| 12:30 | Provisioning fails; the cleanup deletes the family children-first; usage drops with the rows. |

## Behavior changes

- A create, resize, or scale up that carries a hold is checked against the quota of its project, each ancestor
  project, and the tenant, before the save. An order over any cap is rejected, naming the scope that failed.
  Concurrent orders for one tenant serialize on the scopes they share.
- Creation relationships are declared in the registry, beside the holdings: what an order implicitly creates, and
  which field on each created row carries the link.
- New APIs and tables: an admin limits API covering both scopes, a tenant-facing usage view with a
  per-project breakdown, threshold and increase-request services, and the tables behind them. Onboarding
  copies the deployment's default limits into the tenant's rows.
- Quota writes threshold and rejection events to its outbox, and a publisher drains them to
  `osac.notifications.<tenant>`. The reserved `system` and `shared` tenants stay outside quota, matching the
  billing design's exemption.

## Goals and Non-Goals

### Goals

- The PRD's dimensions, enforced per tenant and per project.
- Composite orders summed whole: a cluster order covers its control plane, its workers, and its endpoint IPs.
- A tenant-facing usage view, an admin API for limits, and an increase-request workflow.

### Non-Goals

- Budget quota, limits in currency, and billing enforcement. They build on this foundation later.
- Label-scoped quota. The PRD scopes quota to the tenant and its projects.
- Fair-share, borrowing, preemption, and expiring allocations. The PRD rules them out.
- Capacity reservation. A limit permits provisioning up to an amount and guarantees no hardware.
- Quota on workloads inside a tenant's own cluster or VM. OSAC cannot observe them.
- MaaS token and request rate limits. A rate over a time window is a separate PRD.
- Historical usage reporting. The tenant view shows current usage against limits.

## Design Details

### Dimensions and declarations

A dimension is a resource kind and its unit, spelled as one flat key such as `compute.vcpus`. A typed dimension
embeds the class name: the storage tier, the GPU type, the bare-metal instance type. Limits are stored per tenant
or project and dimension, so a new class is a new key, which is a row of data. The initial dimensions, from the PRD:

| Dimension | Unit | Held by |
|---|---|---|
| `compute.vcpus`, `compute.memory_gib` | cores, GiB | a VM, through its instance type |
| `compute.gpu.<type>` | count | a VM, through its instance type |
| `storage.volumes`, `storage.<tier>.gib` | count, GiB | a volume |
| `images.count`, `images.gib` | count, GiB | a tenant-uploaded image |
| `network.external_ips` | count | an external IP |
| `network.nat_gateways`, `network.virtual_networks` | count | a NAT gateway, a virtual network |
| `bare_metal.instances.<instance type>` | count | a standalone instance, a cluster node set |
| `caas.control_planes` | count | a cluster |

A resource's proto declares its holdings beside its fields, the way metering's annotations declare tracked fields.
No new proto fields are added: each annotation rides an existing field, and the kind says how the held amount is
derived from it. Four kinds cover every case, and a hold may carry a guard, a boolean field that switches it on:

| Kind | The resource holds | Example |
|---|---|---|
| count | one of the dimension | a virtual network holds one `network.virtual_networks` |
| field | a field's value of the dimension | a volume holds its `size_gib` of `storage.<tier>.gib` |
| through | the holds a referenced type declares | a VM holds its instance type's vCPUs and memory |
| set | per map entry, its size times the referenced type's holds | a node set holds size times the type's count |

The `set` shape (the final proto option syntax is settled in implementation):

```proto
message ClusterSpec {
  map<string, ClusterNodeSet> node_sets = 3 [(osac.private.v1.quota) = {
    set: {dimension: "bare_metal.instances.{baremetal_instance_type}", size: "size"}
  }];
}
```

A `through` hold resolves the reference and reads the referenced type's current declaration. An instance type
declares its vCPUs and memory as field holds, so a VM inherits them. A bare-metal instance type declares one
count of its own key, so a standalone instance holds one and a node set holds its size of that key.

A registry, `proto/quota`, mirrors `proto/metering`: it walks the compiled private protos, collects every quota
annotation, and fails loudly on an invalid one; test 11 lists the cases. The walk stays separate from metering's
package: metering refuses repeated and map fields, and quota's `set` kind lives on a map field, so the walker is
extended either way. The checker and the tenant view read this one registry. The dimension keys live in the
annotations and the limits rows; no Go map of dimension names exists to edit.

**A new service is data.** A WaaS proto that declares a `set` on its WaaS2 pools, with the WaaS2 type declaring
its own holds, is enforced with no engine change. Test 12 proves it with a test resource.

### Where the check sits

Fulfillment serves every write through one shared CRUD path: the public server maps the object, the private
server validates it, and `GenericServer` saves it through the DAO. A gRPC interceptor opens one transaction per
request and commits on return; triggers capture the save into the `changes` outbox in that transaction.

The quota check is one hook in that path. `GenericServerBuilder` installs it for every resource whose proto
declares a hold, and the hook runs in candidate preparation (`PrepareCandidateFunc`): after validation, before
the save, on create and update alike. On update it sees the stored object and the proposal, so it sums the
difference. Controllers write through the private API, so their writes reach the same hook; sub-resource creates
pass it by the bypass rule (see Composite resources and ownership).

What the caller sees:

- gRPC: `FAILED_PRECONDITION`, reason `QUOTA_EXCEEDED`, with the scope that failed, the dimension, the limit,
  the usage, and the requested amount. A composite rejection names the part of the order that hit the limit.
- REST: the gateway maps `FAILED_PRECONDITION` to 400 with the same body. The message names the quota, so a
  quota denial is told apart from a permission denial from the error alone.
- A dry-run create runs the check and returns the candidate without saving, so a Tenant User can see whether an
  order fits before submitting it. The tenant view (below) shows the headroom per dimension.

### Counting usage, atomically

A scope is the tenant or one project, and an order's scope chain is its project, each ancestor project, and
the tenant. Projects nest: a project's parent is named by its `metadata.project` field. A project's usage is
the rows in its whole subtree, nested projects included. Both a project's parent and a resource's project
are immutable, so a row's chain is fixed at creation. The count resolves a subtree with a recursive query
over the project parent pointers.

The check runs inside the request transaction, in four steps:

1. Lock the limit rows in `quota_limits`: the tenant-scope rows first, then the order's ancestor project
   rows, from the root ancestor down to the order's project, each `SELECT ... FOR UPDATE` ordered by
   dimension. The sequence is the same for every check.
2. Count held usage for every scope in the chain: a project's subtree rows, and the tenant's rows across all
   projects. Each count is one SQL aggregate per resource kind over the existing tenant index, `SUM` with
   the linkage filter (an empty aggregate reads as zero). The filter skips rows whose linkage field is set,
   because their parent holds them. No rows are materialized in the application.
3. Sum the order's holdings from the candidate, including its sub-resources.
4. Compare per dimension against every cap in the chain: each scope's subtree usage plus requested against
   that scope's limit. Over any cap: return the error naming the scope that failed. The transaction rolls
   back and nothing is saved.

The lock is the tenant's own rows, so one tenant's orders never wait on another tenant's lock; only
same-tenant orders serialize. Orders meet on the scopes they share: the tenant's rows always, and an
ancestor project's rows when both orders are in its subtree. It is taken before any resource row is
touched, and counting reads rows without locking them, so deadlocks cannot form between two orders. This is
the row-lock pattern the external IP pools already use for capacity, with the tenant as the unit of
serialization.

Each count is bounded by the tenant's own limits, because quota caps how many rows a tenant can hold. The
cases outside that bound: lowered limits, system-created machinery, and direct SQL writes.

Deleting a resource moves its row out of the active set in the delete's transaction, so usage is released with
no quota code on the delete path. A delete only lowers usage, so it needs no limit check; it still evaluates
threshold crossings (see Quota events). Resizes and scale ups sum the difference: the proposal's hold replaces
the stored object's hold, and the check compares the increase against headroom. A resize that raises one
dimension passes while another is over limit; only orders that raise the over-limit dimension are rejected. A
decrease always passes.

A resource's project is immutable: the existing immutable-columns trigger rejects a change to it, so the check
never prices a move between scopes. Moving a resource between projects is delete and recreate.

**A family is deleted children-first.** Deleting the parent while linked children linger understates usage:
the children are excluded by their linkage, and the parent's composite is gone, so a concurrent order consumes
phantom headroom. Children first keeps usage reading high between the steps, the safe direction: a spurious
rejection, never an over-admission. The cleanup path deletes this way; test 19 holds it.

**A granted order holds its full amount from submission.** The order's row commits at submission and carries the
full hold, including sub-resources the controller creates later. Later orders see the committed hold, so the
granted order always has room for its workers. When provisioning fails and the cleanup deletes the resource,
usage drops with the rows. A resource the tenant keeps counts until the tenant deletes it, whatever its state:
running, idle, or stopped.

**Quota fails closed.** The check and the save share one database and one transaction, so a quota state that
cannot be read also blocks the save, and the order is rejected. A tenant always owns limit rows: onboarding
creates them, and a startup sync adds rows when new dimensions ship. A check that finds a dimension without a
row fails closed with an internal error, because that state means the deployment is broken.

### Composite resources and ownership

Provisioning one resource can provision others under it: a VM with an auto IP creates one ExternalIP; a cluster
creates its workers and, with endpoint IPs enabled, two more. Creation relationships are declared in the
registry, beside the hold declarations. Each edge names the resource created, the existing field on the
created row that carries the link, and the value shape of that link. The count matches the declared shape
exactly. The fields already exist: a worker's `status.cluster`, an endpoint IP's attachment, the auto-created
IP's `osac.openshift.io/owner-reference` annotation. That annotation already carries a raw fulfillment ID in
some places and a `Kind/name` composite elsewhere: the subnet proto writes one, the bare-metal worker
ownership check the other. Two edges on one key with different shapes would break matching. The typed
references are status fields the server owns, so a tenant cannot set them; the annotation is the one the
bypass rule protects. The registry is the one source of truth for what an order implicitly creates.

**Who creates a resource decides how it counts.** A resource the system creates while executing an order carries
its creation edge and counts inside its parent's composite. A resource the tenant creates and attaches later
counts standalone, always, because the parent's order cannot know at provisioning time. Attachments never
affect counting.

A guard field covers optional auto-creation: a VM order that requests an auto IP carries the IP's hold, and one
that does not, does not.

**The bypass rule.** A write whose creator is `system` skips the check and still counts; the hook runs for
these writes and lets them through. Linkage is honored only on these writes: the server assigns `creator`, so
a tenant cannot claim `system`. A tenant write carrying a linkage annotation is rejected with an
invalid-argument error. The `osac.openshift.io` annotation domain is tenant-writable, and a forged link would
hide a resource from the check and the count. A linked write must name an existing parent in the same tenant.
A system write is onboarding machinery or the execution of a granted order; any other system write rides a
granted order. Default networking is created for a whole tenant at onboarding with no parent resource, and
the bypass covers its write. Blocking it would make a new tenant unusable while dimensions default to zero.

**CI rejects undeclared creation paths.** A code path that creates a resource on behalf of another declares
its creation edge in the registry first. The conformance test fails on an undeclared path (see the Test Plan).

### Limits, defaults, and the tenant view

Three new tables, all regular resources served by the generic server, so they get change events and audit
capture with no extra machinery:

- `quota_limits`: one row per scope and dimension (a null project column means tenant scope), the limit and
  whether it came from a default. Locked by the check; written by the admin API and by onboarding.
- `quota_thresholds`: one row per scope and dimension, a warning percent. The same shape as the limits.
- `quota_outbox`: threshold and rejection events, drained by the publisher.

The limits and thresholds carry a partial unique index on the tenant-scope rows (`WHERE project IS NULL`). A
plain composite unique index treats two nulls as different, so a duplicate tenant-scope row could slip in.

Default limits live in `quota_default_limits`, one row per dimension, owned by the Cloud Provider Admin. The
tenant reconciler, which already creates default networking, copies them into the tenant's rows at onboarding;
later default changes apply to new tenants. A dimension with no default row reads as zero, so a tenant can
start over its limit: default networking counts against a zero limit. The system write skips the check, the
view flags the over-limit state, and orders on that dimension are rejected until the admin sets a limit. Quota
is greenfield: every tenant is onboarded after the defaults exist.

**An absent project row means no project cap; the tenant's cap still applies.** Tenant admins create projects,
and a zero-default would make every new project unusable until the provider configures it. The GCP-style
alternative, copying defaults at project creation, stays a later option.

**Project quotas may oversubscribe.** The projects' limits may sum above the tenant's: 8 and 8 against a
tenant limit of 10. Both caps apply to every order, so the tenant envelope binds.

The dimension vocabulary is generated from the annotations and published as versioned contract artifacts,
following the metering event contract's generator pattern (OSAC-6056). A published version never changes; a new
dimension is a new artifact version.

**A published key never changes meaning.** A rename is a new key plus an admin-executed migration of the limit
rows to the new key, under the tenant lock. A change to a declared hold, an annotation edit or a referenced
type's edit, takes effect on the next count. A tenant may land over its limit; the over-limit rules apply.

The APIs:

- `QuotaLimits`, Cloud Provider Admin: get, list, and set a limit per dimension, for the tenant or, with the
  optional project, for one project. A change takes the same locks as a check, in the same sequence, so a
  check never reads a limit mid-change.
- `TenantQuotas`, tenant read: per dimension, the tenant limit, usage, headroom, and over-limit flag, plus a
  per-project breakdown against the project caps. Computed on demand with the counting code and no lock.
  Powers the UI (OSAC-4504, OSAC-4505) and the CLI.
- `QuotaThresholds`, Tenant Admin: set and clear warning thresholds, for the tenant or for one project.
- `TenantQuotaRequests`: the increase workflow; with every dimension defaulting to zero, an admin's limit
  change is the only way to unblock a tenant, so it lands with this foundation. Approval writes the limit
  through `QuotaLimits`; denial records the reason.

Every quota change is a row change on a quota table, captured by the `changes` outbox like any resource change
and folded by the audit design. That gives the who, when, previous value, and new value; the acting user arrives
on events with request capture (OSAC-6154).

### Quota events

Quota follows the notifications design's emission rules:

- **A threshold crossing rides the mutation's transaction.** The crossing evaluation runs on every mutation
  that moves usage or a limit: an accepted order, a delete, an admin limit change. The event is written into
  `quota_outbox` in the same transaction as the mutation, so the event exists exactly when the change commits.
  Crossing back writes a cleared event.
- **A rejection is written after the abort.** The request transaction rolled back, so quota writes the
  rejection event in its own small committing transaction, naming the dimension, the limit, and the usage.
- **A publisher drains the outbox** to `osac.notifications.<tenant>`, the side-channel topic family. The event
  types are `osac.quota.threshold.crossed.v1`, its cleared variant, and `osac.quota.rejected.v1`. A threshold
  is warning severity. A condition opens once per crossing, keyed by scope and dimension: one notice, then
  silence until usage drops below and crosses again.
- **A delivery failure never fails the flow that caused it.** The publisher owns retries and quarantine, per
  the notifications design.

### Rebuild and recovery

Usage has no stored copy to lose or recompute; see Invariants. A recount at any time produces the same numbers
when nothing changed. Direct SQL writes are counted, because they are rows, and they skip the check, the
operational escape hatch today's guards already offer. Quota's own tables hold configuration: limits,
thresholds, requests. They restore with the database, and the change log holds every change to them.

### What happens when

| Situation | What happens |
|---|---|
| Two orders race for the last headroom | The lock serializes them; the second is rejected when it no longer fits. |
| An order is rejected | Nothing is saved; see the error format under Where the check sits. |
| Provisioning fails after the order commits | The cleanup deletes the family children-first, and usage drops. |
| The cleanup itself fails | Usage reads high, never low; the parent lingers with its composite. Cleanup retries. |
| A tenant keeps a resource in a failed state | It counts until the tenant deletes it. |
| A limit is lowered below usage | Resources keep running; orders on that dimension are rejected; the view flags it. |
| A declared hold changes | The next count reflects it, and the over-limit rules apply (see the row above). |
| A write with its linkage set | Bypass for `creator: system`; rejected for a tenant creator. |
| The CSI driver creates a volume for a PVC | Open question; see Open Questions. |
| Quota state cannot be read mid-order | The order is rejected; quota fails closed. |
| A tenant is offboarded | Its limit, threshold, and request rows go with the tenant. |

## Risks and Mitigations

- **The check pays two counts per write, project and tenant.** Each count is bounded by the tenant's own
  limits and runs while holding the tenant's lock, so a slow count widens that tenant's serialization window
  (see Counting usage, atomically). If profiling shows a cost at scale, usage moves to a stored table whose
  updater is generated from the registry. A hand-written SQL copy of the holdings is the one thing this design
  forbids. The count stays as the auditor: a recount must equal the stored totals, as a test and as the repair
  path. The cost of the fallback: the trigger fires on every row write, including status-only updates.
- **The annotation shape is the hard part.** Composites and catalog lookups are where declarations get
  intricate. The registry fails loudly on a bad annotation, and the registry is quota's one copy of the
  holdings, where metering keeps a SQL twin beside its own.

## Drawbacks

The declaration work lands on every team that adds a resource type: annotations are now part of what a new
offering ships. A tenant's checked writes serialize on one lock, so one slow order adds its latency to the
next order's wait (see Risks).

## Alternatives

- **A separate quota service with its own database.** The check would race the request outside its transaction,
  which the core architecture forbids, and the count needs the resource rows, which live in the fulfillment
  database.
- **Usage counters maintained by database triggers.** A second SQL copy of the holdings, with JSON extraction
  and catalog joins in SQL, plus a recompute path after incidents. It buys speed the foundation does not
  need yet.
- **A transaction-scoped advisory lock for serialization.** The lock would store nothing, and the limits table
  exists anyway. The row lock keeps the serialization point visible to row-based deadlock analysis.
- **An async check that reconciles over-limit tenants.** Rejection would arrive after provisioning began,
  which the PRD rules out.
- **Quota as a consumer of the metering pipeline.** Metering reports consumption over time and eventually;
  quota needs instantaneous holdings decided in under a second. Quota reuses metering's declaration mechanism
  and leaves the metering event contract alone.
- **Counting a linked child as standalone when its parent is absent.** It turns the linkage filter into a
  parent-existence join on every count.

## Open Questions

**CSI volumes: block at the driver, or count without blocking.** A tenant creates a PVC inside its cluster.
Kubernetes admits the PVC at once, and OSAC plays no part at admission. The CSI driver then calls volume
create on the fulfillment private API, carrying the tenant and project taken from the PVC. The options:

- Block at the CSI driver. The volume-create call goes through the quota check. An over-quota PVC stays
  Pending, with the quota reason in its events. Kubernetes natively holds pods that wait for a pending PVC.
  Blocking here settles the bypass edge: the driver's writes go through the check and count as tenant
  writes, so the `creator: system` bypass does not cover them.
- Count without blocking. The driver's writes count toward usage and never reject. A tenant can exceed its
  storage quota through its cluster, with no rejection.

Blocking at the driver has a trust gap. The driver runs inside the tenant's cluster, sends the tenant from
the PVC's parameters, and carries no cluster identity, so the server cannot check which tenant is asking
(`osac-csi-driver/pkg/fulfillment/grpc_client.go`). Blocking would key quota on a client-asserted tenant:
one tenant cluster could consume another tenant's storage headroom, or dodge its own quota. Blocking at the
driver is sound once the server derives the tenant from the calling cluster's identity. That means
per-cluster driver credentials, or cluster provenance on the volume API checked against the cluster's owning
tenant.

## Test Plan

Behaviors to check, grouped: the PRD's criteria first, then the mechanism.

PRD criteria:

1. Every dimension defaults to zero: an order on an unconfigured dimension is rejected.
2. A new tenant starts with the configured default limits.
3. Raising and lowering a limit takes effect at once; lowering below usage blocks new orders and terminates
   nothing.
4. Concurrent orders for one tenant, in one project or across projects, cannot together exceed a limit that
   any one of them alone would fit. Submit parallel orders for the last headroom and count the acceptances.
5. A rejection names the scope that failed, the dimension, the limit, the usage, and the requested amount. A
   composite rejection names the underlying dimension and the part of the order that hit it.
6. Usage stays accurate through a failed order: the cleanup releases it.
7. A composite order is summed whole: a cluster order covers its control plane, its workers, and its endpoint IPs.
8. A resource counts from creation until deletion, whether running, idle, or stopped.
9. A threshold crossing writes the event in the mutation's transaction, on an accepted order, a delete, or a
   limit change; crossing back clears it; one notice arrives per crossing.
10. The tenant view shows usage, limits, headroom, the over-limit state, and the per-project breakdown, and a
    recount of the rows equals the view's usage.

Mechanism:

11. The registry fails loudly on an invalid annotation: a wrong path, an unknown reference, an unreachable field.
12. A new resource type with annotations is enforced with no checker change, proven with a test resource.
13. Every quota change is captured by the change log with the previous and new values.
14. A sub-resource write with `creator: system` and its linkage set skips the check and still counts.
15. The `system` and `shared` tenants are never checked.
16. A conformance test maps every controller code path that creates a resource on behalf of another to a
    declared creation edge, and fails on an undeclared path. It also asserts that the linkage field is set on
    the creating write. Late linkage double-counts the row until it lands, so later orders in that dimension
    are spuriously rejected. The test also checks the public paths. Every create and update path on a
    linkage-carrying resource strips or ignores status, so a tenant cannot set a typed-reference linkage
    through a public path. Status-stripping is a per-path convention, and OSAC-6834 records a path that
    missed it.
17. A sub-resource row whose declared linkage field is set is counted once, through its parent's composite,
    and never standalone.
18. Both caps apply on every order. An order over the tenant quota is rejected naming the tenant scope, and
    an order over the project quota is rejected naming the project scope.
19. A family is deleted children-first: an order submitted between the delete steps sees usage high or exact,
    never low, so headroom is never overstated.
20. A tenant write carrying a linkage annotation is rejected with an invalid-argument error; the same write
    with `creator: system` takes the bypass. A linked write naming a missing parent, or a parent in another
    tenant, is rejected.
21. An order in a nested project is checked against every scope in its chain: the project, each ancestor
    with a limit row, and the tenant. A rejection by an ancestor names that ancestor.

---

## Provenance

Authored: design draft, 2026-11-03, from the merged PRD and the quota research digest.
Revised: 2026-11-04, review answers applied to ownership, open questions, and the resize rule; full revision
pass the same day: invariants table, hold vocabulary, composite compression, query cost and fallback.
Revised: 2026-11-04, project scope per Omer; coderabbit: hold changes, children-first deletes, bypass, crossings.
Revised: 2026-11-04, coderabbit round 2: linkage trust gate, null-scope unique index, immutable project column.
Revised: 2026-11-05, codebase-audit hardening: CSI trust gap, linkage value shapes, creator gate, status test.

> Authoring phases not recorded this session.
