import logging
from typing import List

from skilletlib.snippet.template import TemplateSnippet
from .base import Skillet

logger = logging.getLogger(__name__)


class TemplateSkillet(Skillet):
    snippet_required_metadata = {'name'}

    snippet_optional_metadata = {
        'file': '',
        'element': '',
        'template_title': ''
    }

    def get_snippets(self) -> List[TemplateSnippet]:
        if hasattr(self, 'snippets'):
            return self.snippets

        snippet_list = list()
        for snippet_def in self.snippet_stack:
            if 'element' not in snippet_def or snippet_def['element'] == '':
                template_str = self.load_template(snippet_def.get('file', ''))
                snippet_def['element'] = template_str

            else:
                template_str = snippet_def['element']

            snippet = TemplateSnippet(template_str, snippet_def)
            snippet_list.append(snippet)

        return snippet_list

    def get_results(self) -> dict:
        """
        TemplateSkillet will add an additional attribute into the results dict containing the value of
        the first snippet found to have been successfully executed

        .. code-block:: json

            {
              "snippets": {
                "config_template": "success"
              },
              "template": "Rendered Template output"
            }


        :return: dict containing default outputs plus the rendered template contained in the 'template' attribute
        """

        results = super()._get_snippet_results()
        cleaned_results = dict()
        cleaned_results['snippets'] = dict()
        # include outputs for #104
        cleaned_results['outputs'] = self.captured_outputs
        snippets = results.get('snippets', {})
        for k, v in snippets.items():
            if v != '':
                cleaned_results['template'] = v['raw']
                cleaned_results['snippets'][k] = 'success'
                break
            cleaned_results['snippets'][k] = 'failure'

        return cleaned_results
