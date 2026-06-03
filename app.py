def unificar_pacientes(id_principal, id_duplicado):
    """
    Atualiza todas as referências do paciente duplicado para o paciente principal e remove o duplicado.
    """
    if id_principal == id_duplicado:
        return False, 'IDs iguais, nada a fazer.'

    conn = conectar()
    c = conn.cursor()

    # Atualiza todas as solicitações para apontar para o paciente principal
    c.execute(
        'UPDATE solicitacao SET paciente_id = %s WHERE paciente_id = %s',
        (id_principal, id_duplicado)
    )

    # (Se houver outras tabelas relacionadas, adicionar aqui)

    # Remove o paciente duplicado
    c.execute('DELETE FROM paciente WHERE id = %s', (id_duplicado,))

    conn.commit()
    conn.close()
    return True, 'Unificação concluída com sucesso.'
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, session, flash
import os
import psycopg
import re
import unicodedata
from datetime import datetime
import csv
import io
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import conectar, criar_tabelas

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'trocar-esta-chave-em-producao')

PUBLIC_ENDPOINTS = {'login', 'logout', 'static'}

def usuario_logado():
    return bool(session.get('usuario_id'))

def apenas_admin():
    return session.get('usuario_perfil') == 'ADMIN'

def login_required_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not usuario_logado():
            return redirect(url_for('login'))
        if not apenas_admin():
            flash('Apenas usuários administradores podem acessar esta área.', 'warning')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

@app.before_request
def exigir_login_global():
    endpoint = request.endpoint or ''
    if endpoint in PUBLIC_ENDPOINTS or endpoint.startswith('static'):
        return
    if not usuario_logado():
        return redirect(url_for('login'))

def garantir_usuario_admin():
    admin_user = os.environ.get('ADMIN_USER', '').strip()
    admin_password = os.environ.get('ADMIN_PASSWORD', '').strip()
    if not admin_user or not admin_password:
        return

    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT id FROM usuario WHERE username = %s', (admin_user,))
    existente = c.fetchone()
    if not existente:
        c.execute(
            'INSERT INTO usuario (nome, username, senha_hash, perfil, ativo) VALUES (%s, %s, %s, %s, %s)',
            ('Administrador', admin_user, generate_password_hash(admin_password), 'ADMIN', True)
        )
        conn.commit()
    conn.close()

def normalizar_data_para_iso(data_str):
    if not data_str:
        return None
    data_str = data_str.strip()
    try:
        if '/' in data_str:
            return datetime.strptime(data_str, '%d/%m/%Y').strftime('%Y-%m-%d')
        return datetime.strptime(data_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        return data_str

def formatar_data_br(data_str):
    if not data_str:
        return ''
    data_str = str(data_str).strip()
    try:
        if '-' in data_str:
            return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        if '/' in data_str:
            return datetime.strptime(data_str, '%d/%m/%Y').strftime('%d/%m/%Y')
    except ValueError:
        pass
    return data_str

def normalizar_documento(valor):
    valor = '' if valor is None else str(valor)
    return re.sub(r'\D', '', valor)

def normalizar_texto_busca(valor):
    valor = '' if valor is None else str(valor)
    valor = unicodedata.normalize('NFD', valor)
    valor = ''.join(ch for ch in valor if unicodedata.category(ch) != 'Mn')
    valor = re.sub(r'\s+', ' ', valor).strip()
    return valor.upper()

def eh_cpf(valor):
    return len(normalizar_documento(valor)) == 11

def formatar_cpf(valor):
    cpf = normalizar_documento(valor)
    if len(cpf) != 11:
        return '' if valor is None else str(valor).strip()
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'

def formatar_identificador_paciente(valor):
    valor = '' if valor is None else str(valor).strip()
    if eh_cpf(valor):
        return formatar_cpf(valor)
    return valor

def resolver_id_paciente(identificador):
    identificador = '' if identificador is None else str(identificador).strip()
    if not identificador:
        return None

    documento = normalizar_documento(identificador)
    conn = conectar()
    c = conn.cursor()

    if documento:
        c.execute(
            '''
            SELECT id
            FROM paciente
            WHERE id = %s
               OR regexp_replace(COALESCE(id, ''), '\\D', '', 'g') = %s
               OR regexp_replace(COALESCE(sus, ''), '\\D', '', 'g') = %s
            ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END, nome ASC
            LIMIT 1
            ''',
            (identificador, documento, documento, identificador)
        )
    else:
        c.execute('SELECT id FROM paciente WHERE id = %s LIMIT 1', (identificador,))

    paciente = c.fetchone()
    conn.close()
    return paciente[0] if paciente else None

def buscar_paciente_existente_por_documentos(cpf=None, sus=None):
    documentos = []
    for documento in (cpf, sus):
        doc_normalizado = normalizar_documento(documento)
        if doc_normalizado and doc_normalizado not in documentos:
            documentos.append(doc_normalizado)

    if not documentos:
        return None

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, nome
        FROM paciente
        WHERE regexp_replace(COALESCE(id, ''), '\\D', '', 'g') = ANY(%s)
           OR regexp_replace(COALESCE(sus, ''), '\\D', '', 'g') = ANY(%s)
        LIMIT 1
        ''',
        (documentos, documentos)
    )
    paciente = c.fetchone()
    conn.close()
    return paciente

def formatar_endereco_lista(endereco):
    import re
    endereco = '' if endereco is None else str(endereco).strip()
    if not endereco:
        return ''

    # Remove prefixos "Nº " e "Bairro " gerados pelo formulário de cadastro
    endereco = re.sub(r'\bN[º°]?\s+', '', endereco)
    endereco = re.sub(r'\bBairro\s+', '', endereco, flags=re.IGNORECASE)
    endereco = endereco.strip().strip(',').strip()

    sufixo = 'FERNANDO PEDROZA, RN.'
    endereco_normalizado = endereco.upper().replace('.', '')
    if 'FERNANDO PEDROZA' in endereco_normalizado and 'RN' in endereco_normalizado:
        return endereco

    separador = ', ' if not endereco.endswith(',') else ' '
    return f'{endereco}{separador}{sufixo}'

def escapar_texto_pdf(texto):
    texto = '' if texto is None else str(texto)
    texto = texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return texto.encode('latin-1', errors='replace').decode('latin-1')

def quebrar_linha_pdf(texto, limite=58):
    texto = '' if texto is None else str(texto).strip()
    if not texto:
        return ['']

    palavras = texto.split()
    linhas = []
    atual = ''

    for palavra in palavras:
        candidato = f'{atual} {palavra}'.strip()
        if len(candidato) <= limite:
            atual = candidato
        else:
            if atual:
                linhas.append(atual)
            while len(palavra) > limite:
                linhas.append(palavra[:limite])
                palavra = palavra[limite:]
            atual = palavra

    if atual:
        linhas.append(atual)

    return linhas or ['']

def comando_texto_pdf(x, y, texto, fonte='F1', tamanho=11, cor=(0, 0, 0)):
    r, g, b = cor
    return (
        'q\n'
        f'{r:.3f} {g:.3f} {b:.3f} rg\n'
        f'BT /{fonte} {tamanho} Tf 1 0 0 1 {x} {y} Tm ({escapar_texto_pdf(texto)}) Tj ET\n'
        'Q'
    )

def comando_texto_centralizado_pdf(centro_x, y, texto, largura_maxima, fonte='F1', tamanho=11, cor=(0, 0, 0)):
    texto = '' if texto is None else str(texto)
    largura_estimada = min(len(texto) * tamanho * 0.5, largura_maxima)
    x = centro_x - (largura_estimada / 2)
    return comando_texto_pdf(round(x, 2), y, texto, fonte=fonte, tamanho=tamanho, cor=cor)

def comando_linha_pdf(x1, y1, x2, y2, cor=(0, 0, 0), espessura=1):
    r, g, b = cor
    return (
        'q\n'
        f'{r:.3f} {g:.3f} {b:.3f} RG\n'
        f'{espessura} w\n'
        f'{x1} {y1} m\n'
        f'{x2} {y2} l\n'
        'S\n'
        'Q'
    )

def comando_retangulo_pdf(x, y, largura, altura, cor_borda=None, cor_fundo=None, espessura=1):
    comandos = ['q']

    if cor_fundo:
        r, g, b = cor_fundo
        comandos.append(f'{r:.3f} {g:.3f} {b:.3f} rg')

    if cor_borda:
        r, g, b = cor_borda
        comandos.append(f'{r:.3f} {g:.3f} {b:.3f} RG')
        comandos.append(f'{espessura} w')

    operador = 'S'
    if cor_fundo and cor_borda:
        operador = 'B'
    elif cor_fundo:
        operador = 'f'

    comandos.append(f'{x} {y} {largura} {altura} re {operador}')
    comandos.append('Q')
    return '\n'.join(comandos)

def formatar_periodo_relatorio(data_inicio, data_fim):
    if data_inicio and data_fim:
        return f'{data_inicio} a {data_fim}'
    if data_inicio:
        return f'A partir de {data_inicio}'
    if data_fim:
        return f'Ate {data_fim}'
    return 'Todos os periodos'

def gerar_pdf_relatorio_resumo(resumo, tipo, especialidade, data_inicio, data_fim, total_registros):
    largura_pagina = 595
    altura_pagina = 842
    margem_x = 42
    rodape_y = 36
    largura_util = largura_pagina - (margem_x * 2)
    coluna_especialidade = 385
    coluna_quantidade = largura_util - coluna_especialidade
    topo_tabela = None
    y_atual = 0
    paginas = []
    data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')
    periodo = formatar_periodo_relatorio(data_inicio, data_fim)

    cor_primaria = (0.121, 0.466, 0.705)
    cor_primaria_escura = (0.082, 0.247, 0.396)
    cor_texto = (0.149, 0.164, 0.196)
    cor_muted = (0.420, 0.451, 0.482)
    cor_borda = (0.820, 0.843, 0.878)
    cor_fundo_box = (0.953, 0.965, 0.980)
    cor_linha_alternada = (0.976, 0.980, 0.988)
    cor_branca = (1, 1, 1)

    def adicionar_comando(comando):
        paginas[-1].append(comando)

    def adicionar_texto(x, y, texto, fonte='F1', tamanho=11, cor=cor_texto):
        adicionar_comando(comando_texto_pdf(x, y, texto, fonte=fonte, tamanho=tamanho, cor=cor))

    def desenhar_cabecalho(primeira_pagina=False):
        nonlocal y_atual
        centro_x = margem_x + (largura_util / 2)
        topo_box = altura_pagina - 48
        altura_box = 82
        base_box = topo_box - altura_box

        adicionar_comando(
            comando_retangulo_pdf(
                margem_x,
                base_box,
                largura_util,
                altura_box,
                cor_fundo=cor_primaria,
                cor_borda=cor_primaria,
                espessura=1,
            )
        )
        adicionar_comando(
            comando_linha_pdf(
                margem_x + 28,
                base_box + 48,
                margem_x + largura_util - 28,
                base_box + 48,
                cor=(0.749, 0.827, 0.902),
                espessura=1,
            )
        )
        adicionar_comando(
            comando_texto_centralizado_pdf(
                centro_x,
                topo_box - 18,
                'Secretaria Municipal de Saude de Fernando Pedroza',
                largura_util - 40,
                fonte='F2',
                tamanho=13,
                cor=(0.910, 0.949, 0.984),
            )
        )
        adicionar_comando(
            comando_texto_centralizado_pdf(
                centro_x,
                topo_box - 42,
                'Relatorio de Especialidades Realizadas',
                largura_util - 40,
                fonte='F2',
                tamanho=20,
                cor=cor_branca,
            )
        )
        adicionar_comando(
            comando_texto_centralizado_pdf(
                centro_x,
                topo_box - 61,
                'Procedimentos concluídos agrupados por especialidade',
                largura_util - 40,
                tamanho=10,
                cor=(0.910, 0.949, 0.984),
            )
        )

        y_atual = base_box - 22

        if primeira_pagina:
            altura_box = 88
            base_box = y_atual - altura_box
            adicionar_comando(
                comando_retangulo_pdf(
                    margem_x,
                    base_box,
                    largura_util,
                    altura_box,
                    cor_fundo=cor_fundo_box,
                    cor_borda=cor_borda,
                    espessura=1,
                )
            )
            adicionar_texto(margem_x + 14, y_atual - 20, f'Gerado em: {data_geracao}', fonte='F2', tamanho=11)
            adicionar_texto(margem_x + 14, y_atual - 40, f'Tipo: {tipo.title() if tipo else "Todos"}', tamanho=10, cor=cor_muted)
            adicionar_texto(margem_x + 14, y_atual - 58, f'Especialidade: {especialidade if especialidade else "Todas"}', tamanho=10, cor=cor_muted)
            adicionar_texto(margem_x + 275, y_atual - 20, f'Periodo: {periodo}', tamanho=10, cor=cor_muted)
            adicionar_texto(margem_x + 275, y_atual - 40, f'Total realizado: {total_registros}', fonte='F2', tamanho=12, cor=cor_primaria_escura)
            adicionar_texto(margem_x + 275, y_atual - 58, f'Registros no resumo: {len(resumo)}', tamanho=10, cor=cor_muted)
            y_atual = base_box - 24
        else:
            y_atual -= 10

    def desenhar_cabecalho_tabela():
        nonlocal y_atual, topo_tabela
        topo = y_atual
        base = topo - 28
        topo_tabela = topo

        adicionar_comando(
            comando_retangulo_pdf(
                margem_x,
                base,
                largura_util,
                28,
                cor_fundo=cor_primaria_escura,
                cor_borda=cor_primaria_escura,
            )
        )
        adicionar_comando(comando_linha_pdf(margem_x + coluna_especialidade, base, margem_x + coluna_especialidade, topo, cor=(0.749, 0.827, 0.902), espessura=1))
        adicionar_texto(margem_x + 12, topo - 18, 'Especialidade', fonte='F2', tamanho=11, cor=cor_branca)
        adicionar_texto(margem_x + coluna_especialidade + 12, topo - 18, 'Quantidade', fonte='F2', tamanho=11, cor=cor_branca)
        y_atual = base - 6

    def nova_pagina(primeira_pagina=False):
        paginas.append([])
        desenhar_cabecalho(primeira_pagina=primeira_pagina)
        desenhar_cabecalho_tabela()

    nova_pagina(primeira_pagina=True)

    if resumo:
        for indice, (especialidade_item, quantidade) in enumerate(resumo):
            descricao = especialidade_item if especialidade_item else 'Sem especialidade informada'
            linhas = quebrar_linha_pdf(descricao, limite=52)
            altura_linhas = len(linhas) * 14
            altura_linha = max(28, altura_linhas + 12)

            if y_atual - altura_linha < rodape_y + 22:
                nova_pagina(primeira_pagina=False)

            topo = y_atual
            base = topo - altura_linha
            cor_fundo = cor_linha_alternada if indice % 2 == 0 else cor_branca

            adicionar_comando(
                comando_retangulo_pdf(
                    margem_x,
                    base,
                    largura_util,
                    altura_linha,
                    cor_fundo=cor_fundo,
                    cor_borda=cor_borda,
                    espessura=1,
                )
            )
            adicionar_comando(comando_linha_pdf(margem_x + coluna_especialidade, base, margem_x + coluna_especialidade, topo, cor=cor_borda, espessura=1))

            for posicao, linha in enumerate(linhas):
                adicionar_texto(margem_x + 12, topo - 18 - (posicao * 14), linha, tamanho=10)

            quantidade_y = base + (altura_linha / 2) - 3
            adicionar_texto(margem_x + coluna_especialidade + 12, quantidade_y, str(quantidade), fonte='F2', tamanho=11, cor=cor_primaria_escura)
            y_atual = base - 4
    else:
        altura_box = 42
        if y_atual - altura_box < rodape_y + 22:
            nova_pagina(primeira_pagina=False)

        topo = y_atual
        base = topo - altura_box
        adicionar_comando(
            comando_retangulo_pdf(
                margem_x,
                base,
                largura_util,
                altura_box,
                cor_fundo=cor_fundo_box,
                cor_borda=cor_borda,
                espessura=1,
            )
        )
        adicionar_texto(margem_x + 12, topo - 24, 'Nenhum registro encontrado para os filtros informados.', fonte='F2', tamanho=11, cor=cor_muted)

    total_paginas = len(paginas)
    for indice_pagina, comandos in enumerate(paginas, start=1):
        comandos.append(comando_linha_pdf(margem_x, rodape_y + 10, margem_x + largura_util, rodape_y + 10, cor=cor_borda, espessura=1))
        comandos.append(comando_texto_pdf(margem_x, rodape_y - 2, f'Sistema de Regulacao - emitido em {data_geracao}', tamanho=9, cor=cor_muted))
        comandos.append(comando_texto_pdf(margem_x + largura_util - 76, rodape_y - 2, f'Pagina {indice_pagina}/{total_paginas}', fonte='F2', tamanho=9, cor=cor_muted))

    objetos = {
        1: '<< /Type /Catalog /Pages 2 0 R >>',
        3: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        4: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
        5: '<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>'
    }

    referencias_paginas = []
    numero_objeto = 6

    for comandos in paginas:
        conteudo = '\n'.join(comandos)
        conteudo_bytes = conteudo.encode('latin-1', errors='replace')
        objeto_conteudo = numero_objeto
        objeto_pagina = numero_objeto + 1
        numero_objeto += 2

        objetos[objeto_conteudo] = (
            f'<< /Length {len(conteudo_bytes)} >>\n'
            f'stream\n{conteudo}\nendstream'
        )
        objetos[objeto_pagina] = (
            '<< /Type /Page /Parent 2 0 R '
            f'/MediaBox [0 0 {largura_pagina} {altura_pagina}] '
            '/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> '
            f'/Contents {objeto_conteudo} 0 R >>'
        )
        referencias_paginas.append(f'{objeto_pagina} 0 R')

    objetos[2] = f'<< /Type /Pages /Kids [{" ".join(referencias_paginas)}] /Count {len(referencias_paginas)} >>'

    pdf = io.BytesIO()
    pdf.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

    offsets = {}
    for numero in sorted(objetos):
        offsets[numero] = pdf.tell()
        pdf.write(f'{numero} 0 obj\n'.encode('latin-1'))
        pdf.write(objetos[numero].encode('latin-1'))
        pdf.write(b'\nendobj\n')

    xref_inicio = pdf.tell()
    total_objetos = max(objetos)
    pdf.write(f'xref\n0 {total_objetos + 1}\n'.encode('latin-1'))
    pdf.write(b'0000000000 65535 f \n')

    for numero in range(1, total_objetos + 1):
        offset = offsets.get(numero, 0)
        pdf.write(f'{offset:010} 00000 n \n'.encode('latin-1'))

    pdf.write(
        (
            f'trailer\n<< /Size {total_objetos + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_inicio}\n%%EOF'
        ).encode('latin-1')
    )

    return pdf.getvalue()

def gerar_pdf_termo_retirada_solicitacao(paciente_nome, paciente_id, especialidade, data_entrada, data_retirada, solicitacao_id=None):
    largura_pagina = 595
    altura_pagina = 842
    margem_x = 42
    largura_util = largura_pagina - (margem_x * 2)
    centro_x = margem_x + (largura_util / 2)
    data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')

    cor_primaria = (0.121, 0.466, 0.705)
    cor_primaria_escura = (0.082, 0.247, 0.396)
    cor_texto = (0.149, 0.164, 0.196)
    cor_muted = (0.420, 0.451, 0.482)
    cor_borda = (0.820, 0.843, 0.878)
    cor_fundo_box = (0.953, 0.965, 0.980)
    cor_branca = (1, 1, 1)

    comandos = []

    def adicionar(comando):
        comandos.append(comando)

    def texto(x, y, conteudo, fonte='F1', tamanho=11, cor=cor_texto):
        adicionar(comando_texto_pdf(x, y, conteudo, fonte=fonte, tamanho=tamanho, cor=cor))

    def linha(x1, y1, x2, y2, cor=cor_borda, espessura=1):
        adicionar(comando_linha_pdf(x1, y1, x2, y2, cor=cor, espessura=espessura))

    def caixa(x, y, largura, altura, cor_fundo=None, cor_borda=cor_borda, espessura=1):
        adicionar(comando_retangulo_pdf(x, y, largura, altura, cor_borda=cor_borda, cor_fundo=cor_fundo, espessura=espessura))

    especialidade = '' if especialidade is None else str(especialidade).strip()
    paciente_nome = '' if paciente_nome is None else str(paciente_nome).strip()
    paciente_id = formatar_identificador_paciente(paciente_id)
    data_entrada = formatar_data_br(data_entrada)
    data_retirada = formatar_data_br(data_retirada)
    numero_solicitacao = f'#{solicitacao_id}' if solicitacao_id is not None else ''

    # ── Cabeçalho ──────────────────────────────────────────────────────────
    caixa(margem_x, 734, largura_util, 68, cor_fundo=cor_primaria, cor_borda=cor_primaria)
    adicionar(comando_texto_centralizado_pdf(centro_x, 782, 'Secretaria Municipal de Saude de Fernando Pedroza', largura_util - 40, fonte='F2', tamanho=13, cor=(0.910, 0.949, 0.984)))
    adicionar(comando_texto_centralizado_pdf(centro_x, 757, 'Termo de Retirada de Requisicao', largura_util - 40, fonte='F2', tamanho=21, cor=cor_branca))
    if numero_solicitacao:
        adicionar(comando_texto_centralizado_pdf(centro_x, 741, f'Solicitacao {numero_solicitacao}', largura_util - 40, tamanho=10, cor=(0.910, 0.949, 0.984)))

    # ── Bloco Paciente (nome + ID) ─────────────────────────────────────────
    caixa(margem_x, 646, largura_util, 72, cor_fundo=cor_fundo_box, cor_borda=cor_borda)
    texto(margem_x + 14, 702, 'Paciente', fonte='F2', tamanho=11, cor=cor_muted)
    texto(margem_x + 14, 682, paciente_nome or '-', fonte='F2', tamanho=16, cor=cor_primaria_escura)
    texto(margem_x + 14, 661, f'ID do paciente: {paciente_id or "-"}', tamanho=10, cor=cor_muted)

    # ── Bloco Especialidade ────────────────────────────────────────────────
    caixa(margem_x, 574, largura_util, 56, cor_fundo=cor_branca, cor_borda=cor_borda)
    texto(margem_x + 14, 616, 'Especialidade', fonte='F2', tamanho=11, cor=cor_muted)
    texto(margem_x + 14, 595, especialidade or '-', fonte='F2', tamanho=14, cor=cor_primaria_escura)

    # ── Bloco Datas ────────────────────────────────────────────────────────
    caixa(margem_x, 482, largura_util, 76, cor_fundo=cor_fundo_box, cor_borda=cor_borda)
    texto(margem_x + 14, 542, 'Data de entrada da requisicao', fonte='F2', tamanho=11, cor=cor_muted)
    texto(margem_x + 14, 520, data_entrada or '-', fonte='F2', tamanho=15, cor=cor_primaria_escura)
    texto(margem_x + 300, 542, 'Data de retirada', fonte='F2', tamanho=11, cor=cor_muted)
    texto(margem_x + 300, 520, data_retirada or '-', fonte='F2', tamanho=15, cor=cor_primaria_escura)

    # ── Bloco Declaração + Assinaturas ─────────────────────────────────────
    caixa(margem_x, 248, largura_util, 218, cor_fundo=cor_fundo_box, cor_borda=cor_borda)
    declaracao = 'Declaro que recebi a devolucao da requisicao acima identificada e que estou ciente de que a retirada encerra a movimentacao desta solicitacao na Regulacao do Municipio de Fernando Pedroza.'
    linhas_decl = quebrar_linha_pdf(declaracao, limite=80)
    for i, linha_texto in enumerate(linhas_decl[:3]):
        texto(margem_x + 14, 450 - (i * 16), linha_texto, fonte='F2', tamanho=10.5, cor=cor_texto)
    texto(margem_x + 14, 406, 'Assinaturas', fonte='F2', tamanho=12, cor=cor_primaria_escura)
    texto(margem_x + 14, 382, 'Tecnico da Secretaria', tamanho=10, cor=cor_muted)
    texto(margem_x + 320, 382, 'Paciente', tamanho=10, cor=cor_muted)
    linha(margem_x + 14, 358, margem_x + 258, 358, cor=cor_primaria_escura, espessura=1)
    linha(margem_x + 300, 358, margem_x + largura_util - 14, 358, cor=cor_primaria_escura, espessura=1)
    texto(margem_x + 14, 342, 'Nome por extenso', tamanho=9, cor=cor_muted)
    texto(margem_x + 300, 342, 'Nome por extenso', tamanho=9, cor=cor_muted)
    linha(margem_x + 14, 322, margem_x + 258, 322, cor=cor_borda, espessura=1)
    linha(margem_x + 300, 322, margem_x + largura_util - 14, 322, cor=cor_borda, espessura=1)

    # ── Rodapé ─────────────────────────────────────────────────────────────
    texto(margem_x + 14, 228, f'Documento emitido em {data_geracao}', tamanho=9, cor=cor_muted)
    texto(margem_x + 14, 212, 'Preencher as assinaturas e arquivar junto ao processo administrativo da requisicao.', tamanho=9, cor=cor_muted)

    objetos = {
        1: '<< /Type /Catalog /Pages 2 0 R >>',
        3: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        4: '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
        5: '<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>'
    }

    conteudo = '\n'.join(comandos)
    conteudo_bytes = conteudo.encode('latin-1', errors='replace')
    objetos[6] = f'<< /Length {len(conteudo_bytes)} >>\nstream\n{conteudo}\nendstream'
    objetos[7] = (
        '<< /Type /Page /Parent 2 0 R '
        f'/MediaBox [0 0 {largura_pagina} {altura_pagina}] '
        '/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> '
        '/Contents 6 0 R >>'
    )
    objetos[2] = '<< /Type /Pages /Kids [7 0 R] /Count 1 >>'

    pdf = io.BytesIO()
    pdf.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

    offsets = {}
    for numero in sorted(objetos):
        offsets[numero] = pdf.tell()
        pdf.write(f'{numero} 0 obj\n'.encode('latin-1'))
        pdf.write(objetos[numero].encode('latin-1'))
        pdf.write(b'\nendobj\n')

    xref_inicio = pdf.tell()
    total_objetos = max(objetos)
    pdf.write(f'xref\n0 {total_objetos + 1}\n'.encode('latin-1'))
    pdf.write(b'0000000000 65535 f \n')

    for numero in range(1, total_objetos + 1):
        offset = offsets.get(numero, 0)
        pdf.write(f'{offset:010} 00000 n \n'.encode('latin-1'))

    pdf.write(
        (
            f'trailer\n<< /Size {total_objetos + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_inicio}\n%%EOF'
        ).encode('latin-1')
    )

    return pdf.getvalue()

app.jinja_env.filters['formatar_data'] = formatar_data_br
app.jinja_env.filters['formatar_endereco_lista'] = formatar_endereco_lista
app.jinja_env.filters['formatar_documento'] = formatar_identificador_paciente

@app.route('/login', methods=['GET', 'POST'])
def login():
    if usuario_logado():
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha = request.form.get('senha', '')

        conn = conectar()
        c = conn.cursor()
        c.execute(
            'SELECT id, nome, username, senha_hash, perfil, ativo FROM usuario WHERE username = %s',
            (username,)
        )
        usuario = c.fetchone()
        conn.close()

        if not usuario:
            flash('Usuário ou senha inválidos.', 'danger')
            return render_template('login.html')

        if not usuario[5]:
            flash('Usuário inativo. Contate um administrador.', 'warning')
            return render_template('login.html')

        if not check_password_hash(usuario[3], senha):
            flash('Usuário ou senha inválidos.', 'danger')
            return render_template('login.html')

        session['usuario_id'] = usuario[0]
        session['usuario_nome'] = usuario[1]
        session['usuario_username'] = usuario[2]
        session['usuario_perfil'] = usuario[4]
        flash(f'Bem-vindo, {usuario[1]}!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('login'))

def consultar_solicitacoes(cpf, sus, especialidade, prioridade, status):
    especialidade_normalizada = normalizar_texto_busca(especialidade)
    mostrar_tipos_radiografia = 'RADIOGRAFIA' in especialidade_normalizada
    status_upper = status.upper()
    modo_urgencia_em_espera = (
        status_upper == 'URGENTE' and
        not cpf and
        not sus and
        not especialidade and
        not prioridade
    )

    if modo_urgencia_em_espera:
        query = '''
            SELECT
                p.id,
                p.nome,
                s.especialidade,
                s.prioridade,
                s.status,
                s.data_solicitacao,
                s.data_entrada,
                0 AS retorno_agendado_count
            FROM solicitacao s
            INNER JOIN paciente p ON p.id = s.paciente_id
            WHERE UPPER(s.status) = 'URGENTE'
              AND (s.data_realizacao IS NULL OR TRIM(s.data_realizacao) = '')
            ORDER BY s.data_entrada DESC, s.data_solicitacao DESC
        '''
        conn = conectar()
        c = conn.cursor()
        c.execute(query)
        solicitacoes = c.fetchall()
        conn.close()
        return solicitacoes, True, False, 0, []

    usar_data_urgencia = bool(especialidade and status)
    ultima_data_expr = 'MAX(s.data_entrada) AS ultima_data_entrada'
    tipos_radiografia_expr = "NULL AS tipos_radiografia"
    params = []
    cpf_normalizado = normalizar_documento(cpf)
    sus_normalizado = normalizar_documento(sus)

    if mostrar_tipos_radiografia:
        tipos_radiografia_expr = '''
            (
                SELECT STRING_AGG(sr.especialidade, '||' ORDER BY sr.data_entrada DESC, sr.id DESC)
                FROM solicitacao sr
                WHERE sr.paciente_id = p.id
                  AND translate(UPPER(COALESCE(sr.especialidade, '')),
                        'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                        'AAAAAEEEEIIIIOOOOOUUUUC') LIKE '%RADIOGRAFIA%'
                  AND UPPER(COALESCE(sr.conclusao, '')) <> 'CANCELADO'
            ) AS tipos_radiografia
        '''

    if usar_data_urgencia:
        ultima_data_expr = '''
            COALESCE(
                (
                    SELECT MAX(su.data_solicitacao)
                    FROM solicitacao su
                    WHERE su.paciente_id = p.id
                      AND su.especialidade LIKE %s
                      AND UPPER(su.status) LIKE '%%URGENTE%%'
                      AND UPPER(COALESCE(su.conclusao, '')) <> 'CANCELADO'
                ),
                MAX(s.data_entrada)
            ) AS ultima_data_entrada
        '''
        params.append(f"%{especialidade}%")

    query = f'''
        SELECT
            p.id,
            p.nome,
            COUNT(s.id) AS total_solicitacoes,
            {ultima_data_expr},
            (
                SELECT s2.status
                FROM solicitacao s2
                WHERE s2.paciente_id = p.id
                  AND UPPER(COALESCE(s2.conclusao, '')) <> 'CANCELADO'
                ORDER BY s2.data_entrada DESC, s2.status ASC
                LIMIT 1
            ) AS status_atual,
            (
                SELECT COUNT(1)
                FROM solicitacao sr
                WHERE sr.paciente_id = p.id
                  AND UPPER(COALESCE(sr.status, '')) = 'RETORNO'
                  AND TRIM(COALESCE(sr.data_retorno, '')) <> ''
                  AND UPPER(COALESCE(sr.conclusao, '')) <> 'CANCELADO'
            ) AS retorno_agendado_count,
            {tipos_radiografia_expr}
        FROM paciente p
        LEFT JOIN solicitacao s ON s.paciente_id = p.id AND UPPER(COALESCE(s.conclusao, '')) <> 'CANCELADO'
        WHERE 1=1
    '''

    filtros_id = []
    if cpf_normalizado:
        filtros_id.append("regexp_replace(COALESCE(p.id, ''), '\\D', '', 'g') LIKE %s")
        params.append(f"%{cpf_normalizado}%")
    if sus_normalizado:
        filtros_id.append("regexp_replace(COALESCE(p.id, ''), '\\D', '', 'g') LIKE %s")
        params.append(f"%{sus_normalizado}%")
    if filtros_id:
        query += ' AND (' + ' OR '.join(filtros_id) + ')'
    if especialidade:
        query += " AND (p.nome ILIKE %s OR EXISTS (SELECT 1 FROM solicitacao sx WHERE sx.paciente_id = p.id AND sx.especialidade LIKE %s AND UPPER(COALESCE(sx.conclusao, '')) <> 'CANCELADO'))"
        params.append(f"%{especialidade}%")
        params.append(f"%{especialidade}%")
    if prioridade:
        query += " AND EXISTS (SELECT 1 FROM solicitacao sx WHERE sx.paciente_id = p.id AND sx.prioridade LIKE %s AND UPPER(COALESCE(sx.conclusao, '')) <> 'CANCELADO')"
        params.append(f"%{prioridade}%")
    if status:
        query += " AND EXISTS (SELECT 1 FROM solicitacao sx WHERE sx.paciente_id = p.id AND sx.status LIKE %s AND UPPER(COALESCE(sx.conclusao, '')) <> 'CANCELADO')"
        params.append(f"%{status}%")
    query += ' GROUP BY p.id, p.nome ORDER BY p.nome ASC'

    conn = conectar()
    c = conn.cursor()
    c.execute(query, params)
    solicitacoes = c.fetchall()

    query_retorno = '''
        SELECT
            s.id,
            p.id,
            p.nome,
            s.especialidade,
            s.prioridade,
            s.status,
            s.data_solicitacao,
            s.data_entrada,
            s.data_retorno
        FROM solicitacao s
        INNER JOIN paciente p ON p.id = s.paciente_id
        WHERE UPPER(COALESCE(s.status, '')) = 'RETORNO'
          AND TRIM(COALESCE(s.data_retorno, '')) <> ''
    '''
    params_retorno = []
    filtros_retorno = []

    if cpf_normalizado:
        filtros_retorno.append("regexp_replace(COALESCE(p.id, ''), '\\D', '', 'g') LIKE %s")
        params_retorno.append(f"%{cpf_normalizado}%")
    if sus_normalizado:
        filtros_retorno.append("regexp_replace(COALESCE(p.id, ''), '\\D', '', 'g') LIKE %s")
        params_retorno.append(f"%{sus_normalizado}%")
    if especialidade:
        filtros_retorno.append("(p.nome ILIKE %s OR s.especialidade LIKE %s)")
        params_retorno.append(f"%{especialidade}%")
        params_retorno.append(f"%{especialidade}%")
    if prioridade:
        filtros_retorno.append("s.prioridade LIKE %s")
        params_retorno.append(f"%{prioridade}%")
    if status:
        filtros_retorno.append("s.status LIKE %s")
        params_retorno.append(f"%{status}%")

    if filtros_retorno:
        query_retorno += ' AND ' + ' AND '.join(filtros_retorno)

    query_retorno += ' ORDER BY s.data_retorno ASC, s.data_entrada DESC'
    c.execute(query_retorno, params_retorno)
    retorno_agendado_registros = c.fetchall()
    conn.close()

    return solicitacoes, False, mostrar_tipos_radiografia, len(retorno_agendado_registros), retorno_agendado_registros

def listar_especialidades():
    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT valor
                FROM sugestao_solicitacao
                WHERE tipo = 'especialidade'
                    AND TRIM(valor) <> ''
        ORDER BY valor
        '''
    )
    resultados = c.fetchall()
    conn.close()
    return [r[0] for r in resultados if r and r[0]]

SISTEMAS_INSERCAO_PADRAO = [
    'COPIRN',
    'REGULA RN',
    'REGULA CIRURGIA',
    'SISREG',
    'SOLICITA LMEEC',
    'SMS FERNANDO PEDROZA',
    'CONVÊNIO',
]

def listar_sistemas_insercao():
    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT DISTINCT TRIM(valor) AS valor
        FROM sugestao_solicitacao
        WHERE tipo = 'sistema_insercao'
          AND TRIM(valor) <> ''
        ORDER BY valor
        '''
    )
    resultados = c.fetchall()
    conn.close()

    catalogo = [r[0] for r in resultados if r and r[0]]
    return sorted(set(SISTEMAS_INSERCAO_PADRAO + catalogo))

def listar_sugestoes_endereco(tipo):
    if tipo not in ('rua', 'bairro'):
        return []

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT DISTINCT TRIM(valor) AS valor
        FROM sugestao_endereco
        WHERE tipo = %s
          AND TRIM(valor) <> ''
        ORDER BY valor
        ''',
        (tipo,)
    )
    resultados = c.fetchall()
    conn.close()
    return [r[0] for r in resultados if r and r[0]]

def montar_paginas_visiveis(pagina_atual, total_paginas, alcance=2):
    if total_paginas <= 1:
        return [1]

    paginas = {1, total_paginas}
    inicio = max(1, pagina_atual - alcance)
    fim = min(total_paginas, pagina_atual + alcance)

    for numero in range(inicio, fim + 1):
        paginas.add(numero)

    paginas_ordenadas = sorted(paginas)
    paginas_visiveis = []
    anterior = None

    for numero in paginas_ordenadas:
        if anterior is not None and numero - anterior > 1:
            paginas_visiveis.append(None)
        paginas_visiveis.append(numero)
        anterior = numero

    return paginas_visiveis

def paginar_registros(registros, pagina_atual, itens_por_pagina=30):
    total_registros = len(registros)
    total_paginas = max(1, (total_registros + itens_por_pagina - 1) // itens_por_pagina)

    if pagina_atual < 1:
        pagina_atual = 1
    if pagina_atual > total_paginas:
        pagina_atual = total_paginas

    inicio = (pagina_atual - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    registros_paginados = registros[inicio:fim]

    inicio_exibicao = inicio + 1 if total_registros else 0
    fim_exibicao = min(fim, total_registros) if total_registros else 0

    return {
        'registros': registros_paginados,
        'pagina_atual': pagina_atual,
        'total_paginas': total_paginas,
        'total_registros': total_registros,
        'itens_por_pagina': itens_por_pagina,
        'inicio_exibicao': inicio_exibicao,
        'fim_exibicao': fim_exibicao,
        'paginas_visiveis': montar_paginas_visiveis(pagina_atual, total_paginas),
    }

def permite_replicar_solicitacao(tipo, especialidade):
    if (tipo or '').strip().upper() != 'EXAME':
        return False

    especialidade_normalizada = normalizar_texto_busca(especialidade)
    termos_permitidos = (
        'ANATOMOPATOLOGICO',
        'ANATOMOPATOLÓGICO',
        'EXAMES LABORATORIAIS',
        'EXAME LABORATORIAL',
        'LABORATORIAL',
    )
    return any(termo in especialidade_normalizada for termo in termos_permitidos)

def eh_data_futura(data_str):
    """
    Verifica se uma data está no futuro.
    data_str deve estar no formato ISO (YYYY-MM-DD)
    """
    if not data_str:
        return False
    
    try:
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
        hoje = datetime.now().date()
        return data > hoje
    except (ValueError, TypeError):
        return False

def verificar_solicitacao_duplicada(paciente_id, tipo, especialidade):
    """
    Verifica se existe solicitação duplicada para o mesmo paciente, tipo e especialidade.
    Retorna dict com duplicatas encontradas ou None.
    """
    if not paciente_id or not tipo or not especialidade:
        return None
    
    conn = conectar()
    c = conn.cursor()
    
    # Busca solicitações com mesmo paciente, tipo e especialidade
    c.execute(
        '''
        SELECT id, status, data_realizacao, data_entrada, data_solicitacao
        FROM solicitacao
        WHERE paciente_id = %s 
          AND tipo = %s 
          AND especialidade = %s
        ORDER BY data_solicitacao DESC, id DESC
        LIMIT 5
        ''',
        (paciente_id, tipo, especialidade)
    )
    
    duplicatas = c.fetchall()
    conn.close()
    
    if not duplicatas:
        return None
    
    # Formata os dados para retornar ao cliente
    resultado = {
        'encontradas': True,
        'total': len(duplicatas),
        'solicitacoes': []
    }
    
    for solicitacao in duplicatas:
        resultado['solicitacoes'].append({
            'id': solicitacao[0],
            'status': solicitacao[1],
            'data_realizacao': formatar_data_br(solicitacao[2]),
            'data_entrada': formatar_data_br(solicitacao[3]),
            'data_solicitacao': formatar_data_br(solicitacao[4]),
            'executada': solicitacao[1] == 'EXECUTADO' or solicitacao[2] is not None
        })
    
    return resultado

@app.route('/api/verificar_solicitacao_duplicada', methods=['POST'])
def api_verificar_solicitacao_duplicada():
    """Rota AJAX para verificar solicitação duplicada antes de criar"""
    try:
        paciente_id = request.json.get('paciente_id', '').strip()
        tipo = request.json.get('tipo', '').strip()
        especialidade = request.json.get('especialidade', '').strip()
        
        if not paciente_id or not tipo or not especialidade:
            return jsonify({'encontradas': False}), 200
        
        # Resolve o ID do paciente
        paciente_id_resolvido = resolver_id_paciente(paciente_id)
        if not paciente_id_resolvido:
            return jsonify({'encontradas': False}), 200
        
        resultado = verificar_solicitacao_duplicada(paciente_id_resolvido, tipo, especialidade)
        
        if resultado:
            return jsonify(resultado), 200
        else:
            return jsonify({'encontradas': False}), 200
            
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pacientes')
def pacientes():
    pacientes_por_pagina = 30
    pagina = request.args.get('pagina', 1, type=int) or 1
    if pagina < 1:
        pagina = 1

    conn = conectar()
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM paciente')
    total_pacientes = c.fetchone()[0]
    total_paginas = max(1, (total_pacientes + pacientes_por_pagina - 1) // pacientes_por_pagina)

    if pagina > total_paginas:
        pagina = total_paginas

    offset = (pagina - 1) * pacientes_por_pagina
    c.execute(
        'SELECT * FROM paciente ORDER BY nome ASC LIMIT %s OFFSET %s',
        (pacientes_por_pagina, offset)
    )
    pacientes = c.fetchall()
    conn.close()

    return render_template(
        'pacientes.html',
        pacientes=pacientes,
        pagina_atual=pagina,
        total_paginas=total_paginas,
        total_pacientes=total_pacientes,
        paginas_visiveis=montar_paginas_visiveis(pagina, total_paginas),
    )

@app.route('/novo_paciente', methods=['GET', 'POST'])
def novo_paciente():
    if request.method == 'POST':
        cpf_input = request.form.get('cpf', '').strip()
        sus_input = request.form.get('sus', '').strip()
        cpf = normalizar_documento(cpf_input)
        sus = normalizar_documento(sus_input)
        nome = request.form['nome'].strip().upper()
        nascimento_raw = request.form['nascimento']
        nascimento = normalizar_data_para_iso(nascimento_raw)
        telefone = request.form.get('telefone', '').strip()
        oncologico = request.form.get('oncologico') == 'on'

        rua = request.form.get('rua', '').strip().upper()
        numero = request.form.get('numero', '').strip()
        bairro = request.form.get('bairro', '').strip().upper()

        if rua or numero or bairro:
            partes_endereco = []
            if rua:
                partes_endereco.append(rua)
            if numero:
                partes_endereco.append(f'Nº {numero}')
            if bairro:
                partes_endereco.append(f'Bairro {bairro}')
            endereco = ', '.join(partes_endereco)
        else:
            endereco = request.form.get('endereco', '').strip()

        form_data = {
            'cpf': cpf_input,
            'sus': sus_input,
            'nome': nome,
            'nascimento': nascimento_raw,
            'telefone': telefone,
            'oncologico': oncologico,
            'rua': rua,
            'numero': numero,
            'bairro': bairro,
        }

        ruas_catalogo = listar_sugestoes_endereco('rua')
        bairros_catalogo = listar_sugestoes_endereco('bairro')

        if not cpf and not sus:
            flash('Informe CPF ou Cartão SUS para cadastrar o paciente.', 'warning')
            return render_template('novo_paciente.html', form_data=form_data, ruas=ruas_catalogo, bairros=bairros_catalogo)

        if rua and rua not in ruas_catalogo and not apenas_admin():
            flash('A criação de nova rua é permitida apenas para administradores. Selecione uma opção existente.', 'warning')
            return render_template('novo_paciente.html', form_data=form_data, ruas=ruas_catalogo, bairros=bairros_catalogo)

        if bairro and bairro not in bairros_catalogo and not apenas_admin():
            flash('A criação de novo bairro é permitida apenas para administradores. Selecione uma opção existente.', 'warning')
            return render_template('novo_paciente.html', form_data=form_data, ruas=ruas_catalogo, bairros=bairros_catalogo)

        paciente_existente = buscar_paciente_existente_por_documentos(cpf=cpf, sus=sus)
        if paciente_existente:
            flash(
                f'Paciente já existe no sistema (ID: {formatar_identificador_paciente(paciente_existente[0])} - {paciente_existente[1]}).',
                'danger'
            )
            return render_template('novo_paciente.html', form_data=form_data, ruas=ruas_catalogo, bairros=bairros_catalogo)

        # Prioridade: se CPF preenchido, usar como id; senão, usar SUS
        id = formatar_identificador_paciente(cpf) if cpf else sus
        conn = conectar()
        c = conn.cursor()

        try:
            c.execute("INSERT INTO paciente (id, nome, nascimento, telefone, endereco, sus, oncologico) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                      (id, nome, nascimento, telefone, endereco, sus if sus else None, oncologico))
            # Salva rua e bairro como sugestões para futuros cadastros (somente admin)
            if apenas_admin() and rua and rua not in ruas_catalogo:
                c.execute(
                    'INSERT INTO sugestao_endereco (tipo, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                    ('rua', rua)
                )
            if apenas_admin() and bairro and bairro not in bairros_catalogo:
                c.execute(
                    'INSERT INTO sugestao_endereco (tipo, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                    ('bairro', bairro)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            flash('Não foi possível cadastrar o paciente. Verifique os dados e tente novamente.', 'danger')
            return render_template('novo_paciente.html', form_data=form_data, ruas=ruas_catalogo, bairros=bairros_catalogo)
        conn.close()
        flash('Paciente cadastrado com sucesso!', 'success')
        return redirect(url_for('pacientes'))
    return render_template(
        'novo_paciente.html',
        ruas=listar_sugestoes_endereco('rua'),
        bairros=listar_sugestoes_endereco('bairro'),
    )

@app.route('/admin/endereco-sugestao', methods=['POST'])
@login_required_admin
def adicionar_sugestao_endereco_admin():
    tipo = request.form.get('tipo', '').strip().lower()
    valor = request.form.get('valor', '').strip().upper()

    if tipo not in ('rua', 'bairro'):
        flash('Tipo de sugestão inválido.', 'warning')
        return redirect(url_for('novo_paciente'))

    if not valor:
        flash('Informe o valor para adicionar ao catálogo.', 'warning')
        return redirect(url_for('novo_paciente'))

    conn = conectar()
    c = conn.cursor()
    c.execute(
        'INSERT INTO sugestao_endereco (tipo, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING',
        (tipo, valor)
    )
    inseriu = c.rowcount > 0
    conn.commit()
    conn.close()

    if inseriu:
        mensagem_tipo = 'Bairro adicionado' if tipo == 'bairro' else 'Rua adicionada'
        flash(f'{mensagem_tipo} com sucesso ao catálogo.', 'success')
    else:
        flash(f'Esse {tipo} já existe no catálogo.', 'info')

    return redirect(url_for('novo_paciente'))

@app.route('/paciente/<paciente_id>/editar', methods=['GET', 'POST'])
def editar_paciente(paciente_id):
    paciente_id_resolvido = resolver_id_paciente(paciente_id)
    if not paciente_id_resolvido:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('pacientes'))

    conn = conectar()
    c = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip().upper()
        telefone = request.form.get('telefone', '').strip()
        sus = normalizar_documento(request.form.get('sus', '').strip())
        oncologico = request.form.get('oncologico') == 'on'
        endereco = request.form.get('endereco', '').strip().upper()

        if not nome:
            conn.close()
            flash('O nome do paciente é obrigatório.', 'warning')
            return redirect(url_for('editar_paciente', paciente_id=paciente_id_resolvido))

        c.execute(
            'UPDATE paciente SET nome = %s, telefone = %s, sus = %s, oncologico = %s, endereco = %s WHERE id = %s',
            (nome, telefone, sus if sus else None, oncologico, endereco, paciente_id_resolvido)
        )
        conn.commit()
        conn.close()

        flash('Paciente atualizado com sucesso!', 'success')
        return redirect(url_for('pacientes'))

    c.execute(
        'SELECT id, nome, nascimento, telefone, endereco, sus, oncologico FROM paciente WHERE id = %s',
        (paciente_id_resolvido,)
    )
    paciente = c.fetchone()
    conn.close()

    if not paciente:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('pacientes'))

    return render_template('editar_paciente.html', paciente=paciente)

@app.route('/paciente/<paciente_id>')
def historico_paciente(paciente_id):
    paciente_id_resolvido = resolver_id_paciente(paciente_id)
    if not paciente_id_resolvido:
        flash('Paciente não encontrado.', 'warning')
        return redirect(url_for('pacientes'))

    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT id, nome FROM paciente WHERE id = %s', (paciente_id_resolvido,))
    paciente = c.fetchone()
    c.execute(
        '''
        SELECT
            MIN(id) AS id,
            data_solicitacao,
            data_entrada,
            tipo,
            especialidade,
            prioridade,
            status,
            data_realizacao,
            unidade_realizadora,
            conclusao,
            financiamento,
            COUNT(*) FILTER (WHERE UPPER(COALESCE(conclusao, '')) <> 'CANCELADO') AS quantidade_solicitacoes
        FROM solicitacao
        WHERE paciente_id = %s
        GROUP BY data_solicitacao, data_entrada, tipo, especialidade, prioridade, status, data_realizacao, unidade_realizadora, conclusao, financiamento
        ORDER BY data_entrada DESC, status ASC
        ''',
        (paciente_id_resolvido,)
    )
    historico = c.fetchall()
    conn.close()
    return render_template('historico_paciente.html', paciente_id=paciente_id_resolvido, paciente=paciente, historico=historico)

@app.route('/solicitacao/<int:solicitacao_id>/termo-retirada')
def termo_retirada_solicitacao(solicitacao_id):
    data_retirada_raw = request.args.get('data_retirada', '').strip()
    data_retirada = normalizar_data_para_iso(data_retirada_raw) if data_retirada_raw else datetime.now().strftime('%Y-%m-%d')

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT
            s.id,
            s.paciente_id,
            p.nome,
            s.especialidade,
            s.data_entrada
        FROM solicitacao s
        INNER JOIN paciente p ON p.id = s.paciente_id
        WHERE s.id = %s
        ''',
        (solicitacao_id,)
    )
    solicitacao = c.fetchone()
    conn.close()

    if not solicitacao:
        flash('Solicitação não encontrada para gerar o termo de retirada.', 'warning')
        return redirect(url_for('solicitacoes'))

    pdf_content = gerar_pdf_termo_retirada_solicitacao(
        paciente_nome=solicitacao[2],
        paciente_id=solicitacao[1],
        especialidade=solicitacao[3],
        data_entrada=solicitacao[4],
        data_retirada=data_retirada,
        solicitacao_id=solicitacao[0],
    )

    nome_arquivo = f"termo_retirada_{solicitacao[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        pdf_content,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename={nome_arquivo}'
        }
    )

@app.route('/solicitacao/<int:solicitacao_id>/editar', methods=['GET', 'POST'])
def editar_solicitacao(solicitacao_id):
    conn = conectar()
    c = conn.cursor()

    if request.method == 'POST':
        paciente_id = request.form.get('paciente_id', '').strip()
        data_realizacao = normalizar_data_para_iso(request.form.get('data_realizacao'))
        unidade_realizadora = request.form.get('unidade_realizadora', '').strip().upper()
        financiamento = request.form.get('financiamento', '').strip().upper()
        conclusao = request.form.get('conclusao', '').strip().upper()

        opcoes_conclusao = {'PRESENTE', 'AUSENTE', 'CANCELADO', 'RETIRADO', 'DUPLICADA'}
        conclusao = conclusao if conclusao in opcoes_conclusao else None
        opcoes_financiamento = {'SUS', 'CONVENIO'}
        financiamento = financiamento if financiamento in opcoes_financiamento else None

        # Buscar dados da solicitação original
        c.execute(
            '''
            SELECT paciente_id, data_solicitacao, tipo, especialidade
            FROM solicitacao
            WHERE id = %s
            ''',
            (solicitacao_id,)
        )
        solicitacao_info = c.fetchone()
        
        if solicitacao_info:
            orig_paciente_id, data_solicitacao, tipo, especialidade = solicitacao_info

            if conclusao == 'DUPLICADA':
                # Excluir o registro atual quando houver outra solicitação duplicada para o mesmo paciente.
                c.execute(
                    '''
                    SELECT id
                    FROM solicitacao
                    WHERE paciente_id = %s AND data_solicitacao = %s AND tipo = %s AND especialidade = %s AND id <> %s
                    LIMIT 1
                    ''',
                    (orig_paciente_id, data_solicitacao, tipo, especialidade, solicitacao_id)
                )
                registro_duplicado = c.fetchone()
                if registro_duplicado:
                    c.execute('DELETE FROM solicitacao WHERE id = %s', (solicitacao_id,))
                else:
                    c.execute(
                        '''
                        UPDATE solicitacao
                        SET data_realizacao = %s, unidade_realizadora = %s, conclusao = %s, financiamento = %s 
                        WHERE id = %s
                        ''',
                        (
                            data_realizacao if data_realizacao else None,
                            unidade_realizadora if unidade_realizadora else None,
                            conclusao,
                            financiamento,
                            solicitacao_id
                        )
                    )
            else:
                # Aplicar a mesma ação para todas as solicitações do mesmo paciente 
                # com a mesma especialidade, mesmo tipo e mesma data de solicitação
                c.execute(
                    '''
                    UPDATE solicitacao 
                    SET data_realizacao = %s, unidade_realizadora = %s, conclusao = %s, financiamento = %s 
                    WHERE paciente_id = %s AND data_solicitacao = %s AND tipo = %s AND especialidade = %s
                    ''',
                    (
                        data_realizacao if data_realizacao else None,
                        unidade_realizadora if unidade_realizadora else None,
                        conclusao,
                        financiamento,
                        orig_paciente_id,
                        data_solicitacao,
                        tipo,
                        especialidade
                    )
                )
        
        conn.commit()

        if not paciente_id:
            if solicitacao_info:
                paciente_id = solicitacao_info[0]
            else:
                c.execute('SELECT paciente_id FROM solicitacao WHERE id = %s', (solicitacao_id,))
                linha = c.fetchone()
                paciente_id = linha[0] if linha else ''

        paciente_id = resolver_id_paciente(paciente_id) or paciente_id

        conn.close()
        if paciente_id:
            return redirect(url_for('historico_paciente', paciente_id=paciente_id))
        return redirect(url_for('solicitacoes'))

    c.execute(
        '''
        SELECT id, paciente_id, data_solicitacao, data_entrada, tipo, especialidade, prioridade, status, data_realizacao, unidade_realizadora, conclusao, financiamento
        FROM solicitacao
        WHERE id = %s
        ''',
        (solicitacao_id,)
    )
    solicitacao = c.fetchone()
    conn.close()

    if not solicitacao:
        return redirect(url_for('solicitacoes'))

    paciente_id = resolver_id_paciente(request.args.get('paciente_id', solicitacao[1])) or solicitacao[1]
    return render_template('editar_solicitacao.html', solicitacao=solicitacao, paciente_id=paciente_id)

@app.route('/solicitacoes')
def solicitacoes():
    pagina = request.args.get('pagina', 1, type=int) or 1
    cpf = request.args.get('cpf', '').strip()
    sus = request.args.get('sus', '').strip()
    especialidade = request.args.get('especialidade', '').strip()
    prioridade = request.args.get('prioridade', '').strip()
    status = request.args.get('status', '').strip()
    lista_solicitacoes, modo_urgencia_em_espera, mostrar_tipos_radiografia, total_retorno_agendado, retorno_agendado_registros = consultar_solicitacoes(cpf, sus, especialidade, prioridade, status)
    paginacao = paginar_registros(lista_solicitacoes, pagina)

    return render_template('solicitacoes.html', solicitacoes=paginacao['registros'],
        cpf=cpf, sus=sus, especialidade=especialidade, prioridade=prioridade, status=status,
        total_retorno_agendado=total_retorno_agendado,
        retorno_agendado_registros=retorno_agendado_registros,
        modo_urgencia_em_espera=modo_urgencia_em_espera, mostrar_filtros=False,
        mostrar_tipos_radiografia=mostrar_tipos_radiografia,
        pagina_atual=paginacao['pagina_atual'], total_paginas=paginacao['total_paginas'],
        total_registros=paginacao['total_registros'], itens_por_pagina=paginacao['itens_por_pagina'],
        inicio_exibicao=paginacao['inicio_exibicao'], fim_exibicao=paginacao['fim_exibicao'],
        paginas_visiveis=paginacao['paginas_visiveis'], rota_paginacao='solicitacoes')

@app.route('/pesquisar')
def pesquisar():
    pagina = request.args.get('pagina', 1, type=int) or 1
    cpf = request.args.get('cpf', '').strip()
    sus = request.args.get('sus', '').strip()
    especialidade = request.args.get('especialidade', '').strip()
    prioridade = request.args.get('prioridade', '').strip()
    status = request.args.get('status', '').strip()

    lista_solicitacoes, modo_urgencia_em_espera, mostrar_tipos_radiografia, total_retorno_agendado, retorno_agendado_registros = consultar_solicitacoes(cpf, sus, especialidade, prioridade, status)
    paginacao = paginar_registros(lista_solicitacoes, pagina)

    return render_template('solicitacoes.html', solicitacoes=paginacao['registros'],
        cpf=cpf, sus=sus, especialidade=especialidade, prioridade=prioridade, status=status,
        total_retorno_agendado=total_retorno_agendado,
        retorno_agendado_registros=retorno_agendado_registros,
        modo_urgencia_em_espera=modo_urgencia_em_espera, mostrar_filtros=True,
        mostrar_tipos_radiografia=mostrar_tipos_radiografia,
        pagina_atual=paginacao['pagina_atual'], total_paginas=paginacao['total_paginas'],
        total_registros=paginacao['total_registros'], itens_por_pagina=paginacao['itens_por_pagina'],
        inicio_exibicao=paginacao['inicio_exibicao'], fim_exibicao=paginacao['fim_exibicao'],
        paginas_visiveis=paginacao['paginas_visiveis'], rota_paginacao='pesquisar')

@app.route('/relatorios')
def relatorios():
    tipo = request.args.get('tipo', '').strip().upper()
    especialidade = request.args.get('especialidade', '').strip()
    situacao = request.args.get('situacao', 'REALIZADOS').strip().upper()
    data_inicio_raw = request.args.get('data_inicio', '').strip()
    data_fim_raw = request.args.get('data_fim', '').strip()
    formato = request.args.get('formato', 'html').strip().lower()

    if situacao not in ('REALIZADOS', 'EM_ESPERA'):
        situacao = 'REALIZADOS'

    data_inicio = normalizar_data_para_iso(data_inicio_raw) if data_inicio_raw else ''
    data_fim = normalizar_data_para_iso(data_fim_raw) if data_fim_raw else ''
    financiamento = request.args.get('financiamento', '').strip().upper()
    financiamento = financiamento if financiamento in ('SUS', 'CONVENIO') else ''
    tempo_espera = request.args.get('tempo_espera', '').strip() == '1'

    filtros_aplicados = bool(tipo or especialidade or data_inicio_raw or data_fim_raw or situacao == 'EM_ESPERA' or financiamento or tempo_espera)

    query_resumo = '''
        SELECT
            s.especialidade,
            COUNT(*) AS total_registros
        FROM solicitacao s
        WHERE UPPER(s.tipo) IN ('CONSULTA', 'EXAME')
          AND UPPER(COALESCE(s.conclusao, '')) <> 'CANCELADO'
    '''
    params_resumo = []

    if situacao == 'EM_ESPERA':
        query_resumo += " AND (s.data_realizacao IS NULL OR TRIM(s.data_realizacao) = '')"
    else:
        query_resumo += " AND s.data_realizacao IS NOT NULL AND TRIM(s.data_realizacao) <> ''"

    if tipo in ('CONSULTA', 'EXAME'):
        query_resumo += ' AND UPPER(s.tipo) = %s'
        params_resumo.append(tipo)

    if financiamento:
        query_resumo += " AND UPPER(COALESCE(s.financiamento, '')) = %s"
        params_resumo.append(financiamento)

    if especialidade:
        query_resumo += (
            " AND translate(UPPER(COALESCE(s.especialidade, '')), "
            "'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ', "
            "'AAAAAEEEEIIIIOOOOOUUUUC') LIKE %s"
        )
        valor_busca = normalizar_texto_busca(especialidade)
        params_resumo.append(f"%{valor_busca}%")

    if data_inicio:
        if situacao == 'EM_ESPERA':
            query_resumo += ' AND s.data_entrada >= %s'
        else:
            query_resumo += ' AND s.data_realizacao >= %s'
        params_resumo.append(data_inicio)

    if data_fim:
        if situacao == 'EM_ESPERA':
            query_resumo += ' AND s.data_entrada <= %s'
        else:
            query_resumo += ' AND s.data_realizacao <= %s'
        params_resumo.append(data_fim)

    query_resumo += ' GROUP BY s.especialidade ORDER BY total_registros DESC, s.especialidade'

    conn = conectar()
    c = conn.cursor()
    c.execute(query_resumo, params_resumo)
    resumo = c.fetchall()

    tempo_medio_espera = []
    if tempo_espera:
        query_tempo = '''
            SELECT
                UPPER(s.tipo) AS tipo,
                AVG(DATE(s.data_realizacao) - DATE(s.data_entrada))::numeric(10,1) AS tempo_medio_dias
            FROM solicitacao s
            WHERE UPPER(s.tipo) IN ('CONSULTA', 'EXAME')
              AND UPPER(COALESCE(s.conclusao, '')) <> 'CANCELADO'
        '''
        params_tempo = []

        if tipo in ('CONSULTA', 'EXAME'):
            query_tempo += ' AND UPPER(s.tipo) = %s'
            params_tempo.append(tipo)

        if financiamento:
            query_tempo += " AND UPPER(COALESCE(s.financiamento, '')) = %s"
            params_tempo.append(financiamento)

        if especialidade:
            query_tempo += (
                " AND translate(UPPER(COALESCE(s.especialidade, '')), "
                "'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ', "
                "'AAAAAEEEEIIIIOOOOOUUUUC') LIKE %s"
            )
            params_tempo.append(f"%{normalizar_texto_busca(especialidade)}%")

        if situacao == 'EM_ESPERA':
            query_tempo += " AND (s.data_realizacao IS NULL OR TRIM(s.data_realizacao) = '')"
        else:
            query_tempo += " AND s.data_realizacao IS NOT NULL AND TRIM(s.data_realizacao) <> ''"

        if data_inicio:
            if situacao == 'EM_ESPERA':
                query_tempo += ' AND s.data_entrada >= %s'
            else:
                query_tempo += ' AND s.data_realizacao >= %s'
            params_tempo.append(data_inicio)

        if data_fim:
            if situacao == 'EM_ESPERA':
                query_tempo += ' AND s.data_entrada <= %s'
            else:
                query_tempo += ' AND s.data_realizacao <= %s'
            params_tempo.append(data_fim)

        query_tempo += ' GROUP BY UPPER(s.tipo) ORDER BY UPPER(s.tipo)'
        c.execute(query_tempo, params_tempo)
        tempo_medio_espera = c.fetchall()

    conn.close()

    if formato == 'csv':
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'Especialidade',
            'Quantidade Realizada'
        ])

        for r in resumo:
            writer.writerow([
                r[0] if r[0] else '',
                r[1]
            ])

        csv_content = output.getvalue()
        output.close()

        prefixo_arquivo = 'relatorio_em_espera' if situacao == 'EM_ESPERA' else 'relatorio_realizados'
        nome_arquivo = f"{prefixo_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            '\ufeff' + csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={nome_arquivo}'
            }
        )

    if formato == 'pdf':
        total_registros = sum(item[1] for item in resumo) if resumo else 0
        pdf_content = gerar_pdf_relatorio_resumo(
            resumo,
            tipo,
            especialidade,
            data_inicio_raw,
            data_fim_raw,
            total_registros
        )
        prefixo_arquivo = 'relatorio_em_espera' if situacao == 'EM_ESPERA' else 'relatorio_realizados'
        nome_arquivo = f"{prefixo_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={nome_arquivo}'
            }
        )

    total_registros = sum(item[1] for item in resumo) if resumo else 0

    pacientes_especialidade = []
    mostrar_tipos_radiografia_relatorio = 'RADIOGRAFIA' in normalizar_texto_busca(especialidade)
    if especialidade:
        tipos_radiografia_expr = 'NULL AS tipos_radiografia'
        if mostrar_tipos_radiografia_relatorio:
            tipos_radiografia_expr = '''
                STRING_AGG(s.especialidade, '||' ORDER BY s.data_entrada DESC, s.id DESC) AS tipos_radiografia
            '''

        query_pacientes = '''
            SELECT
                p.id,
                p.nome,
                COUNT(s.id) AS total_solicitacoes,
                {tipos_radiografia_expr}
            FROM paciente p
            INNER JOIN solicitacao s ON s.paciente_id = p.id
            WHERE UPPER(s.tipo) IN ('CONSULTA', 'EXAME')
              AND UPPER(COALESCE(s.conclusao, '')) <> 'CANCELADO'
              AND translate(UPPER(COALESCE(s.especialidade, '')),
                    'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                    'AAAAAEEEEIIIIOOOOOUUUUC') LIKE %s
        '''.format(tipos_radiografia_expr=tipos_radiografia_expr)
        params_pacientes = [f"%{normalizar_texto_busca(especialidade)}%"]

        if financiamento:
            query_pacientes += " AND UPPER(COALESCE(s.financiamento, '')) = %s"
            params_pacientes.append(financiamento)

        if situacao == 'EM_ESPERA':
            query_pacientes += " AND (s.data_realizacao IS NULL OR TRIM(s.data_realizacao) = '')"
        else:
            query_pacientes += " AND s.data_realizacao IS NOT NULL AND TRIM(s.data_realizacao) <> ''"

        if tipo in ('CONSULTA', 'EXAME'):
            query_pacientes += ' AND UPPER(s.tipo) = %s'
            params_pacientes.append(tipo)

        if data_inicio:
            if situacao == 'EM_ESPERA':
                query_pacientes += ' AND s.data_entrada >= %s'
            else:
                query_pacientes += ' AND s.data_realizacao >= %s'
            params_pacientes.append(data_inicio)

        if data_fim:
            if situacao == 'EM_ESPERA':
                query_pacientes += ' AND s.data_entrada <= %s'
            else:
                query_pacientes += ' AND s.data_realizacao <= %s'
            params_pacientes.append(data_fim)

        query_pacientes += ' GROUP BY p.id, p.nome ORDER BY p.nome ASC'

        conn = conectar()
        c = conn.cursor()
        c.execute(query_pacientes, params_pacientes)
        pacientes_especialidade = c.fetchall()
        conn.close()

    return render_template(
        'relatorios.html',
        tipo=tipo,
        especialidade=especialidade,
        situacao=situacao,
        data_inicio=data_inicio_raw,
        data_fim=data_fim_raw,
        financiamento=financiamento,
        tempo_espera=tempo_espera,
        filtros_aplicados=filtros_aplicados,
        resumo=resumo,
        total_registros=total_registros,
        pacientes_especialidade=pacientes_especialidade,
        tempo_medio_espera=tempo_medio_espera,
        mostrar_tipos_radiografia_relatorio=mostrar_tipos_radiografia_relatorio
    )

@app.route('/nova_solicitacao', methods=['GET', 'POST'])
def nova_solicitacao():
    form_data = {
        'paciente_id': request.form.get('paciente_id', '').strip(),
        'data_solicitacao': request.form.get('data_solicitacao', '').strip(),
        'data_entrada': request.form.get('data_entrada', '').strip(),
        'tipo': request.form.get('tipo', ''),
        'especialidade': request.form.get('especialidade', '').strip(),
        'especialidades_multiplas': request.form.getlist('especialidades_multiplas'),
        'prioridade': request.form.get('prioridade', ''),
        'status': request.form.get('status', ''),
        'sistema_insercao': request.form.get('sistema_insercao', '').strip(),
        'quantidade_solicitacoes': request.form.get('quantidade_solicitacoes', '1').strip(),
        'data_insercao': request.form.get('data_insercao', '').strip(),
        'data_retorno': request.form.get('data_retorno', '').strip(),
    }

    if request.method == 'POST':
        paciente_id = form_data['paciente_id']
        paciente_id_resolvido = resolver_id_paciente(paciente_id)
        data_solicitacao = normalizar_data_para_iso(form_data['data_solicitacao'])
        data_entrada = normalizar_data_para_iso(form_data['data_entrada'])
        data_insercao = datetime.now().strftime('%Y-%m-%d')
        tipo = request.form['tipo']
        especialidade = request.form.get('especialidade', '').strip().upper()
        especialidades_multiplas = [e.strip().upper() for e in request.form.getlist('especialidades_multiplas') if e.strip()]
        prioridade = request.form['prioridade']
        encaminhamento = request.form.get('encaminhamento', '').upper() if request.form.get('encaminhamento') else None
        status = request.form['status']
        sistema_insercao = request.form.get('sistema_insercao', '').strip().upper() or None
        quantidade_raw = request.form.get('quantidade_solicitacoes', '1').strip()
        try:
            quantidade_solicitacoes = int(quantidade_raw)
        except (TypeError, ValueError):
            quantidade_solicitacoes = 1
        data_insercao_form = request.form.get('data_insercao', '').strip()
        if data_insercao_form:
            data_insercao = normalizar_data_para_iso(data_insercao_form) or datetime.now().strftime('%Y-%m-%d')
        data_realizacao = normalizar_data_para_iso(request.form.get('data_realizacao'))
        data_retorno = normalizar_data_para_iso(request.form.get('data_retorno'))
        unidade_realizadora = request.form.get('unidade_realizadora', '').upper() if request.form.get('unidade_realizadora') else None

        # Validar datas futuras
        if data_solicitacao and eh_data_futura(data_solicitacao):
            flash('Data de Solicitação não pode ser no futuro.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if data_entrada and eh_data_futura(data_entrada):
            flash('Data de Entrada não pode ser no futuro.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if data_insercao and eh_data_futura(data_insercao):
            flash('Data de Inserção não pode ser no futuro.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if status == 'RETORNO' and not data_retorno:
            flash('Informe a data de previsão de retorno quando o status for Retorno.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if not paciente_id_resolvido:
            flash('Paciente não encontrado. Selecione um paciente válido pelo CPF, SUS ou nome.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if quantidade_solicitacoes < 1:
            flash('A quantidade de solicitações deve ser maior ou igual a 1.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if quantidade_solicitacoes > 100:
            flash('Quantidade máxima permitida por envio: 100 solicitações.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if len(especialidades) == 1 and quantidade_solicitacoes > 1 and not permite_replicar_solicitacao(tipo, especialidades[0]):
            flash(
                'A replicação em quantidade é permitida apenas para exames anatomopatológicos e laboratoriais.',
                'warning'
            )
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if tipo == 'EXAME':
            if not especialidades_multiplas and especialidade:
                especialidades = [e.strip().upper() for e in re.split(r'[;,]+', especialidade) if e.strip()]
            else:
                especialidades = especialidades_multiplas
        else:
            especialidades = [especialidade] if especialidade else []

        if not especialidades:
            flash('Informe a especialidade/descrição da solicitação.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        if not sistema_insercao:
            flash('Informe o sistema de inserção.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=listar_especialidades(),
                sistemas_insercao=listar_sistemas_insercao(),
                form_data=form_data,
            )

        especialidades_catalogo = listar_especialidades()
        especialidades_invalidas = [esp for esp in especialidades if esp not in especialidades_catalogo]
        sistemas_catalogo = listar_sistemas_insercao()
        sistema_existe_catalogo = sistema_insercao in sistemas_catalogo

        if especialidades_invalidas and not apenas_admin():
            flash('A criação de nova especialidade é permitida apenas para administradores. Selecione apenas especialidades existentes.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=especialidades_catalogo,
                sistemas_insercao=sistemas_catalogo,
                form_data=form_data,
            )

        if not sistema_existe_catalogo and not apenas_admin():
            flash('A criação de novo sistema de inserção é permitida apenas para administradores. Selecione uma opção existente.', 'warning')
            return render_template(
                'nova_solicitacao.html',
                especialidades=especialidades_catalogo,
                sistemas_insercao=sistemas_catalogo,
                form_data=form_data,
            )

        conn = conectar()
        c = conn.cursor()
        solicitacoes_criadas = 0
        for especialidade_item in especialidades:
            c.execute(
                "INSERT INTO solicitacao (paciente_id, data_solicitacao, data_entrada, data_insercao, data_realizacao, data_retorno, unidade_realizadora, tipo, especialidade, descricao, prioridade, encaminhamento, status, sistema_insercao) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    paciente_id_resolvido,
                    data_solicitacao,
                    data_entrada,
                    data_insercao,
                    data_realizacao,
                    data_retorno,
                    unidade_realizadora,
                    tipo,
                    especialidade_item,
                    especialidade_item,
                    prioridade,
                    encaminhamento,
                    status,
                    sistema_insercao,
                )
            )
            solicitacoes_criadas += 1
        if apenas_admin():
            for especialidade_item in especialidades:
                if especialidade_item not in especialidades_catalogo:
                    c.execute(
                        '''
                        INSERT INTO sugestao_solicitacao (tipo, valor)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        ''',
                        ('especialidade', especialidade_item)
                    )
        if apenas_admin() and not sistema_existe_catalogo:
            c.execute(
                '''
                INSERT INTO sugestao_solicitacao (tipo, valor)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                ''',
                ('sistema_insercao', sistema_insercao)
            )
        conn.commit()
        conn.close()
        if solicitacoes_criadas > 1:
            flash(f'{solicitacoes_criadas} solicitações criadas com sucesso para o paciente.', 'success')
        else:
            flash('Solicitação criada com sucesso.', 'success')
        return redirect(url_for('solicitacoes'))
    return render_template(
        'nova_solicitacao.html',
        especialidades=listar_especialidades(),
        sistemas_insercao=listar_sistemas_insercao(),
        form_data=form_data,
    )

@app.route('/admin/especialidades', methods=['POST'])
@login_required_admin
def adicionar_especialidade_admin():
    especialidade = request.form.get('especialidade_nova', '').strip().upper()
    if not especialidade:
        flash('Informe a especialidade para adicionar ao catálogo.', 'warning')
        return redirect(url_for('nova_solicitacao'))

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO sugestao_solicitacao (tipo, valor)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        ''',
        ('especialidade', especialidade)
    )
    inseriu = c.rowcount > 0
    conn.commit()
    conn.close()

    if inseriu:
        flash('Especialidade adicionada com sucesso ao catálogo.', 'success')
    else:
        flash('Essa especialidade já existe no catálogo.', 'info')

    return redirect(url_for('nova_solicitacao'))

@app.route('/admin/sistemas-insercao', methods=['POST'])
@login_required_admin
def adicionar_sistema_insercao_admin():
    sistema_insercao = request.form.get('sistema_insercao_novo', '').strip().upper()
    if not sistema_insercao:
        flash('Informe o sistema de inserção para adicionar ao catálogo.', 'warning')
        return redirect(url_for('nova_solicitacao'))

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO sugestao_solicitacao (tipo, valor)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        ''',
        ('sistema_insercao', sistema_insercao)
    )
    inseriu = c.rowcount > 0
    conn.commit()
    conn.close()

    if inseriu:
        flash('Sistema de inserção adicionado com sucesso ao catálogo.', 'success')
    else:
        flash('Esse sistema de inserção já existe no catálogo.', 'info')

    return redirect(url_for('nova_solicitacao'))

@app.route('/api/buscar_paciente')
def api_buscar_paciente():
    termo = request.args.get('termo', '').strip()
    if len(termo) < 3:
        return jsonify([])

    termo_normalizado = normalizar_documento(termo)

    conn = conectar()
    c = conn.cursor()
    if termo_normalizado:
        c.execute(
            """
            SELECT id, nome
            FROM paciente
            WHERE regexp_replace(COALESCE(id, ''), '\\D', '', 'g') LIKE %s
               OR regexp_replace(COALESCE(sus, ''), '\\D', '', 'g') LIKE %s
               OR id ILIKE %s
               OR sus ILIKE %s
               OR nome ILIKE %s
            ORDER BY nome
            LIMIT 10
            """,
            (f"%{termo_normalizado}%", f"%{termo_normalizado}%", f"%{termo}%", f"%{termo}%", f"%{termo}%")
        )
    else:
        c.execute(
            """
            SELECT id, nome
            FROM paciente
            WHERE id ILIKE %s OR sus ILIKE %s OR nome ILIKE %s
            ORDER BY nome
            LIMIT 10
            """,
            (f"%{termo}%", f"%{termo}%", f"%{termo}%")
        )
    pacientes = c.fetchall()
    conn.close()

    resultado = [{'id': formatar_identificador_paciente(p[0]), 'nome': p[1]} for p in pacientes]
    return jsonify(resultado)

@app.route('/api/verificar_paciente_existente')
def api_verificar_paciente_existente():
    cpf = normalizar_documento(request.args.get('cpf', '').strip())
    sus = normalizar_documento(request.args.get('sus', '').strip())

    paciente = buscar_paciente_existente_por_documentos(cpf=cpf, sus=sus)

    if not paciente:
        return jsonify({'existe': False})

    return jsonify({
        'existe': True,
        'id': formatar_identificador_paciente(paciente[0]),
        'nome': paciente[1],
    })

@app.route('/api/sugestoes_endereco')
def api_sugestoes_endereco():
    campo = request.args.get('campo', '').strip()
    termo = request.args.get('termo', '').strip()

    if campo not in ('rua', 'bairro'):
        return jsonify([])

    if len(termo) < 1:
        return jsonify([])

    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT DISTINCT valor
        FROM sugestao_endereco
        WHERE tipo = %s
          AND valor ILIKE %s
        ORDER BY valor
        LIMIT 10
        ''',
        (campo, f'%{termo}%')
    )
    resultados = c.fetchall()
    conn.close()

    return jsonify([r[0] for r in resultados if r and r[0]])

@app.route('/api/sugestoes_solicitacao')
def api_sugestoes_solicitacao():
    campo = request.args.get('campo', '').strip()
    termo = request.args.get('termo', '').strip()

    if campo not in ('especialidade', 'unidade_realizadora'):
        return jsonify([])

    conn = conectar()
    c = conn.cursor()

    if campo == 'especialidade':
        if len(termo) < 1:
            conn.close()
            return jsonify([])

        filtro = f'%{termo}%'
        c.execute(
            '''
            SELECT DISTINCT TRIM(valor) AS valor
            FROM sugestao_solicitacao
            WHERE tipo = 'especialidade'
              AND TRIM(valor) <> ''
              AND valor ILIKE %s
            ORDER BY valor
            LIMIT 30
            ''',
            (filtro,)
        )
    else:
        if len(termo) < 1:
            conn.close()
            return jsonify([])

        c.execute(
            '''
            SELECT DISTINCT TRIM(unidade_realizadora) AS valor
            FROM solicitacao
            WHERE unidade_realizadora IS NOT NULL
              AND TRIM(unidade_realizadora) <> ''
              AND unidade_realizadora ILIKE %s
            ORDER BY valor
            LIMIT 10
            ''',
            (f"%{termo}%",)
        )

    resultados = c.fetchall()
    conn.close()

    return jsonify([r[0] for r in resultados if r and r[0]])

@app.route('/api/alertas_antigos')
def api_alertas_antigos():
    if not usuario_logado():
        return jsonify([])
    conn = conectar()
    c = conn.cursor()
    c.execute(
        '''
        SELECT s.tipo, s.especialidade, s.data_solicitacao, p.nome, p.id
        FROM solicitacao s
        INNER JOIN paciente p ON p.id = s.paciente_id
        WHERE (s.data_realizacao IS NULL OR TRIM(s.data_realizacao) = '')
          AND s.especialidade IS NOT NULL
          AND TRIM(s.especialidade) <> ''
        ORDER BY s.data_solicitacao ASC NULLS LAST, s.data_entrada ASC NULLS LAST
        LIMIT 30
        '''
    )
    rows = c.fetchall()
    conn.close()
    resultado = []
    for row in rows:
        tipo, especialidade, data_sol, nome_paciente, paciente_id = row
        data_fmt = ''
        if data_sol:
            try:
                data_fmt = datetime.strptime(str(data_sol).strip(), '%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                data_fmt = str(data_sol)
        rotulo = tipo.capitalize() if tipo else 'Solicitação'
        resultado.append({
            'texto': f'{rotulo} em {especialidade} — {data_fmt}',
            'paciente': nome_paciente or '',
            'data': data_fmt,
            'paciente_id': paciente_id or '',
        })
    return jsonify(resultado)

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required_admin
def usuarios():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        username = request.form.get('username', '').strip()
        senha = request.form.get('senha', '')
        perfil = request.form.get('perfil', 'OPERADOR').strip().upper()

        if not nome or not username or not senha:
            flash('Preencha nome, usuário e senha.', 'warning')
            return redirect(url_for('usuarios'))

        if perfil not in ('ADMIN', 'OPERADOR'):
            perfil = 'OPERADOR'

        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT id FROM usuario WHERE username = %s', (username,))
        if c.fetchone():
            conn.close()
            flash('Nome de usuário já existe. Use outro.', 'danger')
            return redirect(url_for('usuarios'))

        c.execute(
            'INSERT INTO usuario (nome, username, senha_hash, perfil, ativo) VALUES (%s, %s, %s, %s, %s)',
            (nome, username, generate_password_hash(senha), perfil, True)
        )
        conn.commit()
        conn.close()
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('usuarios'))

    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT id, nome, username, perfil, ativo, criado_em FROM usuario ORDER BY id DESC')
    lista_usuarios = c.fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/admin/pacientes', methods=['GET', 'POST'])
@login_required_admin
def admin_pacientes():
    conn = conectar()
    c = conn.cursor()
    mensagem = None
    if request.method == 'POST':
        paciente_id = request.form.get('paciente_id')
        if paciente_id:
            # Verifica se o paciente existe
            c.execute('SELECT nome FROM paciente WHERE id = %s', (paciente_id,))
            paciente = c.fetchone()
            if paciente:
                # Remove todas as solicitações do paciente (ou só o paciente, se preferir manter histórico)
                c.execute('DELETE FROM solicitacao WHERE paciente_id = %s', (paciente_id,))
                c.execute('DELETE FROM paciente WHERE id = %s', (paciente_id,))
                conn.commit()
                mensagem = f'Paciente {paciente[0]} excluído com sucesso.'
            else:
                mensagem = 'Paciente não encontrado.'
    c.execute('SELECT id, nome, nascimento FROM paciente ORDER BY nome ASC')
    pacientes = c.fetchall()
    conn.close()
    return render_template('admin_pacientes.html', pacientes=pacientes, mensagem=mensagem)

# ======================== ROTAS DE IA ========================

@app.route('/ia_chat')
def ia_chat():
    """Página de chat com IA"""
    if not usuario_logado():
        return redirect(url_for('login'))
    return render_template('ia_chat.html')

@app.route('/api/ia_perguntar', methods=['POST'])
def api_ia_perguntar():
    """Endpoint para processar perguntas da IA"""
    if not usuario_logado():
        return jsonify({'sucesso': False, 'mensagem': 'Não autenticado'}), 401
    
    try:
        from ia_utils import processar_pergunta_ia
        dados = request.get_json()
        pergunta = dados.get('pergunta', '').strip()
        
        if not pergunta or len(pergunta) < 3:
            return jsonify({'sucesso': False, 'mensagem': 'Pergunta muito curta'}), 400
        
        # Adicionar timestamp para evitar cache no backend
        import time
        timestamp = int(time.time() * 1000)
        
        # Processar pergunta com IA - sempre gera nova resposta
        resultado = processar_pergunta_ia(pergunta)
        
        # Adicionar timestamp à resposta para garantir que não é cache
        resultado['timestamp'] = timestamp
        
        return jsonify(resultado)
    
    except Exception as e:
        import traceback
        print(f"Erro em /api/ia_perguntar: {e}")
        print(traceback.format_exc())
        return jsonify({'sucesso': False, 'mensagem': str(e)}), 500

@app.route('/api/ia_relatorio/<tipo>', methods=['GET'])
def api_ia_relatorio(tipo):
    """Endpoint para gerar dados de relatório"""
    if not usuario_logado():
        return jsonify({'sucesso': False, 'mensagem': 'Não autenticado'}), 401
    
    tipos_validos = ['pacientes', 'solicitacoes', 'especialidades', 'status', 'tendencias']
    
    if tipo not in tipos_validos:
        return jsonify({'sucesso': False, 'mensagem': f'Tipo inválido. Use um de: {tipos_validos}'}), 400
    
    try:
        from ia_utils import executar_query_relatorio
        dados = executar_query_relatorio(tipo)
        return jsonify({'sucesso': True, 'tipo': tipo, 'dados': dados})
    except Exception as e:
        return jsonify({'sucesso': False, 'mensagem': str(e)}), 500

@app.route('/api/ia_pdf', methods=['POST'])
def api_ia_pdf():
    """Endpoint para gerar PDF do relatório"""
    if not usuario_logado():
        return jsonify({'sucesso': False, 'mensagem': 'Não autenticado'}), 401
    
    try:
        from ia_utils import gerar_relatorio_pdf
        dados = request.get_json()
        titulo = dados.get('titulo', 'Relatório Gerado pela IA').strip()
        conteudo = dados.get('conteudo', '').strip()
        
        if not conteudo:
            return jsonify({'sucesso': False, 'mensagem': 'Conteúdo vazio'}), 400
        
        resultado = gerar_relatorio_pdf(titulo, conteudo)
        return jsonify(resultado)
    
    except Exception as e:
        return jsonify({'sucesso': False, 'mensagem': str(e)}), 500

@app.route('/relatorio_ia/<arquivo>')
def download_relatorio_ia(arquivo):
    """Download do relatório PDF gerado"""
    if not usuario_logado():
        return redirect(url_for('login'))
    
    try:
        caminho = os.path.join('static', 'relatorios', arquivo)
        if not os.path.exists(caminho):
            return 'Arquivo não encontrado', 404
        
        return redirect(f'/static/relatorios/{arquivo}')
    except Exception as e:
        return f'Erro: {str(e)}', 500

# ======================== FIM ROTAS DE IA ========================

with app.app_context():
    criar_tabelas()
    garantir_usuario_admin()

if __name__ == '__main__':
    app.run(debug=True)
