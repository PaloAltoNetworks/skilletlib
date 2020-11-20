# This test will use skilletLoader to load a workflow skillet

from skilletlib import SkilletLoader
from skilletlib.skillet.base import Skillet
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

# create our context that will contain only a 'config' variable
context = dict()
with open('example_config/config.xml', 'r') as config:
    context['config'] = config.read()


def test_load_skillet():
    """
    Test to verify skilletLoader can successfully load all skillets found in the 'workflow_example'
    directory and return the one with the 'example_workflow_with_filtering' name

    :return: None
    """
    skillet_path = '../example_skillets/workflow_example/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.get_skillet_with_name('example_workflow_with_filtering')
    assert skillet is not None


def test_workflow_skillet():
    """

    Load and execute the workflow skillet and ensure all child skillets are executed properly

    :return: None
    """
    skillet_path = '../example_skillets/workflow_example/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet: Skillet = skillet_loader.get_skillet_with_name('example_workflow_with_filtering')
    # verify we can find and load the correct skillet
    assert skillet.name == 'example_workflow_with_filtering'

    out = skillet.execute(context)
    assert 'pan_validation' in out

    assert 'outputs' in out

    assert 'snippets' in out

    # ensure the correct number of tests are included and executed and reported in the output
    assert len(out['pan_validation']) == 6

    # ensure all three snippets were found and executed
    assert len(skillet.snippet_outputs) == 3


if __name__ == '__main__':
    test_load_skillet()
    test_workflow_skillet()
