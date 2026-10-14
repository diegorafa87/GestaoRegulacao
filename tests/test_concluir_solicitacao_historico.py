from unittest.mock import MagicMock, patch

from app import app as flask_app


def test_concluir_solicitacao_usa_id_do_paciente_sem_abrir_outra_conexao():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    fake_conn = MagicMock()
    fake_cursor = fake_conn.cursor.return_value
    fake_cursor.fetchone.side_effect = [
        ('12345678909', None),
        ('12345678909', '2026-10-01', 'CONSULTA', 'CARDIOLOGIA'),
        None,
    ]

    with patch('app.conectar', return_value=fake_conn) as conectar, \
         patch('app.resolver_id_paciente', side_effect=AssertionError('não deveria consultar novamente')):
        response = client.post('/solicitacao/42/editar', data={
            'data_realizacao': '14/10/2026',
            'unidade_realizadora': 'HOSPITAL MUNICIPAL',
            'financiamento': 'SUS',
            'conclusao': 'PRESENTE',
        }, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/paciente/12345678909')
    conectar.assert_called_once()
    fake_conn.commit.assert_called_once()
    fake_conn.close.assert_called_once()
