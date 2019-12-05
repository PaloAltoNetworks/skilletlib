from skilletlib import Panoply
from skilletlib import SkilletLoader

context = dict()

sl = SkilletLoader()
skillet = sl.load_skillet_from_path('/Users/nembery/PycharmProjects/Skillets/kitchen_sink/validation')
h = Panoply(hostname='10.0.1.119', api_username='admin', api_password='Clouds123', debug=True)

c = sl.execute_panos_skillet(skillet, context, h)

print('*' * 80)
for item in c:
    if item != 'config' and item != 'facts':
        print(f'{item}: {c[item]}')
print('*' * 80)
