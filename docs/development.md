# Development Workflow

This document defines the branching policy, merge request workflow, and verification
commands for GEOSIX.

The goal of the policy is simple: **a merge request diff must show only the work that
the feature actually introduced.** When an epic branch does not share the integration
baseline, every merge request against it reports the entire platform as newly added,
which makes review impossible.

## Integration Branch

The canonical integration/mainline branch is:

```
origin/develop
```

`develop` is the branch where completed epics are landed. It is the only branch that has
absorbed previous epics, and it is the correct base for all new work.

`main` is a release/landing branch. It diverges from `develop` and is **not** a valid
base for epics or features.

### Existing peer epics are not the integration branch

`origin/epic/core-palatform-2` is an existing peer epic branch. It is **not** the
canonical integration branch, and it must not be used as the base for unrelated epics.

The branch name contains a historical typo ("palatform"). It is preserved deliberately
so that existing branch references, merge request targets, and protected-branch rules
keep working. **Do not rename it as a side effect of unrelated work.**

## Epic Branch Creation

Epic branches are created from an up-to-date `develop`.

```bash
git fetch origin --prune
git switch develop
git pull --ff-only
git switch -c epic/<name>
git push -u origin epic/<name>
```

Rules:

- Epic branches are created from `develop`.
- **Never** create an epic branch from the repository root commit. An epic that does not
  contain `develop` cannot be reviewed against and will inflate every merge request
  diff.
- Do not create an epic from another epic unless that coupling is explicitly intended and
  documented in the epic's merge request.
- Name epic branches `epic/<name>`.

## Feature Branch Creation

Feature branches are created from their target epic branch.

```bash
git fetch origin --prune
git switch epic/<name>
git pull --ff-only
git switch -c feat/<epic-name>-<description>
git push -u origin feat/<epic-name>-<description>
```

Rules:

- A feature branch must start from the epic it will be merged into.
- **Never** start a feature branch from an unrelated epic.
- Do not let a feature branch silently start from `develop` or `main` when its target is
  an epic. This produces a diff that appears to add the whole platform.
- Name feature branches `feat/<epic-name>-<description>`.

## Verification

Run these before opening a merge request and again before merging.

### Confirm the branch shares the integration baseline

```bash
git merge-base origin/develop origin/epic/<name>
```

The output must be a commit that is **not** the repository root commit. A result equal to
the root commit means the epic was created from the wrong place.

Compare it against `develop` directly:

```bash
git merge-base --is-ancestor origin/develop origin/epic/<name> && echo PASS || echo FAIL
```

`PASS` means `develop` is fully contained in the epic, which is the required state.

### Review the actual change

```bash
git diff --stat origin/epic/<name>...HEAD
git diff --name-status origin/epic/<name>...HEAD
```

What each command verifies:

| Command | Verifies |
|---------|----------|
| `git merge-base origin/develop origin/epic/<name>` | The epic and `develop` share a real history, not just the root commit |
| `git merge-base --is-ancestor ...` | The integration baseline is fully contained in the epic (no drift) |
| `git diff --stat origin/epic/<name>...HEAD` | The size of the change; a whole-platform-sized stat means a bad baseline |
| `git diff --name-status origin/epic/<name>...HEAD` | Exactly which files change, and whether they are additions, modifications, or deletions |
| `git log --oneline origin/epic/<name>..HEAD` | Which commits the feature actually introduces |

## Merge Request Workflow

```
feature branch  ->  target epic  ->  review  ->  squash merge  ->  delete feature branch
```

1. Open the feature branch against its target epic branch, never against `main`.
2. Review the triple-dot diff and confirm the checklist in the merge request template.
3. Squash merge so the epic receives one reviewable commit per feature.
4. Delete the feature branch after merge.

## Triple-Dot Diff

Use the three-dot form when reviewing a merge request:

```bash
git diff origin/epic/<name>...HEAD
```

The three-dot form compares `HEAD` against the **merge base** of the two branches — the
point where the feature branch diverged. That is exactly the set of changes the feature
introduced, which is what a reviewer needs to see.

The two-dot form compares raw tree snapshots and therefore also reports every difference
caused by the target branch having moved ahead. In a correctly based epic the two forms
agree. When they diverge sharply, the epic baseline is wrong and the triple-dot diff is
the one that reveals it.

The same reasoning applies in the GitLab merge request view: an inflated file count is
the signature of a target branch that does not share the integration baseline.

## CI Diff-Scope Guard

`.gitlab-ci.yml` contains an advisory job, `ci:mr-diff-scope`, that runs on merge request
pipelines and reports:

- the target branch, source branch, source SHA, and target SHA
- whether the target branch contains `origin/develop` as an ancestor
- the merge base between target and source
- the merge-request-visible changed-file list
- the subset of those changes that are files which **already exist on `origin/develop`**
  but are reported as newly added

That last figure is the baseline-inflation signature. In a correctly based epic a file
that already exists on `develop` is also present in the merge base, so it can never be
reported as an addition. A non-zero count means the target branch does not share the
integration baseline and the review diff is larger than the real work.

The job is **report-only**. It runs with `allow_failure: true`, contains no blocking exit
path, and returns success on every error path, including a missing or uncomputable merge
base. It exists to surface baseline problems early; it never rejects a merge request.


## Case Study: the topology epic baseline

`epic/topology-validation` was originally rooted at the repository root commit rather
than at `develop`. As a result it did not share the integration baseline, and merge
requests against it reported the entire platform as newly added.

Merge request !26, "feat: Implement 3D Property Geometry Model", is the concrete
example. Its source branch was `feat/3d-property-geometry-model` and its target was
`epic/topology-validation`. Because the target lacked the platform history, the
merge request showed **146 changed files and roughly 16,200 inserted lines**, while the
feature itself touched only **9 files and roughly 500 inserted lines**. The remaining
files were baseline inflation, not new work.

Merge request !26 is **already merged and closed**. Its historical commits are retained
exactly as they were:

| Commit | Role |
|--------|------|
| `760d454` | squash feature commit for the 3D property geometry model |
| `0655018` | merge commit into `epic/topology-validation` |

Those commits are **not** rewritten, and the historical merge request is not reopened or
rejudged. W36 corrects the branching process and the target branch baseline so that
**future** merge requests into this epic show scoped, reviewable diffs. It does not and
cannot retroactively change what merge request !26 displayed.

The 3D property geometry work itself is unaffected: the geometry model, its migration,
and its tests remain in the epic's history and remain attributable to the feature.

### Measured result

The epic baseline was corrected by merging `origin/develop` into the epic with a normal
merge commit, so no existing commit was rewritten. The two figures below were measured
with the same command, `git diff --shortstat origin/develop...HEAD`, on either side of
that merge.

| Measurement | Before `1e091f0` | After `8bfbf46` |
|-------------|------------------|-----------------|
| Merge base with `origin/develop` | `9c3983f2` (repository root) | `1faae32` (the `develop` tip) |
| `origin/develop` is an ancestor | no | yes |
| Files changed | 184 | 56 |
| Inserted lines | 21,013 | 5,182 |
| Deleted lines | 57 | 79 |
| Added / modified | 183 / 1 | 42 / 14 |
| Files reported as added that already exist on `develop` | 140 | 0 |

The last row is the inflation signature that `ci:mr-diff-scope` reports. It is now zero,
which is the measurable definition of a correctly based epic: the epic contributes only
its own 3D work on top of the shared integration baseline.

The remaining 56 files are the epic's real content, not baseline noise. Before the merge
`develop` was not an ancestor of the epic, so nearly the whole platform was attributed to
the epic; afterwards the diff contains the 3D geometry model, topology endpoints, the
`property_geometry` migration chain, and the tests that cover them.
