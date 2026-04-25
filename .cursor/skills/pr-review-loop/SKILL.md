---
name: pr-review-loop
description: Automates PR loop state setup plus Copilot request/polling with GitHub CLI. Use when you need resumable `init`/`request-copilot`/`poll-copilot` orchestration while handling triage, code fixes, and thread replies/resolution in the main agent flow.
---
 # PR Review Loop

Use this skill to run an automated, iterative PR review loop from an existing PR.

## Utility runner (recommended)

Use the stateful helper to make long waits/retries resumable:

```bash
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py init --owner <owner> --repo <repo> --pr <pr_ref>
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-triage --agent-id <triage-agent-id> --unresolved-decisions "<...>" --action-plan "<...>"
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-implementation --agent-id <implementation-agent-id> --checks-run "<project_final_ci_command>" --checks-passed --push-completed --pushed-sha <sha>
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-self-review --agent-id <self-review-agent-id> --gate pass --notes "<...>"
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py verify-invariants
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py request-copilot
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py poll-copilot --interval-minutes 3 --timeout-minutes 15
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py finalize --interval-minutes 3 --timeout-minutes 15
```

The helper now also enforces iteration role artifacts, invariant checks, and a terminal `finalize` gate tied to the latest pushed implementation SHA.

For autonomous-safe commit/push execution without shell command chaining, use:

```bash
python3 .cursor/skills/pr-review-loop/scripts/git_barrier.py run \
  --files <file1> <file2> \
  --message-file /tmp/pr-loop-commit-message.txt
```

Ready-to-copy message-file flow:

```bash
cat > /tmp/pr-loop-commit-message.txt <<'EOF'
fix(workflow): short imperative subject

Why this change was needed and what risk/behavior it addresses.
EOF
python3 .cursor/skills/pr-review-loop/scripts/git_barrier.py run \
  --files <file1> <file2> \
  --message-file /tmp/pr-loop-commit-message.txt
```

Notes:

- Keep commit message focused on why, not only what.
- Use one file per logical fix commit; repeat this flow for additional commits.
- Add a custom trailer only when needed:
  - `--trailer "Made-with: Cursor"`

State file:

- `.cursor/skills/pr-review-loop/.loop-state.json`

## Safety and scope

- Use `gh` for all GitHub interactions.
- Never force-push or use destructive git commands.
- Invoking `/pr-review-loop <pr>` is explicit approval for this skill run to implement fixes and perform `git add`/`git commit`/`git push` to the PR head branch; no additional commit/push approval prompt is required for that run.
- Commit and push are mandatory once fixes/checks pass; do not continue with any GitHub mutation while local fix commits are unpushed.
- Treat unresolved review threads as source of truth for "open comments".
- Stop immediately and escalate to the operator when blocked by unsolvable or highly ambiguous issues.
- Require permissions for: PR comment reply, thread resolve, reviewer assignment, and branch push. If any permission is denied, stop and escalate with the exact error.

## Mandatory preflight contract check

Before Step 0, extract and track this checklist. Treat each item as a hard gate:

- [ ] This iteration will run with **three distinct subagents** (Agent 1 triage, Agent 2 implementation, Agent 3 self-review).
- [ ] Each heavy-lifting subagent will be launched with `run_in_background: true`.
- [ ] No role reuse in the same iteration (a single subagent cannot perform more than one role).
- [ ] Parent agent will only orchestrate and run parent-owned GitHub mutation/finalize steps.
- [ ] If any required item cannot be satisfied, stop immediately and escalate before continuing.

Hard-fail rule:

- If execution deviates from this contract at any point, stop, report the deviation explicitly, and restart the current iteration from the correct role boundary before any further GitHub mutations.

Deviation recovery protocol:

1. Stop immediately and record the exact deviation (iteration, step, expected behavior, observed behavior).
2. Do not run any GitHub mutation command (`replies`, `resolveReviewThread`, `gh pr edit --add-reviewer`, polling, or `finalize`) while out of compliance.
3. Re-run from the earliest violated role boundary with the correct subagent ownership:
   - if triage role violated: restart at Step 2
   - if implementation role violated: restart at Step 3
   - if self-review role violated: restart at Step 4
4. Replace the affected role artifact only with explicit audit metadata (`--replace --replace-reason "...deviation recovery..."`).
5. Continue only after invariants pass and compliance checklist is fully satisfied.

## Inputs

- PR reference: number, URL, or branch.
- Base branch: derived from the PR `baseRefName` via `gh pr view`.
- Max loops: `10`.
- Copilot poll cadence: every `3` minutes for up to `15` minutes.

## High-level agent choreography

Execution contract (mandatory):

- For each loop iteration, launch **three distinct subagents** for Agent 1, Agent 2, and Agent 3.
- Launch each heavy-lifting subagent with `run_in_background: true`.
- Keep roles isolated: one subagent must not execute more than one role in the same iteration.
- Do not resume/reuse the same subagent across different roles in the same iteration.
- A role is complete only when its required handoff artifact is produced and consumed by the next role.
- Role artifacts are immutable by default; replacing one requires explicit `--replace --replace-reason ...` audit metadata.
- GitHub mutation steps (reply/resolve/re-request/poll) are blocked until the iteration's implementation artifact proves push completion.
- Loop completion is **finalize-only**. Unresolved `0` alone is not sufficient unless `finalize` returns `success`.

1. **Agent 1 (triage/planning):** fetch unresolved threads, validate claims, produce a concrete plan for valid issues.
2. **Agent 2 (implementation):** apply planned fixes, run validations, then commit and push to the PR head branch.
3. **Agent 3 (self-review):** review the updated diff and runtime/test outcomes for regressions.
4. If Agent 3 finds relevant issues, spawn a new planning+implementation cycle in a separate agent.
5. Repeat local implementation/self-review until clean, blocked, or loop cap reached.
6. Enforce commit barrier: all fix changes must be committed and pushed before replying, resolving, re-requesting review, or polling.
7. Post responses to open threads, resolve them, request Copilot review.
8. Poll for Copilot review updates; if new unresolved comments appear, restart from Agent 1.

Parent boundary (mandatory):

- Parent agent must not substitute for Agent 1/2/3 execution roles.
- Parent agent may orchestrate role handoffs and run only post-implementation GitHub mutation/finalize steps.

## Loop state (must persist each iteration)

Track this in working notes and keep it updated:

- `loop_count` (start at 0, max 10)
- `pr_number`
- `pr_branch`
- `copilot_requested_at` (timestamp)
- `known_thread_ids` and current unresolved thread IDs
- `last_processed_head_sha`
- `last_seen_review_event_at`
- `processed_actions` (idempotency set for reply/resolve actions)
- `escalation_reason` (if any)

## Step 0 - Resolve PR context

1. Resolve PR number:
   - `gh pr view <pr> --json number,headRefName,baseRefName,headRefOid,url`
2. Preflight checks:
   - `gh auth status`
   - `git status --porcelain` (must be clean)
3. Ensure local branch is the PR head:
   - `gh pr checkout <pr>`
4. Sync branch safely:
   - `git fetch origin <head_branch>`
   - `git merge --ff-only origin/<head_branch>`

If checkout/sync fails, escalate with exact error.

## Step 1 - Fetch unresolved review threads

Use GraphQL (review thread state is authoritative). Always paginate `reviewThreads` and nested `comments`; do not assume a single page is complete.

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!,$threadsCursor:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      reviewThreads(first:100, after:$threadsCursor){
        nodes{
          id
          isResolved
          isOutdated
          path
          comments(first:100){
            nodes{
              id
              databaseId
              body
              createdAt
              author{login}
              url
            }
            pageInfo{
              hasNextPage
              endCursor
            }
          }
        }
        pageInfo{
          hasNextPage
          endCursor
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F number=<pr_number>
```

For nested comment pagination (`comments.pageInfo.hasNextPage == true`), run a per-thread follow-up query until all comments are collected:

```bash
gh api graphql -f query='
query($threadId:ID!,$commentsCursor:String){
  node(id:$threadId){
    ... on PullRequestReviewThread{
      comments(first:100, after:$commentsCursor){
        nodes{
          id
          databaseId
          body
          createdAt
          author{login}
          url
        }
        pageInfo{
          hasNextPage
          endCursor
        }
      }
    }
  }
}' -F threadId=<thread_id>
```

Filter to `isResolved == false` (include both current and `isOutdated == true` threads so every unresolved comment is triaged and explicitly handled).
For `isOutdated == true`, do not implement new code changes for that thread. Instead, explain why it became outdated based on commit/story context, post that rationale as a reply, and resolve the thread in the same cycle.
When selecting a reply target, ensure nested `comments` were fully paginated first; use the last actionable comment in the fully fetched thread.

## Step 2 - Agent 1 triage and plan

For each unresolved thread:

0. If `isOutdated == true`:
   - Decision: `valid` for handling workflow only (not code changes).
   - Action: reconstruct why it became outdated from the commit story / diff evolution, then prepare a concise rationale reply plus thread resolution.
   - Validation gate: confirm reply posted and thread is resolved.
   - Skip code-change planning for that thread.

1. Classify claim:
   - `valid`: demonstrable bug/risk/style-policy mismatch worth fixing.
   - `invalid`: incorrect claim.
   - `ambiguous`: cannot safely decide without operator input.
2. For `valid`, define plan entries with:
   - target files
   - exact expected behavior
   - validation command(s)
3. For `invalid`, prepare concise rationale and evidence.
4. For `ambiguous`, stop and escalate if ambiguity is material.

Planning output format:

- Issue
- Decision (`valid`/`invalid`/`ambiguous`)
- Action
- Validation gate

Agent 1 handoff artifact (required):

- A structured plan containing only unresolved-thread decisions and concrete plan entries.
- For each `valid` item: target files, expected behavior, and exact validation command(s).
- For each `invalid`/`outdated` item: rationale text to use when replying/resolving.
- If this artifact is missing or incomplete, do not start Agent 2.
- Compliance gate: verify Agent 1 was executed by a dedicated subagent for this iteration.
- Persist the artifact with:
  - `python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-triage --agent-id <triage-agent-id> --unresolved-decisions "<...>" --action-plan "<...>"`

## Step 3 - Agent 2 implementation and validation

Execute only `valid` plan items:

1. Implement minimal scoped fixes.
2. Run incremental checks for changed scope.
3. Run final agreed checks before commit (prefer repo-standard checks).

Suggested validation sequence in the target repository:

```bash
<project_final_ci_command>
```

If needed for narrower failures, run project-specific lint/typecheck/test commands from that repository's CI or contributing docs, for example:

```bash
<project_lint_command>
<project_typecheck_command>
<project_test_command>
```

Record the exact command(s) used in the implementation artifact via `record-implementation --checks-run`.

Mandatory commit/push gate before any further GitHub interaction:

1. Preferred: run `python3 .cursor/skills/pr-review-loop/scripts/git_barrier.py run --files ... --message-file ...`.
2. If not using the helper, run each command separately (never chained with `&&`):
   - `git add ...`
   - `git commit -m "<message>"`
   - `git push`
   - `git status --porcelain`
3. Verify push succeeded (working tree clean and local branch not ahead of remote).

Autonomy rule for this skill:

- Never execute chained mutation commands like `git add ... && git commit ... && git push`.
- Execute one mutation command per shell invocation, or use the skill-local `git_barrier.py` helper.

Agent 2 handoff artifact (required):

- Final patch/diff summary mapped to Agent 1 `valid` items.
- Validation evidence: exact commands run and pass/fail outcomes.
- Commit/push evidence: pushed commit SHA(s) and clean/ahead status confirmation.
- If this artifact is missing, or push is incomplete, do not start Step 5+ GitHub mutations.
- Compliance gate: verify Agent 2 used a different subagent ID than Agent 1.
- Persist the artifact with:
  - `python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-implementation --agent-id <implementation-agent-id> --checks-run "<project_final_ci_command>" --checks-passed --push-completed --pushed-sha <sha>`

If checks fail and fix is clear, iterate locally; otherwise escalate.

Hard guardrail:

- Do not run any of the Step 5-7 GitHub mutation commands (`replies`, `resolveReviewThread`, `gh pr edit --add-reviewer`, polling for next cycle decisions) until the fix commit is pushed.

## Step 4 - Agent 3 self-review gate

Agent 3 reviews:

- diff quality and unintended changes
- correctness against thread intent
- test/lint/build evidence
- architecture/regression risks

Decision:

- **pass:** continue to thread replies/resolution.
- **fail with actionable issues:** spawn a new planning+implementation cycle in a separate agent.
- **unsolvable/high ambiguity:** escalate to operator and stop.

Agent 3 handoff artifact (required):

- Explicit gate decision: `pass`, `fail with actionable issues`, or `unsolvable/high ambiguity`.
- For `fail`: concrete issue list mapped to files/behaviors and next-cycle fix directives.
- For `pass`: explicit confirmation that no relevant regressions were found.
- If this artifact is not explicit, do not proceed to Step 5.
- Compliance gate: verify Agent 3 used a different subagent ID than Agent 1 and Agent 2.
- Persist the artifact with:
  - `python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py record-self-review --agent-id <self-review-agent-id> --gate pass --notes "<...>"`
- Verify iteration invariants before any GitHub mutation:
  - `python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py verify-invariants`

## Step 5 - Reply and resolve review threads

For each previously unresolved thread now addressed:

1. Refetch each thread before mutating. Only proceed if it is still unresolved and the target issue is still applicable.
2. If the thread is outdated, reply with commit-story rationale for why the comment became outdated, then resolve. Do not reopen implementation for outdated-only feedback unless the thread still identifies a current, reproducible issue.
3. Reply to the thread's latest actionable review comment (`databaseId`) on that PR:

```bash
gh api repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies \
  -f body='<resolution summary>'
```

4. Resolve thread via GraphQL:

```bash
gh api graphql -f query='
mutation($threadId:ID!){
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}' -F threadId='<thread_id>'
```

For invalid comments, reply with rationale and leave unresolved only when policy requires; otherwise resolve after explanation.
For outdated comments, default policy is reply + resolve in the same cycle.

## Step 6 - Request Copilot re-review

```bash
gh pr view <pr_number> --json reviewRequests
gh pr edit <pr_number> --add-reviewer @copilot
```

If Copilot is already requested or already has a recent review in the active cycle, do not fail; proceed to polling and store `copilot_requested_at` for this cycle.

Reviewer-state gate for this step:

- Treat `gh pr view <pr_number>` reviewer status as source of truth.
- Continue to Step 7 only when Copilot shows as **Awaiting for review** (requested reviewer present).
- If Copilot is shown as **Commented** (or otherwise not awaiting), issue `gh pr edit <pr_number> --add-reviewer @copilot` and verify it returns to **Awaiting for review** before polling.

Preferred command:

```bash
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py request-copilot
```

## Step 7 - Timed Copilot polling

Poll every 3 minutes for up to 15 minutes. Depending on timing, this can result in up to 6 polling attempts within the 15-minute window (for example at minutes 0, 3, 6, 9, 12, and 15). If API calls fail transiently or hit secondary rate limits, retry with bounded backoff and continue only within the 15-minute window.

At each poll:

1. Fetch PR reviews and relevant comments:
   - `gh api repos/<owner>/<repo>/pulls/<pr_number>/reviews`
   - `gh api graphql ... reviewThreads ...`
2. First check reviewer status from `gh pr view <pr_number>`:
   - while Copilot is **Awaiting for review**, keep polling (review still pending);
   - when Copilot switches out of **Awaiting for review** (typically to **Commented**), treat that transition as review completion for the latest request and then inspect new review activity/comments.
3. Detect new Copilot review activity after `copilot_requested_at` (author `copilot-pull-request-reviewer[bot]` or `copilot-pull-request-reviewer`).
4. If Copilot reviewed, re-check unresolved threads:
   - if unresolved exist: increment `loop_count` and restart at Step 2.
   - if none: finish successfully.

If no Copilot review by timeout, stop and report timeout outcome.

Preferred command:

```bash
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py poll-copilot --interval-minutes 3 --timeout-minutes 15
```

## Terminal finalize gate (mandatory)

After role artifacts are complete and invariant checks pass, run:

```bash
python3 .cursor/skills/pr-review-loop/scripts/loop_runner.py finalize --interval-minutes 3 --timeout-minutes 15
```

`finalize` outcomes:

- `success`: fresh post-fix Copilot cycle completed for the implementation `pushed_sha` and unresolved threads are `0`.
- `needs_loop`: post-fix cycle completed but unresolved threads remain, or freshness proof is invalid.
- `timeout`: polling window expired.
- `drifted`: PR head changed vs implementation `pushed_sha`.
- `cap_exceeded`: iteration 11 attempted (cap is inclusive 1..10).

## Hard stop conditions

Stop and escalate to operator when:

- loop count reaches 10
- issue is unsolvable with local context/permissions
- ambiguity is high and materially affects correctness
- required command/tool is unavailable
- PR head SHA drifted during execution; restart loop from fresh triage snapshot
- repeated API failures exhausted bounded retries

Escalation report must include:

- blocking issue
- attempted actions
- exact errors/evidence
- minimum decision needed from operator

## Execution checklist

- [ ] PR context resolved and branch synced
- [ ] Unresolved threads fetched from GraphQL
- [ ] Agent 1 triage + plan produced
- [ ] Agent 2 implemented valid fixes and ran checks
- [ ] Agent 3 self-review passed (or looped)
- [ ] Fix changes committed and pushed to PR branch before further GitHub mutations
- [ ] Replies posted and applicable threads resolved
- [ ] Copilot requested with `@copilot`
- [ ] Polling completed (review received or timeout)
- [ ] Loop exited by success or explicit stop condition
- [ ] Iteration compliance audit logged (distinct agent IDs, role ownership, hard-gate status)
