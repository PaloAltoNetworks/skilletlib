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

    def get_results(self) -> dict:
        """
        Gets the results from the REST skillet execution. This skillet does not add any additional attirubutes to the
        normal output.

        The following snippet will generate the following output:

        .. code-block: yaml

              - name: Retrieve Remote Network Service IP from Prisma Access
                path: https://api.gpcloudservice.com/getAddrList/latest?fwType=gpcs_remote_network&addrType=public_ip
                operation: GET
                headers:
                  header-api-key: '{{ api_key }}'
                output_type: json
                outputs:
                  - name: status
                    capture_pattern: $.status
                  - name: fwType
                    capture_pattern: $.result.fwType
                  - name: addrList
                    capture_pattern: $.result.addrList


        .. code-block: python

            {
                'snippets': {
                    'Retrieve Remote Network Service IP from Prisma Access': {
                        'results': 'success',
                        'raw': {
                            'status': 'success',
                            'result': {
                                'fwType': 'gpcs_remote_network',
                                'addrListType': 'public_ip',
                                'total-count': 2,
                                'addrList': [
                                    'test-XXX:x.x.x.x',
                                    'pa220-test, pa220-test-2:x.x.x.x'
                                ]
                            }
                        }
                    }
                },
                'outputs': {
                    'status': 'success',
                    'fwType': 'gpcs_remote_network',
                    'addrList': "['test-XXX:x.x.x.x', 'pa220-test, pa220-test-2:x.x.x.x']"
                }
            }


        :return: dictionary of results from the REST Skillet execute or execute_async method
        """

        # this override is only here to provide the docstring
        return super().get_results()
