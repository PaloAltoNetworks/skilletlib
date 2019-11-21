# Copyright (c) 2018, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Authors: Adam Baumeister, Nathan Embery


import logging
import time
from abc import ABC
from abc import abstractmethod
from typing import List

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.snippet.base import Snippet

logger = logging.getLogger(__name__)


class Skillet(ABC):

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
        self.collections = self.skillet_dict['labels']['collection']
        self.context = dict()

    @abstractmethod
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

    @staticmethod
    def initialize_context(initial_context: dict) -> dict:
        """
        Child classes can override this to provide any initialization information in the context
        :param initial_context: Initial Context from user input, environment vars, etc
        :return: updated context with initial context items plus any initialization items
        """
        return initial_context

    def cleanup(self):
        pass

    def execute(self, initial_context: dict) -> dict:

        context = dict()

        try:
            context = self.initialize_context(initial_context)

            for snippet in self.get_snippets():
                # render anything that looks like a jinja template in the snippet metadata
                # mostly useful for xpaths in the panos case
                metadata = snippet.render_metadata(context)
                # check the 'when' conditional against variables currently held in the context
                if snippet.should_execute(context):
                    (output, status) = snippet.execute(context)
                    running_counter = 0
                    while status == 'running':
                        logger.info('Snippet still running...')
                        time.sleep(5)
                        (output, status) = snippet.get_output()
                        running_counter += 1
                        if running_counter > 60:
                            raise SkilletLoaderException('Snippet took too long to execute!')

                    returned_output = snippet.capture_outputs(output)
                    context.update(returned_output)

                else:
                    fail_action = metadata.get('fail_action', 'skip')
                    fail_message = metadata.get('fail_message', 'Aborted due to failed conditional!')
                    if fail_action == 'skip':
                        logger.debug(f'  Skipping Snippet: {snippet.name}')
                    else:
                        logger.debug('Conditional failed and found a fail_action')
                        logger.error(fail_message)
                        context['fail_message'] = fail_message
                        return context
        except SkilletLoaderException as sle:
            logger.error(f'Caught Exception during execution: {sle}')

        except Exception as e:
            logger.error(f'Exception caught: {e}')
        finally:
            self.cleanup()

        return context
