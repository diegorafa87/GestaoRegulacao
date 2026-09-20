from pathlib import Path


def test_relatorios_template_uses_patient_autocomplete_after_three_letters():
    template = Path('templates/relatorios.html').read_text(encoding='utf-8')

    assert 'name="paciente"' in template
    assert 'list="pacientes-sugestoes"' in template
    assert '/api/buscar_paciente' in template
    assert 'termo.length < 3' in template


def test_relatorios_em_espera_exibe_data_de_solicitacao():
    template = Path('templates/relatorios.html').read_text(encoding='utf-8')

    assert "{% if situacao == 'EM_ESPERA' %}Data Solicitação{% elif situacao == 'RETIRADOS' %}Data de Retirada{% else %}Data de Realização{% endif %}" in template
    assert "(p[3] if situacao == 'EM_ESPERA' else p[7])" in template


def test_relatorios_retirados_exibe_data_de_retirada():
    template = Path('templates/relatorios.html').read_text(encoding='utf-8')

    assert 'Data de Retirada' in template
    assert "{% if situacao == 'EM_ESPERA' %}Data Solicitação{% elif situacao == 'RETIRADOS' %}Data de Retirada{% else %}Data de Realização{% endif %}" in template
