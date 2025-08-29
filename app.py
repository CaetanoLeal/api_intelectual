from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações do RD Station CRM - URL CORRIGIDA
RD_API_KEY = "SEU_TOKEN_RDSTATION"
RD_API_URL = "https://api.rd.services/platform/contacts"  # URL CORRETA para v3

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        # Log da requisição recebida
        logger.info("=" * 50)
        logger.info(f"📥 NOVA REQUISIÇÃO RECEBIDA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        data = request.json
        logger.info("📦 DADOS RECEBIDOS DO WIX:")
        logger.info(f"   JSON Completo: {data}")
        
        # CORREÇÃO: Acessar a estrutura correta
        wix_data = data.get("data", {})  # Isso está correto agora
        
        # Extraindo os campos do formulário
        ensino_medio = wix_data.get("field:ensino_medio")
        ensino_fundamental = wix_data.get("field:ensino_fundamental")
        
        # Determina a série de interesse
        if ensino_medio and ensino_medio != "6° Ano":
            serie_interesse = ensino_medio
        elif ensino_fundamental:
            serie_interesse = ensino_fundamental
        else:
            serie_interesse = "Não informado"
        
        responsavel = wix_data.get("field:first_name")
        aluno = wix_data.get("field:sobrenome_fad9")
        email = wix_data.get("field:email")
        telefone = wix_data.get("field:phone")
        nascimento = wix_data.get("field:data_de_nascimento")
        cpf = wix_data.get("field:resposta_curta_01e4")
        ajuda_prova = wix_data.get("field:precisa_de_ajuda_durante_a_prova")
        observacao = wix_data.get("field:resposta_longa_f606")
        confirma_dados = wix_data.get("field:form_field_ddd2")
        autorizacao = wix_data.get("field:form_field_68ba")

        # Log dos dados extraídos
        logger.info("🔍 DADOS EXTRAÍDOS:")
        logger.info(f"   Ensino Médio: {ensino_medio}")
        logger.info(f"   Ensino Fundamental: {ensino_fundamental}")
        logger.info(f"   Série interesse: {serie_interesse}")
        logger.info(f"   Responsável: {responsavel}")
        logger.info(f"   Aluno: {aluno}")
        logger.info(f"   Email: {email}")
        logger.info(f"   Telefone: {telefone}")
        logger.info(f"   Nascimento: {nascimento}")
        logger.info(f"   CPF: {cpf}")
        logger.info(f"   Ajuda prova: {ajuda_prova}")
        logger.info(f"   Observação: {observacao}")
        logger.info(f"   Confirma dados: {confirma_dados}")
        logger.info(f"   Autorização: {autorizacao}")

        # Montando payload para o RD CRM (formato v3)
        lead = {
            "name": responsavel,
            "email": email,
            "personal_phone": telefone,
            "cf_aluno": aluno,
            "cf_serie_interesse": serie_interesse,
            "cf_data_nascimento": nascimento,
            "cf_cpf": cpf,
            "cf_ajuda_prova": ajuda_prova,
            "cf_observacao": observacao,
            "cf_confirma_dados": confirma_dados,
            "cf_autorizacao": autorizacao
        }

        # Log do payload
        logger.info("🚀 PAYLOAD PARA RD STATION:")
        logger.info(f"   {lead}")

        # Fazendo requisição para criar lead no RD CRM (HEADERS CORRETOS)
        logger.info("📤 ENVIANDO PARA RD STATION...")
        headers = {
            "Authorization": f"Bearer {RD_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(RD_API_URL, headers=headers, json=lead)

        # Log da resposta
        logger.info("📥 RESPOSTA DO RD STATION:")
        logger.info(f"   Status Code: {response.status_code}")
        logger.info(f"   Response: {response.text}")
        
        try:
            response_json = response.json()
        except:
            response_json = {"raw_response": response.text}
            
        logger.info("✅ PROCESSAMENTO CONCLUÍDO")
        logger.info("=" * 50)

        return jsonify({
            "status": "success",
            "status_rd": response.status_code,
            "response_rd": response_json,
            "received_data": data
        })

    except Exception as e:
        logger.error("❌ ERRO NO PROCESSAMENTO:")
        logger.error(f"   Tipo do erro: {type(e).__name__}")
        logger.error(f"   Mensagem: {str(e)}")
        logger.error(f"   Dados recebidos: {data if 'data' in locals() else 'N/A'}")
        logger.error("=" * 50)
        
        return jsonify({
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
            "received_data": data if 'data' in locals() else None
        }), 500

# Health check
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    logger.info("🚀 API Iniciada")
    app.run(host="0.0.0.0", port=5000, debug=True)
    