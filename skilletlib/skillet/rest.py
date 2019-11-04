import logging
from pathlib import Path
from typing import List

from skilletlib.snippet.base import Snippet
from skilletlib.snippet.template import RestSnippet
from .base import Skillet

logger = logging.getLogger(__name__)


class RestSkillet(Skillet):

    def get_snippets(self) -> List[Snippet]:
        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            operation = snippet_def.get('operation', 'get')
            if operation == 'post' and 'payload' in snippet_def:
                snippet_file = snippet_path.joinpath(snippet_def['payload'])
                if snippet_file.exists():
                    with open(snippet_file, 'r') as sf:
                        snippet = RestSnippet(sf.read(), snippet_def)
                        snippet_list.append(snippet)

        return snippet_list
