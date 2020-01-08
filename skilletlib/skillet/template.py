import logging
from pathlib import Path
from typing import List

from skilletlib.snippet.template import TemplateSnippet
from .base import Skillet

logger = logging.getLogger(__name__)


class TemplateSkillet(Skillet):

    def get_snippets(self) -> List[TemplateSnippet]:
        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet_file = snippet_path.joinpath(snippet_def['file'])
            if snippet_file.exists():
                with open(snippet_file, 'r') as sf:
                    snippet = TemplateSnippet(sf.read(), snippet_def)
                    snippet_list.append(snippet)

        return snippet_list

    def get_results(self, context: dict) -> str:
        """
        TemplateSkillet should only return the rendered template from the first snippet that successfully executed
        :param context:
        :return: str output of the first successfully rendered template snippet (usually the only one defined)
        return a blank str if not snippets were found
        """
        results = super().get_results(context)
        snippets = results.get('snippets', {})
        for k, v in snippets.items():
            if v == 'success':
                return k

        return ''
