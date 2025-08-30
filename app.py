from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========= CONFIG =========
RD_CRM_TOKEN = "685d3cf0e1321000184f38fc"  # seu token fixo
CRM_BASE = "https://crm.rdstation.com/api/v1"

# Nome do funil
PIPELINE_NAME = "matriculas 2026"
# Sempre usar a primeira etapa
FIRST_STAGE_NAME = None

def auth_params():
    return {"token": RD_CRM_TOKEN}

# ---------- CONTACT ----------
def crm_find_contact_by_email(email: str):
    if not email:
        return None
    try:
        r = requests.get(
            f"{CRM_BASE}/contacts",
            params={**auth_params(), "email": email},
            timeout=30
        )
        if r.status_code == 200:
            items = r.json().get("items") or r.json().get("contacts") or []
            return items[0] if items else None
        else:
            logger.warning(f"[CRM] find contact by email status={r.status_code} body={r.text}")
            return None
    except Exception as e:
        logger.error(f"[CRM] find contact error: {e}")
        return None

def crm_create_contact(contact_data: dict):
    payload = {
        "name": contact_data.get("name") or contact_data.get("cf_responsavel"),
        "emails": [contact_data.get("email")] if contact_data.get("email") else [],
        "phones": [contact_data.get("personal_phone")] if contact_data.get("personal_phone") else [],
        # custom fields (se existirem no CRM com esses "identifiers")
        "cf_responsavel": contact_data.get("cf_responsavel"),
        "cf_aluno": contact_data.get("cf_aluno"),
        "cf_email": contact_data.get("cf_email") or contact_data.get("email"),
        "cf_telefone": contact_data.get("cf_telefone") or contact_data.get("personal_phone"),
        "cf_data_nascimento": contact_data.get("cf_data_nascimento"),
        "cf_cpf": contact_data.get("cf_cpf"),
        "cf_ensino_medio": contact_data.get("cf_ensino_medio"),
        "cf_ensino_fundamental": contact_data.get("cf_ensino_fundamental"),
        "cf_serie_interesse": contact_data.get("cf_serie_interesse"),
        "cf_ajuda_prova": contact_data.get("cf_ajuda_prova"),
        "cf_observacao": contact_data.get("cf_observacao"),
        "cf_confirma_dados": contact_data.get("cf_confirma_dados"),
        "cf_autorizacao": contact_data.get("cf_autorizacao"),
    }
    payload = {k: v for k, v in payload.items() if v not in (None, [], "")}

    r = requests.post(f"{CRM_BASE}/contacts", params=auth_params(), json=payload, timeout=30)
    return r

def get_pipeline_id_by_name(name: str):
    r = requests.get(f"{CRM_BASE}/deal_pipelines", params=auth_params(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Falha ao listar funis: {r.status_code} {r.text}")
    items = r.json().get("items") or r.json()
    for p in items:
        if (p.get("name") or "").strip().lower() == name.strip().lower():
            return p.get("id")
    raise RuntimeError(f"Funil '{name}' não encontrado no RD CRM")

def get_stage_id_for_pipeline(pipeline_id: str, preferred_name: str = None):
    params = {**auth_params(), "deal_pipeline_id": pipeline_id}
    r = requests.get(f"{CRM_BASE}/deal_stages", params=params, timeout=30)
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

def create_deal_for_contact(contact_id: str, stage_id: str, title: str, value: float = 0.0):
    payload = {
        "name": title,
        "value": value,
        "currency": "BRL",
        "deal_stage_id": stage_id,
        "pipeline_id": get_pipeline_id_by_name(PIPELINE_NAME),
        "contact_id": contact_id,
        "notes": "Origem: Formulário Wix (matriculas 2026)"
    }
    r = requests.post(f"{CRM_BASE}/deals", params=auth_params(), json=payload, timeout=30)
    return r

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        data = request.json
        if not data or 'data' not in data:
            return jsonify({"error": "Dados inválidos"}), 400

        wix_data = data.get("data", {})
        contact_info = {
            "name": wix_data.get("field:first_name"),
            "email": wix_data.get("field:email"),
            "personal_phone": wix_data.get("field:phone"),
            "cf_responsavel": wix_data.get("field:first_name"),
            "cf_aluno": wix_data.get("field:sobrenome_fad9"),
            "cf_serie_interesse": wix_data.get("field:ensino_medio") or wix_data.get("field:ensino_fundamental") or "Não informado",
            "cf_data_nascimento": wix_data.get("field:data_de_nascimento"),
            "cf_cpf": wix_data.get("field:resposta_curta_01e4"),
            "cf_ajuda_prova": wix_data.get("field:precisa_de_ajuda_durante_a_prova"),
            "cf_observacao": wix_data.get("field:resposta_longa_f606"),
            "cf_confirma_dados": wix_data.get("field:form_field_ddd2"),
            "cf_autorizacao": wix_data.get("field:form_field_68ba"),
            "cf_ensino_medio": wix_data.get("field:ensino_medio"),
            "cf_ensino_fundamental": wix_data.get("field:ensino_fundamental"),
        }

        existing = crm_find_contact_by_email(contact_info.get("email"))
        if existing:
            contact_id = existing.get("id")
        else:
            c = crm_create_contact(contact_info)
            if c.status_code not in (200, 201):
                return jsonify({"error": "Falha ao criar contato", "details": c.text}), c.status_code
            contact_id = c.json().get("id")

        pipeline_id = get_pipeline_id_by_name(PIPELINE_NAME)
        stage_id = get_stage_id_for_pipeline(pipeline_id, FIRST_STAGE_NAME)

        aluno = contact_info.get("cf_aluno") or contact_info.get("name") or "Matrícula"
        title = f"Matrícula 2026 - {aluno}"
        d = create_deal_for_contact(contact_id, stage_id, title, value=0)

        if d.status_code in (200, 201):
            deal = d.json()
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
    app.run(host="0.0.0.0", port=5000, debug=False)
