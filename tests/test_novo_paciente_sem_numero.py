import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app


def test_novo_paciente_salva_endereco_com_sem_numero():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    fake_conn = MagicMock()
    fake_cursor = fake_conn.cursor.return_value
    fake_cursor.execute.return_value = None
    fake_conn.commit.return_value = None
    fake_conn.close.return_value = None

    with patch('app.conectar', return_value=fake_conn), \
         patch('app.buscar_paciente_existente_por_documentos', return_value=None), \
         patch('app.listar_sugestoes_endereco', side_effect=lambda tipo: []), \
         patch('app.apenas_admin', return_value=True):
        response = client.post('/novo_paciente', data={
            'cpf': '12345678909',
            'sus': '123456789012345',
            'nome': 'JOAO DA SILVA',
            'nome_mae': 'MARIA DA SILVA',
            'nascimento': '01/01/2000',
            'telefone': '999999999',
            'rua': 'RUA DAS FLORES',
            'numero': '',
            'bairro': 'CENTRO',
            'sem_numero': 'on',
        }, follow_redirects=False)

    assert response.status_code == 302
    insert_args = fake_cursor.execute.call_args_list[0].args
    assert insert_args[1][4] == 'RUA DAS FLORES, S/N, BAIRRO CENTRO'
