import json
import logging
from typing import Tuple
from urllib.parse import quote

import urllib3
from requests import Response
from requests import Session

from .template import TemplateSnippet
from ..exceptions import SkilletLoaderException

logger = logging.getLogger(__name__)
urllib3.disable_warnings()


class RestSnippet(TemplateSnippet):
    """
    Rest Snippet
    """
    # required metadata items
    required_metadata = {'name'}

    name = ''
    path = ''

    template_metadata = {'path', 'element', 'headers'}

    output_type = 'rest'
    # optional metadata items and their default values
    optional_metadata = {
        'path': '',
        'operation': 'get',
        'payload': '',
        'headers': {},
        'content_type': '',
        'accepts_type': ''
    }

    operation = 'get'
    payload = ''
    headers = dict()
    content_type = ''
    accepts_type = ''

    def __init__(self, payload_str: str, metadata: dict, session: Session):

        # use element loaded in metadata if found, otherwise use passed in payload_str
        super().__init__(metadata.get('element', payload_str), metadata)
        # keep track of session from the parent skillet
        self.session = session

        if self.content_type != '':
            self.headers['Content-Type'] = self.content_type

        if self.accepts_type != '':
            self.headers['Accepts-Type'] = self.accepts_type

    def sanitize_metadata(self, metadata: dict) -> dict:
        """
        Clean and sanitize metadata elements in this snippet definition

        :param metadata: dict
        :return: dict
        """
        metadata = super().sanitize_metadata(metadata)

        # FIX for #59 - ensure operation is always lower cased
        if 'operation' in metadata:
            metadata['operation'] = str(metadata['operation']).lower()

        if metadata['operation'] not in ('post', 'get'):
            err = 'Supported operations are currently post and get only'
            raise SkilletLoaderException(f'Invalid metadata configuration: {err}')

        if 'path' in metadata:
            metadata['path'] = str(metadata['path']).strip().replace('\n', '')

        return metadata

    def execute(self, raw_context: dict) -> Tuple[str, str]:

        context = dict()

        if raw_context is not None:
            # always enforce quotes in the context
            for k, v in raw_context.items():
                if isinstance(v, str):
                    context[k] = quote(v)

        url = self.metadata['path']

        if self.operation == 'post':
            rendered_payload = self.metadata['element']
            if 'form' in self.headers.get('Content-Type', ''):
                payload = json.loads(rendered_payload)
            else:
                payload = rendered_payload

            response = self.session.post(url, data=payload, headers=self.metadata['headers'], verify=False)
            return self.__handle_response(response)

        # support 'noop' for #100
        elif self.operation == 'noop':
            return 'noop', 'success'

        else:
            # FIX for #59 - Ensure we pass headers to get operations properly
            response = self.session.get(url, verify=False, headers=self.metadata['headers'])
            return self.__handle_response(response)

    def __handle_response(self, response: Response) -> Tuple[str, str]:
        if not response.ok:
            logger.error(f'Failed to execute REST snippet {self.name}: {response.status_code}')
            return response.text, 'failure'
        else:

            # capture response headers into self.context for use by capture_variable for #156
            self.context['response_headers'] = dict(response.headers)

            if 'json' in response.headers.get('content-type', ''):
                r = response.json()
            else:
                r = response.text

            return r, 'success'
