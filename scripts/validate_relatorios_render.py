from jinja2 import Environment, FileSystemLoader
import os

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
# Add minimal filters used by templates
env.filters['formatar_documento'] = lambda v: v
env.filters['formatar_data'] = lambda v: v
env.globals['url_for'] = lambda endpoint, **kwargs: ('/static/' + kwargs.get('filename')) if endpoint == 'static' and 'filename' in kwargs else ('/' + endpoint)
env.globals['session'] = {}
env.globals['get_flashed_messages'] = lambda **kwargs: []

def render_and_check(situacao):
    template = env.get_template('relatorios.html')
    resumo = [
        ('EXAMES LABORATORIAIS', 395),
        ('ORTOPEDIA', 59),
    ]
    html = template.render(
        situacao=situacao,
        resumo=resumo,
        tipo='', especialidade='', financiamento='', tempo_espera=False,
        filtros_aplicados=False, total_registros=454, tempo_medio_espera=None,
        pacientes_especialidade=None, mostrar_tipos_radiografia_relatorio=False,
        data_inicio='', data_fim=''
    )
    # Simple checks
    issues = []
    # Ensure quantities only in the quantity column: check that the pattern '395 EXAMES' does not appear
    if '395 EXAMES' in html or '395 ORTOPEDIA' in html:
        issues.append('Quantidade aparece antes do nome na coluna Resumo')
    # Ensure 'em espera' suffix not present in the Resumo column when situacao == EM_ESPERA
    if situacao == 'EM_ESPERA':
        marker = '<th class="text-center">Resumo</th>'
        idx = html.find(marker)
        if idx != -1:
            tbody_idx = html.find('<tbody>', idx)
            if tbody_idx != -1:
                # get first row block
                first_row_start = html.find('<tr>', tbody_idx)
                first_row_end = html.find('</tr>', first_row_start)
                first_row = html[first_row_start:first_row_end]
                # split tds
                tds = first_row.split('<td')
                if len(tds) >= 4:
                    resumo_td = tds[3]
                    if 'em espera' in resumo_td:
                        issues.append("Sufixo 'em espera' ainda presente na coluna Resumo")
    return html, issues

if __name__ == '__main__':
    for situacao in ['EM_ESPERA', 'REALIZADOS']:
        html, issues = render_and_check(situacao)
        print(f'--- Teste situacao={situacao} ---')
        if issues:
            print('Problemas encontrados:')
            for it in issues:
                print(' -', it)
        else:
            print('Nenhum problema detectado na renderização.')
        # Print a small snippet of the Resumo column occurrence
        start = html.find('<th class="text-center">Resumo</th>')
        snippet = html[start:start+800] if start!=-1 else html[:800]
        print('Snippet:', snippet.replace('\n','')[:400])
        print()
