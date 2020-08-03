from skilletlib import SkilletLoader
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()


def load_and_execute_skillet(skillet_path: str) -> dict:
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.skillets[0]
    print('=' * 80)
    print(f'Executing {skillet.label}\n'.center(80))

    output: dict = skillet.execute(context)

    return output


def test_inline_template():
    skillet_path = '../example_skillets/template_inline_skillet/'
    output = load_and_execute_skillet(skillet_path)
    assert 'template' in output
    rendered_output = output.get('template', '')
    assert 'Variable is present.' in rendered_output


def test_template_skillet():
    skillet_path = '../example_skillets/template_skillet'
    output = load_and_execute_skillet(skillet_path)
    assert 'template' in output
    rendered_output = output.get('template', '')

    assert 'You variable value is: present.' in rendered_output


if __name__ == '__main__':
    test_inline_template()
    test_template_skillet()
