"""PlotView — thin convenience wrapper that hosts a PlotBackend in a WebBridgeView."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from qtviz.backends.webengine.backend import PlotBackend
from qtviz.backends.webengine.core._inject import inject_head_scripts, wrap_as_script
from qtviz.backends.webengine.core._runtime import CORE_JS, load_qwebchannel_js
from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView
from qtviz.backends.webengine.theme import Theme


class PlotView(WebBridgeView):
    """A WebBridgeView that hosts a PlotBackend.

    Adds nothing visualization-specific — backends carry their own verbs and
    typed events. This class exists only to remove the per-use boilerplate of
    instantiating a backend, injecting its js_runtime, and reloading on
    `set_figure`.

    Parameters
    ----------
    backend : PlotBackend | None
        Initial backend. May be set later via `set_backend`.
    parent : QWidget | None
    theme : Theme | None
        If provided, applied to every backend on attach. Use
        `Theme.from_qt_app()` to match the host app's palette automatically.
    """

    def __init__(
        self,
        backend: PlotBackend | None = None,
        parent: QWidget | None = None,
        *,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend: PlotBackend | None = None
        self._theme: Theme | None = theme
        if backend is not None:
            self.set_backend(backend)

    @property
    def backend(self) -> PlotBackend | None:
        return self._backend

    @property
    def theme(self) -> Theme | None:
        return self._theme

    def set_theme(self, theme: Theme | None) -> None:
        """Set or clear the theme; re-applies to the current backend and
        re-renders."""
        self._theme = theme
        if self._backend is not None:
            if theme is not None:
                self._backend.apply_theme(theme)
            self._render()

    def set_backend(self, backend: PlotBackend) -> None:
        if self._backend is not None:
            self._backend.on_detach()
        self._backend = backend
        if self._theme is not None:
            backend.apply_theme(self._theme)
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
        # _load_prepared (parent) routes large offline-inlined pages through a temp
        # file — setHtml caps at ~2 MB and would otherwise load blank.
        self._load_prepared(prepared, self._backend.base_url())

    def _inject_with_backend_runtime(self, html: str) -> str:
        scripts = [
            wrap_as_script(load_qwebchannel_js()),
            wrap_as_script(CORE_JS),
        ]
        backend_js = self._backend.js_runtime() if self._backend else None
        if backend_js:
            scripts.append(wrap_as_script(backend_js))
        return inject_head_scripts(html, scripts)
