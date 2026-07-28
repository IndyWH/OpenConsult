"""face_3d — Python side of the robot face renderer.

The face itself lives in ``web_assets/face3d.js`` — a retro LED
dot-matrix panel drawn on a 2D canvas (no WebGL / no dependency). This
module provides everything the web UI needs to drive it:

- :func:`face_payload` — convert a :class:`FaceState` (12 FACS muscles)
  plus a mood color into the JSON dict the JS ``setTargets`` API expects.
- :func:`container_html` / :func:`boot_script` / :func:`boot_js` — the
  DOM container and the bootstrap for the page.

The JS face lerps toward the targets it is given and layers its own life
on top: blinking, eye saccades, a breathing glow, and a syllable-rate
mouth flap while the browser speaks the reply.

(The ``face_3d`` / ``face3d.js`` names are kept for continuity with the
page wiring; the renderer is 2D, not 3D.)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vendor.kindalive.expression.face import FaceState

#: Default mood accent (calm teal) used before any emotion dominates.
DEFAULT_MOOD_COLOR = "#4FB7A6"

CONTAINER_ID = "kindalive-face3d"

WEB_ASSETS_DIR = Path(__file__).parent / "web_assets"


def face_payload(
    face: FaceState,
    mood_color: str = DEFAULT_MOOD_COLOR,
    mood_intensity: float = 0.3,
) -> dict[str, Any]:
    """Build the dict consumed by ``window.kindaliveFace.setTargets``.

    Args:
        face: Current 12-muscle facial state, each value in [0, 1].
        mood_color: Hex accent color for the dominant emotion — tints
            the iris glow and the backdrop light bands.
        mood_intensity: Strength of the dominant emotion in [0, 1].
    """
    return {
        "muscles": {k: round(v, 4) for k, v in face.as_dict().items()},
        "mood": {
            "color": mood_color,
            "intensity": max(0.0, min(1.0, mood_intensity)),
        },
    }


def payload_js(payload: dict[str, Any]) -> str:
    """JS statement pushing a payload to the face (no-op until ready)."""
    return (
        "window.kindaliveFace && "
        f"window.kindaliveFace.setTargets({json.dumps(payload)});"
    )


def container_html(container_id: str = CONTAINER_ID) -> str:
    """The DOM node the renderer mounts into. Size it with CSS."""
    return f'<div id="{container_id}" class="face3d-stage"></div>'


def boot_script(container_id: str = CONTAINER_ID) -> str:
    """Module script that boots the face once the page is parsed.

    Kept for callers that inject HTML directly; the web UI prefers
    :func:`boot_js` via ``ui.run_javascript`` so no inline ``<script>``
    has to survive NiceGUI's HTML sanitization.
    """
    return (
        '<script type="module">'
        'import initFace3D from "/webassets/face3d.js";'
        f'initFace3D("{container_id}");'
        "</script>"
    )


def boot_js(container_id: str = CONTAINER_ID) -> str:
    """JS that dynamically imports the face module and boots it.

    Designed for ``ui.run_javascript`` — a bare dynamic ``import()`` with
    no ``<script>`` wrapper, so it is unaffected by HTML sanitization in
    newer NiceGUI releases.
    """
    return (
        'import("/webassets/face3d.js")'
        f'.then(m => m.default("{container_id}"))'
        '.catch(e => console.error("face3d boot failed:", e));'
    )

