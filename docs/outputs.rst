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

Output Templates
~~~~~~~~~~~~~~~~

A very common use case is to collect some information from a NGFW, filter or otherwise manipulate
that data, then display it to the user. This is so common, we've added a simple way to do both
of these tasks in the same Skillet.

Output templates are normal jinja2 templates used to display data after the Skillet exeuciton is
complete. By adding an 'output_template' key with a value of a relative path to a jinja2 template
file, skilletlib will find and load that template, then render it using the outputs and context
of the Skillet.

By default the template engine has access to the following context items:
 * snippet_outputs
 * captured_outputs
 * context

See the 'output_template' directory in example_skillets for a complete example.



