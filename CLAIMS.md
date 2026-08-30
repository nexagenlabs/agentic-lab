# CLAIMS.md

Behavioural claims the book makes about this repository.

The listings conformance gate checks that printed code blocks match the
repository. It cannot check the prose. This file holds every claim the
book's text makes about what the code *does*, so those can be verified
too.

Each claim is written as a statement that is either true of the code or
not. Verify each one by reading the code and running it, not by reading
the spec or the README, which are as capable of being wrong as the book
is. Where a claim cannot be verified, say so rather than assuming.

Report per claim: TRUE, FALSE, or UNVERIFIABLE, with the file and line
that decides it.

A FALSE is a finding about the book, not about the code. Do not change
code to make a claim true without saying so.

---

## Chapter 1, no build

- C1.1 The book states that a run terminating exactly at its step cap
  should be treated as failed. Every build that has a step cap must
  distinguish "completed" from "hit the cap", and no build may return an
  answer on the latter.

## Chapter 2, no build

- C2.1 The book says every build reads its model name from a single
  configuration file, and that a model change is one line rather than
  forty. Verify: in each build, count the places a model name string
  appears outside a stage file.
- C2.2 The book says tool definitions in plain JSON schema carry over
  between the raw SDK and frameworks almost unchanged. Verify the tool
  declarations in Builds 01, 02 and 03 are plain schema and not
  framework-specific objects.

## Chapter 3, Builds 01 and 02

- C3.1 The loop "fits in about sixty lines". Count the non-blank lines
  of `run_agent` in `stage3.py`. The book says the printed loop is 28
  non-blank lines and that it remains recognisable inside `agent.py`.
- C3.2 "Six of those seven steps are ordinary software, and the model
  appears only at steps two, four and six." Count the model calls in one
  full turn of the loop. There should be exactly one.
- C3.3 On step exhaustion, the loop returns `INCOMPLETE` with
  `answer: None`, and never a partial summary.
- C3.4 The budget is checked **before** the model call, not after.
- C3.5 Retries count against the step budget, so a nested loop cannot
  hide from the ceiling.
- C3.6 A 429 retries and a 400 never does.
- C3.7 After three consecutive failures from one tool, that tool is
  disabled for the rest of the run and the model is told so.
- C3.8 Every error path returns a structured object with a `status`
  field. No error is returned to the model as prose.
- C3.9 The trace is JSONL, one event per line, and records the model
  version, each tool request with arguments, each result with status,
  and the terminating condition.
- C3.10 In Build 02, a malformed call never enters the function body.
  Verify by a test that the function raises on entry and is not reached.
- C3.11 In Build 02, the tool declaration's `input_schema` is generated
  from the Pydantic model rather than hand-written.
- C3.12 Build 02 declares at least two tools, and each description
  contains an explicit negative case naming its sibling.

## Chapter 4, Builds 03 and 04

- C4.1 Criteria live in a versioned YAML file, not in a prompt string,
  and a criteria file failing validation halts the run rather than
  falling back to a default.
- C4.2 `criteria_version` is stamped on every verdict.
- C4.3 Scoring two screens under different criteria versions raises.
- C4.4 The loop is driven by an explicit list of identifiers, and an
  unscreened record is a logged gap rather than an absence.
- C4.5 Totals are computed in Python. The agent is never asked how many
  records it screened.
- C4.6 On ambiguity the verdict is `flag` with low confidence, never a
  guess.
- C4.7 Accuracy is refused with an explanatory message, not merely
  omitted.
- C4.8 The gold set is defined by a rule, not a hard-coded size, and its
  seed is recorded.
- C4.9 A record appearing in two gold-set categories appears once.
- C4.10 Kappa, PABAK and Gwet's AC1 are all computed, and a test asserts
  them against fixture values known in advance.
- C4.11 `same_agent_twice` raises without an explicit acknowledgement.
- C4.12 Disagreements go to adjudication and none is resolved
  automatically.
- C4.13 The book says the two screens must be independent. Verify
  structurally: can screen B read screen A's verdicts at any point?

## Chapter 5, Build 05

- C5.1 "The agent never touches a number." Verify no model output is
  used as a numeric value anywhere in the transform path.
- C5.2 The agent sees the first fifteen lines and a shape summary, never
  the whole file.
- C5.3 `apply_mapping` raises on a mapping whose `approved_at` is unset.
- C5.4 Everything is read as text, with `keep_default_na=False`, so the
  string NA is not converted to a null.
- C5.5 Units live in column names. Verify no numeric column in the
  schema lacks a unit suffix where one is meaningful.
- C5.6 All six assertions from Table 5.2 exist and each raises a named
  exception identifying which assertion failed.
- C5.7 Row conservation permits removal with a logged reason and forbids
  silent absence.
- C5.8 A transposed plate passes the schema and fails the identifier
  integrity assertion. This is the chapter's failure account and must be
  demonstrably true.
- C5.9 The same input produces byte-identical output including column
  order.
- C5.10 Merging a micromolar and a nanomolar column raises rather than
  concatenating.

## Chapter 6, Builds 06 and 07

- C6.1 The design file is validated before any layout is produced, and a
  design naming a cell line without an RRID is rejected.
- C6.2 The synergy model is named with a written justification and a
  timestamp, and a commitment later than the earliest reading fails.
- C6.3 `choose_synergy_model()` raises. The system does not select one.
- C6.4 A consensus request containing both Bliss and ZIP is rejected.
- C6.5 The dilution check tests solvent percentage at the top dose,
  transfer volume against the pipetting minimum, and whether the series
  spans the expected IC50.
- C6.6 The printed design fits its plate: treatment wells plus controls
  plus excluded perimeter equals the plate format. The book says 40
  combinations plus 12 controls fit in 60 interior wells.
- C6.7 Each replicate gets its own plate, rather than replicates being
  packed end to end.
- C6.8 Layout randomisation is reproducible from a recorded seed, and a
  different seed produces a different layout.
- C6.9 In Build 07, every parameter in Table 6.2 appears in exactly one
  of the four lists. Silence about any of them is an error.
- C6.10 An ambiguous source parameter is treated as not stated rather
  than interpreted.

## Chapter 7, Build 08

- C7.1 No method returns a predicted affinity. Any that would must raise
  with an explanatory message.
- C7.2 A result set containing both EXPERIMENTAL and PREDICTED entries
  raises unless an explicit flag is passed, and the flag reaches the
  manifest.
- C7.3 A comparison set built from two different box strategies raises.
- C7.4 `prediction_confidence` is specified over the pocket, not the
  whole chain.
- C7.5 Preparation decisions have no defaults: protonation, waters,
  metals, tautomer.
- C7.6 The full pose distribution is retained, not just the top pose,
  and an outlier is distinguishable from a cluster.
- C7.7 The redocking control recovers a known pose within two angstroms.
- C7.8 Enrichment is measured against property-matched decoys.
- C7.9 The seed and exhaustiveness are recorded and a run replays from
  the manifest.
- C7.10 No test requires AutoDock Vina to be installed.

## Chapter 8, Build 09

- C8.1 The client exposes no update and no delete method, at the
  interface level rather than as policy.
- C8.2 No write reaches the client while a proposal is unapproved, and
  an approval with an empty approver name is not an approval.
- C8.3 Everything read is wrapped as untrusted content.
- C8.4 A numeric value in a proposal is checked against the design file
  and mismatches are flagged before a human sees the diff.
- C8.5 The local ledger is append-only and every notebook entry has a
  corresponding approved proposal.
- C8.6 Scope is enforced before a request is formed, not after.
- C8.7 The book claims six injection fixtures are all flagged. Verify
  the detection rate independently, and check whether the stub model is
  credulous enough for the test to be non-vacuous.

## Chapter 9, Build 10

- C9.1 Audit replay reproduces every output hash with the model client
  and HTTP transport patched to raise, and the patch is proven to bite
  before the replay runs.
- C9.2 Inputs are addressed by content hash, not filename, and altering
  one byte halts verification naming the file.
- C9.3 External responses are hashed, so database drift is detectable.
- C9.4 `git_dirty` is recorded and disclosed rather than blocking.
- C9.5 A run at its step cap records INCOMPLETE with a halt reason and a
  downstream consumer refuses to treat it as finished.
- C9.6 The difference report attributes divergence to code, model or
  world, and for the drifted fixture attributes it to the world and
  states that neither run was wrong.
- C9.7 `manifest.describe()` names the corpus snapshot, the commit and
  the model versions.

## Chapter 10, Build 11

- C10.1 A missed fault that completes normally is counted separately
  from one that crashes.
- C10.2 The detection rate is always reported with its denominator.
- C10.3 Citation checking resolves references against a metadata source
  rather than checking that they look right.
- C10.4 Drift is detected by comparing against the original instruction,
  not the previous step.
- C10.5 Every family contains a fault known to be caught and one known
  to be missed, and both are asserted.
- C10.6 Negative controls do not fire.
- C10.7 A family can be registered at runtime without editing the model.
- C10.8 The book reports 11 of 25 caught by the earlier builds alone,
  and all fourteen misses silent. Verify both numbers.

## Chapter 12, Build 12

- C12.1 Exactly three stages are agent loops, asserted behaviourally
  rather than by counting imports.
- C12.2 No stage downstream of an unapproved checkpoint executes, and
  the prohibition is proven to bite.
- C12.3 A full desk run replays offline from its manifest.
- C12.4 The routed run costs roughly an order of magnitude less than
  all-frontier, and the shortlist is unchanged between them.
- C12.5 Every Table 12.3 refusal raises with an explanation.
- C12.6 There is no coordinator delegating to specialist agents.
- C12.7 The book states the desk's shortlist contains no antiparasitic
  because the corpus does not suit the question. Verify this is still
  true and has not been quietly fixed.

---

## Cross-cutting

- X.1 No test anywhere touches the network. The three tools do, by
  design, and are not collected by pytest.
- X.2 No test passes because a stub is well behaved. Sample five tests
  that assert something cannot happen and confirm each was proven to
  bite.
- X.3 Every build runs from a clean clone with no API key present.
- X.4 No build imports from another build.
- X.5 The repository contains no em dashes or en dashes, in code,
  comments, documentation or fixtures.
