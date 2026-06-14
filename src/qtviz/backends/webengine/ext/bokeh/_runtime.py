"""JS that handles Bokeh-namespaced commands from Python.

Event forwarding is set up Python-side via `CustomJS` callbacks injected onto
the figure (see `backend.py::_instrument`). This module only handles the
Python -> JS command path (patch a ColumnDataSource, stream new rows, set a
property).
"""

BOKEH_JS = r"""
(function () {
  function waitForBokeh(cb) {
    if (window.Bokeh && Bokeh.documents && Bokeh.documents.length) { cb(); return; }
    setTimeout(function () { waitForBokeh(cb); }, 20);
  }

  // BokehJS doesn't expose a single stable `select`-by-name API across
  // versions. Walk every document and every model, matching on `.name`.
  function findByName(name) {
    if (!window.Bokeh || !Bokeh.documents) return null;
    for (let i = 0; i < Bokeh.documents.length; i++) {
      const doc = Bokeh.documents[i];
      if (!doc) continue;

      // Preferred: 3.x exposes get_model_by_name on the document.
      if (typeof doc.get_model_by_name === "function") {
        try {
          const m = doc.get_model_by_name(name);
          if (m) return m;
        } catch (e) { /* fall through */ }
      }

      // Fallback: iterate the document's model map. Across versions this
      // shows up as `_all_models` (Map), `models` (Map), or a plain object.
      const candidates = [];
      if (doc._all_models) candidates.push(doc._all_models);
      if (doc.models) candidates.push(doc.models);

      for (let c = 0; c < candidates.length; c++) {
        const all = candidates[c];
        if (!all) continue;

        if (typeof all.values === "function") {
          for (const m of all.values()) {
            if (m && m.name === name) return m;
          }
        } else if (typeof all.forEach === "function") {
          let found = null;
          all.forEach(function (m) { if (m && m.name === name) found = m; });
          if (found) return found;
        } else {
          for (const id in all) {
            const m = all[id];
            if (m && m.name === name) return m;
          }
        }
      }
    }
    return null;
  }

  qtwebplot.onReady(function () {
    qtwebplot.on("bokeh.patch", function (p) {
      const src = findByName(p.name);
      if (!src) { console.warn("[bokeh] no source named", p.name); return; }
      src.data = p.data;
      if (src.change && typeof src.change.emit === "function") src.change.emit();
    });

    qtwebplot.on("bokeh.stream", function (p) {
      const src = findByName(p.name);
      if (!src || typeof src.stream !== "function") {
        console.warn("[bokeh] cannot stream to", p.name); return;
      }
      src.stream(p.data, p.max_points || undefined);
    });

    qtwebplot.on("bokeh.set_property", function (p) {
      const model = findByName(p.name);
      if (!model) { console.warn("[bokeh] no model named", p.name); return; }
      model[p.property] = p.value;
    });

    waitForBokeh(function () {
      qtwebplot.send("bokeh.attached", {ok: true});
    });
  });
})();
"""
