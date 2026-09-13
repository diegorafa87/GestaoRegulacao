import app as app_module

client = app_module.app.test_client()
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'

resp = client.get('/relatorios?view=paciente&acao=paciente&paciente=ana&formato=pdf')
print(resp.status_code)
print(resp.headers.get('content-type'))
print(resp.data[:200])
