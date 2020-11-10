# This script will load the example configuration found in 'tests/example_config/config.xml'
# and then execute all the example skillets found in the 'skilletlib/example_skillets' directory.


from skilletlib import SkilletLoader
from skilletlib.skillet.base import Skillet
from skilletlib.snippet.base import Snippet
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()
with open('example_config/config.xml', 'r') as config:
    context['config'] = config.read()


def load_and_execute_skillet(skillet_path: str, skillet_name: str) -> dict:
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.get_skillet_with_name(skillet_name)
    print('=' * 80)
    print(f'Executing {skillet.label}\n'.center(80))

    output = skillet.execute(context)

    if 'pan_validation' in output:
        for k, v in output.get('pan_validation', {}).items():
            r = str(v.get('results', 'False'))
            print(f'{k:60}{r}')
            assert r == 'True'

    return output


def test_get_skillet_by_name():
    skillet_path = '../example_skillets/skillet_includes/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.get_skillet_with_name('include_other_skillets')
    assert skillet is not None


def test_skillet_includes():
    skillet_path = '../example_skillets/skillet_includes/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet: Skillet = skillet_loader.get_skillet_with_name('include_other_skillets')
    assert skillet.name == 'include_other_skillets'
    assert len(skillet.snippets) == 6

    included_snippet: Snippet = skillet.get_snippet_by_name('check_network_profiles')
    assert included_snippet is not None
    assert included_snippet.metadata.get('label', '') == 'Check Network Profiles Override'

    included_variable: dict = skillet.get_variable_by_name('some_update_variable')
    assert included_variable is not None
    assert included_variable.get('default', '') == 'test123456'


if __name__ == '__main__':
    test_get_skillet_by_name()
    test_skillet_includes()

