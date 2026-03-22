---
title: dns-api
authors:
  - dmanor
creation-date: 2026-03-17
last-updated: 2026-03-22
tracking-link:
  - TBD
see-also:
  - "/enhancements/networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# DNS API

## Summary

OSAC currently hardcodes AWS Route 53 as the DNS backend for managing DNS
records during cluster provisioning (CaaS). This enhancement introduces a
pluggable internal DNS API that abstracts DNS record management behind a
class-agnostic interface. Deployers of OSAC will be able to use any
supported DNS backend (AWS Route 53, Cloudflare, Azure DNS, Google Cloud DNS,
etc.) by selecting a DNS class and supplying the appropriate
credentials, without modifying the core provisioning logic.

## Motivation

OSAC's Cluster-as-a-Service provisioning creates DNS records for each managed
cluster (API endpoint, API-internal endpoint, and wildcard ingress). A pluggable
DNS layer will make OSAC deployable in environments that use any DNS backend,
whether a commercial DNS service (such as AWS Route 53, Cloudflare, or Azure
DNS), a self-hosted DNS server using the RFC 2136 protocol (such as BIND or
PowerDNS), or any other provider. This abstraction also establishes a pattern
that future OSAC services (VMaaS, BareMetal-as-a-Service) can reuse when they
need DNS record management.

### User Stories

- As an OSAC deployer using a commercial DNS service (such as Route 53 or
  Cloudflare DNS), I want to configure OSAC to create DNS records via my
  provider's API so that I can use my existing DNS infrastructure.

- As an OSAC deployer using a self-hosted DNS server (such as BIND or
  PowerDNS), I want to configure OSAC to manage DNS records via the RFC 2136
  protocol so that records are resolvable within my private network.

- As an OSAC template developer, I want a simple, generic interface for
  creating and deleting DNS records so that I do not need to write
  backend-specific logic in my templates.

- As an OSAC platform operator, I want to manage DNS provider credentials
  through standard Kubernetes/OpenShift credential mechanisms (e.g., Secrets)
  so that secrets are handled consistently and securely.

### Goals

- Introduce a generic DNS role (`osac.service.dns`) in the `osac.service`
  Ansible collection that supports creating and deleting DNS records.
- Implement an initial set of DNS providers: AWS Route 53 (existing behavior),
  RFC 2136 (for self-hosted DNS servers like BIND or PowerDNS), and additional
  providers as needed (e.g., Cloudflare or Azure DNS).
- Refactor all roles that currently call `amazon.aws.route53` directly
  to use the new DNS abstraction.
- Allow deployers to select their DNS provider via configuration
  (group_vars/extra vars) without modifying roles or playbooks.

### Non-Goals

- Providing a user-facing DNS API through the Fulfillment Service or CLI.
  This enhancement is scoped to the internal Ansible automation layer.
- Managing DNS zones or delegations. The DNS API only manages individual
  records within an existing zone.
- Supporting DNS record types beyond A and AAAA records. CNAME and other
  record types may be added later as needed.
- Replacing the `wait_for_dns` role. DNS propagation verification remains
  class-agnostic (uses `dig`) and does not need changes.

## Proposal

This proposal introduces a new Ansible role `osac.service.dns` that provides a
uniform interface for DNS record management. The role dispatches to
class-specific implementations based on a configurable `dns_class` variable,
following the same pattern as NetworkClass in the Networking API. Each DNS class
implementation is a separate task file within the role.

All roles that currently manage DNS records will call `osac.service.dns` instead of directly invoking
backend-specific modules.

### Workflow Description

**OSAC deployer** is the person deploying and configuring the OSAC platform.

**OSAC template developer** is a developer creating or modifying Ansible
templates for cluster or VM provisioning.

#### Deployer Configures DNS Class

1. The deployer sets `dns_class` in their environment's group_vars or extra
   vars (e.g., `dns_class: route53`).
2. The deployer provides class-specific configuration variables. Each class
   manages its own backend-specific details (e.g., zone, credentials) so that
   callers of the DNS role don't need to know about them.
3. The deployer provides credentials through standard Kubernetes/OpenShift
   mechanisms (e.g., Secrets), which are then made available to the automation
   layer.

#### Cluster Provisioning Creates DNS Records

1. The external access role determines the DNS records needed (API,
   API-internal, wildcard ingress).
2. Instead of calling `amazon.aws.route53` directly, it includes the
   `osac.service.dns` role with `dns_state: present` and the record details.
3. The `osac.service.dns` role reads `dns_class` and dispatches to the
   appropriate class task file (e.g., `class_route53.yaml`,
   `class_cloudflare.yaml`).
4. The class task file creates the DNS record using the appropriate Ansible
   module.
5. The existing `wait_for_dns` role verifies DNS propagation (unchanged).

#### Cluster Deletion Removes DNS Records

1. The external access role's destroy tasks include the `osac.service.dns`
   role with `dns_state: absent` and the record names.
2. The DNS role dispatches to the appropriate class and deletes the records.

### API Extensions

This enhancement does not introduce new CRDs or modify the Fulfillment API. It
is scoped to the internal Ansible automation layer.

### Implementation Details/Notes/Constraints

#### New Role: `osac.service.dns`

The `osac.service.dns` role will live in the `osac.service` Ansible collection
at:

```
collections/ansible_collections/osac/service/roles/dns/
  meta/
    argument_specs.yaml
  defaults/
    main.yaml
  tasks/
    main.yaml
    create.yaml
    delete.yaml
    class_route53.yaml
    class_cloudflare.yaml
    class_rfc2136.yaml
```

#### Role Interface (argument_specs)

```yaml
argument_specs:
  create:
    short_description: Create a DNS record
    options:
      dns_class:
        type: str
        required: true
        description: >
          DNS class. Determines which backend module is used, following
          the same pattern as NetworkClass in the Networking API.
        choices:
          - route53
          - cloudflare
          - rfc2136
      dns_record_name:
        type: str
        required: true
        description: Fully qualified domain name for the record.
      dns_record_type:
        type: str
        required: true
        default: A
        choices: [A, AAAA]
        description: >
          DNS record type. A for IPv4 addresses, AAAA for IPv6 addresses.
      dns_record_value:
        type: str
        required: true
        description: >
          The value for the record (e.g., an IPv4 address for A records,
          an IPv6 address for AAAA records).
      dns_record_ttl:
        type: int
        default: 1800
        description: TTL in seconds.
      dns_record_overwrite:
        type: bool
        default: true
        description: Whether to overwrite an existing record.
  delete:
    short_description: Delete a DNS record
    options:
      dns_class:
        type: str
        required: true
        choices:
          - route53
          - cloudflare
          - rfc2136
      dns_record_name:
        type: str
        required: true
      dns_record_type:
        type: str
        required: true
        default: A
        choices: [A, AAAA]
```

#### DNS Class Dispatch (tasks/create.yaml)

```yaml
---
- name: Create DNS record via {{ dns_class }}
  ansible.builtin.include_tasks:
    file: "class_{{ dns_class }}.yaml"
  vars:
    _dns_action: present
```

#### DNS Class Dispatch (tasks/delete.yaml)

```yaml
---
- name: Delete DNS record via {{ dns_class }}
  ansible.builtin.include_tasks:
    file: "class_{{ dns_class }}.yaml"
  vars:
    _dns_action: absent
```

#### Route 53 Class (tasks/class_route53.yaml)

```yaml
---
- name: "{{ _dns_action }} DNS record {{ dns_record_name }} via Route 53"
  amazon.aws.route53:
    state: "{{ _dns_action }}"
    zone: "{{ dns_route53_zone }}"
    record: "{{ dns_record_name }}"
    type: "{{ dns_record_type }}"
    ttl: "{{ dns_record_ttl | default(1800) }}"
    value: "{{ dns_record_value | default(omit) }}"
    wait: true
    overwrite: "{{ dns_record_overwrite | default(true) }}"
```

#### Cloudflare Class (tasks/class_cloudflare.yaml)

```yaml
---
- name: "{{ _dns_action }} DNS record {{ dns_record_name }} via Cloudflare"
  community.general.cloudflare_dns:
    state: "{{ _dns_action }}"
    zone: "{{ dns_cloudflare_zone }}"
    record: "{{ dns_record_name }}"
    type: "{{ dns_record_type }}"
    value: "{{ dns_record_value | default(omit) }}"
    ttl: "{{ dns_record_ttl | default(1) }}"
    api_token: "{{ dns_cloudflare_api_token }}"
    solo: "{{ dns_record_overwrite | default(true) }}"
```

#### RFC 2136 Class (tasks/class_rfc2136.yaml)

```yaml
---
- name: "{{ _dns_action }} DNS record {{ dns_record_name }} via RFC 2136"
  community.general.nsupdate:
    state: "{{ _dns_action }}"
    server: "{{ dns_rfc2136_server }}"
    port: "{{ dns_rfc2136_port | default(53) }}"
    zone: "{{ dns_rfc2136_zone }}"
    record: "{{ dns_record_name }}"
    type: "{{ dns_record_type }}"
    ttl: "{{ dns_record_ttl | default(1800) }}"
    value: "{{ dns_record_value | default(omit) }}"
    key_name: "{{ dns_rfc2136_key_name }}"
    key_secret: "{{ dns_rfc2136_key_secret }}"
    key_algorithm: "{{ dns_rfc2136_key_algorithm | default('hmac-sha256') }}"
```

#### Refactored external access roles (create example)

The current DNS tasks in the relevant roles
follow the same pattern. example:

```yaml
# Before (hardcoded Route 53):
- name: Create dns records
  amazon.aws.route53:
    state: present
    zone: "{{ external_access_base_domain }}"
    record: "{{ item.name }}"
    type: A
    ttl: "{{ external_access_dns_ttl }}"
    value: "{{ item.addr | regex_replace('/.*$', '') }}"
    wait: true
    overwrite: true
  loop:
    - name: "{{ external_access_api_domain }}"
      addr: "{{ external_access_api_floating_ip }}"
    - name: "{{ external_access_api_int_domain }}"
      addr: "{{ external_access_api_floating_ip }}"
    - name: "*.{{ external_access_ingress_domain }}"
      addr: "{{ netris_l4lb_ingress_ip }}"
```

Would become:

```yaml
# After (class-agnostic):
- name: Create dns records
  ansible.builtin.include_role:
    name: osac.service.dns
    tasks_from: create
  vars:
    dns_record_name: "{{ item.name }}"
    dns_record_type: A
    dns_record_ttl: "{{ external_access_dns_ttl }}"
    dns_record_value: "{{ item.addr | regex_replace('/.*$', '') }}"
  loop:
    - name: "{{ external_access_api_domain }}"
      addr: "{{ external_access_api_floating_ip }}"
    - name: "{{ external_access_api_int_domain }}"
      addr: "{{ external_access_api_floating_ip }}"
    - name: "*.{{ external_access_ingress_domain }}"
      addr: "{{ netris_l4lb_ingress_ip }}"
```

#### Refactored external access roles (destroy example)

Similarly, the delete tasks in both roles would change from:

```yaml
# Before:
- name: Delete dns records
  amazon.aws.route53:
    state: absent
    zone: "{{ external_access_base_domain }}"
    record: "{{ item }}"
    type: A
    wait: true
  loop:
    - "api.{{ external_access_name }}.{{ external_access_base_domain }}"
    - "api-int.{{ external_access_name }}.{{ external_access_base_domain }}"
    - "*.apps.{{ external_access_name }}.{{ external_access_base_domain }}"
```

To:

```yaml
# After:
- name: Delete dns records
  ansible.builtin.include_role:
    name: osac.service.dns
    tasks_from: delete
  vars:
    dns_record_name: "{{ item }}"
    dns_record_type: A
  loop:
    - "api.{{ external_access_name }}.{{ external_access_base_domain }}"
    - "api-int.{{ external_access_name }}.{{ external_access_base_domain }}"
    - "*.apps.{{ external_access_name }}.{{ external_access_base_domain }}"
```

#### Configuration (group_vars)

Deployers configure their DNS class in group_vars:

```yaml
# group_vars/all/dns.yaml

# DNS class selection
dns_class: route53  # or: cloudflare

# Route 53 class-specific configuration
# dns_route53_zone: "example.com"
# (uses AWS credentials from environment/AAP credential)

# Cloudflare class-specific configuration
# dns_cloudflare_zone: "example.com"
# dns_cloudflare_api_token: "{{ vault_cloudflare_api_token }}"

# RFC 2136 class-specific configuration
# dns_rfc2136_server: "ns1.example.com"
# dns_rfc2136_port: 53
# dns_rfc2136_zone: "example.com"
# dns_rfc2136_key_name: "osac-update-key"
# dns_rfc2136_key_secret: "{{ vault_rfc2136_key_secret }}"
# dns_rfc2136_key_algorithm: "hmac-sha256"
```

#### Adding a New DNS Class

To add support for a new DNS class (e.g., Azure DNS):

1. Create `tasks/class_azure_dns.yaml` in the `osac.service.dns` role.
2. Implement the create/delete logic using the appropriate Ansible module
   (e.g., `azure.azcollection.azure_rm_dnsrecordset`).
3. Add the class name to the `dns_class` choices in `argument_specs.yaml`.
4. Add any required class-specific variables to the argument spec and
   document them.
5. Add the required Ansible collection to `collections/requirements.yml` if not
   already present.

#### Collection Dependencies

Each DNS class may require its own Ansible collection:

| DNS Class  | Ansible Collection       | Already Vendored |
|------------|--------------------------|------------------|
| route53    | `amazon.aws`             | Yes              |
| cloudflare | `community.general`      | Yes              |
| rfc2136    | `community.general`      | Yes              |
| azure_dns  | `azure.azcollection`     | No               |
| gcp_dns    | `google.cloud`           | No               |

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Class module API differences | Different modules have different parameters and behaviors (e.g., Cloudflare uses `solo` vs Route 53 uses `overwrite`) | Abstract differences inside each class task file; expose only the common interface |
| Credential management varies per provider | Each DNS provider uses different authentication mechanisms | Document credential setup per provider; manage credentials via Kubernetes Secrets |
| Wildcard record support | Not all DNS backends handle wildcard DNS records identically | Test wildcard record creation/deletion for each supported class before release |
| Breaking existing deployments | Deployers currently using Route 53 implicitly | Default `dns_class` to `route53` so existing deployments work without config changes |

### Drawbacks

- Adds a layer of indirection for DNS operations. Debugging DNS issues now
  requires understanding which DNS class is configured and how the dispatch
  works.
- Each new DNS class requires implementing and maintaining a class task file,
  adding to the maintenance surface.
- Backend-specific features (e.g., Route 53 health checks, Cloudflare
  proxying) are not exposed through the common interface. Deployers who need
  these features would need to extend the class task files.

## Alternatives (Not Implemented)

### Alternative 1: DNS API in the Fulfillment Service

Expose DNS record management as a first-class API in the Fulfillment Service
(similar to the Networking API), with a gRPC/REST interface and CRDs.

**Why not selected**: DNS record management during cluster provisioning is an
infrastructure concern handled entirely within the Ansible automation layer.
Adding it to the Fulfillment Service would introduce unnecessary complexity and
API surface for what is essentially an infrastructure-side operation. This alternative
could be revisited if tenant-facing DNS management becomes a requirement.

### Alternative 2: Ansible Role per DNS Class (no dispatcher)

Instead of a single `osac.service.dns` role with class dispatch, create
separate roles like `osac.service.dns_route53`,
`osac.service.dns_cloudflare`, etc., and have the caller select the role.

**Why not selected**: This pushes class selection to every caller, requiring
template developers to add conditional logic wherever DNS is used. A single
role with internal dispatch keeps the caller interface clean and centralizes
class selection.

## Open Questions

1. Should the DNS role support batch operations (multiple records in a single
   call) for DNS classes that support atomic batch updates, or is per-record
   invocation via `loop` sufficient?

2. Should we define a standard Kubernetes Secret format for each DNS provider,
   or leave credential management to the deployer?

3. Which additional DNS providers should be included in the initial
   implementation beyond Route 53? Cloudflare is proposed as the second
   provider, but Azure DNS or Google Cloud DNS may be higher priority depending
   on the deployment targets.

## Test Plan

*Section not required until targeted at a release.*

- **Unit tests**: Validate DNS class dispatch logic (correct task file included
  based on `dns_class` value; error on unsupported class).
- **Integration tests**: For each supported DNS class, test create and delete
  of A and AAAA records, including wildcard records, against a real DNS zone
  in a CI environment.
- **Migration test**: Verify that existing deployments using Route 53 continue
  to work with `dns_class: route53` (default) without any configuration
  changes.

## Graduation Criteria

*Section not required until targeted at a release.*

- **Dev Preview**: Route 53 DNS class working through the new abstraction;
  relevant roles refactored to use
  `osac.service.dns`.
- **Tech Preview**: At least one additional DNS class implemented and tested;
  documentation for adding new DNS classes.
- **GA**: All supported DNS classes documented and tested; migration guide
  published.

## Upgrade / Downgrade Strategy

- Existing deployments that do not set `dns_class` will default to
  `route53`, preserving current behavior with no changes required.
- Both relevant roles will be updated
  to use the new DNS role. Since this is an internal implementation change, it
  does not affect the external API or CRDs.
- Downgrade: reverting to a previous version of the `osac.service` collection
  restores the hardcoded Route 53 behavior.

## Version Skew Strategy

This enhancement is contained within the `osac.service` Ansible collection and
the `osac-aap` repository. There are no cross-component version skew concerns
since DNS record management is invoked synchronously during playbook execution.

## Support Procedures

- **DNS record creation fails**: Check the `dns_class` value and ensure
  class-specific credentials are configured. Review the Ansible task output
  for class-specific error messages (e.g., invalid API token, zone not found).
- **Unsupported class error**: The DNS role will fail with a clear error
  message if `dns_class` is set to a value that does not have a corresponding
  `class_<name>.yaml` task file.
- **DNS propagation timeout**: The `wait_for_dns` role (unchanged) will report
  which records failed to resolve. This is independent of the DNS class and
  may indicate a backend-side delay or misconfiguration.

## Infrastructure Needed

No new infrastructure is required. Testing may require credentials for each
supported DNS class's API (AWS, Cloudflare, etc.) in the CI environment.
