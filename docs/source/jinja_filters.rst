Working with Objects
====================

.. _jinja_filters_section:

Jinja Filters
-------------

Skillets use the templating language Jinja since it is widely used across the industry. Basic configuration skillets
use minimal Jinja capabilities, primarily the {{ variable }} notation, for value substitutions.

.. _Jinja filters: https://jinja.palletsprojects.com/en/2.10.x/templates/#filters

Validation skillets require additional capabilities such as `Jinja filters`_ to inspect and evaluate various criteria
within a configuration element.

Filters come after the variable separated by a pipe symbol (|).


Jinja Filters for Validation
----------------------------

To make working with objects easier, a set of skillet-specific Jinja filters have been created to inspect xml configuration
elements:

- tag_present / tag_absent
- element_value
- element_value_contains
- attribute_present / attribute_absent
- append_uuid

The value checks below use this reference xml snippet.

.. code-block:: XML

    <external-list>
      <entry name="spamhaus_drop">
        <type>
          <ip>
            <recurring>
              <five-minute/>
            </recurring>
            <description>spamhaus drop list</description>
            <url>https://panwdbl.appspot.com/lists/shdrop.txt</url>
          </ip>
        </type>
      </entry>
    <external-list>


tag_present
~~~~~~~~~~~

This filter will validate that a given xpath tag is present in the variable object. The xpath argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return True. This is useful to validate a specific element tag is present.

.. code-block:: yaml

  - name: set_edl_update_five_minutes
    label: Check that EDL update interval is five minutes
    test: spamhaus_object| tag_present('type.ip.recurring.five-minute')

.. Note::
    tag_absent is the inverse of tag_present resulting in True if the tag is absent. This is often used to ensure
    an item does not exist that may lead to potential conflicts when merging configuration elements

element_value
~~~~~~~~~~~~~

This filter will return the value of the given path in the variable object. This value can then be used with any
valid jinja expression. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will return leaf node text value.

.. code-block:: yaml

  - name: check edl url
    label: check that external-list matches spamhaus url
    test: spamhaus_object | node_value('type.ip.url') == 'https://panwdbl.appspot.com/lists/shdrop.txt'


attribute_present
~~~~~~~~~~~~~~~~~

This filter will determine if a node exists with the given attribute name and value. This is useful for parts of the
configuration where there may be many 'entries' under a specific xpath. For example, security profiles or interfaces.
This filter takes a configuration path as the first argument, similar to the node_present filter. The second argument
is the attribute name and the third is the attribute value. If the configuration path is found, and has an attribute
that matches both the name and value, this filter will return True.

.. code-block:: yaml

  - name: check_for_spamhaus_drop
    label: Check that spamhaus drop edl is configured
    test: external_lists | node_attribute_present('entry', 'name', 'spamhaus_drop')

.. Note::
    attribute_absent is the inverse of attribute_present resulting in True if the attribute is absent.
    This is often used to ensure an item does not exist that may lead to potential conflicts when merging configuration elements

element_contains
~~~~~~~~~~~~~~~~~~~

This filter is useful for times when the xpath may contain a list of items. The path argument is a '.' or '/'
separated list. The variable object is inspected to verify each item in the path list is present. If all elements are
found, this filter will inspect the found value. If the value is a list, this filter will determine if the second
argument is present in the list. If the value is a string, the filter will check if the string matches the second
argument.

.. code-block:: yaml

  - name: security_rules_outbound_edl
    label: check that spamhaus drop edl is added to the edl security policy
    test: security_rule_outbound_edl | node_value_contains('destination.member', 'spamhaus_drop')



