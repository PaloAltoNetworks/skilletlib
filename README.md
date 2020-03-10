# Skilletlib
Base Classes and Utilities for working with Skillets. Skilletlib encapsulates all the logic necessary to 
execute a skillet in your app or tooling. 

See [here](https://live.paloaltonetworks.com/t5/Skillet-District/ct-p/Skillets) for information about Skillets and
what skillets may be available. A list of example skillets may be found 
[here as well](https://github.com/PaloAltoNetworks/skillets).


## About Skillets

Skillets are designed to be sharable units of configuration or validation data. They are perfectly suited for 
'Compliance as Code' or 'Infrastructure as Code' type environments. All the 'knowledge' of doing a thing is encapsulated
in the skillet. Skillets strive to be tooling agnostic. A subject matter expert should not have to define best 
practices in multiple domain specific languages. Ideally, this should be expressed once, and executed in a variety of
tools. Skilletlib makes it easy to allow Skillets to be executed in your tooling, or tooling of choice. 

Skillets are meant to be stored and shared via source control repositories along with the rest of your infrastructure.
This allows complex NGFW configurations and use case specific compliance checks to be executed as part of your 
deployment pipeline.  


## Installation

Skilletlib is distributed as a python shared library on [pypi.org](https://pypi.org/project/skilletlib/).

```bash

pip install skilletlib

```


## Basic Example

```python

from skilletlib import SkilletLoader

# init SkilletLoader Class
sl = SkilletLoader()

# Load the skillet found in the current directory
skillet = sl.load_skillet_from_path('.')

# Every skillet requires a context, which is a dict containing
# any user-input or other variables to allow customization.
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



## Other projects that use Skilletlib

Here are a couple of examples of other projects that use skilletlib

* [Panhandler](https://github.com/PaloAltoNetworks/panhandler/)
    Panhandler is a tool to manage collections of Skillets and their respective git repositories
* [SkilletLoader](https://github.com/nembery/skilletLoader/)
    SkilletLoader is a tool to load and test skillets in a CI/CD pipeline via Docker
* [Ansible Skillets](https://github.com/PaloAltoNetworks/panw-gse.skillets)
    Ansible roles and libraries for loading PAN-OS and related skillets via Ansible playbooks
* [Demisto XSOAR Integration](https://github.com/nembery/content/tree/skilletlib/Packs/skilletlib)
    Experimental in development Demisto XSOAR integration
    
    
    
## Other utilities in Skilletlib

Skilletlib includes all the necessary libraries and code to work directly with PAN-OS and Panorama devices. A call
called 'Panoply' is included which includes many often needed methods when working with emphemeral PAN-OS devices, such
as in a CI/CD pipeline. 