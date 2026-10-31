/**
 * Despesas — Copilot (insights) e histórico
 * Análise do período em blocos curtos, filtros por categoria e lista agrupada por dia.
 */

function updateExpenseAssistantCard(catTotals, periodExpenses) {
    const el = document.getElementById("expAssistantDesc");
    if (!el) return;

    const block = (tone, icon, title, text) => `
        <div class="xp-insight" data-tone="${tone}">
            <span class="xp-insight-ico"><svg><use href="${icon}"/></svg></span>
            <div class="xp-insight-body"><h5>${title}</h5><p>${text}</p></div>
        </div>`;

    const total = Object.values(catTotals).reduce((a, b) => a + b, 0);
    if (total <= 0) {
        el.innerHTML = block("info", "#i-spark", "Sem gastos neste período",
            "As suas contas estão intactas. Registe uma compra no campo abaixo ou com o botão <b>Registar despesa</b>.");
        return;
    }

    const factor = getBudgetFactor();
    const budgets = getCategoryBudgets();
    const [topCat, topAmt] = Object.entries(catTotals).sort((a, b) => b[1] - a[1])[0];
    const topPct = Math.round((topAmt / total) * 100);

    const overs = Object.entries(catTotals)
        .map(([c, a]) => ({ c, excess: a - (budgets[c] || 35000) * factor }))
        .filter(o => o.excess > 0)
        .sort((a, b) => b.excess - a.excess);
    const overTotal = overs.reduce((a, o) => a + o.excess, 0);

    const out = [];
    out.push(block("info", "#i-pie", "Maior concentração",
        `<b>${topCat}</b> representa <b>${topPct}%</b> dos gastos (${fmtKz(topAmt)}).`));

    if (overs.length) {
        const names = overs.length > 2
            ? `${overs.slice(0, 2).map(o => `<b>${o.c}</b>`).join(", ")} e mais ${overs.length - 2}`
            : overs.map(o => `<b>${o.c}</b>`).join(" e ");
        out.push(block("warn", "#i-target", "Acima da meta",
            `${names} ${overs.length === 1 ? "ultrapassou" : "ultrapassaram"} a meta em ${fmtKz(overTotal)} no total.`));
        out.push(block("tip", "#i-trending", "Como poupar",
            `Trazer ${overs.length === 1 ? "esta categoria" : "estas categorias"} de volta à meta liberta até <b>${fmtKz(overTotal)}</b>.`));
    } else {
        const margin = Object.entries(catTotals).reduce((a, [c, v]) => a + Math.max(0, (budgets[c] || 35000) * factor - v), 0);
        out.push(block("good", "#i-check", "Dentro das metas",
            `Todas as categorias estão dentro da meta. Margem total de <b>${fmtKz(margin)}</b>.`));
        const sav = catTotals["Poupança"] || 0;
        if (sav <= 0) {
            const suggestion = Math.round((total * 0.1) / 500) * 500;
            out.push(block("tip", "#i-piggy", "Que tal poupar?",
                `Ainda não depositou em poupança neste período. Reservar 10% dos gastos seria <b>${fmtKz(suggestion)}</b>.`));
        } else {
            out.push(block("tip", "#i-piggy", "Bom ritmo de poupança",
                `A poupança já representa <b>${Math.round((sav / total) * 100)}%</b> do que gastou (${fmtKz(sav)}).`));
        }
    }
    el.innerHTML = out.join("");
}

function dayHeading(iso) {
    if (iso === localISODate(0)) return "Hoje";
    if (iso === localISODate(-1)) return "Ontem";
    const d = new Date(iso + "T12:00:00");
    if (isNaN(d)) return "Sem data";
    const sameYear = d.getFullYear() === new Date().getFullYear();
    const t = d.toLocaleDateString("pt-AO", { weekday: "long", day: "numeric", month: "long", ...(sameYear ? {} : { year: "numeric" }) });
    return t.charAt(0).toUpperCase() + t.slice(1);
}

function renderExpenseItemsList(periodExpenses) {
    const listEl = document.getElementById("expensesList");
    const chipsEl = document.getElementById("expCategoryFilters");
    const summaryEl = document.getElementById("xpHistorySummary");
    if (!listEl) return;

    // Chips de categoria (só as que têm gastos no período) com contagem
    const counts = {};
    periodExpenses.forEach(e => {
        const c = EXPENSE_CATEGORIES[e.category] ? e.category : "Outros";
        counts[c] = (counts[c] || 0) + 1;
    });
    if (activeExpenseCategoryFilter !== "all" && !counts[activeExpenseCategoryFilter]) {
        activeExpenseCategoryFilter = "all";
    }
    if (chipsEl) {
        const chip = (cat, label, icon, n) => `
            <button type="button" role="tab" aria-selected="${activeExpenseCategoryFilter === cat}"
                class="xp-chip ${activeExpenseCategoryFilter === cat ? "active" : ""}"
                onclick="setExpenseCategoryFilter('${cat}')">
                <svg><use href="${icon}"/></svg>${label}<em>${n}</em>
            </button>`;
        chipsEl.innerHTML = chip("all", "Todas", "#i-list", periodExpenses.length) +
            Object.keys(EXPENSE_CATEGORIES).filter(c => counts[c])
                .map(c => chip(c, c === "Telecomunicações" ? "Telecom" : c, EXPENSE_CATEGORIES[c].icon, counts[c])).join("");
    }

    const filtered = periodExpenses
        .filter(e => activeExpenseCategoryFilter === "all" || (EXPENSE_CATEGORIES[e.category] ? e.category : "Outros") === activeExpenseCategoryFilter)
        .slice()
        .sort((a, b) => String(b.date).localeCompare(String(a.date)));

    const sum = filtered.reduce((a, e) => a + Number(e.amount || 0), 0);
    if (summaryEl) {
        const where = currentExpensesMonth ? monthKeyLabel(currentExpensesMonth) : "todos os meses";
        summaryEl.textContent = filtered.length
            ? `${filtered.length} ${filtered.length === 1 ? "despesa" : "despesas"} · ${fmtKz(sum)} · ${where}`
            : `Sem despesas · ${where}`;
    }

    if (!filtered.length) {
        listEl.innerHTML = `
            <div class="xp-empty">
                <div class="xp-empty-ico"><svg><use href="#i-receipt"/></svg></div>
                <h4>Nenhuma despesa encontrada</h4>
                <p>Não há gastos para este período${activeExpenseCategoryFilter === "all" ? "" : " e categoria"}.</p>
                <button type="button" class="btn btn-sm btn-primary" onclick="openNewExpenseModal()"><svg><use href="#i-plus"/></svg><span>Registar despesa</span></button>
            </div>`;
        return;
    }

    // Agrupar por dia
    const groups = [];
    filtered.forEach(e => {
        const day = String(e.date || "").slice(0, 10);
        let g = groups[groups.length - 1];
        if (!g || g.day !== day) { g = { day, items: [], total: 0 }; groups.push(g); }
        g.items.push(e);
        g.total += Number(e.amount || 0);
    });

    listEl.innerHTML = groups.map(g => `
        <section class="xp-day">
            <header class="xp-day-head"><span>${dayHeading(g.day)}</span><em>−${fmtKz(g.total)}</em></header>
            ${g.items.map(e => {
                const cat = EXPENSE_CATEGORIES[e.category] ? e.category : "Outros";
                const info = EXPENSE_CATEGORIES[cat];
                const tag = e.origin === "ai" ? `<span class="xp-tag ai">Copilot</span>`
                          : e.origin === "savings" ? `<span class="xp-tag sav">Poupança</span>` : "";
                return `
                <div class="xp-item" id="exp_${e.id}" style="--c:${info.color}">
                    <span class="xp-item-icon"><svg><use href="${info.icon}"/></svg></span>
                    <div class="xp-item-main">
                        <div class="xp-item-name"><b>${escapeHtml(e.name)}</b>${tag}</div>
                        <div class="xp-item-meta"><span>${escapeHtml(cat)}</span>${e.notes ? `<span class="xp-note">${escapeHtml(e.notes)}</span>` : ""}</div>
                    </div>
                    <div class="xp-item-right">
                        <strong>−${fmtKz(e.amount)}</strong>
                        <div class="xp-item-actions">
                            <button type="button" class="xp-icon-btn" title="Editar despesa" aria-label="Editar despesa" onclick="openEditExpenseModal('${e.id}')"><svg><use href="#i-edit"/></svg></button>
                            <button type="button" class="xp-icon-btn danger" title="Apagar despesa" aria-label="Apagar despesa" onclick="deleteExpense('${e.id}')"><svg><use href="#i-trash"/></svg></button>
                        </div>
                    </div>
                </div>`;
            }).join("")}
        </section>`).join("");
}

// Mantido por compatibilidade com shell.js (os chips são agora gerados em renderExpenseItemsList)
function initExpenseCategoryFilters() {}
