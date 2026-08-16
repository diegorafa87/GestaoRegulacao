import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import app as flask_app, listar_cids_sugestoes


def test_nova_solicitacao_template_has_cid_field():
    template = Path('templates/nova_solicitacao.html').read_text(encoding='utf-8')

    assert 'name="cid"' not in template
    assert 'CID:' not in template
    assert 'id="cid-sugestoes"' not in template
    assert 'placeholder="Digite um CID ou palavra-chave"' not in template


def test_nova_solicitacao_template_has_resumo_clinico_field():
    template = Path('templates/nova_solicitacao.html').read_text(encoding='utf-8')

    assert 'name="resumo_clinico"' in template
    assert 'Resumo Clínico:' in template
    assert 'placeholder="Descreva o resumo clínico da requisição"' in template


def test_nova_solicitacao_page_does_not_load_full_cid_catalog():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    with patch('app.listar_cids_sugestoes', side_effect=AssertionError('CID catalog should not be loaded during page render')):
        response = client.get('/nova_solicitacao')

    assert response.status_code == 200


def test_cids_sugestoes_endpoint_is_available_without_login():
    client = flask_app.test_client()

    response = client.get('/cid_sugestoes?query=S09&limit=5')

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload


def test_cids_sugestoes_endpoint_filters_by_query():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    response = client.get('/cid_sugestoes?query=R00&limit=5')

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload
    assert payload[0][0].startswith('R00')


def test_cids_sugestoes_endpoint_returns_broader_prefixes_when_query_is_empty():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    response = client.get('/cid_sugestoes?limit=40')

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload
    assert any(not item[0].startswith('A') for item in payload)


def test_cids_sugestoes_endpoint_matches_partial_code_like_s09():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    response = client.get('/cid_sugestoes?query=S09&limit=10')

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert payload
    assert any(item[0].startswith('S09') for item in payload)


def test_listar_cids_sugestoes_loads_entries_from_local_csv(tmp_path):
    csv_path = tmp_path / 'cid10.csv'
    csv_path.write_text('codigo;descricao\nR10.0;Dor abdominal\nS09.0;Lesão do pescoço\n', encoding='utf-8')

    with patch.dict(os.environ, {'CID10_CSV_PATH': str(csv_path)}, clear=False):
        with patch('app.icd10', None):
            sugestoes = listar_cids_sugestoes(query='S09', limit=5)

    assert sugestoes
    assert ('S09.0', 'LESÃO DO PESCOÇO') in sugestoes


def test_listar_cids_sugestoes_loads_entries_from_zip(tmp_path):
    csv_path = tmp_path / 'cid10.csv'
    csv_path.write_text('codigo;descricao\nR10.0;Dor abdominal\nS09.0;Lesão do pescoço\n', encoding='utf-8')

    zip_path = tmp_path / 'cid10.zip'
    with zipfile.ZipFile(zip_path, 'w') as archive:
        archive.write(csv_path, arcname='cid10.csv')

    with patch.dict(os.environ, {'CID10_ZIP_PATH': str(zip_path)}, clear=False):
        with patch('app.icd10', None):
            sugestoes = listar_cids_sugestoes(query='S09', limit=5)

    assert sugestoes
    assert ('S09.0', 'LESÃO DO PESCOÇO') in sugestoes


def test_listar_cids_sugestoes_loads_entries_from_zip_with_cid10csv_name(tmp_path):
    csv_path = tmp_path / 'cid10.csv'
    csv_path.write_text('codigo;descricao\nR10.0;Dor abdominal\nS09.0;Lesão do pescoço\n', encoding='utf-8')

    zip_path = tmp_path / 'CID10CSV.zip'
    with zipfile.ZipFile(zip_path, 'w') as archive:
        archive.write(csv_path, arcname='cid10.csv')

    with patch.dict(os.environ, {}, clear=False):
        with patch('app.icd10', None):
            with patch('app.app.root_path', str(tmp_path)):
                sugestoes = listar_cids_sugestoes(query='S09', limit=5)

    assert sugestoes
    assert ('S09.0', 'LESÃO DO PESCOÇO') in sugestoes


def test_listar_cids_sugestoes_loads_entries_from_latin1_zip(tmp_path):
    csv_path = tmp_path / 'cid10.csv'
    csv_path.write_bytes('codigo;descricao\nR10.0;Dor abdominal\nS09.0;Lesão do pescoço\n'.encode('latin-1'))

    zip_path = tmp_path / 'cid10.zip'
    with zipfile.ZipFile(zip_path, 'w') as archive:
        archive.write(csv_path, arcname='cid10.csv')

    with patch.dict(os.environ, {'CID10_ZIP_PATH': str(zip_path)}, clear=False):
        with patch('app.icd10', None):
            sugestoes = listar_cids_sugestoes(query='R', limit=5)

    assert sugestoes
    assert ('R10.0', 'DOR ABDOMINAL') in sugestoes


def test_listar_cids_sugestoes_diversifies_prefixes_when_query_is_empty():
    with patch('app.carregar_catalogo_cid10', return_value=[
        ('A00', 'COLERA'),
        ('A01', 'FEBRE TIFOIDE'),
        ('A02', 'OUTRAS INFECCOES'),
        ('A03', 'SHIGUELOSE'),
        ('B00', 'HERPES'),
        ('B01', 'VARICELA'),
        ('C00', 'NEOPLASIA'),
    ]):
        sugestoes = listar_cids_sugestoes(query='', limit=6)

    codigos = [codigo for codigo, _ in sugestoes]
    assert 'B00' in codigos
    assert 'C00' in codigos


def test_listar_cids_sugestoes_for_single_letter_query_prioritizes_code_prefix():
    with patch('app.carregar_catalogo_cid10', return_value=[
        ('A00', 'COLERA'),
        ('R10.0', 'DOR ABDOMINAL'),
        ('R50.9', 'FEBRE, NÃO ESPECIFICADA'),
    ]):
        sugestoes = listar_cids_sugestoes(query='R', limit=5)

    codigos = [codigo for codigo, _ in sugestoes]
    assert 'R10.0' in codigos
    assert 'A00' not in codigos


def test_nova_solicitacao_allows_submission_without_sistema_insercao():
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
        sess['usuario_perfil'] = 'ADMIN'

    fake_conn = MagicMock()
    fake_cursor = fake_conn.cursor.return_value
    fake_cursor.execute.return_value = None
    fake_cursor.rowcount = 1
    fake_conn.commit.return_value = None
    fake_conn.close.return_value = None

    with patch('app.resolver_id_paciente', return_value='123'), \
         patch('app.listar_especialidades', return_value=['CARDIOLOGIA']), \
         patch('app.listar_sistemas_insercao', return_value=['COPIRN']), \
         patch('app.listar_sistemas_insercao_catalogo', return_value=['COPIRN']), \
         patch('app.permite_replicar_solicitacao', return_value=False), \
         patch('app.conectar', return_value=fake_conn):
        response = client.post('/nova_solicitacao', data={
            'paciente_id': '123',
            'data_solicitacao': '14/08/2026',
            'data_entrada': '14/08/2026',
            'tipo': 'CONSULTA',
            'especialidade': 'CARDIOLOGIA',
            'prioridade': 'SIM',
            'status': 'ELETIVO',
            'quantidade_solicitacoes': '1',
            'cid': 'R10.0',
        }, follow_redirects=False)

    assert response.status_code == 302
    assert 'Informe o sistema de inserção' not in response.get_data(as_text=True)
