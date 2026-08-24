from app import gerar_pdf_relatorio_paciente


def test_gerar_pdf_relatorio_paciente_inclui_logo_no_cabecalho():
    paciente_relatorio = ('12345678900', 'Ana Silva', '2000-01-01', '1234567890')
    relatorio_paciente = [
        [1, '2026-05-08', '2026-05-08', 'CONSULTA', '7 anos', 'P', 'NORMAL', 'EM ANDAMENTO', '2026-05-08', 'US', 'SUS', 'PRESENTE']
    ]

    pdf_bytes = gerar_pdf_relatorio_paciente(paciente_relatorio, relatorio_paciente)

    assert pdf_bytes.startswith(b'%PDF')
    assert b'/Subtype /Image' in pdf_bytes
    assert b'/XObject' in pdf_bytes
