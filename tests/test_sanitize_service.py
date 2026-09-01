from app.services.sanitize_service import clean_html, html_to_markdown


def test_clean_html_strips_script_tags():
    result = clean_html("<script>alert(1)</script><p>after</p>")
    # The tag itself is removed (no executable <script> element survives);
    # bleach with strip=True leaves the inert text content behind rather
    # than deleting it outright.
    assert "<script" not in result
    assert "</script>" not in result
    assert "<p>after</p>" in result


def test_clean_html_strips_event_handler_attributes():
    result = clean_html('<img src="x" onerror="alert(1)">')
    assert "onerror" not in result


def test_clean_html_strips_javascript_href():
    result = clean_html('<a href="javascript:alert(1)">bad link</a>')
    assert "javascript:" not in result


def test_clean_html_keeps_safe_formatting():
    result = clean_html("<p>Hello <strong>world</strong></p><ul><li>one</li></ul>")
    assert result == "<p>Hello <strong>world</strong></p><ul><li>one</li></ul>"


def test_clean_html_keeps_data_uri_images():
    result = clean_html('<img src="data:image/png;base64,iVBORw0KGgo=" alt="x">')
    assert 'src="data:image/png;base64,iVBORw0KGgo="' in result


def test_clean_html_treats_blank_quill_editor_as_none():
    assert clean_html("<p><br></p>") is None


def test_clean_html_none_and_empty_string():
    assert clean_html(None) is None
    assert clean_html("") is None


def test_html_to_markdown_converts_formatting():
    html = "<p>The form is <strong>vulnerable</strong> to <em>injection</em>.</p>"
    assert html_to_markdown(html) == "The form is **vulnerable** to _injection_."


def test_html_to_markdown_converts_lists():
    html = "<ul><li>one</li><li>two</li></ul>"
    md = html_to_markdown(html)
    assert "- one" in md
    assert "- two" in md


def test_html_to_markdown_converts_links():
    html = '<a href="https://example.com">example</a>'
    assert html_to_markdown(html) == "[example](https://example.com)"


def test_html_to_markdown_handles_empty_input():
    assert html_to_markdown(None) == ""
    assert html_to_markdown("") == ""


def test_clean_html_normalizes_quill_bullet_list():
    # Quill 2.x renders both bullet and ordered lists as <ol><li data-list=...>
    # with an injected UI marker span — this must become a real <ul> so it
    # renders as bullets outside the editor and converts to "-" in markdown.
    quill_html = (
        '<ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>a</li>'
        '<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>b</li></ol>'
    )
    cleaned = clean_html(quill_html)
    assert cleaned == "<ul><li>a</li><li>b</li></ul>"
    assert "ql-ui" not in cleaned
    assert "data-list" not in cleaned
    assert html_to_markdown(cleaned) == "- a\n- b"


def test_clean_html_normalizes_quill_ordered_list():
    quill_html = (
        '<ol><li data-list="ordered"><span class="ql-ui" contenteditable="false"></span>a</li>'
        '<li data-list="ordered"><span class="ql-ui" contenteditable="false"></span>b</li></ol>'
    )
    cleaned = clean_html(quill_html)
    assert cleaned == "<ol><li>a</li><li>b</li></ol>"
    assert html_to_markdown(cleaned) == "1. a\n2. b"


def test_clean_html_preserves_plain_ul_without_data_list():
    cleaned = clean_html("<ul><li>one</li><li>two</li></ul>")
    assert cleaned == "<ul><li>one</li><li>two</li></ul>"
    assert html_to_markdown(cleaned) == "- one\n- two"
