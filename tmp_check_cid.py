import app

client = app.app.test_client()
with client.session_transaction() as sess:
    sess['usuario_id'] = 1
    sess['usuario_perfil'] = 'ADMIN'

resp = client.get('/cid_sugestoes?query=S09&limit=20')
print(resp.status_code)
print(resp.get_json()[:20])
