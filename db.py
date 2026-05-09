import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuario (
        id SERIAL PRIMARY KEY,
        nome TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL DEFAULT 'OPERADOR',
        ativo BOOLEAN NOT NULL DEFAULT TRUE,
        criado_em TIMESTAMP NOT NULL DEFAULT NOW()
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS paciente (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        nascimento TEXT NOT NULL,
        telefone TEXT,
        endereco TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS solicitacao (
        id SERIAL PRIMARY KEY,
        paciente_id TEXT NOT NULL,
        data_solicitacao TEXT,
        data_entrada TEXT,
        data_insercao TEXT,
        data_realizacao TEXT,
        unidade_realizadora TEXT,
        tipo TEXT,
        especialidade TEXT,
        descricao TEXT,
        prioridade TEXT,
        encaminhamento TEXT,
        status TEXT,
        sistema_insercao TEXT,
        FOREIGN KEY(paciente_id) REFERENCES paciente(id)
    )''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    criar_tabelas()
    print('Banco de dados e tabelas criados com sucesso!')
