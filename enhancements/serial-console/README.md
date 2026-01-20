---
title: serial-console-access
authors:
  - Austin Jamias
creation-date: 2026-01-29
last-updated: 2026-01-29
tracking-link:
  - "innabox/issues#282"
see-also:
  - "/enhancements/bare-metal-fulfillment"
replaces:
  - None
superseded-by:
  - None
---

# Serial Console Access

## Summary

One of the ways to access a bare metal host is through its serial console. The
serial console provides the tenant text-based, out-of-band access to the host
regardless of its operating system and boot status. It is useful for observing
boot logs and troubleshooting lower level failures.

This proposal describes the design for providing unified serial console access
for both bare metal hosts and virtual compute instances.

## Motivation

Serial console access is one of the future features mentioned in the bare metal
fulfillment enhancement proposal. It is also important to abstract the
underlying console access interfaces away from the user for ease of use.

### User Stories

* As a tenant, I want to be able to enable and disable serial console access on
  my hosts and compute instances.
* As a tenant, I want to be able to view the URL to the serial console.
* As a tenant, I want to connect to the serial console URL using socat.

### Goals

We will implement a way for tenants to access serial consoles to their bare
metal hosts and virtual compute instances. It will be a success if the user is:
- able to enable and disable serial console access
- able to retrieve a serial console URL after enabling access
- able to use socat to connect to the serial console
- unable to retrieve and connect to the serial console after disabling access

### Non-Goals

This proposal will not focus on BMC operations such as power management.

## Proposal

At a high level, tenants will be able to manage and connect to the serial
console of their resources by editing its CR and using socat to connect.

The following components would need to be updated to accomplish the goals:
* Serial Console Service: A new service that handles authentication,
  authorization, and proxy connections to actual BMC consoles
* Cloudkit AAP: Updates to the roles responsible for Hosts and ComputeInstances
  for enabling/disabling serial console access.
* Host/ComputeInstance CRDs: Schema updates to include consoleState and
  consoleURL fields.
* Envoy Configuration: Route configuration to forward console connections to
  the new serial console service.
* Authorino Configuration: New authorization configuration to allow specific
  accounts to access the serial console on their resources.

### Workflow Description

#### Enable/Disable Serial Console Access
_This workflow description is similar to the one titled "Host Operations" in
the Bare Metal Fulfillment enhancement proposal._

1. The tenant uses the Fulfillment CLI to edit the resource's CR to enable
   serial console access (e.g. `fulfillment-cli edit Host <host_id>`).
2. The Fulfillment Service receives the request and updates the resource to
   have the console enabled/disabled.
3. The OSAC Operator begins the reconciliation process for the resource,
   calling the update webhook, and having AAP generate a unique URL to access
   the resource's serial console. The URL is stored in an attribute under the
   'status' field.
4. The OSAC Operator monitors the status of the reconciliation process and
   updates the status of the resource to reflect its current serial console
   state.
5. The tenant uses the Fulfillment CLI to check the current state of the
   resource's serial console.

#### View Serial Console Endpoint
1. The tenant uses the Fulfillment CLI to view their Host or Compute Instance
   with the URL under 'status' (e.g. `fulfillment-cli get Host <host_id>`).

#### Connect to the Serial Console
1. The tenant uses the Fulfillment CLI to enable the serial console on the
   resource.
2. The tenant uses the Fulfillment CLI to view the resource's serial console
   endpoint. It may take time for the OSAC Operator to reconcile the state, so
   the tenant would have to poll until the update takes place.
3. The tenant obtains a service account token with appropriate permissions
4. The tenant uses a tool such as `socat` to connect to the endpoint using the
   obtained token.

### API Extensions

Support for serial console access will require the Host and ComputeInstance
CR spec and status to be updated.

The following is what a Host with disabled serial console would look like:
```
apiVersion: cloudkit.openshift.io/v1alpha1
kind: Host
metadata:
  name: examplehost
spec:
  powerState: Off
  consoleState: Disabled
status:
  powerState: Off
  consoleState: Disabled
  consoleURL: ""
  ...
  state: Ready
```

Once the reconciliation is successfully finished. This is what the resource
would look like.
```
apiVersion: cloudkit.openshift.io/v1alpha1
kind: Host
metadata:
  name: examplehost
spec:
  powerState: Off
  consoleState: Enabled
status:
  powerState: Off
  consoleState: Enabled
  consoleURL: "example.host:1234/console/123a456b-789c-123d-456e-789f123a456b789c"
  ...
  state: Ready
```

### Implementation Details/Notes/Constraints

The token used by the fulfillment-cli will be used for establishing the
connection. Because of this, an HTTP request would be sent for auth, and then
the connection can be upgraded to a raw TCP connection for serial data.

**Accessing the Console**
* Assume using `socat`
* Initial connection needs to be HTTP**S**
* Example connection command: `echo -ne "GET /console/${RESOURCE_ID} HTTP/1.1\r\nHost: ${HOST}\r\nAuthorization: Bearer $TOKEN\r\nConnection: Upgrade\r\nUpgrade: console\r\n\r\n" | socat - openssl:${HOST}`

**Serial Console Service**
The serial-console service would have to do the following:
* Receive HTTP request with token and protocol upgrade request
* Extract token to authenticate and authorize access to the resource
* Check if JWT has access to the Host/ComputeInstance via SubjectAccessReview
* Translate resource id to BMC console endpoint
* Send HTTP 101 Switching Protocols response
* Establish bidirectional proxy between client and actual console endpoint

### Risks and Mitigations

TBD

### Drawbacks

N/A

## Alternatives (Not Implemented)

One alternative is to display and connect to the actual serial console endpoint
instead of a proxy, which reduces system complexity. However, this introduces
the need for storing additional credentials for the user to access each
console. This is not simple UX as the user would have to "remember" or
repeatedly query for credentials.

## Open Questions [optional]

1. Is it necessary to go through envoy to establish a connection, or can socat
   immediately go to the serial-console service?
2. This implementation assumes that the serial-console service knows the
   usernames and passwords to access each BMC. Is this allowed?

## Test Plan

N/A

## Graduation Criteria

N/A

### Removing a deprecated feature

N/A

## Upgrade / Downgrade Strategy

N/A

## Version Skew Strategy

N/A

## Support Procedures

N/A

## Infrastructure Needed [optional]

N/A
