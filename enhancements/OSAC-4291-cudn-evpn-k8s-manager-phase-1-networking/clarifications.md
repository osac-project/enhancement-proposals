# CUDN EVPN Design Decisions

The [design](design.md) defines the implementation; the [PRD](prd.md) defines observable outcomes. This table is a decision index, not a separate contract or an implementation-status report.

| Subject | Selected behavior |
|---|---|
| Tenant compatibility | Preserve VirtualNetwork/Subnet APIs, immutable specs, identities and recorded allocations. Fresh activation only; no writes to live legacy networks. |
| Gateway | OVN-Kubernetes serves VM `gateway_ipv4` through CUDN `defaultGatewayIPs` and routes into the IP-VRF. Fabric carries/routes the VRFs; a physical gateway is a BMaaS concern. |
| Identifier handoff | VN create returns `l3_vni`, recorded on VN status; both Subnet tasks receive it. Subnet create returns only `{type, l2_vni}`. |
| Route targets | MAC-VRF `0:<l2_vni>`, IP-VRF `0:<l3_vni>` on both sides; no ASN-based 16-bit VNI restriction. Every supported Fabric pair needs its own validation. |
| Host networking | Installer `osac-infra` `evpn` values configure prerequisites and advertise CUDNs labelled `evpn: "true"`; tenant tasks consume and validate them. |
| Namespace and groups | One VN-owned namespace, one policy per group; groups need no Subnet. Subnet and attachment cleanup retain the namespace and independent groups. |
| Owner claim | VN-keyed CUDN creation claims one owner Subnet by API ID; terminating owners retain the claim; no handover. |
| Policy updates | Non-creating JSON Patch with UID/RV tests; separate rule/membership mutations preserve each other's fields. Missing targets reject stale patches. |
| Unsupported policy | Explicit ICMP rules fail permanently; validate default rules before onboarding. |
| Address stability | Recorded IPAM, explicit infrastructure/exclusions and persistent IPAMClaims; VMaaS/KubeVirt owns VM and claim integration. |
| DNS | Validate the installed OVN DHCP DNS-Service configuration against agreed resolvers; no invented CUDN DNS field or direct OVN database writes. |
| Cleanup | Complete owned removal and no post-success recreation. The missing backend ordering/fencing proof remains a blocker; no retained tombstones or eventual-cleanup exception. |

Platform version qualification, real-pair evidence and the backend deletion proof are the explicit acceptance gates in the design. Later controller-supplied route targets require a separately reviewed API/handoff before replacing the current rule.
