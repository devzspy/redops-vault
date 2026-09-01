(function () {
    "use strict";

    var NODE_COLORS = {
        hostname: "#0d6efd",
        ip_address: "#6610f2",
        domain: "#20c997",
        region: "#fd7e14",
        cloud_provider: "#6c757d",
    };

    document.addEventListener("DOMContentLoaded", function () {
        var container = document.getElementById("cy");
        if (!container) {
            return;
        }

        if (window.cytoscape && window.cytoscapeDagre) {
            window.cytoscape.use(window.cytoscapeDagre);
        }

        var exportBtn = document.getElementById("export-map-png");

        var graphUrl = container.getAttribute("data-graph-url");
        fetch(graphUrl, { credentials: "same-origin" })
            .then(function (resp) {
                return resp.json();
            })
            .then(initMap)
            .catch(function () {
                container.textContent = "Failed to load network data.";
            });

        function initMap(data) {
            var attackerNodes = (data.nodes || []).filter(function (n) {
                return n.category === "attacker";
            });

            if (attackerNodes.length === 0) {
                container.textContent = "No infrastructure recorded yet for this engagement.";
                return;
            }

            var attackerIds = {};
            attackerNodes.forEach(function (n) {
                attackerIds["n" + n.id] = true;
            });

            var edges = (data.edges || []).filter(function (e) {
                return attackerIds["n" + e.source] && attackerIds["n" + e.target];
            });

            var elements = attackerNodes
                .map(function (n) {
                    return {
                        data: {
                            id: "n" + n.id,
                            label: n.name,
                            node_type: n.node_type,
                            role: n.role,
                        },
                    };
                })
                .concat(
                    edges.map(function (e) {
                        return {
                            data: {
                                id: "e" + e.id,
                                source: "n" + e.source,
                                target: "n" + e.target,
                                label: e.label || "",
                            },
                        };
                    })
                );

            var cy = window.cytoscape({
                container: container,
                elements: elements,
                style: buildStyle(),
                layout: { name: "dagre", rankDir: "LR", nodeSep: 40, rankSep: 90, animate: false },
            });

            setupExport(cy);
        }

        function setupExport(cy) {
            if (!exportBtn) {
                return;
            }
            exportBtn.disabled = false;
            exportBtn.addEventListener("click", function () {
                downloadCyPng(cy, container.getAttribute("data-export-filename") || "network-map");
            });
        }

        function buildStyle() {
            var style = [
                {
                    selector: "node",
                    style: {
                        "background-color": "#999",
                        label: "data(label)",
                        "text-valign": "bottom",
                        "text-halign": "center",
                        "text-margin-y": 6,
                        "font-size": 10,
                        color: "#333",
                        width: 42,
                        height: 42,
                        "border-width": 2,
                        "border-color": "#fff",
                    },
                },
                {
                    selector: "edge",
                    style: {
                        "curve-style": "bezier",
                        "target-arrow-shape": "triangle",
                        "line-color": "#999",
                        "target-arrow-color": "#999",
                        width: 2,
                        label: "data(label)",
                        "font-size": 9,
                        "text-background-color": "#fff",
                        "text-background-opacity": 0.85,
                        "text-rotation": "autorotate",
                    },
                },
            ];

            Object.keys(NODE_COLORS).forEach(function (type) {
                style.push({
                    selector: 'node[node_type = "' + type + '"]',
                    style: { "background-color": NODE_COLORS[type] },
                });
            });

            return style;
        }

        function downloadCyPng(cy, filenameBase) {
            var blob = cy.png({ output: "blob", full: true, scale: 2, bg: "#ffffff" });
            var url = URL.createObjectURL(blob);
            var safeName = filenameBase.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "map";
            var link = document.createElement("a");
            link.href = url;
            link.download = safeName + ".png";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }
    });
})();
