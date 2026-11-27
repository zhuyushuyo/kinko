"""KINKO's palette follows colour-themes: same roles, same contrast rules, plus warn and risk."""
import json

import pytest

pytest.importorskip("PyQt6.QtGui")

from kinko.ui import theme  # noqa: E402

# The colour-themes rules (tools/build.py): (foreground, background, least ratio).
CHECKS = [
    ("text", "bg", 7.0), ("text", "surf2", 7.0), ("text2", "surf2", 4.5), ("text3", "surf2", 4.5),
    ("text3", "side", 4.5), ("accent", "bg", 4.5), ("accent", "surf2", 4.5), ("btn_ink", "btn", 7.0),
    ("good", "side", 4.5),
]
LIGHT_CHECKS = CHECKS + [
    ("text2", "side", 4.5), ("accent", "side", 4.5), ("accent", "surf", 4.5),
    ("good", "bg", 4.5), ("app", "bg", 4.5), ("app", "side", 4.5),
    ("script", "bg", 4.5), ("script", "side", 4.5),
]
# KINKO's own: the safety colours and the hints are text on every pane.
KINKO_CHECKS = [(fg, bg, 4.5) for fg in ("good", "warn", "risk", "text3")
                for bg in ("bg", "side", "surf", "surf2")]
COLOUR_THEMES_ROLES = {"bg", "side", "surf", "surf2", "line", "line_strong", "text", "text2", "text3", "accent",
                       "btn", "btn_ink", "track", "good", "app", "script", "accent_soft", "nav_on"}


def test_palette_has_every_role():
    data = json.loads(theme.PALETTE_FILE.read_text(encoding="utf-8"))
    for mode in theme.MODES:
        assert set(data[mode]) == COLOUR_THEMES_ROLES | {"warn", "risk"}
        assert set(theme.ROLES) <= set(data[mode])


@pytest.mark.parametrize("mode", theme.MODES)
def test_contrast(mode):
    p = theme.load_palettes(override=theme.PALETTE_FILE.with_name("missing.json"))[mode]
    rules = (LIGHT_CHECKS if mode == "light" else CHECKS) + KINKO_CHECKS
    low = [f"{fg} on {bg}: {theme.contrast(p[fg], p[bg]):.2f}" for fg, bg, least in rules
           if theme.contrast(p[fg], p[bg]) < least]
    assert low == []
    assert (theme.luminance(p["bg"]) < theme.luminance(p["text"])) == (mode == "dark")


@pytest.mark.parametrize("dark", [True, False])
def test_badges_and_categories_readable(dark):
    tok = theme.resolve(dark, theme.load_palettes(override=theme.PALETTE_FILE.with_name("missing.json")))
    for fg in ("tokiwa", "kincha", "bengara", "ai"):
        tint = tok[f"{fg}_tint"] if fg != "ai" else tok["ai_tint"]
        assert theme.contrast(tok[fg], tint) >= 4.5, fg
    assert theme.contrast(tok["btn_ink"], tok["btn"]) >= 7
    for key, pair in theme.CAT_COLORS.items():
        colour = pair[1] if dark else pair[0]
        tint = theme.mix(tok["paper"], colour, 0.2 if dark else 0.12)
        assert theme.contrast(colour, tok["paper"]) >= 4.5, key
        assert theme.contrast(colour, tint) >= 4.5, key


def test_style_sheet_builds_in_both_modes():
    for dark in (True, False):
        qss = theme.build_qss(theme.resolve(dark), 13, False)
        assert "$" not in qss.replace("${", "")  # every placeholder was filled


def test_theme_json_overrides_roles(tmp_path):
    f = tmp_path / "theme.json"
    f.write_text(json.dumps({"dark": {"accent": "#6fd8cc", "bogus": "#000000"}, "light": {"text": "red"}}),
                 encoding="utf-8")
    p = theme.load_palettes(override=f)
    assert p["dark"]["accent"] == "#6FD8CC"
    assert "bogus" not in p["dark"]
    assert p["light"]["text"] == "#211F38"  # not a colour: ignored
    f.write_text("{not json", encoding="utf-8")
    assert theme.load_palettes(override=f)["dark"]["accent"] == "#BBAAF7"
