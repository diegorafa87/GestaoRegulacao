import os
import psycopg
from psycopg import sql
from datetime import datetime
from dotenv import load_dotenv
from flask import g, has_app_context

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

try:
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover
    ConnectionPool = None

_pool = None


class _ConexaoPool:
    """Devolve a conexão ao pool em close(), mantendo a API do psycopg."""

    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        if has_app_context():
            if not hasattr(g, 'conexoes_db_pendentes'):
                g.conexoes_db_pendentes = set()
            g.conexoes_db_pendentes.add(self)

    def __getattr__(self, nome):
        return getattr(self._conn, nome)

    def close(self):
        conn, self._conn = self._conn, None
        if conn is None:
            return
        if has_app_context():
            getattr(g, 'conexoes_db_pendentes', set()).discard(self)
        try:
            if not conn.closed:
                conn.rollback()
        except Exception:
            pass
        self._pool.putconn(conn)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

def devolver_conexoes_pendentes(exception=None):
    if not has_app_context():
        return
    conexoes = g.pop('conexoes_db_pendentes', set())
    for conn in conexoes:
        conn.close()


def conectar():
    global _pool
    if ConnectionPool is None:
        return psycopg.connect(DATABASE_URL)
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=int(os.environ.get('DB_POOL_MAX', '6')),
            kwargs={
                'connect_timeout': 10,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 3,
            },
            check=ConnectionPool.check_connection,
            max_idle=60,
            max_lifetime=900,
            timeout=15,
            open=True,
        )
    return _ConexaoPool(_pool, _pool.getconn())

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
    c.execute('ALTER TABLE usuario ADD COLUMN IF NOT EXISTS especialidades_permitidas TEXT')
    c.execute('''CREATE TABLE IF NOT EXISTS paciente (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        nascimento TEXT NOT NULL,
        telefone TEXT,
        endereco TEXT,
        sus TEXT,
        data_obito TEXT,
        oncologico BOOLEAN DEFAULT FALSE,
        nome_mae TEXT,
        telefone2 TEXT
    )''')
    c.execute('ALTER TABLE paciente ADD COLUMN IF NOT EXISTS sus TEXT')
    c.execute('ALTER TABLE paciente ADD COLUMN IF NOT EXISTS nome_mae TEXT')
    c.execute('ALTER TABLE paciente ADD COLUMN IF NOT EXISTS telefone2 TEXT')
    c.execute('ALTER TABLE paciente ADD COLUMN IF NOT EXISTS data_obito TEXT')
    c.execute('ALTER TABLE paciente ADD COLUMN IF NOT EXISTS oncologico BOOLEAN DEFAULT FALSE')
    c.execute('''CREATE TABLE IF NOT EXISTS solicitacao (
        id SERIAL PRIMARY KEY,
        paciente_id TEXT NOT NULL,
        data_solicitacao TEXT,
        data_entrada TEXT,
        data_insercao TEXT,
        data_realizacao TEXT,
        data_retorno TEXT,
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
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS data_retorno TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS conclusao TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS financiamento TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS cid TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS resumo_clinico TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS profissional_solicitante TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS ocupacao TEXT')
    c.execute('ALTER TABLE solicitacao ADD COLUMN IF NOT EXISTS unidade_solicitante TEXT')
    c.execute('''CREATE TABLE IF NOT EXISTS sugestao_endereco (
        tipo TEXT NOT NULL,
        valor TEXT NOT NULL,
        UNIQUE(tipo, valor)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sugestao_solicitacao (
        tipo TEXT NOT NULL,
        valor TEXT NOT NULL,
        categoria TEXT,
        UNIQUE(tipo, valor)
    )''')
    c.execute('ALTER TABLE sugestao_solicitacao ADD COLUMN IF NOT EXISTS categoria TEXT')
    c.execute('CREATE INDEX IF NOT EXISTS idx_solicitacao_paciente_entrada ON solicitacao (paciente_id, data_entrada DESC)')
    conn.commit()
    conn.close()

    garantir_foreign_key_solicitacao_paciente()
    migrar_cpfs_com_mascara()

if __name__ == '__main__':
    criar_tabelas()
    print('Banco de dados e tabelas criados com sucesso!')
