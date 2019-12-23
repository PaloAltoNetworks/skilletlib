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
        """
        Initialize the base skillet type
        :param s: loaded dictionary from the .meta-cnc.yaml file
        """

        self.skillet_dict = s
        self.name = self.skillet_dict['name']
        self.label = self.skillet_dict['label']
        self.snippet_stack = self.skillet_dict['snippets']
        self.type = self.skillet_dict['type']
        self.supported_versions = 'not implemented'
        self.variables = self.__initialize_variables(s['variables'])
        # path is needed only when snippets are held in a relative file path
        self.path = self.skillet_dict.get('snippet_path', '')
        self.labels = self.skillet_dict['labels']
        self.collections = self.skillet_dict['labels']['collection']
        self.context = dict()

    @abstractmethod
    def get_snippets(self) -> List[Snippet]:
        """
        Each skillet determines how it's snippets are to be loaded and initialized. Each Skillet type must
        implement this method.
        :return:
        """
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet = Snippet(snippet_def)
            snippet_list.append(snippet)

        return snippet_list

    def update_context(self, d: dict) -> dict:
        """
        Take the input dict d and update the skillet context. I.e. any variables passed in via environment variables
        will be used to update the context stored on this skillet.
        :param d: dictionary of key value pairs. Any keys that match 'variable' keys will be used to update the context
        :return: updated context stored on this skillet
        """
        for var in self.variables:
            if var['name'] in d:
                self.context[var['name']] = d[var['name']]
            else:
                self.context[var['name']] = var['default']

        return self.context

    def initialize_context(self, initial_context: dict) -> dict:
        """
        Child classes can override this to provide any initialization information in the context
        :param initial_context: Initial Context from user input, environment vars, etc
        :return: updated context with initial context items plus any initialization items
        """
        self.context.update(initial_context)
        self.update_context(initial_context)
        return self.context

    @staticmethod
    def __initialize_variables(vars_dict: dict) -> dict:
        """
        Ensure the proper default values are configured for each type of variable that may be present in the skillet
        :param vars_dict: Skillet 'variables' stanza
        :return: variables stanza with default values correctly parsed
        """

        for variable in vars_dict:
            default = variable.get('default', '')
            type_hint = variable.get('type_hint', 'text')
            if type_hint == "dropdown" and "dd_list" in variable:
                for item in variable.get('dd_list', []):
                    if 'key' in item and 'value' in item:
                        if default == item['key'] and default != item['value']:
                            # user set the key as the default and not the value, just fix it for them here
                            variable['default'] = item['value']
            elif type_hint == "radio" and "rad_list" in variable:
                rad_list = variable['rad_list']
                for item in rad_list:
                    if 'key' in item and 'value' in item:
                        if default == item['key'] and default != item['value']:
                            variable['default'] = item['value']
            elif type_hint == "checkbox" and "cbx_list" in variable:
                cbx_list = variable['cbx_list']
                for item in cbx_list:
                    if 'key' in item and 'value' in item:
                        if default == item['key'] and default != item['value']:
                            variable['default'] = item['value']

        return vars_dict

    def cleanup(self):
        pass

    def execute(self, initial_context: dict) -> dict:
        """
        The heart of the Skillet class. This method executes the skillet by iterating over all the skillets returned
        from the 'get_skillets' method. Each one is checked if it should be executed if a 'when' conditional attribute
        is found, and if so, is executed using the snippet execute method.
        :param initial_context: context of key values pairs to use for the execution. By default this is all the
        variables defined in the skillet file with their default values. Updates from user input, the environment, etc
        will override these default values vai the 'update_context' method.
        :return: a dict containing the updated context containing the output of each of the snippets
        """

        context = dict()
        returned_outputs = dict()

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

                    returned_output = snippet.capture_outputs(output, status)
                    returned_outputs.update(returned_output)
                    context.update(returned_output)

        except SkilletLoaderException as sle:
            logger.error(f'Caught Exception during execution: {sle}')

        except Exception as e:
            logger.error(f'Exception caught: {e}')
        finally:
            self.cleanup()

        return self.get_results(returned_outputs)

    def get_results(self, context: dict) -> dict:
        results = dict()
        for s in self.snippet_stack:
            snippet_name = s.get('name', '')
            if snippet_name in context:
                results[snippet_name] = context[snippet_name]

        return results


