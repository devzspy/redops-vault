(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var chips = document.querySelectorAll("[data-copy-value]");
        if (chips.length === 0) {
            return;
        }

        chips.forEach(function (chip) {
            chip.addEventListener("click", function () {
                var value = chip.getAttribute("data-copy-value");
                if (!value || !navigator.clipboard) {
                    return;
                }
                navigator.clipboard
                    .writeText(value)
                    .then(function () {
                        var label = chip.querySelector(".copy-chip-copied-label");
                        var valueEl = chip.querySelector(".copy-chip-value");
                        chip.classList.add("copy-chip-copied");
                        if (label) {
                            label.classList.remove("d-none");
                        }
                        if (valueEl) {
                            valueEl.classList.add("d-none");
                        }
                        setTimeout(function () {
                            chip.classList.remove("copy-chip-copied");
                            if (label) {
                                label.classList.add("d-none");
                            }
                            if (valueEl) {
                                valueEl.classList.remove("d-none");
                            }
                        }, 1200);
                    })
                    .catch(function () {
                        // Clipboard write can be denied (no focus, blocked
                        // permission) — nothing useful to do about it here.
                    });
            });
        });
    });
})();
