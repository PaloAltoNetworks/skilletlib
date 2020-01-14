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


.. _jinja_filters_section:

Jinja Filters
-------------

tag_present
~~~~~~~~~~~~

This filter will validate that the given path is present in the variable object. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return True. This is useful to validate a specific element is present.

.. code-block::

  - name: update_schedule_stats_service_configured
    label: Ensure Statistics Service is enabled
    test: update_schedule_object| tag_present('update-schedule.statistics-service')

element_value
~~~~~~~~~~~~~

This filter will return the value of the given path in the variable object. This value can then be used with any
valid jinja expression. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return leaf node text value.

.. code-block::

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

.. code-block::

  - name: check_profile_exists
    when: network_profiles is not none
    label: Ensure Named profile exists
    test: network_profiles | attribute_present('entry', 'name', 'default')


element_value_contains
~~~~~~~~~~~~~~~~~~~

This filter is useful for times when the xpath may contain a list of items. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will inspect the found value. If the value is a list, this filter will determine if the second
argument is present in the list. If the value is a string, the filter will check if the string matches the second
argument.

.. code-block::

  - name: security_rules_outbound_edl
    label: check for IronSkillet outbound EDL block rule member
    test: security_rule_outbound_edl | element_value_contains('destination.member', 'panw-bulletproof-ip-list')
    documentation_link: https://ironscotch.readthedocs.io/en/docs_dev/viz_guide_panos.html#device-setup-telemetry-telemetry
