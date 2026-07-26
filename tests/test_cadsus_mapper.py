import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import mapear_dados_cadsus


def test_mapear_dados_cadsus_extrai_campos_basicos():
    payload = {
        'nomeCompleto': 'MARIA DA SILVA',
        'sus': '123456789012345',
        'nomeMae': 'JOANA SILVA',
        'endereco': {
            'logradouro': 'RUA DAS FLORES',
            'numero': '100',
            'bairro': 'CENTRO'
        }
    }

    resultado = mapear_dados_cadsus(payload)

    assert resultado['nome'] == 'MARIA DA SILVA'
    assert resultado['sus'] == '123456789012345'
    assert resultado['nome_mae'] == 'JOANA SILVA'
    assert resultado['endereco'] == 'RUA DAS FLORES, Nº 100, Bairro CENTRO'
