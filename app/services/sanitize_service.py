import re
from html.parser import HTMLParser

import bleach

# Deliberately excludes alignment/indent/color formatting (and any attribute
# that would carry it, like `class` or `style`) so the sanitized HTML has no
# dependency on the editor's own CSS to render correctly wherever it's shown.
ALLOWED_TAGS = [
    "p", "br",
    "strong", "b", "em", "i", "u", "s", "strike",
    "ul", "ol", "li",
    "a",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "code", "pre",
    "img",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}
ALLOWED_PROTOCOLS = ["http", "https", "data", "mailto"]


class _QuillListNormalizer(HTMLParser):
    """Quill 2.x renders both bullet and numbered lists as <ol><li
    data-list="bullet|ordered"> with an injected <span class="ql-ui"> marker
    in every item — the distinction only means anything via Quill's own CSS.
    This rewrites that into plain semantic <ul>/<ol>/<li> HTML so it renders
    correctly wherever it's displayed (not just inside the editor) and so
    html_to_markdown() can tell bullets from numbers. Must run before
    clean_html()'s tag allowlist strips the data-list attribute.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0
        self.source_list_stack = []  # 'ul'/'ol' as seen in the source, for li's with no data-list
        self.open_wrapper = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "span" and "ql-ui" in (attr_dict.get("class") or ""):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in ("ul", "ol"):
            self.source_list_stack.append(tag)
            return
        if tag == "li":
            data_list = attr_dict.get("data-list")
            if data_list == "bullet":
                kind = "ul"
            elif data_list == "ordered":
                kind = "ol"
            elif self.source_list_stack:
                kind = self.source_list_stack[-1]
            else:
                kind = "ul"
            if self.open_wrapper != kind:
                if self.open_wrapper:
                    self.out.append(f"</{self.open_wrapper}>")
                self.out.append(f"<{kind}>")
                self.open_wrapper = kind
            self.out.append("<li>")
            return
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if not self.skip_depth:
            self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag == "span":
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in ("ul", "ol"):
            if self.source_list_stack:
                self.source_list_stack.pop()
            if self.open_wrapper:
                self.out.append(f"</{self.open_wrapper}>")
                self.open_wrapper = None
            return
        if tag == "li":
            self.out.append("</li>")
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(data)

    def result(self):
        if self.open_wrapper:
            self.out.append(f"</{self.open_wrapper}>")
            self.open_wrapper = None
        return "".join(self.out)


def _normalize_quill_lists(raw_html):
    parser = _QuillListNormalizer()
    parser.feed(raw_html)
    parser.close()
    return parser.result()


def clean_html(raw_html):
    """Sanitizes rich-text editor output to a safe tag/attribute allowlist
    before it's stored. WYSIWYG content is rendered back with the `safe`
    filter, so this is the only point where untrusted HTML gets neutralized.
    """
    if not raw_html:
        return None
    cleaned = bleach.clean(
        _normalize_quill_lists(raw_html),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    ).strip()
    if not cleaned:
        return None

    # A blank Quill editor serializes as "<p><br></p>" — visually empty but
    # non-empty as a string, so check for real text/image content before
    # treating it as a value worth storing.
    text_only = bleach.clean(cleaned, tags=[], attributes={}, strip=True).strip()
    if not text_only and "<img" not in cleaned:
        return None
    return cleaned


class _MarkdownConverter(HTMLParser):
    """Converts the exact tag set clean_html() allows into plain Markdown
    syntax (not HTML-in-markdown) so exported findings paste cleanly into
    Confluence, SharePoint, or any other system's markdown importer.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.list_stack = []  # list of [kind, item_count] for nested ul/ol
        self.link_href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "br":
            self.chunks.append("  \n")
        elif tag in ("strong", "b"):
            self.chunks.append("**")
        elif tag in ("em", "i"):
            self.chunks.append("_")
        elif tag in ("s", "strike"):
            self.chunks.append("~~")
        elif tag == "a":
            self.link_href = attrs.get("href", "")
            self.chunks.append("[")
        elif tag == "img":
            self.chunks.append(f"![{attrs.get('alt', '')}]({attrs.get('src', '')})")
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
        elif tag == "li":
            if self.list_stack:
                self.list_stack[-1][1] += 1
                kind, index = self.list_stack[-1]
                indent = "  " * (len(self.list_stack) - 1)
                marker = "-" if kind == "ul" else f"{index}."
                self.chunks.append(f"\n{indent}{marker} ")
        elif len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            self.chunks.append("\n" + "#" * int(tag[1]) + " ")
        elif tag == "blockquote":
            self.chunks.append("\n> ")
        elif tag == "pre":
            self.chunks.append("\n```\n")
        elif tag == "code":
            self.chunks.append("`")

    def handle_endtag(self, tag):
        if tag == "p":
            self.chunks.append("\n\n")
        elif tag in ("strong", "b"):
            self.chunks.append("**")
        elif tag in ("em", "i"):
            self.chunks.append("_")
        elif tag in ("s", "strike"):
            self.chunks.append("~~")
        elif tag == "a":
            self.chunks.append(f"]({self.link_href or ''})")
            self.link_href = None
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self.chunks.append("\n")
        elif len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            self.chunks.append("\n")
        elif tag == "blockquote":
            self.chunks.append("\n")
        elif tag == "pre":
            self.chunks.append("\n```\n")
        elif tag == "code":
            self.chunks.append("`")

    def handle_data(self, data):
        self.chunks.append(data)

    def markdown(self):
        text = "".join(self.chunks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html):
    """Converts sanitized rich-text HTML (from clean_html()) into plain
    Markdown. Assumes input is already sanitized — this is a formatting
    step, not a security boundary.
    """
    if not html:
        return ""
    parser = _MarkdownConverter()
    parser.feed(html)
    parser.close()
    return parser.markdown()
