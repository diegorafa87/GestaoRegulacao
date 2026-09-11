from app import gerar_relatorio_procedimentos_sintetico, gerar_relatorio_procedimentos_detalhado, listar_tipos_relatorio


def test_listar_tipos_relatorio_inclui_cirurgia():
    assert listar_tipos_relatorio() == ['TODOS', 'CONSULTA', 'EXAME', 'CIRURGIA']


def test_gerar_relatorio_procedimentos_sintetico_agrupa_por_principio_sem_nomes_pacientes():
    solicitacoes = [
        {'paciente_nome': 'Ana', 'procedimento': 'ULTRASSONOGRAFIA TRANSVAGINAL'},
        {'paciente_nome': 'Bia', 'procedimento': 'ULTRASSONOGRAFIA MAMARIA'},
        {'paciente_nome': 'Carlos', 'procedimento': 'RESSONANCIA NUCAL'},
        {'paciente_nome': 'Duda', 'procedimento': 'RADIOGRAFIA DE COLUNA'},
    ]

    resultado = gerar_relatorio_procedimentos_sintetico(solicitacoes)

    assert resultado == [
        'ULTRASSONOGRAFIAS (2)',
        'RESSONANCIAS (1)',
        'RADIOGRAFIAS (1)',
    ]
    assert all('Ana' not in item and 'Bia' not in item for item in resultado)


def test_gerar_relatorio_procedimentos_detalhado_inclui_procedimentos_e_pacientes():
    solicitacoes = [
        {'paciente_nome': 'Ana', 'procedimento': 'ULTRASSONOGRAFIA TRANSVAGINAL'},
        {'paciente_nome': 'Bia', 'procedimento': 'RESSONANCIA NUCAL'},
    ]

    resultado = gerar_relatorio_procedimentos_detalhado(solicitacoes, incluir_pacientes=True)

    assert resultado[0].startswith('ULTRASSONOGRAFIA TRANSVAGINAL')
    assert 'Ana' in resultado[0]
    assert resultado[1].startswith('RESSONANCIA NUCAL')
    assert 'Bia' in resultado[1]


def test_gerar_relatorio_procedimentos_detalhado_sem_pacientes_para_relatorio_geral():
    solicitacoes = [
        {'paciente_nome': 'Ana', 'procedimento': 'ULTRASSONOGRAFIA TRANSVAGINAL'},
        {'paciente_nome': 'Bia', 'procedimento': 'RESSONANCIA NUCAL'},
    ]

    resultado = gerar_relatorio_procedimentos_detalhado(solicitacoes, incluir_pacientes=False)

    assert resultado == [
        'ULTRASSONOGRAFIA TRANSVAGINAL',
        'RESSONANCIA NUCAL',
    ]


def test_gerar_relatorio_procedimentos_sintetico_usa_tipo_e_especialidade_para_consultas_e_exames():
    solicitacoes = [
        {'paciente_nome': 'Ana', 'procedimento': 'ORTOPEDIA', 'tipo': 'CONSULTA'},
        {'paciente_nome': 'Bia', 'procedimento': 'CIRURGIA GERAL', 'tipo': 'CONSULTA'},
        {'paciente_nome': 'Carlos', 'procedimento': 'LABORATORIAL', 'tipo': 'EXAME'},
    ]

    resultado = gerar_relatorio_procedimentos_sintetico(solicitacoes)

    assert resultado == [
        'CONSULTA EM ORTOPEDIA (1)',
        'CONSULTA EM CIRURGIA GERAL (1)',
        'EXAMES LABORATORIAIS (1)',
    ]
