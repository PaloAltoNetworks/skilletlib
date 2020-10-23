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

import copy
import html
import logging
import os
import sys
import time
from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import Generator
from typing import List

import yaml
from yaml.scanner import ScannerError

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.exceptions import SkilletValidationException
from skilletlib.snippet.base import Snippet
from skilletlib.snippet.template import SimpleTemplateSnippet

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not len(logger.handlers):
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


class Skillet(ABC):
    # each skillet type can override this and set what metadata attributes are required
    snippet_required_metadata = {'name'}

    # optional metadata that can be present on each snippet
    snippet_optional_metadata = dict()

    def __init__(self, s: dict):
        """
        Initialize the base skillet type

        :param s: loaded dictionary from the .meta-cnc.yaml file
        """

        self.skillet_dict = self.__normalize_skillet_dict(s)
        self.name = self.skillet_dict['name']
        self.label = self.skillet_dict['label']
        self.description = self.skillet_dict['description']
        self.snippet_stack = self.skillet_dict['snippets']
        self.type = self.skillet_dict['type']
        self.supported_versions = 'not implemented'
        self.variables = self.__initialize_variables(s['variables'])
        # path is needed only when snippets are held in a relative file path
        self.path = self.skillet_dict.get('snippet_path', '')
        self.labels = self.skillet_dict['labels']
        self.collections = self.skillet_dict['labels'].get('collection', list())
        self.context = dict()
        self.captured_outputs = dict()
        self.snippet_outputs = dict()

        # ensure all values are set appropriately in the snippet definition
        self.__validate_snippet_metadata()

        # initialize our snippets
        self.snippets = self.get_snippets()

        # update our list of declared variables
        self.declared_variables = self.get_declared_variables()

        debug = os.environ.get('SKILLET_DEBUG', False)

        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug('Debugging output enabled')

    @abstractmethod
    def get_snippets(self) -> List[Snippet]:
        """
        Each skillet determines how it's snippets are to be loaded and initialized. Each Skillet type must
        implement this method.

        :return: List of Snippets for this Skillet Class
        """
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet = Snippet(snippet_def)
            snippet_list.append(snippet)

        return snippet_list

    def load_template(self, template_path: str) -> str:
        """
        Utility method to load a template file and return the contents as str

        :param template_path: relative path to the template to load
        :return: str contents
        """
        if template_path == '' or template_path is None:
            logger.error('Refusing to load empty template path')
            return ''

        skillet_path = Path(self.path)
        template_file = skillet_path.joinpath(template_path).resolve()

        if template_file.exists():
            with template_file.open() as sf:
                return html.unescape(sf.read())

        else:
            # Add the snippet name here as well to allow for more context
            # fix for https://gitlab.com/panw-gse/as/panhandler/-/issues/19
            logger.error(f'Snippet: {self.name} has file attribute that does not exist')
            logger.error(f'Snippet file path is: {template_path}')
            raise SkilletLoaderException(f'Snippet: {self.name} - Could not resolve template path!')

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
        Child classes can override this to provide any initialization information in the context. For example, 'panos'
        skillets use this to set up and initialize a Panos device object

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

    def execute_async(self, initial_context: dict) -> Generator:
        """
        Returns a generator that can be used to iterate over the output as it's generated
        from each snippet. The calling application should call 'get_results' once the execute is complete

        :param initial_context: context of key values pairs to use for the execution. By default this is all the
        variables defined in the skillet file with their default values. Updates from user input, the environment, etc
        will override these default values via the 'update_context' method.
        :return: generator[str]
        """
        try:
            context = self.initialize_context(initial_context)
            logger.debug(f'Executing Async Skillet: {self.name}')

            for snippet in self.get_snippets():
                try:
                    # render anything that looks like a jinja template in the snippet metadata
                    # mostly useful for xpaths in the panos case
                    snippet.render_metadata(context)
                    # check the 'when' conditional against variables currently held in the context

                    if snippet.should_execute(context):
                        (output, status) = snippet.execute(context)
                        logger.debug(f'{snippet.name} - status: {status}')

                        if output:
                            logger.debug(f'{snippet.name} - output: {output}')

                        full_output = ''
                        while status == 'running':
                            # logger.info('Snippet still running...')
                            time.sleep(5)
                            (partial_output, status) = snippet.get_output()

                            full_output += partial_output

                            yield partial_output
                            output = full_output

                        # capture all outputs
                        snippet_outputs = snippet.get_default_output(output, status)
                        captured_outputs = snippet.capture_outputs(output, status)

                        if captured_outputs:
                            logger.debug(f'{snippet.name} - captured_outputs: {captured_outputs}')

                        self.snippet_outputs.update(snippet_outputs)
                        self.captured_outputs.update(captured_outputs)

                        context.update(snippet_outputs)
                        context.update(captured_outputs)

                except SkilletLoaderException as sle:
                    logger.error(f'Caught Exception during execution: {sle}')
                    snippet_outputs = snippet.get_default_output(str(sle), 'error')
                    logger.error(snippet_outputs)
                    self.snippet_outputs.update(snippet_outputs)

                except Exception as e:
                    logger.error(f'Exception caught: {e}')
                    snippet_outputs = snippet.get_default_output(str(e), 'error')
                    self.snippet_outputs.update(snippet_outputs)

        finally:
            self.cleanup()

        return None

    def execute(self, initial_context: dict) -> dict:
        """
        The heart of the Skillet class. This method executes the skillet by iterating over all the skillets returned
        from the 'get_skillets' method. Each one is checked if it should be executed if a 'when' conditional attribute
        is found, and if so, is executed using the snippet execute method.

        :param initial_context: context of key values pairs to use for the execution. By default this is all the
        variables defined in the skillet file with their default values. Updates from user input, the environment, etc
        will override these default values via the 'update_context' method.
        :return: a dict containing the updated context containing the output of each of the snippets
        """
        try:
            context = self.initialize_context(initial_context)
            logger.debug(f'Executing Skillet: {self.name}')

            for snippet in self.get_snippets():
                try:
                    # render anything that looks like a jinja template in the snippet metadata
                    # mostly useful for xpaths in the panos case
                    snippet.render_metadata(context)
                    # check the 'when' conditional against variables currently held in the context

                    if snippet.should_execute(context):
                        (output, status) = snippet.execute(context)
                        logger.debug(f'{snippet.name} - status: {status}')

                        if output:
                            logger.debug(f'{snippet.name} - output: {output}')

                        running_counter = 0

                        while status == 'running':
                            logger.info('Snippet still running...')
                            time.sleep(5)
                            (output, status) = snippet.get_output()
                            running_counter += 1

                            if running_counter > 60:
                                raise SkilletLoaderException('Snippet took too long to execute!')

                        # capture all outputs
                        snippet_outputs = snippet.get_default_output(output, status)
                        captured_outputs = snippet.capture_outputs(output, status)

                        if captured_outputs:
                            logger.debug(f'{snippet.name} - captured_outputs: {captured_outputs}')

                        self.snippet_outputs.update(snippet_outputs)
                        self.captured_outputs.update(captured_outputs)

                        context.update(snippet_outputs)
                        context.update(captured_outputs)

                except SkilletLoaderException as sle:
                    logger.error(f'Caught Exception during execution: {sle}')
                    snippet_outputs = snippet.get_default_output(str(sle), 'error')
                    logger.error(snippet_outputs)
                    self.snippet_outputs.update(snippet_outputs)

                except Exception as e:
                    logger.error(f'Exception caught: {e}')
                    snippet_outputs = snippet.get_default_output(str(e), 'error')
                    self.snippet_outputs.update(snippet_outputs)

        finally:
            self.cleanup()

        return self.get_results()

    def get_results(self) -> dict:
        """
        Returns the results from the skillet execution. This must be called manually if using 'execute_async'. The
        returned dict will include a 'snippets' dictionary that contains a key for each snippet that was executed. Each
        snippet dictionary will contain the 'results' and 'raw' attributes.

        .. code-block:: json

            {
              'snippets': {
                'check_hostname_again': {
                  'results': 'success',
                  'changed': True
                }
              },
              'outputs': {
                'url-db': 'paloaltonetworks',
                'pa-version': '1.5.0'
              },
              'result': 'success',
              'changed': True
            }


        :return: dictionary of results from the Skillet execute or execute_async method
        """

        results = self._get_snippet_results()

        results['outputs'] = self.captured_outputs
        return self._parse_output_template(results)

    def _get_snippet_results(self) -> dict:
        """
        Iterate the snippets in the skillet and collect their combined results into the 'results' dict

        :return: dict with 'snippets' key
        """
        results = dict()
        results['snippets'] = dict()

        for s in self.snippet_stack:
            snippet_name = s.get('name', '')

            if snippet_name in self.snippet_outputs:
                results['snippets'][snippet_name] = self.snippet_outputs[snippet_name]

        return results

    def _parse_output_template(self, results: dict) -> dict:
        """
        Check for the presence of the output_template label. If found, load and parse the template
        using the results. The parsed output will be placed in the 'output_template' key in the results

        :param results: results of the skillet execution
        :return: results plus the output_template value if found
        """
        try:
            if 'output_template' in self.labels:
                output_template = self.load_template(self.labels['output_template'])
                template_snippet = SimpleTemplateSnippet(output_template)
                # create context dict for template parsing
                # add all outputs as 'top-level' attributes
                context = results.get('outputs', {})
                # add other keys as top-level attributes as well...
                for k, v in results.items():
                    if k != 'outputs':
                        context[k] = v
                results['output_template'] = template_snippet.template(context)

        except SkilletLoaderException as sle:
            print(sle)

        return results

    def __validate_snippet_metadata(self) -> None:
        """
        Perform snippet metadata validation before we attempt to instantiate the snippet

        This will throw a SkilletLoaderException if a required attribute is not present in the metadata
        Will also set all optional metadata attributes with their default values

        :raises: SkilletLoaderException if a required field is not present
        :return: None
        """
        for s in self.snippet_stack:
            name = s.get('name', '')
            for r in self.snippet_required_metadata:
                if r not in s:
                    raise SkilletLoaderException(f'Invalid snippet metadata configuration: attribute: {r} '
                                                 f'is required for snippet: {name}')

            for k, v in self.snippet_optional_metadata.items():
                if k not in s:
                    s[k] = v

    def get_declared_variables(self) -> List[str]:
        """
        Return a list of all variables defined in all the snippets that are not defined as an output

        :return: list of variable names
        """

        # get list of output_vars from all snippets using double list comprehension
        output_vars = [o for s in self.get_snippets() for o in s.get_output_variables()]

        # get list of all variables defined in all snippets that are NOT in the output_vars
        dv = [x for s in self.get_snippets() for x in s.get_snippet_variables() if x not in output_vars]

        # convert to set and back to list to remove dups
        return list(set(dv))

    @staticmethod
    def __normalize_skillet_dict(skillet: dict) -> dict:

        if skillet is None:
            skillet = dict()

        if type(skillet) is not dict:
            skillet = dict()

        if 'name' not in skillet:
            skillet['name'] = 'Unknown Skillet'

        if 'label' not in skillet:
            skillet['label'] = 'Unknown Skillet'

        if 'type' not in skillet:
            skillet['type'] = 'template'

        if 'description' not in skillet:
            skillet['description'] = 'Unknown Skillet'

        if 'variables' not in skillet:
            skillet['variables'] = list()

        if 'snippets' not in skillet:
            skillet['snippets'] = list()

        if 'labels' not in skillet:
            skillet['labels'] = dict()

        if 'collection' not in skillet['labels']:
            skillet['labels']['collection'] = list()
            skillet['labels']['collection'].append('Kitchen Sink')

        return skillet

    def dump_yaml(self) -> str:
        """
        Convert this Skillet into a YAML formatted string

        :return: YAML formatted string
        """
        try:

            # remove non-essential non-portable items from the dict before dumping
            safe_skillet_dict = copy.deepcopy(self.skillet_dict)

            safe_skillet_dict.pop('snippet_path', None)
            safe_skillet_dict.pop('app_data', None)

            # source https://stackoverflow.com/a/45004775
            yaml.SafeDumper.org_represent_str = yaml.SafeDumper.represent_str

            def repr_str(dumper, data):
                if '\n' in data:
                    return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')

                return dumper.org_represent_str(data)

            yaml.add_representer(str, repr_str, Dumper=yaml.SafeDumper)

            return yaml.safe_dump(safe_skillet_dict, indent=4)

        except (ScannerError, ValueError) as err:
            raise SkilletValidationException(f'Could not dump Skillet as YAML: {err}')
