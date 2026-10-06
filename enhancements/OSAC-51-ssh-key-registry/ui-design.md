---
title: ssh-key-registry-ui
authors:
  - lsoffer
creation-date: 2026-10-06
last-updated: 2026-10-06
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-51
prd:
  - SSH key registry PRD: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-51-ssh-key-registry/prd.md
see-also:
  - https://redhat.atlassian.net/browse/OSAC-51
replaces:
  - N/A
superseded-by:
  - N/A
---

# SSH Key Registry UI

## Summary

This design adds tenant-user UI for registering, listing, filtering, and
deleting SSH public keys through the existing `Secret` API with
`SecretType.SSH_PUBLIC_KEY`. It also replaces the inline SSH key text field in
both the ComputeInstance and BareMetalInstance creation wizards with a
`SecretSelectionField` that references a registered key by name.

## Scope

In scope:

- Add `SSH_PUBLIC_KEY` to the Secret create wizard type selector.
- Add an SSH-specific data-entry field with client-side key-format validation.
- Add `SSH public key` to the Secret list page type filter.
- Replace the inline `SshKeyField` in both the ComputeInstance and
  BareMetalInstance create wizards with `SecretSelectionField`, referencing
  registered SSH public key secrets by name.

## Proposal

### Secret Create Wizard — Type Selector

- Add `SecretType.SSH_PUBLIC_KEY` to the `SECRET_TYPES` array in
  `SecretTypeField.tsx` with a title and description card.

### Secret Create Wizard — Data Entry

- When `SSH_PUBLIC_KEY` is selected, render a single `SecretValueField` bound
  to a new `sshPublicKey` form field with fixed key `public_key` (matching
  `getSecretTypeDataKeys`).
- The value field should use the `enter` input mode by default (text area),
  with file upload as an alternative — same as other typed secrets.

### Secret Create Wizard — Validation

- Add a Yup test on the `sshPublicKey` entry's decoded text value using
  the existing `isValidSshPublicKey` helper from
  `catalogProvision/wizard/fields/credentialValidation.ts`.
- Error message: `Enter a valid OpenSSH public key (ssh-rsa, ssh-ed25519, or ecdsa-sha2-nistp*).`
- The value-required and max-size tests from existing `getValueSchema` apply
  unchanged.

### Secret Create Wizard — Payload

- Add an `SSH_PUBLIC_KEY` case to `buildTypedData` in `payload.ts`:
  `{ 'public_key': getEntryBytes(values.sshPublicKey) }`.

### Secret Create Wizard — Form Values

- Add `sshPublicKey: SecretDataEntry` to `SecretValues` with default
  `{ key: 'public_key', value: emptyValue() }`.
- Map it in `getSecretValues` the same way `kubeconfig`/`pullsecret`/etc.
  are mapped.

### Secret List Page — Type Filter

- Add `'sshpublickey'` to `TYPE_FILTER_VALUES` in `utils.ts`.
- Map it in `TYPE_FILTER_TO_ENUM`: `sshpublickey: SecretType.SSH_PUBLIC_KEY`.

### ComputeInstance and BareMetalInstance Create Wizards — SSH Key Selection

- Replace the inline `SshKeyField` in both `VmGeneralStep.tsx` and
  `BareMetalGeneralStep.tsx` with `SecretSelectionField`, filtered to
  `SecretType.SSH_PUBLIC_KEY` and scoped to the selected project.
- Update `spec.sshKey` in both wizard value types from inline key text to a
  secret name reference.
- Update both payload builders to send the secret name instead of the raw key.
- Remove `isValidSshPublicKey` from both instance schemas (validation moves to
  secret registration time).

## Failure Handling

- Secret creation failures surface via the existing wizard's
  `OSACWizardFooter` error alert. Title: `Failed to create secret`.
- SSH key format validation errors appear inline on the value field before
  submission.

## Test Plan

- Unit-test that `SSH_PUBLIC_KEY` appears in the type selector and is
  selectable.
- Unit-test SSH key format validation: valid keys pass, invalid strings
  rejected.
- Unit-test the create payload includes `{ 'ssh-publickey': ... }` for
  `SSH_PUBLIC_KEY` type.
- Unit-test that the list page type filter includes `SSH public key` and
  filters correctly.
