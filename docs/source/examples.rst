Examples
========


Validation Examples
~~~~~~~~~~~~~~~~~~~

Validation Skillets work by comparing the 'configuration objects` against a set of rules defined in each snippet.
By default, the configuration is placed in the context as the 'config' variable and is a string representation of the
raw XML. To compare and validate specific parts of the config, you can use the 'parse' command to convert a part of the
configuration into an object that can then be used with simple logical operators or jinja filters.

Variable Parsing
----------------

This example captures a variable called `update_schedule_object` by converting the configuration elements found at the
given `xpath` from the `config` variable. The output of this snippet is a new variable is placed into the context
and is available for use in subsequent steps.

.. code-block:: yaml

  - name: create_update_schedule_object
    cmd: parse
    variable: config
    outputs:
      - name: update_schedule_object
        capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule


The `updated_schedule_object` variable will contain all the configuration elements found at that xpath:

.. code-block:: xml

     <update-schedule>
      <statistics-service>
        <application-reports>yes</application-reports>
        <threat-prevention-reports>yes</threat-prevention-reports>
        <threat-prevention-pcap>yes</threat-prevention-pcap>
        <threat-prevention-information>yes</threat-prevention-information>
        <passive-dns-monitoring>yes</passive-dns-monitoring>
        <url-reports>yes</url-reports>
        <health-performance-reports>yes</health-performance-reports>
        <file-identification-reports>yes</file-identification-reports>
      </statistics-service>
      <threats>
        <recurring>
          <every-30-mins>
            <at>2</at>
            <action>download-and-install</action>
          </every-30-mins>
          <threshold>48</threshold>
        </recurring>
      </threats>
      <anti-virus>
        <recurring>
          <hourly>
            <at>4</at>
            <action>download-and-install</action>
          </hourly>
        </recurring>
      </anti-virus>
      <wildfire>
        <recurring>
          <every-min>
            <action>download-and-install</action>
          </every-min>
        </recurring>
      </wildfire>
      <global-protect-datafile>
        <recurring>
          <hourly>
            <at>40</at>
            <action>download-and-install</action>
          </hourly>
        </recurring>
      </global-protect-datafile>
      <global-protect-clientless-vpn>
        <recurring>
          <hourly>
            <at>50</at>
            <action>download-and-install</action>
          </hourly>
        </recurring>
      </global-protect-clientless-vpn>
    </update-schedule>


The previous XML fragment will be converted into an object with name `update_schedule_object` with the following
value:

.. code-block:: json

    {
      "update-schedule": {
        "threats": {
          "recurring": {
            "every-30-mins": {
              "at": "2",
              "action": "download-and-install"
            },
            "threshold": "48"
          }
        },
        "statistics-service": {
          "application-reports": "yes",
          "threat-prevention-reports": "yes",
          "threat-prevention-pcap": "yes",
          "threat-prevention-information": "yes",
          "passive-dns-monitoring": "yes",
          "url-reports": "yes",
          "health-performance-reports": "yes",
          "file-identification-reports": "yes"
        },
        "anti-virus": {
          "recurring": {
            "hourly": {
              "at": "4",
              "action": "download-and-install"
            }
          }
        },
        "wildfire": {
          "recurring": {
            "every-min": {
              "action": "download-and-install"
            }
          }
        },
        "global-protect-datafile": {
          "recurring": {
            "hourly": {
              "at": "40",
              "action": "download-and-install"
            }
          }
        },
        "global-protect-clientless-vpn": {
          "recurring": {
            "hourly": {
              "at": "50",
              "action": "download-and-install"
            }
          }
        }
      }
    }


Validation
----------

The `validation` cmd type can be used to validate configuration objects with simple logical operators and Jinja filters.
This example will validate that a configuration node is present on the `update_schedule_object` variable.

.. code-block:: yaml

  - name: update_schedule_stats_service_configured
    when: update_schedule_object is not none
    label: Ensure Statistics Service is enabled
    test: update_schedule_object| node_present('update-schedule.statistics-service')
    documentation_link: https://docs.paloaltonetworks.com/pan-os/8-0/pan-os-new-features/content-inspection-features/telemetry-and-threat-intelligence-sharing

.. note::

    See the :ref:`jinja_filters_section` for details on available filters.


XML Validate
-------------

The `validate_xml` cmd type can be used to compare the configuration against an XML Snippet either in whole, or
against a smaller portion of the XML Fragment using `cherry_pick`.

This will query the configuration for the XML Element at the given XPath and compare it against the contents of the
'file' or 'element' attributes. The `file` attribute, if found, will be rendered using Jinja and stored in the
`element` attribute for comparison. The `file` or `element` must be rooted at the same xpath. If you have
many validations to perform in the same area of the configuration, you can use `cherry_pick` to validate portions
of a larger XML `file` or `element`.


.. code-block:: yaml

  # this example will validate that the application-reports xml fragment matches that that is found in the
  # device_system.xml file
  - name: validate_application_reports
    cmd: validate_xml
    xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system
    file: device_system.xml
    cherry_pick: update-schedule/statistics-service/application-reports

  - name: validate_statistics_service
    cmd: validate_xml
    xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system
    file: device_system.xml
    cherry_pick: update-schedule/statistics-service

  - name: validate_update_anti_virus
    cmd: validate_xml
    xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/anti-virus
    file: anti_virus.xml


