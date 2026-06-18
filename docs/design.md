# Design notes

qtviz is designed in the open. The full specification, development plan, milestone
notes, and a decision log live in the repo's
[`design/`](https://github.com/jawjay/qtviz/tree/main/design) directory.

Good starting points:

- **[`spec.md`](https://github.com/jawjay/qtviz/blob/main/design/spec.md)** — the
  concrete specification: the `Element` model, the data layer, backends, events.
- **[`roadmap.md`](https://github.com/jawjay/qtviz/blob/main/design/roadmap.md)** —
  phases, architecture, and what ships in `0.1`.
- **[`development-plan.md`](https://github.com/jawjay/qtviz/blob/main/design/development-plan.md)**
  — design invariants, the build sequence, and the verification strategy (tiered tests
  + a backend/adapter conformance suite).
- **[`discussion-items.md`](https://github.com/jawjay/qtviz/blob/main/design/discussion-items.md)**
  — the decision log (`[D#]`): every non-obvious choice, its options, and the rationale.

## Core ideas

- **Pure, value-hashed `Element`s.** An Element says *what* to plot, not *how*; it
  carries no Qt and no backend state, so it is trivially testable and composable.
- **Registered backends and data adapters.** The core never imports a backend or a
  container library — each is registered, so adding an engine or a data container is
  purely additive.
- **Lazy-first data layer.** One `DataRef` contract covers eager and out-of-core
  containers; expensive resolution runs off the GUI thread.
- **Offline by construction.** No network at render time; the webengine backend
  bundles its JavaScript from the installed packages.
