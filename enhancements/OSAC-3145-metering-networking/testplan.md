# Testplan — OSAC-3145 Networking Metering

## Scope and test locations

Tests use Ginkgo v2 in
`osac-metering/metering-service/internal/{events,watch,reconciliation,projection}`,
`osac-metering/adapters/cmd/m360-adapter`,
`fulfillment-service/internal/servers`, and
`osac-operator/internal/controller`. E2E tests use pytest under
`tests/e2e/`.

Networking metering inherits the [unified networking deployment support
boundary](../OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
these tests cover connected deployments only; air-gapped and disconnected
networking deployments are outside the supported scope.

## Unit tests

- Reject NATGateway in the API oneof and reject invalid common proto imports
  through `buf lint`.
- Reject update masks that target parent output fields.
- Verify exact event predicates, lifecycle transitions, target endpoint rules,
  fixed-point quantities, correction sign/unit validation, gate union/reload
  routing, and total/progress pagination.

## Integration tests

- Verify attachment Ready and Delete transitions update both rows atomically;
  force each DAO failure and verify rollback.
- Exercise VMaaS `auto_external_ip_attachment` create, rollback, pre-Ready,
  and cleanup, plus Cluster, BMaaS, default-networking, manual attachment,
  and NATGateway paths.
- Attach and detach an allocated ExternalIP. Verify old and new dimension
  slices close and open at `attachment_transition_time`, heartbeat replacement
  stays within the active slice, delayed/replayed transitions do not
  double-count, and allocation seconds equal the disjoint slice total.
- Replay lifecycle and heartbeat events through two fresh adapter instances
  and verify one provider record per stable `event_id`.
- Delete ExternalIP/NATGateway, delay feedback, and verify usage closes at
  `metadata.deletion_timestamp`, not feedback time.
- Verify no operator parent writes, non-empty event IDs, correction
  topic/chart/adapter routing, one provider submission per adjustment, shared
  correction/group IDs, unique adjustment/provider keys, durable replay
  no-ops, offset commit ordering, partial-failure retry, NAT dimensions,
  cache failures, correction apply/reverse, concurrent-delete/shift Get
  confirmation, and M360 flat payload routing.

## End-to-end tests

- Exercise unattached ExternalIP, ComputeInstance, Cluster API/Ingress, and
  BareMetal attachments, including detach and cleanup.
- Exercise NATGateway with VirtualNetwork dimensions.
- Verify excluded VirtualNetwork/Subnet/SecurityGroup/NetworkACL billing cases, failures,
  retries, duplicate replay, Kafka/DLQ behavior, gate reload/disable/re-enable,
  and resource-seconds totals.
