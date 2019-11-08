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
