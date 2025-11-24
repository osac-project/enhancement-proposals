---
title: bare-metal-fulfillment
authors:
  - Tzu-Mainn Chen
creation-date: 2025-09-08
last-updated: 2025-09-15
tracking-link:
  - None
see-also:
  - None
replaces:
  - None
superseded-by:
  - None
---

# Bare Metal Fulfillment

## Summary

Bare metal fulfillment refers to the process through which a tenant acquires bare metal hosts and configures their networking.
Afterwards, the tenant will be able to perform selected operations on the host: inventory information, power control, and
serial console access. Any further operations - for example, image-based provisioning - are outside the scope of the O-SAC
solution and must be integrated by the cloud provider.

We believe this feature set is generic enough to support a wide range of initial bare metal cluster use cases, including:

* support for an environment where developers have the flexibility to install their own operating systems and software
* support for alternative clusters such as SLURM
* support for bare metal configuration during O-SAC cluster fulfillment

In this context, a “tenant” is an organization that can perform selected actions on the requested bare metal resources in
order to achieve these use cases; at the MOC, a tenant would be led by a ColdFront PI or manager.

## Motivation

Bare metal fulfillment is a fundamental requirement for O-SAC, identified as an explicit need for the MOC. It will also serve
as a component for other fulfillment workflows, such as VDC and OpenShift cluster fulfillment.

### User Stories

* As a provider, I want to define the available bare metal resource classes.
* As a provider, I want to mark hosts as available for bare metal fulfillment.
* As a tenant, I want to see available bare metal resource classes.
* As a tenant, I want to select hosts for a bare metal cluster by resource class and other possible filters (such as rack location).
* As a tenant, I want to increase or decrease the number of hosts for an existing bare metal cluster.
* As a tenant, I want to view inventory details for my hosts.
* As a tenant, I want to connect to the serial console of my hosts.
* As a tenant, I want to perform basic power control (power on/power off/reset) of my hosts.
* As a tenant, I want to specify network attachments for a host when I first acquire it.
* As a tenant, I want to modify the network attachments of a host that I have already acquired.
* As a tenant, I want to manage connectivity at the interface level in order to support hardware that may have both regular and high performance interfaces (for example, some hosts may have high-bandwidth connectivity for GPU workloads, and it may be necessary to attach specific networks to these interfaces).

### Goals

We will implement bare metal fulfillment in the O-SAC solution, covering the user stories described above. This implementation will
be first deployed and tested in the MOC; as a result, the implementation will rely upon ESI for bare metal management (although
it will be designed to allow easy replacement of the bare metal management layer). While not addressed in this proposal, a long term goal
of bare metal fulfillment is to have it be used as the basis of bare metal configuration during cluster fulfillment.

### Non-Goals

We will not look into alternatives for ESI; that work will be covered through a future enhancement.

We will not substantially modify the existing cluster fulfillment workflow at this time.

## Proposal

The implementation of bare metal fulfillment relies on three concepts:

* HostPool: A collection of requested bare metal machines (potentially from multiple resource classes), along with their desired network configuration.
* Host: An ephemeral resource created when bare metal resources are acquired from the underlying bare metal management layer. They represent the assignment of a bare metal resource to a HostPool, and provide an endpoint for host-specific operations.
* HostClass: Defines a set of bare metal properties, such as memory, CPU, and network interfaces. Each Host has a single HostClass attribute. HostClasses are defined by the provider.

At a high level, tenants will request a HostPool by specifying:

* the number and HostClass of hosts, as well as any desired filters (for example: "hosts on rack X" or "not host with name Y")
* the network configuration to be applied to those hosts (note that this configuration applies to each individual host in the HostPool)

The O-SAC solution will find available hosts matching the request from the system's inventory, which is managed separately by the cloud provider. O-SAC
will then assign them to the tenant, creating matching Host resources for each host. The tenant can then perform available operations upon the Host.

We expect bare metal fulfillment to follow the same workflow used for cluster fulfillment; as such, we expect to update the
following existing O-SAC components:

* Fulfillment Service: Define the API for HostPools, Hosts, and HostClasses
* Fulfillment CLI: Give the tenant access to the API
* O-SAC Operator: Manage and reconcile the Custom Resources for HostPools and Hosts
* O-SAC AAP: Use Ansible playbooks to perform the requested reconciliation operations of HostPools and Hosts by calling Bare Metal Management APIs.
* Bare Metal Management: Manage the hardware; we will use ESI for now

Much of the development work can simply follow the established patterns set by the cluster fulfillment workflow. However, the
following topics merit further discussion in the "Implementation Details/Notes/Constraints" below:

* ESI playbooks
* Serial console support

### Workflow Description

#### Host Pool Creation

1. The tenant uses the Fulfillment CLI to request a HostPool by specifying the desired number of hosts and resource classes, as well as the desired network configuration.
2. The Fulfillment Service receives the request and creates a new HostPool custom resource (CR) in the appropriate Hub.
3. The O-SAC Operator begins the reconciliation process for the new HostPool CR, finding the requested hosts and creating matching Host CRs, and performing the requested network configuration.
4. The O-SAC Operator monitors the status of the reconciliation process and updates the status of the HostPool CR to reflect the current state.
5. The tenant uses the Fulfillment CLI to check the status of their requested HostPool.

#### Host Pool Network Update

1. The tenant uses the Fulfillment CLI to update the network configuration of a HostPool.
2. The Fulfillment Service receives the request and updates the existing HostPool CR in the appropriate Hub.
3. The O-SAC Operator begins the reconciliation process for the HostPool CR, noting the discrepency between the current network configuration and the desired networking confiuration, and updating the network configuration of the hosts.
4. The O-SAC Operator monitors the status of the reconciliation process and updates the status of the HostPool CR to reflect the current state.
5. The tenant uses the Fulfillment CLI to check the status of the HostPool.

#### Host Pool Expansion

1. The tenant uses the Fulfillment CLI to increase the number of requested hosts specified in a HostPool, updating any desired filters.
2. The Fulfillment Service receives the request and updates the existing HostPool CR in the appropriate Hub.
3. The O-SAC Operator begins the reconciliation process for the HostPool CR, noting the discrepency between the current host count and the desired host count, and adding the requested hosts.
4. The O-SAC Operator monitors the status of the reconciliation process and updates the status of the HostPool CR to reflect the current state.
5. The tenant uses the Fulfillment CLI to check the status of the HostPool.

#### Host Pool Reduction

1. The tenant uses the Fulfillment CLI to decrease the number of requested hosts specified in a HostPool; they also optionally mark specific hosts for removal (this is detailed further below).
2. The Fulfillment Service receives the request and updates the existing HostPool CR in the appropriate Hub.
3. The O-SAC Operator begins the reconciliation process for the HostPool CR, noting the discrepency between the current host count and the desired host count, and removing the requested hosts.
4. The O-SAC Operator monitors the status of the reconciliation process and updates the status of the HostPool CR to reflect the current state.
5. The tenant uses the Fulfillment CLI to check the status of the HostPool.

#### Host Operations

1. The tenant uses the Fulfillment CLI to view their Hosts.
2. The tenant uses the Fulfillment CLI to perform available operations upon the desired Host. Initially, these actions will be limited to power control; additional actions (such as console enablement) may be added later.
3. The Fulfillment Service receives the request and updates the existing Host CR in the appropriate Hub.
3. The O-SAC Operator begins the reconciliation process for the Host CR, noting any discrepency between the current state and the desired state, and calling the bare metal service to perform any needed host operations.
4. The O-SAC Operator monitors the status of the reconciliation process and updates the status of the Host CR to reflect the current state.
5. The tenant uses the Fulfillment CLI to check the status of the Host.

#### Host Pool Deletion

1. The tenant uses the Fulfillment CLI to delete a HostPool.
2. The Fulfillment Service receives the request and deletes the existing HostPool CR in the appropriate Hub.
3. The deletion of the HostPool CR triggers cascading deletes of associated Hosts.
4. The O-SAC Operator detects these deletions and calls the bare metal service to clean these hosts.

### API Extensions

#### HostPools

A tenant requests bare metal resources by creating a HostPool with a desired specification. Once created, O-SAC
will repeatedly attempt to fulfill the request until the state of the HostPool matches its specification. Tenants
can update a HostPool specification, and the same reconciliation process will perform the needed operations to change
the state of the HostPool.

In the following example, the tenant uses the Fulfillment CLI to request a HostPool with two fc430 hosts and one h100.
Each host will have `network1` attached as a native VLAN on one physical interface; and a trunk port with `network2` as a native
VLAN and `network3` as a tagged VLAN on a second physical interface. It is assumed that the tenant will have knowledge of their
available networks from a separate O-SAC network service (whose implementation is outside the scope of this proposal).

    $ ./fulfillment-cli create hostpool \
           --host-set workers=host_class:fc430,size:2 \
           --host-set gpus=host_class:h100,size:1 \
           --network-attachments primary:network1 \
           --network-attachments primary:network2,vlans:network3

The Fulfillment CLI sends this JSON request to the Fulfillment Service:

    {
      "object": {
        "spec": {
          "host_sets": {
            "workers": {
              "resource_class": "fc430",
              "replicas": 2
            },
            "gpus": {
              "resource_class": "h100",
              "replicas": 1
            }
          },
          "network_attachments": [
            {
              "primary": "network1"
            },
            {
              "primary": "network2",
              "vlans": ["network3"]
            },
          ]
        }
      }
    }

The Fulfillment Service creates the following HostPool CR:

    apiVersion: o-sac.openshift.io/v1alpha1
    kind: HostPool
    metadata:
      name: examplehostpool
    spec:
      hostSets:
        workers:
          resourceClass: fc430
          replicas: 2
        gpus
          resourceClass: h100
          replicas: 1
      selector:
        matchLabels:
          hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40

      # The networkAttachments section controls how networks are connected to
      # physical interfaces.
      networkAttachments:
      # This configuration will match any available interface.
      - primary: network1
      - primary: network2
        vlans:
        - network3

Note that the selector values are supplied by the Fulfillment Service; these values are used to label the
created Hosts without any input needed from the tenant.

If the tenant wishes to specify host properties, they can filter hosts by specifying hostSelectors that use standard
Kubernetes `matchLabel` and `matchExpression` syntax; for example, this HostPool CR requires that the fc430 hosts be
located on rack R2, but not in cabinet C2:

    apiVersion: o-sac.openshift.io/v1alpha1
    kind: HostPool
    metadata:
      name: examplehostpool
    spec:
      hostSets:
        workers:
          resourceClass: fc430
          replicas: 2
          hostSelectors:
            matchLabels:
              row: R2
            matchExpressions:
            - op: NotIn
              key: cabinet
              values: ["C2"]
        gpus:
          resourceClass: h100
          replicas: 1
      selector:
        matchLabels:
          hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40

      # The networkAttachments section controls how networks are connected to
      # physical interfaces.
      networkAttachments:
      # This configuration will match any available interface.
      - primary: network1
      - primary: network2
        vlans:
        - network3

Note that initially, information regarding valid key/value pairs will have to be provided out-of-band by the
cloud provider. A later enhancement may allow O-SAC to provide this information through an API.

If the tenant wishes to remove a host from their HostPool, then they will update their HostPool specification to reduce
the number of Hosts of a resource class, resulting in the following CR. The reconciliation process will remove an arbitrary
Host of that resource class from the HostPool:

    apiVersion: o-sac.openshift.io/v1alpha1
    kind: HostPool
    metadata:
      name: examplehostpool
    spec:
      hostSets:
        workers:
          resourceClass: fc430
          replicas: 1
        gpus:
          resourceClass: h100
          replicas: 1
      selector:
        matchLabels:
          hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40

      # The networkAttachments section controls how networks are connected to
      # physical interfaces.
      networkAttachments:
      # This configuration will match any available interface.
      - primary: network1
      - primary: network2
        vlans:
        - network3

If the tenant wishes to remove a specific host from their HostPool, then they will first mark a Host for removal
using an O-SAC API that annotates the Host with a marker for deletion before reducing the number of Hosts within a HostPool.
The reconciliation process will favor removing Hosts with that annotation.

If a tenant wishes to remove a specific host and prevent it from ever being re-added to the HostPool, they can add
a host selector that excludes a particular host by name. Note that this also allows for a tenant to replace a host by keeping the
number of hosts constant while also excluding the unwanted host.

    apiVersion: o-sac.openshift.io/v1alpha1
    kind: HostPool
    metadata:
      name: examplehostpool
    spec:
      hostSets:
        workers:
          resourceClass: fc430
          replicas: 1
          hostSelectors:
            matchExpressions:
            - op: NotIn
              key: hostName
              values: ["examplehost"]
        gpus:
          resourceClass: h100
          replicas: 1
      selector:
        matchLabels:
          hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40

      # The networkAttachments section controls how networks are connected to
      # physical interfaces.
      networkAttachments:
      # This configuration will match any available interface.
      - primary: network1
      - primary: network2
        vlans:
        - network3

Tenants can also attach networks to interfaces matching a specific property. In this example,
each fc430 will be configured with `network1` attached to any available physical interface,
while `storage-network` will only be attached to an interface with the `25gb` property.

    apiVersion: o-sac.openshift.io/v1alpha1
    kind: HostPool
    metadata:
      name: example
    spec:
      hostSets:
        workers:
          resourceClass: fc430
          replicas: 2
        gpus:
          resourceClass: h100
          replicas: 1
      selector:
        matchLabels:
          hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40

      # The networkAttachments section controls how networks are connected to
      # physical interfaces.
      networkAttachments:
      # This configuration will match any available interface.
      - primary: network1
      # This configuration will only match interfaces with the `25gb` property
      - matches:
            property: 25gb
        primary: storage-network

#### Hosts

Tenants do not create Hosts directly; instead, they are created as part of the HostPool fulfillment workflow, resulting in a Host CR.
For example:

    apiVersion: cloudkit.openshift.io/v1alpha1
    kind: Host
    metadata:
      name: examplehost
      ownerReferences:
      - apiVersion: o-sac.openshift.io/v1alpha1
        blockOwnerDeletion: true
        controller: true
        kind: HostPool
        name: examplehostpool
        uid: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
      labels:
        hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
    spec:
      powerState: PowerOff
      serialConsole: Enabled
    status:
      powerState: PowerOff
      serialConsole: Enabled
      name: examplehost
      properties:
        cpus: 512
        memory_mb: 1572864
        accelerators:
        - "NVIDIA Corporation GH100"

The listed properties will depend upon the attributes returned by the underlying bare metal management service.

Note that each Host has an ownerReferences entry to the parent HostPool; this will enable both cascading resource deletion, while
also preventing the parent HostPool from being deleted until its child Hosts are deleted.

Once created, tenants can use the Fulfillment CLI to perform various operations against the host:

* Power control
* Serial console access
* Inventory information

A Hosts API will support these operations. For example, the tenant can edit the Host spec to change the power state, resulting
in the following Host CR:

    apiVersion: cloudkit.openshift.io/v1alpha1
    kind: Host
    metadata:
      name: examplehost
      ownerReferences:
      - apiVersion: o-sac.openshift.io/v1alpha1
        blockOwnerDeletion: true
        controller: true
        kind: HostPool
        name: examplehostpool
        uid: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
      labels:
        hostPoolUID: 66b8ed6f-1af2-4892-ac12-47bd47dacd40
    spec:
      powerState: PowerOn
      serialConsole: Enabled
    status:
      powerState: PowerOff
      serialConsole: Enabled
      name: examplehost
      properties:
        cpus: 512
        memory_mb: 1572864
        accelerators:
        - "NVIDIA Corporation GH100"

The O-SAC Operator will detect the difference in powerState between the spec and the status, and call the bare metal service
to power the host on before updating the Host's status to PowerOn.

### Implementation Details/Notes/Constraints

#### ESI Playbooks

The ESI API supports all of the needed bare metal functionality (the cluster fulfillment workflow already relies upon ESI
playbooks for bare metal network configuration) . However, it is important to recognize that O-SAC will not use the ESI concept
of tenancy; from an ESI perspective, hosts will always remain leased to the O-SAC project. As a result, we will need to introduce
a new method of keeping track of O-SAC tenancy.

One solution would be to rely upon Ironic’s extra field, which allows an ESI project to set arbitrary key/value pairs upon a
specified host. Doing so would not be difficult; it simply creates additional considerations when implementing playbooks related
to host assignment and unassignment.

#### Serial Console Support

We would like to implement a solution for serial console access that can be utilized by both the bare metal service and the virtual machine service.
We will propose a design for that solution in a future enhancement proposal.

#### Task Groupings

We can perform this implementation in smaller steps:

* HostPool and Host
  * Tenants can create/update/delete HostPools
  * No network attachments
  * Hosts are created when a HostPool is fulfilled
  * Tenants can view their Hosts
  * Tenants have power control on their Hosts
* Implement HostPool hostSelectors
  * filter by name (to support removal of specific hosts from a HostPool)
  * filter by rack
  * affinity/anti-affinity
* Network Attachments
  * Tenants can specify network attachments when creating/updating HostPools
  * Requires network service
* Serial Console
  * Tenants can enable/disable serial console on a Host

### Risks and Mitigations

How do we prevent a tenant from performing unauthorized bare metal operations? The first layer of protection
is the fact that the tenant never has direct access to the underlying bare metal management service; they
only have access to the fulfillment service and the limited operations provided by the fulfillment API.
Naturally, that API will need strong multi-tenancy support in order to prevent a tenant from accessing
resources allocated to a different tenant; that feature is being implemented outside of this proposal.

### Drawbacks

??

## Alternatives (Not Implemented)

* One alternative would be to focus on an ESI replacement before developing the bare metal fulfillment functionality. However, we anticipate that the MOC will continue to use ESI for now; for that reason, it makes sense to perform this implementation with ESI in mind, and simply make it easy to replace ESI if/when needed. Note that it is also possible that we will continue to use ESI if the issues pushing us towards a replacement are resolved.
* We could limit a HostPool to hosts from a single resource class; a tenant in need of hosts from multiple resource classes would simply create multiple HostPools. However allowing multiple resource classes in HostPool does provide additional conveniences. For example, cluster fulfillment allows for OpenShift clusters with mixed resource classes; if we move that workflow towards using HostPools for bare metal configuration, then associating that cluster with a single HostPool allows for far easier bare metal tracking and management.

## Open Questions [optional]

* Can we manage network attachment by MAC address?
* Do we allow a network to be attached multiple times to a host (on different interfaces)?

## Test Plan

TBD

## Graduation Criteria

TBD

### Removing a deprecated feature

TBD

## Upgrade / Downgrade Strategy

TBD

## Version Skew Strategy

TBD

## Support Procedures

TBD

## Infrastructure Needed [optional]

None
