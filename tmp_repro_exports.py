from app import app
app.testing = True
app.config['PROPAGATE_EXCEPTIONS'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'
for path in [
    '/relatorios?view=paciente&acao=paciente&paciente=ana&formato=csv',
    '/relatorios?view=paciente&acao=paciente&paciente=ana&formato=pdf',
    '/relatorios?view=resumo&formato=pdf',
]:
    resp = client.get(path)
    print(path, resp.status_code, resp.headers.get('Content-Type'))
    print(resp.data[:200].decode('utf-8', 'ignore'))
    print('---')
