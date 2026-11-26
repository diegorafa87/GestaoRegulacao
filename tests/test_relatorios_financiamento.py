import app as app_module


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.executions = []
        self.current_query = ''

    def execute(self, query, params=None):
        self.queries.append(query)
        self.executions.append((query, params))
        self.current_query = query

    def fetchall(self):
        return []


class FakeCursorComSolicitacoes(FakeCursor):
    def fetchall(self):
        if 'AS financiamento' in self.current_query:
            return [('CARDIOLOGIA', '2026-09-10', 'ANA EXEMPLO', 'CONSULTA', '')]
        if 'AS paciente_id' in self.current_query:
            return [(
                9001,
                '12345678901',
                'ANA EXEMPLO',
                'CONSULTA',
                'CARDIOLOGIA',
                '2026-09-10',
                'PRESENTE',
                None,
            )]
        return []


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor

    def close(self):
        pass


class FakeConnectionComSolicitacoes(FakeConnection):
    def __init__(self):
        self.fake_cursor = FakeCursorComSolicitacoes()


def _consultar_relatorios(monkeypatch, query_string):
    connection = FakeConnection()
    monkeypatch.setattr(app_module, 'conectar', lambda: connection)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['usuario_id'] = 1

    response = client.get(f'/relatorios?{query_string}')
    assert response.status_code == 200
    return connection.fake_cursor.queries


def test_relatorios_realizados_com_financiamento_nao_inclui_retirados(monkeypatch):
    queries = _consultar_relatorios(monkeypatch, 'situacao=REALIZADOS&financiamento=SUS')

    queries_com_realizacao = [
        query for query in queries
        if 'data_realizacao IS NOT NULL' in query
    ]
    assert queries_com_realizacao
    assert all(
        "UPPER(COALESCE(s.conclusao, '')) <> 'RETIRADO'" in query
        for query in queries_com_realizacao
    )


def test_relatorios_retirados_continua_exibindo_retirados(monkeypatch):
    queries = _consultar_relatorios(monkeypatch, 'situacao=RETIRADOS&financiamento=SUS')

    query_resumo = next(query for query in queries if 'COUNT(*) AS total_registros' in query)
    assert "UPPER(COALESCE(s.conclusao, '')) = 'RETIRADO'" in query_resumo
    assert "UPPER(COALESCE(s.conclusao, '')) <> 'RETIRADO'" not in query_resumo


def test_relatorios_filtra_especialidade_por_sexo(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(app_module, 'conectar', lambda: connection)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['usuario_id'] = 1

    response = client.get('/relatorios?especialidade=Cardiologia&sexo=FEMININO')

    assert response.status_code == 200
    assert b'value="FEMININO" selected' in response.data
    query_resumo, params_resumo = next(
        execution for execution in connection.fake_cursor.executions
        if 'COUNT(*) AS total_registros' in execution[0]
    )
    assert 'LEFT JOIN paciente p ON p.id = s.paciente_id' in query_resumo
    assert "UPPER(COALESCE(p.sexo, '')) = %s" in query_resumo
    assert 'FEMININO' in params_resumo

    query_pacientes, params_pacientes = next(
        execution for execution in connection.fake_cursor.executions
        if 'COUNT(s.id) AS total_solicitacoes' in execution[0]
    )
    assert "UPPER(COALESCE(p.sexo, '')) = %s" in query_pacientes
    assert 'FEMININO' in params_pacientes


def test_filtro_sexo_na_visao_tempo_de_espera_mantem_parametros(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(app_module, 'conectar', lambda: connection)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['usuario_id'] = 1

    response = client.get(
        '/relatorios?view=especialidades_maior_espera&especialidade=Cardiologia&sexo=MASCULINO'
    )

    assert response.status_code == 200
    query_espera, params_espera = next(
        execution for execution in connection.fake_cursor.executions
        if 'AVG(DATE(s.data_realizacao)' in execution[0]
    )
    assert "UPPER(COALESCE(p.sexo, '')) = %s" in query_espera
    assert query_espera.count('%s') == len(params_espera)
    assert 'MASCULINO' in params_espera


def test_grafico_nao_informado_abre_lista_com_acao_de_correcao(monkeypatch):
    connection = FakeConnectionComSolicitacoes()
    monkeypatch.setattr(app_module, 'conectar', lambda: connection)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session['usuario_id'] = 1

    resposta_resumo = client.get('/relatorios')
    assert resposta_resumo.status_code == 200
    assert 'view=financiamento_nao_informado' in resposta_resumo.get_data(as_text=True)

    resposta_lista = client.get(
        '/relatorios?view=financiamento_nao_informado&situacao=REALIZADOS'
    )
    conteudo_lista = resposta_lista.get_data(as_text=True)
    assert resposta_lista.status_code == 200
    assert 'ANA EXEMPLO' in conteudo_lista
    assert '/solicitacao/9001/editar?next=' in conteudo_lista
    assert 'Corrigir' in conteudo_lista

    query_lista = next(query for query in connection.fake_cursor.queries if 'AS paciente_id' in query)
    assert "UPPER(COALESCE(s.financiamento, '')) NOT IN ('SUS', 'CONVENIO')" in query_lista
    assert "UPPER(COALESCE(s.conclusao, '')) <> 'RETIRADO'" in query_lista
