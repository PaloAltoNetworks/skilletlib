from skilletlib import Panoply
from skilletlib.utils.testing_utils import setup_dir

setup_dir()

context = dict()


def test_generate_skillet():
    """
    This test exercises the generate_skillet method of panoply. The output is known and should be consistent

    :return: None
    """
    expected_ordering = ['/config/devices/entry[@name="localhost.localdomain"]/vsys/entry[@name="vsys1"]/tag',
                         '/config/devices/entry[@name="localhost.localdomain"]/vsys/entry[@name="vsys1"]/'
                         'log-settings/profiles',
                         '/config/devices/entry[@name="localhost.localdomain"]/vsys/entry[@name="vsys1"]',
                         '/config/devices/entry[@name="localhost.localdomain"]/vsys/entry[@name="vsys1"]/'
                         'rulebase/security/rules',
                         '/config/devices/entry[@name="localhost.localdomain"]/vsys/entry[@name="vsys1"]/'
                         'rulebase/security/rules']

    p = Panoply()

    with open('example_config/before_config.xml', 'r') as config:
        previous_config = config.read()

    with open('example_config/after_config.xml', 'r') as config:
        latest_config = config.read()

    generated_skillet_snippets = p.generate_skillet_from_configs(previous_config, latest_config)

    found_ordering = list()

    for snippet in generated_skillet_snippets:
        found_ordering.append(snippet['xpath'])

    assert found_ordering == expected_ordering

    # ensure uuid are removed properly - in this example the last snippet contains
    assert 'uuid' not in generated_skillet_snippets[-1]['element']


def test_set_cli_generator():
    p = Panoply()

    with open('example_config/before_config.xml', 'r') as config:
        previous_config = config.read()

    with open('example_config/after_config.xml', 'r') as config:
        latest_config = config.read()

    set_cmds = p.generate_set_cli_from_configs(previous_config, latest_config)

    # ensure 'shared log-settings' is before others in the examples - test proper ordering
    # this also tests the special case of log-settings profiles, which need conversion into the shared space
    # for set cli
    assert 'shared log-settings profiles objects-log-forwarding' in set_cmds[0]

    # test ordering 'tag' should be right after shared items
    assert 'tag my_tag' in set_cmds[5]

    # ensure we found the edl and it comes after the 2 tag set commands
    assert 'external-list my_edl' in set_cmds[7]

    # ensure security rules come last
    assert 'rulebase security rules my_edl-block_outbound' in set_cmds[-1]


if __name__ == '__main__':
    test_generate_skillet()
    test_set_cli_generator()
