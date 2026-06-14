"""The resolve pipeline (D14, milestone-data-core §4).

`resolve_node` walks a Node tree and, for each Element, resolves its channel
accessors against its data ref into a role-keyed eager ref — so renderers read
fixed channel roles (`x`, `y`, …) regardless of whether the user bound a string,
an Expression, a callable, or a raw array. For lazy refs this is the unit the
async Worker runs (milestone step 2); here (eager) it runs synchronously.

Duck-typed (a node with `channels()` is an Element; one with `children` is a
composite) so this module stays free of a `core` import cycle.
"""

from __future__ import annotations

from .ref import EagerTabularRef


def resolve_node(node):
    if hasattr(node, "channels"):  # Element
        channels = node.channels()
        if not channels:
            return node  # gridded / no data-bound channels (e.g. Image)
        arrays = node.data.resolve_channels(channels)
        return node._replace_data(EagerTabularRef(arrays, arrays))
    if hasattr(node, "children"):  # Overlay / Layout
        return node.with_(children=tuple(resolve_node(c) for c in node.children))
    return node
