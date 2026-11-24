---
name: gate
description: Review a phase gate (G0-G4) - deterministic checks, evidence summary, Owner approval, decision log.
argument-hint: "G0|G1|G2|G3|G4"
disable-model-invocation: true
shell: bash
---
!`python econ.py gate check $ARGUMENTS --soft`
!`python econ.py log tail -n 5 --soft`

Gate requested: $ARGUMENTS

1. If the check lists missing items: tell the Owner (Vietnamese, <= 6 lines) what is missing and who owns
   each item; offer to create tasks (`python econ.py task add ...`). Stop there.
2. If READY: summarise the evidence for this gate in <= 8 lines (what was built, test status, open risks;
   for G3 include n_eff and skill vs baseline per model from docs/models/). Then ask with AskUserQuestion:
   approve / approve with conditions / reject.
3. On approval: `python econ.py gate approve $ARGUMENTS --note "<conditions>" --stage <next phase>`.
   On rejection: `python econ.py log decision "<reason>" --gate $ARGUMENTS` and create fix tasks.
Never approve without the Owner's explicit answer.
