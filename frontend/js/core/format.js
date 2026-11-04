/**
 * Formatação e leitura de valores monetários
 * parseCleanNumber, formatNumberWithDots, formatMoney, formatTwoTierMoney, groupDigits.
 */

// Converte texto digitado pelo utilizador num número.
// Aceita: "25000", "25.000", "25 000", "25.000,50", "1,5", "25000 KZ"
function parseCleanNumber(value) {
    if (typeof value === "number") return isFinite(value) ? value : 0;
    let s = String(value == null ? "" : value).toLowerCase()
        .replace(/kz|kwanzas?|aoa/g, "")
        .replace(/[\s\u00a0]/g, "")
        .replace(/[^0-9.,-]/g, "");
    if (!s) return 0;

    const lastDot = s.lastIndexOf(".");
    const lastComma = s.lastIndexOf(",");

    if (lastDot !== -1 && lastComma !== -1) {
        // O último separador é o decimal; o outro é de milhares
        const decSep = lastDot > lastComma ? "." : ",";
        const thouSep = decSep === "." ? "," : ".";
        s = s.split(thouSep).join("").replace(decSep, ".");
    } else if (lastComma !== -1) {
        // Em pt-AO a vírgula é decimal (várias vírgulas = milhares)
        s = (s.match(/,/g).length > 1) ? s.replace(/,/g, "") : s.replace(",", ".");
    } else if (lastDot !== -1) {
        // "25.000" / "1.250.000" = milhares; "12.5" = decimal
        if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
    }
    const n = parseFloat(s);
    return isFinite(n) ? n : 0;
}
// Número com pontos de milhares e vírgula decimal (pt-AO): 1250000 -> "1.250.000", 25.5 -> "25,5"
function formatNumberWithDots(value) {
    const n = Number(value);
    if (!isFinite(n)) return "0";
    const [int, dec] = Math.abs(n).toFixed(2).split(".");
    const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const decimals = dec.replace(/0+$/, "");
    return (n < 0 ? "-" : "") + grouped + (decimals ? "," + decimals : "");
}

// Campos com class="js-money": separador de milhares enquanto se escreve (25000 -> 25.000).
// Corre na fase de captura para que os oninput do próprio campo já leiam o valor formatado.
document.addEventListener("input", function (e) {
    const el = e.target;
    if (!el || !el.classList || !el.classList.contains("js-money")) return;
    const raw = el.value;
    const caret = el.selectionStart == null ? raw.length : el.selectionStart;
    const digitsBeforeCaret = raw.slice(0, caret).replace(/[^0-9,]/g, "").length;

    let clean = raw.replace(/[^0-9,]/g, "");
    const comma = clean.indexOf(",");
    let intPart = comma === -1 ? clean : clean.slice(0, comma);
    let decPart = comma === -1 ? null : clean.slice(comma + 1).replace(/,/g, "").slice(0, 2);
    intPart = intPart.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const formatted = intPart + (decPart === null ? "" : "," + decPart);
    if (formatted === raw) return;
    el.value = formatted;

    // repõe o cursor depois do mesmo número de dígitos
    let pos = 0, seen = 0;
    while (pos < formatted.length && seen < digitsBeforeCaret) {
        if (/[0-9,]/.test(formatted[pos])) seen++;
        pos++;
    }
    try { el.setSelectionRange(pos, pos); } catch (_) { /* tipos sem seleção */ }
}, true);

// Formatação Monetária
function groupDigits(value) {
    const compact = String(value || "").replace(/\s+/g, "");
    return compact.replace(/(.{4})/g, "$1 ").trim();
}
function formatMoney(amount, currency = "AOA") {
    const formatted = typeof bkFormatNumber === "function" ? bkFormatNumber(amount, 2) : new Intl.NumberFormat("pt-AO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(amount) || 0);

    const cur = (currency || "AOA").toUpperCase();
    if (cur === "AOA" || cur === "KZ") return `${formatted} KZ`;
    if (cur === "EUR") return `${formatted} €`;
    if (cur === "USD") return `${formatted} $`;
    return `${formatted} ${cur}`;
}
function formatTwoTierMoney(amount, currency = "USD") {
    const cur = (currency || "USD").toUpperCase();
    const formatted = typeof bkFormatNumber === "function" ? bkFormatNumber(amount, 2) : new Intl.NumberFormat("pt-AO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(amount) || 0);

    if (cur === "USD") return `${formatted} $`;
    if (cur === "AOA" || cur === "KZ") return `${formatted} KZ`;
    if (cur === "EUR") return `${formatted} €`;
    return `${formatted} ${cur}`;
}
