# This test will use skilletLoader to load a skillet that includes snippets and variables from other skillets

import pytest

from skilletlib import SkilletLoader
from skilletlib.skillet.base import Skillet
from skilletlib.snippet.base import Snippet
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

# create our context that will contain only a 'config' variable
context = dict()
with open('example_config/config.xml', 'r') as config:
    context['config'] = config.read()


def test_get_skillet_by_name():
    """
    Test to verify skilletLoader can successfully load all skillets found in the 'skillet_incluedes'
    directory and return the one with the 'include_other_skillets' name

    :return: None
    """
    skillet_path = '../example_skillets/skillet_includes/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.get_skillet_with_name('include_other_skillets')
    assert skillet is not None


def test_skillet_includes():
    """
    Tests to verify the Skillet object is successfully compiled from all included skillets.
    The 'include_other_skillets' skillet includes snippets and variables from two other skillets
    in the same directory

    :return: None
    """
    skillet_path = '../example_skillets/skillet_includes/'
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet: Skillet = skillet_loader.get_skillet_with_name('include_other_skillets')
    # verify we can find and load the correct skillet
    assert skillet.name == 'include_other_skillets'

    # verify the correct number of snippets.
    assert len(skillet.snippets) == 14

    included_snippet: Snippet = skillet.get_snippet_by_name('network_profiles.check_network_profiles')

    # verify we can get an included snippet from the skillet object
    assert included_snippet is not None

    # verify the 'label' metadata attribute has been overridden correctly
    assert included_snippet.metadata.get('label', '') == 'Check Network Profiles Override'

    included_variable: dict = skillet.get_variable_by_name('another_variable')

    # verify the included variable is present in the compiled skillet
    assert included_variable is not None

    # verify the default value is correctly overridden from the included variable
    assert included_variable.get('default', '') == 'test123456'

    second_included_variable: dict = skillet.get_variable_by_name('some_update_variable')
    assert second_included_variable is not None

    another_included_variable: dict = skillet.get_variable_by_name('zone_to_test')
    assert another_included_variable["default"] == "untrust"

    # verify that shared children variables merge attributes
    merged_override_from_all_variable: dict = skillet.get_variable_by_name('qos_class')
    assert merged_override_from_all_variable["toggle_hint"] is not None
    assert "internet" in merged_override_from_all_variable["toggle_hint"]["value"]
    assert "untrust" in merged_override_from_all_variable["toggle_hint"]["value"]

    # verify that the override variables brought up to the parent are preserved
    parent_preserve_variable: dict = skillet.get_variable_by_name('shared_base_variable')
    assert "toggle_hint" not in parent_preserve_variable

    # verify that child override works
    child_override_1_variable: dict = skillet.get_variable_by_name('child_1_unique_variable')
    assert child_override_1_variable["toggle_hint"] is not None

    child_override_2_variable: dict = skillet.get_variable_by_name('child_2_unique_variable')
    assert child_override_2_variable["toggle_hint"] is not None

    # Ensure using includes / overrides leaves our original skillet definition intact
    # added for issue #163
    child_skillet: Skillet = skillet_loader.get_skillet_with_name('network_profiles')
    child_snippet: Snippet = child_skillet.get_snippet_by_name('check_network_profiles')

    assert child_snippet.metadata.get('label', '') == 'Ensure Named profile exists'


def test_load_skillet_from_path():
    skillet_path = '../example_skillets/skillet_includes/include_other_skillets.skillet.yaml'
    skillet_loader = SkilletLoader()
    skillet = skillet_loader.load_skillet_from_path(skillet_path)

    # verify we can find and load the correct skillet
    assert skillet.name == 'include_other_skillets'

    # verify the correct number of snippets.
    assert len(skillet.snippets) == 14

    included_snippet: Snippet = skillet.get_snippet_by_name('network_profiles.check_network_profiles')

    # verify we can get an included snippet from the skillet object
    assert included_snippet is not None


if __name__ == '__main__':
    test_get_skillet_by_name()
    test_skillet_includes()
