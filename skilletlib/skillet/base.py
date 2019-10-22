import logging
from pathlib import Path
from typing import List

from skilletlib.snippet.base import Snippet

logger = logging.getLogger(__name__)


class Skillet:

    def __init__(self, s: dict):

        self.skillet_dict = s
        self.name = self.skillet_dict['name']
        self.snippet_stack = self.skillet_dict['snippets']
        self.type = self.skillet_dict['type']
        self.supported_versions = 'not implemented'
        self.variables = self.skillet_dict['variables']
        self.context = dict()

    def get_snippets(self) -> List[Snippet]:
        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet_file = snippet_path.joinpath(snippet_def['file'])
            if snippet_file.exists():
                with open(snippet_file, 'r') as sf:
                    snippet = Snippet(sf.read(), snippet_def)
                    snippet_list.append(snippet)

        return snippet_list

    def update_context(self, d: dict) -> dict:
        for var in self.variables:
            if var['name'] in d:
                self.context[var['name']] = d[var['name']]
            else:
                self.context[var['name']] = var['default']

        return self.context
