# Clarification Log — OSAC-1644

## Status

- Scope: confirmed
- Open gaps: none
- Exit criteria met: Yes

## Confirmed TLS Trust Scope

### Q1: What is the scope of OSAC-1644?

#### Answer

OSAC-1644 is a TLS-trust feature only. Every OSAC-deployed component that
connects to fulfillment service, including workloads on tenant clusters, must
trust the certificates presented by that service.

#### Decision

Restrict OSAC-1644 to fulfillment-service TLS trust for management- and
tenant-cluster components.

---

### Q2: What must happen on tenant clusters?

#### Answer

Cert-manager is already enabled by the management-cluster installer and the
standard hosted-cluster post-install path creates a cert-manager Subscription.
It is an existing platform prerequisite, not a separate OSAC-1644 outcome.
The missing behavior is making the management-cluster CA that signs the
fulfillment-service certificate available to the trust store used by each
fulfillment-service client on a tenant cluster.

#### Decision

OSAC-1644 delivers TLS trust support only. Cert-manager installation is an
existing prerequisite; the feature acceptance outcome is trusted,
certificate-verified fulfillment-service connectivity.

---

### Q3: Are TLS-verification bypasses allowed?

#### Answer

Production deployments must verify the fulfillment-service certificate and must
not rely on an insecure TLS option or equivalent bypass. Test environments may
use an explicit, isolated override where necessary.

#### Decision

No insecure TLS mode is an accepted production path for a
fulfillment-service connection; test-only overrides are allowed.

---

### Q4: Which identity work is excluded?

#### Answer

The generic API and lifecycle for tenant-scoped Keycloak service accounts is a
separate feature, OSAC-5137. The audit and remediation of Kubernetes
service-account tokens used by fulfillment-service clients is a separate epic.
CSI-specific identity and credential delivery remains separate from this PRD.

#### Decision

Keep identity APIs, Kubernetes service-account remediation, and CSI credential
lifecycle out of OSAC-1644.

---

### Q5: Does the implementation inventory cover CaaS, VMaaS, and BMaaS?

#### Answer

Yes. The shared operator fulfillment-service connection is used by the
cluster-feedback, compute-instance, and bare-metal-instance paths. AAP
template publishing and metering also communicate with fulfillment service,
and tenant CSI is a separate fulfillment-service client.

#### Decision

Treat CaaS, VMaaS, BMaaS, metering, AAP publishing, tenant CSI, and installer
Helm hooks as in-scope fulfillment-service client classes for TLS-trust
analysis and testing.

---

### Q6: What TLS support is already present, and what is missing?

#### Answer

The fulfillment-service certificate and management-cluster CA bundle already
exist. AAP template publishing and metering already use that bundle. The
operator uses insecure gRPC, installer Helm hooks bypass certificate
verification, and tenant CSI lacks management-CA trust configuration.

#### Decision

Cover the remaining TLS trust and verification gaps: CA distribution to tenant
clusters, client consumption of that CA, and removal of production
verification bypasses for fulfillment-service connections.

---

### Q7: What certificate-management baseline does this feature use?

#### Answer

The OSAC installer should install cert-manager and create the management-cluster
CA used by fulfillment service. Supported integration and E2E environments
should provide the same CA setup. OSAC-1644 must distribute that CA certificate
to every fulfillment-service client that needs it, including clients on tenant
clusters, and require those clients to trust the fulfillment-service
certificate. The feature does not require Let's Encrypt or another external CA.

#### Decision

Use the installer-managed CA as the trust source for fulfillment-service
clients. OSAC-1644 covers CA certificate availability and verified client
trust, not certificate-manager rollout or external CA integration.
