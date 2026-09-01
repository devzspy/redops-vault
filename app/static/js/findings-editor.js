(function () {
    "use strict";

    // Deliberately excludes alignment/indent/color — matches the tag
    // allowlist in app/services/sanitize_service.py, which strips anything
    // that would need Quill's own CSS classes to render (see that file for
    // why: keeps saved content self-contained wherever it's displayed).
    var TOOLBAR_OPTIONS = [
        ["bold", "italic", "underline", "strike"],
        ["blockquote", "code-block"],
        [{ list: "ordered" }, { list: "bullet" }],
        ["link", "image"],
        ["clean"],
    ];

    document.addEventListener("DOMContentLoaded", function () {
        if (!window.Quill) {
            return;
        }

        var editors = [];
        document.querySelectorAll(".finding-editor").forEach(function (el) {
            var textarea = el.nextElementSibling;
            if (!textarea || textarea.tagName !== "TEXTAREA") {
                return;
            }
            // Quill reads the container's existing HTML (rendered server-side
            // from the finding's saved value) as its initial content.
            var quill = new window.Quill(el, {
                theme: "snow",
                modules: { toolbar: TOOLBAR_OPTIONS },
            });
            editors.push({ quill: quill, textarea: textarea });
        });

        if (editors.length === 0) {
            return;
        }

        // Not document.querySelector("form") — base.html's navbar logout
        // form appears earlier in the DOM and would be matched instead.
        var form = editors[0].textarea.closest("form");
        if (!form) {
            return;
        }
        form.addEventListener("submit", function () {
            editors.forEach(function (entry) {
                entry.textarea.value = entry.quill.root.innerHTML;
            });
        });
    });
})();
