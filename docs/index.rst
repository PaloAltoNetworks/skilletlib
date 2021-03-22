Welcome to Skilletlib's documentation!
======================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   examples
   skillet_classes
   skilletloader
   panoply
   outputs
   jinja_filters


About
-----

Skilletlib is a library for working with Skillets. Skillets are a collection of configuration templates and some
metadata about how those templates should be rendered and applied. Skillets were created to help manage complex
shareable configuration sets for PAN-OS devices.

Skillets can also be thought of as wrappers around atomic automation units. A collection of PAN-OS
XML configuration snippets can be grouped together as a unit to be shared and applied together. Skilletlib
provides a convenient mechanism to examine and apply these automation units.

Building Skillets
-----------------

This documentation is intended document the internals the Skilletlib python library. For more information about building
and using Configuration and Validation Skillets, refer to the
`Skillet Builder <https://skilletbuilder.readthedocs.io/en/latest/>`_ documentation.

Disclaimer
----------

This software is provided without support, warranty, or guarantee.
Use at your own risk.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
