"""JS bootstrap for the core bridge.

The string `CORE_JS` is injected into every hosted page. It assumes
`qwebchannel.js` is already loaded (we ensure that by injecting it just before
this script). It exposes `window.qtwebplot` with:

- `bridge`         — the QObject proxy once the channel is ready (else null).
- `send(name, p)`  — emit an event to Python.
- `handlers`       — `{name: function(payload)}` registry for Py->JS commands.
- `onReady(fn)`    — register a callback to run after the bridge handshake.
- `_dispatch`      — called by Python via runJavaScript to invoke a handler.
"""

from __future__ import annotations

from PySide6.QtCore import QFile, QIODevice


def load_qwebchannel_js() -> str:
    """Read Qt's bundled qwebchannel.js out of the resource system.

    PySide6's QtWebChannel module registers `:/qtwebchannel/qwebchannel.js` on
    import; we read it lazily to avoid shipping our own copy.
    """
    # Importing QWebChannel ensures the resource is registered.
    from PySide6.QtWebChannel import QWebChannel  # noqa: F401

    f = QFile(":/qtwebchannel/qwebchannel.js")
    if not f.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        raise RuntimeError(
            "Could not load qwebchannel.js from Qt resources. "
            "Is PySide6's QtWebChannel module installed?"
        )
    try:
        return bytes(f.readAll().data()).decode("utf-8")
    finally:
        f.close()


CORE_JS = r"""
(function () {
  if (window.qtwebplot && window.qtwebplot.__installed__) return;

  const qtwebplot = {
    __installed__: true,
    bridge: null,
    handlers: {},
    _ready: false,
    _readyCallbacks: [],

    onReady: function (fn) {
      if (this._ready) { fn(); } else { this._readyCallbacks.push(fn); }
    },

    send: function (name, payload) {
      if (this.bridge) {
        this.bridge.emit_event(String(name), payload === undefined ? null : payload);
      } else {
        console.warn("[qtwebplot] send() before bridge ready:", name);
      }
    },

    on: function (name, fn) { this.handlers[name] = fn; },

    _dispatch: function (name, payload) {
      const h = this.handlers[name];
      if (h) {
        try { h(payload); }
        catch (e) { console.error("[qtwebplot] handler", name, "threw:", e); }
      } else {
        // Notify Python that the message couldn't be delivered. We truncate
        // the payload echo to keep the report small.
        try {
          let echo = payload;
          if (echo && typeof echo === "object") {
            const s = JSON.stringify(echo);
            if (s && s.length > 512) echo = {_truncated: true, len: s.length};
          }
          this.send("_qtwebplot.undelivered", {name: name, payload: echo});
        } catch (e) { /* fall through */ }
        console.warn("[qtwebplot] no handler for", name);
      }
    },

    _markReady: function (channel) {
      this.bridge = channel.objects.bridge;
      this._ready = true;
      try { this.bridge.notify_ready(); } catch (e) { /* ignore */ }
      const cbs = this._readyCallbacks.slice();
      this._readyCallbacks = [];
      for (let i = 0; i < cbs.length; i++) {
        try { cbs[i](); } catch (e) { console.error("[qtwebplot] onReady cb threw:", e); }
      }
    },
  };

  window.qtwebplot = qtwebplot;

  function boot() {
    if (typeof QWebChannel === "undefined" || typeof qt === "undefined" || !qt.webChannelTransport) {
      // qwebchannel.js or the transport isn't here yet; retry shortly.
      setTimeout(boot, 10);
      return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      qtwebplot._markReady(channel);
    });
  }
  boot();
})();
"""
