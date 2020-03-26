import logging
from pathlib import Path
from typing import List

import requests

from skilletlib.snippet.base import Snippet
from skilletlib.snippet.rest import RestSnippet
from .base import Skillet

logger = logging.getLogger(__name__)


class RestSkillet(Skillet):

    snippet_required_metadata = {'name', 'path'}

    snippet_optional_metadata = {
        'operation': 'get',
        'payload': '',
        'headers': {},
        'content_type': '',
        'accepts_type': ''
    }

    def __init__(self, metadata: dict):
        super().__init__(metadata)
        self.session = requests.Session()

    def get_snippets(self) -> List[Snippet]:
        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            operation = snippet_def.get('operation', 'get').lower()
            if operation == 'post' and 'payload' in snippet_def:
                snippet_file = snippet_path.joinpath(snippet_def['payload'])
                if snippet_file.exists():
                    with open(snippet_file, 'r') as sf:
                        snippet = RestSnippet(sf.read(), snippet_def, self.session)
                        snippet_list.append(snippet)
                else:
                    logger.warning(f'Snippet file: {snippet_def["name"]} was not found!')
            else:
                snippet = RestSnippet('', snippet_def, self.session)
                snippet_list.append(snippet)

        return snippet_list
