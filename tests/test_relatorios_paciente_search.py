from pathlib import Path


def test_relatorios_template_uses_patient_autocomplete_after_three_letters():
    template = Path('templates/relatorios.html').read_text(encoding='utf-8')

    assert 'name="paciente"' in template
    assert 'list="pacientes-sugestoes"' in template
    assert '/api/buscar_paciente' in template
    assert 'termo.length < 3' in template
