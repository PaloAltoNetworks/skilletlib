Working with Objects
====================

To make working with objects easier, we have created the following jinja filters:

- tag_present 
- tag_absent
- attribute_present
- attribute_absent
- element_value
- element_value_contains
- append_uuid
- md5_hash


.. _jinja_filters_section:

Jinja Filters
-------------

tag_present
~~~~~~~~~~~~

This filter will validate that the given path is present in the variable object. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return True. This is useful to validate a specific element is present.

.. code-block:: yaml

  - name: update_schedule_stats_service_configured
    label: Ensure Statistics Service is enabled
    test: update_schedule_object| tag_present('update-schedule.statistics-service')

element_value
~~~~~~~~~~~~~

This filter will return the value of the given path in the variable object. This value can then be used with any
valid jinja expression. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return leaf node text value.

.. code-block:: yaml

  - name: ensure_ip_address
    label: Ensure IP Address is configured
    test: device_system | element_value('ip-address') == '10.10.10.10'

attribute_present
~~~~~~~~~~~~~~~~~

This filter will determine if a node exists with the given attribute name and value. This is useful for parts of the
configuration where there may be many 'entries' under a specific xpath. For example, security profiles or interfaces.
This filter takes a configuration path as the first argument, similar to the tag_present filter. The second argument
is the attribute name and the third is the attribute value. If the configuration path is found, and has an attribute
that matches both the name and value, this filter will return True.

.. code-block:: yaml

  - name: check_profile_exists
    when: network_profiles is not none
    label: Ensure Named profile exists
    test: network_profiles | attribute_present('entry', 'name', 'default')


element_value_contains
~~~~~~~~~~~~~~~~~~~~~~

This filter is useful for times when the xpath may contain a list of items. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will inspect the found value. If the value is a list, this filter will determine if the second
argument is present in the list. If the value is a string, the filter will check if the string matches the second
argument.

.. code-block:: yaml

  - name: security_rules_outbound_edl
    label: check for IronSkillet outbound EDL block rule member
    test: security_rule_outbound_edl | element_value_contains('destination.member', 'panw-bulletproof-ip-list')
    documentation_link: https://ironscotch.readthedocs.io/en/docs_dev/viz_guide_panos.html#device-setup-telemetry-telemetry


items_present
~~~~~~~~~~~~~

This filter will iterate over a list and ensure all items from the first list appear
in the second list. The second list can be a list of objects, in which case an optional
path argument may be supplied.

Consider the case where you have a list of objects. Each object has it's own list of members.
You want to ensure that all items from a list appear at least once in one of the objects
member lists. For example, ensure a list of blocked application appear in at least one
block rule.

.. code-block:: yaml

    snippets:
      - name: grab_security_rules
        cmd: parse
        variable: config
        outputs:
          - name: security_rules
            capture_list: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules/entry
          - name: deny_rules
            capture_expression: security_rules
            filter_items: item | element_value('entry.action') == 'deny'
      - name: all_apps_blocked
        label: Ensure all blocked apps appear in the rules
        test: blocked_apps | items_present(deny_rules, 'entry.application.member')
        documentation_link: https://iron-skillet.readthedocs.io

Additional Filters
==================

Additional filters have been included from the `Jinja2 Ansible Filters <https://pypi.org/project/jinja2-ansible-filters/>`_
project. 

Included filters

  * b64decode
  * b64encode
  * basename
  * bool
  * checksum
  * comment
  * dirname
  * expanduser
  * expandvars
  * extract
  * fileglob
  * flatten
  * from_json
  * from_yaml
  * from_yaml_all
  * ans_groupby
  * hash
  * mandatory
  * md5
  * quote
  * ans_random
  * random_mac
  * realpath
  * regex_escape
  * regex_findall
  * regex_replace
  * regex_search
  * relpath
  * sha1
  * shuffle
  * splitext
  * strftime
  * subelements
  * ternary
  * to_datetime
  * to_json
  * to_nice_json
  * to_nice_yaml
  * to_uuid
  * to_yaml
  * type_debug
  * win_basename
  * win_dirname
  * win_splitdrive
