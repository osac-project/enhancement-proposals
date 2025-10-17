---
title: Virtual-Machine-as-a-service
authors:
  - Adrien Gentil
creation-date: 2025-09-15
last-updated: 2025-09-15
tracking-link:
  - TBD
see-also:
replaces:
superseded-by:
---

# Virtual-Machine-as-a-Service


## Summary

This document proposes a service enabling tenants to easily create, manage, and
operate virtual machines (VMs) within a self-service environment. The service
will provide user-friendly APIs for provisioning, customizing, and controlling
the lifecycle of VMs attaching storage, and accessing specialized hardware
(GPUs).

This design aims to provide tenants with virtual machines using a
straightforward networking model. More advanced capabilities, such as those
related to Virtual Data Center-as-a-Service (VDCaaS), will be addressed in a
separate proposal.

## Motivation

Virtual-Machine-as-a-Service (VMaaS) addresses the need for flexible, on-demand
compute resources within a multi-tenant environment. Additionally, VMaaS enables
the sharing of specialized hardware resources, such as GPUs, across multiple
projects, maximizing hardware utilization and accessibility. This addresses a
need identified in the scope of O-SAC, and will benefit the MOC.

### User Stories

- As a provider, I want to define VM templates that my tenants will be able to
  use
- As a tenant, I want to list pre-defined VM templates
- As a tenant, I want to create a VM based on a pre-defined template
- As a tenant, I want a VM that has access to specialized hardware (e.g.: GPU)
- As a tenant, I want to manage the lifecycle of my VM (start/stop/terminate)
- As a tenant, I want to connect on my VM through serial console
- As a tenant, I want to be able to expose network services to an external
  network

### Goals

- Provide a self-service API for tenants to create, manage, and operate virtual
  machines (VMs) with minimal operational overhead
- Support a catalog of pre-defined VM templates
- Offer access to specialized hardware (e.g., GPUs) for tenants that require it
  through the catalog of templates
- Use ESI to assign floating IPs to created VM so they can be accessed
- Achieve high availability by supporting live migration of VMs
- Implement a quota system (to limit the number of VMs, storage, or resources
  each tenant can use) is out of scope for this enhancement and will be
  addressed in a separate proposal

### Non-Goals

The following are explicitly out of scope for this proposal:

- Implementing advanced VM orchestration features such as auto-scaling, and
  region placement
- Implementing Virtual Data Center-as-a-Service (VDCaaS) features such as
  virtual private networks
- Automatically add physical resources to cope with the demand of VMs
- Offering built-in backup, restore, or disaster recovery solutions for VMs or
  attached storage
- Delivering a marketplace for third-party VM images or applications, we expect
  tenant to rely on an external image registry to distribute OS base images

## Proposal

The process of fulfilling virtual machine requests is based on two primary APIs:

* **ComputeInstance**: Represents an individual virtual machine that a tenant
  can create and manage. Tenants can only see the virtual machines they created.
* **ComputeInstanceTemplate**: Defined by the provider, this is a pre-configured
  blueprint for virtual machines. Each template is identified by a unique
  template ID and includes a set of parameters (some required, some optional)
  that tenants can specify when creating a VM. Templates are available to all
  tenants to use, they cannot edit them.

To request a new ComputeInstance, tenants must provide:

* The ID of the desired ComputeInstanceTemplate
* Any required or optional parameters for that template
* The desired initial state of the VM (e.g., started or stopped)

The virtual machine fulfillment process will align with existing O-SAC
fulfillment workflows. To support this, the following O-SAC components will be
enhanced or updated:

* **Fulfillment Service**: Defines and exposes the APIs for managing
  ComputeInstance and ComputeInstanceTemplate resources.
* **Fulfillment CLI**: Provides tenants with command-line access to the
  Fulfillment Service APIs.
* **O-SAC Operator**: Monitors and reconciles ComputeInstance custom resources
  within the system.
* **O-SAC AAP (Ansible Automation Platform)**: Executes automation tasks (via
  Ansible playbooks) to reconcile ComputeInstance resources, including
  interactions with KubeVirt for VM lifecycle management and ESI APIs for
  assigning floating IPs.

### Workflow Description

#### Virtual machine creation and update

1. The tenant initiates the creation of a new ComputeInstance using the
   Fulfillment CLI. The tenant must provide:
    - The ID of the desired ComputeInstanceTemplate
    - All required and any optional parameters for the template (such as CPU,
      memory, disk size, network configuration)
    - The desired initial state of the VM (e.g., started or stopped)

2. The Fulfillment Service receives this request and performs validation to
   ensure:
    - The specified template exists and is available
    - All required parameters are provided and valid

3. Upon successful validation, the Fulfillment Service creates a new
   ComputeInstance custom resource (CR) in the appropriate Hub and namespace.

4. The O-SAC Operator detects the new ComputeInstance CR and begins the
   reconciliation process.

5. The Operator, using Ansible Automation Platform (AAP), automates the
   following steps:
    - Provisions necessary resources, including:
        - Tenant's namespace
        - A UDN L2 network to provide network isolation
        - A load balancer service with the VM as its backend
        - Assignment of a floating IP to the load balancer service for external
          access
    - Creates the KubeVirt VirtualMachine resource using the specified template
      and parameters
    - Performs any additional operations required by the selected template

6. The Operator continuously monitors the VM’s status and updates the
   ComputeInstance CR status to reflect the current state.

7. The tenant can check the VM’s status at any time using the Fulfillment CLI or
   API, and can access the VM via the assigned floating IP.

The update process is the same as the creation workflow as it will be designed
to be idempotent.

#### Virtual machine deletion

When a tenant requests the deletion of a ComputeInstance, the following workflow
is executed:

1. The tenant initiates the deletion of a ComputeInstance using the Fulfillment
   CLI or API by specifying its identifier.

2. The Fulfillment Service receives the deletion request and performs validation
   to ensure:
    - The specified ComputeInstance resource exists and is available.
    - The tenant has permission to delete the resource.

3. Upon successful validation, the Fulfillment Service deletes the
   ComputeInstance custom resource (CR) from the appropriate namespace.

4. The O-SAC Operator detects the deletion of the ComputeInstance CR and begins
   the cleanup process.

5. The Operator, using Ansible Automation Platform (AAP), automates the
   following steps:
    - Deletes the KubeVirt VirtualMachine resource.
    - Releases and deallocate any associated resources, including:
        - Tenant's namespace
        - UDN L2 network
        - Load balancer service
        - Floating IPs via ESI APIs
    - Performs any additional cleanup operations required by the selected
      virtual machine template.
    - Deletes the dedicated namespace if it is no longer needed.

6. The Operator updates the status of the deletion operation and ensures all
   resources are properly cleaned up.

7. The tenant can confirm the deletion and cleanup via the Fulfillment CLI or
   API.

This workflow ensures that all resources associated with the ComputeInstance are
properly deprovisioned and that no orphaned resources remain.

#### Virtual machine template management

Virtual machine templates are centrally managed by the provider using a GitOps
approach. All templates are stored in a version-controlled repository, which
acts as the single source of truth. At regular intervals, an automated job in
Ansible Automation Platform (AAP) synchronizes the latest templates from this
repository to the Fulfillment Service. As a result, any changes to the
templates—such as updates, additions, or deletions—are automatically and
consistently reflected in the Fulfillment Service. This process ensures that
tenants always have access to the most current catalog of available VM
templates.

### API Extensions

#### ComputeInstance

A tenant requests a virtual machine by requesting a ComputeInstance to the
Fulfillment Service. Here is an example of request that creates a VM, using a
template that let tenants to customize the amount of CPUs, memory and boot disk
size:

```json
{
  "object": {
    "id": "myvm",
    "spec": {
      "state": "started",
      "template": "ocp_virt_vm",
      "template_parameters": {
        "vm_cpu_cores": {
          "value": 4
        },
        "vm_disk_size": {
          "value": "30Gi"
        },
        "vm_memory": {
          "value": "4Gi"
        }
      }
    }
  }
}
```

After creating a virtual machine, tenants can check its current status and
details as follows:

```json
{
  "@type": "type.googleapis.com/fulfillment.v1.ComputeInstance",
  "id": "fecb9b9e-07ac-4d56-8b48-9d50aab71677",
  "metadata": {
    "creation_timestamp": "2025-09-17T08:14:17.569076Z",
    "creators": [
      "guest"
    ]
  },
  "spec": {
    "state": "started",
    "template": "ocp_virt_vm",
    "template_parameters": {
      "vm_cpu_cores": {
        "value": 4
      },
      "vm_disk_size": {
        "value": "30Gi"
      },
      "vm_memory": {
        "value": "4Gi"
      }
    }
  },
  "status": {
    "conditions": [
      {
        "last_transition_time": "2025-09-19T17:32:24.054439350Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_CONDITION_TYPE_PROVISIONING"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_STATE_STARTING"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_TRUE",
        "type": "COMPUTE_INSTANCE_STATE_RUNNING"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_STATE_STOPPING"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_STATE_STOPPED"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_STATE_TERMINATING"
      },
      {
        "last_transition_time": "2025-09-17T08:52:12.652582382Z",
        "message": "",
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_STATE_PAUSED"
      },
      {
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_CONDITION_TYPE_FAILED"
      },
      {
        "status": "CONDITION_STATUS_FALSE",
        "type": "COMPUTE_INSTANCE_CONDITION_TYPE_DEGRADED"
      }
    ],
    "state": "COMPUTE_INSTANCE_STATE_RUNNING",
    "internalIP": "10.0.0.1",
    "externalIP": "193.1.2.3"
  }
}
```

The status section provides two types of IP addresses for the virtual machine:

- `internalIP`: The private IP address assigned to the virtual machine on the
  internal network.

- `externalIP`: The public (floating) IP address assigned to the virtual
  machine. This address allows the virtual machine to be accessed from outside
  the internal network, such as from the internet.

The virtual machine can be in one of the following states, as reflected in the
status section above. These states are mapped from the underlying KubeVirt
VirtualMachine status conditions:

- **Provisioning** (`COMPUTE_INSTANCE_STATE_PROVISIONING`): The virtual machine
  is being created.
- **Starting** (`COMPUTE_INSTANCE_STATE_STARTING`): The virtual machine started.
- **Running** (`COMPUTE_INSTANCE_STATE_RUNNING`): The virtual machine is
  actively running.
- **Stopping** (`COMPUTE_INSTANCE_STATE_STOPPING`): The virtual machine is in
  the process of shutting down.
- **Stopped** (`COMPUTE_INSTANCE_STATE_STOPPED`): The virtual machine is
  stopped.
- **Terminating** (`COMPUTE_INSTANCE_STATE_TERMINATING`): The virtual machine is
  in the process of being deleted.
- **Paused** (`COMPUTE_INSTANCE_STATE_PAUSED`): The virtual machine is in a
  suspended state.

These states are reported in the `type` field of the VM's `conditions` array in
the status section.


#### ComputeInstanceTemplate

Virtual machine templates are implemented as Ansible roles. Each role must
include the following files:

* `vm_template_role/meta/argument_specs.yaml`: Defines the [Ansible argument
  specification](https://docs.ansible.com/ansible/latest/dev_guide/developing_program_flow_modules.html#argument-spec).
  This file is required.
* `vm_template_role/meta/cloudkit.yaml`: Contains metadata for the template,
  including the title and description. This file is required.

Example of `cloudkit.yaml`:

```yaml
title: VM Template
description: >
  This template provisions a virtual machine.
```

A periodic job will publish the Ansible roles as virtual machine templates to
the Fulfillment Service, using the required files described above. The following
is the API format used for this publication:

```json
{
  "object": {
    "id": "vm_template_role",
    "title": "VM Template",
    "description": "This template provisions a virtual machine.",
    "parameters": [
      {
        "name": "vm_cpu_cores",
        "default": {
          "value": 2
        }
      },
      {
        "name": "vm_memory",
        "default": {
          "value": "2Gi"
        }
      },
      {
        "name": "vm_disk_size",
        "default": {
          "value": "20Gi"
        }
      }
    ]
  }
}
```

### Implementation Details/Notes/Constraints

This proposal is built upon OpenShift Virtualization, which leverages KubeVirt
to provide virtualization capabilities. By using OpenShift Virtualization, we
are able to offer tenants a self-service platform for creating, managing, and
operating virtual machines (VMs) with minimal operational overhead, directly
aligning with our goal of providing a user-friendly API for VM lifecycle
management.

When a VM is created, it is connected to a dedicated UDN (User Defined Network)
that is assigned to the tenant. In other words, all VMs belonging to the same
tenant share a single UDN, while VMs from different tenants are placed on
separate UDNs. This design ensures strong network isolation between tenants.

Even though all of a tenant's VMs share the same UDN (User Defined Network) in a
given HUB cluster, each VM still needs its own floating IP in order to be
accessible from other VMs. This is because the Fulfillment Service may provision
a tenant's VMs on different HUB clusters, as a consequence, internal network
connectivity between VMs cannot be guaranteed. The floating IP is also required
to access the VM from the outside.

To allow services running on a VM to be accessible from outside the cluster, the
template may handle the port mapping through a parameter. Defining which ports
to be exposed as a template parameter provides flexibility: it allows us to
easily adjust how ports will be exposed in the future, especially when VDCaaS
(Virtual Data Center as a Service) will introduce new ways to manage external
access.

### Risks and Mitigations

TBD

### Drawbacks

#### Virtual machines on HUB cluster

Initially, all virtual machines will be created on the HUB cluster selected by
the Fulfillment Service.

In the future, we plan to support deploying virtual machines on remote,
dedicated clusters. This approach offers several advantages:

- It provides stronger isolation between customer workloads and the cloud
  provider’s management tools
- It allows the management (HUB) cluster to be upgraded, maintained, or migrated
  independently from the clusters running customer VMs
- The clusters hosting VMs can be managed and monitored according to their own
  uptime and operational requirements, even if they share hardware with the
  management cluster (in case of Hosted Clusters)
- It enables the possibility of creating dedicated virtualization clusters for
  individual tenants, which is important for tenants who require higher levels
  of isolation

This feature will be part of a separate enhancement.

#### Networking

While simple, the initial design of VMaaS networking has significant
limitations:

- Tenants cannot create complex VM architectures that use both public and
  private networks. Features such as security groups and network ACLs are also
  missing
- Each gets a floating IP assigned to it, this pool of IPs is limited
- OpenShift team doesn't recommend more than 100 UDNs per cluster, this solution
  will then be limited to 100 tenants using VMs

We expect to revisit and improve this design once the VDCaaS (Virtual Data
Center as a Service) functionality is available.

## Alternatives (Not Implemented)


## Open Questions [optional]


## Test Plan

TBD

## Graduation Criteria

TBD

### Removing a deprecated feature

N/A

## Upgrade / Downgrade Strategy

N/A

## Version Skew Strategy

N/A

## Support Procedures

TBD

## Infrastructure Needed [optional]

N/A
