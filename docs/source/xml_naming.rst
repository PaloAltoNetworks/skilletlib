Working with XML
================

.. _xml_section:

XML Constructs
--------------

Validation skillets for xml inspect and evaluate various elements of the xml configuration to determine if items are
present, absent or equate to a value.
This validation therefore depends heavily on an understanding of xml components in a configuration file.

The example below is representation of the external-dynamic list (EDL) portion of the configuration.

.. toggle-header:: class
    :header: **show/hide start tags**

    .. code-block:: XML

        <config>
         <devices>
          <entry name="localhost.localdomain"
           <vsys>
            <entry name="vsys1">

.. code-block:: XML

    .
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

.. toggle-header:: class
    :header: **show/hide end tags**

    .. code-block:: XML

            </entry name="vsys1">
           </vsys>
          </entry name="localhost.localdomain">
         </devices>
        </config>


element tags
~~~~~~~~~~~~

Element tags use the <tag> notation and are paired with a respective end tag as </tag>. Some of the element tags in the EDL example
include <entry>, <type>, <ip>, <recurring>, and <url>.

Element tags can include configuration values such as <five-minute> for the EDL refresh interval in the above example.
Changing to recurring hourly will set a different tag value.

element text value
~~~~~~~~~~~~~~~~~~

Text values are value contained between a pair of start-end tags that are leaf nodes. In the EDL example, the url and
description values sit between the <url> and <description> tags.

attributes
~~~~~~~~~~

Attributes are values defined within an element tags. They have an attribute name and then its associated value.

In the EDL example, the name of the EDL is set as 'spamhaus_drop' using the attribute of name. One or more attribute values
can sit with an element tag.

.. NOTE::
    The three above examples are the key types of value setting in the configuration file and mostly likely components
    for configuration inspection and validation.

element
~~~~~~~

The element is the entire snippet of xml content inclusive of and contained within start and end element tags.

In this example <external-list> and </external-list> are the start and end element tags for the EDL configuration element.


xpath
~~~~~

The xpath is the list of element tags from the root, <config> for firewall configurations, down to the location of
the configuration element. So the xpath for the external-list configuration element, shown above the example element is:

.. code-block:: bash

    /config/devices/entry[@name='localhost.localdomain']/vsys/[@name='vsys1']

.. Note::
    The xpath uses a different format than the xml file config tags and attributes. Tags are chained using the forward slash
    and the name="value" in the xml file is noted as [@name='value'] in the xpath.


