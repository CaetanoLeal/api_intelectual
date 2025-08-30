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
PIPELINE_NAME = "matriculas 2026"
FIRST_STAGE_NAME = None  # usa a primeira etapa por padrão

def auth_params():
    return {"token": RD_CRM_TOKEN}

# ---------- CONTACT ----------
def crm_find_contact_by_email(email: str):
    if not email:
        logger.warning("Email vazio ao buscar contato")
        return None
    try:
        logger.info(f"Buscando contato pelo email: {email}")
        r = requests.get(f"{CRM_BASE}/contacts", params={**auth_params(), "email": email}, timeout=30)
        logger.info(f"Status da busca: {r.status_code} | Response: {r.text}")
        if r.status_code == 200:
            items = r.json().get("items") or r.json().get("contacts") or []
            return items[0] if items else None
        return None
    except Exception as e:
        logger.exception("Erro ao buscar contato")
        return None

def crm_create_contact(contact_data: dict):
    payload = {k: v for k, v in contact_data.items() if v not in (None, [], "")}
    try:
        logger.info(f"Criando contato com payload: {payload}")
        r = requests.post(f"{CRM_BASE}/contacts", params=auth_params(), json=payload, timeout=30)
        logger.info(f"Status criação contato: {r.status_code} | Response: {r.text}")
        return r
    except Exception as e:
        logger.exception("Erro ao criar contato")
        raise

def get_pipeline_id_by_name(name: str):
    try:
        r = requests.get(f"{CRM_BASE}/deal_pipelines", params=auth_params(), timeout=30)
        logger.info(f"Status pipelines: {r.status_code} | Response: {r.text}")
        if r.status_code != 200:
            raise RuntimeError(f"Falha ao listar funis: {r.status_code} {r.text}")
        items = r.json().get("items") or r.json()
        for p in items:
            if (p.get("name") or "").strip().lower() == name.strip().lower():
                logger.info(f"Pipeline encontrado: {p}")
                return p.get("id")
        raise RuntimeError(f"Funil '{name}' não encontrado")
    except Exception as e:
        logger.exception("Erro ao obter pipeline")
        raise

def get_stage_id_for_pipeline(pipeline_id: str, preferred_name: str = None):
    try:
        params = {**auth_params(), "deal_pipeline_id": pipeline_id}
        r = requests.get(f"{CRM_BASE}/deal_stages", params=params, timeout=30)
        logger.info(f"Status stages: {r.status_code} | Response: {r.text}")
        if r.status_code != 200:
            raise RuntimeError(f"Falha ao listar etapas: {r.status_code} {r.text}")
        stages = r.json().get("items") or r.json()
        if preferred_name:
            for s in stages:
                if (s.get("name") or "").strip().lower() == preferred_name.strip().lower():
                    return s.get("id")
        stages_sorted = sorted(stages, key=lambda s: (s.get("position") or 0))
        if not stages_sorted:
            raise RuntimeError("Nenhuma etapa encontrada")
        return stages_sorted[0].get("id")
    except Exception as e:
        logger.exception("Erro ao obter stage_id")
        raise

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
    try:
        logger.info(f"Criando deal com payload: {payload}")
        r = requests.post(f"{CRM_BASE}/deals", params=auth_params(), json=payload, timeout=30)
        logger.info(f"Status criação deal: {r.status_code} | Response: {r.text}")
        return r
    except Exception as e:
        logger.exception("Erro ao criar deal")
        raise

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        data = request.json
        logger.info(f"Recebido POST do Wix: {data}")
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

        logger.info(f"Dados do lead extraídos: {contact_info}")

        existing = crm_find_contact_by_email(contact_info.get("email"))
        if existing:
            contact_id = existing.get("id")
            logger.info(f"Contato já existe: {contact_id}")
        else:
            c = crm_create_contact(contact_info)
            if c.status_code not in (200, 201):
                logger.error(f"Falha ao criar contato: {c.text}")
                return jsonify({"error": "Falha ao criar contato", "details": c.text}), c.status_code
            contact_id = c.json().get("id")
            logger.info(f"Contato criado: {contact_id}")

        pipeline_id = get_pipeline_id_by_name(PIPELINE_NAME)
        stage_id = get_stage_id_for_pipeline(pipeline_id, FIRST_STAGE_NAME)
        logger.info(f"Pipeline ID: {pipeline_id} | Stage ID: {stage_id}")

        aluno = contact_info.get("cf_aluno") or contact_info.get("name") or "Matrícula"
        title = f"Matrícula 2026 - {aluno}"
        d = create_deal_for_contact(contact_id, stage_id, title, value=0)

        if d.status_code in (200, 201):
            deal = d.json()
            logger.info(f"Deal criado com sucesso: {deal}")
            return jsonify({
                "status": "success",
                "contact_id": contact_id,
                "deal_id": deal.get("id"),
                "pipeline": PIPELINE_NAME
            }), 201
        else:
            logger.error(f"Falha ao criar deal: {d.text}")
            return jsonify({"error": "Falha ao criar negociação", "details": d.text}), d.status_code

    except Exception as e:
        logger.exception("Erro geral na rota /wix-lead")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
