# How this was built: a spec-first AI workflow

This repository was built with [Claude Code](https://claude.com/claude-code)
as the implementing engineer and me as the designer and reviewer. I use AI
heavily, and the division of labour mirrors the library's
own core principle: code for the tedium, humans at the fragile points. The
fragile points in AI-assisted work are specification and verification; the
tedium is everything in between.

## Specification before code

For every data source I automate, the working sequence is:

1. I write a prose diagnostic of the source's methodology first: where the
   data lives, what transformations are required, what the previous
   methodology got wrong, and which parts of the layout I judge fragile.
2. The agent proposes the safety-check design in plain language: which
   checks, catching which failure modes, surfacing what to whom.
3. Only after I've approved the intuition does any code get written.

The order matters. Reviewing a check design in prose takes minutes and
catches wrong assumptions while they're still cheap; reviewing the same
assumptions after they're encoded in 300 lines of Python is slower and
biased toward approval. The expensive artifact to get right is the
specification, precisely because the code has become cheap.

## Verification without redoing the work

I don't re-derive the agent's outputs by hand; that would forfeit the
speed, and redoing the same work by the same method has the same blind
spots anyway. Instead, every write is verified structurally:

- every batch of changes produces a changelog (cell, old value, new value,
  reason) that I can scan in seconds and archive as an audit trail;
- outputs are verified by reading back the committed file rather than by
  trusting that the write happened as intended; I have watched a stale
  buffer silently revert a whole section, and "the code ran without error"
  is not evidence of anything;
- test suites and benchmark runs (see
  [design-principles.md](design-principles.md)) gate everything the agent
  produces, exactly as they would gate my own code.

## Context is an artifact worth engineering

The repository carries a [CLAUDE.md](../CLAUDE.md) with the project's
conventions and non-negotiable rules, so any future session starts already
knowing that alignment is by label, that reports are exceptions-only, and
that fuzzy matching is banned. On longer projects I maintain handoff
documents that let a fresh session (or a fresh human) inherit settled
design decisions instead of relitigating them. Treating the AI's context
as an engineering artifact in its own right is, in my experience, the
habit that has paid off most in this way of working.
