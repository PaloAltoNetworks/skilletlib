import skilletlib
from skilletlib.skilletLoader import SkilletLoader

# Instantiating SkilletLoader with no init args will result in
# no skillets being loaded by default, you can also pass it an optional
# directory as a string, which will be recursively searched for skillets.
#
# If you search for skillets using a directory, they will be stored in a list
# at sl.skillets
sl = SkilletLoader()

# With an instantiated SkilletLoader you can can load a skillet based on path. 
# This example will look inside the directory /skillet for a .meta-cnc.yml file
skillet = sl.load_skillet_from_path('/skillet')


# Validation skillets at a minimum require connectivity information to validate
# configuration on a device
context = {
        "username": "username",
        "password": "password",
        "ip_address": "ip_or_hostname"
    }

# The execute function takes context as an argument and returns information
# on the requested validations in a dict 
output = skillet.execute(context)

# For convenience, the results of each snippet processing validation is provided
# as a key / value pair inside the 'snippets' key. The key being the nme of the 
# snippet and the value being a boolean test result
snippets = output['snippets']
for s in snippets:
    # In this case, 's' refers to the name of the snippet, and snippets[s] will
    # return True or False based on the validation check
    print(f'{s} - {snippets[s]}')

# More detailed information is available inside the 'pan_validation' key. This 
# returns a dict where each key is the name of the snippet and the value is a dict
# containing information about the skillet itself in key value pairs.
validation = output['pan_validation']
for s in validation:
    snippet = validation[s]
    print(snippet['label'] + ' - ' + snippet['output_message'])
    if not snippet['results']:
        print(snippet['documentation_link'])