# Human review gate refresh

`review-gate.yml` keeps `check-human-reviews` read-only, including on fork PRs.
It evaluates all review pages, ignoring bots and non-decisive comments. Each
human's latest decisive review determines whether that human still requests
changes. API or evaluation errors fail the check.

Review events create separate workflow runs: a later passing review-event run
does not refresh the original `pull_request` run. For example, the public
[PR #459](https://github.com/osac-project/enhancement-proposals/pull/459) had
failing PR-event run `41867805257` and passing review-event run `42041871450`
on the same head. An external rerun refreshed the original suite before a
manual merge. This does not imply all historical failed suites block merging.

`refresh-review-gate.yml` handles completed review-event runs on the trusted
default branch. Its only write operation reruns matching `pull_request`
review-gate runs, preserving their required check name, GitHub Actions app,
original SHA/ref, and original actor privileges. It never trusts the review
run's conclusion: the original gate fetches current reviews again.

The relay verifies repository, workflow ID/path, event, unique PR association,
current open PR/head/base, and target fork/branch/head. Association uses the
commit-to-PR API because fork run payloads can have empty `pull_requests`;
ambiguous associations fail rather than guessing. Review runs may report the
base repository as `head_repository`, unlike the original fork PR run.
Closed or stale revisions are ignored. Only trusted workflow-commit code is
checked out, with no persisted credentials; no fork code, caches or artifacts
are consumed. Write permission is limited to Actions in the relay job.

Relay runs are serialized per exact branch/SHA pair without canceling an active
refresh. An unprivileged job hashes this pair so different branches, including
names differing only in case, cannot coalesce through GitHub's case-insensitive
concurrency groups. The privileged job verifies the lock metadata against a
fresh API read. Pending events for that revision can coalesce because every
rerun evaluates current reviews. An active target is polled for at most five
minutes before failing visibly rather than issuing an overlapping rerun.
PR state is checked again while waiting. A head
change after the last read can only rerun the old SHA, not publish a result on
the new revision. Completion of the rerun does not loop: only review-event runs
are eligible sources.

All matching PR-event runs on the current revision are refreshed: `opened`,
`reopened`, and `ready_for_review` can create more than one PR-event suite on a
single head. Choosing only the newest or a previously failing run would assume
undocumented required-check selection and could leave another authoritative
PR-event result stale. Review-event suites and other revisions are not rerun.

GitHub permits reruns only within 30 days of the initial run. Expired runs,
API failures, and missing targets cause a visible relay failure, not a fabricated
passing check. A new PR revision supplies a new original run when a run expires.
This is not a retroactive cleanup of existing suites, and the relay must first
be merged onto the default branch to receive future review completions.

## Local checks

From `.github/scripts`, run `python3 -m unittest test_review_gate -v` for the
focused mock-API and actual bash/jq evaluator tests. The normal Python unittest
CI consumer discovers these tests, including on either gate workflow change.
Run pre-commit and actionlint on changed workflows before publication.

## GitHub semantics

- [Workflow events and fork permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)
- [Rerun SHA, privileges and eligibility](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
- [Concurrency groups and pending-event coalescing](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)

Rollback is a revert of the workflow/script/test change; keep required-check
settings and the human-review policy unchanged.
