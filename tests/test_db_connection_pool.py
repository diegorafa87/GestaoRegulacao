from unittest.mock import MagicMock

from app import app as flask_app
from db import _ConexaoPool


def test_conexao_nao_devolvida_e_liberada_ao_encerrar_contexto():
    pool = MagicMock()
    conn = MagicMock()
    conn.closed = False

    try:
        with flask_app.app_context():
            _ConexaoPool(pool, conn)
            raise RuntimeError('falha simulada na requisição')
    except RuntimeError:
        pass

    conn.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


def test_conexao_devolvida_manualmente_nao_e_liberada_duas_vezes():
    pool = MagicMock()
    conn = MagicMock()
    conn.closed = False

    with flask_app.app_context():
        conexao = _ConexaoPool(pool, conn)
        conexao.close()

    conn.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(conn)
