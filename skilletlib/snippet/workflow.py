import logging
from typing import Tuple
from typing import Union

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
    optional_metadata = {}
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
