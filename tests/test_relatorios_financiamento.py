import app as app_module


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.current_query = ''

    def execute(self, query, params=None):
        self.queries.append(query)
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
