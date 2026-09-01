(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var chips = document.querySelectorAll("[data-totp-url]");
        if (chips.length === 0) {
            return;
        }

        chips.forEach(function (chip) {
            var period = parseInt(chip.getAttribute("data-totp-period"), 10) || 30;
            var state = {
                code: chip.getAttribute("data-totp-code") || "------",
                remaining: parseInt(chip.getAttribute("data-totp-remaining"), 10) || 0,
                url: chip.getAttribute("data-totp-url"),
                period: period,
            };

            render(chip, state);

            setInterval(function () {
                state.remaining -= 1;
                if (state.remaining <= 0) {
                    refresh(chip, state);
                } else {
                    render(chip, state);
                }
            }, 1000);

            chip.addEventListener("click", function () {
                copyToClipboard(chip, state.code);
            });
        });

        function refresh(chip, state) {
            fetch(state.url, { credentials: "same-origin" })
                .then(function (resp) {
                    if (!resp.ok) {
                        throw new Error("totp fetch failed");
                    }
                    return resp.json();
                })
                .then(function (data) {
                    state.code = data.code;
                    state.remaining = data.seconds_remaining;
                    render(chip, state);
                })
                .catch(function () {
                    state.remaining = 2;
                });
        }

        function render(chip, state) {
            var codeEl = chip.querySelector(".totp-code-value");
            if (codeEl) {
                codeEl.textContent = state.code;
            }
            var bar = chip.parentElement && chip.parentElement.querySelector(".totp-progress-bar");
            if (bar) {
                var pct = Math.max(0, Math.min(100, (state.remaining / state.period) * 100));
                bar.style.width = pct + "%";
            }
        }

        function copyToClipboard(chip, code) {
            if (!navigator.clipboard) {
                return;
            }
            navigator.clipboard.writeText(code).then(function () {
                var label = chip.querySelector(".totp-copied-label");
                var codeEl = chip.querySelector(".totp-code-value");
                chip.classList.add("totp-chip-copied");
                if (label) {
                    label.classList.remove("d-none");
                }
                if (codeEl) {
                    codeEl.classList.add("d-none");
                }
                setTimeout(function () {
                    chip.classList.remove("totp-chip-copied");
                    if (label) {
                        label.classList.add("d-none");
                    }
                    if (codeEl) {
                        codeEl.classList.remove("d-none");
                    }
                }, 1200);
            }).catch(function () {
                // Clipboard write can be denied by the browser (e.g. no user
                // focus, blocked permission) — nothing useful to do but avoid
                // an unhandled rejection.
            });
        }
    });
})();
