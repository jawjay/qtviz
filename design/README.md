# design/ — qtviz is designed in the open

This directory is the project's design corpus: the specification, the
architecture records, the decision log, and the research notes behind the
code. Code comments, commits, and tests reference decisions by their `[Dnn]`
tags — every tag resolves to an entry in [`discussion-items.md`](discussion-items.md)
or one of the architecture documents below.

## Reading order

1. [`spec.md`](spec.md) — the canonical specification: the Element model, the
   backend contract, the data layer, events, theming.
2. [`architecture.md`](architecture.md) — how the packages fit together.
3. [`2.0-mark-ir-and-surface.md`](2.0-mark-ir-and-surface.md) — the 2.0
   architecture: the Mark IR, the uniform channel vocabulary, and the §8
   record of what actually shipped.
4. [`development-plan.md`](development-plan.md) — the invariants and the
   verification strategy (tiered tests, conformance suite, honesty guards).

## The decision log

[`discussion-items.md`](discussion-items.md) holds the numbered decisions
([D1]–[D60] in full; later decisions live in the document for their arc —
e.g. [`2.0-mark-ir-and-surface.md`](2.0-mark-ir-and-surface.md) for
[D121]–[D136], [`public-release.md`](public-release.md) for [D137]–[D144]).

## Research notes

- [`matplotlib-support-matrix.md`](matplotlib-support-matrix.md) — what the
  matplotlib backend renders, feature by feature.
- [`webengine-arrow-transport.md`](webengine-arrow-transport.md) /
  [`webengine-rehome.md`](webengine-rehome.md) — the Qt↔JS bridge design.
- [`dask-datashader-research.md`](dask-datashader-research.md) — the
  big-data path.
- [`native-pivot-research.md`](native-pivot-research.md),
  [`axis-surface-feasibility.md`](axis-surface-feasibility.md) — feasibility
  studies behind shipped features.

## archive/

[`archive/`](archive/) preserves the working notes — milestone plans,
roadmaps, audits, retrospectives — exactly as they were written during
development. They contain point-in-time statuses and are superseded by the
documents above and the [docs site](../docs/); kept because the CHANGELOG and
the decision log cross-reference them.
