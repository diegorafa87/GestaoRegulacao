from unittest.mock import MagicMock, patch

from app import app as flask_app


def _client(perfil='ADMIN', usuario_id=1):
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = usuario_id
        sess['usuario_perfil'] = perfil
    return client


def test_admin_can_render_user_edit_form():
    client = _client()
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (
        2, 'Operador', 'operador', 'OPERADOR', True, None,
    )

    with patch('app.conectar', return_value=conn), \
         patch('app.listar_especialidades', return_value=['CARDIOLOGIA']):
        response = client.get('/usuarios/2/editar')

    assert response.status_code == 200
    assert b'operador' in response.data
    assert b'Nova senha' in response.data


def test_admin_can_update_user_without_changing_password():
    client = _client()
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [
        (2, 'OPERADOR', True),
        None,
    ]

    with patch('app.conectar', return_value=conn):
        response = client.post('/usuarios/2/editar', data={
            'nome': 'Novo Nome',
            'username': 'novo_usuario',
            'perfil': 'OPERADOR',
            'ativo': 'on',
        })

    assert response.status_code == 302
    updates = [
        call for call in conn.cursor.return_value.execute.call_args_list
        if 'UPDATE usuario' in call.args[0]
    ]
    assert len(updates) == 1
    assert 'senha_hash' not in updates[0].args[0]
    assert updates[0].args[1] == (
        'Novo Nome', 'novo_usuario', 'OPERADOR', True, None, 2,
    )
    conn.commit.assert_called_once()


def test_admin_cannot_delete_own_account():
    client = _client()

    with patch('app.conectar') as conectar:
        response = client.post('/usuarios/1/excluir')

    assert response.status_code == 302
    conectar.assert_not_called()


def test_admin_cannot_delete_last_active_administrator():
    client = _client()
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [
        (2, 'ADMIN', True),
        None,
    ]

    with patch('app.conectar', return_value=conn):
        response = client.post('/usuarios/2/excluir')

    assert response.status_code == 302
    assert not any(
        'DELETE FROM usuario' in call.args[0]
        for call in conn.cursor.return_value.execute.call_args_list
    )
    conn.commit.assert_not_called()


def test_admin_can_delete_another_non_admin_user():
    client = _client()
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (2, 'OPERADOR', True)

    with patch('app.conectar', return_value=conn):
        response = client.post('/usuarios/2/excluir')

    assert response.status_code == 302
    assert any(
        'DELETE FROM usuario WHERE id = %s' in call.args[0]
        for call in conn.cursor.return_value.execute.call_args_list
    )
    conn.commit.assert_called_once()
