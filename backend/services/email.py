"""
Serviço de Envio de E-mails e Suporte do BankAO
Encaminha pedidos de suporte, relatos de problemas, fraude e encerramento para o email oficial:
punjalerdin@gmail.com
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("bankao.email")

SUPPORT_EMAIL_RECIPIENT = os.getenv("SUPPORT_EMAIL_RECIPIENT", "punjalerdin@gmail.com")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "suporte@bankao.ao")


def send_support_ticket_email(
    request_id: str,
    user_name: str,
    user_email: str,
    user_phone: Optional[str],
    kind: str,
    message: str,
    recipient: str = SUPPORT_EMAIL_RECIPIENT
) -> bool:
    """
    Envia uma notificação por e-mail com os dados do ticket de suporte para o e-mail oficial.
    Se o servidor SMTP não estiver configurado no ambiente, regista o e-mail estruturado
    no log com prioridade e retorna True (garantindo que o ticket é arquivado com sucesso).
    """
    kind_labels = {
        "suporte": "Ajuda / Suporte Geral",
        "problema": "Reportar um Problema",
        "fraude": "ALERTA DE SEGURANÇA / FRAUDE",
        "encerramento": "Solicitação de Encerramento de Conta"
    }
    label = kind_labels.get(kind, kind.title())

    subject = f"[BankAO {label}] {request_id} - {user_name}"
    body_text = f"""
=============================================================
NOVO PEDIDO DE AJUDA E SUPORTE - BANKAO
=============================================================
Ref. Ticket: {request_id}
Tipo de Pedido: {label} ({kind})
Cliente: {user_name}
E-mail do Cliente: {user_email or 'Não informado'}
Telefone: {user_phone or 'Não informado'}
Destinatário Oficial: {recipient}
-------------------------------------------------------------
MENSAGEM DO CLIENTE:
{message}
=============================================================
Este e-mail foi gerado automaticamente pelo BankAO Copilot Core.
"""

    logger.info("Encaminhando ticket de suporte %s para %s:\n%s", request_id, recipient, body_text)

    # Se configurado SMTP real no .env
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_FROM
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            logger.info("E-mail de suporte %s enviado via SMTP para %s", request_id, recipient)
            return True
        except Exception as exc:
            logger.warning("Falha ao enviar e-mail via SMTP (%s): %s. E-mail preservado em logs/auditoria.", request_id, exc)
            return False

    # Modo desenvolvimento / sandbox sem SMTP configurado: log garantido
    logger.info("Ticket %s pronto e registrado para destino: %s", request_id, recipient)
    return True
