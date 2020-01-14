from typing import Tuple

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.skillet.base import Skillet
from skilletlib.skilletLoader import SkilletLoader
from .base import Snippet


class WorkflowSnippet(Snippet):
    """
    WorkflowSnippet wraps the steps in a workflow skillet
    """
    required_metadata = {'name'}

    output_type = 'text'

    def __init__(self, metadata, skillet: Skillet, skillet_loader: SkilletLoader):
        self.skillet_loader = skillet_loader
        self.skillet = skillet
        super().__init__(metadata)

    def execute(self, context: dict) -> Tuple[dict, str]:
        try:
            output = self.skillet.execute(context)
            return output, 'success'
        except SkilletLoaderException as sle:
            output = dict()
            output['fail_message'] = sle
            return output, 'failure'

    def capture_outputs(self, results: str, status: str) -> dict:
        if 'outputs' in results:
            return results['outputs']

        else:
            return dict()

    def get_default_output(self, results: dict, status: str) -> dict:
        # The underlaying skillet will return us a dict with keys 'skillets' and also any skillet specific keys
        # such as panos will add a top level 'result' key. template type will add a top level 'template' type
        # we need to include all those here as well
        workflow_results = dict()
        workflow_results['skillets'] = dict()
        if type(results) is dict:
            for k, v in results.items():
                if k == 'snippets':
                    workflow_results.update(v)
                elif k == 'outputs':
                    continue
                else:
                    workflow_results['skillets'][k] = v

        return workflow_results

