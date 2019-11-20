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
