from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


class ReferenceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        for attribute in ("href", "src"):
            value = attributes.get(attribute)
            if value:
                self.references.append((value, attribute))


def local_path(source, reference):
    url = urlsplit(reference)
    if url.scheme or url.netloc or not url.path:
        return None, url.fragment

    path = unquote(url.path)
    target = ROOT / path.lstrip("/") if path.startswith("/") else source.parent / path
    return target.resolve(), unquote(url.fragment)


def check_html(path, errors):
    parser = ReferenceParser()
    parser.feed(path.read_text(encoding="utf-8"))
    for reference, attribute in parser.references:
        target, fragment = local_path(path, reference)
        if target is None:
            if reference.startswith("#") and fragment not in parser.ids:
                errors.append(f"{path.relative_to(ROOT)}: missing anchor #{fragment}")
            continue

        if not target.is_file():
            errors.append(
                f"{path.relative_to(ROOT)}: missing {attribute} target {reference}"
            )
        elif fragment and target.suffix.lower() in {".html", ".htm"}:
            target_parser = ReferenceParser()
            target_parser.feed(target.read_text(encoding="utf-8"))
            if fragment not in target_parser.ids:
                errors.append(
                    f"{path.relative_to(ROOT)}: missing anchor "
                    f"#{fragment} in {reference.split('#', 1)[0]}"
                )


def check_css(path, errors):
    content = path.read_text(encoding="utf-8")
    references = re.findall(r"url\(\s*(['\"]?)(.*?)\1\s*\)", content, re.I)
    for _, reference in references:
        reference = reference.strip()
        target, _ = local_path(path, reference)
        if target is not None and not target.is_file():
            errors.append(
                f"{path.relative_to(ROOT)}: missing CSS asset {reference}"
            )

    imports = re.findall(r"@import\s+(['\"])(.*?)\1", content, re.I)
    for _, reference in imports:
        target, _ = local_path(path, reference)
        if target is not None and not target.is_file():
            errors.append(
                f"{path.relative_to(ROOT)}: missing CSS import {reference}"
            )


def main():
    errors = []
    for path in ROOT.rglob("*.html"):
        if ".git" not in path.parts:
            check_html(path, errors)
    for path in ROOT.rglob("*.css"):
        if ".git" not in path.parts:
            check_css(path, errors)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("All local HTML/CSS references and anchors are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
