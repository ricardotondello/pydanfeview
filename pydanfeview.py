# - coding: utf-8 --
import json
import logging
import os
import threading
import time
import requests
import glob
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from logging.handlers import RotatingFileHandler
from nfelib.v4_00 import leiauteNFe_sub as parser


FLASK_PORT = 5012
FLASK_SERVER = '0.0.0.0'
PASTA_XML = './'
log_name = 'app.log'
app = Flask(__name__)


class ArquivoXml:
    def __init__(self):
        self.xml_file = ''
        self.NF = ''
        self.serie = ''
        self.data_emissao = ''
        self.operacao = ''
        self.razao_social = ''
        self.CNPJ_CPF = ''
        self.total = ''
        self.chave = ''
        self.xml_valido = False


    def load_data_from_xml(self, xml):
        try:
            # vamos importar o XML da nota e transforma-lo em objeto Python:
            nota = parser.parse(xml)
            self.xml_valido = nota.infNFe is not None
            if not self.xml_valido:
                return

            self.xml_file = xml
            self.NF = str(nota.infNFe.ide.nNF)
            self.serie = str(nota.infNFe.ide.serie)
            self.data_emissao = str(nota.infNFe.ide.dhEmi).replace('T', '')
            self.operacao = str(nota.infNFe.ide.natOp).upper()
            self.razao_social = str(nota.infNFe.emit.xNome).upper()
            self.CNPJ_CPF = f'{nota.infNFe.emit.CNPJ}{nota.infNFe.emit.CPF}'
            self.total = str(nota.infNFe.total.ICMSTot.vNF)
            self.chave = str(nota.infNFe.Id[3:])

        except Exception as e:
            logger.error(f'Erro ao ler arquivo xml ({xml}): {e}')


def montar_lista_xmls():
    xml_files = glob.glob(f'{PASTA_XML}/**/*.xml', recursive=True)
    arquivos = []

    try:
        for file in xml_files:
            arquivo = ArquivoXml()
            arquivo.load_data_from_xml(file)
            if arquivo.xml_valido:
                arquivos.append(arquivo)

    except Exception as e:
        logger.error(f'Erro ao ler arquivo xml: {e}')


def validar_file(ps_file):
    if not ps_file:
        return False
    return os.path.isfile(ps_file) and os.access(ps_file, os.R_OK)


@app.before_first_request
def activate_job():
    def run_job_xml():
        while True:
            logger.info("buscando xmls...")
            montar_lista_xmls()
            time.sleep(3600)

    thread_xml = threading.Thread(target=run_job_xml)
    thread_xml.start()


def start_runner():
    def start_loop():
        not_started = True
        while not_started:
            logger.info('Starting server...')
            try:
                r = requests.get(f'http://127.0.0.1:{FLASK_PORT}/hl')
                if r.status_code == 200:
                    not_started = False
                logger.info(r.status_code)
            except Exception as e:
                logger.error(f'Error during start server: {e}')
            time.sleep(2)

    logger.info('Server ON')
    thread = threading.Thread(target=start_loop)
    thread.start()


@app.route("/hl")
def hello():
    return "Hello World!"


def ler_config():
    global FLASK_PORT
    global FLASK_SERVER
    global PASTA_XML

    path = str(Path().absolute()) + '\\settings.json'

    if not validar_file(path):
        return

    config = json.load(open(path))
    FLASK_PORT = int(config.get('FLASK_PORT', 5012))
    FLASK_SERVER = int(config.get('FLASK_SERVER', '0.0.0.0'))
    PASTA_XML = int(config.get('PASTA_XML', './'))


@app.route('/')
def main():
    return render_template('main.html')


if __name__ == "__main__":
    # create logger
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    handler = RotatingFileHandler(log_name, maxBytes=1000000, backupCount=3)
    handler.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # add formatter to handler
    handler.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(handler)
    ler_config()
    start_runner()
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.secret_key = os.urandom(12)
    app.run(host=FLASK_SERVER, port=FLASK_PORT)

