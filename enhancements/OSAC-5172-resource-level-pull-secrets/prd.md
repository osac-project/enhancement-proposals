# Resource-Level Pull Secrets for VMaaS Private Registries

| Field | Value |
|---|---|
| Author(s) | Ygal Blum |
| Jira | [OSAC-5172 — Support referencing pull secrets for private registries at DiskImage, ComputeInstance, and CatalogItem levels](https://redhat.atlassian.net/browse/OSAC-5172) |
| Date | 2026-10-23 |
| Last revised | 2026-10-28 |
| Revision | 4 — settled API/UI, validation, and error behavior |
| Target milestone | 0.6, as recorded in the feature's Jira Fix Version |

## 1. Problem Statement

VMaaS users need to provision virtual machines from private image registries without making repositories public or manually supplying credentials outside OSAC. Typed pull-secret support already exists through completed [OSAC-5099](https://redhat.atlassian.net/browse/OSAC-5099); this feature adds the resource-level references needed to use it from a DiskImage, a ComputeInstanceCatalogItem, or a ComputeInstance. Cloud Provider Admins and Tenant Admins need reusable image and catalog credentials, while Tenant Users need an optional instance-specific reference that overrides the inherited pull secret. Provider-managed DiskImages must also work for tenants who cannot access the underlying secret, without exposing that secret's identity or contents.

## 2. Goals and Non-Goals

### 2.1 Goals

- Authorized users provision VMs from private registry images using credentials referenced through the UI or API, with no need to make the image repository public.
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
- Multi-registry failover or fallback logic.

## 3. Requirements

In this document, “catalog item” means ComputeInstanceCatalogItem. An **explicit reference** identifies the single secret supplied on a resource. The **selected pull secret** is the complete secret chosen from the most-specific resource with a supplied reference, under FR-4 and FR-5. An empty reference means no explicit selection at that level; it does not disable inheritance.

### 3.1 Functional Requirements

#### Referencing and inheritance

- **FR-1 — DiskImage reference:** Cloud Provider Admins and Tenant Admins must be able to attach one optional pull-secret reference to a DiskImage through the UI and API, within their authorized resource scope.
- **FR-2 — Catalog-item reference:** Cloud Provider Admins and Tenant Admins must be able to attach one optional pull-secret reference to a catalog item through the UI and API, within their authorized resource scope.
- **FR-3 — Instance reference:** Tenant Users must be able to supply one optional pull-secret reference when provisioning a ComputeInstance through the UI and API.
- **FR-4 — Whole-secret precedence:** OSAC must select one complete pull secret from the most-specific resource that supplies a reference: ComputeInstance first, then catalog item, then DiskImage. Credentials from different resource levels must not be combined. A supplied more-specific secret must not be supplemented with registry entries from less-specific secrets.
- **FR-5 — Empty means inherit:** Leaving a reference empty must allow selection to continue at the less-specific levels in FR-4; an empty reference must not disable inherited pull-secret use.

#### Provisioning and protected inherited use

- **FR-6 — Private-registry provisioning:** VMaaS must use the selected pull secret’s credentials to provision VMs from private image registries, including registries where anonymous access is disabled.
- **FR-7 — Protected provider-managed images and non-reusable references:** A Cloud Provider Admin must be able to create a DiskImage backed by a secret that tenants cannot access. Authorized tenants must be able to provision ComputeInstances from that DiskImage without permission to retrieve or select the protected secret. Inherited credential use must be implicit in the consuming UI and API: no inherited secret reference, identity, or inheritance indication may be returned or displayed. Normal authorized visibility of source configuration and the caller’s own explicit references remains unchanged. Inherited use must not authorize Tenant Users or Tenant Admins to reuse the protected reference explicitly on their own DiskImages, catalog items, or ComputeInstances, even if they know its ID or name. Enforce this boundary in the API as well as the UI; explicitly authorized secret selections remain allowed. NFR-1 applies to all tenant-facing representations.
- **FR-8 — Immediate explicit-reference validation:** On a permitted resource create or update, the UI/API must immediately reject an explicit secret reference that does not exist, is inaccessible or unauthorized, or has an incompatible type, before saving the resource, following existing secret-reference validation conventions. References must use the existing pull-secret type; no new secret type is introduced. An empty optional reference remains valid for inheritance. Authorized protected inheritance must not be rejected merely because the tenant cannot directly retrieve or select the inherited secret. These checks do not guarantee that the selected credentials will authorize a later image pull. [Jira: OSAC-5099]

#### Lifecycle and documentation

- **FR-9 — Reusable-reference changes:** Cloud Provider Admins and Tenant Admins must be able to change or clear a DiskImage or catalog-item reference within their authorized scope. The changed resolution applies only to provisioning started afterward; it must not alter provisioning already started or existing instances.
- **FR-10 — Instance-reference immutability:** Once a ComputeInstance pull-secret reference is set, it must not be changed or cleared, regardless of whether initial provisioning is pending, failed, or successful. This is a restriction on the instance’s reference, not on the referenced secret’s contents; this feature does not change existing secret-content update rules.
- **FR-11 — Referenced-secret deletion protection:** Deleting a secret must be blocked while a DiskImage or catalog item references it, or while a referencing ComputeInstance exists. Successful provisioning must not release the instance's protection. After instance deletion completes, that instance no longer blocks secret deletion; other references and ordinary deletion authorization still apply.
- **FR-12 — User and API documentation:** Documentation must explain how to attach references through the UI and API, how whole-secret precedence and empty-reference inheritance work, which references can be changed or cleared, and when secret deletion is blocked. API documentation must describe the permitted reference operations at all three resource levels, including immediate explicit-reference validation, the immutable-once-set instance restriction, implicit protected inheritance, the prohibition on directly reusing a protected reference, and established error conventions.

### 3.2 Non-Functional Requirements

- **NFR-1 — Protected-secret confidentiality:** Tenant-facing UI and API responses, selectors, and error messages must not disclose the ID, name, or value of an inherited provider/system secret that the tenant is not authorized to access. Using a provider-managed DiskImage must not grant tenants permission to list, retrieve, or discover that protected secret. This constraint concerns protected inherited secrets; it does not redefine visibility of a tenant's own authorized explicit selections. [Jira: OSAC-5425]
- **NFR-2 — Existing error conventions:** Reference validation, incompatible types, immutable-field changes, secrets still in use, and provisioning or registry-authentication failures must follow the existing OSAC conventions for analogous cases. Do not introduce a feature-specific error taxonomy, message catalog, or protocol codes. Reuse must preserve FR-7 and NFR-1, including protected-secret nondisclosure and non-reuse.

## 4. Acceptance Criteria

The following scenarios define user-verifiable acceptance outcomes; their checkboxes do not indicate that implementation has been tested. Exercise reference configuration and lifecycle restrictions through both the UI and API where the operation is exposed. Use a private registry with anonymous access disabled for provisioning scenarios. Confirm credential selection through authorized test evidence, not inherited-credential metadata returned to tenant interfaces. Refusal and provisioning-error scenarios follow NFR-2 while preserving confidentiality. Registry names below are conceptual test labels.

- [ ] **AC-1 — Image-level credentials:** With anonymous access disabled on a private image registry, a Cloud Provider Admin or Tenant Admin attaches an authorized pull secret to a DiskImage. A Tenant User provisions a VM from the image while leaving more-specific references empty; provisioning succeeds without making the repository public. Covers FR-1, FR-3, FR-5, FR-6.
- [ ] **AC-2 — Selection without an instance reference:** The instance supplies no pull-secret reference. The catalog-item and DiskImage pull-secret references may independently be present or absent. Verify that the catalog item’s secret is used when supplied; otherwise the DiskImage’s secret is used when supplied. If neither is supplied, neither level contributes a resource-level secret. Credentials at a less-specific level need not be invalid: verify which secret is used rather than inferring selection from provisioning success alone. Covers FR-2, FR-4–FR-6.
- [ ] **AC-3 — Instance selection:** The instance supplies a pull-secret reference. The catalog-item and DiskImage pull-secret references may each be present or absent. Across separate initial configurations for those combinations, verify that the instance’s secret is used. Provisioning succeeds when the selected secret authorizes the private image; lower-level references need not exist and their credentials need not be invalid. Verify the selected secret rather than inferring selection from success alone. Covers FR-3, FR-4, FR-6.
- [ ] **AC-5 — Implicit protected shared-image use:** A Cloud Provider Admin creates a DiskImage using a secret unavailable to the tenant. An authorized Tenant User provisions successfully without directly selecting or retrieving that secret. Consuming tenant UI/API views and responses contain neither the inherited secret reference or identity nor an inheritance indication. Secret discovery remains unavailable. Normal authorized views of the source configuration and of explicitly selected references remain unchanged. Verify the confidentiality boundary for Tenant Admin and Tenant User views within their existing permissions. Covers FR-7, NFR-1.
- [ ] **AC-6 — Future-only reusable changes:** Arrange the original and revised secret selections to produce distinguishable provisioning outcomes. Start provisioning, then change a DiskImage or catalog-item reference, and start another provisioning operation afterward. The first operation uses the original selected secret; the second uses the revised selected secret; existing instances remain unaffected. Verify both reference replacement and clearing at each reusable resource level. For clearing, the later operation follows the remaining applicable inheritance. Covers FR-5, FR-9.
- [ ] **AC-7 — Immutable instance reference:** After an instance reference is set, attempts to replace or clear it are rejected while the original reference remains unchanged. This is verified for pending, failed, and successfully provisioned instances. Covers FR-10, NFR-2.
- [ ] **AC-8 — Instance-only deletion protection:** A secret is referenced only by a retained ComputeInstance. Deletion is rejected whether that instance is pending, failed, or successfully provisioned. Once instance deletion completes, that instance no longer prevents secret deletion, subject to ordinary authorization. Covers FR-11, NFR-2.
- [ ] **AC-9 — Reusable references still protect the secret:** A secret is referenced by an instance and by a DiskImage. Completing instance deletion does not permit secret deletion while the DiskImage reference remains. An authorized change or clearing of that image reference removes only that dependency; any other reference still protects the secret. Repeat with a catalog item instead of the DiskImage. Covers FR-9, FR-11.
- [ ] **AC-10 — Immediate invalid-reference rejection:** At each resource level, use an otherwise permitted operation to submit a nonexistent, unauthorized/inaccessible, or non-pull-secret-type explicit reference. The resource save is rejected immediately and the invalid reference is not persisted. The UI may prevent the selection or surface the existing validation behavior; direct API submissions must also be rejected. An empty optional reference still inherits, and legitimate provider-image inheritance must not require the tenant to retrieve the protected secret. Errors follow NFR-2 without exposing protected information. Covers FR-5, FR-7, FR-8, NFR-1–NFR-2.
- [ ] **AC-11 — Authorization boundary:** A tenant unable to discover a provider/system secret cannot discover it through the new image, catalog, or instance reference experience, including reference-validation and provisioning failures. Authorized inherited use through the provider-managed DiskImage still succeeds without returning inherited credential metadata. Errors use existing analogous conventions without disclosing protected identities or values. Covers FR-7, NFR-1–NFR-2.
- [ ] **AC-12 — Documented permitted operations:** A reviewer with appropriate configuration access can use the user/API documentation to configure references, predict whole-secret selection from configuration they are authorized to inspect, and distinguish inherited use from direct secret access. The documentation explains implicit inherited use, immediate explicit-reference validation, immutable instance references, and reference-based deletion protection using established error conventions. It does not promise changing or clearing an already-set instance reference or exposing inherited credentials in consuming interfaces. Covers FR-1–FR-5, FR-7–FR-12, NFR-2.
- [ ] **AC-13 — Whole-secret priority:** In separate initial configurations, supply references at all three levels, at catalog-item and DiskImage levels only, and at DiskImage level only. Verify that the instance’s, catalog item’s, and DiskImage’s secret is selected respectively using authorized test evidence, without exposing protected credentials or inherited-selection metadata to tenants. Provisioning failures use existing conventions under NFR-2. Covers FR-4–FR-6, NFR-2.
- [ ] **AC-14 — Single optional reference at each level:** During initial resource configuration through the UI and API, an authorized user may omit the explicit pull-secret reference or supply one reference for each DiskImage, catalog item, or ComputeInstance; neither interface accepts multiple references on one resource. An omitted reference preserves inheritance rather than requiring another explicit selection or disabling credentials. Covers FR-1–FR-5.
- [ ] **AC-15 — Other instances still protect the secret:** Two retained ComputeInstances reference the same secret, with no image or catalog-item references. Completing deletion of one instance does not permit secret deletion while the second still exists. Only after deletion of the second completes does this pair of instances cease to block deletion, subject to any other references and ordinary authorization. Covers FR-11.
- [ ] **AC-16 — Protected references cannot be reused:** An authorized tenant actor can provision from the provider-managed DiskImage through inherited use. For each of DiskImage, catalog item, and ComputeInstance, use a tenant actor otherwise authorized to configure that resource to attempt supplying the protected secret’s known reference explicitly through the available reference-setting paths. None of those explicit attachments is accepted, including direct API submissions that bypass UI restrictions; invalid explicit references are rejected before saving. The protected reference and values remain undisclosed, while the authorized inherited-use workflow still succeeds. Refusals follow existing error conventions under NFR-2. Covers FR-7, FR-8, NFR-1–NFR-2.

## 5. Dependencies

- **Provider/system secret management and isolation:** Protected provider-managed image inheritance depends on the system-tenant secret capability and its tenant-isolation boundary described by [OSAC-5425 — Allow cloud administrators to manage secrets in the system tenant](https://redhat.atlassian.net/browse/OSAC-5425). Inherited credential use and tenant access to the secret are distinct permissions.
- **Deployment compatibility:** OSAC does not currently support in-place upgrades. Existing-resource data and compatibility across independently deployed components require assessment during design; no migration mechanism or new upgrade capability is specified here. See the [OSAC feature dimensions](https://github.com/osac-project/osac/blob/2753cc412ff464a964de1e5a20dc3a06c925c234/docs/agent-context/osac-dimensions.md).

## 6. Risks

### 6.1 Protected credential identity leaks through resource presentation

A tenant could be prevented from retrieving a secret while still learning its identity from an image, catalog item, instance, selector, or error message.

- **Owner:** VMaaS feature owner, as identified by OSAC-5172 ownership.
- **Mitigation:** Apply NFR-1 to the tenant-facing reference experience and verify inherited use and nondisclosure through AC-5 and AC-11. Independently enforce FR-7’s non-reuse rule and AC-16 even when a protected identifier is known; hiding it in the UI is not an authorization control. Consuming UI/API views must not add an inherited-reference or inheritance indicator; normal authorized source-configuration visibility is preserved.

### 6.2 An unusable reference leaves an unsuccessful instance that still protects the secret

A reference can pass attachment checks while its credentials do not authorize the requested registry image. The instance's reference remains immutable, and its existence continues to block deletion of the secret even if provisioning fails.

- **Owner:** VMaaS feature owner, as identified by OSAC-5172 ownership.
- **Mitigation:** Document the immutable-reference and deletion rules. A different instance-specific reference requires a replacement instance rather than editing the retained instance's reference; deleting the original instance removes only its own deletion dependency. Use established failure reporting under NFR-2 while preserving NFR-1.
