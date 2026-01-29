# Implementation Plan: AAP Integration Abstraction with Feedback

## Context

**Current Architecture:**

1. **User API call** → fulfillment-service gRPC API
2. **fulfillment-service** → Stores ComputeInstance in PostgreSQL database
3. **fulfillment-service reconciler** → Creates Kubernetes ComputeInstance CR in hub cluster
4. **cloudkit-operator** (in hub) → Watches ComputeInstance CRs, triggers webhook to EDA
5. **EDA** → Receives webhook, triggers AAP job template
6. **AAP** → Runs playbook to create VM, updates ComputeInstance CR annotation `cloudkit.openshift.io/reconciled-config-version`
7. **cloudkit-operator** → Reads annotation, marks CR as Ready when `desired == reconciled`
8. **fulfillment-service reconciler** → Observes CR status change, updates database object status

**Problems with current EDA approach:**
- No job completion feedback (only knows job was triggered, not if it succeeded)
- Unreliable job status delivery
- Can't tell if automation failed vs still running
- No progress updates during long-running jobs

**Goal:** Create abstraction layer allowing both "AAP with EDA" and "AAP without EDA" implementations, with proper feedback mechanisms for job status, completion, and failure.

## Architecture

### Abstraction Layer Design

Create a **ProvisioningProvider** interface that encapsulates the "trigger automation and get feedback" pattern:

```go
// ProvisioningProvider abstracts the mechanism for triggering infrastructure automation
type ProvisioningProvider interface {
    // TriggerProvision starts provisioning for a resource
    // Returns a job ID that can be used to track status
    TriggerProvision(ctx context.Context, resource ProvisioningResource) (jobID string, err error)

    // GetProvisionStatus checks the status of a provisioning job
    // Returns current status and whether the job is complete
    GetProvisionStatus(ctx context.Context, jobID string) (ProvisionStatus, error)

    // TriggerDeprovision starts deprovisioning for a resource
    TriggerDeprovision(ctx context.Context, resource ProvisioningResource) (jobID string, err error)

    // GetDeprovisionStatus checks the status of a deprovisioning job
    GetDeprovisionStatus(ctx context.Context, jobID string) (ProvisionStatus, error)

    // Name returns the provider name for logging
    Name() string
}

type ProvisioningResource interface {
    GetName() string
    GetNamespace() string
    GetDesiredConfigVersion() string
    // Add other methods as needed
}

type ProvisionStatus struct {
    JobID      string
    State      JobState  // Pending, Running, Succeeded, Failed
    Message    string    // Human-readable status message
    Progress   int       // 0-100 percentage (optional)
    StartTime  time.Time
    EndTime    time.Time

    // For successful jobs
    ReconciledVersion string  // The config version that was successfully applied

    // For failed jobs
    ErrorDetails string
}

type JobState string
const (
    JobStatePending   JobState = "Pending"
    JobStateRunning   JobState = "Running"
    JobStateSucceeded JobState = "Succeeded"
    JobStateFailed    JobState = "Failed"
)
```

### Implementation 1: EDA Provider (existing behavior)

```go
type EDAProvider struct {
    webhookClient *WebhookClient
    createURL     string
    deleteURL     string
}

func (p *EDAProvider) TriggerProvision(ctx context.Context, resource ProvisioningResource) (string, error) {
    // Current webhook-based approach
    // EDA handles the actual job triggering
    // JobID is the resource name (since we don't get a real job ID from EDA)
    _, err := p.webhookClient.TriggerWebhook(ctx, p.createURL, resource)
    return resource.GetName(), err
}

func (p *EDAProvider) GetProvisionStatus(ctx context.Context, jobID string) (ProvisionStatus, error) {
    // EDA doesn't provide status polling
    // We rely on the annotation being set by AAP
    // This returns "unknown" and the reconciler must check the CR annotation
    return ProvisionStatus{
        JobID: jobID,
        State: JobStateRunning,  // Assume running until annotation appears
    }, nil
}
```

### Implementation 2: AAP Direct Provider (new, without EDA)

```go
type AAPDirectProvider struct {
    aapClient     *AAPClient  // New AAP API client
    aapBaseURL    string
    aapToken      string
    templateName  string  // AAP job template name
}

func (p *AAPDirectProvider) TriggerProvision(ctx context.Context, resource ProvisioningResource) (string, error) {
    // Call AAP API directly to launch job template
    // POST /api/v2/job_templates/{id}/launch/
    jobLaunchResp, err := p.aapClient.LaunchJobTemplate(ctx, LaunchRequest{
        TemplateName: p.templateName,
        ExtraVars: map[string]interface{}{
            "compute_instance": resource,
            "compute_instance_name": resource.GetName(),
        },
    })

    if err != nil {
        return "", fmt.Errorf("failed to launch AAP job: %w", err)
    }

    return jobLaunchResp.JobID, nil
}

func (p *AAPDirectProvider) GetProvisionStatus(ctx context.Context, jobID string) (ProvisionStatus, error) {
    // Poll AAP API for job status
    // GET /api/v2/jobs/{job_id}/
    job, err := p.aapClient.GetJob(ctx, jobID)
    if err != nil {
        return ProvisionStatus{}, fmt.Errorf("failed to get job status: %w", err)
    }

    status := ProvisionStatus{
        JobID:     jobID,
        Message:   job.ResultTraceback,
        StartTime: job.Started,
        EndTime:   job.Finished,
    }

    // Map AAP status to our JobState
    switch job.Status {
    case "pending", "waiting":
        status.State = JobStatePending
    case "running":
        status.State = JobStateRunning
    case "successful":
        status.State = JobStateSucceeded
        // Extract reconciled version from job artifacts or set it
        status.ReconciledVersion = job.ExtraVars["desired_config_version"]
    case "failed", "error", "canceled":
        status.State = JobStateFailed
        status.ErrorDetails = job.ResultTraceback
    }

    return status, nil
}
```

### AAP API Client

Create new Go client for AAP REST API:

```go
// cloudkit-operator/internal/aap/client.go

type AAPClient struct {
    baseURL    string
    httpClient *http.Client
    token      string
}

type LaunchRequest struct {
    TemplateName string
    ExtraVars    map[string]interface{}
}

type LaunchResponse struct {
    JobID string `json:"id"`
}

type Job struct {
    ID              string                 `json:"id"`
    Status          string                 `json:"status"`
    Started         time.Time              `json:"started"`
    Finished        time.Time              `json:"finished"`
    ExtraVars       map[string]interface{} `json:"extra_vars"`
    ResultTraceback string                 `json:"result_traceback"`
}

func (c *AAPClient) LaunchJobTemplate(ctx context.Context, req LaunchRequest) (*LaunchResponse, error) {
    // POST to /api/v2/job_templates/{template_name}/launch/
}

func (c *AAPClient) GetJob(ctx context.Context, jobID string) (*Job, error) {
    // GET /api/v2/jobs/{jobID}/
}
```

## Critical Files to Modify

### 1. Create Abstraction Interface
**File:** `cloudkit-operator/internal/provisioning/provider.go` (new)
- Define `ProvisioningProvider` interface
- Define `ProvisionStatus`, `JobState` types
- Define `ProvisioningResource` interface

### 2. Create EDA Provider Implementation
**File:** `cloudkit-operator/internal/provisioning/eda_provider.go` (new)
- Implement `EDAProvider` struct
- Wrap existing webhook-based approach
- Maintain backward compatibility

### 3. Create AAP Direct Provider Implementation
**File:** `cloudkit-operator/internal/provisioning/aap_direct_provider.go` (new)
- Implement `AAPDirectProvider` struct
- Direct AAP API integration
- Job polling logic

### 4. Create AAP API Client
**File:** `cloudkit-operator/internal/aap/client.go` (new)
- HTTP client for AAP REST API
- Methods: LaunchJobTemplate, GetJob, GetJobEvents (for progress)
- Authentication with token

### 5. Update ComputeInstance Reconciler
**File:** `cloudkit-operator/internal/controller/computeinstance_controller.go`
- Replace `WebhookClient` with `ProvisioningProvider`
- Update `handleUpdate` to use provider abstraction
- Add job tracking in CR status
- Poll for job status if provider supports it
- Handle job failures explicitly

### 6. Update ComputeInstance CRD
**File:** `cloudkit-operator/api/v1alpha1/computeinstance_types.go`
- Add `ProvisionJobID` to status
- Add `ProvisionJobStatus` to status
- Add `LastProvisionError` to status

### 7. Configuration
**File:** `cloudkit-operator/cmd/main.go`
- Add flags for provider selection: `--provisioning-provider` (eda|aap-direct)
- Add flags for AAP config: `--aap-url`, `--aap-token-file`, `--aap-template-name`
- Initialize correct provider based on flags

### 8. Update Helm Chart
**File:** `cloudkit-operator/config/manager/manager.yaml`
- Add environment variables for provider configuration
- Add secret for AAP token

## Implementation Steps

### Phase 1: Create Abstraction Layer
1. Define `ProvisioningProvider` interface in new file
2. Define supporting types (`ProvisionStatus`, `JobState`, etc.)
3. Create unit tests for interface contract

### Phase 2: Implement EDA Provider (backward compatibility)
1. Create `EDAProvider` wrapping existing webhook logic
2. Move webhook code into provider
3. Implement all interface methods
4. Write unit tests

### Phase 3: Create AAP API Client
1. Implement HTTP client for AAP REST API
2. Add authentication (token-based)
3. Implement job launch endpoint
4. Implement job status endpoint
5. Write unit tests with mocked HTTP responses

### Phase 4: Implement AAP Direct Provider
1. Create `AAPDirectProvider` using AAP client
2. Implement job triggering via API
3. Implement status polling
4. Handle job failures and error reporting
5. Write unit tests

### Phase 5: Update ComputeInstance Reconciler
1. Replace `WebhookClient` field with `ProvisioningProvider`
2. Update `handleUpdate`:
   - Trigger provision via provider
   - Store job ID in CR status
   - Poll for status if not EDA provider
   - Update reconciled version when job succeeds
   - Handle failures explicitly
3. Add requeueing logic for active jobs
4. Write integration tests

### Phase 6: Update CRD and Configuration
1. Add new status fields to ComputeInstance CRD
2. Update CRD YAML files
3. Add provider selection flags to main.go
4. Add configuration for AAP credentials
5. Update Helm charts with new config

### Phase 7: Documentation and Migration
1. Document provider abstraction
2. Document how to configure each provider
3. Create migration guide from EDA to AAP Direct
4. Update deployment documentation

## Testing Strategy

### Unit Tests
- Provider interface contract tests
- EDA Provider implementation
- AAP Direct Provider implementation
- AAP Client (with mocked HTTP)

### Integration Tests
- End-to-end with EDA provider (existing behavior)
- End-to-end with AAP Direct provider (new behavior)
- Test job success scenarios
- Test job failure scenarios
- Test long-running jobs with polling

### Migration Testing
- Deploy with EDA provider (default)
- Switch to AAP Direct provider
- Verify both work with same playbooks

## Configuration Examples

### EDA Provider (current, default)
```yaml
args:
  - --provisioning-provider=eda
  - --create-compute-instance-webhook=http://eda-server:5000/webhook
  - --delete-compute-instance-webhook=http://eda-server:5000/webhook
```

### AAP Direct Provider (new)
```yaml
args:
  - --provisioning-provider=aap-direct
  - --aap-url=https://aap.example.com
  - --aap-token-file=/etc/aap/token
  - --aap-create-template-name=cloudkit_create_compute_instance
  - --aap-delete-template-name=cloudkit_delete_compute_instance
env:
  - name: AAP_TOKEN
    valueFrom:
      secretKeyRef:
        name: aap-credentials
        key: token
```

## Verification

### Success Criteria
- [ ] Provider abstraction allows swapping implementations
- [ ] EDA provider maintains current behavior (backward compatible)
- [ ] AAP Direct provider can trigger jobs via API
- [ ] AAP Direct provider polls for job completion
- [ ] Job failures are reported in CR status
- [ ] Configuration supports both providers
- [ ] All unit tests pass
- [ ] Integration tests pass for both providers
- [ ] Documentation is complete

### Manual Testing Steps
1. Deploy with EDA provider, verify compute instance creation works
2. Switch to AAP Direct provider
3. Create compute instance, verify:
   - Job is triggered via AAP API
   - Job ID is stored in CR status
   - Reconciler polls for status
   - When job completes, CR is marked Ready
   - If job fails, error is shown in CR status
4. Test deletion flow with both providers

## Rollout Strategy

1. **Phase 1: Release with EDA as default**
   - Add abstraction layer
   - Both providers available but EDA is default
   - Users can opt-in to AAP Direct

2. **Phase 2: Gather feedback**
   - Monitor AAP Direct usage
   - Fix any issues discovered
   - Document common configurations

3. **Phase 3: Make AAP Direct default (optional)**
   - Switch default in future release
   - Provide migration guide
   - Deprecate EDA provider (but keep for compatibility)
