import logging
from pathlib import Path
from typing import List

from skilletlib.snippet.template import TemplateSnippet
from .base import Skillet

logger = logging.getLogger(__name__)


class TemplateSkillet(Skillet):

    snippet_required_metadata = {'name', 'file'}

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

    def get_results(self) -> dict:
        """
        TemplateSkillet will add an additional attribute into the results dict containing the value of
        the first snippet found to have been successfully executed
        :return: dict containing default outputs plus the rendered template
        """

        results = super().get_results()
        cleaned_results = dict()
        cleaned_results['snippets'] = dict()
        snippets = results.get('snippets', {})
        for k, v in snippets.items():
            if v != '':
                cleaned_results['template'] = v['raw']
                cleaned_results['snippets'][k] = 'success'
                break
            cleaned_results['snippets'][k] = 'failure'

        return cleaned_results
