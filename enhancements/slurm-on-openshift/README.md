---
title: slurm-on-openshift
authors:
  - Swati Kale, Ecosystem Engineering
creation-date: 2025-12-16
last-updated: 2026-03-27
tracking-link:
  - TBD
see-also:
  - None
replaces:
  - None
superseded-by:
  - None
---

# Slurm on OpenShift with Slinky

## Summary

This enhancement proposes integrating Slurm workload manager with OpenShift clusters designed for broader Open Sovereign AI Cloud (OSAC) adoption using the Slinky operator. Slurm (Simple Linux Utility for Resource Management) is a widely-used open-source workload manager designed for Linux clusters of all sizes, commonly used in high-performance computing (HPC) environments. By deploying Slurm on OpenShift through the Slinky operator, tenants will be able to run traditional HPC workloads alongside cloud-native applications, leveraging OpenShift's container orchestration capabilities while maintaining familiar Slurm-based job scheduling and resource management.

The implementation will modify existing Ansible templates from the osac-templates repository to automate the deployment of complete OpenShift clusters with Slurm pre-configured and integrated via the Slinky operator, providing a seamless HPC-as-a-Service experience.

## Motivation

Many enterprises and research organizations already rely on Slurm for:
- HPC batch workloads
- GPU-intensive AI/ML training and inference
- Large-scale, multi-tenant compute environments

At the same time, OpenShift is increasingly used as the standard platform for:
- Containerized AI/ML platforms (e.g., OpenShift AI)
- Secure, policy-driven cluster operations
- Hybrid and sovereign cloud deployments

Today, these worlds often remain separate. Users must choose between:
- Running Slurm on bare metal or VMs, or
- Rewriting workflows to fit Kubernetes-native schedulers

This enhancement aims to **bridge Slurm and OpenShift**, allowing existing Slurm users to adopt OpenShift incrementally while preserving their current workflows.

### User Stories

**Personas:**
- **Provider**: Cloud infrastructure operator who manages O-SAC platform
- **Cluster Administrator**: Organization or team that requests/manages a Slurm cluster
- **Job Submitter**: Individual researcher or developer who submits and runs Slurm jobs

#### Cluster Provisioning Stories

**Provider-Provisioned Model:**
* As a provider, I want to deploy OpenShift clusters with Slurm pre-configured using the Slinky operator, so that I can offer HPC-as-a-Service to my tenant organizations.
* As a provider, I want to customize Slurm configurations during cluster deployment, so that I can tailor the HPC environment to specific organizational needs.

**Self-Service Model:**
* As a cluster administrator, I want to request and provision my own Slurm-enabled OpenShift cluster through the Fulfillment Service, so that my organization has dedicated HPC resources.
* As a cluster administrator, I want to customize Slurm partition configurations (CPU, GPU, memory) during cluster request, so that I can match my team's workload requirements.

#### Job Submission and Management Stories

* As a job submitter, I want to submit traditional Slurm batch jobs to an OpenShift cluster, so that I can run my existing HPC workflows without modification.
* As a job submitter, I want to use familiar Slurm commands (sbatch, squeue, scancel, etc.) to manage my compute jobs on OpenShift.
* As a job submitter, I want Slurm to leverage OpenShift's AI/HPC infrastructure capabilities, so that I can benefit from automated resource management, security compliance, and high availability.
* As a job submitter, I want to access specialized hardware resources (GPUs, high-memory nodes) through Slurm scheduling on OpenShift.

#### Cluster Operations Stories

* As a cluster administrator, I want to monitor Slurm job metrics and cluster utilization through OpenShift's observability stack. [optional]
* As a cluster administrator, I want to manage Slurm configurations declaratively using Kubernetes custom resources. [optional]

### Goals

* Integrate Slurm workload manager into OpenShift clusters using the Slinky operator
* Enable automated provisioning of OpenShift clusters with Slurm pre-configured and ready for HPC workloads
* Enable tenants to submit and manage Slurm jobs on OpenShift clusters
* Support standard Slurm commands and workflows for backward compatibility with existing HPC applications
* Leverage OpenShift's AI/HPC infrastructure capabilities for enhanced Slurm deployments:
  - **Resource Isolation**: CPU/memory/GPU limits, namespace quotas, and QoS classes
  - **Network Security**: NetworkPolicies for security controls and compliance (HIPAA, NIST 800-171)
  - **Hardware Management**: NVIDIA GPU Operator for automatic GPU discovery and allocation
  - **High Availability**: Pod failover, anti-affinity spreading across failure domains
  - **Monitoring**: Prometheus metrics and audit logging for compliance and troubleshooting
* Provide configuration options for Slurm parameters during cluster deployment
* Enable monitoring and observability of Slurm workloads through OpenShift tools [optional]

### Non-Goals

* Replacing OpenShift's native workload scheduling with Slurm (both will coexist)
* Supporting all Slurm plugins and advanced features in the initial implementation
* Migrating existing standalone Slurm clusters to OpenShift (this is a greenfield deployment)
* Providing a GUI interface for Slurm job submission (command-line interface will be primary)
* Implementing custom Slurm accounting or billing systems (organizations can integrate their own)
* Supporting multi-cluster Slurm federations across multiple OpenShift clusters in the initial phase
* Dynamic autoscaling of compute nodes via KEDA or similar metrics-based scaling (static node pools in MVP)

## Proposal

The implementation of Slurm on OpenShift leverages the Slinky operator, which provides Kubernetes-native management of Slurm components. The proposal involves:

* **Slinky Operator**: A Kubernetes operator that manages Slurm controller, compute nodes, and database components as Kubernetes resources
* **Slurm Components**: Traditional Slurm components (slurmctld, slurmd, slurmdbd) running as containerized workloads on OpenShift
* **Integration Points**: Connections between Slurm and OpenShift for resource discovery, job scheduling, and monitoring

The deployment will use an independent Ansible collection for slinky-on-openshift:

* **Ansible Collection**: Standalone collection providing roles and playbooks for Slinky operator deployment and Slurm cluster configuration
* **Fulfillment Integration**: Collection can be invoked from O-SAC fulfillment workflows to provision Slurm-enabled clusters
* **Cluster Configuration**: Collection handles Slinky operator deployment, Slurm custom resource creation, and initial configuration
* **Reusability**: Collection can be used independently of O-SAC for other OpenShift environments

### Architecture Overview

```
+---------------------------+
|   OSAC Ansible Templates  |
| (Cluster Provisioning)   |
+-------------+-------------+
              |
              v
+---------------------------+
|   OpenShift Cluster       |
|  (GPU / CPU Workers)     |
+-------------+-------------+
              |
              v
+---------------------------+
|   Slurm Control Plane     |
| (slurmctld, slurmdbd)    |
|   running on OpenShift   |
+-------------+-------------+
              |
              v
+---------------------------+
|          Slinky           |
|   Slurm ↔ Kubernetes     |
|        Integration       |
+-------------+-------------+
              |
              v
+---------------------------+
|   Kubernetes Pods        |
| (HPC / AI / GPU Jobs)    |
+---------------------------+
```


### Workflow Description

#### Slurm-enabled OpenShift Cluster Creation

1. The tenant uses the Fulfillment CLI to request an OpenShift cluster with Slurm enabled, specifying:
   - Standard OpenShift cluster parameters (size, node types, networking)
   - Slurm-specific configuration (partition definitions, compute node counts, accounting database settings)
   - Resource allocations for Slurm controller and compute nodes

2. The Fulfillment Service validates the request and creates an OpenShift cluster custom resource (CR) with Slurm integration flags.

3. The O-SAC Operator detects the new cluster CR and initiates the reconciliation process.

4. The Operator, using Ansible Automation Platform (AAP), executes the modified osac-templates playbooks:
   - Provisions the base OpenShift cluster using existing cluster deployment workflows
   - Deploys the Slinky operator to the cluster
   - Creates Slurm custom resources (SlurmCluster, SlurmPartition, etc.) based on tenant specifications
   - Configures Slurm controller (slurmctld) as a highly-available deployment
   - Provisions Slurm database (slurmdbd) with persistent storage
   - Deploys Slurm compute nodes (slurmd) as workloads on designated OpenShift nodes
   - Configures networking for Slurm components
   - Sets up authentication and authorization integration

5. The Slinky operator reconciles the Slurm custom resources:
   - Creates containerized Slurm controller and database deployments
   - Provisions Slurm compute node DaemonSets or Deployments
   - Generates and distributes Slurm configuration files (slurm.conf, slurmdbd.conf)
   - Establishes inter-component communication

6. The O-SAC Operator monitors the deployment status and updates the cluster CR to reflect Slurm readiness.

7. The tenant receives cluster access information via the Fulfillment CLI/API, including:
   - **Login Endpoint**: FQDN and SSH port for the login pod (e.g., `slurm-login.cluster-name.example.com:22`)
   - **Slurm Controller Endpoint**: Internal service endpoint for slurmctld (e.g., `slurm-controller.slurm-system.svc.cluster.local:6817`)
   - **SSH Credentials**: SSH public key to add to authorized_keys, or generated SSH keypair for login pod access
   - **Kubeconfig**: Credentials for kubectl access to the OpenShift cluster (for administrators)
   - **User Accounts**: List of pre-configured Slurm user accounts 


#### Submitting and Managing Slurm Jobs

1. The tenant connects to the Slurm cluster using the SSH endpoint and credentials provided during cluster provisioning:
   ```bash
   ssh -i ~/.ssh/slurm-key user@slurm-login.my-hpc-cluster.apps.example.com
   ```
   The login pod provides access to Slurm CLI commands and communicates with the Slurm controller for job management. 

2. The tenant submits a Slurm job using standard commands:
   ```bash
   sbatch --partition=compute --nodes=2 --ntasks-per-node=4 my_job_script.sh
   ```

3. The Slurm controller (slurmctld) receives the job request and schedules it based on available resources.

4. Slurm compute nodes (slurmd) execute the job steps, launching containers or processes as configured.

5. The tenant monitors job status using standard Slurm commands:
   ```bash
   squeue              # View job queue
   scontrol show job <jobid>   # View job details
   scancel <jobid>     # Cancel a job
   ```

6. Job accounting information is recorded in the Slurm database for auditing and reporting.


#### Updating Slurm Configuration

1. The cluster administrator uses kubectl to update Slurm custom resources:
   ```bash
   kubectl edit slurmcluster main-cluster
   ```

2. The Slinky operator detects the configuration change and reconciles:
   - Updates Slurm configuration files
   - Performs rolling updates of affected components
   - Triggers configuration reloads where appropriate

3. The administrator monitors the update progress through OpenShift resources and Slurm status commands.

#### Cluster Deletion

When a Slurm-enabled OpenShift cluster is deleted, the standard O-SAC cluster deletion workflow applies. The Slinky operator and Slurm custom resources are removed as part of the cluster cleanup process, with no special Slurm-specific handling required.

### Implementation Details/Notes/Constraints

#### Slinky Operator Integration

The implementation will leverage the upstream Slinky operator from the SlinkyProject community (https://github.com/SlinkyProject/slurm-operator). The operator will be deployed via Operator Lifecycle Manager (OLM) for standardized installation and lifecycle management.

Key integration points:

* **Operator Deployment**: The Slinky operator will be deployed to a dedicated namespace (e.g., `slurm-system`) during cluster provisioning
* **Custom Resource Management**: The operator manages Slurm lifecycle through Kubernetes custom resources
* **Configuration Management**: Slurm configuration files are generated from CRs and distributed via ConfigMaps
* **Container Images**: Slurm components run in containers with appropriate entrypoints and health checks

#### Ansible Template Modifications

The osac-templates repository will be extended with:

* **New Roles**:
  - `slinky-operator-deploy`: Deploys the Slinky operator
  - `slurm-cluster-configure`: Creates and configures Slurm custom resources
  - `slurm-node-prepare`: Prepares OpenShift nodes for Slurm compute workloads

* **Modified Playbooks**:
  - `cluster-create.yml`: Extended to conditionally deploy Slurm when requested
  - `cluster-configure.yml`: Enhanced to handle Slurm-specific configurations

* **Variable Templates**:
  - Parameterized Slurm configurations for flexible deployment
  - Partition definitions based on node types and resources

#### Proposed API design 

The following enumerates **field names and types** for review. This is a **proposed contract** for what Fulfillment (or equivalent automation) should collect and return; it is **not** a shipped HTTP/OpenAPI implementation in this enhancement. Shapes are aligned with the **Slinky** Kubernetes API (`apiVersion: slinky.slurm.net/v1beta1`, kinds **`Controller`** and **`NodeSet`**) as used in a Slurm-on-OpenShift proof of concept. Ansible variables, Fulfillment request bodies, or parent cluster CR `status` subresources can **project** these same fields. Upstream docs and playbooks that refer to “Slurm cluster” resources should map to these kinds.

#### Input — configuration collected at provision time

**Placement and naming**

| Field | Type | Slinky mapping |
| --- | --- | --- |
| `slurm_namespace` | `string` | Namespace for `Controller` / `NodeSet` (e.g. `slurm`) |
| `controller_name` | `string` | `Controller` `metadata.name` |
| `nodeset_name` | `string` | `NodeSet` `metadata.name` (repeat pattern if multiple NodeSets) |

**Auth — secret references (values are not embedded in CRs)**

| Field | Type | Slinky mapping |
| --- | --- | --- |
| `jwt_secret_ref.name` | `string` | `spec.jwtHs256KeyRef.name` |
| `jwt_secret_ref.key` | `string` | `spec.jwtHs256KeyRef.key` |
| `slurm_key_secret_ref.name` | `string` | `spec.slurmKeyRef.name` |
| `slurm_key_secret_ref.key` | `string` | `spec.slurmKeyRef.key` |

**`Controller` spec**

| Field | Type | Slinky mapping |
| --- | --- | --- |
| `slurmctld.image` | `string` | `spec.slurmctld.image` |
| `slurmctld.resources.requests.cpu` | `string` | Kubernetes quantity |
| `slurmctld.resources.requests.memory` | `string` | Kubernetes quantity |
| `slurmctld.resources.limits.cpu` | `string` | Kubernetes quantity |
| `slurmctld.resources.limits.memory` | `string` | Kubernetes quantity |
| `persistence.enabled` | `boolean` | `spec.persistence.enabled` |
| `persistence.storage` | `string` | e.g. `spec.persistence.resources.requests.storage` |
| `persistence.access_modes` | `array[string]` | e.g. `ReadWriteOnce` |
| `slurm_extra_conf` | `string` | `spec.extraConf` (Slurm.conf lines, including `PartitionName=...`) |

**`NodeSet` spec**

| Field | Type | Slinky mapping |
| --- | --- | --- |
| `controller_ref.name` | `string` | `spec.controllerRef.name` |
| `controller_ref.namespace` | `string` | `spec.controllerRef.namespace` |
| `compute_replicas` | `integer` | `spec.replicas` |
| `partition.enabled` | `boolean` | `spec.partition.enabled` |
| `slurmd.image` | `string` | `spec.slurmd.image` |
| `slurmd.resources.requests` / `limits` | `object` | Same structure as controller resources |
| `node_selector` | `map[string]string` | `spec.template.spec.nodeSelector` |
| `tolerations` | `array[object]` | `spec.template.spec.tolerations` (optional) |
| `affinity` | `object` | `spec.template.spec.affinity` (optional) |

**Helm values path (optional)**

If provisioning uses the Slinky Helm chart instead of raw CRs, the same logical fields appear under chart values (for example `controller.*`, `compute.replicas`, `slurm.partitions[]` with `name`, `default`, `maxTime`, `nodes`, and `network.serviceType`). Automation should either generate CRs from those values or treat the chart as the single source of truth.

#### Output — information returned to the tenant after successful provisioning

Prefer **references** for secrets; avoid returning raw key material in API responses unless policy explicitly requires it.

**Connection and inventory (non-sensitive)**

| Field | Type | How populated (conceptual) |
| --- | --- | --- |
| `slurm_namespace` | `string` | From request / applied manifest |
| `controller_cr_name` | `string` | `Controller` name |
| `nodeset_names` | `array[string]` | All `NodeSet`s for the controller |
| `slurmctld_service_hostname` | `string` | Kubernetes Service DNS name for slurmctld (from cluster API after reconcile) |
| `slurmctld_port` | `integer` | Typically `6817` |
| `openshift_api_url` | `string` | Standard cluster handoff (cluster admins) |
| `console_url` | `string` | Optional OpenShift console URL |
| `effective_partitions` | `array[object]` | Post-ready: e.g. `{ name, default, max_time, nodes_expr }` from `sinfo` or generated `slurm.conf` |

**Credentials (by reference or platform pattern)**

| Field | Type | Notes |
| --- | --- | --- |
| `credential_refs` | `array[object]` | e.g. `{ secret_name, namespace, purpose: "jwt" \| "slurm_key" }` |
| `kubeconfig_delivery` | `string` | Enum or platform convention: e.g. `standard_cluster_handoff`, `vault`, `one_time_download` |

**Optional — external login / SSH (when a login pod and Route exist)**

| Field | Type |
| --- | --- |
| `login_ssh_host` | `string` |
| `login_ssh_port` | `integer` |
| `ssh_key_ref` or `ssh_public_key` | `string` (reference or material per security review) |

A minimal POC often uses **`kubectl` / `oc` and `oc exec` into the controller pod** instead of an SSH login service; the output contract should still expose **service hostname**, **port**, and **namespace** so clients and automation can connect without ad hoc discovery.

##### Delivery mechanism

The concrete channel (Fulfillment API JSON body, artifacts from AAP, or `status.slurm` on a parent cluster CR) is **implementation-specific** and should be chosen in the fulfillment and operator design pass. The tables above define **what** to surface; **where** it lives can follow existing O-SAC patterns for cluster credentials and endpoints.

#### Networking Considerations

* **Slurm Controller Access**: Exposed via Kubernetes Service (ClusterIP or LoadBalancer)
* **Compute Node Communication**: Leverages Kubernetes pod networking
* **External Access**: Optional NodePort or LoadBalancer for external job submission

#### Authentication and Authorization

* **MVP Approach**:
  - **Inter-component auth**: Slurm native auth via slurm.key secret (deployed and configured by the operator for controller and NodeSets)
  - **Local User Management**: Users created in Slurm pods with synchronized UID/GID mappings
  - **Static User Database**: Pre-configured user accounts deployed via ConfigMaps
* **Post-MVP**: LDAP/AD integration with SSSD for centralized identity management and existing filesystem compatibility

#### Storage Requirements

* **Slurm Configuration**: ConfigMaps for slurm.conf, slurmdbd.conf, and related files
* **Accounting Database**: PersistentVolume for MySQL/MariaDB data
* **Job State Information**: PersistentVolume for Slurm controller state files

##### MVP Approach for Shared Storage

* **NFS CSI Driver**: For shared home directories and job data across compute nodes
* **PersistentVolumeClaims**: User-specific storage with ReadWriteMany (RWX) access mode
* **Mount Paths**:
  - `/home/<username>`: User home directories
  - `/scratch`: Shared scratch space for job I/O
* **Post-MVP**: CephFS and Lustre integration for HPC workloads requiring parallel filesystems

#### Resource Management

* **Node Selection**: Slurm compute nodes run on designated OpenShift nodes via nodeSelectors or taints/tolerations
* **Resource Isolation**: Kubernetes resource limits and requests configured for Slurm components
* **GPU Access**: Integration with OpenShift's GPU operator for GPU-enabled Slurm partitions

#### Deployment Status Reporting

* **MVP Approach**:
  - Ansible playbooks wait for Slurm components to reach ready state before completing
  - Monitor SlurmCluster custom resource status conditions for deployment progress
  - Verify Slurm controller and database pods are running and passing health checks
  - Report success/failure status back to fulfillment service based on observed resource conditions
  - Allow administrative intervention for troubleshooting deployment issues
* **Post-MVP**: Real-time status updates via Kubernetes events and metrics-based validation

#### OpenShift-Native Monitoring and Observability [optional]

Standard Slurm monitoring and logging tools (sinfo, squeue, sacct, slurmctld logs, etc.) will be available for cluster administrators to monitor Slurm cluster health and troubleshoot issues. This section describes optional OpenShift-native integrations for unified observability:

* **Metrics Collection**: Slurm metrics exported via Prometheus exporters for integration with OpenShift monitoring
* **Log Aggregation**: Slurm logs forwarded to OpenShift's logging stack (e.g., EFK/ELK) for centralized log management
* **Alerts**: Prometheus alerts for Slurm controller failures, database issues, node failures
* **Dashboards**: Grafana dashboards for Slurm job statistics and resource utilization alongside other cluster metrics

## Test Plan

**Unit Tests**:
* Ansible role validation for Slinky deployment
* Template rendering for Slurm custom resources
* Configuration file generation logic

**Integration Tests**:
* End-to-end cluster creation with Slurm enabled
* Slurm job submission and execution
* Job accounting and reporting
* Failover scenarios for Slurm controller
* Resource allocation and isolation

## Support Procedures

**Disabling/Removing Slurm** [optional] :

To disable Slurm on a cluster:
1. Drain all running jobs: `scancel -u <all_users>`
2. Scale down Slurm components: `kubectl scale <resource-type> <resource-name> --replicas=0`
3. Delete SlurmCluster CR: `kubectl delete slurmcluster <name>`
4. Uninstall Slinky operator if no longer needed

**Consequences**:
* Existing cluster health: Removing Slurm doesn't affect other OpenShift workloads

**Graceful Failure and Recovery**:
* Slurm controller uses persistent volumes for state; jobs resume after controller restart
* Database uses replication and backups for recovery
* Jobs are automatically requeued on node failures (configurable per job)
* Operator reconciliation ensures desired state is restored after transient failures


