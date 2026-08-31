# Design principles

This library condenses what I learned automating the annual update of a
financial-markets statistical publication — a few hundred tables compiled
every year from central-bank APIs, exchange federations, and downloaded
spreadsheets, where each year's editor retraces the previous editor's
methodology, evaluates it critically, and applies it to the new year. All
code here is written from scratch on public data; what carries over is the
thinking. This document is that thinking.

## The threat model: plausible-but-wrong

A pipeline that crashes is a solved problem — you see the traceback, you fix
it. The failure mode that actually costs you is the number that is *wrong
but plausible*: an annual total built from eleven months instead of twelve,
a value converted at the year-average exchange rate when the methodology
says end-of-year, a country whose data landed one row up because the source
inserted a spacer row. Every one of these survives a visual scan. Some
survive an audit. The design question is never "how do I detect errors?" in
the abstract — there is no universal error detector — but "which *classes*
of silent error can I make structurally impossible or loudly visible, every
run, by default?"

## Code for data entry, humans for judgment

Deterministic code is auditable but brittle to changes in source format;
human judgment is robust but expensive and inconsistent. So the division of
labour is not "automate as much as possible" — it is: put the code where the
work is tedious (copying, converting, summing) and put the human exactly at
the fragile points (mapping a source to a target, deciding whether a flagged
discrepancy is an error or an event). A pipeline that asks the human to do
tedium will be rushed; one that asks the code to make judgment calls will be
confidently wrong.

## Checks are free, questions are expensive

The scarce resource in a human-in-the-loop pipeline is not compute — it is
the reviewer's attention. So the budget is measured in *interactions*, not
in number of checks. Run every check on every run, silently; surface only
exceptions. A clean run should cost one glance and one line: "identity
holds; benchmark clean; no tolerance flags." The alternative — a
confirmation prompt per table — trains the reviewer to rubber-stamp, and a
rubber-stamped check protects nothing. This inverts the intuitive design
("show the human everything, to be safe") on the observation that showing
everything and showing nothing converge to the same behaviour.

## Landmarks, not coordinates

Never anchor a parser to a coordinate ("data starts at row 8"). Anchor it to
what the file itself asserts — the header text, the row labels — and derive
the coordinates from that. The failure this prevents is specific and I have
watched it happen: a parser written against a *hand-edited working copy* of
a source file (two extra note rows typed above the table) runs against the
clean download, scans past the first countries, and emits them as missing —
no error, and the downstream aggregates quietly understate. Two corollaries:

- Vintage working files may be hand-modified; never infer a source's layout
  from anything but a clean download.
- A run of fresh missing values at the *top* of a table is the signature of
  a parsing bug, not a fact about the world. Real coverage losses do not hit
  exactly the rows a broken offset would skip.

The same principle governs writing: values transfer to a target by matched
row *label*, never by position. Positional pasting fails three independent
ways I have found in the wild — spacer rows present in one file and not the
other, one table ordering a block differently from its siblings, and a
source emitting rows the target deliberately omits — and every one of them
misaligns silently. Label matching turns all three into explicit "unmatched"
lists. Where names legitimately differ ("Korea" vs "Korea, Rep."), the
bridge is a *declared* alias, never fuzzy matching: guessing the mapping is
precisely the judgment call the code must not make on the human's behalf.

## Each series is its own null hypothesis

To decide whether a new value is suspicious, a flat threshold ("flag moves
over 25%") is simultaneously too noisy and too permissive, because series
volatilities differ by orders of magnitude: derivatives turnover doubling is
routine; a large economy's outstanding debt moving a quarter is front-page
news. So the threshold comes from the series itself: take the row's own
historical year-on-year changes, and flag the new change when it falls
outside two standard deviations of that history. Volatile rows earn wide
bands, stable rows tight ones, with zero per-row configuration.

Two caveats belong in the design, not a footnote. A σ estimated from a
handful of changes is noise, so below a minimum history the check falls back
to a flat band rather than pretending to rigor. And financial series are
fat-tailed — historical shocks inflate σ and desensitise the test — so the
band is a triage tool that under-flags relative to a normal distribution,
not a hypothesis test. Separately, transitions between data and missing are
flagged unconditionally: no magnitude test can see a value that vanished.

## Classify discrepancies by pattern, not magnitude

When a rebuilt table disagrees with the reference version, the *size* of the
disagreement says almost nothing about its cause, and thresholding on size
gets it exactly backwards. The case that convinced me: a uniform 0.5–1%
discrepancy across every country — far below any sane threshold — turned out
to be a wrong exchange-rate convention (annual-average instead of
end-of-period), a genuine methodology error. Meanwhile a 30% swing in one
country was a legitimate retroactive revision. What identifies the cause is
the shape of the disagreement across rows:

- the same ratio everywhere is a multiplicative slip — FX, units, scaling —
  and printing the implied ratio often names the culprit on sight (≈1000 is
  a units error; ≈1.01 smells like an FX convention);
- a shared sign with varying size is an additive slip — a component omitted
  or double-counted in one of the two methodologies;
- mixed signs, scattered, mostly exact matches — consistent with source
  revisions; rank the largest few for a glance and move on;
- exact zeros everywhere — say so, once. Positive signals are cheap and
  build calibrated trust.

Patterns narrow where to look; attribution still means opening the source.
The win is that whole classes of error are *detected* every run by default,
instead of depending on someone happening to notice.

## Reproduce yesterday before trusting today

The strongest regression test a data pipeline can have is one it gets for
free: re-extract a period whose answers already exist — last year's
published edition — through *exactly* the code path that will produce the
new period, and compare. A clean benchmark licenses trust in the new
numbers, because they flow through a path just validated on known answers.
A special-cased benchmark path would test the special case.

Two subtleties make this workable rather than naive. First, sources revise
data retroactively, so a perfect match is not the bar: the benchmark
validates the *pipeline*, not the values, and revisions inject exactly the
mixed-sign idiosyncratic noise the pattern classifier is calm about, while
pipeline bugs produce structure. Second, the reference embodies a
methodology, not the truth — it may carry its author's inherited error — so
a flag means "these methodologies differ", not "you are wrong". Which one is
right is the human's call, made with the pattern as evidence.

Coverage is diffed alongside values, because an absence is invisible unless
something owns an expected list: "this country reported last year and is
missing now — confirm?" is a question the pipeline must ask, since no one
spots a hole they aren't looking for.

## What diff-based checks structurally miss

An error shared by both methodologies — inherited from the previous edition
and faithfully reproduced — produces a zero diff. Manual re-checking has the
same blind spot, so re-verifying by hand adds no coverage; what helps is a
check of a *different kind*, whose blind spots don't overlap: reconciling
against identities the source itself publishes (in the demo: euro-denominated
plus foreign-currency issuance must equal the published total), comparing
country sums against published aggregates, and a once-a-year review of each
series' precise definition at the moment of confirmation.

## Fabrication is worse than absence

A pipeline must never write a placeholder where a number belongs — no
carried-forward value, no interpolation it wasn't asked for, no "0" standing
in for unknown. A visible gap invites a question; a fabricated cell answers
it, wrongly, in a way nobody thinks to re-ask. The same discipline applies
at the end of the run: verify what was actually written to the output file
by reading it back, not what the code intended to write — buffered writes
and stale file handles can silently revert a section, and intent is not
evidence.
