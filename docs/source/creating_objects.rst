Creating Validation Objects
===========================

.. _creating_objects_section:

Validation Objects
------------------

Validation objects are the reference content used for testing. It is a subset of the xml configuration file.

Based on the application used, the validation object may derive from an input of text content or be exported from the
firewall using the API. How the data is captured if beyond the scope of the skillet itself.

outputs
~~~~~~~

The output creates the object for the validation checks or subsequent filters and outputs. In the example above, an object
with the name 'telemetry' is captured at the associated xpath location in the config file.

The name of the object is referenced within the validation tests.

This is example creates an object 'external_list' at its respective xpath, the capture_object.

.. code-block:: yaml

  - name: firewall_config
    cmd: parse
    variable: config
    outputs:
      - name: external_list
        capture_object: /config/devices/entry[@name='localhost.localdomain']/vsys/[@name='vsys1']/external-list

In cases where there is an attribute name used to differentiate between a set of objects, such as multiple EDLs,
then the capture object has to include the xpath down to the attribute name.

.. code-block:: yaml

  - name: firewall_config
    cmd: parse
    variable: config
    outputs:
      - name: external_list
        capture_object: /config/devices/entry[@name='localhost.localdomain']/vsys/[@name='vsys1']/external-list/[@name='spamhaus_drop']

This object would allow for validation checks specific to the spamhaus_drop external-list. Example are to check type: ip
or recurring: five-minute intervals.

multiple outputs and referencing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The design of a validation skillet allows the creator to either have simple outputs close to the validation checks or create
a set of named output objects.

The first examples shows xpath references that are highly granularity allowing for contextual naming within the validation checks.
Checks can check configuration criteria using names 'telemetry', 'wf_update', 'dns_servers', and 'login_banner'.

.. code-block:: yaml

      - name: device_config_file
        cmd: parse
        variable: config
        outputs:
          # capture all the xml elements referenced for validations using the full config file
          - name: telemetry
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/statistics-service
          - name: threats_update
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/threats
          - name: wf_update
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/wildfire
          - name: av_update
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/anti-virus
          - name: snmp_version
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/snmp-setting/access-setting/version
          - name: dns_servers
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/dns-setting/servers
          - name: ntp_servers
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/ntp-servers
          - name: login_banner
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/login-banner
          - name: timezone
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/timezone
          - name: password_complexity

An alternative is using a more coarse xpath definition and then associated names in the validation check. Instead
of explicity naming each object, the result is shorthand notation for a common xpath prefix.

.. code-block:: yaml

      - name: device_config_file
        cmd: parse
        variable: config
        outputs:
          # capture all the xml elements referenced for validations using the full config file
          - name: device_system
            capture_object: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system

Here the xpath name is limited with the rest of tree left in the validation test. Below are translation examples
of the more granular named objects in the first example with their relative pointers use device_system.

* telemetry is device_system.update-schedule.statistics-service
* wf_update is device_system.update-schedule.wildfire
* dns_servers is device_system.dns-setting.servers
* login_banner is device_system.login-banner

The end result is the same and up to the designer to determine what works best for them.


TO DO:
. more output example with filters, chaining