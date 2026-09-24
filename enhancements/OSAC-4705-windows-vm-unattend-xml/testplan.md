# Test Plan — OSAC-4705: Create Windows VMs with a Caller-Supplied Unattend.xml

## Test Plan Overview

This test plan validates the Unattend.xml delivery feature across the four
interface changes identified in the design document. Tests are organized by
component and cover positive paths, validation rejection, edge cases, and
backward compatibility.

---

## Test Cases

### Fulfillment Service — XML Validation (IC-1)

#### TC-1.1: Create Windows VM with well-formed inline Unattend.xml

| Field | Value |
|-------|-------|
| PRD Requirements | FR: `user_data` validated as well-formed XML when DiskImage is Windows |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Preconditions:** DiskImage exists with `guest_os_family = WINDOWS`.

**Steps:**
1. Call CreateComputeInstance with `disk_image` referencing the Windows
   DiskImage and `user_data` containing well-formed XML:
   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <unattend xmlns="urn:schemas-microsoft-com:unattend">
     <settings pass="oobeSystem">
       <component name="Microsoft-Windows-Shell-Setup" ...>
         <OOBE><HideEULAPage>true</HideEULAPage></OOBE>
       </component>
     </settings>
   </unattend>
   ```
2. Verify: create succeeds (no validation error).

#### TC-1.2: Reject malformed XML inline user_data for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: reject if `user_data` is not well-formed XML on Windows |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage and `user_data` containing
   malformed XML (e.g., unclosed tags, invalid characters).
2. Verify: create fails with `INVALID_ARGUMENT` containing
   `"user_data is not well-formed XML"`.

#### TC-1.3: Accept non-XML user_data for Linux VM (no validation)

| Field | Value |
|-------|-------|
| PRD Requirements | FR: XML validation only when DiskImage is Windows |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Linux DiskImage and `user_data` containing
   cloud-init YAML (not XML).
2. Verify: create succeeds — no XML validation applied.

#### TC-1.4: Validate user_data_secret content as XML for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: `user_data_secret` content validated same as inline |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Create an OSAC Secret with `userdata` key containing well-formed XML.
2. Call CreateComputeInstance with Windows DiskImage and `user_data_secret`
   referencing the secret.
3. Verify: create succeeds.

#### TC-1.5: Reject user_data_secret with malformed XML for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: `user_data_secret` validation consistent with inline |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Create an OSAC Secret with `userdata` key containing malformed XML.
2. Call CreateComputeInstance with Windows DiskImage and `user_data_secret`
   referencing the secret.
3. Verify: create fails with error that does NOT expose secret content.

#### TC-1.6: Create Windows VM without user_data (no caller-supplied answer file)

| Field | Value |
|-------|-------|
| PRD Requirements | FR: both fields optional; omit = no caller-supplied answer file |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage, no `user_data`, no
   `user_data_secret`.
2. Verify: create succeeds — no XML validation triggered.
3. Verify: no caller-supplied answer file is attached. (Note: the
   platform-generated `unattend.xml.j2` template may still be rendered by the
   AAP role if `vm_enable_sysprep` is true — see TC-3.2. This test validates
   only that the fulfillment service does not require or validate XML when no
   user data is supplied.)

#### TC-1.7: Reject empty user_data for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: empty payloads rejected when field is present |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage and `user_data` set to
   empty string.
2. Verify: create fails with validation error.

#### TC-1.8: Mutual exclusion of user_data and user_data_secret (existing)

| Field | Value |
|-------|-------|
| PRD Requirements | FR: mutually exclusive fields |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with both `user_data` and `user_data_secret` set.
2. Verify: create fails with mutual exclusion error. (Existing test — verify
   no regression.)

#### TC-1.9: Reject XML with DOCTYPE declaration for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: reject DTD declarations in user_data |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage and `user_data` containing
   an XML document with a DOCTYPE declaration:
   ```xml
   <?xml version="1.0"?>
   <!DOCTYPE unattend SYSTEM "unattend.dtd">
   <unattend/>
   ```
2. Verify: create fails with `INVALID_ARGUMENT` containing
   `"DOCTYPE declarations are not permitted"`.

#### TC-1.10: Reject whitespace-only user_data for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: require a valid XML root element |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage and `user_data` containing
   only whitespace characters (spaces, newlines, tabs).
2. Verify: create fails with `INVALID_ARGUMENT` containing
   `"document is empty"`.

#### TC-1.11: Reject XML fragment with multiple root elements for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: require exactly one XML root element |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Call CreateComputeInstance with Windows DiskImage and `user_data` containing
   multiple root elements:
   ```xml
   <unattend/><unattend/>
   ```
2. Verify: create fails with `INVALID_ARGUMENT` containing
   `"multiple root elements"`.

#### TC-1.12: Reject user_data_secret with DOCTYPE declaration for Windows VM

| Field | Value |
|-------|-------|
| PRD Requirements | FR: reject DTD declarations via secret-backed delivery |
| Interface Change | IC-1 |
| Test Type | Unit (ginkgo) |

**Steps:**
1. Create an OSAC Secret with `userdata` key containing XML with a DOCTYPE
   declaration.
2. Call CreateComputeInstance with Windows DiskImage and `user_data_secret`
   referencing the secret.
3. Verify: create fails with error that rejects the DOCTYPE declaration and
   does NOT expose secret content.

### AAP Role — User-Supplied Sysprep (IC-2)

#### TC-3.1: User-supplied Unattend.xml mounted as sysprep volume

| Field | Value |
|-------|-------|
| PRD Requirements | FR: user Unattend.xml delivered as answer file |
| Interface Change | IC-2 |
| Test Type | Integration (AAP role) |

**Preconditions:** ComputeInstance CR with `guestOSFamily: windows`,
`vm_enable_sysprep: false`, and `userDataSecretRef` pointing to a Secret
with user-supplied Unattend.xml content.

**Steps:**
1. Run the `ocp_virt_vm` role create workflow.
2. Verify: a Secret is created in the VM namespace with key `Unattend.xml`
   containing the user's content.
3. Verify: the VM template spec includes a `sysprep` volume referencing the
   Secret and a `sata` CD-ROM disk.
4. Verify: the Jinja2 `unattend.xml.j2` template was NOT rendered.

#### TC-3.2: Platform-generated sysprep when no user data (Windows)

| Field | Value |
|-------|-------|
| PRD Requirements | FR: omit = no user-supplied answer file |
| Interface Change | IC-2 |
| Test Type | Integration (AAP role) |

**Preconditions:** ComputeInstance CR with `guestOSFamily: windows`,
`vm_enable_sysprep: true`, and NO `userDataSecretRef`.

**Steps:**
1. Run the `ocp_virt_vm` role create workflow.
2. Verify: the Jinja2 `unattend.xml.j2` template IS rendered.
3. Verify: a sysprep Secret and volume are created with the template content.

#### TC-3.3: No sysprep when no user data and sysprep disabled (Windows)

| Field | Value |
|-------|-------|
| PRD Requirements | FR: omit = no answer file |
| Interface Change | IC-2 |
| Test Type | Integration (AAP role) |

**Preconditions:** ComputeInstance CR with `guestOSFamily: windows`,
`vm_enable_sysprep: false`, and NO `userDataSecretRef`.

**Steps:**
1. Run the `ocp_virt_vm` role create workflow.
2. Verify: no sysprep Secret, volume, or disk is created.

#### TC-3.4: Linux user data still uses cloudInitNoCloud volume

| Field | Value |
|-------|-------|
| PRD Requirements | Backward compatibility — Linux unaffected |
| Interface Change | IC-2 |
| Test Type | Integration (AAP role) |

**Preconditions:** ComputeInstance CR with `guestOSFamily: linux` and
`userDataSecretRef` set.

**Steps:**
1. Run the `ocp_virt_vm` role create workflow.
2. Verify: user data is mounted as a `cloudInitNoCloud` volume with `virtio`
   bus (existing behavior).
3. Verify: NO sysprep volume is created.

#### TC-3.5: Secret key mapping — userdata to Unattend.xml

| Field | Value |
|-------|-------|
| PRD Requirements | FR: content delivered as answer file |
| Interface Change | IC-2 |
| Test Type | Integration (AAP role) |

**Steps:**
1. Create a user data Secret with key `userdata` containing Unattend.xml
   content.
2. Run the `ocp_virt_vm` role for a Windows VM.
3. Verify: the created sysprep Secret in the VM namespace has key
   `Unattend.xml` (not `userdata`) containing the original content.

### CLI — Help Text (IC-3)

#### TC-4.1: CLI help text references Unattend.xml for Windows

| Field | Value |
|-------|-------|
| PRD Requirements | FR: CLI supplies Unattend.xml through existing mechanism |
| Interface Change | IC-3 |
| Test Type | Unit (go test) |

**Steps:**
1. Run `osac create compute-instance --help`.
2. Verify: `--user-data` description mentions Unattend.xml for Windows
   DiskImages.
3. Verify: `--user-data-secret` description mentions Unattend.xml for
   Windows DiskImages.

### UI — Windows-Aware Input (IC-4)

#### TC-5.1: UI shows Unattend.xml label for Windows DiskImage

| Field | Value |
|-------|-------|
| PRD Requirements | FR: UI supplies Unattend.xml through existing mechanism |
| Interface Change | IC-4 |
| Test Type | E2E (UI) |

**Steps:**
1. Navigate to ComputeInstance creation form.
2. Select a DiskImage with `guest_os_family = WINDOWS`.
3. Verify: the user data input is labeled "Unattend.xml" (not "Cloud-init").
4. Verify: a hint indicates content must be well-formed XML.

#### TC-5.2: UI shows cloud-init label for Linux DiskImage

| Field | Value |
|-------|-------|
| PRD Requirements | Backward compatibility — Linux UI unaffected |
| Interface Change | IC-4 |
| Test Type | E2E (UI) |

**Steps:**
1. Navigate to ComputeInstance creation form.
2. Select a DiskImage with `guest_os_family = LINUX`.
3. Verify: the user data input is labeled for cloud-init (existing behavior).

#### TC-5.3: UI does not persist user_data in browser storage

| Field | Value |
|-------|-------|
| PRD Requirements | NFR: UI must not cache user_data |
| Interface Change | IC-4 |
| Test Type | E2E (UI) |

**Steps:**
1. Create a Windows VM with inline `user_data` via the UI.
2. Check browser localStorage, sessionStorage, and cache storage.
3. Verify: no `user_data` content is persisted.

### End-to-End Tests

#### TC-E2E-1: Windows VM with user-supplied Unattend.xml (full path)

| Field | Value |
|-------|-------|
| PRD Requirements | E2E: create with supplied Unattend.xml |
| Interface Change | IC-1, IC-2 |
| Test Type | E2E (pytest) |

**Preconditions:** Windows DiskImage available; tenant project with
appropriate permissions.

**Steps:**
1. Create a ComputeInstance via the API with:
   - `disk_image` referencing a Windows DiskImage
   - `user_data` containing a valid Unattend.xml that sets a specific
     hostname and skips OOBE
2. Wait for the ComputeInstance to reach Running state.
3. Verify: the VM's sysprep volume contains the supplied Unattend.xml.
4. Verify: Windows first boot follows the answer file settings.

#### TC-E2E-2: Windows VM without Unattend.xml (no answer file)

| Field | Value |
|-------|-------|
| PRD Requirements | E2E: create without = no unattend volume |
| Interface Change | IC-1, IC-2 |
| Test Type | E2E (pytest) |

**Steps:**
1. Create a ComputeInstance with a Windows DiskImage and no `user_data` or
   `user_data_secret`, with `vm_enable_sysprep: false`.
2. Wait for the ComputeInstance to reach Running state.
3. Verify: no sysprep volume is attached to the VM.

#### TC-E2E-3: Windows VM with user_data_secret delivery

| Field | Value |
|-------|-------|
| PRD Requirements | E2E: create with user_data_secret |
| Interface Change | IC-1, IC-2 |
| Test Type | E2E (pytest) |

**Steps:**
1. Create an OSAC Secret with `userdata` key containing a valid Unattend.xml.
2. Create a ComputeInstance with a Windows DiskImage and `user_data_secret`
   referencing the secret.
3. Wait for the ComputeInstance to reach Running state.
4. Verify: the VM's sysprep volume contains the Unattend.xml from the secret.

---

## Coverage Matrix

| IC | Test Cases | Coverage |
|----|-----------|----------|
| IC-1 (XML validation) | TC-1.1, TC-1.2, TC-1.3, TC-1.4, TC-1.5, TC-1.6, TC-1.7, TC-1.8, TC-1.9, TC-1.10, TC-1.11, TC-1.12 | Create-time validation for all delivery paths and OS families, including DOCTYPE rejection, empty/whitespace content, and multi-root fragments |
| IC-2 (AAP sysprep) | TC-3.1, TC-3.2, TC-3.3, TC-3.4, TC-3.5 | Volume routing for all OS/user-data combinations |
| IC-3 (CLI help) | TC-4.1 | Help text accuracy |
| IC-4 (UI adaptation) | TC-5.1, TC-5.2, TC-5.3 | Label switching, no-cache compliance |
| E2E | TC-E2E-1, TC-E2E-2, TC-E2E-3 | Full create-to-running path |

### IC Coverage Gaps

None identified. All interface changes have corresponding test cases covering
positive paths, rejection paths, and backward compatibility.
