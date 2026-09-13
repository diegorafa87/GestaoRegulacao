from app import app
app.testing = True
app.config['PROPAGATE_EXCEPTIONS'] = True
client = app.test_client()
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'
for path in ['/api/buscar_paciente?termo=ana', '/relatorios?view=paciente&acao=paciente&paciente=ana']:
    resp = client.get(path)
    print(path, resp.status_code)
    print(resp.data[:3000].decode('utf-8', 'ignore'))
    print('---')
