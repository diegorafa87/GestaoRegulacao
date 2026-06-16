import os
import traceback
from dotenv import load_dotenv
load_dotenv()
try:
    import google.generativeai as genai
except Exception as e:
    print('Erro ao importar google.generativeai:', e)
    raise
print('GEMINI_API_KEY present:', bool(os.environ.get('GEMINI_API_KEY')))
try:
    genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content('Olá, me diga 1 frase curta em português.', generation_config=genai.types.GenerationConfig(max_output_tokens=60))
    print('Resposta gerada:')
    print(getattr(response, 'text', response))
except Exception:
    traceback.print_exc()
