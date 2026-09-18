# Researcher Machines: portable personal GPU machines for AI teams

| Field       | Value   |
|-------------|---------|
| Author(s)   | Oleg Silkin <osilkin@redhat.com> |
| Jira        | [OSAC-3446](https://redhat.atlassian.net/browse/OSAC-3446) |
| Date        | 2026-07-30 |

## Problem Statement

AI researchers and ML engineers need a personal GPU machine to do their daily
work: a system they own, with their tools installed, that keeps their
environment intact over weeks of experimentation. Today OSAC provisions
clusters, VMs, and bare metal for tenant admins, but there is no answer for
the individual researcher on top of that infrastructure. In practice research
teams hand-build SSH fleets on raw GPU nodes, and every team builds it
differently. These are real problems our team has hit running exactly that
kind of hand-built fleet:

**Environments pinned to nodes misallocate scarce GPUs.** When an environment
lives on one node, freeing that node for a serious multi-node job means
asking people to abandon working experimental setups, which turns every
reshuffle into a negotiation. Worse, people develop loyalty to whatever node
their environment lives on even when it hurts them. A concrete example from
our own team: months of paper experiments ran on an A100 machine at roughly
4x the runtime, while an H100 machine sat idle, purely because the
environment was already on the A100. Portable environments make node choice
a scheduling decision instead of a sunk cost.

**Researchers need to experiment without risking heavy loss.** Installing
packages is daily work, and supply-chain attacks on npm and PyPI are now
routine. On a shared hand-built node, one bad dependency can have a blast
radius of the whole cluster. For someone working toward a paper deadline or
a rebuttal, that is devastating. Each researcher needs an isolated machine
where a broken or compromised environment is contained to that machine and
recoverable from storage, and where copying an environment before a risky
change is one action.

**Training artifacts live in the wrong place because speed wins.** Training
jobs write large numbers of checkpoints. Teams keep them on the node's local
drives because local reads and writes are fast and cloud storage is not. On
many cloud GPU instances those local drives are ephemeral, so a node failure
or stop takes the artifacts with it. That trade cost members of our team
real work within the last week when a node went down. It also scatters
artifacts across nodes where nobody can find them later. The storage layer
has to remove the trade-off: a directory that reads and writes at local
disk speed but is transparently and asynchronously backed by the provider's
cloud storage, so the fast path and the durable path converge.

**Hand-built fleets drift, and then nobody can update them.** On a
long-lived bare-metal fleet, node configuration drifts: driver versions
diverge, nobody can say with confidence what is installed where, and updates
happen ad-hoc, disrupting whoever else was on the node or breaking someone
else's setup. Worst of all, necessary updates stop happening: a CVE that
needs a critical system update waits, because patching means taking down
nodes where people are running paper experiments. Separating the layers
fixes the standoff: admins manage a uniform, boring node layer they can
patch by moving machines off a node and back, users get complete control
inside their own machines, and the platform can see what is actually
running across the fleet, so drift and exposure become measurable instead
of folklore.

**CPU work squats on GPU nodes.** GPU nodes ship with generous CPU and RAM,
so people run CPU-only workloads on them. This slows the GPU jobs the nodes
exist for, makes true utilization impossible to track, and leaves CPU users
as second-class citizens: an admin who sees no GPU activity assumes a reboot
is safe and destroys their work. CPU-only machines on dedicated CPU nodes
need to be a first-class part of the same system, with the same environment
portability, so CPU work has a legitimate home.

Going all-in on a cluster platform does not solve these problems for a
research team either: it asks researchers to learn cluster-specific idioms,
most solutions end up working around the platform rather than with it, and
in large organizations installing even one helpful operator can mean weeks
of approvals. Small and mid-size teams end up needing to become
infrastructure experts to do model research. The missing piece is a layer
that gives researchers simple, safe, portable machines on top of the
infrastructure the platform already provisions.

This is also distinct from notebook-centric environments such as OpenShift AI
workbenches or Dev Spaces. Those provide a containerized IDE or notebook
session on a cluster; this proposal provides a full system machine the
researcher owns: root access, systemd, SSH as the front door, arbitrary
system packages that persist across restarts and hardware moves, and a
lifecycle measured in months. The two are complementary: a workbench is a
session on someone else's infrastructure, a researcher machine is
infrastructure of your own.

This proposal is based on a system designed and built by the Red Hat AI
Innovation team, running in production with real users since July 2026. We
propose contributing its design and operational lessons as an OSAC service,
with the intent that the service is owned and maintained within OSAC and our
team becomes its first tenant. We have also received independent interest in
this capability from a commercial GPU cloud operator, so the gap extends
beyond internal research teams to commercial GPU providers.

## In Scope

- A Machine resource usable from UI, API, and CLI: request a machine by
  naming a hardware pool and a GPU count (zero for CPU machines), then
  start it, stop it, move it, delete it. CPU, memory, and storage
  entitlements are derived from the pool's published hardware profile, so
  a request is always just those two choices. Zero-GPU requests are valid
  only for CPU pools; GPU pools reject them at create and at move, so CPU
  work can never occupy a GPU node. Automation (for example CI jobs)
  drives machines through the same API as humans.
- Sub-node GPU sharing: several users share one GPU node. A request for N
  GPUs succeeds with all N or fails with none; no partial allocation ever
  persists. A machine's claim is exactly its running allocation, and
  stopping a machine frees its GPUs immediately. All pool-derived
  entitlements are platform-enforced: memory limits are hard, CPU and
  storage allocations are bounded, and a machine sees only its own
  assigned devices, so no machine can consume a neighbor's entitlement.
- Environment portability across heterogeneous hardware: the same environment
  moves between nodes, between GPU models (for example L40S and H100),
  between GPU counts, or onto a CPU-only node, with identical contents
  throughout. Moves are fast enough to be routine: seconds when the
  destination has hosted the machine before, on the order of a minute
  otherwise.
- A durability contract on stop and move: a stopped machine's state is
  fully persisted before its resources are released, so a machine that
  reports stopped can always be started elsewhere with nothing lost. A
  move is transactional: it completes with the machine intact at the
  destination, or it fails leaving the source environment untouched and
  every destination claim released.
- A standard machine image with the research toolchain preinstalled, plus a
  first-boot self-check that reports honestly whether the machine is healthy.
- A per-user data directory that reads and writes at local disk speed and
  becomes durable independently of the node within a bounded window after
  each write; in-flight writes inside that window are the only allowed
  loss on sudden node failure. Training checkpoints and datasets get local
  speed without local risk, regardless of the node's storage type.
- Copying an environment as a new machine. A copy is point-in-time
  consistent (snapshot semantics) and succeeds only when a complete
  consistent environment exists; a failed copy leaves nothing behind. A
  copy belongs to the same owner, and machine-level identity (host keys
  and any per-machine credentials) is regenerated rather than cloned.
- Sharing a machine with another user: pick them from a user list, and the
  machine appears in their UI with their own login command. Sharing adds
  the invitee's own identity; the owner's credentials are never
  transmitted. Invitees receive login access as their own user; lifecycle
  control (start, stop, move, delete, share) stays with the owner. The
  owner can unshare at any time, which removes the invitee's login and
  access immediately. Because a share grants access to the machine, its
  contents become visible to the invitee, and the UI states this plainly.
- Defined deletion semantics: deleting a machine removes the machine and
  all of its stored environment state, including copies and backups. Any
  retention window before permanent removal is an explicit provider
  policy, never a hidden default.
- A deliberately minimal tenant UX: five actions in the first milestone
  (create, launch, stop, move, delete), with copy and share arriving as
  additional actions in later milestones, and every failure surfaces one
  plain sentence with a support reference code.

## Out of Scope

- Replacing VMaaS or BMaaS. This layer consumes them as substrates.
- Batch scheduling and job queues.
- Building the multi-node network fabric. The machine design must not
  preclude attaching fast inter-node networking to a group of machines
  later, but the fabric itself is follow-on work.
- Model serving (Models-as-a-Service territory).

## User Stories

### Tenant User (AI researcher or ML engineer)

- As a Tenant User, I want to request a machine with 2 GPUs on a shared node
  and be working over SSH within a minute, so that getting compute does not
  involve coordinating with other users over chat.
- As a Tenant User, I want my resource claims enforced by the system, not by
  etiquette: while my machine holds its GPUs, nobody else can take or use
  them no matter what they run. Honor-based reservations work for very
  small teams and turn into permanent system debt as the team grows, which
  is exactly the situation hand-built fleets end up in.
- As a Tenant User, I want to install system packages (for example dnf install
  nvtop) and have them persist across restarts and hardware moves, so that
  my machine stays mine.
- As a Tenant User, I want to stop my machine at the end of the day knowing my
  environment is safely stored and my GPUs are released to teammates, so
  that stopping work does not cost me my setup or the team its capacity.
- As a Tenant User, I want to move my environment from an L40S machine to an
  H100 machine (or down to a CPU-only machine for light work) without
  rebuilding anything, so that I can match hardware to the current phase of
  my work.
- As a Tenant User, I want that move to be fast and seamless: seconds when a
  node has seen my machine before, about a minute otherwise, so that
  relocating is something I do without thinking rather than a chore. Any
  system can copy environments around with bulk file transfer; doing it
  slowly burns network bandwidth and eats time I could be spending on
  experiments, which in practice means people stop moving at all.
- As a Tenant User, I want to make a copy of my machine before a risky
  change (a dependency upgrade, an unfamiliar package), so that if it goes
  wrong I throw away the copy instead of my working setup.
- As a Tenant User, I want the system to remember things I provide once (SSH
  keys, git identity, common tooling preferences) and apply them to every
  machine I create, so that a new machine is ready to use immediately
  instead of starting with a setup checklist.
- As a Tenant User, I want my training checkpoints in a directory that reads
  and writes at local NVMe speed but is backed by cloud storage, so that a
  node failure never costs me artifacts and I never have to choose between
  fast and safe.
- As a Tenant User doing CPU-only work (data processing, evaluation), I want
  a CPU machine on a dedicated CPU node that is a first-class citizen of the
  system, so that my long-running work is not squatting on a GPU node where
  an admin might reboot it out from under me.
- As a Tenant User, I want to share my machine with a collaborator so it
  appears in their UI with their own login, so that pair-debugging a
  training run does not require sharing credentials.
- As a Tenant User, when something fails I want one plain sentence and a
  reference code, so that I can hand support something actionable without
  writing a bug report.

### Tenant Admin

- As a Tenant Admin, I want to see every machine, who holds which GPUs and for
  how long, with idle holds flagged, so that I can reclaim scarce capacity
  without interrogating people.
- As a Tenant Admin, I want to free up a whole node for a multi-node job by
  having its machines move elsewhere in minutes with nothing lost, so that
  big jobs do not require negotiating with everyone whose environment lives
  there.
- As a Tenant Admin, I want to organize hardware into named pools and control
  who sees what: a core team member might have access to several pools
  while an external collaborator gets a single node. One admin should be
  able to manage all of this from one page, without becoming an expert in
  cloud consoles or cluster access-control systems.
- As a Tenant Admin, when someone leaves the team I want one action that
  removes their access everywhere: their keys live in one central place, so
  revocation is surgical and complete, including access they had to
  machines other users shared with them.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to onboard a new GPU node by running one pipeline
  against a machine that meets a written hardware spec, so that fleet growth
  is not artisanal work.
- As a Cloud Infrastructure Admin, I want any machine restorable after
  node loss, so that disaster recovery is the same mechanism as everyday
  mobility rather than a separate untested path.
- As a Cloud Infrastructure Admin, I want to patch or rebuild a node by moving its machines
  elsewhere and back, so that critical updates (for example a CVE response)
  never have to wait for someone's experiment to finish.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want machines to be auditable for
  compromise: because every environment is platform-managed, its network
  traffic can be monitored for connections to known-bad destinations, and
  its stored state can be inspected out-of-band for what software is
  installed, without touching the running machine or depending on the
  user. Every privileged inspection is itself resource-scoped,
  authorized, and logged, so audit capability never becomes unaudited
  access to tenant data. If a bad dependency does get in (see the
  supply-chain problem above), incident response starts from platform
  data instead of guesswork.
- As a Cloud Provider Admin, I want automation (CI service accounts) to
  obtain machines through the same admission path as human users, bounded
  by explicit per-account machine caps and pool grants. When capacity is
  exhausted, automation waits or fails; it never displaces a human user's
  machine. Providers can additionally fence automation into dedicated
  pools, so CI load cannot starve researchers even at its caps.

### Automation (service accounts)

- As a Tenant Admin, I want a service account for CI with an API token that can
  request a machine, run a job (for example a GPU benchmark on a pull
  request), and release it, so that automated workloads use the platform
  the same way people do instead of through a side channel.
- As a Tenant Admin, I want those tokens scoped and revocable: a token can
  only manage its own account's machines within its allowed pools, it can
  be revoked at any time, and it goes through the same admission as human
  users, so automation can never starve researchers or escalate beyond its
  lane.

## Terminology

- **Machine**: the unit a user owns and operates; a full system with root
  access, reached over SSH, holding one environment.
- **Environment**: everything inside a machine that makes it that user's
  system: installed packages, configuration, home directory, data.
- **Pool**: a named group of nodes with a published hardware profile;
  admins grant users access per pool.
- **Move**: relocating a machine (and its environment) to a different
  node, GPU model, GPU count, or to a CPU node.
- **Node**: provider-managed hardware that hosts machines; users never
  interact with nodes directly.

## Milestone scoping

First milestone, demonstrably working for users: machine lifecycle
(create, launch, stop, move, delete) with pool-based access and atomic
GPU admission, environment portability with the stop/move durability
contract, the fast durable data directory, and the standard image with
first-boot health check. Later milestones: copies, sharing, service
account tokens, and compromise auditability. End-to-end testing scope,
installation prerequisites, and documentation needs are deferred to the
design document.

## Assumptions

- Tenants using this service have researchers comfortable with SSH as the
  primary way of using their machines. The UI manages machines; work happens
  over SSH.
- The provider runs an object storage service reachable from the GPU nodes
  with reasonable throughput. Mobility performance depends on it.
- The system works regardless of the node's storage type (instance-local
  drives or attached volumes); faster storage makes machines faster, but
  nothing in the requirements depends on a particular storage layout.

## Dependencies

- **VMaaS / BMaaS:** supply the substrate the machines run on. This service
  schedules researcher machines onto capacity those services provision.
- **Identity provider:** user identity and team membership for access
  control and machine sharing.
- **Object storage:** backing store for environment state, mobility, and
  disaster recovery.
