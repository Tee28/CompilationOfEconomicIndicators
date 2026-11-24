---
name: econ-probe
description: P0 probe of Claude Code behaviour on this machine - hooks, agent_type, nested spawning, skill commands, token logging.
disable-model-invocation: true
shell: bash
---
!`python econ.py probe enable --soft`
!`python econ.py probe mark skill-bang --soft`

The two lines above enabled the probe (note the nonce) and recorded that skill `!` commands run.
Now do exactly this, in order, without editing any file:

1. Read `.econ/probe/big.txt` WITHOUT offset/limit. The token guard should DENY it - that is the expected
   result; do not retry with a slice.
2. Spawn the `probe-manager` agent with the prompt `Run the probe. NONCE=<nonce>`.
3. When it has finished (you are notified if it runs in the background), run `python econ.py probe report`.
4. Run `python econ.py probe disable`.
5. Report to the user in Vietnamese, max 10 lines: every FAIL/WARN with its fallback, and what that means
   for the agent setup (nested managers, ownership guard, token log).
