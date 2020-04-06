Outputs
========


Executing Skillets
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from skilletlib.skilletLoader import SkilletLoader
    sl = SkilletLoader()
    skillet = sl.load_skillet_from_path('.')
    out = skillet.execute(dict())
    print(out)



Examining the Output
~~~~~~~~~~~~~~~~~~~~

Each Skillet type may return data differently. For example, `pan_validation` Skillets will return a dict
with each key being the name of a snippet that was executed. It's value will be the results of that snippet.

.. code-block:: javascript

    {
        "update_schedule_configured": {
            "results": true,
            "label": "Ensure Update Schedules are Configured",
            "severity": "low",
            "documentation_link": "https://iron-skillet.readthedocs.io",
            "test": "update_schedule_object is not none",
            "output_message": "Snippet Validation Passed"
        },
    }


Outputs Per Type
~~~~~~~~~~~~~~~~

View the documentation for the 'get_results' method of each skillet class to determine what structure
is returned by the Skillet type.

