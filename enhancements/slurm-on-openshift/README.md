---
title: slurm-on-openshift
authors:
  - Swati Kale, Ecosystem Engineering
creation-date: 2025-12-16
last-updated: 2025-12-16
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

This enhancement proposes integrating Slurm workload manager with OpenShift clusters on Mass Open Cloud (MOC) using the Slinky operator. Slurm (Simple Linux Utility for Resource Management) is a widely-used open-source workload manager designed for Linux clusters of all sizes, commonly used in high-performance computing (HPC) environments. By deploying Slurm on OpenShift through the Slinky operator, tenants will be able to run traditional HPC workloads alongside cloud-native applications, leveraging OpenShift's container orchestration capabilities while maintaining familiar Slurm-based job scheduling and resource management.

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

* As a provider, I want to deploy OpenShift clusters with Slurm pre-configured using the Slinky operator, so that I can offer HPC-as-a-Service to my tenants.
* As a provider, I want to customize Slurm configurations during cluster deployment, so that I can tailor the HPC environment to specific use cases.
* As a tenant, I want to submit traditional Slurm batch jobs to an OpenShift cluster, so that I can run my existing HPC workflows without modification.
* As a tenant, I want to use familiar Slurm commands (sbatch, squeue, scancel, etc.) to manage my compute jobs on OpenShift.
* As a tenant, I want Slurm to integrate with OpenShift's resource management, so that I can take advantage of container-based isolation and orchestration.
* As a tenant, I want to access specialized hardware resources (GPUs, high-memory nodes) through Slurm scheduling on OpenShift.
* As a cluster administrator, I want to monitor Slurm job metrics and cluster utilization through OpenShift's observability stack. [optional]
* As a cluster administrator, I want to manage Slurm configurations declaratively using Kubernetes custom resources. [optional]

### Goals

* Integrate Slurm workload manager into OpenShift clusters using the Slinky operator
* Enable automated provisioning of OpenShift clusters with Slurm pre-configured and ready for HPC workloads
* Enable tenants to submit and manage Slurm jobs on OpenShift clusters
* Support standard Slurm commands and workflows for backward compatibility with existing HPC applications
* Leverage OpenShift's container orchestration for enhanced Slurm capabilities:
  - **Resource Isolation**: CPU/memory/GPU limits, namespace quotas, and QoS classes
  - **Network Security**: NetworkPolicies for tenant isolation and compliance (HIPAA, NIST 800-171)
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

7. The tenant receives cluster access credentials and can submit Slurm jobs using standard commands.


#### Submitting and Managing Slurm Jobs

1. The tenant accesses the cluster using provided credentials (SSH to login node or kubectl access).

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

1. The tenant requests deletion of the Slurm-enabled OpenShift cluster through the Fulfillment Service.

2. The O-SAC Operator detects the cluster deletion request.

3. The Operator initiates cleanup:
   - Drains and terminates running Slurm jobs (with configurable grace periods)
   - Deletes Slurm custom resources managed by the Slinky operator
   - Removes the Slinky operator deployment
   - Proceeds with standard OpenShift cluster deletion workflow

4. All associated resources (persistent volumes, network configurations, compute nodes) are released.

### Implementation Details/Notes/Constraints

#### Slinky Operator Integration

The implementation will leverage the upstream Slinky operator from the SlinkyProject community (https://github.com/SlinkyProject/slurm-operator). Using the upstream operator ensures vendor neutrality, broader community support, and compatibility across different OpenShift distributions. The operator will be deployed via Operator Lifecycle Manager (OLM) for standardized installation and lifecycle management.

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

#### Networking Considerations

* **Slurm Controller Access**: Exposed via Kubernetes Service (ClusterIP or LoadBalancer)
* **Compute Node Communication**: Leverages Kubernetes pod networking
* **External Access**: Optional NodePort or LoadBalancer for external job submission
* **Munge Authentication**: Shared secrets distributed via Kubernetes Secrets

#### Authentication and Authorization

* **MVP Approach**:
  - **Munge**: Inter-component authentication for Slurm services
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
* **Mixed Workloads**: Slurm nodes can potentially run both Slurm jobs and native Kubernetes workloads with appropriate resource allocation

#### Monitoring and Observability [optional]

* **Metrics Collection**: Slurm metrics exported via Prometheus exporters
* **Log Aggregation**: Slurm logs forwarded to OpenShift's logging stack (e.g., EFK/ELK)
* **Alerts**: Prometheus alerts for Slurm controller failures, database issues, node failures
* **Dashboards**: Grafana dashboards for Slurm job statistics and resource utilization

## Open Questions [optional]

* Should Slurm nodes be dedicated or can they share resources with other OpenShift workloads?

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
2. Scale down Slurm components: `kubectl scale deployment slurmctld --replicas=0`
3. Delete SlurmCluster CR: `kubectl delete slurmcluster <name>`
4. Uninstall Slinky operator if no longer needed

**Consequences**:
* Existing cluster health: Removing Slurm doesn't affect other OpenShift workloads

**Graceful Failure and Recovery**:
* Slurm controller uses persistent volumes for state; jobs resume after controller restart
* Database uses replication and backups for recovery
* Jobs are automatically requeued on node failures (configurable per job)
* Operator reconciliation ensures desired state is restored after transient failures


