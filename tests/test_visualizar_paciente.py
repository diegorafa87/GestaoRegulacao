from unittest.mock import MagicMock, patch

from app import app as flask_app, calcular_idade


PACIENTE = (
    '12345678909',
    'JOAO DA SILVA',
    '2000-01-01',
    'MASCULINO',
    '999999999',
    '888888888',
    '123456789012345',
    'RUA DAS FLORES, 1, BAIRRO CENTRO',
    'MARIA DA SILVA',
    'JOSE DA SILVA',
    True,
    True,
    False,
    None,
)


def _client(perfil='ADMIN'):
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['usuario_perfil'] = perfil
    return client


def test_visualizar_paciente_exibe_ficha_sem_campos_de_formulario():
    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = PACIENTE

    with patch('app.conectar', return_value=connection), \
         patch('app.resolver_id_paciente', return_value=PACIENTE[0]):
        response = _client().get('/paciente/12345678909/visualizar')

    assert response.status_code == 200
    html = response.data.decode()
    card_inicio = html.index('<div class="card shadow-sm mb-4">')
    assert html.index('JOAO DA SILVA', card_inicio) < html.index('Dados pessoais', card_inicio)
    assert calcular_idade(PACIENTE[2]) in html[card_inicio:]
    for valor in (
        'Ficha do Paciente',
        'JOAO DA SILVA',
        'MASCULINO',
        '999999999',
        '888888888',
        'MARIA DA SILVA',
        'JOSE DA SILVA',
        'RUA DAS FLORES, 1, BAIRRO CENTRO',
        'Paciente oncológico',
        'Hipertensão',
    ):
        assert valor.encode() in response.data
    assert b'<input' not in response.data
    assert b'Editar paciente' in response.data


def test_perfil_setor_pode_visualizar_ficha_sem_opcao_de_edicao():
    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = PACIENTE

    with patch('app.conectar', return_value=connection), \
         patch('app.resolver_id_paciente', return_value=PACIENTE[0]):
        response = _client('SETOR').get('/paciente/12345678909/visualizar')

    assert response.status_code == 200
    assert b'Ficha do Paciente' in response.data
    assert b'Editar paciente' not in response.data


def test_lista_de_pacientes_tem_acoes_de_visualizar_e_editar():
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = [(
        *PACIENTE[:3],
        PACIENTE[4],
        PACIENTE[7],
        None,
        None,
        PACIENTE[10],
    )]

    with patch('app.conectar', return_value=connection):
        response = _client().get('/pacientes')

    assert response.status_code == 200
    assert b'aria-label="Visualizar paciente"' in response.data
    assert b'aria-label="Editar paciente"' in response.data
    assert b'/paciente/12345678909/visualizar' in response.data
    assert b'/paciente/12345678909/editar' in response.data
