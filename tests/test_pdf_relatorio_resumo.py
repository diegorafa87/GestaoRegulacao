import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import gerar_pdf_relatorio_resumo


def test_gerar_pdf_relatorio_resumo_inclui_pacientes_por_especialidade():
    resumo = [('CARDIOLOGIA', 2)]
    pacientes_por_especialidade = {
        'CARDIOLOGIA': [(123, 'JOAO SILVA'), (456, 'MARIA SOUZA')]
    }

    pdf_bytes = gerar_pdf_relatorio_resumo(
        resumo,
        'CONSULTA',
        'CARDIOLOGIA',
        '',
        '',
        2,
        pacientes_por_especialidade=pacientes_por_especialidade,
    )
    texto_pdf = pdf_bytes.decode('latin-1', errors='ignore')

    assert 'JOAO SILVA' in texto_pdf
    assert 'MARIA SOUZA' in texto_pdf
