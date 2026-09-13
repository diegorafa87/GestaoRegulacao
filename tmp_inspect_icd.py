import app

print('icd10 module:', app.icd10)
if app.icd10 is not None:
    items = list(app.icd10.codes.items())
    print('count', len(items))
    for code, value in items[:20]:
        print(code, '=>', value)
    print('--- sample A ---')
    for code, value in items:
        if str(code).startswith('A'):
            print(code, value)
            break
    print('--- sample R ---')
    for code, value in items:
        if str(code).startswith('R'):
            print(code, value)
            break
