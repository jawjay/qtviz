# Security policy

## Supported versions

The latest 2.x release receives fixes. Older versions are not maintained.

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub's private vulnerability reporting](https://github.com/jawjay/qtviz/security/advisories/new)
— not in a public issue. This is a best-effort, single-maintainer project;
you can expect an initial response within a couple of weeks.

## Scope notes

- qtviz renders **local data, 100% offline by construction** — there is no
  network access at render time, no telemetry, and no remote content loading.
- The webengine backend embeds Chromium via Qt WebEngine and injects
  JavaScript bundled from your locally installed `plotly`/`bokeh` packages.
  Issues in how the Qt↔JS bridge handles figure payloads are in scope.
- Vulnerabilities in the underlying engines (Qt/Chromium, plotly.js, BokehJS,
  matplotlib, pyqtgraph) should be reported to those projects; qtviz will
  track affected version floors where relevant.
