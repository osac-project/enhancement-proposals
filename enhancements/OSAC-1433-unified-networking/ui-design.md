---
title: unified-networking-ui
authors:
  - brotman@redhat.com
  - dmanor@redhat.com
creation-date: 2026-08-12
last-updated: 2026-11-17
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

The UI follows PatternFly 6 (the repository pins `^6.6.1`) and reuses the repository's existing list, details, form, and modal components:

- **Navigation.** One expandable **Networking** group; the item of a resource stays active on its details and create routes ([Navigation](https://www.patternfly.org/components/navigation/design-guidelines)).
- **Action placement.** The create action is the primary button in the page toolbar or header; row actions are in a kebab in the last column; details page actions are at the top right ([Actions](https://www.patternfly.org/patterns/actions)). A Delete item is last in its menu and is never red ([Menu](https://www.patternfly.org/components/menus/menu/design-guidelines)).
- **Disabled with a reason.** An action that the user cannot take on a resource stays in its place and is disabled with `isAriaDisabled`, so it stays focusable, plus a Tooltip that says why or what to do: the resource is Default or Auto, a dependent still exists, or a parent is not Ready. Every row of a list keeps the same menu. Only a create that OSAC alone makes (the NATGateway of a tenant default VirtualNetwork) is hidden ([Actions](https://www.patternfly.org/patterns/actions), [Button accessibility](https://www.patternfly.org/components/button/accessibility)).
- **Badges.** **Default** and **Auto** are compact, non-status Labels next to the name, with a Tooltip ([Label](https://www.patternfly.org/components/label/design-guidelines)).
- **Status.** A status is a Label with an icon and text. When the API `message` is set, the Label itself is clickable (`Label` with `onClick`) and opens a Popover titled **Status details** with the message; there is no separate help icon. A details page of a FAILED resource shows the message once, in an inline danger Alert titled by what failed ("Provisioning failed", "Security group failed", "The network class is not ready"), with no Popover ([Status and severity](https://www.patternfly.org/patterns/status-and-severity), [Alert](https://www.patternfly.org/components/alert/design-guidelines)).
- **Create forms.** Every networking create is a page (`/…/create`), like the security group create: Breadcrumb to where it started, Title, a one-column Form with labels on top and inline errors on blur and on submit, and primary **Create** and link **Cancel** at the bottom; no create wizards and no create modals. The one exception is a create started from inside another form (a picker's create option): it opens a modal Form, so the form behind it keeps its values; the workload wizards' virtual network field keeps its `VirtualNetworkCreateModal` for this. Long lists use a typeahead Select; fewer than five choices use Radio buttons ([Form](https://www.patternfly.org/components/forms/form/design-guidelines), [Modal](https://www.patternfly.org/components/modal/design-guidelines)).
- **After create.** As elsewhere in the console, a create opens the new resource's page: a VirtualNetwork, SecurityGroup or ExternalIPPool its details page, and a NATGateway its VirtualNetwork's details page, whose **Overview** shows it. A Subnet or ExternalIP, which has no page, returns to where the create started. A success toast names the resource.
- **Create from a picker.** A picker for a resource the user may still need to create ends with a create option (`ResourceSelectField` `createOption`: last item, plus icon), as the workload wizards' virtual network field does. Choosing it opens the create modal, and the new resource is selected when it is created.
- **Batch edit.** Security group rules are edited as one batch on a full page form, not inline row by row, because one Update replaces both rule lists ([Inline edit](https://www.patternfly.org/components/inline-edit/design-guidelines)).
- **Delete confirmation.** Delete opens the repository's existing delete modal: warning title icon, the danger button only in the modal ([Modal](https://www.patternfly.org/components/modal/design-guidelines)).
- **Details pages and links.** A resource gets a details page only when it has more than a list row can show: a VirtualNetwork (its Subnets, SecurityGroups and NATGateway), a SecurityGroup (its rules and **Edit rules**), and an ExternalIPPool (from OSAC-4418). Subnets, NATGateways, ExternalIPs and ExternalIPAttachments fit in their row, and their actions are in its kebab. Only a resource with a page is linked, and so are projects and workloads. A NATGateway links to its VirtualNetwork's details page, whose **Overview** shows it, because a VirtualNetwork has at most one. An ExternalIP address, which has no page, is plain text. Every networking link has one style (`NetworkingResourceName`), and a name with its address or kind stays on one line, for example `default (203.0.113.2)` ([Link](https://www.patternfly.org/components/button/design-guidelines)).
- **Lists.** The repository's list pattern: a toolbar with a name search and attribute filters shown as filter labels with **Clear all filters** ([Filters](https://www.patternfly.org/patterns/filters/design-guidelines)), and three empty states: no resources (with the create action), no results (one **Clear all filters**), and load error, in one layout on every networking list ([Empty state](https://www.patternfly.org/components/empty-state/design-guidelines)).
- **Details pages.** Breadcrumb, Title with the status Label, actions at the top right, and primary Tabs. Content follows the virtual machine details page: titled sections (`Title` h2) in a `Grid`, each a compact `DescriptionList` in its default vertical layout, with the value under its label, and no Cards; a related resource with one action is a row with a secondary Button next to its value, as the VM page's External IP row ([Tabs](https://www.patternfly.org/components/tabs/design-guidelines), [Description list](https://www.patternfly.org/components/description-list/design-guidelines)). The read-only **Network class** page groups its values in Cards ([Network class](#network-class)). The ExternalIPPool details page (OSAC-4418) is not changed here.
- **Wording.** Sentence case for every label, title, and button ([Capitalization](https://www.patternfly.org/content-design/grammar/capitalization)); "Create \<resource\>", never "New" or "Add" for a resource ([Terminology](https://www.patternfly.org/content-design/grammar/terminology)); success toasts name the result without "successfully" ([Alert](https://www.patternfly.org/components/alert/design-guidelines)).

## Proposal

### Information architecture

**Navigation** (`shellNav.ts`, routes in `AppShell.tsx`). The **Networking** group:

| # | Item | Route | Tenant admin, tenant user | Provider admin |
|---|---|---|---|---|
| 1 | Virtual networks | `/networking/virtual-networks` | Yes | No |
| 2 | Subnets | `/networking/subnets` | Yes | No |
| 3 | Security groups | `/networking/security-groups` | Yes | No |
| 4 | NAT gateways | `/networking/nat-gateways` | Yes | No |
| 5 | External IPs (tabs **Addresses** and **Attachments**) | `/networking/external-ips`, `?tab=attachments` | Yes | No |
| 6 | External IP pools | `/admin/infrastructure/external-ip-pools` (unchanged; moved here from **Infrastructure**) | No | Yes |
| 7 | Network class | `/admin/infrastructure/network-class` | No | Yes |

The tenant identity provider manager role has no **Networking** group, as today. The provider admin's navigation has no tenant-scoped resources, as for virtual machines and clusters: [PRD FR-11](prd.md#fr-11-unified-networking-ui-and-documentation) gives tenants the networking resources and the provider admin the NetworkClass and ExternalIPPools ([Provider admin](#provider-admin)).

**Rationale.** Large public cloud consoles commonly give each networking resource its own list page in the sidebar, so a user finds every subnet or security group without knowing its parent first. Child resources also appear in context on the parent's page, and child lists have a parent network filter that the parent's page links to. Associations, such as an address attached to a workload, are not top-level items; they live with the resource they extend. This layout follows that practice: every resource in the [resource hierarchy](design.md#resource-hierarchy) has a list page, and ExternalIPAttachments are a tab of External IPs.

**Where each action lives:**

| Resource | List page | Details page | Parent's page |
|---|---|---|---|
| VirtualNetwork | Create | Delete | — |
| Subnet | Create, Delete (row) | — (no details page) | VirtualNetwork **Subnets** tab: Create, Delete (row) |
| SecurityGroup | Create (page, with rules) | Edit rules, Delete | VirtualNetwork **Security groups** tab: Create |
| NATGateway | Create, Delete (row) | — (no details page; its VirtualNetwork's **Overview** shows it) | VirtualNetwork **Overview**, **NAT gateway** section: Create, Delete |
| ExternalIP | **Addresses** tab: Create, Delete (row) | — (no details page) | Create NAT gateway page: **Create external IP** in the picker |
| ExternalIPAttachment | **Attachments** tab: Delete (row) | — | Virtual machine and Cluster details pages (existing attach and detach) |
| ExternalIPPool | Create | Delete | — |
| NetworkClass | — | **Network class**: view only | — |

### Rules for every networking page

- The UI uses only the fulfillment API calls of the [API operation constraint](design.md#api-operation-constraint): List, Get, Create, Delete, and `SecurityGroups.Update`. Its only edit form is [Edit rules](#security-groups); any other change is delete and recreate.
- Status shows the API `state` as a Label and the `message` in a Popover on it ([Status](design.md#status)). A SecurityGroup that is READY with the message `Updating` shows **Updating**. The API has no field that marks the whole rule update: once the message changes to the running task, the group shows Ready with that message in the Popover, and an **Edit rules** save made then gets the server's `FAILED_PRECONDITION` message ([Security groups](#security-groups)).
- A resource with the label `osac.openshift.io/default: "true"` shows the **Default** badge (Tooltip "Created automatically as a tenant default."); an automatic resource shows the **Auto** badge (Tooltip "Created automatically for \<kind\> \<owner\>. It is deleted with it."; the owner is the `auto-created-for` label, which holds the owner's API ID, and an ExternalIPAttachment, which has no kind label, names its target) ([CaaS UI — Automatic resource indicators](/enhancements/OSAC-1436-caas-networking/ui-design.md#automatic-resource-indicators)). Their Delete and (Auto) **Edit rules** actions are disabled, because the [deletion guards](design.md#deletion-dependency-guards) always reject them; the Tooltip is "Created as a tenant default. It is deleted with the tenant." for Default and the Auto Tooltip for Auto (`protectedResourceReason`). **Edit rules** stays enabled on the default SecurityGroup.
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
- A create whose parent is not READY is `isAriaDisabled` with the Tooltip "Available when the virtual network is Ready." **Create external IP pool** is `isAriaDisabled` with "Available when the network class is Ready." until the NetworkClass is READY; tenants cannot read the NetworkClass, so for their creates the server decides. The server checks the [creation readiness gates](design.md#creation-readiness-gates) the UI cannot see, and the form shows its message.
- Every create button (`CreateButton`) asks `SelfSubjectAccessReviews` whether the user may create the resource and is `isAriaDisabled` when not. Delete and **Edit rules** rely on the server's authorization; the modal or form shows its message.
- **Create subnet** and **Create security group** opened from their list filtered by a VirtualNetwork pre-fill that network only when it is READY; otherwise the user picks one. The other list creates do not pre-fill.
- Every Delete asks for confirmation in the existing delete modal. The server's [deletion guards](design.md#deletion-dependency-guards) decide; the modal shows a guard's message and stays open.
- Pickers offer only READY resources; the ExternalIP picker follows the [ExternalIP picker rule](#externalip-picker-rule).
- No page says or implies that a resource is reachable from the Internet. "External" means outside the virtual network; address fields in forms carry the help text "Reachable where your provider routes it." Table headers carry no help icons.

### Virtual networks

- **List page** (`VirtualNetworksListPage`, osac #2048, aligned with the OSAC UX design): a card view (`VirtualNetworkCard`) and a table view (`VirtualNetworkTable`) with a view switcher, a URL-backed name search and state filter, a result count, and contextual empty states. Each network shows **Name** (with badge), **Status** (with the message popover), **IPv4 CIDR**, **Subnets** and **Security groups** counts, the **NAT gateway** (`name (address)` on one line, or a dash), and **Project**, plus a **View details** action. The card shows these in its body and **Created** in its footer (`OsacCardFooterRow`), as the other resource cards do. The card labels the CIDR **IPv4 CIDR**, as every other page does. The **Project** filter is sent to the server. **Create virtual network** opens `VirtualNetworkCreatePage` (`/networking/virtual-networks/create`): **Project**, **Name**, **IPv4 CIDR**; no NetworkClass field. On success it opens the new VirtualNetwork's details page. The server checks the prefix limit ([Subnet address layout](design.md#subnet-address-layout)); the form shows its message.
- **Details page** (`VirtualNetworkDetailPage`, `/networking/virtual-networks/:id`). Header action **Delete virtual network** (disabled for Default) opens `VirtualNetworkDeleteModal`. When the UI has loaded the VirtualNetwork's Subnets, SecurityGroups, NATGateway and, when bare-metal is enabled, FabricDomains, and any exist, the action is `isAriaDisabled` with a Tooltip naming them ("Delete its dependents first: …"), a prerequisite the user can fix; while they load or fail to load, the server's [deletion guards](design.md#deletion-dependency-guards) decide. Primary Tabs **Overview**, **Subnets** and **Security groups**, kept in the URL (`?tab=`):
  - **Overview**: one **Details** section: IPv4 CIDR, project, NAT gateway, and created. The **NAT gateway** row (`VirtualNetworkNatGatewayRow`, which replaces `NatGatewayCard`) is where outbound access is added and removed, like the External IP row of the virtual machine details page (`VmExternalIpSection`): with a NATGateway, `name (address)`, its status Label and a secondary **Delete** button (`DetachNatGatewayModal`; `isAriaDisabled` with the reason for the default NATGateway and while a Cluster uses it), which removes the NATGateway and keeps the ExternalIP; without one, a dash and a secondary **Create NAT gateway** button, which opens the [create page](#nat-gateways) for this VirtualNetwork, `isAriaDisabled` unless the VirtualNetwork is READY, and hidden on a tenant default VirtualNetwork, where only OSAC creates the NATGateway.
  - **Subnets**: the [Subnets](#subnets) table filtered to this VirtualNetwork. **Create subnet** opens the create page with the VirtualNetwork pre-filled and locked.
  - **Security groups**: the [Security groups](#security-groups) table filtered to this VirtualNetwork. **Create security group** opens the create page with the VirtualNetwork pre-filled and locked.
- The tab Create buttons and **Create NAT gateway** are `isAriaDisabled` with the parent Tooltip unless the VirtualNetwork is READY.

### Subnets

- **List page** (`SubnetsListPage`, `/networking/subnets`). Columns: **Name** (with badge), **Status**, **IPv4 CIDR**, **Virtual network** (link to its details page), **Project**. Filters: name, project, **Virtual network** (URL parameter `virtualNetwork=<id>`). No Subnet details page; a row links to its VirtualNetwork.
- **Create subnet** opens `SubnetCreatePage` (`/networking/subnets/create`; `?virtualNetwork=<id>` pre-fills and locks the network, with that VirtualNetwork in the breadcrumb): **Virtual network** (select, READY VirtualNetworks only, each shown as `name (IPv4 CIDR)` (`virtualNetworkOptionLabel`), hint "Only ready virtual networks are listed." unless locked; pre-filled from the filter, locked when opened from a VirtualNetwork), **Name**, **IPv4 CIDR** inside the VirtualNetwork's CIDR and not overlapping one of its Subnets (helper "Must be inside 192.168.101.0/24."; the placeholder is an example inside it: the first block no Subnet of the network uses, with a prefix two bits longer than the network's, from /24 to /26, or the network's own CIDR when it is /26 or longer, and no placeholder when no such block is free, `subnetCidrExample`; /26 is the strictest [prefix limit](design.md#subnet-address-layout) of the plans the installer derives, so the example is never rejected for its length). In a tenant default VirtualNetwork whose default Subnet is not READY, **Create** is `isAriaDisabled` and an inline info Alert and Tooltip say "Available when the default subnet is Ready." ([creation readiness gates](design.md#creation-readiness-gates)). It sends `spec.virtual_network: { id }` and the VirtualNetwork's project. The server checks the prefix limit and, in a default VirtualNetwork, that the default Subnet is READY; the form shows its message. A Subnet has no page, so Create, like **Cancel**, returns to where the user started: the Subnets list or the VirtualNetwork's **Subnets** tab.
- **Row kebab:** **Delete subnet** (`SubnetActionsMenu`; disabled for Default and Auto, while a workload uses it, and while it is being deleted).

### Security groups

- **List page** (`SecurityGroupsListPage`). Columns: **Name** (with badge), **Status**, **Virtual network** (link), **Inbound rules** and **Outbound rules** (counts; the headers wrap), **Project**. Filters: name, project, **Virtual network** (the same `virtualNetwork` URL parameter).
- **Create security group** opens `SecurityGroupCreatePage` (`/networking/security-groups/create`; `?virtualNetwork=<id>` pre-fills and locks the network when opened from a VirtualNetwork, with that VirtualNetwork in the breadcrumb). A **General** section has **Virtual network** (select, READY only, `name (IPv4 CIDR)`) and **Name**; then the **Inbound rules** and **Outbound rules** sections of [Edit rules](#security-groups) (`SecurityGroupRuleSections`, shared by both pages), which start empty and say "No inbound rules. Incoming traffic is blocked." **Create** sends one `SecurityGroups.Create` with the VirtualNetwork's project, the name and both rule lists, then opens the new group's details page; **Cancel** returns to where the user started. The server's rejection, for example ICMP not supported, shows above the form with the values kept.
- **Details page** (`SecurityGroupDetailPage`, `/networking/security-groups/:id`). Header actions: **Edit rules** (disabled for Auto with the Auto Tooltip; `isAriaDisabled` while the group is PENDING or **Updating**, Tooltip "Available when the security group is Ready or Failed.", and while DELETING, Tooltip "Rules cannot be edited while the security group is being deleted.") and **Delete security group** (disabled for Default and Auto, while a workload uses it, and while it is being deleted). Primary Tabs **Details** (one section: **Virtual network**, **Project**, **Created**) and **Rules**. **Rules** shows **Inbound rules (n)** and then **Outbound rules (n)**, each a titled read-only `SecurityGroupRulesTable` (**Protocol**, **Port range**, **Source CIDR** or **Destination CIDR**), in the order of the form. A group has a handful of rules (the tenant default has the installer's few), so one tab holds both without scrolling past a long list; `?tab=rules` selects it.
- **Edit rules** (`SecurityGroupEditRulesPage`, `/networking/security-groups/:id/edit-rules`). A full page form with the **Inbound rules** and **Outbound rules** sections of the create page, loaded with the group's rules. The API allows this one change in place ([API operation constraint](design.md#api-operation-constraint)), so the action stays alongside the rules at create. Each rule is one row: **Protocol** (Select: TCP, UDP, All), **Port from** and **Port to** (TCP and UDP only, required, 1–65535, from ≤ to), and **Source IPv4 CIDR** or **Destination IPv4 CIDR** (canonical). Each section has an **Add rule** link button and a **Remove** action per row. Fields validate on blur and on **Save**. **Save** (primary) sends one `SecurityGroups.Update` with the complete lists ([rule updates](design.md#securitygroup)) and returns to the details page; **Cancel** (link) discards. The public Update has no optimistic-lock option, so when two people edit the same group, the later save replaces both lists; the server only rejects a save while an update is in progress. The per-rule add, edit, and delete modals (`SecurityGroupRuleModal`, `SecurityGroupRuleForm`) are removed.
- **ICMP.** New rules never offer ICMP ("The CLI and UI do not offer ICMP", [SecurityGroup rules](design.md#securitygroup)). A row loaded with an ICMP rule keeps ICMP as its value and option, so Save does not change it silently; where the managers do not support ICMP, the server rejects the update, and the form shows its message, which tells the user to use All. The form marks each ICMP row ("The network does not support ICMP rules. Remove the rule, or use All, which also allows TCP and UDP on every port."), because All widens the rule beyond ICMP. The rejection has no `ErrorInfo` reason, so the form recognizes it by the word ICMP in the message; this is the one exception to [Failure Handling](#failure-handling).
- **Update state.** After Save, a READY group shows **Updating** and a FAILED group shows PENDING; with provider networking disabled the group stays READY without **Updating**, because the save only stores the rules ([Status](design.md#status)). **Updating** and the disabled **Edit rules** last while the message is `Updating`; later in the update the API reports READY with the task message, so **Edit rules** is enabled, and a save then shows the server's message above the form with the rows kept. A final failure shows FAILED with the manager's message, when it has one, in the alert, which is shown even without a message and says that the rules shown are saved but may not be enforced: each manager keeps the rules of its last successful update, so managers can enforce different rules, until a save succeeds ([rule updates](design.md#securitygroup)); **Edit rules** stays available to fix the rules.

### NAT gateways

- **List page** (`NatGatewaysListPage`, `/networking/nat-gateways`). Columns: **Name** (with badge; links to its VirtualNetwork's details page), **Status**, **Virtual network** (link), **External IP** (address), **Project**. Filters: name, project, **Virtual network**. No NATGateway details page.
- **Create NAT gateway** opens `NatGatewayCreatePage` (`/networking/nat-gateways/create`; `?virtualNetwork=<id>` pre-fills and locks the network when opened from a VirtualNetwork, with that VirtualNetwork in the breadcrumb, and **Virtual networks** stays the active nav item). One page, no steps: **Virtual network** (READY VirtualNetworks that are not a tenant default and have no NATGateway, `name (IPv4 CIDR)`; when none qualifies, an inline warning Alert says why), **Name**, and **External IP** per the [ExternalIP picker rule](#externalip-picker-rule). The page describes the NATGateway as outbound translation to addresses outside the virtual network. **Create** creates the NATGateway with the VirtualNetwork's project and opens the VirtualNetwork's details page; **Cancel** returns to where the user started: the NAT gateways list or the VirtualNetwork's page.
- **Create external IP from the picker.** The **External IP** picker ends with **Create external IP** (`createOption`); when no ExternalIP can be picked, it is the only option and the placeholder says "No unused external IP. Create one." The option opens `ExternalIpCreateModal`: **Name** and **IP pool** (READY pools, each with its `available`; pools with 0 disabled), with the VirtualNetwork's project shown read-only. **Create** creates the ExternalIP in that project, closes the modal and selects the new address in the picker; the page keeps what the user typed. The picker accepts the new address while it is still being allocated; the server's [creation readiness gates](design.md#creation-readiness-gates) decide when the NATGateway is created.
- **Row kebab:** **Delete** opens the existing `DetachNatGatewayModal` (disabled for the default NATGateway and while a Cluster on its VirtualNetwork uses it). Changing the ExternalIP is Delete, then Create.

### External IPs

The page (`ExternalIpListPage`, `/networking/external-ips`, description "Addresses from shared provider pools that make workloads reachable from outside the virtual network.") has primary Tabs **Addresses** and **Attachments**; the URL parameter `tab=attachments` selects the second.

- **Addresses tab.** Columns: **Name** (with badge), **Status**, **Address**, **IP pool** (name), **Attached to**, **Project**. Like the other networking lists it has no **Created** column; names and pools stay on one line. Filters: name, project. **Create external IP** opens `ExternalIpCreatePage` (`/networking/external-ips/create`, replacing the wizard): **Project**, **Name** and the **IP pool** select, which shows each pool's `available` and disables pools with 0 (the public List returns only READY pools with free addresses); no Review step. Row kebab: **Delete** (`ExternalIpDeleteModal`, disabled for Default and Auto). While a NATGateway or ExternalIPAttachment uses the address, Delete is `isAriaDisabled` with a Tooltip naming the next step, for example "Delete NAT gateway app-nat first." or "Delete its attachment to virtual machine web-1 first."; the server's guard still decides.
- **Attached to.** The term of attachments in the CLI and the workload pages. The NATGateway or ExternalIPAttachment that references the ExternalIP, on one line as `name (kind)`, for example `default (NAT gateway)`, with the name linked to the NATGateway's VirtualNetwork or the target workload, from `useExternalIpConsumers` and `useExternalIpJoins`. It never comes from `status.attached` alone, because a NATGateway does not set it ([ExternalIP](design.md#externalip)).
- **Attachments tab** (`ExternalIpAttachmentsTable`). Columns: **Name** (with Auto badge), **External IP** (address), **Target** (kind and name, linked to the workload's details page, plus the endpoint for a Cluster), **Status**, **Project**. Filters: name, project. Row kebab: **Delete** (disabled for Auto); the confirmation says the ExternalIP is kept. The tab has no create: an ExternalIP is attached from the workload that uses it, with **Attach external IP** on a virtual machine's details page and per endpoint on a Cluster's ([CaaS UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md)), where the target and, for a Cluster, the endpoint are already known. The empty state says "Attach an external IP from the details page of a virtual machine or cluster." The bare-metal instance page has no attach today; that is the bare-metal UI's to add ([BMaaS networking](/enhancements/OSAC-1437-bmaas-networking/design.md)).

#### ExternalIP picker rule

Every ExternalIP picker (Create NAT gateway, workload attach modals) offers an ExternalIP only when it is ALLOCATED, has no Auto or Default label, `status.attached` is not true, and no NATGateway or ExternalIPAttachment references it (`isSelectable` of `useExternalIpConsumers`, which lists every NATGateway and ExternalIPAttachment). The server's [creation readiness gates](design.md#creation-readiness-gates) still decide.

### External IP pools

Provider admin only, under **Networking**; the route and pages are unchanged. Pools use the private API. Tenants see pools only in the ExternalIP create pickers.

- **List page** (`ExternalIpPoolsListPage`). Columns: **Name**, **Status**, **IPv4 CIDR** (every range of the pool; the field is repeated, but the [server accepts exactly one IPv4 CIDR](design.md#externalippool), and the UI creates a pool with one), **Available** as "12 of 16 (75%)": the available and total addresses and the available share, never rounded to 0% while any address is free or to 100% while any is used ("<1%", ">99%"); "—" for a pool with no addresses. The name links to the details page. **Create external IP pool** opens the create page (disabled until the NetworkClass is READY); the row kebab has **View details** and **Delete**. A pool with addresses but none available shows a **None available** warning Label.
- **Details page** (`ExternalIpPoolDetailsPage`): overview, capacity, and the CIDR. Capacity is a PatternFly Progress bar of the used share (`total` − `available`), labelled "56 of 256 used", warning from 80% used and danger when none is available, so a nearly full pool stands out before it blocks new ExternalIPs, and **Available** as in the list; header action **Delete** (`ExternalIpPoolDeleteConfirmModal`). In both places Delete is `isAriaDisabled` with "Delete its 2 external IPs first." while `status.allocated` is above 0; the server still rejects it while any ExternalIP of the pool exists.
- **Create** (`ExternalIpPoolCreatePage`, replacing the wizard): one page with **Name** and one **IPv4 CIDR**, no Review step; it opens the new pool's details page. There is no tenant field: a pool is shared by all tenants ([Resource hierarchy](design.md#resource-hierarchy)), so the request sets the tenant `shared`. Client validation rejects an empty, malformed, non-canonical, or IPv6 CIDR. It sends `{ metadata: { name, tenant: "shared" }, spec: { ipFamily: IP_FAMILY_IPV4, cidrs: [cidr] } }`.

### Network class

Provider admin only, last item under **Networking** (`NetworkClassPage`, `/admin/infrastructure/network-class`). A read-only view of the NetworkClass from the private `NetworkClasses.List` ([NetworkClass](design.md#networkclass)), with no actions; the installer creates it. The page is named after the resource, not "settings", because the NetworkClass is an installer-owned resource, not configuration edited here. It shows whether networking is ready, which managers were resolved, what they support, and the values every tenant and Subnet got. Three Cards: a full-width Card with the NetworkClass title, its description as the subtitle, and a three-column vertical `DescriptionList` (`columnModifier` 3Col on large screens) of the status, managers and capabilities; then **Tenant defaults** and **Subnet address plan** side by side. They show:

- title, description, and status with message;
- **Fabric manager** and **Kubernetes manager**, one row each: the manager OSAC resolved (`status.network_managers`), with its Ansible role below it; until it is resolved, the requested name (`fabric_manager`, `k8s_manager`) with "(not resolved yet)"; **Kubernetes manager** shows "None (virtual machines are disabled)" when none is requested; and **Network type**;
- **East-west Ethernet** (`supports_east_west_ethernet`);
- **ICMP in security groups** (`status.security_group_icmp`, optional): **Supported**, **Not supported** (help text: a network manager does not support ICMP rules, so security groups reject them; the All protocol still includes ICMP), or **Unknown** while the field is unset because no manager is resolved yet (help text: shown once the network managers are resolved; ICMP rules may be rejected until then);
- **Tenant defaults** (`spec.defaults`): **Virtual network CIDR** and **Subnet CIDR** in two columns, then one read-only **Default security group rules** table with **Direction** (Inbound, Outbound), **Protocol**, **Port range** and **CIDR**, with "No rules." when both lists are empty;
- **Subnet address plan** (`spec.address_plan`): a table of **Range**, **Share** (a percentage) and **Used for**: **Virtual machines** (`overlay`, addresses from the Kubernetes manager), **Fabric** (`fabric`, Fabric DHCP for bare-metal servers and cluster workers, and provider devices), and **Cluster ingress** (`lb_vip`) ([Subnet address plan](design.md#subnet-address-plan)).

The installer fixes the defaults and the plan when it creates the NetworkClass and fails a rollout that changes them, so they are what every tenant and Subnet got; each Card says they are set at installation. A deployment has one NetworkClass, and the page shows it. When sites are introduced, with a NetworkClass per site, this item becomes a **Network classes** list with a site column, and this page becomes its details page.

### Provider admin

The provider admin's **Networking** has **External IP pools** and **Network class** only. The tenant-scoped pages (virtual networks, Subnets, SecurityGroups, NATGateways, ExternalIPs and attachments) are not in the provider admin's navigation, as virtual machines and clusters are not: [PRD FR-11](prd.md#fr-11-unified-networking-ui-and-documentation) gives tenant admins and tenant users the networking resources and the provider admin the NetworkClass and ExternalIPPools. So these pages have no **Tenant** column, filter or picker, and their creates never ask for a tenant: Subnets, SecurityGroups and NATGateways take their VirtualNetwork's project, and an ExternalIP the project the user picks. A console-wide way for the provider admin to act inside a tenant is out of scope here.

### Workload network attachment pickers

The VM, bare-metal, and Cluster create wizards have the **Use tenant default network** toggle. Toggle on: the attachment is omitted and the tenant defaults apply ([defaulting](design.md#network-attachment-field-presence-and-defaulting)). Toggle off: the shared `NetworkAttachmentPickers` component shows the pickers in the table below (bare-metal interface selection: [BMaaS UX Alignment](/enhancements/OSAC-1437-bmaas-networking/design.md#ux-alignment)). Pickers offer only READY resources of one VirtualNetwork, never an automatic SecurityGroup; the server checks the [gates](design.md#creation-readiness-gates) the UI cannot see, and the form shows its message. The VM, bare-metal, and Cluster create wizards all send `auto_external_ip_attachment`

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
- **Pagination.** `useVirtualNetworks`, `useSubnets` and `useSecurityGroups` load every page, and so does the External IPs list (`useExternalIpsData`), because no list has page controls, and so does the External IP pools list. Joins and counts (Subnets per VirtualNetwork, NATGateway addresses, **Attached to**, the ExternalIP picker's consumer check) fetch all pages, so no row is missing its join. The External IPs list's pool, NATGateway and attachment joins load those lists without an ID filter, because a filter that lists every displayed ID outgrows the server's filter size limit on a long list; the NATGateway and attachment lists are the ones the consumer check loads, so they share its cache. A picker that filters in the browser after the server filter fetches all pages too: the Create NAT gateway page's ExternalIP picker and the Cluster attach modal's (`ResourceSelectField` with `loadAllPages`). The **IP pool** picker loads every page too, because the typeahead searches only the loaded items. Other typeahead pickers load one page, 100 items by the server default.
- **ICMP.** Not offered for new rules; an existing ICMP rule is kept on edit ([Security groups](#security-groups)). **Network class** shows whether the managers support it.

## Out of scope

- ExternalIP, Subnet, and NATGateway details pages.
- Bulk selection and bulk actions.
- A topology view.
- A "create with extras" flow (for example a VirtualNetwork with Subnets and a NATGateway in one form).
- Tenant-scoped networking pages for the provider admin, and a console-wide tenant switcher.
- Creating ExternalIPAttachments from the networking pages (they are created from the workload).
- Typed-name delete confirmation.
- UI gating for provider networking disabled.
- Showing `DefaultNetworkingReady`.

## Failure Handling

The UI shows the server's message as a form-level or modal Alert, reads error reasons only from `ErrorInfo.reason` (exception: the ICMP rejection in [Security groups](#security-groups), which has none), and keeps the resource listed. Codes and messages: [Error codes](design.md#error-codes).

| Failure | What the user sees |
|---|---|
| Create rejected (`INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `ALREADY_EXISTS`) | The message above the create form; the values stay. |
| Delete rejected by a [deletion guard](design.md#deletion-dependency-guards) | The message in the delete modal, which stays open. |
| **Edit rules** rejected (for example ICMP not supported, or the group became PENDING) | The message above the form; the edited rows stay. |
| `ABORTED` or `INTERNAL` | The message; the action stays available for retry. |
| A delete task keeps failing | The row shows DELETING with the message; OSAC retries, the UI does nothing. |
| A resource FAILED | Status label with the message; on a details page also an inline danger Alert. |
| Any List or Get failure | `QueryErrorState`; a failing join shows a dash in its column. |

## Implementation Details

- **Hooks** (`api/v1/networking.ts`, `api/v1/external-ip-data.ts`, `api/use-resource.ts`): `useVirtualNetworks`, `useVirtualNetwork`, `useCreateVirtualNetwork`, `useDeleteVirtualNetwork`, `useSubnets`, `useCreateSubnet`, `useDeleteSubnet`, `useSecurityGroups`, `useSecurityGroup`, `useCreateSecurityGroup`, `useUpdateSecurityGroup`, `useDeleteSecurityGroup`, `useNatGateway`, `useNatGateways`, `useExternalIpsData`, `useExternalIpJoins`, `useExternalIpConsumers`; `useNetworkConsumers` and `useClustersOnVirtualNetwork` (`api/v1/networking-consumers.ts`, the workloads that use a Subnet, SecurityGroup or NATGateway); the generic `useListResource`, `useListAllResources`, `useGetResource`, `useCreateResource`, and `useDeleteResource` for NATGateways, ExternalIPAttachments, ExternalIPPools, and the private NetworkClasses. Types from `@osac/types` and `@osac/types/private`.
- **Shared components** (`components/networking/`): `ResourceOriginBadge`, `NetworkingResourceName`, `NetworkingProjectName`, `resourceOrigin.ts` (badges, `isProtectedResource`, `protectedResourceReason`), `deleteDisabledReasons.ts` (the delete pre-checks), `useNetworkClassNotReadyReason` (pool create), and `subnetCidrExample`; `StatusWithMessage`, a wrapper around `ResourceStatusLabel` that makes the Label clickable and opens the message Popover when there is a message (other resources can adopt it), used by the existing status labels (`VirtualNetworkStatusLabel`, `SubnetStatusLabel`, `SecurityGroupStatusLabel`, `NatGatewayStatusLabel`, `ExternalIpStatusLabel`, `ExternalIpAttachmentStatusLabel` (Attaching, Attached, Failed, Detaching), `ExternalIpPoolStatusLabel`); `DeleteResourceModal` for every delete.
- **New pages and components:** `SubnetsListPage`, `NatGatewaysListPage`, `ExternalIpAttachmentsTable`; the create pages `VirtualNetworkCreatePage`, `SubnetCreatePage`, `SecurityGroupCreatePage`, `NatGatewayCreatePage`, `ExternalIpCreatePage` and `ExternalIpPoolCreatePage`; `SecurityGroupEditRulesPage` and its shared `SecurityGroupRuleSections`; `VirtualNetworkNatGatewayRow`; `ExternalIpCreateModal` (the NAT gateway picker's create option); `NetworkClassPage`. The Subnets and SecurityGroups tables are shared by the list pages and the VirtualNetwork tabs.
- **Removed:** `SecurityGroupRuleModal`, `SecurityGroupRuleForm`, `SecurityGroupCreateModal`, `SubnetCreateModal`, `NatGatewayCard`, the NAT gateway network picker modal, `AttachNatGatewayWizard` and its page, `ExternalIpWizard` and `ExternalIpPoolWizard` with their pages; `VirtualNetworkCreateModal` stays only for the workload wizards' inline create; the ExternalIP pool `TenantStep` (removed by the shared-tenant pool change, osac #2217).
- **Test fixtures:** `createMockConnectTransport.ts` serves NATGateways, ExternalIPs, ExternalIPAttachments, FabricDomains, private ExternalIPPools, and the private NetworkClass.

### Component tests

| Page or component | Scenarios |
|---|---|
| Navigation (`shellNav`) | Items and order per role; the provider admin has only External IP pools and Network class; item active on details and create routes |
| `VirtualNetworksListPage`, `VirtualNetworkCreatePage` | Columns, badge, NAT gateway on one line with its links, project column and filter; card footer shows Created; the create page opens the new network's details page |
| `VirtualNetworkDetailPage` | Three tabs; Overview is one vertical list; the NAT gateway row's Create and Delete buttons and their gating; tab Create buttons `isAriaDisabled` with Tooltip unless READY and locked to this network; Delete disabled for Default and with dependents, including fabric domains; project named Root |
| `SubnetsListPage`, `SubnetCreatePage` | Virtual network filter from the URL; the create page pre-fills it (locked from a network) and sends `virtualNetwork: { id }` and its project; project column, link and filter; Delete disabled for Default and Auto and while a workload uses the subnet, enabled for workloads of services that are not enabled; Create waits for the default subnet; CIDR example and helper from the parent; Create and Cancel return to the start |
| `SecurityGroupsListPage` | Virtual network filter; Create opens the create page; wrapped rule headers; one link style |
| `SecurityGroupCreatePage` | Network locked from `virtualNetwork`; rows added and removed; one Create with name, network, project and both rule lists; opens the details page; server rejection shown with values kept |
| `SecurityGroupDetailPage` | Details and Rules tabs; both rule tables with counts; **Edit rules** disabled for Auto and while PENDING or Updating; Delete disabled for Default and Auto and while a workload uses the group; Project and Created on Details |
| `SecurityGroupEditRulesPage` | Add and remove rows; port validation on blur and Save; ICMP not offered on new rows and kept on an existing one; one Update with both complete lists; server error shown |
| `NatGatewaysListPage` | Create opens the create page; Delete disabled for the default and while a cluster uses the gateway; the name links to the network's details page, the address is plain text |
| `NatGatewayCreatePage` | Network picker offers only READY, non-default networks without a NATGateway, locked from `virtualNetwork`; ExternalIP picker rule; **Create external IP** is the last option and the only one when none is free; the created address is selected and the name kept; NATGateway created with the network's project; Create opens the network's details page, Cancel returns to the start |
| `ExternalIpCreateModal` | Name and pool required; pools with 0 disabled; created in the network's project; server rejection shown |
| `ExternalIpListPage` | Tabs from `tab`; **Attached to** from NATGateway and attachment references, not `status.attached`; the create page's pool select disables pools with 0 available; no pool count in the list, project linked and Root for the root project; Attachments tab has no create and Delete is disabled for Auto |
| `ExternalIpPoolCreatePage` | One page, no tenant field; one IPv4 CIDR; tenant `shared` in the request; opens the new pool |
| `ExternalIpPoolsListPage`, `ExternalIpPoolDetailsPage` | Delete disabled while the pool has allocated external IPs; Create disabled until the network class is Ready |
| `NetworkClassPage` | Status, one row per manager (resolved with its role, or not resolved yet) and capabilities from the fixture, including Supported, Not supported and Unknown ICMP; tenant defaults with one rules table with Direction and an empty state; address plan as a table; three Cards; no actions |
| `StatusWithMessage` | Clickable Label opens the Popover with the message; plain Label without one |

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
