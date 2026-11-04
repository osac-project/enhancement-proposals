# Resource-Level Pull Secrets for VMaaS Private Registries

| Field | Value |
|---|---|
| Author(s) | Ygal Blum |
| Jira | [OSAC-5172 — Support referencing pull secrets for private registries at DiskImage, ComputeInstance, and CatalogItem levels](https://redhat.atlassian.net/browse/OSAC-5172) |
| Date | 2026-10-23 |
| Last revised | 2026-11-03 |
| Revision | 8 — User Stories |
| Target milestone | 0.6, as recorded in the feature's Jira Fix Version |

## 1. Problem Statement

VMaaS users need to provision virtual machines from private image registries without making repositories public or manually supplying credentials outside OSAC. Typed pull-secret support already exists through completed [OSAC-5099](https://redhat.atlassian.net/browse/OSAC-5099); this feature adds the resource-level references needed to use it from a DiskImage, a ComputeInstanceCatalogItem, or a ComputeInstance. Cloud Provider Admins and Tenant Admins need reusable image and catalog credentials, while Tenant Users need an optional instance-specific reference that overrides the inherited pull secret. Provider-managed DiskImages must also work for tenants who cannot access the underlying secret, without exposing that secret's identity or contents.

## 2. Goals and Non-Goals

### 2.1 Goals

- Authorized users provision VMs from private registry images using credentials referenced through the UI, CLI, or API, with no need to make the image repository public.
- Users obtain predictable selection of one pull secret across DiskImage, catalog item, and ComputeInstance, without repeating a reference already supplied at a less-specific level.
- Tenants provision from provider-managed DiskImages without discovering the protected secret's ID, name, or value.
- Users encounter predictable reference-change and secret-deletion rules across reusable resources and individual instances.

### 2.2 Non-Goals

- Installation-wide and tenant-scoped default pull-secret references; these are separate work tracked by [OSAC-5302](https://redhat.atlassian.net/browse/OSAC-5302).
- Creating or managing pull-secret contents, or adding new secret-management capabilities. Typed-secret management is separate; enforcing the reference-based deletion restrictions below is in scope.
- CaaS cluster-instance credential management.
- Credential rotation or expiry management.
- Integration with external secret-management systems.
- Registry mirror or proxy configuration.
- Adding or managing registry CA trust configuration.
- Multi-registry failover or fallback logic.

### 2.3 User Stories

These stories apply through the UI, CLI, and API within each persona's existing resource and secret permissions.

#### Cloud Provider Admin

- As a Cloud Provider Admin, I want to associate an authorized pull-secret reference with a shared DiskImage or ComputeInstanceCatalogItem, so that tenants can provision VMs from private registries without discovering or explicitly reusing the protected secret reference.

#### Tenant Admin

- As a Tenant Admin, I want to reference an authorized pull secret on my tenant's DiskImage or ComputeInstanceCatalogItem, so that authorized tenant users can provision private-registry VMs without supplying that reference on every instance.

#### Tenant User

- As a Tenant User, I want to use inherited credentials or supply an authorized ComputeInstance pull-secret reference at creation, so that I can launch a VM from a private image registry without making the repository public.

## 3. Requirements

In this document, “catalog item” means ComputeInstanceCatalogItem. An **explicit reference** identifies the single secret supplied on a resource. The **selected pull secret** is the complete secret chosen from the most-specific resource with a supplied reference, under FR-4 and FR-5. An empty reference means no explicit selection at that level; it does not disable inheritance. Reference configuration and presentation through the UI, CLI, and API follow the existing [OSAC-1330 type-safe resource-reference contract](../OSAC-1330-type-safe-resource-references/prd.md), subject to FR-7 and NFR-1 confidentiality and authorization constraints. Serialized request fields and storage mechanisms remain technical-design and API-specification concerns.

### 3.1 Functional Requirements

#### Referencing and inheritance

- **FR-1 — DiskImage reference:** Cloud Provider Admins and Tenant Admins must be able to attach one optional pull-secret reference to a DiskImage through the UI, CLI, and API, within their authorized resource scope.
- **FR-2 — Catalog-item reference:** Cloud Provider Admins and Tenant Admins must be able to attach one optional pull-secret reference to a catalog item through the UI, CLI, and API, within their authorized resource scope.
- **FR-3 — Instance reference:** Tenant Users must be able to supply one optional pull-secret reference when provisioning a ComputeInstance through the UI, CLI, and API.
- **FR-4 — Whole-secret precedence:** OSAC must select one complete pull secret from the most-specific resource that supplies a reference: ComputeInstance first, then catalog item, then DiskImage. Credentials from different resource levels must not be combined. A supplied more-specific secret must not be supplemented with registry entries from less-specific secrets.
- **FR-5 — Empty means inherit:** Leaving a reference empty must allow selection to continue at the less-specific levels in FR-4; an empty reference must not disable inherited pull-secret use.

#### Provisioning and protected inherited use

- **FR-6 — Private-registry provisioning:** VMaaS must use the selected pull secret’s credentials to provision VMs from private image registries, including registries where anonymous access is disabled.
- **FR-7 — Protected provider-managed images and non-reusable references:** A Cloud Provider Admin must be able to create a DiskImage backed by a secret that tenants cannot access. Authorized tenants must be able to provision ComputeInstances from that DiskImage without permission to retrieve or select the protected secret. Inherited credential use must be implicit in the consuming UI, CLI, and API: no inherited secret reference, identity, or inheritance indication may be returned or displayed. Normal authorized visibility of source configuration and the caller’s own explicit references remains unchanged. Inherited use must not authorize Tenant Users or Tenant Admins to reuse the protected reference explicitly on their own DiskImages, catalog items, or ComputeInstances, even if they know its ID or name. Enforce this boundary in the API as well as the UI and CLI; explicitly authorized secret selections remain allowed. NFR-1 applies to all tenant-facing representations.
- **FR-8 — Immediate explicit-reference validation:** On a permitted resource create or update, the UI/CLI/API must immediately reject an explicit secret reference that does not exist, is inaccessible or unauthorized, or has an incompatible type, before saving the resource, following existing secret-reference validation conventions. References must use the existing pull-secret type; no new secret type is introduced. An empty optional reference remains valid for inheritance. Authorized protected inheritance must not be rejected merely because the tenant cannot directly retrieve or select the inherited secret. These checks do not guarantee that the selected credentials will authorize a later image pull. [Jira: OSAC-5099]

#### Lifecycle and documentation

- **FR-9 — Reusable-reference changes:** Cloud Provider Admins and Tenant Admins must be able to change or clear a DiskImage or catalog-item reference within their authorized scope. The changed resolution applies only to instances created afterward; it must not alter the selected secret of an existing instance, including one whose initial provisioning has not yet begun. An instance created before a source-reference change and provisioned afterward must still use its creation-time selection.
- **FR-10 — Instance-reference immutability:** A ComputeInstance pull-secret reference must be immutable from creation, including when initially empty. After creation, users must not first-set an empty reference, replace a supplied reference, or clear a supplied reference, regardless of whether initial provisioning is pending, failed, or successful. An initially empty reference resolves inheritance once at instance creation through catalog item then DiskImage under FR-4 and FR-5. The explicit instance reference remains empty; the inherited choice does not become a visible resolved reference, identity, origin, or inheritance indicator. This restriction applies only to the ComputeInstance reference: authorized DiskImage and catalog-item changes remain allowed under FR-9, and existing secret-content update rules remain unchanged.
- **FR-11 — Referenced-secret deletion protection:** Deleting a secret must be blocked while any OSAC resource not marked for deletion refers to it: a DiskImage or catalog item through its reference, or a ComputeInstance through its creation-time selected secret, whether explicit or inherited. Instance protection begins immediately at creation, before initial provisioning, and continues while provisioning is pending, failed, or successful until OSAC successfully marks that instance for deletion. Changing or clearing a source DiskImage or catalog-item reference, or marking that source for deletion, must not change a non-deleting instance's selection or release its protection. Once OSAC successfully marks a referring resource for deletion, that resource no longer blocks secret deletion; waiting for its full cleanup must not prolong the guard. A failed deletion request or a client-supplied indication of deletion does not release protection. Other non-deleting referring resources still block secret deletion, and ordinary deletion authorization still applies. Releasing a resource's guard does not automatically delete the secret.
- **FR-12 — User, CLI, and API documentation:** Documentation must explain how to attach references through the UI, CLI, and API using the existing OSAC-1330 contract, how whole-secret precedence and empty-reference inheritance work, which references can be changed or cleared, and when secret deletion is blocked. It must describe permitted operations at all three resource levels, immediate explicit-reference validation, instance-reference immutability from creation including initially empty references, implicit protected inheritance, the prohibition on explicitly reusing a protected reference, and established error conventions. It must explain once-at-creation inheritance selection with the explicit reference remaining empty and no inherited-choice metadata exposed, distinguish authorized source-reference changes affecting only later-created instances from the unchanged selection of earlier-created instances even before initial provisioning, and describe protection of each selected secret from instance creation until OSAC marks the instance for deletion. It must explain that a source's deletion does not release a non-deleting instance's guard, that a referring resource's full cleanup does not prolong its guard once marked for deletion, and that other non-deleting referrers and ordinary authorization still apply without automatic secret deletion.

### 3.2 Non-Functional Requirements

- **NFR-1 — Protected-secret confidentiality:** Tenant-facing UI, CLI, and API responses, selectors, and error messages must not disclose the ID, name, or value of an inherited provider/system secret that the tenant is not authorized to access. Using a provider-managed DiskImage must not grant tenants permission to list, retrieve, or discover that protected secret. This constraint concerns protected inherited secrets; it does not redefine visibility of a tenant's own authorized explicit selections. [Jira: OSAC-5425]
- **NFR-2 — Existing error conventions:** Reference validation, incompatible types, immutable-field changes, secrets still in use, and provisioning or registry-authentication failures must follow the existing OSAC conventions for analogous cases. Do not introduce a feature-specific error taxonomy, message catalog, or protocol codes. Reuse must preserve FR-7 and NFR-1, including protected-secret nondisclosure and non-reuse.

## 4. Acceptance Criteria

These criteria describe observable outcomes, not test procedures. They apply through the UI, CLI, and API wherever the operation is exposed, within the authorization, confidentiality, and error conventions in FR-7, FR-8, NFR-1, and NFR-2. Existing source-resource deletion restrictions and other non-deleting references still apply. Releasing a deletion guard does not automatically delete the secret.

- [ ] **AC-1 — Image-level credentials:** Authorized admins can configure a DiskImage pull-secret reference. With valid image-level credentials and no more-specific reference, an authorized Tenant User can provision a private-registry VM without enabling anonymous access or making the repository public. Covers FR-1, FR-3, FR-5, FR-6.
- [ ] **AC-2 — Inherited selection:** Without an instance reference, the catalog-item secret is selected when supplied, otherwise the DiskImage secret. If neither supplies a reference, neither contributes a resource-level secret. Covers FR-2, FR-4–FR-6.
- [ ] **AC-3 — Instance override:** An instance reference takes precedence whether lower-level references are present or absent. Provisioning succeeds when the selected credentials authorize the requested private image. Covers FR-3, FR-4, FR-6.
- [ ] **AC-5 — Implicit protected inheritance:** Authorized tenants can provision from a provider-managed DiskImage without access to its protected secret. Consuming interfaces expose neither its inherited reference or identity nor an inheritance indication; normal authorized source and explicit-reference visibility is unchanged. Covers FR-7, NFR-1.
- [ ] **AC-6 — Creation-time selection:** Changing or clearing an image or catalog reference affects only later-created instances. Existing instances retain their creation-time selected secret, even if initial provisioning has not begun; new instances follow the current inheritance rules. Covers FR-4, FR-5, FR-9, FR-10.
- [ ] **AC-7 — Immutable instance reference:** An instance reference cannot be first-set, replaced, or cleared after creation, regardless of provisioning state. An initially empty explicit reference remains empty while using its creation-time inherited selection. Covers FR-4, FR-5, FR-7, FR-9, FR-10, NFR-1–NFR-2.
- [ ] **AC-8 — Instance deletion guard:** The creation-time selected secret, whether explicit or inherited, is protected from instance creation, including before provisioning. Only OSAC successfully marking the instance for deletion releases that instance's guard; provisioning state, later source-reference changes or deletion, failed deletion requests, and client-supplied deletion indications do not. Full cleanup need not finish. Covers FR-9, FR-11, NFR-2.
- [ ] **AC-9 — Reusable-resource deletion guards:** A non-deleting DiskImage or catalog reference independently protects its secret. Replacing or clearing the reference releases only that source's dependency on the previous secret. OSAC successfully marking the source for deletion releases its guard without waiting for cleanup. Failed requests or client-supplied deletion indications do not release it. Covers FR-9, FR-11.
- [ ] **AC-10 — Invalid-reference rejection:** Nonexistent, unauthorized or inaccessible, and incompatible-type explicit references are rejected before saving. Empty references and authorized protected inheritance remain valid; inherited use does not require direct access to the protected secret. Covers FR-5, FR-7, FR-8, NFR-1–NFR-2.
- [ ] **AC-11 — Confidentiality boundary:** Reference views, selectors, responses, and failure messages do not reveal protected secret IDs, names, or values, or grant tenants additional secret discovery, listing, or retrieval access. Authorized inherited use remains available. Covers FR-7, NFR-1–NFR-2.
- [ ] **AC-12 — Usable documentation:** UI, CLI, and API documentation explains reference configuration under OSAC-1330 and the selection, inheritance, authorization, confidentiality, lifecycle, and error rules in FR-1–FR-12 and NFR-1–NFR-2. Covers FR-1–FR-5, FR-7–FR-12, NFR-1–NFR-2.
- [ ] **AC-13 — One complete secret:** Private-registry pulls use the selected secret as a whole, without merging or supplementing its credentials from other resource levels. Covers FR-4–FR-6, NFR-2.
- [ ] **AC-14 — One optional reference:** Initial configuration accepts zero or one explicit reference per DiskImage, catalog item, or ComputeInstance, never multiple references on one resource. An omitted reference preserves inheritance rather than disabling it. Covers FR-1–FR-5.
- [ ] **AC-15 — Independent instance guards:** Marking one instance for deletion does not release another non-deleting instance's guard on the same selected secret. Once all referring instances are marked for deletion, their guards end without waiting for cleanup. Covers FR-11.
- [ ] **AC-16 — No protected-reference reuse:** Tenants cannot explicitly attach an inherited protected secret to their own image, catalog item, or instance, even with its known reference and otherwise-valid resource permissions. Direct API submissions are rejected before saving; authorized inherited use still works. Covers FR-7, FR-8, NFR-1–NFR-2.

## 5. Dependencies

- **Provider/system secret management and isolation:** Protected provider-managed image inheritance depends on the system-tenant secret capability and its tenant-isolation boundary described by [OSAC-5425 — Allow cloud administrators to manage secrets in the system tenant](https://redhat.atlassian.net/browse/OSAC-5425). Inherited credential use and tenant access to the secret are distinct permissions.
- **Deployment compatibility:** OSAC does not currently support in-place upgrades. Existing-resource data and compatibility across independently deployed components require assessment during design; no migration mechanism or new upgrade capability is specified here. See the [OSAC feature dimensions](https://github.com/osac-project/osac/blob/2753cc412ff464a964de1e5a20dc3a06c925c234/docs/agent-context/osac-dimensions.md).

## 6. Risks

### 6.1 Protected credential identity leaks through resource presentation

A tenant could be prevented from retrieving a secret while still learning its identity from an image, catalog item, instance, selector, or error message.

- **Owner:** VMaaS feature owner, as identified by OSAC-5172 ownership.
- **Mitigation:** Apply NFR-1 to the tenant-facing reference experience and verify inherited use and nondisclosure through AC-5 and AC-11. Independently enforce FR-7’s non-reuse rule and AC-16 even when a protected identifier is known; hiding it in the UI or CLI is not an authorization control. Consuming UI/CLI/API views must not add an inherited-reference or inheritance indicator; normal authorized source-configuration visibility is preserved.

### 6.2 An unusable reference leaves an unsuccessful instance that still protects the secret

A reference can pass attachment checks while its credentials do not authorize the requested registry image. The instance's reference is immutable from creation, even when empty, and its creation-time selected secret remains protected from creation until OSAC marks the instance for deletion whether explicit or inherited, including before initial provisioning and despite source-reference changes, source deletion, or successful provisioning.

- **Owner:** VMaaS feature owner, as identified by OSAC-5172 ownership.
- **Mitigation:** Document and verify through UI/CLI/API the creation-time selection, reference immutability, and deletion-protection rules under AC-6, AC-7, AC-8, AC-12, and AC-15. First-setting an initially empty reference or replacing or clearing a supplied instance reference requires a replacement instance; authorized source-reference changes affect only later-created instances, not earlier-created instances awaiting initial provisioning. Once OSAC marks the original instance for deletion, its own guard ends without waiting for full cleanup; other non-deleting referrers still protect the secret and ordinary deletion authorization still applies. Use established failure reporting under NFR-2 while preserving NFR-1; existing secret-content update rules remain unchanged.
