# Skilletlib
Base Classes and Utilities for working with Skillets in Python 3.7+. Skilletlib encapsulates all the logic necessary to 
execute a skillet in your app or tooling. 

See [here](https://live.paloaltonetworks.com/t5/Skillet-District/ct-p/Skillets) for information about Skillets and
what skillets may be available. 


## About Skillets

Skillets are designed to be sharable units of configuration or validation data. They are perfectly suited for 
'Compliance as Code' or 'Infrastructure as Code' type environments. All the 'knowledge' of doing a thing is encapsulated
in the skillet. Skillets strive to be tooling agnostic. A subject matter expert should not have to define best 
practices in multiple domain specific languages. Ideally, this should be expressed once, and executed in a variety of
tools. Skilletlib makes it easy to allow Skillets to be executed in your tooling of choice. 

Skillets are meant to be stored and shared via source control repositories along with the rest of your infrastructure.
This allows complex NGFW configurations and use case specific compliance checks to be executed as part of your 
deployment pipeline.  

## Resources

* [Information on building Skillets and working with the PAN-OS XML API](https://SkilletBuilder.readthedocs.io)

* [Example Skillets](https://github.com/PaloAltoNetworks/skilletlib/tree/master/example_skillets)

* [PAN-OS XML Quickstart](https://strata.pan.dev/docs/apis/xmlapi_qs)

* [PAN-OS Exploring the API](https://docs.paloaltonetworks.com/pan-os/9-0/pan-os-panorama-api/get-started-with-the-pan-os-xml-api/explore-the-api.html)

## Installation

Skilletlib is distributed as a python shared library on [pypi.org](https://pypi.org/project/skilletlib/).

```bash

pip install skilletlib

```


## Example Loading a Skillet

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

## using Skilletlib to find recent changes in Set CLI Format

```python

import os

# The Panos class is a wrapper around the XML API that provides some convience methods
from skilletlib import Panos

auth = {
    'hostname': os.environ.get('ip_address', ''),
    'api_username': os.environ.get('username', ''),
    'api_password': os.environ.get('password', ''),
    'debug': os.environ.get('debug', True),
}
device = Panos(**auth)

# you can pass negative integers to the 'get_configuration' method to retrive the most to least recent
# running configurations. This is very useful to finding the Set CLI or XML equivelent of GUI configuration 
# changes
previous_config = device.get_configuration(config_source='-1')
latest_config = device.get_configuration(config_source='running')

# The 'generate_set_cli_from_configs' method returns the difference between two config files. In this case,
# we'll use the running config and the most recent running config audit backup. This will give us all the 
# changes made via the most recent commit in Set CLI format
cmds = device.generate_set_cli_from_configs(previous_config, latest_config)

for cmd in cmds:
    print(cmd)



```

## Other projects that use Skilletlib

Here are a couple of examples of other projects that use skilletlib

* [Panhandler](https://github.com/PaloAltoNetworks/panhandler/)
    Panhandler is a tool to manage collections of Skillets and their respective git repositories
* [SLI](https://gitlab.com/panw-gse/as/sli)
    SLI is a CLI interface to Skilletlib. This tool allows rapid testing and prototyping of Skillets
* [SkilletLoader](https://github.com/nembery/skilletLoader/)
    SkilletLoader is a tool to load and test skillets in a CI/CD pipeline via Docker
* [Ansible Skillets](https://github.com/PaloAltoNetworks/panw-gse.skillets)
    Ansible roles and libraries for loading PAN-OS and related skillets via Ansible playbooks
* [Demisto XSOAR Integration](https://github.com/nembery/content/tree/skilletlib/Packs/skilletlib)
    Experimental in development Demisto XSOAR integration
  
    
    
## Other utilities in Skilletlib

Skilletlib also includes a collection of tools and methods called 
'[Panoply](https://www.merriam-webster.com/dictionary/panoply)' which eases working with emphemeral PAN-OS and 
Panorama devices, such as in a CI/CD Pipeline or development environment. 