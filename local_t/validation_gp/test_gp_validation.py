from skilletlib import SkilletLoader

sl = SkilletLoader(path='.')
d = sl.skillets[0]

context = dict()
with open('config.xml', 'r') as config:
    context['config'] = config.read()

out = d.execute(context)
for k, v in d.get_results(out).items():
    if 'results' in v:
        r = str(v['results'])
        print(f'{k:60}{r}')

