(function () {
    "use strict";

    var NODE_COLORS = {
        hostname: "#0d6efd",
        ip_address: "#6610f2",
        domain: "#20c997",
        region: "#fd7e14",
        cloud_provider: "#6c757d",
    };
    var ACTIVE_COLOR = "#00d4ff";
    var VISITED_COLOR = "#adb5bd";
    var LABEL_COLOR = "#e8ecf4";
    var EDGE_COLOR = "#4b5b78";
    var CARD_BG = "#0b1120";
    var NODE_RADIUS = 22;
    var STEP_INTERVAL_MS = 1600;
    var MIN_USABLE_SIZE = 100;
    var FALLBACK_WIDTH = 800;
    var FALLBACK_HEIGHT = 480;

    function usableOrFallback(measured, fallback) {
        return measured >= MIN_USABLE_SIZE ? measured : fallback;
    }

    document.addEventListener("DOMContentLoaded", function () {
        var container = document.getElementById("g6-canvas");
        if (!container) {
            return;
        }

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
            if (!data.nodes || data.nodes.length === 0) {
                container.textContent = "No infrastructure recorded yet for this engagement.";
                return;
            }

            var nodes = data.nodes.map(function (n) {
                return {
                    id: "n" + n.id,
                    label: n.name,
                    node_type: n.node_type,
                    style: {
                        fill: NODE_COLORS[n.node_type] || "#999",
                        stroke: "#ffffff",
                        lineWidth: 2,
                        shadowColor: "rgba(0, 0, 0, 0.45)",
                        shadowBlur: 14,
                    },
                };
            });
            var edges = data.edges.map(function (e) {
                return {
                    id: "e" + e.id,
                    source: "n" + e.source,
                    target: "n" + e.target,
                    label: e.label || "",
                };
            });

            var graph = new window.G6.Graph({
                container: container,
                width: usableOrFallback(container.clientWidth, FALLBACK_WIDTH),
                height: usableOrFallback(container.clientHeight, FALLBACK_HEIGHT),
                fitView: true,
                fitViewPadding: 40,
                modes: { default: ["drag-canvas", "zoom-canvas", "drag-node"] },
                layout: { type: "dagre", rankdir: "LR", nodesep: 40, ranksep: 100 },
                defaultNode: {
                    type: "circle",
                    size: NODE_RADIUS * 2,
                    labelCfg: {
                        position: "bottom",
                        offset: 8,
                        style: { fill: LABEL_COLOR, fontSize: 11 },
                    },
                },
                defaultEdge: {
                    type: "quadratic",
                    style: {
                        stroke: EDGE_COLOR,
                        lineWidth: 2,
                        endArrow: { path: window.G6.Arrow.triangle(6, 8, 0), fill: EDGE_COLOR },
                    },
                    labelCfg: {
                        autoRotate: true,
                        style: {
                            fill: "#9fb0c9",
                            fontSize: 9,
                            background: { fill: CARD_BG, padding: [2, 4, 2, 4], radius: 3 },
                        },
                    },
                },
                nodeStateStyles: {
                    visited: { stroke: VISITED_COLOR, lineWidth: 3 },
                    active: { stroke: ACTIVE_COLOR, lineWidth: 3, shadowColor: ACTIVE_COLOR, shadowBlur: 26 },
                },
                edgeStateStyles: {
                    visited: {
                        stroke: VISITED_COLOR,
                        lineWidth: 3,
                        endArrow: { path: window.G6.Arrow.triangle(6, 8, 0), fill: VISITED_COLOR },
                    },
                    active: {
                        stroke: ACTIVE_COLOR,
                        lineWidth: 3,
                        endArrow: { path: window.G6.Arrow.triangle(6, 8, 0), fill: ACTIVE_COLOR },
                    },
                },
            });

            graph.data({ nodes: nodes, edges: edges });
            graph.render();

            observeContainerSize(container, graph);
            setupTimeline(graph, data.killchain || []);
        }

        function observeContainerSize(container, graph) {
            // Falls back to fixed dimensions when the container is measured before
            // layout has settled (e.g. still 0x0 on first paint). Once real
            // dimensions are available, resize and re-fit so the graph isn't
            // stuck at the fallback size.
            if (!window.ResizeObserver) {
                window.addEventListener("resize", function () {
                    if (container.clientWidth && container.clientHeight) {
                        graph.changeSize(container.clientWidth, container.clientHeight);
                    }
                });
                return;
            }

            var lastWidth = container.clientWidth;
            var lastHeight = container.clientHeight;
            var observer = new ResizeObserver(function (entries) {
                var entry = entries[0];
                var width = Math.round(entry.contentRect.width);
                var height = Math.round(entry.contentRect.height);
                // Ignore transient tiny sizes seen mid-layout (e.g. during a
                // flex reflow) — fitting the view to those produces an
                // out-of-range zoom ratio and is never useful anyway.
                if (width >= MIN_USABLE_SIZE && height >= MIN_USABLE_SIZE && (width !== lastWidth || height !== lastHeight)) {
                    lastWidth = width;
                    lastHeight = height;
                    graph.changeSize(width, height);
                    graph.fitView(40);
                }
            });
            observer.observe(container);
        }

        function pulseNode(item) {
            var shape = item.getKeyShape();
            shape.stopAnimate();
            shape.animate(
                function (ratio) {
                    var wobble = Math.sin(ratio * Math.PI * 2);
                    return {
                        r: NODE_RADIUS + wobble * 4,
                        shadowBlur: 26 + wobble * 16,
                    };
                },
                { repeat: true, duration: 1400 }
            );
        }

        function unpulseNode(item) {
            var shape = item.getKeyShape();
            shape.stopAnimate();
            shape.attr({ r: NODE_RADIUS, shadowBlur: 14, shadowColor: "rgba(0, 0, 0, 0.45)" });
        }

        function flowEdge(item) {
            var shape = item.getKeyShape();
            shape.stopAnimate();
            shape.animate(
                function (ratio) {
                    return { lineDash: [6, 4], lineDashOffset: -ratio * 40 };
                },
                { repeat: true, duration: 900 }
            );
        }

        function unflowEdge(item) {
            var shape = item.getKeyShape();
            shape.stopAnimate();
            shape.attr("lineDash", null);
        }

        function findEdgeBetween(graph, aId, bId) {
            var edges = graph.getEdges();
            for (var i = 0; i < edges.length; i++) {
                var model = edges[i].getModel();
                if ((model.source === aId && model.target === bId) || (model.source === bId && model.target === aId)) {
                    return edges[i];
                }
            }
            return null;
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

        function escapeHtml(str) {
            var div = document.createElement("div");
            div.textContent = str;
            return div.innerHTML;
        }

        function setupTimeline(graph, killchain) {
            var mapped = killchain.filter(function (entry) {
                return entry.infra_node_id !== null && entry.infra_node_id !== undefined;
            });
            var unmapped = killchain.filter(function (entry) {
                return entry.infra_node_id === null || entry.infra_node_id === undefined;
            });

            var playBtn = document.getElementById("timeline-play");
            var stepBackBtn = document.getElementById("timeline-step-back");
            var stepForwardBtn = document.getElementById("timeline-step-forward");
            var scrubber = document.getElementById("timeline-scrubber");
            var readout = document.getElementById("timeline-readout");
            var unmappedList = document.getElementById("unmapped-entries");

            renderUnmapped(unmapped, unmappedList);

            if (mapped.length === 0) {
                playBtn.disabled = true;
                stepBackBtn.disabled = true;
                stepForwardBtn.disabled = true;
                scrubber.disabled = true;
                readout.textContent = "No kill chain entries linked to infrastructure yet.";
                return;
            }

            scrubber.max = String(mapped.length - 1);

            var currentIndex = -1;
            var playing = false;
            var playHandle = null;
            var pulsingNode = null;
            var flowingEdge = null;

            function clearHighlights() {
                graph.getNodes().forEach(function (n) {
                    graph.clearItemStates(n);
                });
                graph.getEdges().forEach(function (e) {
                    graph.clearItemStates(e);
                });
                if (pulsingNode) {
                    unpulseNode(pulsingNode);
                    pulsingNode = null;
                }
                if (flowingEdge) {
                    unflowEdge(flowingEdge);
                    flowingEdge = null;
                }
            }

            function showStep(index) {
                if (index < 0) index = 0;
                if (index > mapped.length - 1) index = mapped.length - 1;
                currentIndex = index;
                scrubber.value = String(index);

                clearHighlights();

                for (var j = 1; j <= index; j++) {
                    var prevId = "n" + mapped[j - 1].infra_node_id;
                    var curId = "n" + mapped[j].infra_node_id;
                    var edge = findEdgeBetween(graph, prevId, curId);
                    if (edge) {
                        if (j === index) {
                            graph.setItemState(edge, "active", true);
                            flowEdge(edge);
                            flowingEdge = edge;
                        } else {
                            graph.setItemState(edge, "visited", true);
                        }
                    }
                }

                for (var k = 0; k < index; k++) {
                    var visitedNode = graph.findById("n" + mapped[k].infra_node_id);
                    if (visitedNode) {
                        graph.setItemState(visitedNode, "visited", true);
                    }
                }

                var entry = mapped[index];
                var activeNode = graph.findById("n" + entry.infra_node_id);
                if (activeNode) {
                    graph.setItemState(activeNode, "active", true);
                    pulseNode(activeNode);
                    pulsingNode = activeNode;
                    graph.focusItem(activeNode, true, { easing: "easeCubic", duration: 400 });
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
    });
})();
