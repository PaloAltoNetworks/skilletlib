from skilletlib.skilletLoader import SkilletLoader

sl = SkilletLoader()
skillets = sl.load_all_skillets_from_dir('.')
d = skillets[0]
out = d.execute(dict())
print(out)
