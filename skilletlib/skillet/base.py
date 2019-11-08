import logging
from typing import List

from skilletlib.snippet.base import Snippet

logger = logging.getLogger(__name__)


class Skillet:

    def __init__(self, s: dict):

        self.skillet_dict = s
        self.name = self.skillet_dict['name']
        self.label = self.skillet_dict['label']
        self.snippet_stack = self.skillet_dict['snippets']
        self.type = self.skillet_dict['type']
        self.supported_versions = 'not implemented'
        self.variables = self.skillet_dict['variables']
        self.path = self.skillet_dict['snippet_path']
        self.labels = self.skillet_dict['labels']
        self.collections = self.skillet_dict['labels']['collections']
        self.context = dict()

    def get_snippets(self) -> List[Snippet]:
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet = Snippet(snippet_def)
            snippet_list.append(snippet)

        return snippet_list

    def update_context(self, d: dict) -> dict:
        for var in self.variables:
            if var['name'] in d:
                self.context[var['name']] = d[var['name']]
            else:
                self.context[var['name']] = var['default']

        return self.context
