import os

from skilletlib.skilletLoader import SkilletLoader

salt_user = os.environ.get('SALT_API_USER', 'salt')
salt_pass = os.environ.get('SALT_API_PASSWORD', 'BqFRpSZxezKckwVQgtibBZa6GcVK')
salt_host = os.environ.get('SALT_API_HOST', '10.70.221.10')
salt_port = os.environ.get('SALT_API_PORT', '8000')

vars = dict()
vars['provisioner_username'] = salt_user
vars['provisioner_password'] = salt_pass
vars['provisioner_host'] = salt_host
vars['provisioner_port'] = salt_port

sl = SkilletLoader()
skillets = sl.load_all_skillets_from_dir('.')
d = skillets[0]
out = d.execute(vars)
print('This is what we found here')

print(out)

print('And all done')
