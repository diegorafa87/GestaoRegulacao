import app

client = app.app.test_client()
client.environ_base['REMOTE_USER'] = 'admin'
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'

resp = client.get('/nova_solicitacao')
print('status', resp.status_code)
print('content-type', resp.content_type)
print(resp.get_data(as_text=True)[:1000])
