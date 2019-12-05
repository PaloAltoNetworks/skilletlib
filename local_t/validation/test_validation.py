from skilletlib.skilletLoader import SkilletLoader

sl = SkilletLoader()
skillets = sl.load_all_skillets_from_dir('.')
d = skillets[0]

context = dict()
with open('config.xml', 'r') as config:
    context['config'] = config.read()

out = d.execute(context)
print(out)
