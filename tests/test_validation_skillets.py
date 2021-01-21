# This script will load the example configuration found in 'tests/example_config/config.xml'
# and then execute all the example skillets found in the 'skilletlib/example_skillets' directory.


from skilletlib import SkilletLoader
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()
with open('example_config/config.xml', 'r') as config:
    context['config'] = config.read()


def load_and_execute_skillet(skillet_path: str) -> dict:
    skillet_loader = SkilletLoader(path=skillet_path)
    skillet = skillet_loader.skillets[0]
    print('=' * 80)
    print(f'Executing {skillet.label}\n'.center(80))

    output = skillet.execute(context)

    if 'pan_validation' in output:
        for k, v in output.get('pan_validation', {}).items():
            r = str(v.get('results', 'False'))
            print(f'{k:60}{r}')
            assert r == 'True'

    return output


#
# def test_capture_expression():
#     skillet_path = '../example_skillets/capture_expression/'
#     load_and_execute_skillet(skillet_path)


def test_output_template():
    skillet_path = '../example_skillets/output_template/'
    output = load_and_execute_skillet(skillet_path)
    assert 'output_template' in output
    assert 'Success' in output['output_template']


def test_basic_structure():
    skillet_path = '../example_skillets/capture_value/'
    output = load_and_execute_skillet(skillet_path)
    assert 'pan_validation' in output
    assert 'ensure_hostname_was_found' in output['pan_validation']


def test_capture_value():
    skillet_path = '../example_skillets/capture_value/'
    out = load_and_execute_skillet(skillet_path)

    assert 'pan_validation' in out

    # ensure default_documentation_link label is set correctly here for #14
    assert out['pan_validation']['ensure_hostname_was_found']['documentation_link'] != ''


def test_capture_object():
    skillet_path = '../example_skillets/capture_object/'
    out = load_and_execute_skillet(skillet_path)

    # ensure validation skillets also include captured values in the output under the 'outputs' key
    assert 'outputs' in out
    assert 'system_object' in out['outputs']

    # this skillet captures the gp app crypto profiles as an object
    assert 'profiles' in out['outputs']
    entry_list = out['outputs']['profiles']['global-protect-app-crypto-profiles']['entry']

    # test to ensure skilletlib is properly converting the 'entry' into a single item list
    assert isinstance(entry_list, list)
    assert len(entry_list) == 1

    assert 'gp_profile_entry' in out['outputs']
    gp_profile_entry = out['outputs']['gp_profile_entry']

    # test to ensure capture object will not convert 'top-level' entry items into a list and instead
    # return the actual object instead
    assert(isinstance(gp_profile_entry, dict))


def test_capture_list_filter():
    skillet_path = '../example_skillets/capture_list_filter/'
    load_and_execute_skillet(skillet_path)


def test_capture_variable():
    skillet_path = '../example_skillets/capture_variable/'
    out = load_and_execute_skillet(skillet_path)
    assert 'interface_object' in out['outputs']
    interface_object = out['outputs']['interface_object']

    # ensure the capture_object
    assert isinstance(interface_object, dict)


def test_tag_present():
    skillet_path = '../example_skillets/tag_present/'
    load_and_execute_skillet(skillet_path)


def test_tag_absent():
    skillet_path = '../example_skillets/tag_present/'
    load_and_execute_skillet(skillet_path)


def test_when_conditional():
    skillet_path = '../example_skillets/when_conditional/'
    load_and_execute_skillet(skillet_path)


def test_cmd_validate_xml():
    skillet_path = '../example_skillets/cmd_validate_xml'
    load_and_execute_skillet(skillet_path)


def test_cmd_validate_xml_cherry_pick():
    skillet_path = '../example_skillets/cmd_validate_xml_cherry_pick'
    load_and_execute_skillet(skillet_path)


def test_fail_message():
    skillet_path = '../example_skillets/fail_message'
    load_and_execute_skillet(skillet_path)


def test_element_value():
    skillet_path = '../example_skillets/filter_element_value'
    load_and_execute_skillet(skillet_path)


def test_element_value_contains():
    skillet_path = '../example_skillets/filter_element_value_contains'
    load_and_execute_skillet(skillet_path)


def test_attribute_present():
    skillet_path = '../example_skillets/filter_attribute_present'
    load_and_execute_skillet(skillet_path)


def test_attribute_absent():
    skillet_path = '../example_skillets/filter_attribute_absent'
    load_and_execute_skillet(skillet_path)


if __name__ == '__main__':
    test_capture_object()
    test_capture_list_filter()
    test_capture_value()
    test_capture_variable()
    test_cmd_validate_xml()
    test_cmd_validate_xml_cherry_pick()
    test_fail_message()
    test_attribute_present()
    test_attribute_absent()
    test_element_value()
    test_element_value_contains()
    test_tag_present()
    test_tag_absent()
    test_when_conditional()
