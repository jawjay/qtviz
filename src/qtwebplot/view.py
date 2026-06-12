"""PlotView — thin convenience wrapper that hosts a PlotBackend in a WebBridgeView."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from qtwebplot.backend import PlotBackend
from qtwebplot.core._inject import inject_head_scripts, wrap_as_script
from qtwebplot.core._runtime import CORE_JS, load_qwebchannel_js
from qtwebplot.core.web_bridge_view import WebBridgeView


class PlotView(WebBridgeView):
    """A WebBridgeView that hosts a PlotBackend.

    Adds nothing visualization-specific — backends carry their own verbs and
    typed events. This class exists only to remove the per-use boilerplate of
    instantiating a backend, injecting its js_runtime, and reloading on
    `set_figure`.
    """

    def __init__(
        self,
        backend: PlotBackend | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend: PlotBackend | None = None
        if backend is not None:
            self.set_backend(backend)

    @property
    def backend(self) -> PlotBackend | None:
        return self._backend

    def set_backend(self, backend: PlotBackend) -> None:
        if self._backend is not None:
            self._backend.on_detach()
        self._backend = backend
        backend.on_attach(self)
        self._render()

    def set_figure(self, figure: Any) -> None:
        if self._backend is None:
            raise RuntimeError("PlotView has no backend; call set_backend() first.")
        self._backend.set_figure(figure)
        self._render()

    def _render(self) -> None:
        if self._backend is None:
            return
        html = self._backend.to_html()
        prepared = self._inject_with_backend_runtime(html)
        # bypass parent's load_html so we inject the backend runtime too
        self._is_ready = False
        self._view.setHtml(prepared, self._backend.base_url())

    def _inject_with_backend_runtime(self, html: str) -> str:
        scripts = [
            wrap_as_script(load_qwebchannel_js()),
            wrap_as_script(CORE_JS),
        ]
        backend_js = self._backend.js_runtime() if self._backend else None
        if backend_js:
            scripts.append(wrap_as_script(backend_js))
        return inject_head_scripts(html, scripts)
