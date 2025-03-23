from flask import Flask, request, jsonify
from flask_cors import CORS  # Importa o CORS
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

# Flask server
app = Flask(__name__)

# Ativa o CORS para permitir acesso de qualquer origem (apenas para desenvolvimento)
CORS(app)

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
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
