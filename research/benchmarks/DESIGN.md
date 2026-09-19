# Benchmark corpus design and adjudication

This is a reviewed descriptive foundation for a future exact structured
defect-detection benchmark. It contains 24 synthetic, independently reviewable
fixtures: eight each for React, Next.js, and React Native. Every label names a
catalog rule, cites public source lines, records the public assumptions needed
to assess it, and cites an official primary source. This is corpus
adjudication, not provider execution or a human-expert certification.

The corpus has five intentional-clean restraint controls: `react-06`,
`next-02`, `rn-01`, `rn-02`, and `rn-07`. Their `ADVERSARIAL` difficulty means
they are designed to attract unsupported advice; it does not mean they contain
a hidden defect.

The candidate and baseline receive the same source context, rule catalog,
response schema, evidence-span contract, and permission to return no findings.
The candidate treatment adds only the committed inline `SKILL.md`. Referenced
rubrics, agents, router material, and external skills are excluded from both
prompts.

No provider pilot, capture, model comparison, or aggregate run exists in this
repository. The corpus therefore supports no performance, provider-authenticity,
severity-quality, full-skill, or statistical claim. Historical benchmark
reports remain rejected rather than evidence of the redesigned corpus.
