# Skilletlib
Base Classes and Utilities for working with Skillets. Skilletlib encapsulates all the logic necessary to 
execute a skillet in your app or tooling. 


## Basic Example

```python

from skilletlib import SkilletLoader

# init SkilletLoader Class
sl = SkilletLoader()

# Load all skillets from the current directory
skillets = sl.load_all_skillets_from_dir('.')

# get the first skillet found
skillet = skillets[0]

# Every skillet requires a context, which is a dict containing
# any user-input or other variables
context = dict()

# In this example, our skillet needs a configuration.xml file to be loaded into a variable
# called 'config'
with open('config.xml', 'r') as config:
    context['config'] = config.read()

# execute the skillet and return the results
out = skillet.execute(context)

# Do something interesting with the results, like print it out :-)
print(out)
print('all done')

```


## Loading Skillets from a Git repository

```python

from skilletlib import SkilletLoader
repo_url = 'https://github.com/nembery/Skillets'
repo_branch = 'develop'
directory = '/var/tmp/skillets'
repo_name = 'example skillets'

sl = SkilletLoader()
skillets = sl.load_from_git(repo_url, repo_name, repo_branch, local_dir=directory)

for s in skillets:
    print(s.name)

```