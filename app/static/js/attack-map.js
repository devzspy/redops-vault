(function () {
    "use strict";

    var NODE_COLORS = {
        hostname: "#0d6efd",
        ip_address: "#6610f2",
        domain: "#20c997",
        region: "#fd7e14",
        cloud_provider: "#6c757d",
        file_share: "#d63384",
        cloud_storage: "#0dcaf0",
        database: "#198754",
        wiki: "#ffc107",
        source_control: "#6f42c1",
        ticketing: "#dc3545",
        collaboration: "#84cc16",
        backup_system: "#8d6e63",
    };
    var ACTIVE_COLOR = "#007fff";
    var VISITED_COLOR = "#adb5bd";
    var STEP_INTERVAL_MS = 1600;
    var DASH_TICK_MS = 60;

    document.addEventListener("DOMContentLoaded", function () {
        var container = document.getElementById("attack-map");
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
                container.textContent = "Failed to load attack map data.";
            });

        function initMap(data) {
            var targetNodes = (data.nodes || []).filter(function (n) {
                return n.category === "target";
            });

            if (targetNodes.length === 0) {
                container.textContent = "No targets or victims recorded yet for this engagement.";
                setupTimeline(null, data.killchain || [], {});
                return;
            }

            var targetIds = {};
            targetNodes.forEach(function (n) {
                targetIds["n" + n.id] = true;
            });

            var edges = (data.edges || []).filter(function (e) {
                return targetIds["n" + e.source] && targetIds["n" + e.target];
            });

            var elements = targetNodes
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

            setupDashAnimation(cy);
            setupTimeline(cy, data.killchain || [], targetIds);
            setupExport(cy);
        }

        function setupExport(cy) {
            if (!exportBtn) {
                return;
            }
            exportBtn.disabled = false;
            exportBtn.addEventListener("click", function () {
                downloadCyPng(cy, container.getAttribute("data-export-filename") || "attack-map");
            });
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
                {
                    selector: "node.visited",
                    style: { "border-color": VISITED_COLOR, "border-width": 3 },
                },
                {
                    selector: "node.active",
                    style: {
                        "border-color": ACTIVE_COLOR,
                        "border-width": 4,
                        "overlay-color": ACTIVE_COLOR,
                        "overlay-padding": 6,
                        "overlay-opacity": 0.3,
                    },
                },
                {
                    selector: "edge.visited",
                    style: { "line-color": VISITED_COLOR, "target-arrow-color": VISITED_COLOR, width: 3 },
                },
                {
                    selector: "edge.active",
                    style: {
                        "line-color": ACTIVE_COLOR,
                        "target-arrow-color": ACTIVE_COLOR,
                        width: 4,
                        "line-style": "dashed",
                        "line-dash-pattern": [6, 3],
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

        function setupDashAnimation(cy) {
            setInterval(function () {
                cy.edges(".active").forEach(function (edge) {
                    var offset = edge.numericStyle("line-dash-offset") || 0;
                    edge.style("line-dash-offset", offset - 1);
                });
            }, DASH_TICK_MS);
        }

        function setupTimeline(cy, killchain, targetIds) {
            var isOnMap = function (entry) {
                return (
                    entry.infra_node_id !== null &&
                    entry.infra_node_id !== undefined &&
                    targetIds["n" + entry.infra_node_id]
                );
            };
            var mapped = killchain.filter(isOnMap);
            var unmapped = killchain.filter(function (entry) {
                return !isOnMap(entry);
            });

            var playBtn = document.getElementById("timeline-play");
            var stepBackBtn = document.getElementById("timeline-step-back");
            var stepForwardBtn = document.getElementById("timeline-step-forward");
            var scrubber = document.getElementById("timeline-scrubber");
            var readout = document.getElementById("timeline-readout");
            var unmappedList = document.getElementById("unmapped-entries");

            renderUnmapped(unmapped, unmappedList);

            if (!cy || mapped.length === 0) {
                playBtn.disabled = true;
                stepBackBtn.disabled = true;
                stepForwardBtn.disabled = true;
                scrubber.disabled = true;
                readout.textContent = "No kill chain entries linked to a target yet.";
                return;
            }

            scrubber.max = String(mapped.length - 1);

            var currentIndex = -1;
            var playing = false;
            var playHandle = null;

            function findEdgeBetween(aId, bId) {
                return cy
                    .edges()
                    .filter(function (edge) {
                        var s = edge.data("source");
                        var t = edge.data("target");
                        return (s === aId && t === bId) || (s === bId && t === aId);
                    })
                    .first();
            }

            function formatTimestamp(iso) {
                if (!iso) {
                    return "";
                }
                var d = new Date(iso);
                if (isNaN(d.getTime())) {
                    return "";
                }
                return d.toLocaleString();
            }

            function showStep(index) {
                if (index < 0) index = 0;
                if (index > mapped.length - 1) index = mapped.length - 1;
                currentIndex = index;
                scrubber.value = String(index);

                cy.elements().removeClass("active visited");

                for (var j = 1; j <= index; j++) {
                    var prevId = "n" + mapped[j - 1].infra_node_id;
                    var curId = "n" + mapped[j].infra_node_id;
                    var edge = findEdgeBetween(prevId, curId);
                    if (edge && edge.nonempty()) {
                        edge.addClass(j === index ? "active" : "visited");
                    }
                }

                for (var k = 0; k < index; k++) {
                    var visitedNode = cy.getElementById("n" + mapped[k].infra_node_id);
                    if (visitedNode.nonempty()) {
                        visitedNode.addClass("visited");
                    }
                }

                var entry = mapped[index];
                var activeNode = cy.getElementById("n" + entry.infra_node_id);
                if (activeNode.nonempty()) {
                    activeNode.addClass("active");
                    cy.animate({ center: { eles: activeNode }, duration: 300 });
                }

                var ts = formatTimestamp(entry.occurred_at);
                var readoutHtml =
                    "<strong>" +
                    escapeHtml(entry.stage_label) +
                    "</strong> &mdash; " +
                    escapeHtml(entry.title) +
                    (ts ? " <span class=\"text-muted\">(" + escapeHtml(ts) + ")</span>" : "");
                if (entry.description) {
                    readoutHtml += "<div>" + escapeHtml(entry.description) + "</div>";
                }
                readout.innerHTML = readoutHtml;
            }

            function stopPlaying() {
                playing = false;
                playBtn.textContent = "Play";
                if (playHandle) {
                    clearInterval(playHandle);
                    playHandle = null;
                }
            }

            function startPlaying() {
                if (currentIndex >= mapped.length - 1) {
                    showStep(0);
                }
                playing = true;
                playBtn.textContent = "Pause";
                playHandle = setInterval(function () {
                    if (currentIndex >= mapped.length - 1) {
                        stopPlaying();
                        return;
                    }
                    showStep(currentIndex + 1);
                }, STEP_INTERVAL_MS);
            }

            playBtn.addEventListener("click", function () {
                if (playing) {
                    stopPlaying();
                } else {
                    startPlaying();
                }
            });

            stepBackBtn.addEventListener("click", function () {
                stopPlaying();
                showStep(currentIndex - 1);
            });

            stepForwardBtn.addEventListener("click", function () {
                stopPlaying();
                showStep(currentIndex + 1);
            });

            scrubber.addEventListener("input", function () {
                stopPlaying();
                showStep(parseInt(scrubber.value, 10));
            });

            showStep(0);
        }

        function renderUnmapped(entries, listEl) {
            listEl.innerHTML = "";
            if (entries.length === 0) {
                var li = document.createElement("li");
                li.className = "text-muted";
                li.textContent = "None.";
                listEl.appendChild(li);
                return;
            }
            entries.forEach(function (entry) {
                var li = document.createElement("li");
                li.textContent = entry.stage_label + " — " + entry.title;
                listEl.appendChild(li);
            });
        }

        function escapeHtml(str) {
            var div = document.createElement("div");
            div.textContent = str;
            return div.innerHTML;
        }
    });
})();
