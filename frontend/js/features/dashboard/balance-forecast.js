/**
 * Previsao do Saldo - Grafico de linhas historico + projetado
 *
 * Busca dados de /api/accounts/analytics e constroi um grafico SVG interativo:
 *  - Linha solida  = valores historicos (ultimos 30 dias)
 *  - Linha tracejada = valores projetados (proximos 30-90 dias)
 *  - Zona de alerta = dias em que o saldo podera ficar baixo
 *  - Tooltip interativo ao passar o cursor
 *  - Badge "Estimativa" claramente visivel
 */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Estado interno
    // -----------------------------------------------------------------------
    let _forecastData = null;
    let _chartW = 0, _chartH = 0;
    let _allPoints = [];
    let _histLen = 0;

    // -----------------------------------------------------------------------
    // API
    // -----------------------------------------------------------------------
    async function loadForecastData(projDays) {
        if (!state.token) return;
        const days = projDays || 90;
        try {
            const r = await fetch(
                `${API_BASE}/api/accounts/analytics?range_days=30&projection_days=${days}`,
                { headers: { Authorization: `Bearer ${state.token}` } }
            );
            if (!r.ok) return;
            const data = await r.json();
            _forecastData = _transform(data);
            renderForecastChart();
        } catch (e) {
            console.warn('[ForecastChart]', e);
        }
    }

    function _transform(data) {
        const hist = (data.balance_series || []).map(function(p) {
            return { date: p.date, balance: p.balance, projected: false };
        });
        const proj = (((data.projection || {}).points) || []).map(function(p) {
            return { date: p.date, balance: p.balance, projected: true };
        });
        return {
            historical: hist,
            projected: proj,
            alerts: ((data.projection || {}).low_balance_alerts || []),
            assumptions: ((data.projection || {}).assumptions || {}),
            currency: data.currency || 'AOA',
            isEstimate: true
        };
    }

    // -----------------------------------------------------------------------
    // Renderizacao
    // -----------------------------------------------------------------------
    function renderForecastChart() {
        var wrap = document.getElementById('forecastChartWrap');
        if (!wrap) return;

        if (!_forecastData) {
            _showEmpty(wrap, 'A carregar previsao...');
            return;
        }

        var historical = _forecastData.historical;
        var projected  = _forecastData.projected;
        var alerts     = _forecastData.alerts;
        var assumptions= _forecastData.assumptions;
        var currency   = _forecastData.currency;
        var combined   = historical.concat(projected);

        if (combined.length < 2) {
            _showEmpty(wrap, 'Sem dados suficientes para gerar previsao. Faca movimentos para ativar a previsao.');
            return;
        }

        _allPoints = combined;
        _histLen   = historical.length;

        // ---- Dimensoes ----
        var rect = wrap.getBoundingClientRect();
        var wrapW = wrap.clientWidth || (rect ? rect.width : 0) || 340;
        _chartW = Math.max(wrapW, 280);
        _chartH = _chartW < 520 ? 300 : 330;
        var PAD = { t: 28, r: 18, b: 42, l: 14 };
        var W = _chartW - PAD.l - PAD.r;
        var H = _chartH - PAD.t - PAD.b;

        // ---- Escala ----
        var vals = combined.map(function(p) { return p.balance; });
        var minV = Math.min.apply(null, vals.concat([0]));
        var maxV = Math.max.apply(null, vals);
        var span = maxV - minV || 1;

        function xOf(i)  { return PAD.l + (i / (combined.length - 1)) * W; }
        function yOf(v)  { return PAD.t + H - ((v - minV) / span) * H; }

        var coords = combined.map(function(p, i) { return [xOf(i), yOf(p.balance)]; });
        var histCoords = coords.slice(0, _histLen);
        var projCoords = coords.slice(Math.max(0, _histLen - 1));

        // ---- Alert band ----
        var alertDates = {};
        alerts.forEach(function(a) { alertDates[a.date] = true; });
        var alertBands = '';
        if (alerts.length) {
            var firstAlertIdx = -1;
            for (var ai = 0; ai < combined.length; ai++) {
                if (alertDates[combined[ai].date]) { firstAlertIdx = ai; break; }
            }
            if (firstAlertIdx >= 0) {
                var ax1 = xOf(firstAlertIdx);
                var ax2 = PAD.l + W;
                alertBands = '<rect x="' + ax1.toFixed(1) + '" y="' + PAD.t + '" width="' + (ax2-ax1).toFixed(1) + '" height="' + H + '" fill="url(#alertBandGrad)" rx="3"/>';
            }
        }

        // ---- Paths ----
        function pathD(pts) {
            return pts.map(function(c, i) {
                return (i ? 'L' : 'M') + c[0].toFixed(1) + ',' + c[1].toFixed(1);
            }).join(' ');
        }
        var histPath = pathD(histCoords);
        var projPath = pathD(projCoords);
        var hc = histCoords;
        var hFill = hc.length >= 2
            ? histPath + ' L' + hc[hc.length-1][0].toFixed(1) + ',' + (PAD.t+H).toFixed(1) + ' L' + PAD.l.toFixed(1) + ',' + (PAD.t+H).toFixed(1) + ' Z'
            : '';

        // ---- Zero line ----
        var zeroY = yOf(0);
        var zeroLine = (zeroY >= PAD.t && zeroY <= PAD.t + H)
            ? '<line x1="' + PAD.l + '" y1="' + zeroY.toFixed(1) + '" x2="' + (PAD.l+W) + '" y2="' + zeroY.toFixed(1) + '" stroke="rgba(239,68,68,0.4)" stroke-width="1" stroke-dasharray="4 3"/>'
            : '';

        // ---- Y labels ----
        var yLabelsSVG = '';
        var yVals = _niceYLabels(minV, maxV, 4);
        yVals.forEach(function(v) {
            var ly = yOf(v).toFixed(1);
            yLabelsSVG += '<text x="' + (PAD.l + W + 2) + '" y="' + ly + '" dominant-baseline="middle" class="fc-axis-lbl">' + _shortMoney(v, currency) + '</text>';
            yLabelsSVG += '<line x1="' + PAD.l + '" y1="' + ly + '" x2="' + (PAD.l+W) + '" y2="' + ly + '" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>';
        });

        // ---- X labels ----
        var xLabelsSVG = '';
        var xIdxs = _spreadIndices(combined.length, 4);
        xIdxs.forEach(function(i) {
            var cx = coords[i][0];
            var cls = combined[i].projected ? 'fc-axis-lbl fc-proj-lbl' : 'fc-axis-lbl';
            xLabelsSVG += '<text x="' + cx.toFixed(1) + '" y="' + (PAD.t+H+13).toFixed(1) + '" text-anchor="middle" class="' + cls + '">' + _shortDate(combined[i].date) + '</text>';
        });

        // ---- Junction dot ----
        var junctionDot = '';
        if (_histLen > 0 && _histLen < combined.length) {
            var jx = coords[_histLen-1][0].toFixed(1);
            var jy = coords[_histLen-1][1].toFixed(1);
            junctionDot = '<circle cx="' + jx + '" cy="' + jy + '" r="4.5" fill="#38BDF8" stroke="#0F172A" stroke-width="2" class="fc-junction"/>';
        }

        // ---- Assumptions ----
        var incEst = _shortMoney(assumptions.monthly_income_estimate || 0, currency);
        var expEst = _shortMoney(assumptions.monthly_expense_estimate || 0, currency);
        var lookback = assumptions.lookback_days || 90;
        var noHistory = !historical.length;

        // ---- Build HTML ----
        var alertLegend = alerts.length ? '<span class="fc-leg-item"><span class="fc-leg-dot alert"></span>Saldo baixo</span>' : '';
        var assHTML = noHistory ? '' :
            '<div class="fc-assumptions">' +
            '<span class="fc-ass-item"><span class="fc-ass-arrow up"></span>Receita est.: <strong>' + incEst + '/mes</strong></span>' +
            '<span class="fc-ass-item"><span class="fc-ass-arrow down"></span>Despesa est.: <strong>' + expEst + '/mes</strong></span>' +
            '<span class="fc-ass-notice">Base: ultimos ' + lookback + ' dias &bull; Os valores futuros sao estimativas e podem nao refletir a realidade.</span>' +
            '</div>';

        wrap.innerHTML =
            '<div class="fc-head">' +
                '<div class="fc-head-left">' +
                    '<span class="fc-title">Previsao do Saldo</span>' +
                    '<span class="fc-estimate-badge">Estimativa</span>' +
                '</div>' +
                '<div class="fc-range-btns" role="group" aria-label="Horizonte da previsao">' +
                    '<button type="button" class="fc-range-btn active" data-days="30">30d</button>' +
                    '<button type="button" class="fc-range-btn" data-days="60">60d</button>' +
                    '<button type="button" class="fc-range-btn" data-days="90">90d</button>' +
                '</div>' +
            '</div>' +
            '<div class="fc-chart-area" id="fcChartArea">' +
                '<svg id="fcSvg" viewBox="0 0 ' + _chartW + ' ' + _chartH + '" width="100%" height="' + _chartH + '" aria-label="Grafico de previsao do saldo" role="img">' +
                    '<defs>' +
                        '<linearGradient id="histFillGrad" x1="0" y1="0" x2="0" y2="1">' +
                            '<stop offset="0%" stop-color="#38BDF8" stop-opacity="0.20"/>' +
                            '<stop offset="100%" stop-color="#38BDF8" stop-opacity="0.01"/>' +
                        '</linearGradient>' +
                        '<linearGradient id="histLineGradF" x1="0" y1="0" x2="1" y2="0">' +
                            '<stop offset="0%" stop-color="#38BDF8"/>' +
                            '<stop offset="100%" stop-color="#818CF8"/>' +
                        '</linearGradient>' +
                        '<linearGradient id="alertBandGrad" x1="0" y1="0" x2="0" y2="1">' +
                            '<stop offset="0%" stop-color="rgba(239,68,68,0.10)"/>' +
                            '<stop offset="100%" stop-color="rgba(239,68,68,0.02)"/>' +
                        '</linearGradient>' +
                        '<filter id="fcGlow"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
                    '</defs>' +
                    alertBands +
                    zeroLine +
                    yLabelsSVG +
                    (hFill ? '<path d="' + hFill + '" fill="url(#histFillGrad)"/>' : '') +
                    (histPath ? '<path d="' + histPath + '" fill="none" stroke="url(#histLineGradF)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>' : '') +
                    (projPath ? '<path d="' + projPath + '" fill="none" stroke="#818CF8" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="6 4" opacity="0.85"/>' : '') +
                    junctionDot +
                    '<line id="fcCrosshair" x1="0" y1="' + PAD.t + '" x2="0" y2="' + (PAD.t+H) + '" stroke="rgba(255,255,255,0.22)" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>' +
                    '<circle id="fcHoverDot" cx="0" cy="0" r="5" fill="#818CF8" stroke="#0F172A" stroke-width="2" filter="url(#fcGlow)" opacity="0"/>' +
                    xLabelsSVG +
                    '<rect id="fcOverlay" x="' + PAD.l + '" y="' + PAD.t + '" width="' + W + '" height="' + H + '" fill="transparent" style="cursor:crosshair"/>' +
                '</svg>' +
                '<div class="fc-tooltip" id="fcTooltip" role="tooltip" aria-hidden="true"></div>' +
            '</div>' +
            '<div class="fc-legend">' +
                '<span class="fc-leg-item"><span class="fc-leg-line hist"></span>Historico</span>' +
                '<span class="fc-leg-item"><span class="fc-leg-line proj"></span>Projecao</span>' +
                alertLegend +
            '</div>' +
            assHTML;

        _bindEvents(wrap, combined, coords, PAD, W, H, currency);
    }

    function _bindEvents(wrap, combined, coords, PAD, W, H, currency) {
        var overlay   = document.getElementById('fcOverlay');
        var crosshair = document.getElementById('fcCrosshair');
        var hoverDot  = document.getElementById('fcHoverDot');
        var tooltip   = document.getElementById('fcTooltip');
        var svg       = document.getElementById('fcSvg');
        var area      = document.getElementById('fcChartArea');
        if (!overlay || !svg) return;

        function getIdx(clientX) {
            var svgRect = svg.getBoundingClientRect();
            var svgW    = svgRect.width;
            var scale   = _chartW / svgW;
            var svgX    = (clientX - svgRect.left) * scale;
            var best = 0, bestDist = Infinity;
            coords.forEach(function(c, i) {
                var d = Math.abs(c[0] - svgX);
                if (d < bestDist) { bestDist = d; best = i; }
            });
            return best;
        }

        function showTip(idx, clientX, clientY) {
            if (idx < 0 || idx >= combined.length) return;
            var p  = combined[idx];
            var cx = coords[idx][0];
            var cy = coords[idx][1];
            var isProj = p.projected;

            crosshair.setAttribute('x1', cx.toFixed(1));
            crosshair.setAttribute('x2', cx.toFixed(1));
            crosshair.setAttribute('opacity', '1');
            hoverDot.setAttribute('cx', cx.toFixed(1));
            hoverDot.setAttribute('cy', cy.toFixed(1));
            hoverDot.setAttribute('fill', isProj ? '#818CF8' : '#38BDF8');
            hoverDot.setAttribute('opacity', '1');

            tooltip.innerHTML =
                '<div class="fc-tip-date">' + _longDate(p.date) +
                '<span class="fc-tip-badge' + (isProj ? ' proj' : '') + '">' + (isProj ? 'Estimativa' : 'Real') + '</span></div>' +
                '<div class="fc-tip-bal">' + _fmtBalance(p.balance, currency) + '</div>';

            tooltip.setAttribute('aria-hidden', 'false');
            var areaRect = area.getBoundingClientRect();
            var svgRect  = svg.getBoundingClientRect();
            var scaledCx = (cx / _chartW) * svgRect.width;
            var tx = svgRect.left - areaRect.left + scaledCx + 14;
            var ty = clientY - areaRect.top - 24;
            if (tx + 160 > areaRect.width) tx = svgRect.left - areaRect.left + scaledCx - 162;
            tooltip.style.left = Math.max(0, tx) + 'px';
            tooltip.style.top  = Math.max(0, ty) + 'px';
            tooltip.classList.add('visible');
        }

        function hideTip() {
            crosshair.setAttribute('opacity', '0');
            hoverDot.setAttribute('opacity', '0');
            tooltip.classList.remove('visible');
            tooltip.setAttribute('aria-hidden', 'true');
        }
        window.clearWidgetHoverDetails = hideTip;

        var touchStartY = null;
        var touchCancelled = false;

        overlay.addEventListener('mousemove', function(e) { showTip(getIdx(e.clientX), e.clientX, e.clientY); });
        overlay.addEventListener('mouseleave', hideTip);

        overlay.addEventListener('touchstart', function(e) {
            touchCancelled = false;
            if (e.touches && e.touches.length) {
                touchStartY = e.touches[0].clientY;
            }
        }, { passive: true });

        overlay.addEventListener('touchmove', function(e) {
            if (!e.touches.length) return;
            if (touchCancelled) return;
            var cy = e.touches[0].clientY;
            if (touchStartY != null) {
                var deltaUp = touchStartY - cy;
                if (deltaUp > 14 || Math.abs(cy - touchStartY) > 22) {
                    touchCancelled = true;
                    hideTip();
                    document.documentElement.classList.remove('chart-touch-locked');
                    document.body.classList.remove('chart-touch-locked');
                    return;
                }
            }
            showTip(getIdx(e.touches[0].clientX), e.touches[0].clientX, e.touches[0].clientY);
            if (e.cancelable) e.preventDefault();
        }, { passive: false });

        overlay.addEventListener('touchend', function() {
            touchStartY = null;
            hideTip();
        });
        overlay.addEventListener('touchcancel', function() {
            touchStartY = null;
            hideTip();
        });

        wrap.querySelectorAll('.fc-range-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                wrap.querySelectorAll('.fc-range-btn').forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
                loadForecastData(parseInt(btn.dataset.days, 10));
            });
        });
    }

    // -----------------------------------------------------------------------
    // Utilitarios
    // -----------------------------------------------------------------------
    function _showEmpty(wrap, msg) {
        wrap.innerHTML =
            '<div class="fc-head"><span class="fc-title">Previsao do Saldo</span><span class="fc-estimate-badge">Estimativa</span></div>' +
            '<div class="fc-empty">' + msg + '</div>';
    }

    function _niceYLabels(minV, maxV, count) {
        var range = maxV - minV || 1;
        var step  = range / (count - 1);
        var arr = [];
        for (var i = 0; i < count; i++) arr.push(minV + i * step);
        return arr;
    }

    function _spreadIndices(total, n) {
        if (total <= n) { var a = []; for (var i = 0; i < total; i++) a.push(i); return a; }
        var a = [];
        for (var i = 0; i < n; i++) a.push(Math.round(i * (total - 1) / (n - 1)));
        return a;
    }

    function _shortMoney(v, curr) {
        var abs = Math.abs(v);
        var sign = v < 0 ? '-' : '';
        var s;
        if (abs >= 1000000) s = (abs / 1000000).toFixed(1) + 'M';
        else if (abs >= 1000) s = (abs / 1000).toFixed(0) + 'k';
        else s = abs.toFixed(0);
        if (curr === 'AOA') return sign + s + ' Kz';
        if (curr === 'USD') return sign + '$' + s;
        if (curr === 'EUR') return sign + '\u20ac' + s;
        return sign + s;
    }

    function _fmtBalance(v, curr) {
        var f = function(n) { return n.toLocaleString('pt-AO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
        if (curr === 'AOA') return f(v) + ' Kz';
        if (curr === 'USD') return '$' + f(v);
        if (curr === 'EUR') return '\u20ac' + f(v);
        return f(v) + ' ' + curr;
    }

    function _shortDate(iso) {
        if (!iso) return '';
        var parts = iso.split('-');
        var months = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
        return parseInt(parts[2]) + ' ' + months[parseInt(parts[1]) - 1];
    }

    function _longDate(iso) {
        if (!iso) return '';
        var d = new Date(iso + 'T12:00:00');
        return d.toLocaleDateString('pt-AO', { day: '2-digit', month: 'short', year: 'numeric' });
    }

    // Exportar
    window.loadForecastData    = loadForecastData;
    window.renderForecastChart = renderForecastChart;

}());
