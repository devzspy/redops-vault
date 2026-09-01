(function () {
    "use strict";

    var SCROLL_SHOW_THRESHOLD = 400;

    document.addEventListener("DOMContentLoaded", function () {
        setupDetailsToggleLabels();
        setupBackToTop();
    });

    function setupDetailsToggleLabels() {
        document.querySelectorAll('[data-bs-toggle="collapse"][data-bs-target^="#details-"]').forEach(function (btn) {
            var target = document.querySelector(btn.getAttribute("data-bs-target"));
            if (!target) {
                return;
            }
            target.addEventListener("shown.bs.collapse", function () {
                btn.textContent = "Hide details";
            });
            target.addEventListener("hidden.bs.collapse", function () {
                btn.textContent = "Show details";
            });
        });
    }

    function setupBackToTop() {
        var btn = document.getElementById("back-to-top");
        if (!btn) {
            return;
        }
        window.addEventListener("scroll", function () {
            btn.classList.toggle("d-none", window.scrollY <= SCROLL_SHOW_THRESHOLD);
        });
        btn.addEventListener("click", function () {
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }
})();
