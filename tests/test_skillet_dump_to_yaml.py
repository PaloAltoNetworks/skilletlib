import yaml

from skilletlib import SkilletLoader
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()


def load_and_dump_skillet(skillet_path: str) -> str:
    skillet_loader = SkilletLoader()
    skillet = skillet_loader.load_skillet_from_path(skillet_path)

    print('=' * 80)
    print(f'Checking {skillet.label}\n'.center(80))

    output: str = skillet.dump_yaml()

    return output


def test_yaml_load():
    skillet_path = '../example_skillets/rest_get'
    skillet_yaml_str = load_and_dump_skillet(skillet_path)

    skillet_dict = yaml.safe_load(skillet_yaml_str)

    # ensure basic structure is in tact after dump to yaml
    assert 'name' in skillet_dict

    # ensure optional metadata is not dumped in the resulting yaml
    for snippet in skillet_dict.get('snippets', []):
        assert 'content_type' not in snippet


def test_template_yaml_load():
    skillet_path = '../example_skillets/template_inline_skillet'
    skillet_yaml_str = load_and_dump_skillet(skillet_path)

    skillet_dict = yaml.safe_load(skillet_yaml_str)

    # ensure basic structure is in tact after dump to yaml
    assert 'name' in skillet_dict

    # ensure optional metadata is not dumped in the resulting yaml
    for snippet in skillet_dict.get('snippets', []):
        # check for file and template_title in template types
        assert 'file' not in snippet
        assert 'template_title' not in snippet
