from unittest.mock import MagicMock, patch

from app import app as flask_app


def _client(perfil):
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = perfil
    return client


def _fake_connection():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (
        '12345678909',
        'JOAO DA SILVA',
        '2000-01-01',
        '999999999',
        'RUA DAS FLORES, 1, BAIRRO CENTRO',
        None,
        None,
        False,
        'MARIA DA SILVA',
        None,
    )
    return conn


def test_admin_can_update_patient_birthdate():
    client = _client('ADMIN')
    conn = _fake_connection()

    with patch('app.conectar', return_value=conn), \
         patch('app.resolver_id_paciente', return_value='12345678909'):
        response = client.post('/paciente/12345678909/editar', data={
            'nome': 'JOAO DA SILVA',
            'nascimento': '02/03/2001',
        })

    assert response.status_code == 302
    update = next(
        call for call in conn.cursor.return_value.execute.call_args_list
        if 'UPDATE paciente SET' in call.args[0]
    )
    assert 'nascimento = %s' in update.args[0]
    assert update.args[1][-2:] == ('2001-03-02', '12345678909')


def test_only_admin_sees_editable_patient_birthdate():
    for perfil in ('ADMIN', 'OPERADOR'):
        client = _client(perfil)
        conn = _fake_connection()

        with patch('app.conectar', return_value=conn), \
             patch('app.resolver_id_paciente', return_value='12345678909'):
            response = client.get('/paciente/12345678909/editar')

        assert response.status_code == 200
        assert (b'name="nascimento"' in response.data) == (perfil == 'ADMIN')


def test_non_admin_cannot_update_patient_birthdate():
    client = _client('OPERADOR')
    conn = _fake_connection()

    with patch('app.conectar', return_value=conn), \
         patch('app.resolver_id_paciente', return_value='12345678909'):
        response = client.post('/paciente/12345678909/editar', data={
            'nome': 'JOAO DA SILVA',
            'nascimento': '02/03/2001',
        })

    assert response.status_code == 302
    update = next(
        call for call in conn.cursor.return_value.execute.call_args_list
        if 'UPDATE paciente SET' in call.args[0]
    )
    assert 'nascimento' not in update.args[0]


def test_admin_must_submit_a_valid_patient_birthdate():
    client = _client('ADMIN')
    conn = _fake_connection()

    with patch('app.conectar', return_value=conn), \
         patch('app.resolver_id_paciente', return_value='12345678909'):
        response = client.post('/paciente/12345678909/editar', data={
            'nome': 'JOAO DA SILVA',
            'nascimento': '31/02/2001',
        })

    assert response.status_code == 302
    assert not any(
        'UPDATE paciente SET' in call.args[0]
        for call in conn.cursor.return_value.execute.call_args_list
    )
    conn.commit.assert_not_called()
