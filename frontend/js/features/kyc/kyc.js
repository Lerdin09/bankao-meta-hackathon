/**
 * KYC — verificação de identidade
 * Fluxo em 4 passos: documento, fotos, extração por IA e confirmação.
 */

// =====================================================================
//  KYC — Verificação de Identidade por IA (4 Passos)
// =====================================================================

const kycState = {
    docType: null,
    fotoFrente: null,
    fotoVerso: null,
    extracted: null
};
function openKYCModal() {
    kycState.docType = null;
    kycState.fotoFrente = null;
    kycState.fotoVerso = null;
    kycState.extracted = null;
    // Reset visual
    ['optBI','optPassaporte'].forEach(id => document.getElementById(id).classList.remove('selected'));
    document.getElementById('btnKycStep1Next').disabled = true;
    document.getElementById('btnKycStep2Next').disabled = true;
    resetPhotoZone('frente');
    resetPhotoZone('verso');
    // Reset progress dots
    for (let i = 1; i <= 4; i++) {
        const d = document.getElementById(`kycStepDot${i}`);
        d.classList.remove('active','done');
    }
    document.getElementById('kycStepDot1').classList.add('active');

    const m = document.getElementById('modalKYC');
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('active'), 10);
    kycShowPanel(1);
}
function closeKYCModal() {
    const m = document.getElementById('modalKYC');
    m.classList.remove('active');
    setTimeout(() => m.style.display = 'none', 300);
}
function kycShowPanel(n) {
    for (let i = 1; i <= 4; i++) {
        document.getElementById(`kycPanel${i}`).style.display = i === n ? '' : 'none';
    }
}
function kycUpdateStepDots(currentStep) {
    for (let i = 1; i <= 4; i++) {
        const d = document.getElementById(`kycStepDot${i}`);
        d.classList.remove('active','done');
        if (i < currentStep) d.classList.add('done');
        else if (i === currentStep) d.classList.add('active');
    }
}
function selectDocType(type) {
    kycState.docType = type;
    document.getElementById('optBI').classList.toggle('selected', type === 'bilhete');
    document.getElementById('optPassaporte').classList.toggle('selected', type === 'passaporte');
    document.getElementById('btnKycStep1Next').disabled = false;

    // Adaptar rótulos do passo 2
    const isPassaporte = type === 'passaporte';
    document.getElementById('kycUploadTitle').textContent = isPassaporte ? 'Fotografias do Passaporte' : 'Fotografias do Bilhete de Identidade';
    document.getElementById('kycUploadDesc').textContent = isPassaporte
        ? 'Tire ou carregue fotografias da página de dados (com foto) e da página de assinatura.'
        : 'Tire ou carregue fotografias da frente e do verso do Bilhete de Identidade.';
    document.getElementById('labelFrente').textContent = isPassaporte ? 'Página de dados (com foto)' : 'Frente do BI';
    document.getElementById('labelVerso').textContent = isPassaporte ? 'Página de assinatura' : 'Verso do BI';
    document.getElementById('kycDocNumLabel').textContent = isPassaporte ? 'N.º do Passaporte' : 'NIF / N.º do Bilhete';
}
async function kycGoToStep(step) {
    if (step === 3) {
        // Validar fotos antes de avançar
        if (!kycState.fotoFrente || !kycState.fotoVerso) {
            toast('Carregue as duas fotografias do documento antes de continuar.', 'error');
            return;
        }
        kycShowPanel(3);
        kycUpdateStepDots(3);
        // Reiniciar animação de progresso
        const fill = document.getElementById('kycProgressFill');
        fill.style.animation = 'none';
        fill.offsetHeight; // reflow
        fill.style.animation = '';
        // Chamar extração por IA
        await extractKYCData();
        return;
    }
    kycShowPanel(step);
    kycUpdateStepDots(step);
}
function resetPhotoZone(side) {
    const placeholder = document.getElementById(`placeholder${side.charAt(0).toUpperCase() + side.slice(1)}`);
    const preview = document.getElementById(`preview${side.charAt(0).toUpperCase() + side.slice(1)}`);
    const zone = document.getElementById(`zone${side.charAt(0).toUpperCase() + side.slice(1)}`);
    placeholder.style.display = '';
    preview.style.display = 'none';
    preview.src = '';
    zone.classList.remove('has-photo');
}
function handleDocPhoto(side, input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        const b64 = e.target.result;
        const capSide = side.charAt(0).toUpperCase() + side.slice(1);
        const preview = document.getElementById(`preview${capSide}`);
        const placeholder = document.getElementById(`placeholder${capSide}`);
        const zone = document.getElementById(`zone${capSide}`);
        preview.src = b64;
        preview.style.display = 'block';
        placeholder.style.display = 'none';
        zone.classList.add('has-photo');
        if (side === 'frente') kycState.fotoFrente = b64;
        else kycState.fotoVerso = b64;
        // Habilitar botão quando ambas estiverem carregadas
        document.getElementById('btnKycStep2Next').disabled = !(kycState.fotoFrente && kycState.fotoVerso);
    };
    reader.readAsDataURL(file);
}
async function loadSampleDocument() {
    const btn = document.getElementById('btnUseSample');
    const origText = btn.textContent;
    btn.textContent = 'A carregar amostra...';
    btn.disabled = true;
    try {
        const docType = kycState.docType || 'bilhete';
        const res = await fetch(`${API_BASE}/api/kyc/samples/${docType}`, {
            headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
        });
        if (!res.ok) throw new Error('Amostra não disponível.');
        const data = await res.json();

        // Preencher frente
        kycState.fotoFrente = data.foto_frente;
        const previewF = document.getElementById('previewFrente');
        previewF.src = data.foto_frente;
        previewF.style.display = 'block';
        document.getElementById('placeholderFrente').style.display = 'none';
        document.getElementById('zoneFrente').classList.add('has-photo');

        // Preencher verso
        kycState.fotoVerso = data.foto_verso;
        const previewV = document.getElementById('previewVerso');
        previewV.src = data.foto_verso;
        previewV.style.display = 'block';
        document.getElementById('placeholderVerso').style.display = 'none';
        document.getElementById('zoneVerso').classList.add('has-photo');

        document.getElementById('btnKycStep2Next').disabled = false;
        toast('Documento de amostra carregado. Pronto para validar com IA!', 'success');
    } catch (err) {
        toast('Erro ao carregar amostra: ' + err.message, 'error');
    } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
}
async function extractKYCData() {
    const statusEl = document.getElementById('kycAiStatus');
    statusEl.innerHTML = 'A comprimir e enviar imagens ao modelo de IA...<br>Aguarde, este processo pode demorar alguns segundos.';
    try {
        const res = await fetch(`${API_BASE}/api/kyc/extract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({
                doc_type: kycState.docType,
                foto_frente: kycState.fotoFrente,
                foto_verso: kycState.fotoVerso
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro na extração de dados.');

        kycState.extracted = data.extracted;
        statusEl.innerHTML = 'Dados extraídos com sucesso! A preparar a confirmação...';

        // Preencher campos do passo 4
        const ext = data.extracted;
        document.getElementById('kycNomeCompleto').value  = ext.nome_completo || '';
        document.getElementById('kycPrimeiroNome').value  = ext.primeiro_nome || '';
        document.getElementById('kycUltimoNome').value    = ext.ultimo_nome || '';
        document.getElementById('kycNomePai').value       = ext.nome_pai || '';
        document.getElementById('kycNomeMae').value       = ext.nome_mae || '';
        document.getElementById('kycDocNumero').value     = ext.doc_numero || '';
        document.getElementById('kycDataEmissao').value   = ext.data_emissao || '';
        document.getElementById('kycMorada').value        = ext.morada || '';

        // Avançar para passo 4 com pequeno delay para feedback visual
        setTimeout(() => {
            document.getElementById('kycProgressFill').style.width = '100%';
            setTimeout(() => {
                kycShowPanel(4);
                kycUpdateStepDots(4);
            }, 600);
        }, 800);
    } catch (err) {
        statusEl.innerHTML = `<span style="color:var(--red)">Erro: ${err.message}</span><br><br><button class="btn btn-ghost" onclick="kycGoToStep(2)">← Voltar e tentar novamente</button>`;
    }
}
async function confirmKYC() {
    const errEl = document.getElementById('kycConfirmError');
    errEl.classList.remove('show');
    const btn = document.getElementById('btnKycConfirm');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A guardar...';

    try {
        const payload = {
            nome_completo:  document.getElementById('kycNomeCompleto').value.trim(),
            primeiro_nome:  document.getElementById('kycPrimeiroNome').value.trim(),
            ultimo_nome:    document.getElementById('kycUltimoNome').value.trim(),
            nome_pai:       document.getElementById('kycNomePai').value.trim(),
            nome_mae:       document.getElementById('kycNomeMae').value.trim(),
            doc_tipo:       kycState.docType,
            doc_numero:     document.getElementById('kycDocNumero').value.trim(),
            morada:         document.getElementById('kycMorada').value.trim(),
            data_emissao:   document.getElementById('kycDataEmissao').value.trim()
        };
        if (!payload.nome_completo || !payload.doc_numero) {
            throw new Error('Nome completo e número de documento são obrigatórios.');
        }

        const res = await fetch(`${API_BASE}/api/kyc/confirm`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao confirmar identidade.');

        // Atualizar estado local
        state.user = { ...state.user, ...data.user, kyc_status: 'verificado' };
        localStorage.setItem('bankao_user', JSON.stringify(state.user));
        updateTopbarUser(state.user);

        closeKYCModal();
        await loadUserData();
        toast('✅ Identidade verificada! A sua carteira BankAO está ativa com 100.000 Kz de bónus.', 'success');
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Confirmar e Ativar Carteira';
    }
}
