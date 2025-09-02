from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import json

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========= CONFIG =========
RD_CRM_TOKEN = "685d3cf0e1321000184f38fc"
CRM_BASE = "https://crm.rdstation.com/api/v1"
PIPELINE_NAME = "matriculas 2026"
FIRST_STAGE_NAME = None  # usa a primeira etapa

def auth_headers():
    return {"Authorization": f"Bearer {RD_CRM_TOKEN}"}

# ---------- CONTACT ----------
def crm_find_contact_by_email(email: str):
    if not email:
        return None
    try:
        r = requests.get(f"{CRM_BASE}/contacts/email/{email}", headers=auth_headers(), timeout=30)
        logger.info(f"Buscar contato por email={email}, status={r.status_code}, resp={r.text}")
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        logger.exception("Erro ao buscar contato")
        return None

def crm_create_contact(contact_data: dict):
    payload = {
        "name": contact_data.get("name"),
        "emails": [{"email": contact_data.get("email"), "type": "personal"}] if contact_data.get("email") else [],
        "phones": [{"phone": contact_data.get("personal_phone"), "type": "mobile"}] if contact_data.get("personal_phone") else [],
        "custom_fields": [
            {"custom_field_id": "685ac5b788f78e001fd61690", "value": contact_data.get("cf_aluno")},
            {"custom_field_id": "685ac789ef58410018d21e32", "value": contact_data.get("cf_serie")},
            {"custom_field_id": "68b22d41efed600017c2d72b", "value": contact_data.get("cf_cpf")},
            {"custom_field_id": "68b22d59b64e5d0018e2b5f5", "value": contact_data.get("cf_data_nascimento")}
        ]
    }
    payload["custom_fields"] = [f for f in payload["custom_fields"] if f["value"]]
    logger.info(f"Payload criar contato: {json.dumps(payload, ensure_ascii=False)}")
    r = requests.post(f"{CRM_BASE}/contacts", headers=auth_headers(), json=payload, timeout=30)
    logger.info(f"Resposta criar contato: status={r.status_code}, resp={r.text}")
    return r

def get_pipeline_id_by_name(name: str):
    r = requests.get(f"{CRM_BASE}/deal_pipelines", headers=auth_headers(), timeout=30)
    logger.info(f"Listar pipelines status={r.status_code}, resp={r.text}")
    if r.status_code != 200:
        raise RuntimeError(f"Falha ao listar funis: {r.status_code} {r.text}")
    items = r.json().get("items") or r.json()
    for p in items:
        if (p.get("name") or "").strip().lower() == name.strip().lower():
            return p.get("id")
    raise RuntimeError(f"Funil '{name}' não encontrado")

def get_stage_id_for_pipeline(pipeline_id: str, preferred_name: str = None):
    r = requests.get(f"{CRM_BASE}/deal_stages", headers=auth_headers(), params={"deal_pipeline_id": pipeline_id}, timeout=30)
    logger.info(f"Listar etapas status={r.status_code}, resp={r.text}")
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

def create_deal_for_contact(contact_id: str, stage_id: str, title: str, value: float = 0.0, deal_data: dict = None):
    pipeline_id = get_pipeline_id_by_name(PIPELINE_NAME)
    payload = {
        "name": title,
        "value": value,
        "currency": "BRL",
        "deal_stage_id": stage_id,
        "deal_pipeline_id": pipeline_id,
        "contact_id": contact_id,
        "notes": "Origem: Formulário Wix (matriculas 2026)",
        "custom_fields": [
            {"custom_field_id": "688b554ef4d99700148b735d", "value": deal_data.get("cf_serie_turma")},
            {"custom_field_id": "68978c98b577530014215608", "value": deal_data.get("cf_responsavel_financeiro")},
            {"custom_field_id": "68b233fb62256e0018cb0d41", "value": deal_data.get("cf_valor_mensalidade")}
        ]
    }
    payload["custom_fields"] = [f for f in payload["custom_fields"] if f["value"]]
    logger.info(f"Payload criar deal: {json.dumps(payload, ensure_ascii=False)}")
    r = requests.post(f"{CRM_BASE}/deals", headers=auth_headers(), json=payload, timeout=30)
    logger.info(f"Resposta criar deal: status={r.status_code}, resp={r.text}")
    return r

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        data = request.json
        logger.info(f"Recebido do Wix: {json.dumps(data, ensure_ascii=False)}")

        if not data or 'data' not in data:
            return jsonify({"error": "Dados inválidos"}), 400

        wix_data = data.get("data", {})
        contact_info = {
            "name": wix_data.get("field:first_name"),
            "email": wix_data.get("field:email"),
            "personal_phone": wix_data.get("field:phone"),
            "cf_aluno": wix_data.get("field:sobrenome_fad9"),
            "cf_serie": wix_data.get("field:ensino_medio") or wix_data.get("field:ensino_fundamental"),
            "cf_cpf": wix_data.get("field:resposta_curta_01e4"),
            "cf_data_nascimento": wix_data.get("field:data_de_nascimento"),
        }
        logger.info(f"Montado contact_info: {contact_info}")

        existing = crm_find_contact_by_email(contact_info.get("email"))
        if existing and existing.get("id"):
            contact_id = existing.get("id")
            logger.info(f"Contato já existia id={contact_id}")
        else:
            c = crm_create_contact(contact_info)
            if c.status_code not in (200, 201):
                return jsonify({"error": "Falha ao criar contato", "details": c.text}), c.status_code
            contact_id = c.json().get("id")
            logger.info(f"Contato criado id={contact_id}")

        pipeline_id = get_pipeline_id_by_name(PIPELINE_NAME)
        stage_id = get_stage_id_for_pipeline(pipeline_id, FIRST_STAGE_NAME)

        aluno = contact_info.get("cf_aluno") or contact_info.get("name") or "Matrícula"
        title = f"Matrícula 2026 - {aluno}"

        deal_data = {
            "cf_serie_turma": contact_info.get("cf_serie"),
            "cf_responsavel_financeiro": contact_info.get("name"),
            "cf_valor_mensalidade": "0"
        }
        d = create_deal_for_contact(contact_id, stage_id, title, value=0, deal_data=deal_data)

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
