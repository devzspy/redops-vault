(function () {
    "use strict";

    var SCROLL_STEP = 220;
    var EDITABLE_TAGS = ["INPUT", "TEXTAREA", "SELECT"];

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".attack-cell-expand").forEach(function (btn) {
            var contentEl = document.getElementById(btn.getAttribute("data-popover-target"));
            if (!contentEl || !window.bootstrap) {
                return;
            }
            new window.bootstrap.Popover(btn, {
                html: true,
                content: contentEl.innerHTML,
                title: btn.getAttribute("data-popover-title"),
                trigger: "focus",
                placement: "right",
                container: "body",
                customClass: "attack-popover",
            });
        });

        setupArrowKeyScroll();
    });

    function setupArrowKeyScroll() {
        var matrix = document.querySelector(".attack-matrix");
        if (!matrix) {
            return;
        }

        document.addEventListener("keydown", function (event) {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
                return;
            }
            var active = document.activeElement;
            if (active && EDITABLE_TAGS.indexOf(active.tagName) !== -1) {
                return;
            }
            event.preventDefault();
            matrix.scrollBy({
                left: event.key === "ArrowLeft" ? -SCROLL_STEP : SCROLL_STEP,
                behavior: "smooth",
            });
        });
    }
})();
