# OSAC Tenant UI: Networking Section
| Field       | Value   |
|-------------|---------|
| Author(s)   | Elay Aharoni, Dan Manor |
| Jira        | [OSAC-1425](https://redhat.atlassian.net/browse/OSAC-1425) |
| Date        | 2026-06-28 |
## 1. Problem Statement
Tenant users and tenant admins currently lack a dedicated UI for managing networking resources (VirtualNetworks, Subnets, SecurityGroups, PublicIPs) in the OSAC platform. While the fulfillment API provides full CRUD capabilities for these resources, users must either use the CLI or construct API calls directly. Additionally, when creating VMs through the VMaaS wizard, users have no integrated way to create or select networking resources inline—they must context-switch to external tools or pre-create resources before provisioning compute instances. This creates friction in the user experience, increases time-to-first-VM for new tenants, and reduces discoverability of networking capabilities.
## 2. Goals and Non-Goals
### 2.1 Goals
- Tenant users can create, list, view, and delete VirtualNetworks through a dedicated Networking section in the OSAC UI sidebar
- Tenant users can manage Subnets and SecurityGroups scoped to a VirtualNetwork from the VirtualNetwork detail page
- Tenant users can allocate and release PublicIPs from provider-managed pools through a dedicated PublicIPs page
- New tenants creating their first VM can provision all required networking resources (VirtualNetwork, Subnet, SecurityGroup) inline within the VM creation wizard without leaving the wizard flow
- Returning tenants can select from existing networking resources in the VM creation wizard with smart defaults (auto-select when only one option exists)
### 2.2 Non-Goals
- NATGateway, ExternalIPAttachment, NetworkClass management (these are provider-only or future scope)
- PublicIPPool CRUD operations (pools are provider-managed, read-only for tenants)
- BaremetalInstance networking or Cluster networking (out of scope for VMaaS phase)
- Migration or enhancement of the existing AdminNetworksPage topology view (future scope)
## 3. Requirements
### 3.1 Functional Requirements
#### Virtual Networks
- **FR-1:** The UI must provide a VirtualNetworks list page (`/networking/virtual-networks`) displaying all VirtualNetworks owned by the tenant with columns for Name, IPv4 CIDR, Subnets count, and Status
- **FR-2:** The VirtualNetworks list page must support filtering by Status, sorting by Name/Status, and searching by Name
- **FR-3:** The UI must provide a "Create virtual network" action that opens a side panel form with fields for NetworkClass (required dropdown showing available NetworkClasses with name and region), Name (required, DNS-valid, unique within tenant), IPv4 CIDR (required, /16 to /24 range), and IPv6 CIDR (optional)
- **FR-4:** The Create VirtualNetwork form must validate inputs inline (show validation errors below each field) and disable the Create button until all required fields are valid
- **FR-5:** After successful VirtualNetwork creation, the UI must close the form, refresh the list, show a success toast notification, and display the new VN with "Provisioning" status
- **FR-6:** The UI must provide a VirtualNetwork detail page (`/networking/virtual-networks/:id`) showing the VN name as page title, breadcrumb navigation, status badge, IPv4 CIDR (and IPv6 CIDR if configured) as key properties, and a Delete action in the header
- **FR-7:** The VirtualNetwork detail page must display three tabs: Subnets (default), Security Groups, and Details
- **FR-8:** The UI must block deletion of a VirtualNetwork if it has subnets or security groups, showing an error message directing the user to delete child resources first

#### Subnets

- **FR-9:** The Subnets tab on the VirtualNetwork detail page must display all subnets belonging to that VN in a table with columns for Name, CIDR, and Status
- **FR-10:** The Subnets tab must provide a "Create subnet" action that opens a side panel form with the parent VN pre-selected and fields for Name (required, DNS-valid) and CIDR (required, must be within parent VN CIDR, must not overlap existing subnets)
- **FR-11:** The Create Subnet form must show the parent VN CIDR as context and display existing subnet CIDRs to help users select a non-overlapping range
- **FR-12:** Clicking on a subnet name must show subnet metadata and a list of attached resources (compute instances) in a side drawer
- **FR-13:** Subnets must not have their own top-level sidebar entry—they are managed exclusively from the VirtualNetwork detail page
- **FR-14:** The UI must block deletion of a Subnet if it has attached compute instances, showing an error message directing the user to remove or migrate instances first

#### Security Groups

- **FR-15:** The UI must provide a SecurityGroups list page (`/networking/security-groups`) displaying all SecurityGroups across all VirtualNetworks with columns for Name, Virtual Network (link to VN detail), Inbound Rules count, Outbound Rules count, and Status
- **FR-16:** The SecurityGroups list page must support filtering by Virtual Network and Status, and searching by Name
- **FR-17:** The UI must provide a "Create security group" action (available from both the SG list page and the VN detail Security Groups tab) that opens a side panel form with fields for Virtual Network (required dropdown, pre-selected if triggered from VN detail), Name (required, DNS-valid), and expandable Inbound/Outbound Rules sections
- **FR-18:** The Create SecurityGroup form must allow users to add multiple inbound and outbound rules inline, with each rule having fields for Protocol (dropdown: TCP/UDP/ICMP/All), Port Range (text input, disabled for ICMP), and Source/Destination CIDR (text with CIDR validation)
- **FR-19:** The UI must provide a SecurityGroup detail page (`/networking/security-groups/:id`) with tabs for Inbound Rules, Outbound Rules, and Details
- **FR-20:** The Inbound Rules and Outbound Rules tabs must display rules in a table (columns: Protocol, Port Range, Source/Destination CIDR) with "Add Rule" action and row-level Edit/Delete actions. Rule edits use `PATCH /v1/securitygroups/{id}` to replace the full rule set (the API does not support individual rule-level endpoints)
- **FR-21:** SecurityGroups must be accessible from both the sidebar (top-level) and the VirtualNetwork detail page (Pattern 3: top-level but VN-scoped)
- **FR-22:** The UI must block deletion of a SecurityGroup if it is attached to compute instances, showing an error message directing the user to remove it from all instances first

#### Public IPs

- **FR-23:** The UI must provide a PublicIPs list page (`/networking/public-ips`) displaying all PublicIPs allocated to the tenant with columns for Address, Pool, Attached To (resource name + type, or dash if unattached), and Status
- **FR-24:** The PublicIPs list page must support filtering by Pool, Status, and Attached (yes/no)
- **FR-25:** The UI must provide an "Allocate IP" action that opens a modal dialog with fields for Pool (required dropdown showing available pools with remaining IP count, e.g., "external-pool-1 (Available: 245 IPs)") and Name (required, label for this allocation)
- **FR-26:** After successful IP allocation, the UI must close the modal and show the new IP as "Available" (unattached) in the list
- **FR-27:** The UI must provide Attach and Detach row actions for PublicIPs—Attach (if Available) opens a side panel listing eligible resources (ComputeInstances/VMs) in a searchable table; Detach (if Attached) opens a confirmation modal warning the user that the VM will lose external connectivity on this IP
- **FR-28:** The UI must provide a Release action for PublicIPs with confirmation, blocked if the IP is currently attached

#### Sidebar Navigation

- **FR-29:** The tenant user sidebar must add a new "Networking" section with sub-items: Virtual Networks, Security Groups, Public IPs (Subnets are not a sidebar item)
- **FR-30:** The tenant admin sidebar must add the same "Networking" section under the existing Management section, preserving the existing Infrastructure (Networks topology view) section

#### VMaaS Wizard Integration

- **FR-31:** The VM creation wizard (`/vms/create/:catalogItemId`) must include a Network Configuration step after basic VM settings (name, SSH key, etc.) with sections for Network Attachment and Public IP (optional)
- **FR-32:** The Network Attachment section must provide fields for Virtual Network (required dropdown showing all tenant VNs with name and CIDR, with "Create new VN" link), Subnet (required dropdown filtered to selected VN, showing CIDR and available IP count, with "Create new Subnet" link), and Security Groups (optional multi-select checkboxes showing SGs scoped to selected VN with rule count summary, with "Create new Security Group" link)
- **FR-33:** When a user clicks "Create new VN" from the wizard, the UI must open the Create VN side panel that overlays the wizard—after VN creation, the new VN must be auto-selected in the wizard
- **FR-34:** The wizard must support multi-NIC configuration via an "[+ Add another network attachment]" button—each attachment has its own VN/Subnet/SG selection, and exactly one attachment must be marked as Primary (radio button) which determines the default gateway. Note: All subnets must belong to the same VirtualNetwork (OSAC platform constraint to simplify initial networking model; future phases may support cross-VN attachments)
- **FR-35:** The wizard's Public IP section must provide radio button options: No public IP, Use existing (dropdown of Available PublicIPs), or Allocate new from pool (dropdown of pools with IP count)—if "Allocate new" is selected, a new PublicIP must be allocated and attached during VM creation
- **FR-36:** The wizard must enforce that VirtualNetwork is required (block VM creation without network attachment), Subnet is required and must belong to the selected VN, and show a warning if no Security Groups are selected ("No security groups selected. Your VM will have no firewall rules.")
- **FR-37:** The wizard must implement smart defaults: if the tenant has exactly one VN auto-select it, if the selected VN has exactly one subnet auto-select it, if the selected VN has exactly one SG pre-check it, if only one PublicIP pool exists pre-select it for "Allocate new"
- **FR-38:** If no VNs exist when the wizard reaches the Network Configuration step, the UI must show a prominent message "You need to create a virtual network before provisioning a VM" with a "Create Virtual Network" button that opens the inline Create VN side panel (see FR-33) with automatic return to the wizard after creation

#### Error States and Edge Cases

- **FR-39:** When no resources exist, list pages must show empty states with illustrations, helpful headings (e.g., "No virtual networks yet"), descriptions, and primary action buttons (e.g., "Create virtual network")
- **FR-40:** When PublicIP pools are unavailable, the PublicIPs list page must show an informational banner: "No IP pools available. Contact your provider to provision IP address pools."
- **FR-41:** While a resource is in Provisioning or Deleting state, the UI must disable Delete actions, show a spinner next to the status badge, and auto-refresh the list every 5 seconds until the resource reaches a terminal state (Ready or Failed)
- **FR-42:** For failed resources, the UI must show the error message from the API in a collapsible alert on the detail page and provide Retry and Delete actions. Retry re-submits the original creation request (POST) to the same endpoint; the UI does not persist intermediate state—users must re-enter form data if the retry also fails
- **FR-43:** The UI must use TanStack Query's stale-while-revalidate pattern for concurrent modification handling, show a Refresh button in the toolbar, auto-refetch on window focus, and show optimistic updates for delete operations (gray out the row immediately)

#### API Integration

- **FR-44:** The UI must use protobuf-generated types from `libs/types/src/osac/public/v1/` and create TanStack Query hooks for each resource (useVirtualNetworks, useVirtualNetwork, useCreateVirtualNetwork, useDeleteVirtualNetwork, etc.)
- **FR-45:** The UI must call the following REST gateway endpoints: VirtualNetworks (GET /api/fulfillment/v1/virtual_networks, GET /api/fulfillment/v1/virtual_networks/{id}, POST /api/fulfillment/v1/virtual_networks, PATCH /api/fulfillment/v1/virtual_networks/{id}, DELETE /api/fulfillment/v1/virtual_networks/{id}), Subnets (GET /api/fulfillment/v1/subnets with filter by virtual_network, GET /api/fulfillment/v1/subnets/{id}, POST /api/fulfillment/v1/subnets, DELETE /api/fulfillment/v1/subnets/{id}—note: Subnets are create/delete only, no PATCH endpoint), SecurityGroups (GET /api/fulfillment/v1/security_groups with filter by virtual_network, GET /api/fulfillment/v1/security_groups/{id}, POST /api/fulfillment/v1/security_groups, PATCH /api/fulfillment/v1/security_groups/{id}, DELETE /api/fulfillment/v1/security_groups/{id}), PublicIPs (GET /api/fulfillment/v1/public_ips, GET /api/fulfillment/v1/public_ips/{id}, POST /api/fulfillment/v1/public_ips, DELETE /api/fulfillment/v1/public_ips/{id}), PublicIPPools (GET /api/fulfillment/v1/public_ip_pools, read-only), NetworkClasses (GET /api/fulfillment/v1/network_classes, read-only)
### 3.2 Non-Functional Requirements
- **NFR-1:** The UI must be built with React 19 and TypeScript using the PatternFly 6 design system (Red Hat design system)
- **NFR-2:** The UI must use react-router-dom v7 for routing, TanStack Query (React Query) for data fetching, and Connect-ES for gRPC-Web client integration
- **NFR-3:** The UI must follow the file structure pattern: list pages in `libs/ui-components/src/pages/networking/`, detail pages in the same directory, table/form components in `libs/ui-components/src/components/networking/`, and TanStack Query hooks in `libs/ui-components/src/api/v1/`
- **NFR-4:** The UI must use PatternFly components: PageSection/Title/Text for page layout, Table/Thead/Tr/Th/Tbody/Td for tables, Toolbar/ToolbarContent/ToolbarItem for search/filter toolbars, Form/FormGroup/TextInput/FormSelect for forms, DrawerPanelContent for side panels, Modal for confirmations, Label for status badges, EmptyState for empty states, Tabs/Tab for detail pages, Breadcrumb/BreadcrumbItem for navigation, Wizard/WizardStep for the VM wizard
- **NFR-5:** Status badges must use consistent colors: Ready (green pf-m-green), Provisioning (blue pf-m-blue with spinner), Failed (red pf-m-red), Deleting (orange pf-m-orange), Available (green for PublicIPs), Attached (blue for PublicIPs)
- **NFR-6:** Tables must be responsive using PatternFly's responsive table breakpoints—on small screens, use compound expansion to show row details instead of navigating to a detail page
- **NFR-7:** Side panels (create forms) must become full-width drawers on mobile, and the sidebar must remain collapsible as in the current OSAC UI
- **NFR-8:** All form inputs must have associated labels (PatternFly FormGroup handles this), status badges must have aria-labels (include text like "Status: Ready," not just color), table row actions must be keyboard-navigable, modal focus must be trapped (PatternFly Modal handles this), status changes must be announced via aria-live regions, and CIDR inputs must have helper text explaining the expected format
- **NFR-9:** The UI must handle at least 100 VirtualNetworks, 500 Subnets, 200 SecurityGroups, and 1000 PublicIPs per tenant with acceptable performance—pagination should be enforced when counts exceed these thresholds
## 4. Acceptance Criteria
- [ ] A tenant user can navigate to Networking > Virtual Networks from the sidebar and see a list of all their VirtualNetworks with Name, IPv4 CIDR, Subnets count, and Status columns
- [ ] A tenant user can click "Create virtual network" and successfully create a VN by filling in Name and IPv4 CIDR fields with inline validation
- [ ] A tenant user can click on a VirtualNetwork name to see the detail page with Subnets, Security Groups, and Details tabs
- [ ] A tenant user can create a Subnet from the Subnets tab with the parent VN pre-selected, and the form validates that the subnet CIDR is within the parent VN CIDR and does not overlap existing subnets
- [ ] A tenant user can view all SecurityGroups across all VNs from the Networking > Security Groups page, filtered by VirtualNetwork
- [ ] A tenant user can create a SecurityGroup from either the SG list page or the VN detail page, selecting a VN and adding inbound/outbound rules inline with Protocol, Port Range, Source/Destination CIDR, and Description fields
- [ ] A tenant user can view SecurityGroup inbound and outbound rules on the SG detail page in separate tabs, with Add Rule, Edit, and Delete actions
- [ ] A tenant user can allocate a PublicIP from the Networking > Public IPs page by selecting a pool and providing a name
- [ ] A tenant user can see Attach and Detach actions for PublicIPs—Attach shows a searchable list of VMs, Detach shows a confirmation modal
- [ ] A new tenant creating their first VM sees "You need to create a virtual network before provisioning a VM" when reaching the Network Configuration step in the VM wizard
- [ ] A new tenant can click "Create Virtual Network" from the wizard, create a VN inline (side panel overlay), and the new VN is auto-selected in the wizard after creation
- [ ] A new tenant can create Subnets and SecurityGroups inline from the wizard using "Create new Subnet" and "Create new Security Group" links, with the current VN pre-selected
- [ ] A returning tenant with one VN, one Subnet, and one SG sees all three auto-selected in the VM wizard Network Configuration step
- [ ] A tenant user can add multiple network attachments in the VM wizard via "[+ Add another network attachment]" and mark one as Primary
- [ ] The wizard blocks VM creation if no VirtualNetwork is selected and shows a warning if no SecurityGroups are selected
- [ ] Empty states show helpful illustrations and "Create" buttons on all list pages when no resources exist
- [ ] Resources in Provisioning or Deleting state show a spinner, disable Delete actions, and auto-refresh every 5 seconds
- [ ] Deletion of a VirtualNetwork is blocked if it has subnets or security groups, with an error message directing the user to delete children first
- [ ] Deletion of a Subnet is blocked if it has attached compute instances, with an error message
- [ ] Deletion of a SecurityGroup is blocked if it is attached to compute instances, with an error message
- [ ] Deletion of a PublicIP is blocked if it is currently attached to a resource
- [ ] All forms validate inputs inline and disable the Create/Submit button until all required fields are valid
- [ ] Status badges use correct colors (Ready=green, Provisioning=blue with spinner, Failed=red, Deleting=orange, Available=green for PublicIPs, Attached=blue for PublicIPs) and include aria-labels for accessibility
## 5. Assumptions
- The OSAC UI codebase uses a pnpm monorepo structure with the UI components in `libs/ui-components/src/`
- The fulfillment API endpoints listed in Section 3.1 (FR-45) are already implemented and stable. Note: PublicIP attach/detach (FR-27, FR-28, FR-35) requires the private API endpoint `/api/private/v1/public_ip_attachments`, which is not exposed in the public API—the UI will need appropriate permissions to call the private API for these operations
- The existing VM creation wizard at `/vms/create/:catalogItemId` has a NetworkAttachmentFields component that can be extended or replaced with the new Network Configuration step
- The existing AdminNetworksPage (topology view) does not require changes as part of this feature—it will be preserved as-is under Infrastructure > Networks for tenant admins
- PatternFly components (DrawerPanelContent, Modal, Wizard, etc.) provide sufficient accessibility support (keyboard navigation, focus management, aria-labels) without additional custom implementation
- The protobuf-generated types in `libs/types/src/osac/public/v1/` include all necessary types for VirtualNetwork, Subnet, SecurityGroup, PublicIP, and PublicIPPool
## 6. Dependencies
- fulfillment-service REST gateway endpoints must be available and stable (GET/POST/PATCH/DELETE for /api/fulfillment/v1/virtual_networks, /api/fulfillment/v1/subnets, /api/fulfillment/v1/security_groups, /api/fulfillment/v1/public_ips)
- fulfillment-service private API endpoint `/api/private/v1/public_ip_attachments` (POST/DELETE) for PublicIP attach/detach operations (FR-27, FR-28, FR-35)
- protobuf-generated TypeScript types must be available in `libs/types/src/osac/public/v1/` for VirtualNetwork, Subnet, SecurityGroup, PublicIP, PublicIPPool, NetworkClass
- The existing OSAC UI navigation/sidebar framework must support adding a new "Networking" section with sub-items
- The existing VM creation wizard framework must support adding a new Network Configuration step with inline resource creation
## 7. Risks
### 7.1 PatternFly version mismatch
- **Status:** RESOLVED — OSAC UI is confirmed to be on PatternFly 6.4.x, so the PRD's PF6 requirement is satisfied
### 7.2 Inline resource creation from wizard complicates state management
- **Owner:** UI team
- **Mitigation:** Use TanStack Query's cache invalidation and refetch mechanisms to ensure the wizard's VN/Subnet/SG dropdowns refresh after inline creation. Test the round-trip flow (create VN → auto-select → create Subnet → auto-select → continue wizard) thoroughly to ensure state consistency.
### 7.3 Performance degradation with large resource counts
- **Owner:** UI team
- **Mitigation:** Implement pagination on list pages when resource counts exceed 100 VNs, 500 Subnets, 200 SGs, or 1000 PublicIPs. Use TanStack Query's pagination support and the API's `page` and `size` parameters. Monitor performance in testing with realistic data volumes.
## 8. Open Questions
### 8.1 Should the "Create new VN" link in the wizard navigate away or use an inline overlay?
- **Owner:** UX team / Product Owner
- **Impact:** Affects the wizard integration implementation (FR-33). Option (A) is an inline side panel overlay that preserves wizard state. Option (B) navigates to `/networking/virtual-networks` and loses wizard state. Option (C) is an inline drawer within the wizard step itself. The specification leans toward Option (A) but doesn't definitively resolve this.
### 8.2 What specific enhancements to the AdminNetworksPage topology view are in scope?
- **Owner:** Product Owner
- **Impact:** Non-Goals section states topology view enhancements are future scope. Clarify whether any enhancements (e.g., integration with the new Networking section, updated styling) are expected in a future phase.
### 8.3 What testing strategy is required for this feature?
- **Owner:** QE team / Product Owner
- **Impact:** Determines deliverables and acceptance criteria. Should the feature include: (a) unit tests for all components, (b) E2E tests for critical flows (VN creation, wizard integration), (c) accessibility testing with specific tools (e.g., axe, NVDA), (d) manual testing only, or (e) a combination? The specification does not specify testing requirements.
### 8.4 What are the exact error message strings for validation failures?
- **Owner:** UX team / Technical Writer
- **Impact:** Affects form validation implementation (FR-4, FR-11, FR-18). The specification describes validation rules (e.g., "CIDR must be within parent VN CIDR") but does not provide exact error message strings. Should these follow a standard template or be defined per-field?
### 8.5 What performance SLOs should the UI meet for list page load times?
- **Owner:** Product Owner
- **Impact:** NFR-10 assumes pagination thresholds (100 VNs, 500 Subnets, etc.) but does not specify target load times. Should list pages load within 2 seconds at p95? What is the acceptable performance envelope for filter/search operations?
