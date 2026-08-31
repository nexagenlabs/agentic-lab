# Templates

Introduced in **Chapter 11** of *The Agentic Lab*, and reached from
`lab.nexagenlabs.com/ch11`.

Chapter 11 ships no build. What it ships is paperwork: the documents that
belong around an agent rather than inside it. Three templates live here, and
two of them are asked for by earlier chapters, because the paperwork is not
something you start at the end.

| File | Asked for by | What it is |
| --- | --- | --- |
| `context_of_use.md` | Chapter 11 | A form you fill in for one of your own agents. |
| `screen_report.md` | Chapter 4 | The shape of a screening report, with fields a run fills in. |
| `stack.yaml` | Chapter 2 | The Stack Inventory: seven rows, one per thing an agent is made of. |

## `context_of_use.md` is a form, not an example

This is the one most likely to be misread. It is not a filled-in specimen to
copy and adapt, and there is no worked example of it anywhere in this
repository on purpose. It is a blank form, and the answers have to be yours:
the question of interest, the context of use, how much of the decision the
model influences, what happens when it is wrong, what evidence you have, and
who reviews it and when.

One page. If it cannot be completed, the finding is not that the paperwork is
hard. It is that the project is underspecified, and learning that before
building is worth more than the page.

The chapter's argument for narrowing it honestly is worth repeating here,
because it is counterintuitive: a vague context of use does not reduce your
obligations, it maximises them, since an assessor has to read it at its
broadest. Narrowing it costs nothing, needs no engineering, and is usually
just an accurate description of a system that was always narrower than the
first sentence claimed.

Copy it, fill it in for one agent, and commit it beside that agent's criteria
file and design file so it is versioned with everything else.

## `screen_report.md` has a program that fills it in

`builds/04-dual-screen/report.py` writes this template out from an actual run,
called by `scoring.py` at the end of a scored screen, so the copy here is not
the only way to get one. It exists so the shape can be read without running
anything, and so it can be adapted for a screen built outside this repository.

Its placeholders are in `{braces}` and everything below the rule is pasteable
into a methods section once they are replaced. Where a field cannot be filled,
the row stays and stays empty: an empty row is a question somebody can ask, and
a deleted row is one nobody knows to ask.

## `stack.yaml` is the template the builds are held to

Chapter 2's Stack Inventory. Seven rows: `model`, `tools`, `working_memory`,
`episodic_memory`, `reference_memory`, `orchestration` and `trace`.

Every build in this repository emits one of these from its own `stack.py`,
derived from its code rather than written from memory, and
`tests/test_stack_inventory.py` refuses an inventory with a row missing. The
questions in this file are the ones those emitted inventories carry, word for
word, and that test holds them to it.

The rule that makes it worth keeping: an unanswered row is written
`UNSPECIFIED` rather than left blank or left out. A blank row reads as a
system with nothing in that position and an absent row reads as a question
nobody thought to ask, and an unanswered row means neither. It means nobody
decided, and a step nobody decided is not a default.
