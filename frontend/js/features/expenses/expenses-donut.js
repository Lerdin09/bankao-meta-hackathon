/**
 * Despesas — gráfico donut
 * Donut interativo, detalhe da categoria (spotlight) e lista de tipos de despesa.
 */

const DONUT_R = 70;
const DONUT_C = 2 * Math.PI * DONUT_R;

function renderInteractiveDonutChart(catTotals, activeTotal, totalPurchases) {
    const svgEl = document.getElementById("expDonutSvg");
    const hub = document.getElementById("expDonutCenterHub");
    const hubLbl = document.getElementById("expDonutHubLabel");
    const hubVal = document.getElementById("expTotalGastoVal");
    const hubSub = document.getElementById("expTotalCountVal");
    const resetBtn = document.getElementById("btnResetDonutSelection");

    if (resetBtn) resetBtn.style.visibility = selectedSpotlightCategory ? "visible" : "hidden";
    if (!svgEl) return;

    const track = `<circle cx="100" cy="100" r="${DONUT_R}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="24"/>`;
    const setHub = (label, value, sub) => {
        if (hubLbl) hubLbl.textContent = label;
        if (hubVal) {
            hubVal.textContent = value;
            hubVal.dataset.size = value.length > 11 ? "sm" : value.length > 8 ? "md" : "lg";
        }
        if (hubSub) hubSub.textContent = sub;
    };

    if (activeTotal <= 0) {
        svgEl.classList.remove("has-selection");
        svgEl.dataset.sig = "";
        svgEl.innerHTML = track;
        setHub("Sem gastos", "0 KZ", "nenhuma compra");
        if (hub) hub.disabled = true;
        return;
    }
    if (hub) hub.disabled = !selectedSpotlightCategory;

    const entries = Object.entries(catTotals)
        .filter(([cat, amt]) => selectedCategoriesForChart.has(cat) && amt > 0)
        .sort((a, b) => b[1] - a[1]);
    const gap = entries.length > 1 ? 2.5 : 0;

    let offset = 0;
    let arcs = "";
    entries.forEach(([cat, amt]) => {
        const pct = amt / activeTotal;
        const full = pct * DONUT_C;
        const arc = Math.max(full - gap, 0.5);
        const color = (EXPENSE_CATEGORIES[cat] && EXPENSE_CATEGORIES[cat].color) || "#64748B";
        const sel = selectedSpotlightCategory === cat;
        const tip = `${cat}: ${fmtKz(amt)} (${Math.round(pct * 100)}%)`;
        arcs += `
            <circle class="xp-arc ${sel ? "is-selected" : ""}" data-cat="${cat}" cx="100" cy="100" r="${DONUT_R}" fill="none"
                stroke="${color}" stroke-width="24"
                stroke-dasharray="${arc} ${DONUT_C - arc}" stroke-dashoffset="${-(offset + gap / 2)}"
                tabindex="0" role="button" aria-label="${tip}"
                onclick="handleDonutCategoryClick('${cat}')"
                onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();handleDonutCategoryClick('${cat}')}">
                <title>${tip}</title>
            </circle>`;
        offset += full;
    });

    svgEl.classList.toggle("has-selection", !!selectedSpotlightCategory);
    // Só recria o SVG quando os dados mudam; ao selecionar apenas troca classes (sem saltos)
    const sig = entries.map(([c, a]) => c + ":" + a).join("|") + "|" + activeTotal;
    if (svgEl.dataset.sig === sig) {
        svgEl.querySelectorAll(".xp-arc").forEach(a => a.classList.toggle("is-selected", a.dataset.cat === selectedSpotlightCategory));
    } else {
        svgEl.dataset.sig = sig;
        svgEl.innerHTML = `${track}<g transform="rotate(-90 100 100)">${arcs}</g>`;
    }

    if (selectedSpotlightCategory && catTotals[selectedSpotlightCategory] !== undefined) {
        const catAmt = catTotals[selectedSpotlightCategory] || 0;
        setHub(selectedSpotlightCategory, fmtKz(catAmt), `${Math.round((catAmt / activeTotal) * 100)}% do gráfico`);
    } else {
        setHub("Total no gráfico", fmtKz(activeTotal), `${totalPurchases} compra${totalPurchases === 1 ? "" : "s"}`);
    }
}

function renderDonutSpotlight(catTotals, catCounts, activeTotal) {
    const emptyState = document.getElementById("spotlightEmptyState");
    const content = document.getElementById("spotlightContent");
    if (!emptyState || !content) return;

    // Os dois estados ficam empilhados na mesma área: a altura do card nunca muda
    const card = document.getElementById("expDonutSpotlightCard");
    if (card) card.classList.toggle("has-cat", !!selectedSpotlightCategory);
    if (!selectedSpotlightCategory) return;

    const cat = selectedSpotlightCategory;
    const amt = catTotals[cat] || 0;
    const count = catCounts[cat] || 0;
    const info = EXPENSE_CATEGORIES[cat] || { icon: "#i-receipt", color: "#64748B", label: cat };
    const factor = getBudgetFactor();
    const budget = (getCategoryBudgets()[cat] || 35000) * factor;

    const $ = id => document.getElementById(id);
    const iconWrap = $("spotlightIconWrap");
    if (iconWrap) {
        iconWrap.innerHTML = `<svg><use href="${info.icon}"/></svg>`;
        iconWrap.style.background = `${info.color}22`;
        iconWrap.style.borderColor = `${info.color}55`;
        iconWrap.style.color = info.color;
    }
    $("spotlightName").textContent = info.label || cat;

    const share = activeTotal > 0 ? Math.round((amt / activeTotal) * 100) : 0;
    const badge = $("spotlightShareBadge");
    badge.textContent = `${share}% do gráfico`;
    badge.style.color = info.color;
    badge.style.borderColor = `${info.color}55`;
    badge.style.background = `${info.color}18`;

    $("spotlightPurchasesCount").textContent = `${count} ${count === 1 ? "compra" : "compras"}`;
    $("spotlightTotalSpent").textContent = fmtKz(amt);
    $("spotlightBudgetLabel").textContent = factor > 1 ? `Meta (${factor} meses)` : "Meta mensal";
    $("spotlightNormalSpent").textContent = fmtKz(budget);

    const used = budget > 0 ? (amt / budget) * 100 : 0;
    const fill = $("spotlightMeterFill");
    const trend = $("spotlightTrendBadge");
    const state = amt === 0 ? "neutral" : amt > budget ? "danger" : used >= 85 ? "warn" : "success";
    fill.style.width = `${Math.min(100, used)}%`;
    fill.dataset.state = state;
    trend.dataset.state = state;
    if (amt === 0) {
        trend.textContent = "Sem gastos no período";
    } else if (amt > budget) {
        trend.textContent = `${fmtKz(amt - budget)} acima da meta (+${Math.round(((amt - budget) / budget) * 100)}%)`;
    } else {
        trend.textContent = `${fmtKz(budget - amt)} livres · ${Math.round(used)}% da meta usada`;
    }
}

function renderSelectableExpenseTypes(catTotals, catCounts, activeTotal, grandTotal) {
    const listEl = document.getElementById("expTypesList");
    if (!listEl) return;

    const factor = getBudgetFactor();
    const budgets = getCategoryBudgets();
    const entries = Object.entries(catTotals).sort((a, b) => b[1] - a[1]);

    listEl.innerHTML = entries.map(([cat, amt]) => {
        const info = EXPENSE_CATEGORIES[cat] || { icon: "#i-receipt", color: "#64748B", label: cat };
        const on = selectedCategoriesForChart.has(cat);
        const spot = selectedSpotlightCategory === cat;
        const count = catCounts[cat] || 0;
        const base = on ? activeTotal : grandTotal;
        const pct = base > 0 ? Math.round((amt / base) * 100) : 0;
        const over = amt > (budgets[cat] || 35000) * factor;

        const sub = [`${count} ${count === 1 ? "gasto" : "gastos"}`];
        if (over) sub.push(`<span class="over">acima da meta</span>`);

        return `
            <div class="xp-type ${on ? "" : "is-off"} ${spot ? "is-spot" : ""}" style="--c:${info.color}">
                <label class="xp-check" title="${on ? "Retirar do gráfico" : "Incluir no gráfico"}">
                    <input type="checkbox" ${on ? "checked" : ""} onchange="toggleChartCategory('${cat}')" aria-label="Incluir ${cat} no gráfico">
                    <span><svg><use href="#i-check"/></svg></span>
                </label>
                <button type="button" class="xp-type-main" onclick="handleDonutCategoryClick('${cat}')" aria-pressed="${spot}">
                    <span class="xp-type-icon"><svg><use href="${info.icon}"/></svg></span>
                    <span class="xp-type-info">
                        <span class="xp-type-top"><b>${cat}</b><em>${sub.join(" · ")}</em></span>
                        <span class="xp-type-bar"><i style="width:${on ? pct : 0}%"></i></span>
                    </span>
                    <span class="xp-type-val">
                        <b>${fmtKz(amt)}</b>
                        <em>${on ? pct + "%" : "fora"}</em>
                    </span>
                </button>
            </div>`;
    }).join("");
}
