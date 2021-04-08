import os

# Import the Panos object from Skilletlib
from skilletlib import Panos

# get your auth information, In this case it's passed in via the environment
username = os.environ.get("TARGET_USERNAME", "admin")
password = os.environ.get("TARGET_PASSWORD", "admin")
ip = os.environ.get("TARGET_IP", "10.10.10.10")

# connect to the device using the auth information provided
device = Panos(hostname=ip, api_username=username, api_password=password, debug=True)

# grab any two configs, in this example we will generate a diff from the running and candidate configs
previous_config = device.get_configuration(config_source="candidate")
latest_config = device.get_configuration(config_source="running")

# you can also use saved configurations on the device
unused_config = device.get_saved_configuration("my_saved_config.xml")

# you can get the diffs as a list of xml / xpaths
xml_and_xpaths = device.generate_skillet_from_configs(previous_config, latest_config)

# you can also get the diffs as a set of cli commands
set_clis = device.generate_set_cli_from_configs(previous_config, latest_config)

# each set of xml and corresponding xpaths are called snippets
for snippet in xml_and_xpaths:
    print(snippet)

# the set clis are returned an ordered list
for cli_cmd in set_clis:
    print(cli_cmd)
