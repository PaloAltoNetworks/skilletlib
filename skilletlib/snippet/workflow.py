import logging
from typing import Tuple
from typing import Union

from jinja2 import TemplateError

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.skillet.base import Skillet
from skilletlib.skilletLoader import SkilletLoader
from .base import Snippet

logger = logging.getLogger(__name__)


class WorkflowSnippet(Snippet):
    """
    WorkflowSnippet wraps the steps in a workflow skillet
    """
    required_metadata = {'name'}
    optional_metadata = {
        'include_by_tag': '',
        'include_by_name': '',
        'include_by_regex': '',
        'exclude_by_tag': '',
        'exclude_by_name': '',
        'exclude_by_regex': ''
    }
    output_type = 'text'

    def __init__(self, metadata, skillet: Skillet, skillet_loader: SkilletLoader):
        self.skillet_loader = skillet_loader
        self.skillet = skillet
        super().__init__(metadata)

    def update_context(self, context) -> dict:
        # always remove filter_snippets from the context at this level so we do not filter out
        # actual workflow included skillets, but only their snippets

        if '__filter_snippets' in context:
            context.pop('__filter_snippets')

        if '__filter_snippets' in self.context:
            self.context.pop('__filter_snippets')

        return super().update_context(context)

    def update_snippet_context(self, context) -> dict:

        filter_snippets = dict()
        for filter_def in ('include_by_tag', 'include_by_name', 'include_by_regex', 'exclude_by_tag',
                           'exclude_by_name', 'exclude_by_regex'):
            if filter_def in self.metadata and self.metadata[filter_def] != '':
                filter_snippets[filter_def] = self.metadata[filter_def]

        if filter_snippets:
            context['__filter_snippets'] = filter_snippets

        # transform the context for this snippet
        context.update(self.transform_context(context))

        return context

    def execute(self, context: dict) -> Tuple[dict, str]:
        try:
            snippet_context = self.update_snippet_context(context)
            output = self.skillet.execute(snippet_context)
            return output, 'success'
        except SkilletLoaderException as sle:
            output = dict()
            output['fail_message'] = sle
            return output, 'failure'

    def capture_outputs(self, results: (dict, str), status: str) -> Union[str, dict]:
        if type(results) is dict and 'outputs' in results:
            if type(results['outputs']) is dict:
                return results['outputs']
            else:
                logger.info('unknown results type in workflow:capture_outputs')
                return dict()
        else:
            return dict()

    def transform_context(self, context: dict) -> dict:
        """
        Returns a dict of newly transformed variables. The value of the transform attribute is a list of dicts. Each
        dict should have the following keys: name, source. The name is the name of the new variable to create in the
        context. This should correspond to a variable expected in the Skillet. The source is an expression that is
        evaluated using the context.

        For example, a Skillet may expose the following outputs: ip_address, password. Another Skillet may require
        the following inputs: TARGET_IP, TARGET_PASSWORD. Using this simple transform, we can set the values of
        TARGET_IP and TARGET_PASSWORD accordingly. Note the use of the hash filter to process the password variable
        before setting the TARGET_PASSWORD variable.

        transform:
            - name: TARGET_IP
              source: ip_address
            - name: TARGET_PASSWORD
              source: password | hash

        :param context: dict containing all context variables
        :return: dict containing transformed variables
        """

        transformed_context = dict()

        if 'transform' not in self.metadata:
            return transformed_context

        if not isinstance(self.metadata['transform'], list):
            return transformed_context

        for transform_def in self.metadata['transform']:
            if not {'name', 'source'}.issubset(transform_def):
                logger.error('Malformed transform definition...')
                return transformed_context

            name = transform_def.get('name')
            source_exp = transform_def.get('source')

            try:
                expression = self._env.compile_expression(source_exp)
                value = expression(context)
                transformed_context[name] = value

            except TemplateError as te:
                logger.error('Could not render expression in workflow snippet transform...')
                logger.error(te)

        return transformed_context
