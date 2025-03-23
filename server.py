from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import logging

# Configuração de logging para salvar erros
logging.basicConfig(
    filename="erros.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = Flask(__name__)

# Configuração do CORS para permitir acesso de qualquer origem
CORS(app, resources={r"/*": {"origins": "*"}})

# Função para obter o IP do usuário
def obter_ip():
    return request.remote_addr

# Função para verificar acesso
def verificar_acesso(email, cpf=None, id_venda=None):
    try:
        # Lista de e-mails permitidos
        permitidos = []
        with open('permitidos.csv', mode='r', encoding='utf-8') as file:
            leitor_csv = csv.DictReader(file)  # Lê o CSV como dicionário
            for linha in leitor_csv:
                # Filtrar vendas com "Status da Venda = paid"
                if linha['Status da Venda'].strip().lower() == 'paid':
                    permitidos.append(linha['Email do Cliente'].strip())

        # Verificar se o e-mail está na lista permitida
        if email not in permitidos:
            return False, "E-mail não permitido."

        # Ler controledeacesso.txt para verificar tentativas anteriores
        try:
            with open('controledeacesso.txt', mode='r', encoding='utf-8') as file:
                controle = [line.strip().split() for line in file]
        except FileNotFoundError:
            controle = []

        ip = obter_ip()

        # Verificar condições de acesso
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

        # Registrar novo acesso
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

    # Depurar a leitura do CSV para garantir e-mails válidos
    try:
        permitidos = []
        with open('permitidos.csv', mode='r', encoding='utf-8') as file:
            leitor_csv = csv.DictReader(file)
            for linha in leitor_csv:
                if linha['Status da Venda'].strip().lower() == 'paid':
                    permitidos.append(linha['Email do Cliente'].strip())
        print(f"E-mails permitidos: {permitidos}")
    except Exception as e:
        print(f"Erro ao ler o arquivo CSV: {str(e)}")

    # Verificar acesso
    sucesso, mensagem = verificar_acesso(email, cpf, id_venda)
    if sucesso:
        return jsonify({"message": mensagem})
    else:
        print(f"Erro: {mensagem}")
        return jsonify({"error": mensagem}), 403

# Função que verifica se o link é válido
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

# Rota Flask para verificar os links via HTTP
@app.route('/verificar', methods=['POST'])
def verificar_links_via_http():
    dados = request.get_json()  # Recebe os dados em formato JSON
    lista_links = dados.get('links', [])
    if not lista_links:
        return jsonify({"error": "Nenhum link fornecido"}), 400

    categorias = {}

    # Usar ThreadPoolExecutor para paralelizar as verificações
    with ThreadPoolExecutor() as executor:
        resultados = list(executor.map(verificar_link, lista_links))

    # Organizar os links por categorias
    for nome_grupo, link in resultados:
        if nome_grupo:
            if nome_grupo not in categorias:
                categorias[nome_grupo] = []
            categorias[nome_grupo].append(link)

    return jsonify(categorias)

# Rodando o Flask server
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
