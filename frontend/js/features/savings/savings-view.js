/**
 * Poupança — vista
 * Desenha o resumo, o anel de progresso e os cartões das metas (view-savings).
 */

function renderSavingsView() {
    const goals = getSavingsGoals();
    const totalSaved = goals.reduce((acc, g) => acc + (Number(g.saved) || 0), 0);
    const totalTarget = goals.reduce((acc, g) => acc + (Number(g.target) || 0), 0);
    const globalPct = totalTarget > 0 ? Math.min(100, Math.round((totalSaved / totalTarget) * 100)) : 0;

    const elTotal = document.getElementById("savTotalBalance");
    if (elTotal) elTotal.textContent = formatTwoTierMoney(totalSaved, "AOA");

    const elCountBadge = document.getElementById("savGoalCount");
    const elCountHero = document.getElementById("savGoalCountHero");
    const countText = `${goals.length} meta${goals.length === 1 ? "" : "s"} ativa${goals.length === 1 ? "" : "s"}`;
    if (elCountBadge) elCountBadge.textContent = countText;
    if (elCountHero) elCountHero.textContent = goals.length;

    // Atualizar anel gráfico de progresso SVG
    const ringChart = document.querySelector(".sav-ring-chart circle:nth-child(2)");
    const ringCenterPct = document.querySelector(".sav-ring-center strong");
    if (ringChart) {
        const circumference = 2 * Math.PI * 38; // ~238.76
        const filled = (globalPct / 100) * circumference;
        ringChart.setAttribute("stroke-dasharray", `${filled} ${circumference}`);
    }
    if (ringCenterPct) ringCenterPct.textContent = `${globalPct}%`;

    // Depósitos feitos este mês (despesas ligadas a metas)
    const monthEl = document.getElementById("savMonthDeposits");
    if (monthEl && typeof getExpenses === "function") {
        const mk = localISODate(0).slice(0, 7);
        const v = getExpenses().filter(e => e.goalId && String(e.date).slice(0, 7) === mk)
            .reduce((a, e) => a + (Number(e.amount) || 0), 0);
        monthEl.textContent = "+" + formatTwoTierMoney(v, "AOA");
    }
    renderSavingsCopilot(goals);

    const listEl = document.getElementById("savGoalsList");
    if (!listEl) return;

    if (goals.length === 0) {
        listEl.innerHTML = `<div class="empty">Nenhuma meta criada ainda. Clique em "Nova meta" para começar!</div>`;
        return;
    }

    // Mapa de ícones SVG por categoria de meta (sem emojis)
    const GOAL_ICONS = {
        travel:    "#i-plane",
        home:      "#i-home",
        car:       "#i-car",
        laptop:    "#i-laptop",
        education: "#i-book",
        target:    "#i-target",
        shield:    "#i-shield",
        award:     "#i-award",
        savings:   "#i-piggy",
        health:    "#i-heart",
        default:   "#i-target"
    };

    const EMOJI_TO_KEY = {
        "✈️": "travel", "🏠": "home", "🚗": "car", "💻": "laptop",
        "🎓": "education", "💍": "award", "🛡️": "shield", "🏖️": "travel", "🎯": "target"
    };

    listEl.innerHTML = goals.map(g => {
        const saved = Number(g.saved) || 0, target = Number(g.target) || 0, monthly = Number(g.monthly) || 0;
        const pct = target > 0 ? Math.min(100, Math.round((saved / target) * 100)) : 0;
        const done = g.status === "completed" || pct >= 100;
        const statusClass = done ? "done" : g.status === "at-risk" ? "at-risk" : "on-track";
        const statusLabel = done ? "Concluída" : g.status === "at-risk" ? "Em risco" : "No prazo";
        const iconKey = g.iconKey || EMOJI_TO_KEY[g.icon] || "default";
        const iconHref = GOAL_ICONS[iconKey] || GOAL_ICONS.default;
        const iconGrad = g.gradient || "linear-gradient(135deg,#38BDF8,#6366F1)";
        const left = Math.max(0, target - saved);
        const eta = !done && monthly > 0 ? Math.ceil(left / monthly) : 0;
        const leftChip = done ? "Meta atingida" : `Faltam <b class="sg-money">${formatMoney(left, "AOA")}</b>${eta ? ` · ~${eta} ${eta === 1 ? "mês" : "meses"}` : ""}`;

        return `
            <article class="sg-card ${statusClass}" id="goal_${g.id}">
                <header class="sg-head">
                    <div class="sg-icon" style="background:${iconGrad}"><svg><use href="${iconHref}"/></svg></div>
                    <div class="sg-title">
                        <h4>${escapeHtml(g.name)}</h4>
                        <span><svg><use href="#i-calendar"/></svg>Prazo: ${escapeHtml(g.deadline)}</span>
                        ${g.debitDay && !done ? `<span><svg><use href="#i-refresh"/></svg>Débito automático: dia ${g.debitDay}${g.nextDebit ? ` · próximo ${new Date(g.nextDebit + "T00:00:00").toLocaleDateString("pt-AO", { day: "numeric", month: "short" })}` : ""}</span>` : ""}
                    </div>
                    <span class="sg-status ${statusClass}">${statusLabel}</span>
                </header>
                <div class="sg-amounts">
                    <span class="bal-swap">
                        <span class="bal-mask acc-bal-masked" aria-hidden="true">••••••</span>
                        <strong class="bal-real sav-prog-saved">${formatTwoTierMoney(saved, "AOA")}</strong>
                    </span>
                    <span class="sav-prog-target">de ${formatTwoTierMoney(target, "AOA")}</span>
                    <b class="sg-pct">${pct}%</b>
                </div>
                <div class="sg-track"><i style="width:${pct}%"></i></div>
                <p class="sg-meta">${leftChip}<i></i>Mensal <b class="sg-money">${formatMoney(monthly, "AOA")}</b></p>
                <footer class="sg-actions">
                    <button type="button" class="sg-btn primary" onclick="openDepositGoalModal('${g.id}')"><svg><use href="#i-down"/></svg><span>Depositar</span></button>
                    <button type="button" class="sg-btn icon" onclick="openEditGoalModal('${g.id}')" title="Editar meta" aria-label="Editar meta ${escapeHtml(g.name)}"><svg><use href="#i-edit"/></svg></button>
                    <button type="button" class="sg-btn icon danger" onclick="deleteSavingsGoal('${g.id}')" title="Apagar meta" aria-label="Apagar meta ${escapeHtml(g.name)}"><svg><use href="#i-trash"/></svg></button>
                </footer>
            </article>`;
    }).join("");
}

// ---------- Copilot de poupança: análise real das metas e dos gastos ----------
const SAV_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
function monthsUntilDeadline(txt) {
    const m = String(txt || "").toLowerCase().match(/([a-zç]+)\s+(\d{4})/);
    if (!m) return null;
    const idx = SAV_MONTHS.indexOf(m[1]);
    if (idx < 0) return null;
    const now = new Date();
    return (Number(m[2]) - now.getFullYear()) * 12 + (idx - now.getMonth());
}

function renderSavingsCopilot(goals) {
    const el = document.getElementById("savCopilotInsights");
    const chipsEl = document.getElementById("savCopilotChips");
    if (!el) return;
    const $ = v => `<b class="sg-money">${formatMoney(v, "AOA")}</b>`;
    const row = (tone, icon, title, html) => `
        <div class="sgc-row" data-tone="${tone}">
            <span class="sgc-ico"><svg><use href="${icon}"/></svg></span>
            <div><h5>${title}</h5><p>${html}</p></div>
        </div>`;
    const rows = [];
    const chips = [];

    if (!goals.length) {
        rows.push(row("info", "#i-target", "Comece por uma meta", "Crie a sua primeira meta de poupança e o Copilot passa a acompanhar o seu ritmo e a sugerir ajustes."));
        chips.push("Como começar a poupar?");
    } else {
        const info = goals.map(g => {
            const rem = Math.max(0, (Number(g.target) || 0) - (Number(g.saved) || 0));
            const monthly = Number(g.monthly) || 0;
            const ml = monthsUntilDeadline(g.deadline);
            const need = ml && ml > 0 ? Math.ceil(rem / ml) : null;
            return { g, rem, monthly, ml, need };
        });
        const open = info.filter(x => x.rem > 0);
        const totalRem = open.reduce((a, x) => a + x.rem, 0);
        const totalMonthly = open.reduce((a, x) => a + x.monthly, 0);

        if (!open.length) {
            rows.push(row("good", "#i-check", "Todas as metas atingidas", "Parabéns! Defina uma nova meta para manter o hábito de poupar."));
        } else if (totalMonthly > 0) {
            const months = Math.ceil(totalRem / totalMonthly);
            rows.push(row("info", "#i-trending", "Ritmo atual", `Com ${$(totalMonthly)} por mês em contribuições, conclui todas as metas em cerca de <b>${months} ${months === 1 ? "mês" : "meses"}</b>.`));
        } else {
            rows.push(row("warn", "#i-target", "Sem contribuição mensal", "Nenhuma meta tem depósito mensal definido. Defina um valor para projetar quando as atinge."));
        }

        const late = open.filter(x => x.ml !== null && (x.ml <= 0 || x.monthly < x.need))
            .sort((a, b) => (b.need || b.rem) - (a.need || a.rem));
        if (late.length) {
            const t = late[0];
            const txt = t.ml <= 0
                ? `O prazo de <b>${escapeHtml(t.g.name)}</b> já passou e faltam ${$(t.rem)}. Considere redefinir a data.`
                : `<b>${escapeHtml(t.g.name)}</b> precisa de ${$(t.need)} por mês para chegar a ${escapeHtml(t.g.deadline)} (hoje: ${$(t.monthly)}).`;
            rows.push(row("warn", "#i-target", late.length > 1 ? `Metas em risco (${late.length})` : "Meta em risco", txt));
            chips.push(`Como recuperar a meta ${t.g.name}?`);
        }

        const closest = open.map(x => ({ ...x, p: Math.round(((Number(x.g.saved) || 0) / (Number(x.g.target) || 1)) * 100) })).sort((a, b) => b.p - a.p)[0];
        if (closest && closest.p > 0) {
            rows.push(row("good", "#i-award", "Mais perto de concluir", `<b>${escapeHtml(closest.g.name)}</b> está a <b>${closest.p}%</b>. Faltam ${$(closest.rem)}.`));
        }

        if (typeof getExpenses === "function" && typeof localISODate === "function") {
            const mk = localISODate(0).slice(0, 7);
            const byCat = {};
            getExpenses().filter(e => String(e.date).slice(0, 7) === mk && e.category !== "Poupança")
                .forEach(e => { byCat[e.category] = (byCat[e.category] || 0) + (Number(e.amount) || 0); });
            const top = Object.entries(byCat).sort((a, b) => b[1] - a[1])[0];
            if (top && top[1] > 0) {
                const free = Math.round(top[1] * 0.1 / 500) * 500;
                if (free > 0) rows.push(row("tip", "#i-spark", "Onde poupar mais", `Reduzir 10% em <b>${escapeHtml(top[0])}</b> (${$(top[1])} este mês) liberta ${$(free)} por mês para as suas metas.`));
            }
        }
        chips.push("Como atingir as metas mais cedo?", "Onde posso cortar gastos?");
    }
    el.innerHTML = rows.join("");
    if (chipsEl) {
        chipsEl.innerHTML = chips.slice(0, 3).map(c =>
            `<button type="button" onclick="askCopilotAbout(this.dataset.q)" data-q="${escapeHtml(c)}">${escapeHtml(c)}</button>`).join("");
    }
}

window.askCopilotAbout = function(text) {
    if (typeof showView === "function") showView("view-copilot");
    const input = document.getElementById("copilotUserInput");
    if (!input) return;
    input.value = text;
    input.focus();
    const form = document.getElementById("copilotInputForm");
    if (form && form.requestSubmit) setTimeout(() => form.requestSubmit(), 200);
};
