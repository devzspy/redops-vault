(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var select = document.getElementById("credential-type-select");
        var sections = document.querySelectorAll(".credential-fields");
        if (!select || sections.length === 0) {
            return;
        }

        function sync() {
            sections.forEach(function (section) {
                section.style.display = section.getAttribute("data-credential-type") === select.value ? "" : "none";
            });
        }

        select.addEventListener("change", sync);
        sync();
    });
})();
