import os
import psycopg
from psycopg import sql
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar():
    conn = psycopg.connect(DATABASE_URL)
    return conn

def garantir_foreign_key_solicitacao_paciente():
    conn = conectar()
    c = conn.cursor()

    c.execute(
        '''
        SELECT con.conname, pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE rel.relname = 'solicitacao'
          AND nsp.nspname = current_schema()
          AND con.contype = 'f'
          AND pg_get_constraintdef(con.oid) ILIKE 'FOREIGN KEY (paciente_id)%REFERENCES paciente(id)%'
        '''
    )
    constraints = c.fetchall()

    precisa_recriar = not constraints or any('ON UPDATE CASCADE' not in definicao.upper() for _, definicao in constraints)

    if precisa_recriar:
        for nome_constraint, _ in constraints:
            c.execute(
                sql.SQL('ALTER TABLE solicitacao DROP CONSTRAINT IF EXISTS {}').format(
                    sql.Identifier(nome_constraint)
                )
            )

        c.execute(
            '''
            ALTER TABLE solicitacao
            ADD CONSTRAINT solicitacao_paciente_id_fkey
            FOREIGN KEY (paciente_id) REFERENCES paciente(id)
            ON UPDATE CASCADE
            DEFERRABLE INITIALLY DEFERRED
            '''
        )

    conn.commit()
    conn.close()

def migrar_cpfs_com_mascara():
    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        UPDATE paciente
        SET id =
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 1 FOR 3) || '.' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 4 FOR 3) || '.' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 7 FOR 3) || '-' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 10 FOR 2)
        WHERE LENGTH(regexp_replace(COALESCE(id, ''), '\\D', '', 'g')) = 11
          AND id <>
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 1 FOR 3) || '.' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 4 FOR 3) || '.' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 7 FOR 3) || '-' ||
            SUBSTRING(regexp_replace(id, '\\D', '', 'g') FROM 10 FOR 2)
        '''
    )
    conn.commit()
    conn.close()

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
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS conclusao TEXT')
    c.execute('''CREATE TABLE IF NOT EXISTS sugestao_endereco (
        tipo TEXT NOT NULL,
        valor TEXT NOT NULL,
        UNIQUE(tipo, valor)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sugestao_solicitacao (
        tipo TEXT NOT NULL,
        valor TEXT NOT NULL,
        UNIQUE(tipo, valor)
    )''')
    conn.commit()
    conn.close()

    garantir_foreign_key_solicitacao_paciente()
    migrar_cpfs_com_mascara()

if __name__ == '__main__':
    criar_tabelas()
    print('Banco de dados e tabelas criados com sucesso!')
