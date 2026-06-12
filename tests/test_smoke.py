"""Smoke tests — pure imports + HTML-injection logic. No Qt event loop."""

from __future__ import annotations


def test_import_package() -> None:
    import qtwebplot

    assert hasattr(qtwebplot, "__version__")
    assert qtwebplot.WebBridgeView is not None
    assert qtwebplot.PlotView is not None
    assert qtwebplot.PlotBackend is not None


def test_inject_head_scripts_with_head() -> None:
    from qtwebplot.core._inject import inject_head_scripts

    html = "<html><head><title>x</title></head><body>hi</body></html>"
    out = inject_head_scripts(html, ["<script>A</script>", "<script>B</script>"])

    assert "<script>A</script>" in out
    assert "<script>B</script>" in out
    # Both scripts land before </head>.
    assert out.index("<script>A</script>") < out.index("</head>")
    assert out.index("<script>B</script>") < out.index("</head>")


def test_inject_head_scripts_no_head_falls_back_to_body() -> None:
    from qtwebplot.core._inject import inject_head_scripts

    html = "<html><body>hi</body></html>"
    out = inject_head_scripts(html, ["<script>A</script>"])

    assert "<script>A</script>" in out
    assert out.index("<script>A</script>") < out.index("<body>")


def test_inject_preserves_backslash_sequences_in_scripts() -> None:
    """Regression: injected JS like /\\d+/ or "\\n" must survive verbatim."""
    from qtwebplot.core._inject import inject_head_scripts

    html = "<html><head></head><body></body></html>"
    js = r"<script>var re = /\d+/; var s = '\n'; console.log('\b');</script>"
    out = inject_head_scripts(html, [js])

    assert js in out


def test_inject_body_end_script() -> None:
    from qtwebplot.core._inject import inject_body_end_script

    html = "<html><body>hi</body></html>"
    out = inject_body_end_script(html, "<script>Z</script>")

    assert "<script>Z</script>" in out
    assert out.index("<script>Z</script>") < out.index("</body>")
