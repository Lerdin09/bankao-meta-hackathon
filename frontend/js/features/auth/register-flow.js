/**
 * Fluxo de registo — 7 páginas em 3 etapas
 * 1-3 Dados pessoais · 4 Documentos · 5-7 Segurança e confirmação.
 * No fim: POST /api/auth/register → (opcional) KYC com os documentos → app com a conta ativa.
 */
const rf = { p: 1, d: {}, files: {}, busy: false };
const RF_STEPS = { 1: [1, 'Dados pessoais e contactos'], 2: [1, 'Dados pessoais e contactos'], 3: [1, 'Dados pessoais e contactos'], 4: [2, 'Documentos e verificação'], 5: [3, 'Segurança e confirmação'], 6: [3, 'Segurança e confirmação'], 7: [3, 'Segurança e confirmação'] };
const RF_FIN = ['Poupança', 'Pagamentos', 'Salário', 'Transferências', 'Negócios', 'Outro'];
const RF_TERMS = `<h4>1. Objeto</h4>Os presentes Termos regulam a abertura e utilização da conta digital BankAO, serviço de pagamentos e poupança acessível por aplicação móvel e web. Ao criar conta, o Cliente declara ter lido e aceitado integralmente estas condições.
<h4>2. Elegibilidade</h4>Pode abrir conta qualquer pessoa singular com 18 anos completos, residente ou com ligação a Angola, titular de Bilhete de Identidade ou passaporte válido. O BankAO pode recusar ou cancelar aberturas nos termos da lei.
<h4>3. Verificação de identidade (KYC)</h4>O Cliente obriga-se a fornecer dados verdadeiros, completos e atualizados, bem como documentos legíveis e válidos. A conta fica sujeita a verificação e pode ter limites até à sua conclusão, em cumprimento da legislação de prevenção do branqueamento de capitais e financiamento do terrorismo.
<h4>4. Credenciais e segurança</h4>A palavra-passe e o PIN são pessoais e intransmissíveis. O BankAO nunca solicita estas credenciais por telefone, e-mail ou mensagem. O Cliente deve comunicar de imediato perda, roubo ou suspeita de utilização indevida.
<h4>5. Serviços</h4>A conta permite depósitos, transferências, pagamentos de serviços e referências, metas de poupança e consulta de movimentos. Os limites diários e mensais constam das Definições e podem ser alterados mediante aviso prévio.
<h4>6. Comissões</h4>A abertura e manutenção de conta básica são gratuitas. Operações específicas podem estar sujeitas a comissão, sempre apresentada antes da confirmação. Aplicam-se os impostos legais em vigor.
<h4>7. Responsabilidade</h4>O BankAO não responde por falhas de rede, indisponibilidade de terceiros ou operações autorizadas com as credenciais do Cliente. Responde pelos danos decorrentes de falha comprovada dos seus sistemas, nos limites da lei.
<h4>8. Suspensão e encerramento</h4>A conta pode ser suspensa em caso de suspeita de fraude, dados falsos ou incumprimento. O Cliente pode encerrá-la a qualquer momento, após liquidação de eventuais responsabilidades.
<h4>9. Alterações</h4>Estas condições podem ser alteradas com aviso de 30 dias. A continuação de utilização implica aceitação.
<h4>10. Lei aplicável</h4>Aplica-se a lei angolana, sendo competente o foro da comarca de Luanda.`;
const RF_PRIV = `<h4>1. Responsável pelo tratamento</h4>O BankAO é responsável pelo tratamento dos seus dados pessoais, em conformidade com a Lei n.º 22/11 de Proteção de Dados Pessoais de Angola.
<h4>2. Dados recolhidos</h4>Identificação (nome, data de nascimento, nacionalidade), contactos (telefone, e-mail, morada), dados profissionais e de rendimento, cópia do documento de identificação e dados de utilização da conta e do dispositivo.
<h4>3. Finalidades</h4>Abertura e gestão da conta, cumprimento de obrigações legais (identificação, prevenção de fraude e branqueamento), segurança, apoio ao cliente e melhoria dos serviços.
<h4>4. Partilha</h4>Os dados só são partilhados com autoridades competentes quando legalmente exigido e com prestadores que atuam em nosso nome sob contrato de confidencialidade. Nunca vendemos os seus dados.
<h4>5. Conservação</h4>Os dados são conservados durante a relação contratual e pelo prazo legal posterior aplicável.
<h4>6. Os seus direitos</h4>Pode aceder, retificar, opor-se ou solicitar o apagamento dos seus dados, nos termos da lei, através das Definições ou do apoio ao cliente.
<h4>7. Segurança</h4>Utilizamos encriptação em trânsito, PIN de autorização e controlos de acesso rigorosos.
<h4>8. Armazenamento local</h4>Usamos armazenamento local estritamente necessário ao funcionamento e segurança da aplicação.`;

const $rf = id => document.getElementById(id);
const rfEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function openRegisterFlow() {
    rf.p = 1; rf.d = { nac: 'Angolana' }; rf.files = {};
    $rf('regFlow').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    rfRender();
}
function closeRegisterFlow() {
    $rf('regFlow').style.display = 'none';
    document.body.style.overflow = '';
    rf.d = {}; rf.files = {};   // não guardar palavras-passe / PIN / documentos em memória
}
function rfField(id, label, type = 'text', ph = '', extra = '') {
    return `<label class="rf-l" for="rf_${id}">${label}</label><input id="rf_${id}" type="${type}" placeholder="${ph}" value="${rfEsc(rf.d[id])}" ${extra}><div class="rf-msg" id="rfm_${id}"></div>`;
}
function rfNav(back = true, txt = 'Continuar') {
    return `<div class="rf-btns">${back ? '<button type="button" class="btn btn-ghost" onclick="rfBack()">Voltar</button>' : ''}<button type="button" class="btn btn-primary" id="rfNext" onclick="rfNext()">${txt}</button></div>`;
}
function rfRender() {
    const p = rf.p, [st, name] = RF_STEPS[p];
    ['rfS1', 'rfS2', 'rfS3'].forEach((id, i) => $rf(id).className = i + 1 < st ? 'done' : i + 1 === st ? 'half' : '');
    $rf('rfName').textContent = name;
    $rf('rfNum').textContent = `Passo ${st} de 3 · Página ${p}/7`;
    const d = rf.d; let h = '';
    const maxBirth = new Date(Date.now() - 18 * 365.25 * 864e5).toISOString().slice(0, 10);
    if (p === 1) h = `<h2>Vamos começar</h2><p class="rf-sub">Diga-nos quem é e como o podemos contactar.</p>
        ${rfField('nome', 'Nome completo', 'text', 'Como no seu BI', 'autocomplete="name"')}
        ${rfField('nasc', 'Data de nascimento', 'date', '', `max="${maxBirth}"`)}
        <label class="rf-l" for="rf_tel">Número de telefone</label><div class="rf-phone"><span>🇦🇴 +244</span><input id="rf_tel" type="tel" inputmode="numeric" maxlength="9" placeholder="9XX XXX XXX" value="${rfEsc(d.tel)}" autocomplete="tel-national"></div><div class="rf-msg" id="rfm_tel"></div>
        ${rfField('email', 'E-mail', 'email', 'o.seu@email.com', 'autocomplete="email"')}${rfNav(false)}`;
    if (p === 2) h = `<h2>Sobre si</h2><p class="rf-sub">Nacionalidade, onde vive e o que faz.</p>
        <label class="rf-l" for="rf_nac">Nacionalidade</label><select id="rf_nac">${['Angolana', 'Portuguesa', 'Brasileira', 'Cabo-verdiana', 'Moçambicana', 'Outra'].map(n => `<option ${d.nac === n ? 'selected' : ''}>${n}</option>`).join('')}</select>
        ${rfField('end', 'Endereço de residência', 'text', 'Rua, bairro, município, província', 'autocomplete="street-address"')}
        ${rfField('prof', 'Profissão', 'text', 'Ex.: Engenheiro, Estudante, Comerciante')}${rfNav()}`;
    if (p === 3) h = `<h2>Perfil financeiro</h2><p class="rf-sub">Ajuda-nos a adaptar a conta e a cumprir a lei.</p>
        <label class="rf-l" for="rf_renda">Rendimento mensal aproximado</label><select id="rf_renda"><option value="">Selecione…</option>${['Até 150.000 Kz', '150.000 – 400.000 Kz', '400.000 – 1.000.000 Kz', '1.000.000 – 3.000.000 Kz', 'Mais de 3.000.000 Kz'].map(n => `<option ${d.renda === n ? 'selected' : ''}>${n}</option>`).join('')}</select><div class="rf-msg" id="rfm_renda"></div>
        <label class="rf-l">Finalidade da conta</label><div class="rf-chips">${RF_FIN.map(f => `<div class="rf-chip ${d.fin === f ? 'on' : ''}" onclick="rf.d.fin='${f}';rfRender()">${f}</div>`).join('')}</div><div class="rf-msg" id="rfm_fin"></div>${rfNav()}`;
    if (p === 4) {
        const sides = d.doc === 'bilhete' ? ['Frente do BI', 'Verso do BI'] : d.doc === 'passaporte' ? ['Página de identificação', 'Página da assinatura'] : [];
        h = `<h2>Documento de identificação</h2><p class="rf-sub">Escolha o documento e carregue fotografias nítidas.</p>
        <div class="rf-doc"><div class="rf-dt ${d.doc === 'bilhete' ? 'on' : ''}" onclick="rfDoc('bilhete')"><div>🪪</div><b>Bilhete de Identidade</b><small>Frente e verso</small></div><div class="rf-dt ${d.doc === 'passaporte' ? 'on' : ''}" onclick="rfDoc('passaporte')"><div>📘</div><b>Passaporte</b><small>Páginas principais</small></div></div><div class="rf-msg" id="rfm_doc"></div>
        ${sides.map((s, i) => `<label class="rf-l">${s}</label><label class="rf-up ${rf.files[i] ? 'ok' : ''}">${rf.files[i] ? `<img src="${rf.files[i]}" alt=""><em>✓ Carregado</em>` : '<div>📷<br>Toque para carregar<br><small>JPG ou PNG · máx. 5 MB</small></div>'}<input type="file" accept="image/*" onchange="rfUpload(this,${i})"></label>`).join('')}
        <div class="rf-msg" id="rfm_files"></div><div class="rf-hint">🔒 Os documentos são usados apenas para verificar a sua identidade.</div>${rfNav()}`;
    }
    if (p === 5) h = `<h2>Crie a sua palavra-passe</h2><p class="rf-sub">Será usada para iniciar sessão.</p>
        <label class="rf-l" for="rf_pw">Palavra-passe</label><div class="rf-pw"><input id="rf_pw" type="password" autocomplete="new-password" oninput="rfStrength()" placeholder="Mínimo 8 caracteres" value="${rfEsc(d.pw)}"><button type="button" onclick="rfToggle('rf_pw',this)">Mostrar</button></div>
        <div class="rf-meter"><i id="rfMeter"></i></div><ul class="rf-rules" id="rfRules"><li>8+ caracteres</li><li>Letra maiúscula</li><li>Letra minúscula</li><li>Número</li></ul>
        <label class="rf-l" for="rf_pw2">Confirmar palavra-passe</label><div class="rf-pw"><input id="rf_pw2" type="password" autocomplete="new-password" placeholder="Repita a palavra-passe"><button type="button" onclick="rfToggle('rf_pw2',this)">Mostrar</button></div><div class="rf-msg" id="rfm_pw"></div>${rfNav()}`;
    if (p === 6) { const box = g => `<div class="rf-pin" id="${g}">${[0, 1, 2, 3].map(() => '<input type="password" inputmode="numeric" maxlength="1" autocomplete="off">').join('')}</div>`;
        h = `<h2>Crie o seu PIN</h2><p class="rf-sub">4 dígitos para autorizar transferências e pagamentos.</p><label class="rf-l" style="text-align:center">PIN de segurança</label>${box('rfPin1')}<label class="rf-l" style="text-align:center">Confirmar PIN</label>${box('rfPin2')}<div class="rf-msg" id="rfm_pin" style="text-align:center"></div><div class="rf-hint" style="text-align:center">Evite sequências como 1234 ou datas de nascimento.</div>${rfNav()}`; }
    if (p === 7) h = `<h2>Termos e privacidade</h2><p class="rf-sub">Leia com atenção antes de concluir.</p>
        <div class="rf-tabs"><button type="button" class="on" id="rfT1" onclick="rfTab(1)">Termos e Condições</button><button type="button" id="rfT2" onclick="rfTab(2)">Privacidade</button></div><div class="rf-legal" id="rfLegal">${RF_TERMS}</div>
        <label class="rf-ck"><input type="checkbox" id="rfC1" ${d.ok1 ? 'checked' : ''}>Li e aceito os Termos e Condições do BankAO.</label>
        <label class="rf-ck"><input type="checkbox" id="rfC2" ${d.ok2 ? 'checked' : ''}>Li e aceito a Política de Privacidade e o tratamento dos meus dados.</label>
        <label class="rf-ck"><input type="checkbox" id="rfC3">Confirmo que o telefone <b>&nbsp;+244 ${rfEsc(d.tel)}&nbsp;</b> e o e-mail <b>&nbsp;${rfEsc(d.email)}&nbsp;</b> são meus e estão corretos.</label>
        <div class="rf-msg" id="rfm_ck"></div>${rfNav(true, 'Criar conta')}`;
    $rf('rfStage').innerHTML = `<div class="rf-card">${h}</div>`;
    if (p === 5) rfStrength();
    if (p === 6) rfPins();
    $rf('regFlow').scrollTop = 0;
}
function rfErr(id, t) { const m = $rf('rfm_' + id); if (m) m.textContent = t; const e = $rf('rf_' + id); if (e) e.classList.toggle('rf-bad', !!t); return !t; }
function rfVal() {
    const v = id => $rf('rf_' + id).value.trim(), d = rf.d, p = rf.p; let ok = true;
    if (p === 1) {
        d.nome = v('nome'); d.nasc = v('nasc'); d.tel = v('tel').replace(/\s/g, ''); d.email = v('email');
        const maxBirth = new Date(Date.now() - 18 * 365.25 * 864e5);
        ok &= rfErr('nome', d.nome.split(/\s+/).length < 2 ? 'Introduza o nome completo.' : '');
        ok &= rfErr('nasc', !d.nasc ? 'Indique a data de nascimento.' : new Date(d.nasc) > maxBirth ? 'Tem de ter 18 anos ou mais.' : '');
        ok &= rfErr('tel', !/^9\d{8}$/.test(d.tel) ? 'Número inválido (9 dígitos, começa por 9).' : '');
        ok &= rfErr('email', !/^\S+@\S+\.\S+$/.test(d.email) ? 'E-mail inválido.' : '');
    }
    if (p === 2) { d.nac = $rf('rf_nac').value; d.end = v('end'); d.prof = v('prof');
        ok &= rfErr('end', d.end.length < 8 ? 'Indique o endereço completo.' : ''); ok &= rfErr('prof', d.prof.length < 2 ? 'Indique a profissão.' : ''); }
    if (p === 3) { d.renda = $rf('rf_renda').value; ok &= rfErr('renda', !d.renda ? 'Selecione o rendimento.' : ''); ok &= rfErr('fin', !d.fin ? 'Escolha a finalidade.' : ''); }
    if (p === 4) { ok &= rfErr('doc', !d.doc ? 'Escolha o tipo de documento.' : ''); if (d.doc) ok &= rfErr('files', Object.keys(rf.files).length < 2 ? 'Carregue as duas imagens.' : ''); }
    if (p === 5) { const a = $rf('rf_pw').value, b = $rf('rf_pw2').value; d.pw = a;
        ok &= rfErr('pw', !(a.length >= 8 && /[A-Z]/.test(a) && /[a-z]/.test(a) && /\d/.test(a)) ? 'A palavra-passe não cumpre os requisitos.' : a !== b ? 'As palavras-passe não coincidem.' : ''); }
    if (p === 6) { const g = id => [...document.querySelectorAll(`#${id} input`)].map(i => i.value).join(''), a = g('rfPin1'), b = g('rfPin2'); d.pin = a;
        $rf('rfm_pin').textContent = !/^\d{4}$/.test(a) ? 'Introduza os 4 dígitos.' : ['1234', '0000', '1111', '4321', '2580'].includes(a) ? 'PIN demasiado fácil de adivinhar.' : a !== b ? 'Os PINs não coincidem.' : '';
        ok &= !$rf('rfm_pin').textContent; }
    if (p === 7) { d.ok1 = $rf('rfC1').checked; d.ok2 = $rf('rfC2').checked;
        $rf('rfm_ck').textContent = !(d.ok1 && d.ok2 && $rf('rfC3').checked) ? 'Tem de aceitar todas as caixas para continuar.' : ''; ok &= !$rf('rfm_ck').textContent; }
    return !!ok;
}
function rfNext() { if (!rfVal()) return; if (rf.p === 7) return rfSubmit(); rf.p++; rfRender(); }
function rfBack() { rf.p--; rfRender(); }
function rfDoc(t) { rf.d.doc = t; rf.files = {}; rfRender(); }
function rfUpload(el, i) {
    const f = el.files[0]; if (!f) return;
    if (!f.type.startsWith('image/')) { rfErr('files', 'Escolha uma imagem (JPG ou PNG).'); return; }
    if (f.size > 5 * 1024 * 1024) { rfErr('files', 'Ficheiro acima de 5 MB.'); return; }
    const r = new FileReader(); r.onload = () => { rf.files[i] = r.result; rfRender(); }; r.readAsDataURL(f);
}
function rfToggle(id, b) { const e = $rf(id); e.type = e.type === 'password' ? 'text' : 'password'; b.textContent = e.type === 'password' ? 'Mostrar' : 'Ocultar'; }
function rfStrength() {
    const a = $rf('rf_pw').value, t = [a.length >= 8, /[A-Z]/.test(a), /[a-z]/.test(a), /\d/.test(a)];
    [...$rf('rfRules').children].forEach((l, i) => l.className = t[i] ? 'ok' : '');
    const n = t.filter(Boolean).length; $rf('rfMeter').style.width = n * 25 + '%';
    $rf('rfMeter').style.background = ['', 'var(--red)', '#F59E0B', '#F59E0B', 'var(--green)'][n] || '';
}
function rfPins() {
    ['rfPin1', 'rfPin2'].forEach(g => {
        const ins = [...document.querySelectorAll(`#${g} input`)];
        ins.forEach((el, i) => {
            el.oninput = () => { el.value = el.value.replace(/\D/g, ''); if (el.value && ins[i + 1]) ins[i + 1].focus(); else if (el.value && g === 'rfPin1') document.querySelector('#rfPin2 input').focus(); };
            el.onkeydown = e => { if (e.key === 'Backspace' && !el.value && ins[i - 1]) ins[i - 1].focus(); };
        });
    });
    document.querySelector('#rfPin1 input').focus();
}
function rfTab(n) { $rf('rfLegal').innerHTML = n === 1 ? RF_TERMS : RF_PRIV; $rf('rfT1').className = n === 1 ? 'on' : ''; $rf('rfT2').className = n === 2 ? 'on' : ''; $rf('rfLegal').scrollTop = 0; }

async function rfSubmit() {
    if (rf.busy) return; rf.busy = true;
    const btn = $rf('rfNext'); btn.disabled = true; btn.textContent = 'A criar conta...';
    const d = rf.d;
    try {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome: d.nome, email: d.email, telefone: '+244' + d.tel,
                password: d.pw, confirm_password: d.pw, terms_accepted: true,
                data_nascimento: d.nasc, nacionalidade: d.nac, morada: d.end, profissao: d.prof,
                rendimento_mensal: d.renda, finalidade: d.fin, pin: d.pin
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Verifique os dados introduzidos.');
        await onAuthSuccess(data);
        const docs = { type: d.doc, f: rf.files[0], v: rf.files[1], nome: d.nome, morada: d.end };
        closeRegisterFlow();
        rfVerifyDocs(docs);   // em segundo plano: a conta já está ativa
    } catch (err) {
        $rf('rfm_ck').textContent = err.message;
        btn.disabled = false; btn.textContent = 'Criar conta';
    } finally { rf.busy = false; }
}
// Envia os documentos para o KYC existente (extração por IA + confirmação).
// Se falhar, a conta fica "KYC Pendente" e o cliente pode concluir pelo modal de KYC.
async function rfVerifyDocs(x) {
    const H = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.token}` };
    try {
        toast('A verificar o seu documento...', 'info');
        let r = await fetch(`${API_BASE}/api/kyc/extract`, { method: 'POST', headers: H, body: JSON.stringify({ doc_type: x.type, foto_frente: x.f, foto_verso: x.v }) });
        const ex = (await r.json()).extracted;
        if (!r.ok || !ex || !ex.doc_numero) throw new Error('extract');
        const partes = (ex.nome_completo || x.nome).split(/\s+/);
        r = await fetch(`${API_BASE}/api/kyc/confirm`, { method: 'POST', headers: H, body: JSON.stringify({
            nome_completo: ex.nome_completo || x.nome, primeiro_nome: ex.primeiro_nome || partes[0], ultimo_nome: ex.ultimo_nome || partes[partes.length - 1],
            nome_pai: ex.nome_pai || '', nome_mae: ex.nome_mae || '', doc_tipo: x.type, doc_numero: ex.doc_numero,
            morada: ex.morada || x.morada, data_emissao: ex.data_emissao || '' }) });
        const data = await r.json(); if (!r.ok) throw new Error('confirm');
        state.user = { ...state.user, ...data.user, kyc_status: 'verificado' };
        localStorage.setItem('bankao_user', JSON.stringify(state.user));
        updateTopbarUser(state.user); await loadUserData();
        toast('✅ Identidade verificada! A sua conta BankAO está ativa.', 'success');
    } catch (e) {
        toast('Conta criada. Não conseguimos ler o documento — conclua a verificação quando quiser.', 'info');
    }
}
