"""JS that wires Plotly events through the core bridge and registers
Plotly-flavored command handlers.

Runs after the core bridge bootstrap. Waits for both the bridge handshake and
for the plot div to exist, then attaches event handlers.
"""

PLOTLY_JS = r"""
(function () {
  function findDiv() {
    // qtwebplot.plot_div_id can be set by the backend; default to "qtwp-plot".
    const id = (window.qtwebplot && window.qtwebplot.plot_div_id) || "qtwp-plot";
    return document.getElementById(id);
  }

  function sanitizePoint(p) {
    if (!p) return null;
    return {
      trace_index: p.curveNumber,
      point_index: p.pointIndex !== undefined ? p.pointIndex : (p.pointNumber !== undefined ? p.pointNumber : null),
      x: p.x === undefined ? null : p.x,
      y: p.y === undefined ? null : p.y,
      z: p.z === undefined ? null : p.z,
      text: p.text === undefined ? null : p.text,
      curve_number: p.curveNumber,
    };
  }

  function sanitizeEvent(data) {
    if (!data) return {points: [], raw: {}};
    const pts = (data.points || []).slice(0, 1000).map(sanitizePoint).filter(Boolean);
    let range = null;
    if (data.range) range = data.range;
    return {points: pts, range: range};
  }

  function attach(div) {
    // JS -> Python event forwarding.
    div.on("plotly_hover",    function (d) { qtwebplot.send("plotly.hover",     sanitizeEvent(d)); });
    div.on("plotly_unhover",  function (d) { qtwebplot.send("plotly.unhover",   sanitizeEvent(d)); });
    div.on("plotly_click",    function (d) { qtwebplot.send("plotly.click",     sanitizeEvent(d)); });
    div.on("plotly_selected", function (d) { qtwebplot.send("plotly.selection", sanitizeEvent(d)); });
    div.on("plotly_relayout", function (u) { qtwebplot.send("plotly.relayout",  {update: u}); });

    // Python -> JS command handlers.
    qtwebplot.on("plotly.react", function (p) {
      Plotly.react(div, p.data || [], p.layout || {}, p.config || {});
    });
    qtwebplot.on("plotly.restyle", function (p) {
      Plotly.restyle(div, p.update || {}, p.indices === null ? undefined : p.indices);
    });
    qtwebplot.on("plotly.relayout", function (p) {
      Plotly.relayout(div, p.update || {});
    });
    qtwebplot.on("plotly.extend", function (p) {
      Plotly.extendTraces(div, p.update || {}, p.indices || [], p.max_points || undefined);
    });
    qtwebplot.on("plotly.resize", function () {
      Plotly.Plots.resize(div);
    });

    qtwebplot.send("plotly.attached", {ok: true});
  }

  function waitForPlot() {
    const div = findDiv();
    if (div && div.on && div.data) { attach(div); return; }
    setTimeout(waitForPlot, 20);
  }

  qtwebplot.onReady(function () {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", waitForPlot);
    } else {
      waitForPlot();
    }
  });
})();
"""
