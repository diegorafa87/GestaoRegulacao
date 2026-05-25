import os
import json
import google.generativeai as genai
from db import conectar
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    model = None

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

def processar_pergunta_ia(pergunta, historico=[]):
    """
    Processa uma pergunta em linguagem natural usando Gemini
    e retorna resposta com dados contextualizados
    """
    if not model:
        return {
            'sucesso': False,
            'mensagem': 'API key do Gemini não configurada. Configure GEMINI_API_KEY no .env'
        }
    
    # Obter contexto do sistema
    contexto = obter_contexto_dados()
    
    # Determinar tipo de relatório baseado na pergunta
    pergunta_lower = pergunta.lower()
    tipo_relatorio = None
    
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
    
    # Preparar prompt para a IA
    prompt = f"""
Você é um assistente inteligente de um sistema de gestão de regulação de saúde (GESTÃO REGULAÇÃO).

CONTEXTO DO SISTEMA:
- Data atual: {contexto['data_atual']}
- Total de pacientes: {contexto['total_pacientes']}
- Total de solicitações: {contexto['total_solicitacoes']}
- Solicitações por status: {json.dumps(contexto['solicitacoes_por_status'], ensure_ascii=False)}
- Solicitações por tipo: {json.dumps(contexto['solicitacoes_por_tipo'], ensure_ascii=False)}
- Especialidades mais solicitadas: {json.dumps(contexto['especialidades_top'], ensure_ascii=False)}

DADOS DO RELATÓRIO SOLICITADO:
{json.dumps(dados_relatorio, ensure_ascii=False, indent=2)}

PERGUNTA DO USUÁRIO: {pergunta}

Responda em português brasileiro, de forma clara e objetiva. 
- Se for gerar um relatório, formate de forma legível com bullet points quando apropriado
- Inclua insights e análises dos dados
- Se tiver sugestões, mencione
- Seja conciso mas informativo
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
            'dados_resumidos': {
                'total_pacientes': contexto['total_pacientes'],
                'total_solicitacoes': contexto['total_solicitacoes'],
                'registros_analisados': len(dados_relatorio.get(list(dados_relatorio.keys())[0], []))
            }
        }
    
    except Exception as e:
        return {
            'sucesso': False,
            'mensagem': f'Erro ao processar: {str(e)}'
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
