---
title: osac-controller-migration
authors:
  - CloudKit Team
creation-date: 2026-01-11
last-updated: 2026-01-12
tracking-link:
  - None
see-also:
  - None
replaces:
  - None
superseded-by:
  - None
---

# OSAC Controller Migration

## Summary

This proposal outlines the migration of compute instance provisioning logic from Ansible Automation Platform (AAP) to a native Kubernetes controller within cloudkit-operator. Currently, when a user orders a compute instance, the fulfillment-service creates a ComputeInstance CR, which triggers cloudkit-operator to call AAP via webhook. AAP then creates the underlying KubeVirt VirtualMachine CR and associated resources. This migration will move the KubeVirt VirtualMachine CR creation logic directly into the controller, eliminating external orchestration dependencies and simplifying the provisioning architecture.

**Scope:** This migration moves **Kubernetes-native resource creation** (KubeVirt VirtualMachines, DataVolumes, Secrets, Services) from Ansible to the controller. **Provider-specific infrastructure integration** (networking, load balancers, floating IPs, DNS, TLS) remains in Ansible/AAP as the customization layer where providers integrate with their environment-specific infrastructure. The ComputeInstance CR creation (handled by fulfillment-service) remains unchanged.

## Motivation

The current AAP-based architecture introduces unnecessary complexity, latency, and operational overhead for what is fundamentally a simple Kubernetes-native operation: creating child resources from parent CRs.

### Current Architecture Pain Points

The current architecture spans multiple systems to provision a single compute instance:

```
User → fulfillment-api → fulfillment-service → ComputeInstance CR
     → Webhook → AAP EDA → Rulebook Match → Job Template
     → Ansible Playbook → KubeVirt VirtualMachine CR
     → cloudkit-operator watches → Status updates
```

**Key Issues:**
1. **Multiple failure points:** Webhook delivery, AAP job queue, Ansible execution, K8s API
2. **Debugging complexity:** Logs distributed across fulfillment, AAP, EDA, and controller
3. **Latency overhead:** ~30 seconds from order to compute instance provisioning start
4. **Infrastructure overhead:** AAP Controller, EDA, Execution Environments requiring maintenance
5. **Deployment complexity:** AAP configuration-as-code, collections, job templates

### User Stories

* As an end user, I want my compute instance to be provisioned within seconds of submitting my order, so that I can start using my resources immediately without long wait times.

* As a developer, I want to use native Kubernetes controller patterns (reconciliation loops, status conditions, owner references), so that I can leverage well-established best practices and tooling when implementing compute instance features.

* As an SRE debugging failed compute instance orders, I want to trace the entire provisioning flow in a single controller codebase, so that I can quickly identify root causes without navigating through AAP jobs, EDA rulebooks, and Ansible playbook logs across multiple systems.

* As an SRE, I want to reduce operational overhead by eliminating AAP infrastructure dependencies, so that I have fewer systems to deploy, maintain, and troubleshoot.

* As an SRE, I want to reduce the number of failure points in the provisioning pipeline, so that I have fewer components to monitor and fewer potential causes of outages.

### Goals

- Move KubeVirt VirtualMachine CR creation from Ansible playbooks to cloudkit-controller
- Create associated resources (DataVolumes, Secrets, Services) directly in the controller
- Maintain backwards compatibility during migration using dual-mode operation
- Reduce provisioning latency from ~30s to <5s
- Simplify the architecture by eliminating AAP dependency
- Enable future application of this pattern to Cluster resource provisioning

### Non-Goals

- Changes to ComputeInstance CR creation (already handled by fulfillment-service)
- Provider-specific infrastructure integration (networking, storage, DNS, TLS) - these remain in Ansible/AAP as the customization layer where providers integrate with their environment-specific infrastructure (network fabric, load balancers, floating IPs, VPN, DNS records, TLS certificates, etc.)
- Complete AAP infrastructure removal - providers with custom infrastructure integrations will continue to use Ansible hooks
- Changes to the fulfillment-service API or database schema

## Proposal

### Architectural Boundary: Controller vs Ansible

This enhancement migrates **Kubernetes-native resource orchestration** from Ansible to the controller, while preserving **provider infrastructure integration** in Ansible.

**cloudkit-controller responsibility:**
- Kubernetes-native resource creation and lifecycle management
- Creating KubeVirt VirtualMachines, DataVolumes, Secrets, Services
- Reconciliation loops, status updates, owner references
- Standard Kubernetes patterns and APIs

**Ansible/AAP responsibility (provider integration layer):**
- Environment-specific infrastructure integration that varies by provider:
  - **Networking**: Network fabric integration (UDN/CUDN provisioning), VPN setup, private network plumbing
  - **Load balancing**: MetalLB provisioning, hardware load balancers, floating IP assignment
  - **DNS**: DNS record creation and management
  - **TLS**: Certificate provisioning from provider's certificate authority
  - **Storage**: Integration with provider-specific storage systems
- Enables each provider to customize CloudKit to their infrastructure (network gear, topology, access requirements, etc.)
- Uses Ansible's broad vendor support for network equipment configuration

**Design rationale:** Ansible is the de facto standard for infrastructure automation and covers every major vendor of network gear. This architectural separation allows CloudKit to provide an end-to-end working reference implementation while enabling providers to integrate with their unique infrastructure through well-defined hooks.

**Example:** The `massopencloud.esi` collection demonstrates provider-specific integration - MOC uses OpenStack ESI for floating IPs and port forwarding. Other providers may use different approaches (MetalLB, hardware load balancers, direct network fabric integration, etc.).

### Workflow Description

#### Current Workflow

1. User submits compute instance order via fulfillment-api
2. fulfillment-service creates cloudkit.openshift.io/v1alpha1/ComputeInstance CR
3. cloudkit-operator detects ComputeInstance CR where spec.desiredConfigVersion ≠ status.reconciledConfigVersion
4. cloudkit-operator triggers webhook to AAP EDA
5. EDA rulebook matches webhook and launches Job Template
6. AAP schedules Ansible playbook in Execution Environment
7. Playbook creates KubeVirt VirtualMachine CR and associated resources (Secrets, DataVolumes, Services)
8. Playbook sets cloudkit.openshift.io/reconciled-config-version annotation on ComputeInstance
9. cloudkit-operator watches kubevirt.io/v1/VirtualMachine for actual VM status
10. cloudkit-operator updates ComputeInstance status conditions
11. fulfillment-service polls ComputeInstance status and updates order in database

#### Proposed Workflow

1. User submits compute instance order via fulfillment-api (UNCHANGED)
2. fulfillment-service creates cloudkit.openshift.io/v1alpha1/ComputeInstance CR (UNCHANGED)
3. cloudkit-operator detects ComputeInstance CR where spec.desiredConfigVersion ≠ status.reconciledConfigVersion
4. cloudkit-operator checks annotation "cloudkit.openshift.io/managed-by"
5. **IF managed-by = "controller" (NEW PATH):**
   - Parse TemplateParameters JSON from ComputeInstance.spec
   - Call resource builders to create Kubernetes objects
   - Create KubeVirt VirtualMachine CR directly
   - Create associated resources (Secrets, DataVolumes, Services)
   - Set cloudkit.openshift.io/reconciled-config-version annotation
   - Update ComputeInstance status
6. **ELSE managed-by = "aap" (FALLBACK PATH):**
   - Trigger CreateVMWebhook() (existing behavior during migration)
7. cloudkit-operator watches kubevirt.io/v1/VirtualMachine for actual VM status (UNCHANGED)
8. cloudkit-operator updates ComputeInstance status conditions (UNCHANGED)
9. fulfillment-service polls ComputeInstance status and updates order in database (UNCHANGED)

### API Extensions

No new APIs are introduced. The proposal uses existing ComputeInstance CR with a new annotation to control routing:

```yaml
apiVersion: cloudkit.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: test-vm-001
  annotations:
    cloudkit.openshift.io/managed-by: "controller"  # or "aap"
spec:
  desiredConfigVersion: 1
  tenantNamespace: tenant-ns
  templateParameters: |
    {
      "cpu_cores": 4,
      "memory": "8Gi",
      "disk_size": "50Gi",
      "image_source": "docker://registry.example.com/images/rhel9:latest",
      "cloud_init_config": "I2Nsb3VkLWNvbmZpZw==",
      "ssh_public_key": "c3NoLXJzYSBBQUFB...",
      "exposed_ports": "22/tcp,80/tcp,443/tcp"
    }
status:
  reconciledConfigVersion: 0
  conditions: []
```

The controller will create the following resources in the tenant namespace:

1. **Secret:** `{vm_name}-cloud-init` (cloud-init user data)
2. **Secret:** `{vm_name}-ssh-public-key` (optional, if ssh_public_key provided)
3. **DataVolume:** `{vm_name}-root-disk` (CDI-based disk from container image)
4. **VirtualMachine:** `{vm_name}` (kubevirt.io/v1)
5. **Service:** `{vm_name}-load-balancer` (LoadBalancer type for exposed ports)

All created resources will have OwnerReferences pointing to the ComputeInstance CR for automatic cleanup.

#### Operational Aspects of API Extensions

**Behavior Modification:**
- Modifies reconciliation behavior of existing `cloudkit.openshift.io/v1alpha1/ComputeInstance` CR
- Adds new annotation `cloudkit.openshift.io/managed-by` to control provisioning path
- No changes to CR schema (spec/status fields)
- Backward compatible: ComputeInstances without annotation continue using AAP (existing behavior)

**Operational Impact:**

*During migration (dual-mode operation):*
- **Impact on cluster:** None - both AAP and controller paths create identical Kubernetes resources
- **Impact on existing workloads:** Existing ComputeInstances continue provisioning via AAP unchanged
- **Impact on new workloads:** New ComputeInstances can choose provisioning path via annotation
- **Rollback capability:** Change annotation value or redeploy previous controller version

*After full migration (AAP removed):*
- **Impact on cluster:** AAP infrastructure no longer required for Kubernetes resource provisioning (still needed for provider-specific infrastructure integration if applicable)
- **Impact on existing workloads:** Continue running normally (no reconciliation triggered for running VMs)
- **Impact on new workloads:** All new ComputeInstances provisioned via controller

**Failure modes:**
- If controller crashes during provisioning: Reconciliation resumes on restart (idempotent operations, partial resources safe via OwnerReferences)
- If AAP unavailable: ComputeInstances with `managed-by: aap` will fail to provision until AAP restored
- If annotation invalid/missing: Defaults to AAP (backward compatible)

**Resource cleanup:**
- Deletion of ComputeInstance CR triggers deletion of all child resources via OwnerReferences
- No manual cleanup required

### Implementation Details/Notes/Constraints

#### Resource Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: Compute Instance Order Submission (UNCHANGED)              │
├─────────────────────────────────────────────────────────────────────┤
│ User → fulfillment API → fulfillment-service                        │
│   ↓                                                                  │
│ Creates: cloudkit.openshift.io/v1alpha1/ComputeInstance CR          │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2: Controller Reconciliation (NEW LOGIC)                      │
├─────────────────────────────────────────────────────────────────────┤
│ cloudkit-operator ComputeInstanceReconciler watches CR              │
│   ↓                                                                  │
│ Detects: spec.desiredConfigVersion ≠ status.reconciledConfigVersion│
│   ↓                                                                  │
│ IF annotation "cloudkit.openshift.io/managed-by" = "controller":    │
│   ↓                                                                  │
│   Parse TemplateParameters JSON → Go struct                         │
│   ↓                                                                  │
│   Call resource builders:                                           │
│     - BuildCloudInitSecret()                                        │
│     - BuildSSHKeySecret()                                           │
│     - BuildDataVolume()                                             │
│     - BuildVirtualMachine()                                         │
│     - BuildLoadBalancerService()                                    │
│   ↓                                                                  │
│   Create KubeVirt VirtualMachine and resources in target namespace  │
│   ↓                                                                  │
│   Set annotation: cloudkit.openshift.io/reconciled-config-version  │
│   ↓                                                                  │
│   Update ComputeInstance status conditions                          │
│                                                                      │
│ ELSE (managed-by = "aap"):                                          │
│   Trigger CreateVMWebhook() (FALLBACK during migration)            │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 3: Status Tracking (UNCHANGED)                                │
├─────────────────────────────────────────────────────────────────────┤
│ cloudkit-operator watches kubevirt.io/v1/VirtualMachine             │
│   ↓                                                                  │
│ Updates: ComputeInstance status.conditions[InstanceAvailable]       │
│   ↓                                                                  │
│ fulfillment-service polls ComputeInstance status → Updates order    │
└─────────────────────────────────────────────────────────────────────┘
```

#### Controller Implementation

**Current Code (cloudkit-operator/internal/controller/computeinstance_controller.go):**
```go
func (r *ComputeInstanceReconciler) handleUpdate(ctx context.Context, ci *cloudkitv1alpha1.ComputeInstance) error {
    if ci.Spec.DesiredConfigVersion != ci.Status.ReconciledConfigVersion {
        // Trigger webhook to AAP
        return r.CreateVMWebhook(ctx, ci)
    }
    return nil
}
```

**Proposed Code:**
```go
func (r *ComputeInstanceReconciler) handleUpdate(ctx context.Context, ci *cloudkitv1alpha1.ComputeInstance) error {
    if ci.Spec.DesiredConfigVersion != ci.Status.ReconciledConfigVersion {
        // Check management mode
        managedBy := ci.Annotations["cloudkit.openshift.io/managed-by"]

        if managedBy == "controller" {
            // NEW: Create KubeVirt VirtualMachine and resources directly
            return r.reconcileVMResources(ctx, ci)
        }

        // FALLBACK: Use AAP webhook (during migration)
        return r.CreateVMWebhook(ctx, ci)
    }
    return nil
}

func (r *ComputeInstanceReconciler) reconcileVMResources(ctx context.Context, ci *cloudkitv1alpha1.ComputeInstance) error {
    // 1. Parse TemplateParameters JSON
    params, err := parseTemplateParameters(ci.Spec.TemplateParameters)
    if err != nil {
        return err
    }

    // 2. Build resources
    resources := []client.Object{
        resources.BuildCloudInitSecret(ci, params),
        resources.BuildSSHKeySecret(ci, params),
        resources.BuildDataVolume(ci, params),
        resources.BuildVirtualMachine(ci, params),
        resources.BuildLoadBalancerService(ci, params),
    }

    // 3. Create/update resources
    for _, resource := range resources {
        if err := r.createOrUpdate(ctx, resource); err != nil {
            return err
        }
    }

    // 4. Update status
    ci.Status.ReconciledConfigVersion = ci.Spec.DesiredConfigVersion
    return r.Status().Update(ctx, ci)
}
```

#### New Package Structure

```
cloudkit-operator/pkg/resources/
├── computeinstance/
│   ├── secret.go              # BuildCloudInitSecret, BuildSSHKeySecret
│   ├── datavolume.go          # BuildDataVolume
│   ├── virtualmachine.go      # BuildVirtualMachine (kubevirt.io/v1)
│   ├── service.go             # BuildLoadBalancerService
│   └── types.go               # TemplateParameters struct
└── common/
    └── utils.go               # Shared utilities
```

#### Template Parameters

From `TemplateParameters` JSON field in ComputeInstance.spec:

| Parameter          | Type   | Required | Example                    | Description                      |
|--------------------|--------|----------|----------------------------|----------------------------------|
| `cpu_cores`        | int    | Yes      | `4`                        | Number of CPU cores              |
| `memory`           | string | Yes      | `"8Gi"`                    | Memory allocation                |
| `disk_size`        | string | Yes      | `"50Gi"`                   | Root disk size                   |
| `image_source`     | string | Yes      | `"docker://registry/image"`| Container image for VM disk      |
| `cloud_init_config`| string | Yes      | `"#cloud-config\n..."`     | Cloud-init user data (base64)    |
| `ssh_public_key`   | string | No       | `"ssh-rsa AAAA..."`        | SSH public key (base64)          |
| `exposed_ports`    | string | Yes      | `"22/tcp,80/tcp"`          | Comma-separated port list        |

**Parser Implementation:**
```go
// pkg/resources/computeinstance/types.go
type TemplateParameters struct {
    CPUCores       int    `json:"cpu_cores"`
    Memory         string `json:"memory"`
    DiskSize       string `json:"disk_size"`
    ImageSource    string `json:"image_source"`
    CloudInitB64   string `json:"cloud_init_config"`
    SSHPublicKeyB64 string `json:"ssh_public_key,omitempty"`
    ExposedPorts   string `json:"exposed_ports"`
}

func parseTemplateParameters(jsonStr string) (*TemplateParameters, error) {
    var params TemplateParameters
    if err := json.Unmarshal([]byte(jsonStr), &params); err != nil {
        return nil, fmt.Errorf("failed to parse template parameters: %w", err)
    }
    return &params, nil
}
```

#### Resource Builder Examples

**1. KubeVirt VirtualMachine Builder**
```go
// pkg/resources/computeinstance/virtualmachine.go
func BuildVirtualMachine(ci *cloudkitv1alpha1.ComputeInstance, params *TemplateParameters) *kubevirtv1.VirtualMachine {
    running := true

    kvVM := &kubevirtv1.VirtualMachine{
        ObjectMeta: metav1.ObjectMeta{
            Name:      ci.Name,
            Namespace: ci.Spec.TenantNamespace,
            OwnerReferences: []metav1.OwnerReference{
                *metav1.NewControllerRef(ci, cloudkitv1alpha1.GroupVersion.WithKind("ComputeInstance")),
            },
        },
        Spec: kubevirtv1.VirtualMachineSpec{
            Running: &running,
            Template: &kubevirtv1.VirtualMachineInstanceTemplateSpec{
                Spec: kubevirtv1.VirtualMachineInstanceSpec{
                    Domain: kubevirtv1.DomainSpec{
                        CPU: &kubevirtv1.CPU{
                            Cores: uint32(params.CPUCores),
                        },
                        Memory: &kubevirtv1.Memory{
                            Guest: resource.MustParse(params.Memory),
                        },
                        Devices: kubevirtv1.Devices{
                            Disks: []kubevirtv1.Disk{
                                {
                                    Name: "root-disk",
                                    DiskDevice: kubevirtv1.DiskDevice{
                                        Disk: &kubevirtv1.DiskTarget{},
                                    },
                                },
                                {
                                    Name: "cloudinit",
                                    DiskDevice: kubevirtv1.DiskDevice{
                                        Disk: &kubevirtv1.DiskTarget{},
                                    },
                                },
                            },
                        },
                    },
                    Volumes: []kubevirtv1.Volume{
                        {
                            Name: "root-disk",
                            VolumeSource: kubevirtv1.VolumeSource{
                                DataVolume: &kubevirtv1.DataVolumeSource{
                                    Name: fmt.Sprintf("%s-root-disk", ci.Name),
                                },
                            },
                        },
                        {
                            Name: "cloudinit",
                            VolumeSource: kubevirtv1.VolumeSource{
                                CloudInitNoCloud: &kubevirtv1.CloudInitNoCloudSource{
                                    UserDataSecretRef: &corev1.LocalObjectReference{
                                        Name: fmt.Sprintf("%s-cloud-init", ci.Name),
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    // Add SSH access credentials if provided
    if params.SSHPublicKeyB64 != "" {
        kvVM.Spec.Template.Spec.AccessCredentials = []kubevirtv1.AccessCredential{
            {
                SSHPublicKey: &kubevirtv1.SSHPublicKeyAccessCredential{
                    Source: kubevirtv1.SSHPublicKeyAccessCredentialSource{
                        Secret: &kubevirtv1.AccessCredentialSecretSource{
                            SecretName: fmt.Sprintf("%s-ssh-public-key", ci.Name),
                        },
                    },
                },
            },
        }
    }

    return kvVM
}
```

**2. DataVolume Builder**
```go
// pkg/resources/computeinstance/datavolume.go
func BuildDataVolume(ci *cloudkitv1alpha1.ComputeInstance, params *TemplateParameters) *cdiv1beta1.DataVolume {
    storageClass := getStorageClass() // From env or default

    return &cdiv1beta1.DataVolume{
        ObjectMeta: metav1.ObjectMeta{
            Name:      fmt.Sprintf("%s-root-disk", ci.Name),
            Namespace: ci.Spec.TenantNamespace,
            OwnerReferences: []metav1.OwnerReference{
                *metav1.NewControllerRef(ci, cloudkitv1alpha1.GroupVersion.WithKind("ComputeInstance")),
            },
        },
        Spec: cdiv1beta1.DataVolumeSpec{
            Source: &cdiv1beta1.DataVolumeSource{
                Registry: &cdiv1beta1.DataVolumeSourceRegistry{
                    URL: &params.ImageSource,
                },
            },
            Storage: &cdiv1beta1.StorageSpec{
                StorageClassName: &storageClass,
                Resources: corev1.ResourceRequirements{
                    Requests: corev1.ResourceList{
                        corev1.ResourceStorage: resource.MustParse(params.DiskSize),
                    },
                },
            },
        },
    }
}
```

**3. LoadBalancer Service Builder**
```go
// pkg/resources/computeinstance/service.go
func BuildLoadBalancerService(ci *cloudkitv1alpha1.ComputeInstance, params *TemplateParameters) *corev1.Service {
    ports := parseExposedPorts(params.ExposedPorts)

    return &corev1.Service{
        ObjectMeta: metav1.ObjectMeta{
            Name:      fmt.Sprintf("%s-load-balancer", ci.Name),
            Namespace: ci.Spec.TenantNamespace,
            OwnerReferences: []metav1.OwnerReference{
                *metav1.NewControllerRef(ci, cloudkitv1alpha1.GroupVersion.WithKind("ComputeInstance")),
            },
        },
        Spec: corev1.ServiceSpec{
            Type: corev1.ServiceTypeLoadBalancer,
            Selector: map[string]string{
                "kubevirt.io/vm": ci.Name,
            },
            Ports: ports,
        },
    }
}

func parseExposedPorts(portsStr string) []corev1.ServicePort {
    // Parse "22/tcp,80/tcp,443/tcp" → []ServicePort
    var servicePorts []corev1.ServicePort
    for _, portSpec := range strings.Split(portsStr, ",") {
        parts := strings.Split(strings.TrimSpace(portSpec), "/")
        if len(parts) != 2 {
            continue
        }
        port, _ := strconv.Atoi(parts[0])
        protocol := strings.ToUpper(parts[1])

        servicePorts = append(servicePorts, corev1.ServicePort{
            Name:       fmt.Sprintf("port-%d", port),
            Port:       int32(port),
            TargetPort: intstr.FromInt(port),
            Protocol:   corev1.Protocol(protocol),
        })
    }
    return servicePorts
}
```

#### Dual-Mode Support (Migration Strategy)

To enable zero-downtime migration, the controller will respect an annotation:

```yaml
apiVersion: cloudkit.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: test-vm-001
  annotations:
    cloudkit.openshift.io/managed-by: "controller"  # or "aap"
```

**Migration Flow:**
1. Deploy updated cloudkit-operator with new resource builder logic
2. Default annotation to `"aap"` → no behavior change
3. Gradually update compute instances with `managed-by: "controller"` annotation
4. Monitor success rates, rollback if needed by reverting annotation
5. Once stable, update fulfillment-service to set `managed-by: "controller"` on new compute instance orders
6. After 100% adoption, remove AAP webhook code path

### Risks and Mitigations

#### Risk 1: Template Porting Bugs
**Description:** Go resource builders create resources with subtle differences from Ansible, causing VM boot failures

**Impact:** High - Compute instances fail to provision, user orders fail
**Probability:** Medium - Complex YAML generation logic

**Mitigation:**
- Automated diff testing: Compare controller-generated resources with AAP-generated resources
- Parallel testing: Run AAP and controller side-by-side, compare outputs
- Incremental rollout: Start with 10% traffic, increase only if metrics pass
- Fast rollback: Annotation-based switching allows instant revert to AAP

#### Risk 2: Performance Regression
**Description:** Controller reconciliation causes performance issues (high CPU, slow provisioning)

**Impact:** Medium - Slower provisioning, increased resource usage
**Probability:** Low - Kubernetes controllers are well-optimized

**Mitigation:**
- Load testing in staging with 100+ concurrent compute instance creations
- Prometheus metrics to track reconciliation duration
- Optimize reconciliation loop (efficient caching, predicate filters)
- Add rate limiting if necessary

#### Risk 3: Migration Bugs Affecting Production
**Description:** Controller bugs cause production order failures during rollout

**Impact:** High - Customer impact, revenue loss
**Probability:** Medium - New code path

**Mitigation:**
- Extensive testing (unit, integration, E2E)
- Gradual rollout with 24-hour monitoring windows
- Dual-mode support for instant rollback
- Feature flags to disable controller path
- On-call engineer monitoring during rollout
- Rollback runbook prepared in advance

#### Risk 4: Storage Class Detection Fails
**Description:** Ansible auto-detects default storage class; Go logic may fail in edge cases

**Impact:** Medium - DataVolume creation fails
**Probability:** Low - Well-documented K8s API

**Mitigation:**
- Unit tests for storage class detection logic
- Support explicit override via env var `CLOUDKIT_VM_OPERATIONS_STORAGE_CLASS`
- Graceful error handling with clear error messages
- Test in multiple cluster environments (dev, staging, prod)

### Drawbacks

- Introduces code complexity in cloudkit-operator (more Go code to maintain vs. Ansible playbooks)
- Requires careful migration strategy to avoid service disruption
- Team needs to maintain two code paths (controller and AAP) during migration period
- Providers with custom infrastructure integrations will continue to depend on Ansible/AAP (this is by design, but increases operational complexity for those providers)

## Alternatives (Not Implemented)

### Alternative 1: Keep AAP, Optimize Pipeline
Instead of removing AAP, optimize the webhook → EDA → AAP pipeline to reduce latency.

**Pros:**
- Less disruptive, no code rewrite needed
- Maintains separation of concerns (controller watches, AAP provisions)

**Cons:**
- Still maintains operational overhead of AAP infrastructure
- Latency improvements limited (still external job queue)
- Doesn't address core architectural complexity

This approach doesn't address the root cause of complexity - the fundamental issue is using an external job queue for simple Kubernetes resource creation, not the performance of that queue.

### Alternative 2: New Dedicated OSAC Controller
Create a separate osac-controller repository instead of extending cloudkit-operator.

**Pros:**
- Clean separation, independent versioning
- Can optimize for specific compute instance provisioning use case

**Cons:**
- Another deployment to manage
- Duplicates reconciliation logic already in cloudkit-operator
- More complex dependency management

Extending cloudkit-operator is simpler because it reuses the existing ComputeInstance reconciliation infrastructure and avoids creating another deployment to manage.

### Alternative 3: Hybrid Approach (AAP for Complex Resources)
Keep simple resources in controller, delegate complex resources (DataVolumes, floating IPs) to AAP.

**Pros:**
- Reduces initial migration scope
- Leverages AAP for complex orchestration

**Cons:**
- Maintains dual provisioning model
- Still requires AAP infrastructure
- Debugging still spans multiple systems

This approach doesn't achieve the primary goal of eliminating AAP dependency for Kubernetes resource provisioning and would maintain the split provisioning model that causes debugging complexity.

## Open Questions

### 1. Provider Integration Routing Logic
**Question:** How does the system determine which ComputeInstances need provider-specific infrastructure integrations (and thus should use Ansible/AAP) vs which can be handled entirely by the controller?

**Context:**
- Some providers require custom networking (floating IPs, VPN, network fabric integration)
- The `ocp_virt_vm` template currently always invokes provider integration hooks (e.g., massopencloud.esi)
- No parameter in `templateParameters` currently indicates whether provider integration is needed

**Options:**

**A) Template-based:** Cloud Service Provider (CSP) decides what templates to offer; each template declares its integrations.
- **Pros:** Clear separation, templates explicitly declare dependencies, CSP has full control
- **Cons:** Requires creating multiple template variants (e.g., `ocp_virt_vm_basic`, `ocp_virt_vm_full`)

**B) Parameter-based:** Add `requires_provider_integration: bool` to template parameters
- **Pros:** Single template, runtime decision based on user input
- **Cons:** Adds complexity to template parameters, user must understand infrastructure needs

**C) Provider/environment-based:** Configuration in fulfillment-service per Cloud Service Provider (CSP)
- **Pros:** No template changes needed, centralized configuration
- **Cons:** Hardcoded CSP assumptions, doesn't support mixed deployments within same CSP

**D) Metadata-based:** Template definitions include capabilities/requirements metadata
- **Pros:** Declarative, allows dynamic discovery of template requirements
- **Cons:** Requires new metadata schema, additional complexity in fulfillment-service

**E) Always invoke Ansible:** All templates go through Ansible
- **Pros:** Consistent flow, no routing logic needed, some Ansible customization expected anyway
- **Cons:** Doesn't achieve latency reduction goal for controller-only deployments, maintains AAP dependency

**Team Feedback:**
- **Alona Kaplan:** Prefers Option E (always invoke Ansible) - expects some Ansible plumbing for any Cloud Service Provider
- **Michael Hrivnak:** Supports Option A (template-based) - CSP decides templates and their integrations
- **Consensus:** Floating IP logic stays in Ansible; only KubeVirt VM CR creation moves to controller

**Action Required:** Finalize routing approach before implementation.

### 2. Storage Class Selection
**Question:** How should we handle storage class auto-detection?

**Proposed Go Logic:**
```go
func getStorageClass(ctx context.Context, client client.Client) (string, error) {
    // 1. Check env var
    if sc := os.Getenv("CLOUDKIT_VM_OPERATIONS_STORAGE_CLASS"); sc != "" {
        return sc, nil
    }

    // 2. Find default storage class
    var scList storagev1.StorageClassList
    if err := client.List(ctx, &scList); err != nil {
        return "", err
    }

    for _, sc := range scList.Items {
        if sc.Annotations["storageclass.kubernetes.io/is-default-class"] == "true" {
            return sc.Name, nil
        }
    }

    return "", fmt.Errorf("no default storage class found")
}
```

This matches the current Ansible logic and provides both explicit configuration (via env var) and automatic detection (via default storage class).

### 3. Error Handling Strategy
**Question:** How should we handle transient errors (API server unavailable, etc.)?

**Proposal:**
- Use controller-runtime's built-in retry with exponential backoff
- Max retries: 10 (controller-runtime default)
- Backoff: 5ms → 10ms → 20ms → ... → 1000ms (capped)
- After max retries, update ComputeInstance status with error condition
- Manual intervention required (or webhook fallback to AAP)

### 4. Floating IP as Separate API
**Question:** Should floating IP allocation/association be a separate API operation (day-2) rather than compound with VM creation?

**Context:**
- **Avishay & Eran:** Suggest following AWS model - separate APIs for "Allocate floating IP" and "Attach floating IP"
- VMs should never be created with public IPs by default; IPs managed as day-2 operations via APIs calling Ansible hooks
- Current template allows compound operation (Create VM + Allocate floating IP + Attach floating IP)

**Options:**

**A) Keep compound operation in template (current behavior)**
- **Pros:** Simpler for users (single operation), existing behavior preserved, no migration needed for current templates
- **Cons:** VM created with public IP by default (security concern), harder to manage IPs independently as day-2 operations, doesn't follow AWS/industry best practice model

**B) Separate APIs: VM creation is controller-only, floating IP is separate Ansible-invoked API**
- **Pros:** Better security (VMs private by default), follows AWS model and industry best practices, enables day-2 IP management and lifecycle, clearer separation of concerns between VM and networking
- **Cons:** More complex user workflow (requires two operations), requires API changes and new endpoints, migration effort needed for existing templates

**Team Feedback:**
- **Avishay:** Prefers Option B (separate APIs) - matches AWS model, enables day-2 IP management
- **Eran:** Agrees separate APIs needed; supports keeping compound operation as option if desired

**Action Required:** Determine if this change is in scope for this enhancement or separate future work.

### 5. Service Creation Scope
**Question:** Should LoadBalancer Service creation be part of controller-created resources, or is it provider-specific networking?

**Context:**
- Current proposal includes Service creation in controller
- **Adrien Gentil:** Questions if Service belongs in controller - it's provider-specific networking (MetalLB vs RouterAdvertisement/BGP)
- Different setups may not need Service objects at all
- Exposing ports seems like it should be part of Networking API (security group, LoadBalancer)

**Options:**

**A) Controller creates Service (current proposal)**
- **Pros:** Simple implementation, works for common case (MetalLB), keeps all Kubernetes-native resources in controller, faster initial delivery
- **Cons:** Assumes all providers use Kubernetes Services for networking, not flexible for different networking approaches (BGP, RouterAdvertisement, hardware load balancers), violates architectural boundary (networking is provider-specific)

**B) Service creation moves to Ansible provider integration layer**
- **Pros:** Flexible for provider-specific networking implementations, consistent with architectural boundary (networking in Ansible), supports non-Service networking approaches
- **Cons:** Splits Kubernetes resource creation between controller and Ansible (breaks consistency), requires Ansible even for simple Kubernetes-only deployments

**C) Separate Networking/LoadBalancer API handles Service creation**
- **Pros:** Clean separation of concerns, most flexible architecture, allows day-2 networking changes independent of VM lifecycle, matches conceptual model (networking separate from compute)
- **Cons:** Most complex to implement, requires new API development and additional components, delays feature availability, more moving parts to maintain

**Team Feedback:**
- **Adrien Gentil:** Suggests Service creation might belong in Networking API rather than VM provisioning

**Action Required:** Determine if Service creation stays in controller or moves to provider integration layer.

## Test Plan

### Unit Tests
- Test each resource builder with various parameter combinations
- Test template parameter parsing (valid/invalid JSON)
- Test annotation-based routing logic
- Target: >80% code coverage

### Integration Tests
- Set up `envtest` environment with KubeVirt + CDI CRDs
- Test full reconciliation loop:
  - Create ComputeInstance CR → verify all child resources created
  - Update ComputeInstance CR → verify resources updated
  - Delete ComputeInstance CR → verify cleanup (OwnerReferences)
- Test dual-mode annotation switching

### E2E Testing
- Deploy to dev cluster with real KubeVirt
- Create ComputeInstance CR with `managed-by: controller`
- Verify VM boots successfully
- Compare created resources with AAP-generated resources (diff check)
- Test error scenarios:
  - Invalid template parameters
  - Missing DataVolume storage class
  - KubeVirt API errors

**Acceptance Criteria:**
- All resources match AAP output (functional parity)
- VMs boot and are accessible via SSH
- Status updates correctly propagate to fulfillment-service
- Cleanup works (deletion removes all child resources)

## Graduation Criteria

### Phase 1: Research and Design (COMPLETE)
- ✅ Mapped Ansible playbook flow
- ✅ Documented all resources created by template role
- ✅ Analyzed cloudkit-operator ComputeInstance controller
- ✅ Identified template parameters
- ✅ Corrected terminology (ComputeInstance vs VirtualMachine)
- ✅ Created enhancement proposal

### Phase 2: Core Controller Implementation
**Tasks:**
1. Create `pkg/resources/computeinstance/` package
2. Implement resource builder functions:
   - `BuildCloudInitSecret()`
   - `BuildSSHKeySecret()`
   - `BuildDataVolume()`
   - `BuildVirtualMachine()`
   - `BuildLoadBalancerService()`
3. Implement `parseTemplateParameters()` JSON parser
4. Extend `ComputeInstanceReconciler.handleUpdate()` with dual-mode logic
5. Implement `reconcileVMResources()` method
6. Add annotation check for `managed-by` field
7. Add comprehensive logging and error handling

**Deliverables:**
- Working controller code that creates KubeVirt VirtualMachines natively
- Unit tests for all resource builders
- Integration test with fake Kubernetes client

### Phase 3: Testing
- Unit tests passing with >80% coverage
- Integration tests passing
- E2E tests passing in dev environment
- Resource parity verified (controller output matches AAP output)

### Phase 4: Pilot Deployment
- Deploy to dev environment successfully
- Deploy to staging environment successfully
- Gradual rollout: 10% → 25% → 50% → 100%
- Success rate ≥99.9%
- Latency <5 seconds

### Phase 5: Full Migration
- 100% of new compute instance orders use controller path
- AAP infrastructure idle but running (safety net)
- Extended monitoring period (2+ weeks)
- Zero AAP jobs triggered

### Phase 6: Cleanup
- Remove webhook code path from ComputeInstanceReconciler
- Remove `managed-by` annotation check
- Archive `cloudkit-aap` repository
- Update documentation
- Decommission AAP infrastructure

### Success Metrics

**Must-Have (Required for Production):**
- ✅ Controller successfully creates KubeVirt VirtualMachines from ComputeInstance CRs
- ✅ All resources match AAP-created resources (functional parity)
- ✅ VMs boot successfully and are accessible via SSH
- ✅ Status updates correctly propagate to fulfillment-service
- ✅ Error handling and retries work correctly
- ✅ Cleanup/deletion removes all child resources (via OwnerReferences)
- ✅ Zero downtime migration (dual-mode operation)
- ✅ Success rate ≥99.9% (matching or exceeding AAP)

**Should-Have (Performance Targets):**
- Order-to-VM-creation latency <5 seconds (vs. AAP ~30s)
- Prometheus metrics and Grafana dashboards operational
- Automated test coverage >80%
- Documentation complete (deployment, migration, troubleshooting)

**Nice-to-Have (Future Enhancements):**
- Template validation API (validate parameters before order submission)
- CLI tool for debugging compute instance creation
- Support for custom user-defined templates
- Dry-run mode for testing templates without actual resource creation

## Upgrade / Downgrade Strategy

**Upgrade:**
1. Deploy new cloudkit-operator version with dual-mode support
2. Existing compute instances continue using AAP (managed-by: "aap")
3. New compute instances gradually switch to controller (managed-by: "controller")
4. No API changes, no data migration needed

**Downgrade:**
1. Revert annotation to `managed-by: "aap"` in fulfillment-service
2. AAP continues to handle all provisioning
3. No service disruption

**Version Compatibility:**
- New controller is backwards compatible (AAP path still works)
- fulfillment-service can continue using same ComputeInstance API
- No breaking changes to CRD schema

## Version Skew Strategy

The controller version and fulfillment-service version can be upgraded independently:

- Old controller + New fulfillment-service: Works (AAP path still functional)
- New controller + Old fulfillment-service: Works (defaults to AAP path)
- Mixed compute instances (some AAP, some controller): Supported via annotation

## Support Procedures

**Troubleshooting Controller-Managed Compute Instances:**
1. Check ComputeInstance CR status: `kubectl get computeinstance <name> -o yaml`
2. Check controller logs: `kubectl logs -n cloudkit-system deployment/cloudkit-operator`
3. Check created resources: `kubectl get vm,dv,secret,svc -n <tenant-namespace>`
4. Verify OwnerReferences: `kubectl get vm <name> -o jsonpath='{.metadata.ownerReferences}'`

**Rollback Procedure:**
1. Update fulfillment-service to set `managed-by: "aap"` for new orders
2. Existing compute instances continue working (no action needed)
3. Monitor AAP job queue for activity resumption

**Common Issues:**
- **DataVolume creation fails:** Check storage class configuration
- **VM doesn't boot:** Check cloud-init secret formatting
- **Service doesn't route traffic:** Verify exposed_ports parameter parsing

## Infrastructure Needed

**Development:**
- Dev cluster with KubeVirt + CDI installed
- AAP instance for parallel testing

**Staging:**
- Staging cluster with production-like KubeVirt setup
- AAP instance for gradual rollout testing

**Production:**
- No new infrastructure (extends existing cloudkit-operator)
- Keep AAP infrastructure during migration period

## Appendix

### A. Current Ansible Playbook Flow

**Playbook:** `playbook_cloudkit_create_vm.yml`

```yaml
---
- name: Create CloudKit Compute Instance
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Get ComputeInstance CR from API
      kubernetes.core.k8s_info:
        api_version: cloudkit.openshift.io/v1alpha1
        kind: ComputeInstance
        name: "{{ vm_name }}"
        namespace: "{{ vm_namespace }}"
      register: ci_cr

    - name: Parse template parameters
      set_fact:
        template_params: "{{ ci_cr.resources[0].spec.templateParameters | from_json }}"

    - name: Call template role
      include_role:
        name: cloudkit.templates.ocp_virt_vm
        tasks_from: create
      vars:
        cpu_cores: "{{ template_params.cpu_cores }}"
        memory: "{{ template_params.memory }}"
        disk_size: "{{ template_params.disk_size }}"
        image_source: "{{ template_params.image_source }}"
        cloud_init_config: "{{ template_params.cloud_init_config }}"
        ssh_public_key: "{{ template_params.ssh_public_key | default('') }}"
        exposed_ports: "{{ template_params.exposed_ports }}"

    - name: Update ComputeInstance CR status
      kubernetes.core.k8s:
        api_version: cloudkit.openshift.io/v1alpha1
        kind: ComputeInstance
        name: "{{ vm_name }}"
        namespace: "{{ vm_namespace }}"
        definition:
          metadata:
            annotations:
              cloudkit.openshift.io/reconciled-config-version: "{{ ci_cr.resources[0].spec.desiredConfigVersion }}"
```

### B. References

**Repositories:**
- `cloudkit-operator`: https://github.com/innabox/cloudkit-operator
- `cloudkit-aap`: https://github.com/innabox/cloudkit-aap
- `fulfillment-service`: https://github.com/innabox/fulfillment-service

**Documentation:**
- KubeVirt API: https://kubevirt.io/api-reference/
- CDI API: https://github.com/kubevirt/containerized-data-importer
- controller-runtime: https://pkg.go.dev/sigs.k8s.io/controller-runtime

**Related Proposals:**
- CloudKit Architecture Overview (TBD)
- Bare Metal Fulfillment (../bare-metal-fulfillment/README.md)

### C. Terminology Reference

This proposal uses specific terminology to distinguish between CloudKit and KubeVirt resources:

**ComputeInstance CR** (`cloudkit.openshift.io/v1alpha1/ComputeInstance`):
- The CloudKit custom resource that users order
- Created by fulfillment-service when a user submits a compute instance order
- Contains high-level provisioning parameters in TemplateParameters JSON field
- Watched by cloudkit-operator for reconciliation

**KubeVirt VirtualMachine CR** (`kubevirt.io/v1/VirtualMachine`):
- The KubeVirt custom resource that actually runs the VM
- Created internally by either Ansible (current) or controller (proposed)
- Child resource of ComputeInstance (set via OwnerReferences)
- Watched by cloudkit-operator for status updates

**Usage Examples:**
- "Compute instance order/provisioning" - What users do
- "KubeVirt VirtualMachine CR creation" - Technical implementation detail
- "ComputeInstance CR" - CloudKit resource
- "kubevirt VirtualMachine" - KubeVirt resource

### D. Document Revision History

| Date       | Version | Author       | Changes                                  |
|------------|---------|--------------|------------------------------------------|
| 2026-01-11 | 1.0     | CloudKit Team| Initial design document created          |
| 2026-01-11 | 1.1     | CloudKit Team| Phase 1 research complete, scope refined |
| 2026-01-12 | 2.0     | CloudKit Team| Converted to enhancement proposal format, fixed terminology confusion between ComputeInstance and VirtualMachine |
