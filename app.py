from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import json
import os

# ========= LOGGING =========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========= CONFIG =========
RD_CRM_TOKEN = os.getenv("RD_CRM_TOKEN", "SEU_TOKEN_AQUI")
CRM_BASE = "https://crm.rdstation.com/api/v1"
PIPELINE_NAME = "matriculas 2026"
FIRST_STAGE_NAME = None           # usa a primeira etapa do funil
USE_QUERY_TOKEN_FALLBACK = True   # se sua conta não aceitar Bearer, mantém compatibilidade

def auth_headers():
    return {
        "Authorization": f"Bearer {RD_CRM_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def auth_params():
    # Fallback opcional para contas que exigem ?token=
    return {"token": RD_CRM_TOKEN} if USE_QUERY_TOKEN_FALLBACK else {}

def _req(method, path, *, params=None, json_body=None, timeout=30):
    url = f"{CRM_BASE}{path}"
    params = {**(params or {}), **auth_params()}
    try:
        r = requests.request(
            method, url, headers=auth_headers(), params=params, json=json_body,
            timeout=timeout, allow_redirects=False
        )
        logger.info(f"{method} {url} -> {r.status_code}  resp={r.text[:600]}")
        return r
    except requests.RequestException as e:
        logger.exception(f"Erro HTTP em {method} {url}")
        raise

# ---------- CONTACTS ----------
def crm_find_contact_by_email(email: str):
    """
    Busca contato por e-mail no RD Station CRM.
    Endpoint correto: GET /contacts?email=<email>
    Retorna o primeiro contato encontrado ou None.
    """
    if not email:
        return None
    r = _req("GET", "/contacts", params={"email": email})
    if r.status_code == 200:
        data = r.json()
        items = data.get("items") or data.get("contacts") or data if isinstance(data, list) else []
        return items[0] if items else None
    if r.status_code == 404:
        # Nenhum contato encontrado
        return None
    # Qualquer outro caso tratar como não encontrado
    logger.warning(f"Busca por email retornou status inesperado: {r.status_code}")
    return None

def crm_create_contact(contact_data: dict):
    """
    Cria contato no CRM.
    Payload com emails/phones como objetos (formato mais aceito).
    """
    email = contact_data.get("email")
    phone = contact_data.get("personal_phone")
    payload = {
        "name": contact_data.get("name"),
        # formatos aceitos costumam incluir type (personal, work) / (mobile, work, home)
        "emails": ([{"email": email, "type": "personal"}] if email else []),
        "phones": ([{"phone": phone, "type": "mobile"}] if phone else []),
        "custom_fields": [
            {"custom_field_id": "685ac5b788f78e001fd61690", "value": contact_data.get("cf_aluno")},
            {"custom_field_id": "685ac789ef58410018d21e32", "value": contact_data.get("cf_serie")},
            {"custom_field_id": "68b22d41efed600017c2d72b", "value": contact_data.get("cf_cpf")},
            {"custom_field_id": "68b22d59b64e5d0018e2b5f5", "value": contact_data.get("cf_data_nascimento")},
        ]
    }
    # remove campos vazios
    payload["custom_fields"] = [f for f in payload["custom_fields"] if f.get("value")]
    logger.info(f"Payload criar contato: {json.dumps(payload, ensure_ascii=False)}")
    return _req("POST", "/contacts", json_body=payload)

# ---------- PIPELINES & STAGES ----------
def get_pipeline_id_by_name(name: str):
    r = _req("GET", "/deal_pipelines")
    if r.status_code != 200:
        raise RuntimeError(f"Falha ao listar funis: {r.status_code} {r.text}")
    items = r.json().get("items") or r.json()
    for p in items:
        if (p.get("name") or "").strip().lower() == name.strip().lower():
            return p.get("id")
    raise RuntimeError(f"Funil '{name}' não encontrado")

def get_stage_id_for_pipeline(pipeline_id: str, preferred_name: str = None):
    r = _req("GET", "/deal_stages", params={"deal_pipeline_id": pipeline_id})
    if r.status_code != 200:
        raise RuntimeError(f"Falha ao listar etapas: {r.status_code} {r.text}")
    stages = r.json().get("items") or r.json()
    if preferred_name:
        for s in stages:
            if (s.get("name") or "").strip().lower() == preferred_name.strip().lower():
                return s.get("id")
    stages_sorted = sorted(stages, key=lambda s: (s.get("position") or 0))
    if not stages_sorted:
        raise RuntimeError("Nenhuma etapa encontrada no funil")
    return stages_sorted[0].get("id")

# ---------- DEALS ----------
def create_deal_for_contact(contact_id: str, stage_id: str, pipeline_id: str,
                            title: str, value: float = 0.0, deal_data: dict = None):
    deal_data = deal_data or {}
    payload = {
        "name": title,
        "value": value,
        "currency": "BRL",
        "deal_stage_id": stage_id,
        "pipeline_id": pipeline_id,
        "contact_id": contact_id,
        "notes": "Origem: Formulário Wix (matriculas 2026)",
        "custom_fields": [
            {"custom_field_id": "688b554ef4d99700148b735d", "value": deal_data.get("cf_serie_turma")},
            {"custom_field_id": "68978c98b577530014215608", "value": deal_data.get("cf_responsavel_financeiro")},
            {"custom_field_id": "68b233fb62256e0018cb0d41", "value": deal_data.get("cf_valor_mensalidade")},
        ]
    }
    payload["custom_fields"] = [f for f in payload["custom_fields"] if f.get("value")]
    logger.info(f"Payload criar deal: {json.dumps(payload, ensure_ascii=False)}")
    return _req("POST", "/deals", json_body=payload)

# ---------- WEBHOOK (WIX) ----------
@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        data = request.json
        logger.info(f"Recebido do Wix: {json.dumps(data, ensure_ascii=False)}")

        if not data or 'data' not in data:
            return jsonify({"error": "Dados inválidos"}), 400

        wix_data = data.get("data", {})
        contact_info = {
            "name": wix_data.get("field:first_name") or (wix_data.get("contact", {}).get("name", {}).get("first")),
            "email": wix_data.get("field:email") or wix_data.get("contact", {}).get("email"),
            "personal_phone": wix_data.get("field:phone") or wix_data.get("contact", {}).get("phone"),
            "cf_aluno": wix_data.get("field:sobrenome_fad9"),
            "cf_serie": wix_data.get("field:ensino_medio") or wix_data.get("field:ensino_fundamental"),
            "cf_cpf": wix_data.get("field:resposta_curta_01e4"),
            "cf_data_nascimento": wix_data.get("field:data_de_nascimento") or wix_data.get("contact", {}).get("birthdate"),
        }
        logger.info(f"Montado contact_info: {contact_info}")

        # Estratégia "cria-ou-busca": tenta criar; se API retornar conflito/422, busca por e-mail.
        created = crm_create_contact(contact_info)
        if created.status_code in (200, 201):
            contact_id = created.json().get("id")
            logger.info(f"Contato criado id={contact_id}")
        else:
            # Se já existe / erro de validação, tenta localizar por e-mail
            if created.status_code in (409, 422):
                existing = crm_find_contact_by_email(contact_info.get("email"))
                if existing:
                    contact_id = existing.get("id")
                    logger.info(f"Contato já existia id={contact_id}")
                else:
                    return jsonify({"error": "Falha ao criar contato", "details": created.text}), created.status_code
            else:
                return jsonify({"error": "Falha ao criar contato", "details": created.text}), created.status_code

        pipeline_id = get_pipeline_id_by_name(PIPELINE_NAME)
        stage_id = get_stage_id_for_pipeline(pipeline_id, FIRST_STAGE_NAME)

        aluno = contact_info.get("cf_aluno") or contact_info.get("name") or "Matrícula"
        title = f"Matrícula 2026 - {aluno}"

        deal_data = {
            "cf_serie_turma": contact_info.get("cf_serie"),
            "cf_responsavel_financeiro": contact_info.get("name"),
            "cf_valor_mensalidade": "0",
        }
        d = create_deal_for_contact(contact_id, stage_id, pipeline_id, title, value=0, deal_data=deal_data)

        if d.status_code in (200, 201):
            deal = d.json()
            logger.info(f"Negociação criada id={deal.get('id')}")
            return jsonify({
                "status": "success",
                "contact_id": contact_id,
                "deal_id": deal.get("id"),
                "pipeline": PIPELINE_NAME
            }), 201
        else:
            return jsonify({"error": "Falha ao criar negociação", "details": d.text}), d.status_code

    except Exception as e:
        logger.exception("Erro geral")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
