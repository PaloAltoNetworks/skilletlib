import logging
from typing import Tuple

from pan.xapi import PanXapiError

from .panos import PanosSnippet
from ..exceptions import PanoplyException

logger = logging.getLogger(__name__)


class PanValidationSnippet(PanosSnippet):
    """
    Pan validation Snippet
    """
    required_metadata = {'name'}
    # optional metadata that may be overridden in the snippet definition / metadata
    optional_metadata = {'documentation_link': ''}

    template_metadata = {'label', 'test', 'meta'}

    conditional_template_metadata = {'test'}

    def execute(self, context: dict) -> Tuple[str, str]:
        """
        Execute method in pan_validation snippet overrides the execute method in panos to add ensure any
        exception caught always results in a failed test

        :param context: snippet context used for tests
        :return: tuple consisting of results, (success | failure)
        """
        try:

            return super().execute(context)

        except PanXapiError as px:
            logger.error(f'Exception in {self.name}')
            logger.error(px)
            return str(px), 'failure'
        except PanoplyException as pe:
            logger.error(f'Exception in {self.name}')
            logger.error(pe)
            return str(pe), 'failure'

    def handle_output_type_validation(self, results: str) -> dict:
        """
        Handle output type validation results

        :param results: results from the test execution
        :return: dict containing validation messages
        """
        # if results are anything but True, then this is a failure. This can happen when we catch and exception
        # and return the exception
        if not bool(results):
            results = False

        output = dict()
        output['results'] = results
        output['label'] = self.metadata.get('label', '')
        output['severity'] = self.metadata.get('severity', 'low')
        output['meta'] = self.metadata.get('meta', {})
        output['documentation_link'] = self.metadata.get('documentation_link', '')
        output['test'] = self.metadata.get('test', '')

        # only render pass / fail message relevant to the results per #172
        if results:
            output['output_message'] = self.render(self.metadata.get('pass_message', 'Snippet Validation Passed'),
                                                   self.context)
        else:
            output['output_message'] = self.render(self.metadata.get('fail_message', 'Snippet Validation Failed'),
                                                   self.context)

        o = dict()
        o[self.name] = output
        return o
