# Merge Request

## Description

<!-- Briefly describe the change and why it is needed. -->

## Review Checklist

- [ ] I selected the correct target epic branch.
- [ ] This feature branch was created from the target epic branch.
- [ ] The target is not an unrelated epic.
- [ ] I reviewed the triple-dot diff against the target branch.
- [ ] The diff contains only the intended work.
- [ ] I checked for accidental baseline/platform files.
- [ ] Relevant tests were run.
- [ ] Relevant lint/type-check/build checks were run.

<!--
Why the triple-dot diff matters:

    git diff origin/<target-epic>...HEAD

The three-dot form compares your branch against the merge base, which is exactly the set
of changes this branch introduced. If the target branch does not share the integration
baseline (origin/develop), that same diff also reports the entire platform as newly
added, and the file count becomes meaningless as a review signal.

Check the size before requesting review:

    git diff --stat origin/<target-epic>...HEAD
    git diff --name-status origin/<target-epic>...HEAD

A whole-platform-sized result means the target branch is missing its baseline, not that
your change is large. Confirm the baseline with:

    git merge-base origin/develop origin/<target-epic>
    git merge-base --is-ancestor origin/develop origin/<target-epic> && echo PASS || echo FAIL

See docs/development.md for the full branching policy.
-->
