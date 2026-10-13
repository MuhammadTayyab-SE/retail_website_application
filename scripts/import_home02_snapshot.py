"""Import the user-supplied rendered Home 02 capture, not a WordPress runtime.

Usage: python scripts/import_home02_snapshot.py --archive ../zilly-offline
Keeps captured markup/style classes and copies only referenced local assets.
"""

import argparse
import html
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATIC_PREFIX = "catalog/home02/reference/"
TEMPLATES = ROOT / "catalog/templates/catalog/home02/snapshot"
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SECTION_NAMES = {
    "878cc90": "hero",
    "e7dec89": "offer-ticker",
    "d84a83d": "featured-and-sidebar",
    "7b85529": "sellers",
    "15681d7": "promotions",
    "e40606d": "weekly-deals",
    "84065ce": "section-spacing",
    "6acfb28": "sale-and-top-rated",
    "1368932": "blog",
    "af48681": "services",
}


class CaptureParser(HTMLParser):
    """Locate section boundaries without serializing or altering captured HTML."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0]
        for line in source.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.stack = []
        self.nodes = []
        self.feed(source)

    def position(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        node = {
            "tag": tag,
            "attrs": dict(attrs),
            "start": self.position(),
            "parent": self.stack[-1] if self.stack else None,
        }
        self.nodes.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)
        else:
            node["end"] = node["start"] + len(self.get_starttag_text())

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                self.stack[i]["end"] = self.source.index(">", self.position()) + 1
                self.stack = self.stack[:i]
                break


def import_snapshot(archive):
    archive = archive.resolve()
    page = archive / "pages/home-02/index.html"
    source = page.read_text(encoding="utf8")
    parser = CaptureParser(source)
    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf8"))
    types = {
        (archive / entry["path"]).resolve(): entry.get("type", "")
        for entry in manifest["files"].values()
    }
    copied = {}
    missing = set()

    def destination(path):
        relative = path.relative_to(archive / "assets")
        if not path.suffix and types.get(path, "").startswith("text/css"):
            relative = relative.with_name(relative.name + ".css")
        return relative

    def copy_asset(path):
        path = path.resolve()
        if path in copied:
            return copied[path]
        if not path.is_relative_to(archive / "assets") or not path.is_file():
            missing.add(str(path))
            return None
        relative = destination(path)
        copied[path] = relative
        target = ROOT / "catalog/static" / STATIC_PREFIX / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".css" or types.get(path, "").startswith("text/css"):
            css = path.read_text(encoding="utf8", errors="replace")

            def copy_css_reference(match):
                value = match.group(2).strip()
                parsed = urlsplit(value)
                if not value or parsed.scheme or value.startswith(("//", "#")):
                    return match.group(0)
                dependency = (path.parent / unquote(parsed.path)).resolve()
                result = copy_asset(dependency)
                if result is None:
                    return match.group(0)
                # Archive CSS already uses relative URLs. Only extensionless CSS
                # needs renaming for staticfiles to send the correct MIME type.
                replacement = value
                if result.name != dependency.name:
                    replacement = value.replace(dependency.name, result.name)
                return "url(" + match.group(1) + replacement + match.group(1) + ")"

            css = re.sub(r"url\(\s*(['\"]?)(.*?)\1\s*\)", copy_css_reference, css)
            target.write_text(
                "\n".join(line.expandtabs(4).rstrip() for line in css.splitlines()).rstrip() + "\n",
                encoding="utf8",
            )
        elif path.suffix in {".svg", ".js"}:
            text = path.read_text(encoding="utf8")
            target.write_text(
                "\n".join(line.expandtabs(4).rstrip() for line in text.splitlines()).rstrip()
                + "\n",
                encoding="utf8",
            )
        else:
            shutil.copyfile(path, target)
        return relative

    def rewrite_markup(markup):
        markup = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", markup, flags=re.I | re.S)
        # Embedded WordPress AJAX settings are unnecessary for a static replica.
        markup = re.sub(r'\sdata-rtsb-ajax="[^"]*"', "", markup)
        markup = re.sub(r'\son\w+=("[^"]*"|\'[^\']*\')', "", markup, flags=re.I)

        def replace_asset(match):
            value = html.unescape(match.group(0))
            parsed = urlsplit(value)
            path = (page.parent / unquote(parsed.path)).resolve()
            relative = copy_asset(path)
            if relative is None:
                return value
            suffix = "#" + parsed.fragment if parsed.fragment else ""
            return "{% static '" + STATIC_PREFIX + relative.as_posix() + "' %}" + suffix

        return re.sub(r"(?:\.\.?/)+(?:assets/)[^\s\"'<>),]+", replace_asset, markup)

    TEMPLATES.mkdir(parents=True, exist_ok=True)

    def write_partial(name, markup):
        markup = rewrite_markup(markup)
        (TEMPLATES / f"{name}.html").write_text(
            "{% load static %}\n"
            + "\n".join(line.expandtabs(4).rstrip() for line in markup.splitlines()).rstrip()
            + "\n",
            encoding="utf8",
        )

    head_end = source.index("</head>")
    styles = []
    for node in parser.nodes:
        if (node["tag"] == "link" and node["attrs"].get("rel") == "stylesheet") or (
            node["tag"] == "style" and node["start"] < head_end
        ):
            styles.append(source[node["start"] : node["end"]])
    write_partial("styles", "\n".join(styles))
    body = next(n for n in parser.nodes if n["tag"] == "body")
    content = next(n for n in parser.nodes if n["attrs"].get("id") == "content")
    host = next(n for n in parser.nodes if n["attrs"].get("data-elementor-id") == "178")
    sections = [n for n in parser.nodes if n["parent"] is host]
    write_partial("header", source[body["start"] : content["start"]])
    chunks = [source[content["start"] : sections[0]["start"]]]
    for number, section in enumerate(sections):
        name = SECTION_NAMES.get(section["attrs"].get("data-id"), f"section-{number}")
        write_partial(name, source[section["start"] : section["end"]])
        chunks.append("{% include 'catalog/home02/snapshot/" + name + ".html' %}")
    chunks.append(source[sections[-1]["end"] : content["end"]])
    write_partial("content", "\n".join(chunks))
    footer = next(n for n in parser.nodes if n["tag"] == "footer")
    write_partial("footer", source[content["end"] : footer["end"]] + "\n</div>")

    # Keep the captured demo purchase/currency chrome separately from store content.
    overlay_nodes = []
    for node in parser.nodes:
        if node["start"] <= footer["end"] or "end" not in node:
            continue
        classes = node["attrs"].get("class", "")
        if any(
            name in classes.split()
            for name in (
                "rtdsp-buy-now-float-wrap",
                "switcher-list",
                "rtsb-cart-float-menu",
                "rtsb-drawer-container",
                "drawer-overlay",
            )
        ):
            if not any(
                parent["start"] <= node["start"] < parent["end"] for parent in overlay_nodes
            ):
                overlay_nodes.append(node)
    write_partial("overlays", "\n".join(source[n["start"] : n["end"]] for n in overlay_nodes))

    swiper = next(
        p for p in (archive / "assets").rglob("swiper.min-*.js") if "/elementor/" in p.as_posix()
    )
    relative = copy_asset(swiper)
    (TEMPLATES / "vendor.html").write_text(
        "{% load static %}\n<script src=\"{% static '"
        + STATIC_PREFIX
        + relative.as_posix()
        + "' %}\" defer></script>",
        encoding="utf8",
    )
    if missing:
        raise RuntimeError("Missing referenced archive assets: " + ", ".join(sorted(missing)))
    print(f"Imported {len(sections)} captured sections and {len(copied)} referenced local assets.")


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--archive", type=Path, required=True)
    import_snapshot(args.parse_args().archive)
