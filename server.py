from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import logging
import os

# Configuração de logging
logging.basicConfig(
    filename="erros.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

CSV_PATH = 'permitidos.csv'

# Função para obter IP do usuário
def obter_ip():
    return request.remote_addr

# Função para verificar acesso
def verificar_acesso(email, cpf=None, id_venda=None):
    try:
        permitidos = []
        with open(CSV_PATH, mode='r', encoding='utf-8') as file:
            leitor_csv = csv.DictReader(file)
            for linha in leitor_csv:
                permitidos.append(linha['Email'])

        if email not in permitidos:
            return False, "E-mail não permitido."

        try:
            with open('controledeacesso.txt', mode='r', encoding='utf-8') as file:
                controle = [line.strip().split() for line in file]
        except FileNotFoundError:
            controle = []

        ip = obter_ip()

        for registro in controle:
            if registro[0] == email:
                if registro[1] == ip:
                    return True, "Acesso concedido."
                else:
                    if cpf and id_venda:
                        with open('controledeacesso.txt', mode='a', encoding='utf-8') as file:
                            file.write(f"{email} {ip} {cpf} {id_venda}\n")
                        return True, "Tentativa registrada, acesso concedido."
                    else:
                        return False, "CPF e ID da venda são necessários."

        with open('controledeacesso.txt', mode='a', encoding='utf-8') as file:
            file.write(f"{email} {ip}\n")

        return True, "Acesso concedido e registrado."
    except Exception as e:
        return False, f"Erro interno no servidor: {str(e)}"

@app.route('/login', methods=['POST'])
def login():
    dados = request.get_json()
    email = dados.get('email')
    cpf = dados.get('cpf')
    id_venda = dados.get('id_venda')

    print(f"Recebido: email={email}, cpf={cpf}, id_venda={id_venda}")

    sucesso, mensagem = verificar_acesso(email, cpf, id_venda)
    if sucesso:
        return jsonify({"message": mensagem})
    else:
        print(f"Erro: {mensagem}")
        return jsonify({"error": mensagem}), 403

# Verificação de links
def verificar_link(link):
    try:
        resposta = requests.get(link, timeout=10)
        if resposta.status_code == 200:
            sopa = BeautifulSoup(resposta.content, 'html.parser')
            nome_grupo = sopa.find('meta', {'property': 'og:title'})
            nome_grupo = nome_grupo['content'] if nome_grupo else "Sem Categoria"
            return nome_grupo, link
        else:
            return None, link
    except Exception as e:
        logging.error(f"Erro ao verificar o link {link}: {e}")
        return None, link

@app.route('/verificar', methods=['POST'])
def verificar_links_via_http():
    dados = request.get_json()
    lista_links = dados.get('links', [])
    if not lista_links:
        return jsonify({"error": "Nenhum link fornecido"}), 400

    categorias = {}
    with ThreadPoolExecutor() as executor:
        resultados = list(executor.map(verificar_link, lista_links))

    for nome_grupo, link in resultados:
        if nome_grupo:
            if nome_grupo not in categorias:
                categorias[nome_grupo] = []
            categorias[nome_grupo].append(link)

    return jsonify(categorias)

# Atualiza permitidos.csv com todos os dados do comprador
def atualizar_permitidos(dados):
    caminho_csv = CSV_PATH
    campos = ['Email', 'Nome', 'CPF', 'ID da Venda', 'Valor', 'Data']

    arquivo_existe = os.path.exists(caminho_csv)
    email = dados.get('email', '')

    # Verifica se o email já está registrado
    emails_existentes = set()
    if arquivo_existe:
        with open(caminho_csv, mode='r', encoding='utf-8') as file:
            leitor = csv.DictReader(file)
            for linha in leitor:
                emails_existentes.add(linha['Email'])

    if email not in emails_existentes:
        with open(caminho_csv, mode='a', encoding='utf-8', newline='') as file:
            escritor = csv.DictWriter(file, fieldnames=campos)
            if not arquivo_existe:
                escritor.writeheader()
            escritor.writerow({
                'Email': email,
                'Nome': dados.get('nome', ''),
                'CPF': dados.get('cpf', ''),
                'ID da Venda': dados.get('id_venda', ''),
                'Valor': dados.get('valor', ''),
                'Data': dados.get('data', '')
            })

@app.route('/webhook/cakto', methods=['POST'])
def webhook_cakto():
    try:
        dados = request.get_json()
        print("Payload recebido:", dados)  # 👈 Adicione isso

        if dados.get('status', '').lower() == 'paid':
            atualizar_permitidos(dados)
            return jsonify({"message": "Dados do comprador registrados com sucesso."}), 200
        else:
            return jsonify({"error": "Venda não está paga ou dados incompletos."}), 400
    except Exception as e:
        logging.error(f"Erro no Webhook: {str(e)}")
        return jsonify({"error": "Erro interno no servidor."}), 500

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)

