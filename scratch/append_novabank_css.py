# Script to append NovaBank CSS styles to frontend/style.css
css_rules = """
/* ==========================================================================
   NOVABANK / BANKAO — REFINED DASHBOARD & FLOATING GLASS SIDEBAR
   Inspirado no visual premium "NovaBank": dark glassmorphism, brilho aurora,
   curvas neon, cartões flutuantes e listas elegantes.
   ========================================================================== */

/* ---------- Sidebar Estilo NovaBank ---------- */
@media (min-width: 1024px) {
    .shell {
        display: grid;
        grid-template-columns: 260px minmax(0, 1fr);
        gap: 0;
        background: radial-gradient(1200px 800px at 20% -10%, rgba(56, 189, 248, 0.08), transparent 70%),
                    radial-gradient(1000px 700px at 85% 20%, rgba(129, 140, 248, 0.06), transparent 70%),
                    #070B14;
        min-height: calc(100dvh - var(--banner-h));
    }

    aside.sidebar {
        display: flex !important;
        flex-direction: column;
        justify-content: space-between;
        gap: 20px;
        position: sticky;
        top: 16px;
        height: calc(100dvh - var(--banner-h) - 32px);
        margin: 16px 0 16px 16px;
        padding: 24px 16px;
        background: rgba(11, 17, 32, 0.75);
        backdrop-filter: blur(24px) saturate(180%);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 28px;
        box-shadow: 0 20px 48px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        z-index: 40;
    }

    .sidebar .brand {
        padding: 4px 10px;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .sidebar .brand-mark {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        background: linear-gradient(135deg, #38BDF8 0%, #6366F1 50%, #A855F7 100%);
        box-shadow: 0 6px 18px -4px rgba(99, 102, 241, 0.6);
        color: #FFFFFF;
        font-weight: 800;
        font-size: 1.15rem;
    }

    .sidebar .brand-name {
        font-size: 1.3rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #F8FAFC;
    }

    .side-nav {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 14px;
        flex: 1;
        overflow-y: auto;
        scrollbar-width: none;
    }
    .side-nav::-webkit-scrollbar { display: none; }

    .side-nav .nav-item {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 14px;
        border-radius: 16px;
        color: #94A3B8;
        font-size: 0.92rem;
        font-weight: 500;
        transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
        position: relative;
        border: 1px solid transparent;
        text-align: left;
        width: 100%;
    }

    .side-nav .nav-item-icon {
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        flex-shrink: 0;
        color: inherit;
    }

    .side-nav .nav-item-icon svg {
        width: 20px;
        height: 20px;
    }

    .side-nav .nav-item-text {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .side-nav .nav-item-chevron {
        opacity: 0;
        transform: translateX(-4px);
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
    }
    .side-nav .nav-item-chevron svg {
        width: 16px;
        height: 16px;
    }

    .side-nav .nav-item:hover {
        background: rgba(255, 255, 255, 0.05);
        color: #F1F5F9;
        border-color: rgba(255, 255, 255, 0.05);
    }
    .side-nav .nav-item:hover .nav-item-chevron {
        opacity: 0.5;
        transform: translateX(0);
    }

    .side-nav .nav-item.active {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.22) 0%, rgba(99, 102, 241, 0.42) 100%);
        border: 1px solid rgba(129, 140, 248, 0.4);
        color: #FFFFFF;
        font-weight: 600;
        box-shadow: 0 8px 24px -6px rgba(99, 102, 241, 0.45);
    }

    .side-nav .nav-item.active .nav-item-icon {
        color: #38BDF8;
    }

    .side-nav .nav-item.active .nav-item-chevron {
        opacity: 0.8;
        transform: translateX(0);
        color: #E2E8F0;
    }

    /* Card de Usuário no Fim da Sidebar */
    .sidebar-user-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        transition: background 0.2s;
    }
    .sidebar-user-card:hover {
        background: rgba(255, 255, 255, 0.07);
    }

    .sidebar-avatar {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: linear-gradient(135deg, #38BDF8, #818CF8);
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.85rem;
        display: grid;
        place-items: center;
        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.15);
        flex-shrink: 0;
    }

    .sidebar-user-details {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        flex: 1;
    }

    .sidebar-user-name {
        font-size: 0.88rem;
        font-weight: 600;
        color: #F8FAFC;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .sidebar-user-badge {
        font-size: 0.72rem;
        color: #38BDF8;
        font-weight: 500;
        letter-spacing: 0.02em;
    }

    .sidebar-settings-btn {
        width: 32px;
        height: 32px;
        border-radius: 10px;
        display: grid;
        place-items: center;
        color: #94A3B8;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.06);
        transition: all 0.2s;
        cursor: pointer;
    }
    .sidebar-settings-btn:hover {
        color: #F8FAFC;
        background: rgba(255, 255, 255, 0.12);
        transform: rotate(30deg);
    }
    .sidebar-settings-btn svg {
        width: 17px;
        height: 17px;
    }
}

/* Em ecrãs pequenos ou sem sidebar desktop */
@media (max-width: 1023px) {
    .sidebar-user-card { display: none; }
}

/* ---------- Layout Geral do Dashboard NovaBank ---------- */
.nb-dash-layout {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

@media (min-width: 1100px) {
    .nb-dash-layout {
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(340px, 390px);
        gap: 28px;
        align-items: start;
    }
}

.nb-dash-main {
    display: flex;
    flex-direction: column;
    gap: 22px;
    min-width: 0;
}

/* Header de Boas-vindas */
.nb-dash-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
}

.nb-user-greeting .nb-title {
    font-size: 1.85rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.03em;
    margin: 0;
    line-height: 1.2;
}
.nb-user-greeting .wave-hand {
    display: inline-block;
    animation: waveBounce 2.5s infinite;
    transform-origin: 70% 70%;
}
@keyframes waveBounce {
    0%, 100% { transform: rotate(0deg); }
    15% { transform: rotate(14deg); }
    30% { transform: rotate(-8deg); }
    45% { transform: rotate(14deg); }
    60% { transform: rotate(-4deg); }
    75% { transform: rotate(10deg); }
}

.nb-subtitle {
    font-size: 0.92rem;
    color: #94A3B8;
    margin-top: 4px;
}

.nb-key-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    padding: 5px 12px;
    border-radius: 99px;
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.2);
    font-size: 0.82rem;
    color: #BAE6FD;
}
.nb-key-tag {
    font-weight: 600;
    color: #7DD3FC;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.nb-key-val {
    font-weight: 600;
    color: #F0F9FF;
}
.nb-key-copy-btn {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    display: grid;
    place-items: center;
    color: #7DD3FC;
    background: rgba(255, 255, 255, 0.08);
    cursor: pointer;
    transition: all 0.2s;
}
.nb-key-copy-btn:hover {
    color: #FFFFFF;
    background: rgba(56, 189, 248, 0.3);
}
.nb-key-copy-btn svg { width: 14px; height: 14px; }

/* Botão de Sino / Notificações */
.nb-bell-btn {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: rgba(18, 26, 47, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #E2E8F0;
    cursor: pointer;
    position: relative;
    transition: all 0.2s;
    backdrop-filter: blur(12px);
}
.nb-bell-btn:hover {
    background: rgba(30, 41, 70, 0.9);
    border-color: rgba(99, 102, 241, 0.4);
    transform: translateY(-2px);
}
.nb-bell-btn svg { width: 20px; height: 20px; }
.nb-bell-dot {
    position: absolute;
    top: 11px;
    right: 12px;
    width: 8px;
    height: 8px;
    background: #38BDF8;
    border-radius: 50%;
    box-shadow: 0 0 8px #38BDF8;
}

/* ---------- Card de Saldo Total (Aurora Glow + Sparkline) ---------- */
.nb-balance-card {
    position: relative;
    border-radius: 26px;
    padding: 24px 26px;
    background: linear-gradient(135deg, #0D162C 0%, #111A36 45%, #18193D 100%);
    border: 1px solid rgba(129, 140, 248, 0.22);
    box-shadow: 0 20px 48px -16px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.12);
    overflow: hidden;
    isolation: isolate;
}

.nb-balance-card::before {
    content: "";
    position: absolute;
    top: -50%;
    right: -20%;
    width: 320px;
    height: 320px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}

.nb-balance-card-inner {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.nb-balance-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}

.nb-balance-label-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.nb-balance-label {
    font-size: 0.95rem;
    font-weight: 500;
    color: #94A3B8;
}

.nb-eye-btn {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: grid;
    place-items: center;
    color: #94A3B8;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    cursor: pointer;
    transition: all 0.2s;
}
.nb-eye-btn:hover {
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.12);
}
.nb-eye-btn svg { width: 16px; height: 16px; }
.nb-eye-btn .ic-eye-off { display: none; }
body.balances-hidden .nb-eye-btn .ic-eye { display: none; }
body.balances-hidden .nb-eye-btn .ic-eye-off { display: block; }

.nb-currency-selector {
    display: flex;
    gap: 4px;
    background: rgba(0, 0, 0, 0.3);
    padding: 3px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.dash-curr-tag {
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 700;
    color: #94A3B8;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 0.04em;
}
.dash-curr-tag:hover {
    color: #F1F5F9;
}
.dash-curr-tag.active {
    background: linear-gradient(135deg, #38BDF8, #6366F1);
    color: #FFFFFF;
    box-shadow: 0 2px 8px rgba(56, 189, 248, 0.35);
}

.nb-balance-amount-box {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-height: 48px;
}

.dash-balance-num {
    font-size: 2.35rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
}

.dash-balance-curr {
    font-size: 1.35rem;
    font-weight: 700;
    color: #7DD3FC;
    letter-spacing: -0.01em;
}

.dash-balance-masked {
    display: none;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 4px;
    color: #94A3B8;
    line-height: 1.2;
}

body.balances-hidden .dash-balance-num,
body.balances-hidden .dash-balance-curr,
body.balances-hidden .nb-acc-val,
body.balances-hidden #nbWidgetAmount {
    display: none !important;
}

body.balances-hidden .dash-balance-masked {
    display: inline-block !important;
}

.nb-balance-bottom {
    display: flex;
    align-items: center;
    gap: 12px;
}

.nb-trend-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 99px;
    background: rgba(34, 197, 94, 0.14);
    border: 1px solid rgba(34, 197, 94, 0.28);
    color: #4ADE80;
    font-size: 0.82rem;
    font-weight: 700;
}
.nb-trend-pill svg {
    width: 13px;
    height: 13px;
}

/* Gráfico Sparkline de Fundo */
.nb-balance-chart-art {
    position: absolute;
    right: 18px;
    bottom: 12px;
    width: 180px;
    height: 80px;
    pointer-events: none;
    z-index: 1;
    opacity: 0.85;
}
.nb-sparkline {
    width: 100%;
    height: 100%;
    overflow: visible;
}

/* ---------- 4 Botões Rápidos (Ações em Tiles) ---------- */
.nb-action-tiles {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}

.nb-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 16px 8px;
    background: rgba(18, 26, 47, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
    box-shadow: 0 10px 24px -8px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}

.nb-tile:hover {
    transform: translateY(-3px);
    background: rgba(28, 38, 68, 0.8);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: 0 14px 28px -6px rgba(99, 102, 241, 0.25);
}

.nb-tile:active {
    transform: translateY(0);
}

.nb-tile-ic {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    position: relative;
    transition: all 0.2s;
}

.nb-tile-ic svg {
    width: 22px;
    height: 22px;
}

.nb-tile-ic.blue {
    background: rgba(56, 189, 248, 0.14);
    color: #38BDF8;
    border: 1px solid rgba(56, 189, 248, 0.28);
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.2);
}

.nb-tile-ic.gold {
    background: rgba(245, 158, 11, 0.14);
    color: #FBBF24;
    border: 1px solid rgba(245, 158, 11, 0.28);
    box-shadow: 0 0 16px rgba(245, 158, 11, 0.2);
}

.nb-tile-ic.green {
    background: rgba(34, 197, 94, 0.14);
    color: #4ADE80;
    border: 1px solid rgba(34, 197, 94, 0.28);
    box-shadow: 0 0 16px rgba(34, 197, 94, 0.2);
}

.nb-tile-ic.purple {
    background: rgba(168, 85, 247, 0.14);
    color: #C084FC;
    border: 1px solid rgba(168, 85, 247, 0.28);
    box-shadow: 0 0 16px rgba(168, 85, 247, 0.2);
}

.nb-tile-text {
    font-size: 0.82rem;
    font-weight: 600;
    color: #CBD5E1;
    white-space: nowrap;
}

/* ---------- Secções Gerais e Cabeçalhos de Bloco ---------- */
.nb-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.nb-section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.nb-section-head h3 {
    font-size: 1.05rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 0;
}

.nb-head-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #60A5FA;
    cursor: pointer;
    transition: color 0.2s;
    background: none;
    border: none;
    padding: 0;
}
.nb-head-link svg {
    width: 14px;
    height: 14px;
    transition: transform 0.2s;
}
.nb-head-link:hover {
    color: #93C5FD;
}
.nb-head-link:hover svg {
    transform: translateX(2px);
}

/* Lista: As suas contas */
.nb-accounts-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.nb-account-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    background: rgba(18, 26, 47, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
    box-shadow: 0 8px 20px -6px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}

.nb-account-card:hover {
    background: rgba(28, 38, 68, 0.8);
    border-color: rgba(99, 102, 241, 0.35);
    transform: translateX(3px);
}

.nb-acc-icon-wrap {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    flex-shrink: 0;
}
.nb-acc-icon-wrap svg { width: 22px; height: 22px; }

.nb-acc-icon-wrap.blue {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(99, 102, 241, 0.3));
    color: #38BDF8;
    border: 1px solid rgba(56, 189, 248, 0.3);
}

.nb-acc-icon-wrap.cyan {
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.2), rgba(56, 189, 248, 0.3));
    color: #2DD4BF;
    border: 1px solid rgba(45, 212, 191, 0.3);
}

.nb-acc-details {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
    min-width: 0;
}

.nb-acc-details strong {
    font-size: 0.95rem;
    font-weight: 700;
    color: #F8FAFC;
}

.nb-acc-val {
    font-size: 0.88rem;
    font-weight: 600;
    color: #94A3B8;
    font-variant-numeric: tabular-nums;
}

.nb-account-card .nb-chevron {
    width: 18px;
    height: 18px;
    color: #64748B;
    transition: transform 0.2s, color 0.2s;
}
.nb-account-card:hover .nb-chevron {
    transform: translateX(2px);
    color: #CBD5E1;
}

/* Banner: O seu futuro financeiro */
.nb-future-banner {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 20px 22px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(30, 41, 75, 0.85) 0%, rgba(20, 24, 52, 0.95) 100%);
    border: 1px solid rgba(129, 140, 248, 0.3);
    box-shadow: 0 16px 36px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.12);
    position: relative;
    overflow: hidden;
}

@media (min-width: 640px) {
    .nb-future-banner {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
    }
}

.nb-future-banner::before {
    content: "";
    position: absolute;
    right: -20px;
    bottom: -20px;
    width: 160px;
    height: 160px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.2) 0%, transparent 70%);
    pointer-events: none;
}

.nb-banner-content {
    display: flex;
    align-items: center;
    gap: 14px;
    z-index: 1;
}

.nb-banner-orb {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    background: linear-gradient(135deg, #38BDF8, #818CF8);
    display: grid;
    place-items: center;
    color: #FFFFFF;
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
    flex-shrink: 0;
}
.nb-banner-orb svg { width: 22px; height: 22px; }

.nb-banner-texts h4 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #FFFFFF;
}

.nb-banner-texts p {
    margin: 3px 0 0;
    font-size: 0.84rem;
    color: #94A3B8;
}

.nb-banner-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 14px;
    background: linear-gradient(135deg, #38BDF8, #6366F1);
    color: #FFFFFF;
    font-size: 0.86rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.4);
    transition: all 0.2s;
    white-space: nowrap;
    z-index: 1;
}
.nb-banner-action-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.55);
}
.nb-banner-action-btn svg { width: 14px; height: 14px; }

/* Acordeão de Carteiras Detalhadas */
.wallets-accordion {
    margin-top: 10px;
}

.wallets-details {
    background: rgba(18, 26, 47, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    overflow: hidden;
    transition: all 0.2s;
}

.wallets-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 700;
    color: #E2E8F0;
    user-select: none;
    list-style: none;
}
.wallets-summary::-webkit-details-marker { display: none; }

.summary-title {
    display: flex;
    align-items: center;
    gap: 10px;
}
.summary-ic {
    width: 20px;
    height: 20px;
    color: #38BDF8;
}

.summary-arrow {
    width: 18px;
    height: 18px;
    color: #94A3B8;
    transition: transform 0.2s;
}
.wallets-details[open] .summary-arrow {
    transform: rotate(180deg);
}

.wallets-cards-row {
    padding: 16px 20px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* ---------- Widgets Laterais (Coluna Direita NovaBank) ---------- */
.nb-dash-side-widgets {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.nb-widget-card {
    background: rgba(18, 26, 47, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 16px 36px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.nb-widget-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.nb-widget-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #F8FAFC;
}

.nb-widget-label {
    font-size: 0.85rem;
    font-weight: 500;
    color: #94A3B8;
}

.nb-widget-amount {
    font-size: 1.7rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    margin: 2px 0 4px;
}

.nb-badge-time {
    font-size: 0.76rem;
    font-weight: 600;
    color: #94A3B8;
    background: rgba(255, 255, 255, 0.06);
    padding: 4px 10px;
    border-radius: 99px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

/* Gráfico de Área Detalhado */
.nb-chart-wrapper {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.nb-full-chart {
    width: 100%;
    height: 110px;
    overflow: visible;
}

.nb-chart-dates {
    display: flex;
    justify-content: space-between;
    font-size: 0.74rem;
    color: #64748B;
    font-weight: 600;
    padding: 0 4px;
}

/* Mockup de Cartão NovaBank Visa */
.nb-card-visual {
    height: 160px;
    border-radius: 20px;
    padding: 20px;
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 50%, #7C3AED 100%);
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 16px 36px -10px rgba(37, 99, 235, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.3);
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.nb-card-visual::before {
    content: "";
    position: absolute;
    top: -40%;
    right: -20%;
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 70%);
    pointer-events: none;
}

.nb-card-brand-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.nb-card-brand {
    font-size: 1.15rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.02em;
}

.nb-card-contactless {
    width: 22px;
    height: 22px;
    color: rgba(255, 255, 255, 0.85);
}

.nb-card-number {
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 3px;
    color: #FFFFFF;
    font-family: var(--mono);
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.nb-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}

.nb-card-type {
    font-size: 0.78rem;
    color: rgba(255, 255, 255, 0.85);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.nb-card-network {
    font-size: 1.2rem;
    font-weight: 900;
    font-style: italic;
    color: #FFFFFF;
    letter-spacing: 0.05em;
}

.nb-card-actions {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 4px;
}

.nb-card-act {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 10px 4px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #94A3B8;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}
.nb-card-act svg { width: 18px; height: 18px; color: #CBD5E1; }
.nb-card-act:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #FFFFFF;
    border-color: rgba(99, 102, 241, 0.3);
}

/* Gráfico Donut de Despesas */
.nb-expenses-row {
    display: flex;
    align-items: center;
    gap: 20px;
}

.nb-donut-wrap {
    position: relative;
    width: 104px;
    height: 104px;
    flex-shrink: 0;
}

.nb-donut-chart {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
}

.nb-donut-center {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    pointer-events: none;
}

.nb-donut-center strong {
    font-size: 0.88rem;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.1;
}

.nb-donut-center span {
    font-size: 0.65rem;
    color: #94A3B8;
    font-weight: 600;
    text-transform: uppercase;
}

.nb-expense-legend {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
}

.nb-leg-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.82rem;
    color: #CBD5E1;
}

.nb-leg-item .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}
.nb-leg-item .dot.pink { background: #EC4899; box-shadow: 0 0 6px #EC4899; }
.nb-leg-item .dot.blue { background: #3B82F6; box-shadow: 0 0 6px #3B82F6; }
.nb-leg-item .dot.green { background: #10B981; box-shadow: 0 0 6px #10B981; }
.nb-leg-item .dot.amber { background: #F59E0B; box-shadow: 0 0 6px #F59E0B; }

.nb-leg-item strong {
    font-weight: 700;
    color: #F8FAFC;
    margin-left: auto;
}
"""

with open("frontend/style.css", "a", encoding="utf-8") as f:
    f.write("\n" + css_rules)

print("NovaBank CSS appended successfully!")
