from skilletlib.skilletLoader import SkilletLoader

sl = SkilletLoader()
skillets = sl.load_all_skillets_from_dir('.')
d = skillets[0]

context = dict()
with open('config.xml', 'r') as config:
    context['config'] = config.read()

out = d.execute(context)

for s in d.snippet_stack:
    cmd = s.get('cmd', 'na')
    name = s.get('name', '')
    if cmd == 'validate':
        if name in out:
            print(out[name])


print('all done')
