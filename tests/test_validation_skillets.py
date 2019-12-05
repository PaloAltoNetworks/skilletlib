# This script will load the example configuration found in 'tests/example_config/config.xml'
# and then execute all the example skillets found in the 'skilletlib/example_skillets' directory.


from skilletlib import SkilletLoader
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()
with open('example_config/config.xml', 'r') as config:
    context['config'] = config.read()


def load_and_execute_skillet(skillet_path: str) -> None:
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.skillets[0]
    print('=' * 80)
    print(f'Executing {skillet.label}\n'.center(80))

    output = skillet.execute(context)

    for k, v in output.items():
        if 'results' in v:
            r = str(v['results'])
            print(f'{k:60}{r}')
            assert r == 'True'


def test_capture_value():
    skillet_path = '../example_skillets/capture_value/'
    load_and_execute_skillet(skillet_path)


def test_capture_object():
    skillet_path = '../example_skillets/capture_object/'
    load_and_execute_skillet(skillet_path)


def test_output_capture_filter():
    skillet_path = '../example_skillets/output_capture_filter/'
    load_and_execute_skillet(skillet_path)


def test_tag_present():
    skillet_path = '../example_skillets/tag_present/'
    load_and_execute_skillet(skillet_path)


def test_tag_absent():
    skillet_path = '../example_skillets/tag_present/'
    load_and_execute_skillet(skillet_path)


if __name__ == '__main__':
    test_capture_value()
    test_capture_object()
    test_output_capture_filter()
    test_tag_present()
    test_tag_absent()
