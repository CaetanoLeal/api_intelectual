from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Configurações do RD Station CRM
RD_API_KEY = "SEU_TOKEN_RDSTATION"
RD_API_URL = "https://crm.rdstation.com/api/v1/leads"

@app.route("/wix-lead", methods=["POST"])
def receive_wix_lead():
    data = request.json

    # Extraindo os campos do formulário
    serie = data.get("serie_interesse")
    responsavel = data.get("responsavel")
    aluno = data.get("aluno")
    email = data.get("email")
    telefone = data.get("telefone")
    nascimento = data.get("data_nascimento")
    cpf = data.get("cpf")
    ajuda_prova = data.get("ajuda_prova")
    observacao = data.get("observacao")
    confirma_dados = data.get("confirma_dados")
    autorizacao = data.get("autorizacao")

    # Montando payload para o RD CRM
    lead = {
        "name": responsavel,
        "email": email,
        "personal_phone": telefone,
        "cf_aluno": aluno,                  # campo customizado (cf_*)
        "cf_serie_interesse": serie,
        "cf_data_nascimento": nascimento,
        "cf_cpf": cpf,
        "cf_ajuda_prova": ajuda_prova,
        "cf_observacao": observacao,
        "cf_confirma_dados": confirma_dados,
        "cf_autorizacao": autorizacao
    }

    # Fazendo requisição para criar lead no RD CRM
    response = requests.post(
        RD_API_URL,
        headers={"Authorization": f"Bearer {RD_API_KEY}"},
        json=lead
    )

    return jsonify({
        "status_rd": response.status_code,
        "response_rd": response.json()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
