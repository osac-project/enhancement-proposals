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

## How do I create a PRD?

A PRD (Product Requirements Document) defines **what** a feature delivers and
**why**, from the user's perspective. PRDs are merged before design work begins.
For detailed guidance on writing PRDs, the PRD vs design EP boundary, personas,
and good/bad examples, see [guidelines/prd_guide.md](guidelines/prd_guide.md).

The recommended way to create a PRD is using the `/prd` skill in an AI-assisted
development tool (Claude Code, Cursor, or similar):

1. Run `/prd:ingest` with your Jira ticket to gather requirements.
2. Run `/prd:clarify` to resolve ambiguities through guided Q&A.
3. Run `/prd:draft` to generate the PRD from the project template.
4. Run `/prd:publish` to create a PR on this repository.

The skill produces a PRD that follows [guidelines/prd_template.md](guidelines/prd_template.md),
addresses OSAC feature dimensions, and can be validated with `/prd-review`
before submission.

If you prefer to write manually, copy the template and follow the instructions
inside it:

```sh
mkdir enhancements/storage-backend-osac-1111
cp guidelines/prd_template.md enhancements/storage-backend-osac-1111/prd.md
```

Use the naming convention `<area>-<description>-<ticket-id>`, all lowercase
with hyphens. Create a pull request against `main` when ready.

After the PRD is merged, create the design EP (`design.md`) in the same
directory. See "How do I create an enhancement proposal?" below.

## How do I create an enhancement proposal?

To create an enhancement proposal:

1. Create a new directory inside the `enhancements` directory:

    ```sh
    mkdir enhancements/my-nifty-feature
    ```

2. Copy `guidelines/enhancement_template.md` to `design.md` in your new directory:

    ```sh
    cp guidelines/enhancement_template.md enhancements/my-nifty-feature/design.md
    ```

3. Edit `enhancements/my-nifty-feature/design.md`, following the embedded instructions. If a section does not apply to your proposal, mark it `N/A` rather than removing it.

4. If your proposal requires additional assets -- images, sample configuration files, etc -- include them in the same directory as the `design.md`.

5. Create a pull request with your changes against the main branch of the [enhancement proposals] repository.

6. Select at least three reviewers for your pull request.

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
