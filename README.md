# Enhancement Proposals

This repository is for proposing enhancements to the Open Sovereign AI Cloud (O-SAC) project. It is modeled after the [OpenShift Enhancement Proposals] repository. It provides a rally point to discuss, debate, and reach consensus for how O-SAC enhancements are introduced. The O-SAC solution is built on top of multiple projects, including both existing third party projects and code produced de novo for O-SAC. Given the breadth of the projects and repositories, it is useful to have a centralized place to describe enhancements via an actionable design proposal.

Enhancements may take multiple releases to ultimately complete and thus provide the basis of a roadmap. Enhancements may be filed from anyone in the community, but require consensus from domain specific project maintainers in order to implement and accept into the release.

[openshift enhancement proposals]: https://github.com/openshift/enhancements

## Is my proposed change an enhancement?

A rough heuristic for an enhancement is anything that:

- includes addition or removal of significant capabilities
- impacts upgrade/downgrade
- needs significant effort to complete
- requires consensus/code across multiple domains/repositories
- proposes adding a new user-facing component
- has phases of maturity (Dev Preview, Tech Preview, GA)
- demands formal documentation to utilize

It is unlikely to require an enhancement if it:

- fixes a bug
- adds more testing
- internally refactors a code or component only visible to that components domain
- minimal impact to distribution as a whole

If you are not sure if the proposed work requires an enhancement, file an issue and ask!

## How do I create an enhancement proposal?

OSAC uses a two-document flow: a **PRD** (Product Requirements Document) describes WHAT and WHY, and a **design document** describes HOW.

### Recommended: AI-assisted workflow (osac-workspace)

The [osac-workspace](https://github.com/osac-project/osac-workspace) provides AI-assisted workflows that guide you through the process:

1. **PRD**: Run `/prd:ingest` to start a PRD, then `/prd:draft` and `/prd:publish` to create it in this repo as `enhancements/OSAC-NNNN-feature-slug/prd.md`.
2. **Design**: Run `/design:ingest` to start the design, then `/design:draft` and `/design:publish` to create it as `enhancements/OSAC-NNNN-feature-slug/design.md`.

See the osac-workspace [AGENTS.md](https://github.com/osac-project/osac-workspace/blob/main/AGENTS.md) for full workflow details.

### Manual workflow

1. Create a new directory inside the `enhancements` directory:

    ```sh
    mkdir enhancements/OSAC-1234-my-nifty-feature
    ```

2. Create your PRD (`prd.md`) and design document (`design.md`) in that directory. Use `guidelines/enhancement_template.md` as a starting point for the design if needed (note: this template predates the two-document split and includes sections like User Stories that now belong in the PRD).

3. If your proposal requires additional assets -- images, sample configuration files, etc -- include them in the same directory.

4. Create a pull request with your changes against the main branch of the [enhancement proposals] repository.

5. Select at least three reviewers for your pull request.

## How are enhancement proposals reviewed and approved?

The author of an enhancement is responsible for managing it through the review and approval process, including soliciting feedback on the pull request and in meetings, if necessary.

The set of reviewers for an enhancement proposal can be anyone that has an interest in this work or the expertise to provide a useful input/assessment. At a minimum, the reviewers must include a representative of any team that will need to do work for this proposal, or whose team will own/support the resulting implementation. Be mindful of the workload of reviewers, however, and the challenge of finding consensus as the group of reviewers grows larger. Clearly indicating what aspect of the proposal you expect each reviewer to be concerned with will allow them to focus their reviews.

An enhancement proposal is formally accepted when reviewers have reach consensus on the proposal and it has been merged into the main branch of the repository.

Approval of an enhancement proposal does not guarantee implementation. Developers have existing commitments that may take priority over some (or all) enhancement proposals.

## How Can an Author Help Speed Up the Review Process?

Enhancements should have agreement from all stakeholders prior to being approved and merged. Reviews are not time-boxed. If it is not possible to attract the attention of enough of the right maintainers to act as reviewers, that is a signal that the project's rate of change is maxed out. With that said, there are a few things that authors can do to help keep the conversation moving along:

1. Respond to comments quickly, so that a reviewer can tell you are engaged.

2. Push update patches, rather than force-pushing a replacement, to make it easier for reviewers to see what you have changed. Use descriptive commit messages on those updates, or plan to squash the commits when the pull request merges.

3. If the conversation otherwise seems stuck, pinging reviewers on Slack can be used to remind them to look at updates. It's generally appropriate to give people at least a business day or two to respond in the GitHub thread first, before reaching out to them directly on Slack, so that they can manage their work queue and disruptions.

## What is the lifecycle of an enhancement proposal?

An enhancement begins life as a pull request against the O-SAC [enhancement proposals] repository.

[enhancement proposals]: https://github.com/innabox/enhancement-proposals/

The pull request is reviewed by the core development team and other interested members of the community.

An enhancement proposal is accepted when the pull request has been merged into the main branch of the enhancement proposals repository. Ideally pull requests with enhancement proposals will be merged before significant coding work begins, since this avoids having to rework the implementation if the design changes as well as arguing in favor of accepting a design simply because it is already implemented.

After an enhancement proposal has been accepted and the implementation work is substantially complete, it may be necessary to update the design document in the O-SAC [docs] repository.

[docs]: https://github.com/innabox/docs/
