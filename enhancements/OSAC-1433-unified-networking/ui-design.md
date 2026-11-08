---
title: unified-networking-ui
authors:
  - brotman@redhat.com
  - dmanor@redhat.com
creation-date: 2026-08-12
last-updated: 2026-11-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2632
  - https://redhat.atlassian.net/browse/OSAC-1433
  - https://redhat.atlassian.net/browse/OSAC-7299
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking/design.md"
  - "/enhancements/OSAC-1433-unified-networking/ux-design.md"
replaces:
superseded-by:
---

# Unified Networking — UI Design Addendum

## Contents

- [Summary](#summary)
- [Design system](#design-system)
- [Proposal](#proposal)
  - [Information architecture](#information-architecture)
  - [Rules for every networking page](#rules-for-every-networking-page)
  - [Virtual networks](#virtual-networks)
  - [Subnets](#subnets)
  - [Security groups](#security-groups)
  - [NAT gateways](#nat-gateways)
  - [External IPs](#external-ips)
    - [ExternalIP picker rule](#externalip-picker-rule)
  - [External IP pools](#external-ip-pools)
  - [Network class](#network-class)
  - [Provider admin](#provider-admin)
  - [Workload network attachment pickers](#workload-network-attachment-pickers)
- [Decisions](#decisions)
- [Out of scope](#out-of-scope)
- [Failure Handling](#failure-handling)
- [Implementation Details](#implementation-details)
  - [Component tests](#component-tests)

## Summary

The shared `osac-ui` networking pages for the [Unified Networking](design.md) resources ([OSAC-2632](https://redhat.atlassian.net/browse/OSAC-2632); screen-level UX: [OSAC-2226](https://redhat.atlassian.net/browse/OSAC-2226), [OSAC-7279](https://redhat.atlassian.net/browse/OSAC-7279) and [UX design](ux-design.md); UI story [OSAC-7299](https://redhat.atlassian.net/browse/OSAC-7299)): the **Networking** navigation, the list, details, and create pages of each resource, and the provider admin pages, covering [PRD FR-11](prd.md#fr-11-unified-networking-ui-and-documentation). The workload wizards are not part of this addendum, except the shared [Workload network attachment pickers](#workload-network-attachment-pickers), which other designs link to.

## Design system

The UI follows PatternFly 6 (the repository pins `^6.6.1`) and reuses the repository's existing list, details, modal, and wizard components:

- **Navigation.** One expandable **Networking** group; the item of a resource stays active on its details and create routes ([Navigation](https://www.patternfly.org/components/navigation/design-guidelines)).
- **Action placement.** The create action is the primary button in the page toolbar or header; row actions are in a kebab in the last column; details page actions are at the top right ([Actions](https://www.patternfly.org/patterns/actions)). A Delete item is last in its menu and is never red ([Menu](https://www.patternfly.org/components/menus/menu/design-guidelines)).
- **Disabled with a reason.** An action that the user cannot take on a resource stays in its place and is disabled with `isAriaDisabled`, so it stays focusable, plus a Tooltip that says why or what to do: the resource is Default or Auto, a dependent still exists, or a parent is not Ready. Every row of a list keeps the same menu. Only a create that OSAC alone makes (the NATGateway of a tenant default VirtualNetwork) is hidden ([Actions](https://www.patternfly.org/patterns/actions), [Button accessibility](https://www.patternfly.org/components/button/accessibility)).
- **Badges.** **Default** and **Auto** are compact, non-status Labels next to the name, with a Tooltip ([Label](https://www.patternfly.org/components/label/design-guidelines)).
- **Status.** A status is a Label with an icon and text; the API `message`, when set, is in a Popover on the label, which shows a help icon so it reads as clickable. A details page of a FAILED resource shows the message once, in an inline danger Alert titled by what failed ("Provisioning failed", "Security group failed", "The network class is not ready"), with no Popover ([Status and severity](https://www.patternfly.org/patterns/status-and-severity), [Alert](https://www.patternfly.org/components/alert/design-guidelines)).
- **Create forms.** A create is a modal Form: one column, labels on top, inline errors on blur and on submit, primary **Create**, link **Cancel**. A full page form is used only for repeatable rows (**Edit rules**). Long lists use a typeahead Select; fewer than five choices use Radio buttons ([Form](https://www.patternfly.org/components/forms/form/design-guidelines), [Modal](https://www.patternfly.org/components/modal/design-guidelines)). Existing multi-step creates stay wizards ([Wizard](https://www.patternfly.org/components/wizard/design-guidelines)).
- **Batch edit.** Security group rules are edited as one batch on a full page form, not inline row by row, because one Update replaces both rule lists ([Inline edit](https://www.patternfly.org/components/inline-edit/design-guidelines)).
- **Delete confirmation.** Delete opens the repository's existing delete modal: warning title icon, the danger button only in the modal ([Modal](https://www.patternfly.org/components/modal/design-guidelines)).
- **Details pages and links.** A resource gets a details page only when it has more than a list row can show: a VirtualNetwork (its Subnets, SecurityGroups and NATGateway), a SecurityGroup (its rules and **Edit rules**), and an ExternalIPPool (from OSAC-4418). Subnets, NATGateways, ExternalIPs and ExternalIPAttachments fit in their row, and their actions are in its kebab. Only a resource with a page is linked, and so are projects and workloads. A NATGateway links to its VirtualNetwork's **NAT gateway** tab, which works as its page because a VirtualNetwork has at most one. An ExternalIP address and a tenant, which have no page, are plain text. A pool links to its details page for the provider admin only. Every networking link has one style (`NetworkingResourceName`), and a name with its address or kind stays on one line, for example `default (203.0.113.2)` ([Link](https://www.patternfly.org/components/button/design-guidelines)).
- **Lists.** The repository's list pattern: a toolbar with a name search and attribute filters shown as filter labels with **Clear all filters** ([Filters](https://www.patternfly.org/patterns/filters/design-guidelines)), and three empty states: no resources (with the create action), no results (one **Clear all filters**), and load error, in one layout on every networking list ([Empty state](https://www.patternfly.org/components/empty-state/design-guidelines)).
- **Details pages.** Breadcrumb, Title with the status Label, actions at the top right, primary Tabs, and DescriptionLists ([Tabs](https://www.patternfly.org/components/tabs/design-guidelines), [Description list](https://www.patternfly.org/components/description-list/design-guidelines)).
- **Wording.** Sentence case for every label, title, and button ([Capitalization](https://www.patternfly.org/content-design/grammar/capitalization)); "Create \<resource\>", never "New" or "Add" for a resource ([Terminology](https://www.patternfly.org/content-design/grammar/terminology)); success toasts name the result without "successfully" ([Alert](https://www.patternfly.org/components/alert/design-guidelines)).

## Proposal

### Information architecture

**Navigation** (`shellNav.ts`, routes in `AppShell.tsx`). The **Networking** group:

| # | Item | Route | Tenant admin, tenant user | Provider admin |
|---|---|---|---|---|
| 1 | Virtual networks | `/networking/virtual-networks` | Yes | Yes |
| 2 | Subnets | `/networking/subnets` | Yes | Yes |
| 3 | Security groups | `/networking/security-groups` | Yes | Yes |
| 4 | NAT gateways | `/networking/nat-gateways` | Yes | Yes |
| 5 | External IPs (tabs **Addresses** and **Attachments**) | `/networking/external-ips`, `?tab=attachments` | Yes | Yes |
| 6 | External IP pools | `/admin/infrastructure/external-ip-pools` (unchanged; moved here from **Infrastructure**) | No | Yes |
| 7 | Network class | `/admin/infrastructure/network-class` | No | Yes |

The tenant identity provider manager role has no **Networking** group, as today.

**Rationale.** Large public cloud consoles commonly give each networking resource its own list page in the sidebar, so a user finds every subnet or security group without knowing its parent first. Child resources also appear in context on the parent's page, and child lists have a parent network filter that the parent's page links to. Associations, such as an address attached to a workload, are not top-level items; they live with the resource they extend. This layout follows that practice: every resource in the [resource hierarchy](design.md#resource-hierarchy) has a list page, and ExternalIPAttachments are a tab of External IPs.

**Where each action lives:**

| Resource | List page | Details page | Parent's page |
|---|---|---|---|
| VirtualNetwork | Create | Delete | — |
| Subnet | Create, Delete (row) | — (no details page) | VirtualNetwork **Subnets** tab: Create, Delete (row) |
| SecurityGroup | Create | Edit rules, Delete | VirtualNetwork **Security groups** tab: Create |
| NATGateway | Create, Delete (row) | — (no details page) | VirtualNetwork **NAT gateway** tab: Create, Delete |
| ExternalIP | **Addresses** tab: Create, Delete (row) | — (no details page) | — |
| ExternalIPAttachment | **Attachments** tab: Create, Delete (row) | — | Workload details pages (existing attach and detach) |
| ExternalIPPool | Create | Delete | — |
| NetworkClass | — | **Network class**: view only | — |

### Rules for every networking page

- The UI uses only the fulfillment API calls of the [API operation constraint](design.md#api-operation-constraint): List, Get, Create, Delete, and `SecurityGroups.Update`. Its only edit form is [Edit rules](#security-groups); any other change is delete and recreate.
- Status shows the API `state` as a Label and the `message` in a Popover on it ([Status](design.md#status)). A SecurityGroup that is READY with the message `Updating` shows **Updating**. The API has no field that marks the whole rule update: once the message changes to the running task, the group shows Ready with that message in the Popover, and an **Edit rules** save made then gets the server's `FAILED_PRECONDITION` message ([Security groups](#security-groups)).
- A resource with the label `osac.openshift.io/default: "true"` shows the **Default** badge (Tooltip "Created automatically as a tenant default."); an automatic resource shows the **Auto** badge (Tooltip "Created automatically for \<kind\> \<owner\>. It is deleted with it."; the owner is the `auto-created-for` label, which holds the owner's API ID, and an ExternalIPAttachment, which has no kind label, names its target) ([CaaS UI — Automatic resource indicators](/enhancements/OSAC-1436-caas-networking/ui-design.md#automatic-resource-indicators)). Their Delete, Detach, and (Auto) **Edit rules** actions are disabled, because the [deletion guards](design.md#deletion-dependency-guards) always reject them; the Tooltip is "Created as a tenant default. It is deleted with the tenant." for Default and the Auto Tooltip for Auto (`protectedResourceReason`). **Edit rules** stays enabled on the default SecurityGroup.
- **Project.** Every list has a **Project** column and the console's **Project** filter (`ProjectFilter`), and every details page shows the project. The project is named as everywhere else in the console (`getProjectName`, "Root" for the root project) and links to its details page (`/projects/:id`) when the user can see it (`NetworkingProjectName`).
- **Delete pre-checks.** Delete is `isAriaDisabled` with a Tooltip while a dependent that the UI can see exists ([deletion guards](design.md#deletion-dependency-guards)):

  | Resource | Disabled while | Tooltip |
  |---|---|---|
  | VirtualNetwork | It has Subnets, SecurityGroups, a NATGateway or, when bare-metal is enabled, FabricDomains | "Delete its dependents first: …" |
  | Subnet, SecurityGroup | A VM, bare-metal instance or Cluster (enabled services only) has a network attachment that references it | "Used by virtual machine web-1. Delete it first." or "Used by virtual machine web-1 and 2 more. Delete them first." |
  | NATGateway | A Cluster, in any state, has a network attachment on its VirtualNetwork | "Cluster c1 reaches its management endpoints through this gateway. Delete it first." |
  | ExternalIP | A NATGateway or ExternalIPAttachment references it | "Delete NAT gateway app-nat first." or "Delete its attachment to virtual machine web-1 first." |
  | ExternalIPPool | `status.allocated` is above 0 | "Delete its 2 external IPs first." |
  | Any of them | It is being deleted | "This subnet is being deleted." |

  The joins load every page (`networking-consumers.ts`). The UI sees only what the user may see: not workloads in other projects, not CaaS workers in tenant `system`, and not a workload whose attachment was left to the tenant defaults. Then Delete stays enabled, the server's guard decides, and the delete modal shows its message.
- A create whose parent is not READY is `isAriaDisabled` with the Tooltip "Available when the virtual network is Ready." For the provider admin, **Create virtual network** and **Create external IP pool** are `isAriaDisabled` with "Available when the network class is Ready." until the NetworkClass is READY; tenants cannot read the NetworkClass, so for them the server decides. The server checks the [creation readiness gates](design.md#creation-readiness-gates) the UI cannot see, and the form shows its message.
- Every create button (`CreateButton`) asks `SelfSubjectAccessReviews` whether the user may create the resource and is `isAriaDisabled` when not. Delete, Detach and **Edit rules** rely on the server's authorization; the modal or form shows its message.
- **Create subnet** opened from the Subnets list filtered by a VirtualNetwork pre-fills that network only when it is READY; otherwise the user picks one. The other list creates do not pre-fill.
- Every Delete asks for confirmation in the existing delete modal. The server's [deletion guards](design.md#deletion-dependency-guards) decide; the modal shows a guard's message and stays open.
- Pickers offer only READY resources; the ExternalIP picker follows the [ExternalIP picker rule](#externalip-picker-rule).
- No page says or implies that a resource is reachable from the Internet. "External" means outside the virtual network; address fields carry the help text "Reachable where your provider routes it."

### Virtual networks

- **List page** (`VirtualNetworksListPage`, osac #2048, aligned with the OSAC UX design): a card view (`VirtualNetworkCard`) and a table view (`VirtualNetworkTable`) with a view switcher, a URL-backed name search and state filter, a result count, and contextual empty states. Each network shows **Name** (with badge), **Status** (with the message popover), **IPv4 CIDR**, **Subnets** and **Security groups** counts, the **NAT gateway** (`name (address)` on one line, or a dash), and **Project**, plus a **View details** action; for the provider admin the cards show the tenant, the table adds a **Tenant** column, and a **Tenant** filter is added. The card labels the CIDR **IPv4 CIDR**, as every other page does. The **Project** filter is sent to the server. **Create virtual network** opens `VirtualNetworkCreateModal`: **Project**, **Name**, **IPv4 CIDR**, and, for the provider admin, **Tenant**; no NetworkClass field. The server checks the prefix limit ([Subnet address layout](design.md#subnet-address-layout)); the form shows its message.
- **Details page** (`VirtualNetworkDetailPage`, `/networking/virtual-networks/:id`). Header action **Delete virtual network** (disabled for Default) opens `VirtualNetworkDeleteModal`. When the UI has loaded the VirtualNetwork's Subnets, SecurityGroups, NATGateway and, when bare-metal is enabled, FabricDomains, and any exist, the action is `isAriaDisabled` with a Tooltip naming them ("Delete its dependents first: …"), a prerequisite the user can fix; while they load or fail to load, the server's [deletion guards](design.md#deletion-dependency-guards) decide. Primary Tabs, kept in the URL (`?tab=`):
  - **Overview**: IPv4 CIDR, project, \[tenant\], NAT gateway, and created.
  - **Subnets**: the [Subnets](#subnets) table filtered to this VirtualNetwork. **Create subnet** pre-fills and locks the VirtualNetwork.
  - **Security groups**: the [Security groups](#security-groups) table filtered to this VirtualNetwork. **Create security group** pre-fills and locks the VirtualNetwork.
  - **NAT gateway**: the existing `NatGatewayCard`: the NATGateway's name, ExternalIP address, and status, with Delete (`DetachNatGatewayModal`; disabled for the default NATGateway and while a Cluster uses it), or **Create NAT gateway**, which opens the [attach wizard](#nat-gateways). Create is `isAriaDisabled` unless the VirtualNetwork is READY, and hidden on a tenant default VirtualNetwork, where only OSAC creates the NATGateway.
- Both tab Create buttons are `isAriaDisabled` with the parent Tooltip unless the VirtualNetwork is READY.

### Subnets

- **List page** (`SubnetsListPage`, `/networking/subnets`). Columns: **Name** (with badge), **Status**, **IPv4 CIDR**, **Virtual network** (link to its details page), **Project**, \[**Tenant**\]. Filters: name, project, **Virtual network** (URL parameter `virtualNetwork=<id>`). No Subnet details page; a row links to its VirtualNetwork.
- **Create subnet** opens the existing `SubnetCreateModal`: **Virtual network** (select, READY VirtualNetworks only, hint "Only ready virtual networks are listed." unless locked; pre-filled from the filter, locked when opened from a VirtualNetwork), **Name**, **IPv4 CIDR** inside the VirtualNetwork's CIDR and not overlapping one of its Subnets (helper "Must be inside 192.168.101.0/24."; the placeholder is an example inside it: the first block no Subnet of the network uses, with a prefix two bits longer than the network's, from /24 to /26, or the network's own CIDR when it is /26 or longer, and no placeholder when no such block is free, `subnetCidrExample`; /26 is the strictest [prefix limit](design.md#subnet-address-layout) of the plans the installer derives, so the example is never rejected for its length). In a tenant default VirtualNetwork whose default Subnet is not READY, **Create** is `isAriaDisabled` and an inline info Alert and Tooltip say "Available when the default subnet is Ready." ([creation readiness gates](design.md#creation-readiness-gates)). It sends `spec.virtual_network: { id }` and the VirtualNetwork's project and tenant. The server checks the prefix limit and, in a default VirtualNetwork, that the default Subnet is READY; the form shows its message.
- **Row kebab:** **Delete subnet** (`SubnetActionsMenu`; disabled for Default and Auto, while a workload uses it, and while it is being deleted).

### Security groups

- **List page** (`SecurityGroupsListPage`). Columns: **Name** (with badge), **Status**, **Virtual network** (link), **Inbound rules** and **Outbound rules** (counts; the headers wrap), **Project**, \[**Tenant**\]. Filters: name, project, **Virtual network** (the same `virtualNetwork` URL parameter).
- **Create security group** opens `SecurityGroupCreateModal`: **Virtual network** (select, READY only; locked when opened from a VirtualNetwork) and **Name**. The group is created without rules; the user adds them with **Edit rules**.
- **Details page** (`SecurityGroupDetailPage`, `/networking/security-groups/:id`). Header actions: **Edit rules** (disabled for Auto with the Auto Tooltip; `isAriaDisabled` while the group is PENDING or **Updating**, Tooltip "Available when the security group is Ready or Failed.", and while DELETING, Tooltip "Rules cannot be edited while the security group is being deleted.") and **Delete security group** (disabled for Default and Auto, while a workload uses it, and while it is being deleted). Primary Tabs **Details** (**Virtual network**, **Project**, \[**Tenant**\], **Created**), **Inbound rules**, **Outbound rules**; the rule tabs show a read-only `SecurityGroupRulesTable` (**Protocol**, **Port range**, **Source CIDR** or **Destination CIDR**).
- **Edit rules** (`SecurityGroupEditRulesPage`, `/networking/security-groups/:id/edit-rules`). A full page form with **Inbound rules** and **Outbound rules** sections. Each rule is one row: **Protocol** (Select: TCP, UDP, All), **Port from** and **Port to** (TCP and UDP only, required, 1–65535, from ≤ to), and **Source IPv4 CIDR** or **Destination IPv4 CIDR** (canonical). Each section has an **Add rule** link button and a **Remove** action per row. Fields validate on blur and on **Save**. **Save** (primary) sends one `SecurityGroups.Update` with the complete lists ([rule updates](design.md#securitygroup)) and returns to the details page; **Cancel** (link) discards. The public Update has no optimistic-lock option, so when two people edit the same group, the later save replaces both lists; the server only rejects a save while an update is in progress. The per-rule add, edit, and delete modals (`SecurityGroupRuleModal`, `SecurityGroupRuleForm`) are removed.
- **ICMP.** New rules never offer ICMP ("The CLI and UI do not offer ICMP", [SecurityGroup rules](design.md#securitygroup)). A row loaded with an ICMP rule keeps ICMP as its value and option, so Save does not change it silently; where the managers do not support ICMP, the server rejects the update, and the form shows its message, which tells the user to use All. The form marks each ICMP row ("The network does not support ICMP rules. Remove the rule, or use All, which also allows TCP and UDP on every port."), because All widens the rule beyond ICMP. The rejection has no `ErrorInfo` reason, so the form recognizes it by the word ICMP in the message; this is the one exception to [Failure Handling](#failure-handling).
- **Update state.** After Save, a READY group shows **Updating** and a FAILED group shows PENDING; with provider networking disabled the group stays READY without **Updating**, because the save only stores the rules ([Status](design.md#status)). **Updating** and the disabled **Edit rules** last while the message is `Updating`; later in the update the API reports READY with the task message, so **Edit rules** is enabled, and a save then shows the server's message above the form with the rows kept. A final failure shows FAILED with the manager's message, when it has one, in the alert, which is shown even without a message and says that the rules shown are saved but may not be enforced: each manager keeps the rules of its last successful update, so managers can enforce different rules, until a save succeeds ([rule updates](design.md#securitygroup)); **Edit rules** stays available to fix the rules.

### NAT gateways

- **List page** (`NatGatewaysListPage`, `/networking/nat-gateways`). Columns: **Name** (with badge; links to its VirtualNetwork's **NAT gateway** tab), **Status**, **Virtual network** (link), **External IP** (address), **Project**, \[**Tenant**\]. Filters: name, project, **Virtual network**. No NATGateway details page.
- **Create NAT gateway** opens a small modal with one **Virtual network** select: READY VirtualNetworks that are not a tenant default and have no NATGateway. Its primary button **Continue** opens the create wizard for that VirtualNetwork at `/networking/nat-gateways/create/:id`, so **NAT gateways** stays the active nav item.
- **Create wizard** (`AttachNatGatewayWizardPage`, `/networking/virtual-networks/:id/nat-gateway/attach` from a VirtualNetwork, `/networking/nat-gateways/create/:id` from the NAT gateways list). It is called **NAT gateway** throughout. Steps: **NAT gateway** (the VirtualNetwork, read-only, a **Name**, and an **External IP** picker per the [ExternalIP picker rule](#externalip-picker-rule)) and **Review**. **Create** creates the NATGateway with the VirtualNetwork's project and tenant and, like **Cancel**, returns to where the user started: the NAT gateways list or the VirtualNetwork's **NAT gateway** tab. When no ExternalIP can be picked, an alert links to **Create external IP**. The step describes the NATGateway as outbound translation to addresses outside the virtual network.
- **Row kebab:** **Delete** opens the existing `DetachNatGatewayModal` (disabled for the default NATGateway and while a Cluster on its VirtualNetwork uses it). Changing the ExternalIP is Delete, then Create.

### External IPs

The page (`ExternalIpListPage`, `/networking/external-ips`, description "Addresses from shared provider pools that make workloads reachable from outside the virtual network.") has primary Tabs **Addresses** and **Attachments**; the URL parameter `tab=attachments` selects the second.

- **Addresses tab.** Columns: **Name** (with badge), **Status**, **Address** (help text "Reachable where your provider routes it."), **IP pool** (name; linked to the pool for the provider admin), **Used by**, **Project**, \[**Tenant**\]. Like the other networking lists it has no **Created** column; names and pools stay on one line. Filters: name, project. **Create external IP** opens the existing wizard (`ExternalIpWizardPage`, `/networking/external-ips/create`): for the provider admin a **Tenant** first (`TenantSelectField`), then **Project** and **Name**, then the **IP pool** select, which shows each pool's `available` and disables pools with 0 (the public List returns only READY pools with free addresses), then **Review**. Row kebab: **Delete** (`ExternalIpDeleteModal`, disabled for Default and Auto). While a NATGateway or ExternalIPAttachment uses the address, Delete is `isAriaDisabled` with a Tooltip naming the next step, for example "Delete NAT gateway app-nat first." or "Delete its attachment to virtual machine web-1 first."; the server's guard still decides.
- **Used by.** The NATGateway or ExternalIPAttachment that references the ExternalIP, on one line as `name (kind)`, for example `default (NAT gateway)`, with the name linked to the VirtualNetwork's **NAT gateway** tab or the target workload, from `useExternalIpConsumers` and `useExternalIpJoins`. It never comes from `status.attached` alone, because a NATGateway does not set it ([ExternalIP](design.md#externalip)).
- **Attachments tab** (`ExternalIpAttachmentsTable`). Columns: **Name** (with Auto badge), **External IP** (address), **Target** (kind and name, linked to the workload's details page, plus the endpoint for a Cluster), **Status**, **Project**, \[**Tenant**\]. Filters: name, project. Row kebab: **Delete** (disabled for Auto); the confirmation says the ExternalIP is kept.
- **Create attachment** opens `ExternalIpAttachmentCreateModal`: **External IP** (typeahead, [ExternalIP picker rule](#externalip-picker-rule)), **Target type** (Radio: Virtual machine, Bare-metal instance, Cluster; only enabled services), **Target** (typeahead, READY targets of that type in the ExternalIP's project and tenant, hint "Only ready targets in the external IP's project are listed."; the root project counts as a project; changing or clearing the ExternalIP clears it and disables it again), and for a Cluster **Cluster endpoint** (Radio: API, Ingress). The attachment gets the ExternalIP's project and tenant. The server rejects a target whose endpoint is not ready ([ExternalIPAttachment](design.md#externalipattachment)); the modal shows its message. The Cluster details page keeps its own attach per endpoint ([CaaS UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md)).

#### ExternalIP picker rule

Every ExternalIP picker (attach wizard, Create attachment, workload attach modals) offers an ExternalIP only when it is ALLOCATED, has no Auto or Default label, `status.attached` is not true, and no NATGateway or ExternalIPAttachment references it (`isSelectable` of `useExternalIpConsumers`, which lists every NATGateway and ExternalIPAttachment). The server's [creation readiness gates](design.md#creation-readiness-gates) still decide.

### External IP pools

Provider admin only, under **Networking**; the route and pages are unchanged. Pools use the private API.

- **List page** (`ExternalIpPoolsListPage`). Columns: **Name**, **Status**, **IPv4 CIDR** (every range of the pool; the field is repeated, but the [server accepts exactly one IPv4 CIDR](design.md#externalippool), and the UI creates a pool with one), **Available** as "12 of 16 (75%)": the available and total addresses and the available share, never rounded to 0% while any address is free or to 100% while any is used ("<1%", ">99%"); "—" for a pool with no addresses. The name links to the details page. **Create external IP pool** opens the create wizard (disabled until the NetworkClass is READY); the row kebab has **View details** and **Delete**. A pool with addresses but none available shows a **None available** warning Label.
- **Details page** (`ExternalIpPoolDetailsPage`): overview, capacity, and the CIDR. Capacity is a PatternFly Progress bar of the used share (`total` − `available`), labelled "56 of 256 used", warning from 80% used and danger when none is available, so a nearly full pool stands out before it blocks new ExternalIPs, and **Available** as in the list; header action **Delete** (`ExternalIpPoolDeleteConfirmModal`). In both places Delete is `isAriaDisabled` with "Delete its 2 external IPs first." while `status.allocated` is above 0; the server still rejects it while any ExternalIP of the pool exists.
- **Create** (`ExternalIpPoolWizardPage`): steps **External IP pool** (**Name** and one **IPv4 CIDR**) and **Review**. There is no tenant step: a pool is shared by all tenants ([Resource hierarchy](design.md#resource-hierarchy)), so the request sets the tenant `shared`. Client validation rejects an empty, malformed, non-canonical, or IPv6 CIDR. It sends `{ metadata: { name, tenant: "shared" }, spec: { ipFamily: IP_FAMILY_IPV4, cidrs: [cidr] } }`.

### Network class

Provider admin only, last item under **Networking** (`NetworkClassPage`, `/admin/infrastructure/network-class`). A read-only view of the NetworkClass from the private `NetworkClasses.List` ([NetworkClass](design.md#networkclass)), with no actions; the installer creates it. The page is named after the resource, not "settings", because the NetworkClass is an installer-owned resource, not configuration edited here. It shows whether networking is ready, which managers were resolved, what they support, and the values every tenant and Subnet got. Four Cards with DescriptionLists show:

- title, description, and status with message;
- **Fabric manager** and **Kubernetes manager**, one row each: the manager OSAC resolved (`status.network_managers`), with its Ansible role below it; until it is resolved, the requested name (`fabric_manager`, `k8s_manager`) with "(not resolved yet)"; **Kubernetes manager** shows "None (virtual machines are disabled)" when none is requested; and **Network type**;
- **East-west Ethernet** (`supports_east_west_ethernet`);
- **ICMP in security groups** (`status.security_group_icmp`, optional): **Supported**, **Not supported** (help text: a network manager does not support ICMP rules, so security groups reject them; the All protocol still includes ICMP), or **Unknown** while the field is unset because no manager is resolved yet (help text: shown once the network managers are resolved; ICMP rules may be rejected until then);
- **Tenant defaults** (`spec.defaults`): **Virtual network CIDR** and **Subnet CIDR**, then the default SecurityGroup's inbound and outbound rules in the read-only `SecurityGroupRulesTable`, with "No inbound rules." or "No outbound rules." when a direction is empty;
- **Subnet address plan** (`spec.address_plan`): each share as a percentage with what it is used for: **Virtual machines** (`overlay`, addresses from the Kubernetes manager), **Fabric** (`fabric`, Fabric DHCP for bare-metal servers and cluster workers, and provider devices), and **Cluster ingress** (`lb_vip`) ([Subnet address plan](design.md#subnet-address-plan)).

The installer fixes the defaults and the plan when it creates the NetworkClass and fails a rollout that changes them, so they are what every tenant and Subnet got; each Card says they are set at installation. A deployment has one NetworkClass, and the page shows it. When sites are introduced, with a NetworkClass per site, this item becomes a **Network classes** list with a site column, and this page becomes its details page.

### Provider admin

- Every networking list (Virtual networks, Subnets, Security groups, NAT gateways, both External IPs tabs) shows a **Tenant** column and a **Tenant** filter. External IP pools have none, because every pool is shared.
- Creates that start from a parent inherit its tenant: Subnet, SecurityGroup, and NATGateway from the VirtualNetwork; ExternalIPAttachment from the ExternalIP. VirtualNetwork create asks for the tenant; ExternalIP create asks for it first (`TenantSelectField`).
- Network names repeat across tenants (every tenant has a `default`), so the Virtual network pickers in Create subnet, Create security group and Create NAT gateway label each option `name (IPv4 CIDR, tenant)` (`virtualNetworkOptionLabel`), and the Virtual network list filter shows `name (tenant)`. Tenant users see `name (IPv4 CIDR)`.
- Pickers offer only resources the server accepts: the NAT gateway's ExternalIP picker lists the VirtualNetwork's tenant, and the attachment's Target picker the ExternalIP's tenant, because a reference to another tenant's resource fails like a missing one ([ExternalIPAttachment](design.md#externalipattachment)). Tenant users list only their own tenant.

### Workload network attachment pickers

The VM, bare-metal, and Cluster create wizards have the **Use tenant default network** toggle. Toggle on: the attachment is omitted and the tenant defaults apply ([defaulting](design.md#network-attachment-field-presence-and-defaulting)). Toggle off: the shared `NetworkAttachmentPickers` component shows the pickers in the table below (bare-metal interface selection: [BMaaS UX Alignment](/enhancements/OSAC-1437-bmaas-networking/design.md#ux-alignment)). Pickers offer only READY resources of one VirtualNetwork, never an automatic SecurityGroup; the server checks the [gates](design.md#creation-readiness-gates) the UI cannot see, and the form shows its message. No wizard sets `auto_external_ip_attachment`.

`NetworkAttachmentPickers` (`libs/ui-components/`) renders the cascading VirtualNetwork → Subnet → SecurityGroup pickers for the VM, bare-metal, and Cluster wizard adapters:

| Aspect | Shared component | VM adapter | Bare-metal adapter | Cluster adapter |
|---|---|---|---|---|
| VirtualNetwork picker | `SelectField` from `useVirtualNetworks()`; shows Name and IPv4 CIDR | Required | Required | Optional |
| Subnet picker | `SelectField` from `useSubnets()`, filtered by the selected VirtualNetwork | Required | Required | Optional while no VirtualNetwork is selected; required once one is |
| SecurityGroup multi-select | `MultiSelectField` from `useSecurityGroups()`, filtered by the selected VirtualNetwork, without automatic SecurityGroups | Required | Required | Required only for a Subnet outside the tenant's default VirtualNetwork |
| Cascade reset | Clearing the VirtualNetwork clears Subnet and SecurityGroups | Same | Same | Same |
| Auto-select | A one-option list selects that option | Same | Same | Same |
| Other fields | — | — | **Interface** select of the BareMetalInstanceType's `fabric` ports, first selected | `pod_cidr`, `service_cidr` |
| Payload | — | `network_attachments: [{...}]` (array) | `network_attachments: [{...}]` (array, one item, with `interface`) | `network_attachment: {...}` (singular) |

```text
libs/ui-components/src/components/form/
  NetworkAttachmentPickers.tsx
  NetworkAttachmentPickers.test.tsx
```

```typescript
interface NetworkAttachmentPickersProps {
  /** Formik field path prefix. VM: "spec.network_attachments.0", Cluster: "spec.network_attachment" */
  fieldPrefix: string;
  /** When to require security group selection */
  sgRequired: 'always' | 'when-non-default-vn' | 'never';
  /** Default VN API ID for conditional SG validation (only for 'when-non-default-vn') */
  defaultVnId?: string;
  /** Whether all pickers are optional (cluster: true, VM: false) */
  allOptional?: boolean;
  /** Whether to show VN/Subnet IPv4 CIDR in picker options */
  showCidr?: boolean;
}
```

The component owns the pickers with data loading, cascade reset, auto-select, conditional SecurityGroup validation, and loading and error states. Each adapter owns its Formik prefix, Yup schema fragment, payload shape (`buildCreatePayload`) and other fields. The Cluster adapter: [CaaS UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md).

## Decisions

- **Projects.** VirtualNetwork create asks for a project (`ProjectField`). Subnets, SecurityGroups, and NATGateways get their VirtualNetwork's project; the UI never asks for it. ExternalIP create asks for a project; an ExternalIPAttachment gets its ExternalIP's project. Every resource has a project, and projects decide who sees what, so every list and details page shows it ([Rules for every networking page](#rules-for-every-networking-page)).
- **Provider networking disabled.** The UI does not gate on it, because tenants cannot see the setting ([Provider networking control](design.md#provider-networking-control)). A rejected create, for example an ExternalIP create with `provider networking is disabled`, shows the server's message; READY resources with reason `ProvisioningDisabled` show their message in the status Popover.
- **DefaultNetworkingReady.** These pages do not show the Tenant condition ([Default Networking](/enhancements/OSAC-1433-default-networking/design.md)); a workload create that needs it shows the server's message in its wizard.
- **Pagination.** `useVirtualNetworks`, `useSubnets` and `useSecurityGroups` load every page, and so does the External IPs list (`useExternalIpsData`), because no list has page controls, and so does the External IP pools list. Joins and counts (Subnets per VirtualNetwork, NATGateway addresses, **Used by**, the ExternalIP picker's consumer check) fetch all pages, so no row is missing its join. The External IPs list's pool, NATGateway and attachment joins load those lists without an ID filter, because a filter that lists every displayed ID outgrows the server's filter size limit on a long list; the NATGateway and attachment lists are the ones the consumer check loads, so they share its cache. A picker that filters in the browser after the server filter fetches all pages too: the NAT gateway wizard's ExternalIP picker, the ExternalIP pickers of Create attachment and the Cluster attach modal, and the attachment's Target picker, which checks readiness in the browser (`ResourceSelectField` with `loadAllPages`). The Target picker's server filter also asks only for the ExternalIP's project and, for the provider admin, its tenant. The **Tenant** picker and the **IP pool** picker load every page too, because the typeahead searches only the loaded items. Other typeahead pickers load one page, 100 items by the server default.
- **ICMP.** Not offered for new rules; an existing ICMP rule is kept on edit ([Security groups](#security-groups)). **Network class** shows whether the managers support it.

## Out of scope

- ExternalIP, Subnet, and NATGateway details pages.
- Bulk selection and bulk actions.
- A topology view.
- A "create with extras" flow (for example a VirtualNetwork with Subnets and a NATGateway in one form).
- A global tenant switcher.
- Typed-name delete confirmation.
- Rules in the SecurityGroup create form.
- UI gating for provider networking disabled.
- Showing `DefaultNetworkingReady`.

## Failure Handling

The UI shows the server's message as a form-level or modal Alert, reads error reasons only from `ErrorInfo.reason` (exception: the ICMP rejection in [Security groups](#security-groups), which has none), and keeps the resource listed. Codes and messages: [Error codes](design.md#error-codes).

| Failure | What the user sees |
|---|---|
| Create rejected (`INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `ALREADY_EXISTS`) | The message in the create modal or wizard; the values stay. |
| Delete rejected by a [deletion guard](design.md#deletion-dependency-guards) | The message in the delete modal, which stays open. |
| **Edit rules** rejected (for example ICMP not supported, or the group became PENDING) | The message above the form; the edited rows stay. |
| `ABORTED` or `INTERNAL` | The message; the action stays available for retry. |
| A delete task keeps failing | The row shows DELETING with the message; OSAC retries, the UI does nothing. |
| A resource FAILED | Status label with the message; on a details page also an inline danger Alert. |
| Any List or Get failure | `QueryErrorState`; a failing join shows a dash in its column. |

## Implementation Details

- **Hooks** (`api/v1/networking.ts`, `api/v1/external-ip-data.ts`, `api/use-resource.ts`): `useVirtualNetworks`, `useVirtualNetwork`, `useCreateVirtualNetwork`, `useDeleteVirtualNetwork`, `useSubnets`, `useCreateSubnet`, `useDeleteSubnet`, `useSecurityGroups`, `useSecurityGroup`, `useCreateSecurityGroup`, `useUpdateSecurityGroup`, `useDeleteSecurityGroup`, `useNatGateway`, `useNatGateways`, `useExternalIpsData`, `useExternalIpJoins`, `useExternalIpConsumers`; `useNetworkConsumers` and `useClustersOnVirtualNetwork` (`api/v1/networking-consumers.ts`, the workloads that use a Subnet, SecurityGroup or NATGateway); the generic `useListResource`, `useListAllResources`, `useGetResource`, `useCreateResource`, and `useDeleteResource` for NATGateways, ExternalIPAttachments, ExternalIPPools, and the private NetworkClasses. Types from `@osac/types` and `@osac/types/private`.
- **Shared components** (`components/networking/`): `ResourceOriginBadge`, `NetworkingResourceName`, `NetworkingProjectName`, `resourceOrigin.ts` (badges, `isProtectedResource`, `protectedResourceReason`), `deleteDisabledReasons.ts` (the delete pre-checks), `useNetworkClassNotReadyReason`, and `subnetCidrExample`; `StatusWithMessage`, a wrapper around `ResourceStatusLabel` that adds the message Popover, used by the existing status labels (`VirtualNetworkStatusLabel`, `SubnetStatusLabel`, `SecurityGroupStatusLabel`, `NatGatewayStatusLabel`, `ExternalIpStatusLabel`, `ExternalIpAttachmentStatusLabel` (Attaching, Attached, Failed, Detaching), `ExternalIpPoolStatusLabel`); `DeleteResourceModal` for every delete.
- **New pages and components:** `SubnetsListPage`, `NatGatewaysListPage` with its VirtualNetwork picker modal, `ExternalIpAttachmentsTable` and `ExternalIpAttachmentCreateModal`, `SecurityGroupEditRulesPage`, `NetworkClassPage`. The Subnets and SecurityGroups tables are shared by the list pages and the VirtualNetwork tabs.
- **Removed:** `SecurityGroupRuleModal` and `SecurityGroupRuleForm`; the ExternalIP pool `TenantStep` (removed by the shared-tenant pool change, osac #2217).
- **Test fixtures:** `createMockConnectTransport.ts` serves NATGateways, ExternalIPs, ExternalIPAttachments, FabricDomains, private ExternalIPPools, and the private NetworkClass.

### Component tests

| Page or component | Scenarios |
|---|---|
| Navigation (`shellNav`) | Items and order per role; External IP pools and Network class only for the provider admin; item active on details and create routes |
| `VirtualNetworksListPage` | Columns, badge, NAT gateway on one line with its links, project column and filter, Tenant column for the provider admin; Create disabled for the provider admin until the network class is Ready |
| `VirtualNetworkDetailPage` | Four tabs; tab Create buttons `isAriaDisabled` with Tooltip unless READY and locked to this network; Delete disabled for Default and with dependents, including fabric domains; project named Root |
| `SubnetsListPage` | Virtual network filter from the URL; create pre-fills it and sends `virtualNetwork: { id }` and its project; project column, link and filter; Delete disabled for Default and Auto and while a workload uses the subnet, enabled for workloads of services that are not enabled; Create waits for the default subnet; CIDR example and helper from the parent |
| `SecurityGroupsListPage` | Virtual network filter; create without rules; wrapped rule headers; one link style |
| `SecurityGroupDetailPage` | Read-only rules; **Edit rules** disabled for Auto and while PENDING or Updating; Delete disabled for Default and Auto and while a workload uses the group; Project and Created on Details |
| `SecurityGroupEditRulesPage` | Add and remove rows; port validation on blur and Save; ICMP not offered on new rows and kept on an existing one; one Update with both complete lists; server error shown |
| `NatGatewaysListPage` | Picker offers only READY, non-default networks without a NATGateway; continues to the attach wizard; Delete disabled for the default and while a cluster uses the gateway; the name links to the NAT gateway tab, the address is plain text |
| `AttachNatGatewayWizard` | ExternalIP picker rule; only the network's tenant for the provider admin; NATGateway created with the network's project and tenant |
| `ExternalIpListPage` | Tabs from `tab`; **Used by** from NATGateway and attachment references, not `status.attached`; pool select disables pools with 0 available; no pool count in the list, pool linked for the provider admin, project linked and Root for the root project; tenant first for the provider admin |
| `ExternalIpAttachmentCreateModal` | Target type Radio, Endpoint only for a Cluster, picker rule, targets in the ExternalIP's tenant for the provider admin, target cleared when the ExternalIP changes, server rejection shown; Delete disabled for Auto |
| `ExternalIpPoolWizard` | No tenant step; one IPv4 CIDR; tenant `shared` in the request |
| `ExternalIpPoolsListPage`, `ExternalIpPoolDetailsPage` | Delete disabled while the pool has allocated external IPs; Create disabled until the network class is Ready |
| `NetworkClassPage` | Status, one row per manager (resolved with its role, or not resolved yet) and capabilities from the fixture, including Supported, Not supported and Unknown ICMP; tenant defaults with both rule tables and an empty direction; address plan shares as percentages; no actions |
| `StatusWithMessage` | Popover with the message; no Popover without one |

`NetworkAttachmentPickers.test.tsx`:

| Scenario | Assert |
|----------|--------|
| VirtualNetwork selection filters Subnet and SecurityGroup lists | Options update on VirtualNetwork change |
| Clearing VirtualNetwork resets Subnet and SecurityGroup values | Formik values cleared |
| Single-option list auto-selects | Value auto-selected |
| `sgRequired="always"` with empty SecurityGroup | Validation error |
| `sgRequired="when-non-default-vn"` with default VirtualNetwork, empty SecurityGroup | No error |
| `sgRequired="when-non-default-vn"` with non-default VirtualNetwork, empty SecurityGroup | Validation error |
| `allOptional={true}` with all pickers empty | No errors |
| `allOptional={false}` with VirtualNetwork empty | Validation error |
| Automatic SecurityGroups in the VirtualNetwork | Not offered in the SecurityGroup list |
| Loading and error states | Pickers disabled during load; error on failure |

---

## Provenance

Authored: commit @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 7b09375
Final: respond @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 18a72cb (dirty)

> Context changed between commit and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.3.0","ai_workflows":"1e226e0 (dirty)","source_repo":"18a72cb (dirty)","source_repo_branch":"design/OSAC-2632-ui","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["commit","respond"],"authoring_modes":["skill"],"context_changed":true} -->
