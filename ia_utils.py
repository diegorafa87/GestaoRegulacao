import os
import json
import google.generativeai as genai
from db import conectar
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
USE_MOCK_IA = os.environ.get('USE_MOCK_IA', 'false').lower() == 'true'

if GEMINI_API_KEY and not USE_MOCK_IA:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")
        model = None
        USE_MOCK_IA = True
else:
    model = None
    USE_MOCK_IA = True

def obter_contexto_dados():
    """Obtém contexto geral do sistema para auxiliar a IA"""
    conn = conectar()
    c = conn.cursor()
    
    contexto = {
        'total_pacientes': 0,
        'total_solicitacoes': 0,
        'solicitacoes_por_status': {},
        'solicitacoes_por_tipo': {},
        'especialidades_top': [],
        'especialidades_todas': [],  # NOVO: todas as especialidades
        'data_atual': datetime.now().strftime('%d/%m/%Y'),
    }
    
    try:
        # Total de pacientes
        c.execute('SELECT COUNT(*) FROM paciente')
        contexto['total_pacientes'] = c.fetchone()[0]
        
        # Total de solicitações
        c.execute('SELECT COUNT(*) FROM solicitacao')
        contexto['total_solicitacoes'] = c.fetchone()[0]
        
        # Solicitações por status
        c.execute('SELECT status, COUNT(*) FROM solicitacao GROUP BY status')
        for status, count in c.fetchall():
            contexto['solicitacoes_por_status'][status or 'SEM STATUS'] = count
        
        # Solicitações por tipo
        c.execute('SELECT tipo, COUNT(*) FROM solicitacao GROUP BY tipo')
        for tipo, count in c.fetchall():
            contexto['solicitacoes_por_tipo'][tipo or 'SEM TIPO'] = count
        
        # Top especialidades
        c.execute('SELECT especialidade, COUNT(*) as cnt FROM solicitacao GROUP BY especialidade ORDER BY cnt DESC LIMIT 10')
        contexto['especialidades_top'] = [
            {'especialidade': esp, 'total': cnt}
            for esp, cnt in c.fetchall()
        ]
        
        # Todas as especialidades (para extração de entidades)
        c.execute('SELECT DISTINCT especialidade FROM solicitacao WHERE especialidade IS NOT NULL ORDER BY especialidade')
        contexto['especialidades_todas'] = [row[0] for row in c.fetchall()]
    except Exception as e:
        print(f"Erro ao obter contexto: {e}")
    finally:
        conn.close()
    
    return contexto

def executar_query_relatorio(tipo_relatorio, filtros=None):
    """
    Executa queries para gerar dados de relatório baseado no tipo
    Tipos: 'pacientes', 'solicitacoes', 'especialidades', 'status', 'tendencias'
    """
    conn = conectar()
    c = conn.cursor()
    resultado = {}
    
    try:
        if tipo_relatorio == 'pacientes':
            c.execute('''
                SELECT id, nome, COUNT(s.id) as total_solicitacoes
                FROM paciente p
                LEFT JOIN solicitacao s ON p.id = s.paciente_id
                GROUP BY p.id, p.nome
                ORDER BY total_solicitacoes DESC
                LIMIT 20
            ''')
            resultado['pacientes_top'] = [
                {'id': pid, 'nome': nome, 'solicitacoes': cnt}
                for pid, nome, cnt in c.fetchall()
            ]
        
        elif tipo_relatorio == 'solicitacoes':
            c.execute('''
                SELECT 
                    data_solicitacao,
                    COUNT(*) as total,
                    status
                FROM solicitacao
                WHERE data_solicitacao IS NOT NULL
                GROUP BY data_solicitacao, status
                ORDER BY data_solicitacao DESC
                LIMIT 30
            ''')
            resultado['solicitacoes'] = [
                {'data': str(data), 'total': cnt, 'status': status}
                for data, cnt, status in c.fetchall()
            ]
        
        elif tipo_relatorio == 'especialidades':
            c.execute('''
                SELECT especialidade, COUNT(*) as total, 
                       COUNT(CASE WHEN status='EXECUTADO' THEN 1 END) as executadas
                FROM solicitacao
                WHERE especialidade IS NOT NULL
                GROUP BY especialidade
                ORDER BY total DESC
            ''')
            resultado['especialidades'] = [
                {'nome': esp, 'total': cnt, 'executadas': exec}
                for esp, cnt, exec in c.fetchall()
            ]
        
        elif tipo_relatorio == 'status':
            c.execute('''
                SELECT status, COUNT(*) as total
                FROM solicitacao
                GROUP BY status
            ''')
            resultado['status'] = {
                status or 'SEM STATUS': cnt
                for status, cnt in c.fetchall()
            }
        
        elif tipo_relatorio == 'tendencias':
            # Últimos 7 dias
            hoje = datetime.now()
            semana_atras = (hoje - timedelta(days=7)).strftime('%Y-%m-%d')
            
            c.execute('''
                SELECT data_insercao, COUNT(*) as total
                FROM solicitacao
                WHERE data_insercao >= %s
                GROUP BY data_insercao
                ORDER BY data_insercao
            ''', (semana_atras,))
            resultado['tendencias_7_dias'] = [
                {'data': str(data), 'total': cnt}
                for data, cnt in c.fetchall()
            ]
    
    except Exception as e:
        resultado['erro'] = str(e)
    finally:
        conn.close()
    
    return resultado

def gerar_resposta_mock_ia(pergunta, contexto, dados_relatorio, dados_especificos=None):
    """
    Gera respostas simuladas realistas baseadas nos dados do sistema
    Usada quando a API do Gemini não está disponível ou como fallback
    """
    import random
    pergunta_lower = pergunta.lower()

    def resposta_paciente(dados):
        resposta = "👤 **Informações do Paciente Encontrado**\n\n"
        for pac in dados['pacientes']:
            resposta += f"**Nome:** {pac['nome']}\n"
            resposta += f"**ID/CPF:** {pac['id']}\n"
            if pac.get('data_nascimento'):
                resposta += f"**Data de Nascimento:** {pac['data_nascimento']}\n"
            if pac.get('email'):
                resposta += f"**Email:** {pac['email']}\n"

            solicitacoes_key = f"solicitacoes_{pac['id']}"
            if solicitacoes_key in dados and dados[solicitacoes_key]:
                resposta += f"\n📋 **Solicitações ({len(dados[solicitacoes_key])}):**\n"
                for i, sol in enumerate(dados[solicitacoes_key][:10], 1):
                    resposta += f"\n{i}. **{sol['tipo']}** - {sol['especialidade']}\n"
                    resposta += f"   • Status: {sol['status']}\n"
                    resposta += f"   • Data: {sol['data']}\n"
                    if sol.get('conclusao'):
                        resposta += f"   • Conclusão: {sol['conclusao']}\n"
        return resposta

    def resposta_especialidade(dados):
        esp = dados['especialidade']
        resposta = f"🏥 **Análise de Solicitações - {esp['nome']}**\n\n"
        resposta += f"**Total de Solicitações:** {esp['total']}\n"
        resposta += f"• Executadas: {esp['executadas']}\n"
        resposta += f"• Pendentes: {esp['pendentes']}\n"
        resposta += f"• Urgentes: {esp['urgentes']}\n"
        if dados.get('pacientes_top'):
            resposta += f"\n👥 **Pacientes com mais solicitações ({esp['nome']}):**\n"
            for i, pac in enumerate(dados['pacientes_top'][:5], 1):
                resposta += f"{i}. {pac['nome']} ({pac['solicitacoes']} solicitações)\n"
        return resposta

    def resposta_status(dados):
        st = dados['status_info']
        resposta = f"📊 **Solicitações com Status: {st['status']}**\n\n"
        resposta += f"**Total:** {st['total']} solicitação(ões)\n"
        if dados.get('solicitacoes'):
            resposta += f"\n📋 **Primeiras solicitações:**\n"
            for i, sol in enumerate(dados['solicitacoes'][:10], 1):
                resposta += f"\n{i}. {sol['tipo']} - {sol['especialidade']}\n"
                resposta += f"   • Paciente: {sol['paciente']}\n"
                resposta += f"   • Data: {sol['data']}\n"
        return resposta

    def resposta_temporal(dados):
        resposta = "📈 **Tendência de Solicitações**\n\n"
        total_periodo = sum(item['total'] for item in dados['tendencia'])
        resposta += f"**Total no período:** {total_periodo} solicitações\n\n"
        for item in dados['tendencia'][:10]:
            resposta += f"• {item['data']}: {item['total']} solicitações\n"
        return resposta

    if dados_especificos and dados_especificos.get('encontrado'):
        tipo_busca = dados_especificos['tipo_busca']
        dados = dados_especificos['dados']
        if tipo_busca == 'paciente_especifico' and dados.get('pacientes'):
            return resposta_paciente(dados)
        if tipo_busca == 'especialidade' and dados.get('especialidade'):
            return resposta_especialidade(dados)
        if tipo_busca == 'status' and dados.get('status_info'):
            return resposta_status(dados)
        if tipo_busca == 'temporal' and dados.get('tendencia'):
            return resposta_temporal(dados)

    variacoes_intro = [
        "Aqui está a análise dos dados do sistema:\n\n",
        "Com base nos dados cadastrados:\n\n",
        "Dos registros do sistema:\n\n",
        "Consultando o banco de dados:\n\n"
    ]
    intro = random.choice(variacoes_intro)

    if any(p in pergunta_lower for p in ['quantos', 'quanto', 'total', 'número']):
        if 'paciente' in pergunta_lower:
            return f"""{intro}📊 **Total de Pacientes:** {contexto['total_pacientes']}\n\n**Dados do Sistema:**\n- Solicitações ativas: {contexto['total_solicitacoes']}\n- Data atual: {contexto['data_atual']}\n\nOs pacientes continuam recebendo atendimento conforme suas necessidades de especialidades diversas.\n"""
        if 'solicitação' in pergunta_lower or 'solicitacao' in pergunta_lower:
            return f"""{intro}📋 **Total de Solicitações:** {contexto['total_solicitacoes']}\n\n**Distribuição por Status:**\n{chr(10).join([f'• {status}: {cnt}' for status, cnt in contexto['solicitacoes_por_status'].items()])}\n\n**Distribuição por Tipo:**\n{chr(10).join([f'• {tipo}: {cnt}' for tipo, cnt in contexto['solicitacoes_por_tipo'].items()])}\n"""

    if any(p in pergunta_lower for p in ['especialidade', 'exame', 'consulta']):
        resp = intro + "🏥 **Especialidades Mais Solicitadas**\n\n"
        if contexto['especialidades_top']:
            for i, esp in enumerate(contexto['especialidades_top'][:5], 1):
                resp += f"{i}. **{esp['especialidade']}**: {esp['total']} solicitações\n"
        return resp

    if any(p in pergunta_lower for p in ['status', 'executado', 'pendente', 'urgente']):
        return f"""{intro}📊 **Status Atual das Solicitações**\n\n{chr(10).join([f'• **{status}**: {cnt} solicitações' for status, cnt in contexto['solicitacoes_por_status'].items()])}\n\n**Ações Recomendadas:**\n- Priorizar processamento de solicitações URGENTES\n- Acompanhar cronograma de ELETIVO\n- Validar conclusões de EXECUTADO\n"""

    if any(p in pergunta_lower for p in ['relatório', 'relatorio', 'gere', 'generate', 'análise', 'analise']):
        total_esp = len(contexto['especialidades_top'])
        return f"""{intro}📈 **Relatório Executivo do Sistema**\n\n**Resumo dos Números:**\n- Pacientes Cadastrados: {contexto['total_pacientes']}\n- Solicitações Totais: {contexto['total_solicitacoes']}\n- Especialidades: {total_esp}\n- Data da Consulta: {contexto['data_atual']}\n\n**Distribuição por Status:**\n{chr(10).join([f'• {status}: {cnt}' for status, cnt in contexto['solicitacoes_por_status'].items()])}\n\n**Especialidades com Maior Demanda:**\n{chr(10).join([f'{i+1}. {esp['especialidade']}: {esp['total']} solicitações' for i, esp in enumerate(contexto['especialidades_top'][:5])])}\n\n**Análise:**\nO sistema apresenta movimento consistente nas solicitações. O foco deve ser em agilizar o processamento das especialidades de maior demanda.\n"""

    return f"""{intro}💬 **Informações Disponíveis do Sistema**\n\nSua pergunta foi processada. Aqui está o resumo:\n\n**Estatísticas Gerais:**\n- Pacientes: {contexto['total_pacientes']}\n- Solicitações: {contexto['total_solicitacoes']}\n- Especialidades Ativas: {len(contexto['especialidades_top'])}\n\n**Dicas para Perguntas Mais Específicas:**\n- Pergunte por paciente específico (nome ou CPF)\n- Busque solicitações de uma especialidade\n- Filtre por status (URGENTE, EXECUTADO, etc)\n- Solicite análise de período (últimos dias)\n\nReformule sua pergunta para obter respostas mais detalhadas!\n"""

def extrair_entidades_e_intenção(pergunta, contexto_sistema=None):
    """
    Extrai entidades e intenção da pergunta com análise sofisticada
    Retorna dicionário com: intenção, entidades, filtros
    """
    pergunta_lower = pergunta.lower()
    entidades = {
        'paciente_nome': None,
        'cpf': None,
        'especialidade': None,
        'status': None,
        'data': None,
        'tipo_solicitacao': None,
        'intervalo_dias': None,
    }
    
    intenções_possíveis = []
    
    # Detectar intenção principal
    if any(p in pergunta_lower for p in ['quantos', 'quanto', 'total', 'número', 'contar', 'de quantos']):
        intenções_possíveis.append('contagem')
    if any(p in pergunta_lower for p in ['qual', 'quais', 'mostrar', 'listar', 'ver', 'que', 'o que']):
        intenções_possíveis.append('listagem')
    if any(p in pergunta_lower for p in ['gere', 'crie', 'generate', 'relatório', 'relatorio', 'faça um']):
        intenções_possíveis.append('relatorio')
    if any(p in pergunta_lower for p in ['buscar', 'procurar', 'encontrar', 'pesquisar', 'procura']):
        intenções_possíveis.append('busca')
    if any(p in pergunta_lower for p in ['quando', 'data', 'período', 'período', 'últimos', 'últimas']):
        intenções_possíveis.append('temporal')
    if any(p in pergunta_lower for p in ['tendência', 'tendencia', 'evolução', 'crescimento', 'comportamento']):
        intenções_possíveis.append('tendencia')
    
    # Extrair entidades
    import re
    
    # Nomes de pacientes (palavras capitalizadas após "paciente" ou "de")
    match_nome = re.search(r'(?:paciente|de)\s+([A-Z][a-záàâãéèêíïóôõöúçñ\s]+)', pergunta)
    if match_nome:
        entidades['paciente_nome'] = match_nome.group(1).strip()
    
    # CPF (padrão xxx.xxx.xxx-xx ou xxxxxxxxxx)
    match_cpf = re.search(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', pergunta)
    if match_cpf:
        entidades['cpf'] = match_cpf.group(0).replace('.', '').replace('-', '')
    
    # Especialidades - usar lista dinâmica do sistema quando disponível
    especialidades_lista = []
    if contexto_sistema and 'especialidades_todas' in contexto_sistema:
        especialidades_lista = contexto_sistema['especialidades_todas']
    else:
        # Fallback para lista padrão
        especialidades_lista = ['cardiologia', 'ortopedia', 'neurologia', 'pediatria', 
                                'oftalmologia', 'dermatologia', 'psiquiatria', 'urologia',
                                'gastroenterologia', 'pneumologia', 'reumatologia', 'endocrinologia',
                                'oncologia', 'hematologia', 'nefrologia']
    
    for esp in especialidades_lista:
        if esp and esp.lower() in pergunta_lower:
            entidades['especialidade'] = esp if esp.isupper() else esp.upper()
            break
    
    # Status
    status_comuns = ['urgente', 'eletivo', 'executado', 'pendente', 'cancelado', 'presente', 'ausente']
    for st in status_comuns:
        if st in pergunta_lower:
            entidades['status'] = st.upper()
            break
    
    # Tipo de solicitação
    if 'exame' in pergunta_lower or 'laboratorial' in pergunta_lower:
        entidades['tipo_solicitacao'] = 'EXAME LABORATORIAL'
    elif 'consulta' in pergunta_lower:
        entidades['tipo_solicitacao'] = 'CONSULTA'
    elif 'encaminhamento' in pergunta_lower:
        entidades['tipo_solicitacao'] = 'ENCAMINHAMENTO'
    
    # Extrair intervalo de dias
    match_dias = re.search(r'(\d+)\s*(?:dias|ultimos|últimos|último|ultimas|últimas)', pergunta)
    if match_dias:
        entidades['intervalo_dias'] = int(match_dias.group(1))
    
    intenção_principal = intenções_possíveis[0] if intenções_possíveis else 'contagem'
    
    return {
        'intenção': intenção_principal,
        'intenções': intenções_possíveis,
        'entidades': entidades,
        'pergunta_original': pergunta
    }

def executar_busca_especifica(intenção_info):
    """
    Executa buscas específicas baseado nas entidades extraídas
    Retorna dados estruturados para a IA processar
    """
    entidades = intenção_info['entidades']
    conn = conectar()
    c = conn.cursor()
    resultado = {'encontrado': False, 'dados': {}, 'tipo_busca': None}
    
    try:
        # BUSCA POR PACIENTE ESPECÍFICO
        if entidades['paciente_nome'] or entidades['cpf']:
            resultado['tipo_busca'] = 'paciente_especifico'
            
            query = 'SELECT id, nome, data_nascimento, email FROM paciente WHERE 1=1'
            params = []
            
            if entidades['cpf']:
                query += ' AND regexp_replace(id, \'\\\\D\', \'\', \'g\') = %s'
                params.append(entidades['cpf'])
            elif entidades['paciente_nome']:
                query += ' AND LOWER(nome) LIKE %s'
                params.append(f"%{entidades['paciente_nome'].lower()}%")
            
            c.execute(query, params)
            pacientes = c.fetchall()
            
            if pacientes:
                resultado['encontrado'] = True
                resultado['dados']['pacientes'] = [
                    {'id': p[0], 'nome': p[1], 'data_nascimento': str(p[2]), 'email': p[3]}
                    for p in pacientes
                ]
                
                # Obter solicitações de cada paciente
                for paciente_id in [p[0] for p in pacientes]:
                    c.execute('''
                        SELECT id, tipo, especialidade, status, data_solicitacao, conclusao
                        FROM solicitacao
                        WHERE paciente_id = %s
                        ORDER BY data_solicitacao DESC
                    ''', (paciente_id,))
                    solicitacoes = c.fetchall()
                    resultado['dados'][f'solicitacoes_{paciente_id}'] = [
                        {
                            'id': s[0], 'tipo': s[1], 'especialidade': s[2],
                            'status': s[3], 'data': str(s[4]), 'conclusao': s[5]
                        }
                        for s in solicitacoes
                    ]
        
        # BUSCA POR ESPECIALIDADE
        elif entidades['especialidade']:
            resultado['tipo_busca'] = 'especialidade'
            
            c.execute('''
                SELECT especialidade, COUNT(*) as total,
                       COUNT(CASE WHEN status='EXECUTADO' THEN 1 END) as executadas,
                       COUNT(CASE WHEN status='PENDENTE' THEN 1 END) as pendentes,
                       COUNT(CASE WHEN status='URGENTE' THEN 1 END) as urgentes
                FROM solicitacao
                WHERE UPPER(especialidade) = %s
                GROUP BY especialidade
            ''', (entidades['especialidade'],))
            
            row = c.fetchone()
            if row:
                resultado['encontrado'] = True
                resultado['dados']['especialidade'] = {
                    'nome': row[0],
                    'total': row[1],
                    'executadas': row[2],
                    'pendentes': row[3],
                    'urgentes': row[4]
                }
                
                # Pacientes com solicitações nesta especialidade
                c.execute('''
                    SELECT DISTINCT p.id, p.nome, COUNT(s.id) as total_solicitacoes
                    FROM paciente p
                    JOIN solicitacao s ON p.id = s.paciente_id
                    WHERE UPPER(s.especialidade) = %s
                    GROUP BY p.id, p.nome
                    ORDER BY total_solicitacoes DESC
                    LIMIT 10
                ''', (entidades['especialidade'],))
                
                resultado['dados']['pacientes_top'] = [
                    {'id': p[0], 'nome': p[1], 'solicitacoes': p[2]}
                    for p in c.fetchall()
                ]
        
        # BUSCA POR STATUS ESPECÍFICO
        elif entidades['status']:
            resultado['tipo_busca'] = 'status'
            
            c.execute('''
                SELECT status, COUNT(*) as total
                FROM solicitacao
                WHERE UPPER(status) = %s
                GROUP BY status
            ''', (entidades['status'],))
            
            row = c.fetchone()
            if row:
                resultado['encontrado'] = True
                resultado['dados']['status_info'] = {
                    'status': row[0],
                    'total': row[1]
                }
                
                # Solicitações com este status
                c.execute('''
                    SELECT s.id, s.tipo, s.especialidade, p.nome, s.data_solicitacao
                    FROM solicitacao s
                    JOIN paciente p ON s.paciente_id = p.id
                    WHERE UPPER(s.status) = %s
                    ORDER BY s.data_solicitacao DESC
                    LIMIT 20
                ''', (entidades['status'],))
                
                resultado['dados']['solicitacoes'] = [
                    {
                        'id': s[0], 'tipo': s[1], 'especialidade': s[2],
                        'paciente': s[3], 'data': str(s[4])
                    }
                    for s in c.fetchall()
                ]
        
        # BUSCA TEMPORAL (últimos X dias)
        elif entidades['intervalo_dias']:
            resultado['tipo_busca'] = 'temporal'
            dias = entidades['intervalo_dias']
            
            data_inicio = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
            
            c.execute('''
                SELECT DATE(data_insercao), COUNT(*) as total
                FROM solicitacao
                WHERE data_insercao >= %s
                GROUP BY DATE(data_insercao)
                ORDER BY DATE(data_insercao) DESC
            ''', (data_inicio,))
            
            resultado['encontrado'] = True
            resultado['dados']['tendencia'] = [
                {'data': str(row[0]), 'total': row[1]}
                for row in c.fetchall()
            ]
    
    except Exception as e:
        resultado['erro'] = str(e)
    finally:
        conn.close()
    
    return resultado

def processar_pergunta_ia(pergunta, historico=[]):
    """
    Processa uma pergunta em linguagem natural usando Gemini
    e retorna resposta com dados contextualizados
    
    IMPORTANTE: Esta função SEMPRE executa buscas novas - nunca usa cache
    """
    # Obter contexto do sistema SEMPRE (não usar cache)
    contexto = obter_contexto_dados()
    
    # Extrair entidades e intenção
    intenção_info = extrair_entidades_e_intenção(pergunta, contexto)
    
    # Tentar busca específica - SEMPRE executa
    dados_especificos = executar_busca_especifica(intenção_info)
    
    # Se não houver busca específica, usar lógica anterior
    pergunta_lower = pergunta.lower()
    tipo_relatorio = None
    
    if not dados_especificos['encontrado']:
        if any(palavra in pergunta_lower for palavra in ['paciente', 'pacientes']):
            tipo_relatorio = 'pacientes'
        elif any(palavra in pergunta_lower for palavra in ['especialidade', 'especialidades', 'exame', 'consulta']):
            tipo_relatorio = 'especialidades'
        elif any(palavra in pergunta_lower for palavra in ['status', 'executado', 'pendente']):
            tipo_relatorio = 'status'
        elif any(palavra in pergunta_lower for palavra in ['tendência', 'tendencia', 'trend', 'dias', 'últimos']):
            tipo_relatorio = 'tendencias'
        else:
            tipo_relatorio = 'solicitacoes'
        
        # Obter dados
        dados_relatorio = executar_query_relatorio(tipo_relatorio)
    else:
        dados_relatorio = dados_especificos['dados']
    
    # Se o modelo Gemini não estiver disponível, usar mock IA
    if not model or USE_MOCK_IA:
        resposta_texto = gerar_resposta_mock_ia(pergunta, contexto, dados_relatorio, dados_especificos)
        return {
            'sucesso': True,
            'pergunta': pergunta,
            'resposta': resposta_texto,
            'tipo_relatorio': tipo_relatorio,
            'modo': 'mock',
            'dados_resumidos': {
                'total_pacientes': contexto['total_pacientes'],
                'total_solicitacoes': contexto['total_solicitacoes'],
                'registros_analisados': len(dados_relatorio.get(list(dados_relatorio.keys())[0], [])) if dados_relatorio else 0
            }
        }
    
    # Preparar prompt melhorado com contexto específico
    entidades_info = intenção_info['entidades']
    
    # Construir informações sobre as buscas específicas realizadas
    detalhes_busca = ""
    if dados_especificos['encontrado']:
        detalhes_busca = f"\n📍 BUSCA ESPECÍFICA REALIZADA: {dados_especificos['tipo_busca']}"
        if dados_especificos['tipo_busca'] == 'paciente_especifico':
            if entidades_info['cpf']:
                detalhes_busca += f"\n - CPF: {entidades_info['cpf']}"
            if entidades_info['paciente_nome']:
                detalhes_busca += f"\n - Nome: {entidades_info['paciente_nome']}"
        elif dados_especificos['tipo_busca'] == 'especialidade':
            detalhes_busca += f"\n - Especialidade: {entidades_info['especialidade']}"
        elif dados_especificos['tipo_busca'] == 'status':
            detalhes_busca += f"\n - Status: {entidades_info['status']}"
        elif dados_especificos['tipo_busca'] == 'temporal':
            detalhes_busca += f"\n - Período: Últimos {entidades_info['intervalo_dias']} dias"
    
    prompt = f"""
Você é um assistente inteligente de um sistema de gestão de regulação de saúde (GESTÃO REGULAÇÃO).
Sua especialidade é fazer análises precisas, gerar relatórios bem estruturados e extrair insights dos dados.

CONTEXTO DO SISTEMA:
- Data atual: {contexto['data_atual']}
- Total de pacientes: {contexto['total_pacientes']}
- Total de solicitações: {contexto['total_solicitacoes']}
- Solicitações por status: {json.dumps(contexto['solicitacoes_por_status'], ensure_ascii=False)}
- Solicitações por tipo: {json.dumps(contexto['solicitacoes_por_tipo'], ensure_ascii=False)}
- Especialidades mais solicitadas: {json.dumps(contexto['especialidades_top'], ensure_ascii=False)}

INTENÇÃO DETECTADA: {intenção_info['intenção']}
{detalhes_busca}

DADOS CONSULTADOS:
{json.dumps(dados_relatorio, ensure_ascii=False, indent=2)}

PERGUNTA DO USUÁRIO: {pergunta}

INSTRUÇÕES DE RESPOSTA:
- Responda em português brasileiro, de forma clara e objetiva
- Comece direto com a resposta relevante para a pergunta
- Use formatação com **negrito** para realçar informações importantes
- Use listas com • para enumerar items
- Se encontrou dados específicos de um paciente/especialidade/status, apresente-os em destaque
- Inclua insights analíticos sobre os dados quando apropriado
- Se houver recomendações baseadas nos dados, apresente-as
- Seja conciso mas completo
"""
    
    try:
        # Enviar para Gemini
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2048,
                temperature=0.7,
            )
        )
        
        resposta_texto = response.text if response else "Não consegui gerar uma resposta"
        
        return {
            'sucesso': True,
            'pergunta': pergunta,
            'resposta': resposta_texto,
            'tipo_relatorio': tipo_relatorio,
            'modo': 'gemini',
            'dados_resumidos': {
                'total_pacientes': contexto['total_pacientes'],
                'total_solicitacoes': contexto['total_solicitacoes'],
                'registros_analisados': len(dados_relatorio.get(list(dados_relatorio.keys())[0], [])) if dados_relatorio else 0
            }
        }
    
    except Exception as e:
        # Registrar erro e retornar mensagem clara ao frontend
        import traceback
        print('Erro ao chamar API Gemini:')
        traceback.print_exc()
        erro_msg = str(e)

        # Ainda fornecer uma resposta mock útil, mas sinalizar o erro de API
        resposta_texto = gerar_resposta_mock_ia(pergunta, contexto, dados_relatorio, dados_especificos)
        return {
            'sucesso': True,
            'pergunta': pergunta,
            'resposta': resposta_texto,
            'tipo_relatorio': tipo_relatorio,
            'modo': 'erro_api',
            'erro_api': erro_msg,
            'dados_resumidos': {
                'total_pacientes': contexto['total_pacientes'],
                'total_solicitacoes': contexto['total_solicitacoes'],
                'registros_analisados': len(dados_relatorio.get(list(dados_relatorio.keys())[0], [])) if dados_relatorio else 0
            }
        }

def gerar_relatorio_pdf(titulo, conteudo):
    """
    Gera um PDF com o relatório fornecido pela IA
    Retorna o caminho do arquivo PDF
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib import colors
        from datetime import datetime
        
        # Criar documento
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f'relatorio_ia_{timestamp}.pdf'
        caminho_arquivo = os.path.join('static', 'relatorios', nome_arquivo)
        
        # Garantir que a pasta existe
        os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
        
        doc = SimpleDocTemplate(caminho_arquivo, pagesize=A4)
        elementos = []
        estilos = getSampleStyleSheet()
        
        # Estilos personalizados
        estilo_titulo = ParagraphStyle(
            'titulo_custom',
            parent=estilos['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#003366'),
            spaceAfter=12,
        )
        
        estilo_conteudo = ParagraphStyle(
            'conteudo_custom',
            parent=estilos['BodyText'],
            fontSize=10,
            alignment=4,  # Justificado
        )
        
        # Adicionar título
        elementos.append(Paragraph(titulo, estilo_titulo))
        elementos.append(Paragraph(f'<b>Gerado em:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}', estilos['Normal']))
        elementos.append(Spacer(1, 0.3*inch))
        
        # Adicionar conteúdo
        for linha in conteudo.split('\n'):
            if linha.strip():
                elementos.append(Paragraph(linha, estilo_conteudo))
            else:
                elementos.append(Spacer(1, 0.1*inch))
        
        # Construir PDF
        doc.build(elementos)
        
        return {
            'sucesso': True,
            'arquivo': nome_arquivo,
            'caminho': caminho_arquivo
        }
    
    except ImportError:
        return {
            'sucesso': False,
            'mensagem': 'Reportlab não instalado. Instale com: pip install reportlab'
        }
    except Exception as e:
        return {
            'sucesso': False,
            'mensagem': f'Erro ao gerar PDF: {str(e)}'
        }
