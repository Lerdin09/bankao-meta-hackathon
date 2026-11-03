/**
 * Copilot Charts — Gráficos inline interativos na conversa
 * Suporta: Donut (clicável por fatia), Linha, Barras, Previsão de Saldo
 */

const CHART_PALETTE = [
    "#38BDF8","#34D399","#F59E0B","#818CF8","#EC4899",
    "#FB923C","#A78BFA","#6EE7B7","#FCD34D","#93C5FD"
];

/**
 * buildCopilotChart(chartData) → HTMLElement
 * Renderiza o tipo de gráfico correto com base em chartData.type
 */
function buildCopilotChart(chartData) {
    if (!chartData || !chartData.type) return null;
    switch (chartData.type) {
        case "donut":    return buildDonutChart(chartData);
        case "line":     return buildLineChart(chartData);
        case "bar":      return buildBarChart(chartData);
        case "forecast": return buildForecastChart(chartData);
        default:         return null;
    }
}

/* ═══════════════════════════════════════════════════════════════
   DONUT CHART — Clicável por fatia
   ═══════════════════════════════════════════════════════════════ */
function buildDonutChart(data) {
    const wrap = document.createElement("div");
    wrap.className = "copilot-chart-wrap";

    const segments = data.segments || [];
    const total = data.total || segments.reduce((s, x) => s + x.value, 0);
    const title = data.title || "Distribuição";

    // Canvas
    const canvas = document.createElement("canvas");
    canvas.width = 200;
    canvas.height = 200;
    canvas.style.cssText = "width:200px;height:200px;display:block;margin:0 auto 12px;cursor:pointer";

    // Tooltip
    const tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    tooltip.hidden = true;

    // Legenda clicável
    const legend = document.createElement("div");
    legend.className = "chart-legend";

    // Calcular arcos
    let arcs = [];
    let startAngle = -Math.PI / 2;
    segments.forEach((seg, i) => {
        const sweep = (seg.value / total) * 2 * Math.PI;
        arcs.push({
            ...seg,
            startAngle,
            endAngle: startAngle + sweep,
            color: CHART_PALETTE[i % CHART_PALETTE.length]
        });
        startAngle += sweep;
    });

    // Renderizar canvas
    function drawDonut(highlightIdx = -1) {
        const ctx = canvas.getContext("2d");
        const cx = 100, cy = 100, r = 80, ir = 52;
        ctx.clearRect(0, 0, 200, 200);

        arcs.forEach((arc, i) => {
            ctx.beginPath();
            const scale = (i === highlightIdx) ? 1.06 : 1;
            ctx.save();
            if (scale > 1) {
                ctx.translate(cx, cy);
                ctx.scale(scale, scale);
                ctx.translate(-cx, -cy);
            }
            ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, r, arc.startAngle, arc.endAngle);
            ctx.closePath();
            ctx.fillStyle = arc.color;
            ctx.globalAlpha = (highlightIdx >= 0 && i !== highlightIdx) ? 0.45 : 1;
            ctx.fill();
            ctx.restore();

            // Borda branca
            ctx.beginPath();
            ctx.arc(cx, cy, r, arc.startAngle, arc.endAngle);
            ctx.arc(cx, cy, ir, arc.endAngle, arc.startAngle, true);
            ctx.closePath();
            ctx.strokeStyle = "rgba(255,255,255,0.06)";
            ctx.lineWidth = 1.5;
            ctx.stroke();
        });

        // Buraco central
        ctx.beginPath();
        ctx.arc(cx, cy, ir, 0, Math.PI * 2);
        ctx.fillStyle = "#0D1117";
        ctx.fill();

        // Texto central
        ctx.fillStyle = "#FFFFFF";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (highlightIdx >= 0) {
            const s = arcs[highlightIdx];
            ctx.font = "bold 11px Inter, sans-serif";
            ctx.fillStyle = s.color;
            ctx.fillText(s.label.length > 12 ? s.label.slice(0,11)+"…" : s.label, cx, cy - 10);
            ctx.font = "bold 14px JetBrains Mono, monospace";
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(`${s.pct}%`, cx, cy + 8);
        } else {
            ctx.font = "bold 12px Inter, sans-serif";
            ctx.fillStyle = "rgba(255,255,255,0.6)";
            ctx.fillText("Total", cx, cy - 12);
            ctx.font = "bold 14px JetBrains Mono, monospace";
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(formatMoney(total, "AOA").replace(" Kz",""), cx, cy + 6);
            ctx.font = "10px Inter";
            ctx.fillStyle = "rgba(255,255,255,0.4)";
            ctx.fillText("Kz", cx, cy + 20);
        }
    }

    drawDonut();

    // Eventos do mouse no canvas
    function getArcAt(x, y) {
        const cx = 100, cy = 100;
        const dx = x - cx, dy = y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 52 || dist > 85) return -1;
        let angle = Math.atan2(dy, dx);
        if (angle < -Math.PI / 2) angle += 2 * Math.PI;
        return arcs.findIndex(a => angle >= a.startAngle - Math.PI/2 + Math.PI/2 && angle < a.endAngle - Math.PI/2 + Math.PI/2);
    }

    let hoveredIdx = -1;
    canvas.addEventListener("mousemove", e => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = 200 / rect.width;
        const scaleY = 200 / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;
        const idx = getArcHit(x, y);
        if (idx !== hoveredIdx) {
            hoveredIdx = idx;
            drawDonut(idx);
            if (idx >= 0) {
                const s = arcs[idx];
                tooltip.hidden = false;
                tooltip.innerHTML = `<span style="color:${s.color}">${s.emoji || "💳"} ${s.label}</span><strong>${formatMoney(s.value, "AOA")}</strong><span>${s.pct}%</span>`;
            } else {
                tooltip.hidden = true;
            }
        }
    });
    canvas.addEventListener("mouseleave", () => {
        hoveredIdx = -1;
        drawDonut(-1);
        tooltip.hidden = true;
    });

    // Click → destacar fatia com animação e scroll para legenda
    canvas.addEventListener("click", e => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = 200 / rect.width;
        const scaleY = 200 / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;
        const idx = getArcHit(x, y);
        if (idx < 0) return;
        const s = arcs[idx];
        // highlight na legenda
        legend.querySelectorAll(".chart-legend-item").forEach((el, i) => {
            el.classList.toggle("active", i === idx);
        });
    });

    // Função auxiliar para hit-test (ângulo independente de rotação)
    function getArcHit(x, y) {
        const cx = 100, cy = 100;
        const dx = x - cx, dy = y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 50 || dist > 86) return -1;
        let angle = Math.atan2(dy, dx);
        // Normalizar para começar do topo (-PI/2)
        angle -= (-Math.PI / 2);
        if (angle < 0) angle += 2 * Math.PI;
        return arcs.findIndex(a => {
            let start = a.startAngle + Math.PI / 2;
            let end = a.endAngle + Math.PI / 2;
            if (start < 0) start += 2 * Math.PI;
            if (end < 0) end += 2 * Math.PI;
            if (start > end) return angle >= start || angle < end;
            return angle >= start && angle < end;
        });
    }

    // Legenda
    legend.innerHTML = arcs.map((arc, i) => `
        <div class="chart-legend-item" data-idx="${i}" style="--c:${arc.color}">
            <span class="legend-dot" style="background:${arc.color}"></span>
            <span class="legend-emoji">${arc.emoji || "💳"}</span>
            <span class="legend-label">${arc.label}</span>
            <span class="legend-pct">${arc.pct}%</span>
            <span class="legend-val">${formatMoney(arc.value, "AOA")}</span>
        </div>
    `).join("");

    legend.querySelectorAll(".chart-legend-item").forEach((el, i) => {
        el.addEventListener("click", () => {
            drawDonut(i);
            el.parentElement.querySelectorAll(".chart-legend-item").forEach((e2, j) => {
                e2.classList.toggle("active", j === i);
            });
            tooltip.hidden = false;
            const s = arcs[i];
            tooltip.innerHTML = `<span style="color:${s.color}">${s.emoji || "💳"} ${s.label}</span><strong>${formatMoney(s.value, "AOA")}</strong><span>${s.pct}%</span>`;
            setTimeout(() => { drawDonut(-1); tooltip.hidden = true; el.parentElement.querySelectorAll(".chart-legend-item").forEach(e2 => e2.classList.remove("active")); }, 3000);
        });
    });

    wrap.innerHTML = `<div class="copilot-chart-title">${title}</div>`;
    wrap.appendChild(canvas);
    wrap.appendChild(tooltip);
    wrap.appendChild(legend);
    return wrap;
}

/* ═══════════════════════════════════════════════════════════════
   LINE CHART — Evolução mensal
   ═══════════════════════════════════════════════════════════════ */
function buildLineChart(data) {
    const wrap = document.createElement("div");
    wrap.className = "copilot-chart-wrap";

    const points = data.points || [];
    if (points.length === 0) return null;
    const title = data.title || "Evolução";
    const values = points.map(p => p.value);
    const maxVal = Math.max(...values, 1);
    const minVal = Math.min(...values, 0);
    const range = maxVal - minVal || 1;

    const W = 340, H = 140, PAD = 28;

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.style.cssText = `width:100%;height:${H}px;display:block;overflow:visible`;

    // Linhas de grade
    for (let i = 0; i <= 3; i++) {
        const y = PAD + ((H - PAD * 2) / 3) * i;
        const gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
        gridLine.setAttribute("x1", PAD); gridLine.setAttribute("x2", W - 10);
        gridLine.setAttribute("y1", y); gridLine.setAttribute("y2", y);
        gridLine.setAttribute("stroke", "rgba(255,255,255,0.05)");
        gridLine.setAttribute("stroke-width", "1");
        svg.appendChild(gridLine);
    }

    // Pontos calculados
    const ptCoords = points.map((p, i) => ({
        x: PAD + (i / (points.length - 1)) * (W - PAD - 10),
        y: PAD + (1 - (p.value - minVal) / range) * (H - PAD * 2),
        ...p
    }));

    // Área preenchida
    const areaPath = `M ${ptCoords[0].x} ${H - PAD} ` +
        ptCoords.map(p => `L ${p.x} ${p.y}`).join(" ") +
        ` L ${ptCoords[ptCoords.length - 1].x} ${H - PAD} Z`;
    const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
    area.setAttribute("d", areaPath);
    area.setAttribute("fill", "url(#lineGrad)");
    area.setAttribute("opacity", "0.3");

    // Gradiente
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
        <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38BDF8" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="#38BDF8" stop-opacity="0"/>
        </linearGradient>`;
    svg.appendChild(defs);
    svg.appendChild(area);

    // Linha principal
    const linePath = "M " + ptCoords.map(p => `${p.x} ${p.y}`).join(" L ");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute("d", linePath);
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "#38BDF8");
    line.setAttribute("stroke-width", "2.5");
    line.setAttribute("stroke-linecap", "round");
    svg.appendChild(line);

    // Pontos interativos + labels
    ptCoords.forEach((p, i) => {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", p.x); circle.setAttribute("cy", p.y);
        circle.setAttribute("r", "5");
        circle.setAttribute("fill", "#38BDF8");
        circle.setAttribute("stroke", "#0D1117");
        circle.setAttribute("stroke-width", "2");
        circle.style.cursor = "pointer";
        circle.setAttribute("title", `${p.label}: ${formatMoney(p.value, "AOA")}`);

        // Label mês
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", p.x); label.setAttribute("y", H - 8);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "rgba(255,255,255,0.45)");
        label.setAttribute("font-size", "10");
        label.textContent = p.label;
        svg.appendChild(label);

        // Tooltip ao hover
        const tipText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        tipText.setAttribute("x", p.x); tipText.setAttribute("y", p.y - 12);
        tipText.setAttribute("text-anchor", "middle");
        tipText.setAttribute("fill", "#38BDF8");
        tipText.setAttribute("font-size", "10");
        tipText.setAttribute("font-weight", "bold");
        tipText.textContent = "";
        tipText.style.opacity = "0";
        tipText.style.transition = "opacity 0.2s";

        circle.addEventListener("mouseenter", () => {
            circle.setAttribute("r", "7");
            tipText.textContent = p.value > 0 ? formatMoney(p.value, "AOA").replace(" Kz","K") : "0";
            tipText.style.opacity = "1";
        });
        circle.addEventListener("mouseleave", () => {
            circle.setAttribute("r", "5");
            tipText.style.opacity = "0";
        });

        svg.appendChild(tipText);
        svg.appendChild(circle);
    });

    wrap.innerHTML = `<div class="copilot-chart-title">${title}</div>`;
    wrap.appendChild(svg);
    return wrap;
}

/* ═══════════════════════════════════════════════════════════════
   BAR CHART — Categorias
   ═══════════════════════════════════════════════════════════════ */
function buildBarChart(data) {
    const wrap = document.createElement("div");
    wrap.className = "copilot-chart-wrap";
    const bars = data.bars || [];
    if (bars.length === 0) return null;

    wrap.innerHTML = `<div class="copilot-chart-title">${data.title || "Categorias"}</div>`;
    const grid = document.createElement("div");
    grid.className = "copilot-bar-grid";

    bars.forEach((b, i) => {
        const color = CHART_PALETTE[i % CHART_PALETTE.length];
        const row = document.createElement("div");
        row.className = "copilot-bar-row";
        row.innerHTML = `
            <div class="copilot-bar-label">
                <span>${b.emoji || "💳"}</span>
                <span>${b.label}</span>
            </div>
            <div class="copilot-bar-track">
                <div class="copilot-bar-fill" style="width:0%;background:${color}" data-target="${b.pct}"></div>
            </div>
            <div class="copilot-bar-val">${formatMoney(b.value, "AOA")}</div>
        `;
        grid.appendChild(row);
    });

    wrap.appendChild(grid);

    // Animação das barras
    requestAnimationFrame(() => {
        setTimeout(() => {
            wrap.querySelectorAll(".copilot-bar-fill").forEach(el => {
                el.style.transition = "width 0.6s ease";
                el.style.width = el.dataset.target + "%";
            });
        }, 100);
    });

    return wrap;
}

/* ═══════════════════════════════════════════════════════════════
   FORECAST CHART — Previsão de Saldo
   ═══════════════════════════════════════════════════════════════ */
function buildForecastChart(data) {
    const wrap = document.createElement("div");
    wrap.className = "copilot-chart-wrap forecast-chart";

    const points = data.points || [];
    if (points.length === 0) return null;

    // Usar buildLineChart mas com estilo diferente
    const lineData = {
        ...data,
        type: "line",
        title: data.title,
        points: points
    };
    const lineChart = buildLineChart(lineData);

    // Adicionar nota de previsão
    const note = document.createElement("div");
    note.className = "chart-forecast-note";
    note.textContent = "🔮 " + (data.note || "Previsão estimada com base nos seus hábitos");

    // Estatísticas
    const values = points.map(p => p.value);
    const finalVal = values[values.length - 1];
    const currentVal = data.current || 0;
    const delta = finalVal - currentVal;
    const trend = delta >= 0 ? "▲ +" : "▼ ";
    const trendColor = delta >= 0 ? "#34D399" : "#F87171";

    const stats = document.createElement("div");
    stats.className = "chart-forecast-stats";
    stats.innerHTML = `
        <div class="forecast-stat">
            <span>Saldo atual</span>
            <strong>${formatMoney(currentVal, "AOA")}</strong>
        </div>
        <div class="forecast-stat">
            <span>Previsão 6 meses</span>
            <strong style="color:${trendColor}">${trend}${formatMoney(Math.abs(delta), "AOA")}</strong>
        </div>
    `;

    wrap.innerHTML = `<div class="copilot-chart-title">${data.title || "Previsão de Saldo"}</div>`;
    if (lineChart) {
        // Extrair o SVG do lineChart
        const svg = lineChart.querySelector("svg");
        if (svg) {
            // Mudar cor para roxo/previsão
            svg.querySelectorAll("[stroke='#38BDF8']").forEach(el => {
                el.setAttribute("stroke", "#818CF8");
            });
            svg.querySelectorAll("[fill='#38BDF8']").forEach(el => {
                el.setAttribute("fill", "#818CF8");
            });
            wrap.appendChild(svg);
        }
    }
    wrap.appendChild(stats);
    wrap.appendChild(note);
    return wrap;
}
