from app import app
app.testing = True
app.config['PROPAGATE_EXCEPTIONS'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'
resp = client.get('/relatorios?view=paciente&acao=paciente&paciente=ana')
print('status', resp.status_code)
print(resp.data[:5000].decode('utf-8', 'ignore'))
