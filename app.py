from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações do RD Station CRM
RD_API_KEY = "SEU_TOKEN_RDSTATION"
RD_API_URL = "https://crm.rdstation.com/api/v1/leads"

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    try:
        # Log da requisição recebida
        logger.info("=" * 50)
        logger.info(f"📥 NOVA REQUISIÇÃO RECEBIDA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)
        
        # Log dos headers recebidos
        logger.info("📋 HEADERS RECEBIDOS:")
        for key, value in request.headers.items():
            logger.info(f"   {key}: {value}")
        
        data = request.json
        logger.info("📦 DADOS RECEBIDOS DO WIX:")
        logger.info(f"   JSON Completo: {data}")
        
        # Extraindo os campos do formulário (NOVA ESTRUTURA DO WIX)
        ensino_medio = data.get("ensino_medio")
        ensino_fundamental = data.get("ensino_fundamental")
        
        # Determina a série de interesse baseado em qual campo foi preenchido
        if ensino_medio:
            serie_interesse = ensino_medio
        elif ensino_fundamental:
            serie_interesse = ensino_fundamental
        else:
            serie_interesse = "Não informado"
        
        responsavel = data.get("first_name")
        aluno = data.get("sobrenome_fad9")
        email = data.get("email")
        telefone = data.get("phone")
        nascimento = data.get("data_de_nascimento")
        cpf = data.get("resposta_curta_01e4")
        ajuda_prova = data.get("precisa_de_ajuda_durante_a_prova")
        observacao = data.get("resposta_longa_f606")
        confirma_dados = data.get("form_field_ddd2")
        autorizacao = data.get("form_field_68ba")

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

        # Montando payload para o RD CRM
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

        # Log do payload que será enviado ao RD Station
        logger.info("🚀 PAYLOAD PARA RD STATION:")
        logger.info(f"   {lead}")

        # Fazendo requisição para criar lead no RD CRM
        logger.info("📤 ENVIANDO PARA RD STATION...")
        response = requests.post(
            RD_API_URL,
            headers={"Authorization": f"Bearer {RD_API_KEY}"},
            json=lead
        )

        # Log da resposta do RD Station
        logger.info("📥 RESPOSTA DO RD STATION:")
        logger.info(f"   Status Code: {response.status_code}")
        logger.info(f"   Response: {response.text}")
        
        # Verifica se a resposta é JSON válido
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
        # Log de erro detalhado
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

# Rota de health check para testar se a API está online
@app.route("/health", methods=["GET"])
def health_check():
    logger.info("🔍 Health check realizado")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# Rota para testar o recebimento de dados
@app.route("/test", methods=["POST"])
def test_endpoint():
    logger.info("🧪 TEST ENDPOINT ACESSADO")
    data = request.json
    logger.info(f"Dados de teste recebidos: {data}")
    return jsonify({"status": "test_ok", "received_data": data})

if __name__ == "__main__":
    logger.info("🚀 API Iniciada")
    app.run(host="0.0.0.0", port=5000, debug=True)