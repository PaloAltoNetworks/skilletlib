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

# Authors: Nathan Embery

import json
import logging
import re
import xml.etree.ElementTree as elementTree
from abc import ABC
from abc import abstractmethod
from base64 import urlsafe_b64encode
from copy import deepcopy
from typing import Any
from typing import Tuple
from xml.etree.ElementTree import ParseError

import jmespath
import xmltodict
from jinja2 import BaseLoader
from jinja2 import Environment
from jinja2 import TemplateError
from jinja2 import meta
from jinja2.exceptions import TemplateAssertionError
from jinja2.exceptions import UndefinedError
from jinja2_ansible_filters import AnsibleCoreFiltersExtension
from jsonpath_ng import parse
from lxml import etree
from passlib.hash import md5_crypt

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.exceptions import SkilletValidationException

logger = logging.getLogger(__name__)


class Snippet(ABC):
    """
    BaseSnippet implements a basic Noop snippet
    """
    # set of required metadata, each snippet will define what attributes are required in the snippet definition
    # by default, we only require a 'name' attribute, but sub-classes will require more
    required_metadata = {'name'}

    # dict of optional metadata  and their default values. These values will be set on the snippet class but
    # will not throw an exception is they are not present
    optional_metadata = dict()

    # metadata fields that should be considered templates and rendered
    template_metadata = set()

    # conditional metadata fields should also be considered templates but are not strings
    # these fields should be wrapped in a string before checking for undefined variables
    # For example, see the pan_validation snippet field 'test'
    conditional_template_metadata = set()

    # set a default output type. this can be overridden for each SnippetType. This is used to determine the default
    # output handler to use for each snippet class. This can be set on a per snippet basis, but this allows a
    # short-cut on each
    output_type = 'xml'

    # snippet classes can set a list of keys that xmltodict will convert to lists in __handler_xml_outputs
    xml_force_list_keys = []

    def __init__(self, metadata: dict):

        # first validate all the required fields are present in the metadata (snippet definition)
        self.metadata = self.sanitize_metadata(metadata)
        # always keep a fresh copy of the metadata around for looping
        self.original_metadata = deepcopy(self.metadata)
        # always have a default name, subclasses will set additional fields on the class
        self.name = self.metadata['name']
        # set up jinja environment and add any custom filters. Snippet sub-classes can override __add_filters
        # to append additional filters. See the PanosSnippet class for an example
        self.__init_env()

        # set all the required fields with their values from the snippet definition
        for k in self.required_metadata:
            setattr(self, k, self.metadata[k])

        # iterate the optional_metadata dict and set the default values
        # if they have not been set in the snippet metadata directly
        for k, v in self.optional_metadata.items():
            if v is None:
                continue
            if k in self.metadata:
                setattr(self, k, self.metadata[k])
            else:
                setattr(self, k, v)
                self.metadata[k] = v

        self.context = dict()

    def update_context(self, context: dict) -> dict:
        """
        This will update the snippet context with the passed in dict.
        This gets called inside of 'should_execute'

        :param context: dict of the outer context
        :return: newly updated context
        """
        self.context.update(context)
        return self.context

    @abstractmethod
    def execute(self, context: dict) -> Tuple[str, str]:
        """
        Execute this Snippet and return a tuple consisting on raw output and a string representing
        success, failure, or running.

        Each snippet sub class must override this method!

        :param context: context to use for variable interpolation
        :return: Tuple containing raw snippet output and string indicated success or failure
        """
        return '', 'success'

    def should_execute(self, context: dict) -> bool:
        """
        Evaluate 'when' conditionals and return a bool if this snippet should be executed

        :param context: jinja context containing previous outputs and user supplied variables
        :return: boolean
        """

        logger.debug(f'Checking snippet: {self.name}')

        # hook for pre-conditional checks
        context = self.update_context(context)

        # check if this snippet should be filtered out of execution based on the context object __filter_snippets
        if self.is_filtered(context):
            logger.debug('Skipping this snippet due to snippet inclusion rules')
            return False

        if 'when' not in self.metadata:
            # always execute when no when conditional is present
            logger.debug(f'No conditional present, proceeding with skillet: {self.name}')
            return True

        results = self.execute_conditional(self.metadata['when'], context)
        logger.debug(f'  Conditional Evaluation results: {results} ')
        return results

    def is_filtered(self, context) -> bool:
        """
        Determines if a snippet should be available for execution based on the presence of the `__filter_snippets`
        object in the context. Snippets can be filtered by the following:

        include_by_name: list of names to check. Only snippet names included in this list will be executed
        include_by_tag: list of tags to check. Only snippets with those tags will be executed
        include_by_regex: regular expression match. Only snippets whose name matches the regex will be executed

        any snippet that does not match any of the above rules will be filtered out. The rules are inclusive OR

        :param context: Snippet Context
        :return: bool
        """

        # by default, nothing is filtered out
        is_filtered = None

        if '__filter_snippets' in context:
            logger.debug('filtering snippet...')

            fc = context['__filter_snippets']
            if type(fc) is not dict:
                logger.warning('Snippet filter is malformed...')
                return False
            for filter_def in ('include_by_tag', 'include_by_name', 'include_by_regex', 'exclude_by_tag',
                               'exclude_by_name', 'exclude_by_regex'):
                if filter_def in fc:
                    if type(fc[filter_def]) is list:
                        for item in fc[filter_def]:
                            is_filtered = self.__consider_filter(filter_def, item)
                            # we have discovered this snippet should not be filtered, jump out now
                            if is_filtered is not None:
                                return is_filtered

                    elif type(fc[filter_def]) is str:
                        item = fc[filter_def]
                        is_filtered = self.__consider_filter(filter_def, item)

                # we have discovered this snippet should not be filtered, jump out now
                if is_filtered is not None:
                    return is_filtered

            # we have considered all rules, and still no determination, however, because we have some rules due to
            # presence of '__filter_snippets' any item that is not specifically included or excluded, should be
            # excluded

            if is_filtered is None:
                return True
        else:
            # there is not filter snippets config present, so include all snippets by default
            return False

    def __consider_filter(self, filter_def: str, item: str) -> (bool, None):
        """
        Rules that positively match are returned immediately, any snippet that does NOT specifically match any rule
        is excluded (True response == snippet is NOT executed)

        :param filter_def: type of filter to consider
        :param item: specific filter item
        :return: bool or None if not match
        """
        if filter_def == 'include_by_name':
            # this name matches, do NOT filter it out
            if self.name == item:
                return False

        elif filter_def == 'exclude_by_name':
            # name matches exclusion rule, filter it out
            if self.name == item:
                return True

        if filter_def == 'include_by_tag':
            if self.__has_tag(item):
                # snippet has this tag, do not filter out
                return False

        elif filter_def == 'exclude_by_tag':
            if self.__has_tag(item):
                # snippet has this tag, filter it out
                return True

        if '_by_regex' in filter_def:
            match = re.match(item, self.name)
            if 'include_by_regex' == filter_def:
                if match:
                    return False
            elif 'exclude_by_regex' == filter_def:
                if match:
                    return True

        # this snippet does not match any of the rules above, one way or the other, so filter it out of consideration
        return None

    def get_loop_parameter(self) -> list:
        """
        Returns the loop parameter for this snippet. If a loop parameter is not defined in the snippet def, this
        returns a list with a single blank str. Otherwise, return the value of the loop parameter as a list.

        :return: value of loop_parameter from the context or a list with a single blank str
        """

        default_list = ['']

        if 'loop' in self.metadata:
            loop_var_name = self.metadata['loop']

            if loop_var_name not in self.context:
                return default_list

            loop_var = self.context.get(loop_var_name, list())

            if isinstance(loop_var, list):
                return loop_var

            else:
                return [loop_var]

        return default_list

    def __has_tag(self, tag_to_check: str) -> bool:
        """
        Check if this snippet has a 'tag' or 'tags' attribute and if one of those items
        match the tag_to_check value

        :param tag_to_check: str of tag to check
        :return: boolean True if a tag or tags list item matches
        """
        if 'tag' in self.metadata:
            if type(self.metadata['tag']) is list:
                tags_list = self.metadata['tag']
            else:
                tags_list = [self.metadata['tag']]

        elif 'tags' in self.metadata:
            if type(self.metadata['tags']) is list:
                tags_list = self.metadata['tags']
            else:
                tags_list = [self.metadata['tags']]
        else:
            return False

        for tag in tags_list:
            if tag_to_check == tag:
                return True

        return False

    def execute_conditional(self, test: str, context: dict) -> bool:
        """
        Evaluate 'test' conditionals and return a bool

        :param test: string of the conditional to execute
        :param context: jinja context containing previous outputs and user supplied variables
        :return: boolean
        """
        try:
            test_str = '{{%- if {0} -%}} True {{%- else -%}} False {{%- endif -%}}'.format(test)
            test_template = self._env.from_string(test_str)
            results = test_template.render(context)
            if str(results).strip() == 'True':
                return True
            else:
                return False
        except UndefinedError as ude:
            logger.error(ude)
            # always return false on error condition
            return False
        except TypeError as te:
            logger.error(te)
            return False
        except TemplateAssertionError as tae:
            logger.error(tae)
            raise SkilletValidationException('Malformed Jinja expression!')
        except Exception as e:
            # catch-all - always return false on other error conditions
            logger.error(e)
            logger.error(type(e))
            return False

    def get_output(self) -> Tuple[str, str]:
        """
        get_output can be used when a snippet executes async and cannot or will not return output right away
        snippets that operate async must override this method

        :return: Tuple containing the skillet output as a str and a str indicating success of failure
        """

        return '', 'success'

    def get_default_output(self, results: str, status: str) -> dict:
        """
        each snippet type can override this method to provide it's own default output. This is used
        when there are no variables defined to be captured

        :param results: raw output from snippet execution
        :param status: status of the snippet.execute method
        :return: dict of default outputs
        """

        r = {
            self.name: {
                'results': status,
                'raw': results
            }
        }
        return r

    def capture_outputs(self, results: str, status: str) -> dict:
        """
        All snippet output or portions of snippet output can be captured and saved on the context as a new variable

        :param results: the raw output from the snippet execution
        :param status: status of the snippet.execute method
        :return: a dictionary containing all captured variables
        """

        captured_outputs = dict()

        output_type = self.metadata.get('output_type', self.output_type)

        # check if this snippet type wants to handle it's own outputs
        if hasattr(self, f'handle_output_type_{output_type}'):
            func = getattr(self, f'handle_output_type_{output_type}')
            return func(results)

        # added for issue #151 - snippets can return 'failure' after catching an exception in which case
        # we cannot capture outputs as the output may be an exception message instead of the expected results
        if status != 'success':
            logger.error('Not capturing outputs for failed snippet execution...')
            return captured_outputs

        # otherwise, check all the normal types here
        if 'outputs' not in self.metadata:
            return captured_outputs

        for output in self.metadata['outputs']:

            outputs = dict()

            if 'name' not in output:
                continue

            # allow jinja syntax in capture_pattern, capture_value, capture_object etc
            output = self.__render_output_metadata(output, self.context)

            if not results:
                outputs[output['name']] = ''
                continue

            if 'capture_variable' in output:
                outputs[output['name']] = self.render(output['capture_variable'], self.context)

            elif 'capture_json' in output:
                outputs[output['name']] = json.loads(self.render(output['capture_json'], self.context))

            elif 'capture_expression' in output:
                expression = self._env.compile_expression(output['capture_expression'])
                value = expression(self.context)
                if isinstance(value, list) and 'filter_items' in output:
                    outputs[output['name']] = self.__filter_outputs(output, value, self.context)
                else:
                    outputs[output['name']] = value

            else:

                if output_type == 'xml':
                    outputs = self.__handle_xml_outputs(output, results)
                elif output_type == 'manual':
                    outputs = self.__handle_manual_outputs(output, results)
                elif output_type == 'text':
                    outputs = self.__handle_text_outputs(output, results)
                elif output_type == 'json':
                    outputs = self.__handle_json_outputs(output, results)
            # elif output_type == 'base64':
            #     outputs = self._handle_base64_outputs(results)

            # elif output_type == 'manual':
            #     outputs = self._handle_manual_outputs(results)
            # elif output_type == 'text':
            #     outputs = self.__handle_text_outputs(results)
            # # sub classes can handle their own output types
            # # see panos/__handle_validation for example
            # elif hasattr(self, f'handle_output_type_{output_type}'):
            #     func = getattr(self, f'handle_output_type_{output_type}')
            #     outputs = func(results)
            captured_outputs.update(outputs)
            self.context.update(outputs)

        return captured_outputs

    def __render_output_metadata(self, output: dict, context: dict) -> dict:
        # fix for #78 allow filter_items to be rendered
        keys = ('name', 'capture_value', 'capture_pattern', 'capture_object', 'capture_list', 'filter_items')
        for k in keys:
            if k in output:
                output[k] = self.render(output[k], context)

        return output

    def __filter_outputs(self, output_definition: dict, output: (str, dict, list), local_context: dict) -> (list, None):
        """
        Filter OUT items that do not pass the test

        :param output_definition: the output definition from the skillet
        :param output: the captured object to test
        :param local_context: local context for the jinja expression based tests
        :return: a list of the items that passed the test, or all items if there is not test defined
        """
        if 'filter_items' not in output_definition:
            return output

        # grab the test string to evaluate
        test_str = output_definition['filter_items']

        # keep a new list of all the items that have matched the test
        filtered_items = list()

        if isinstance(output, list):
            for item in output:
                local_context['item'] = item
                results = self.execute_conditional(test_str, local_context)
                if results:
                    filtered_items.append(item)

            return filtered_items

        elif isinstance(output, str) or isinstance(output, dict):
            local_context['item'] = output
            results = self.execute_conditional(test_str, local_context)
            if results:
                filtered_items.append(output)

        return filtered_items

    def render(self, template_str: str, context: (dict, None)) -> str:
        """
        Convenience method to quickly render a template_str using the provided context

        :param template_str: jinja2 template to render
        :param context: context to pass to the jinja2 environment
        :return: rendered string
        """
        if context is None:
            context = self.context

        if not isinstance(template_str, str):
            return template_str

        t = self._env.from_string(template_str)
        return t.render(context)

    def get_variables_from_template(self, template_str: str) -> list:
        """
        Returns a list of jinja2 variable found in the template

        :param template_str: jinja2 template
        :return: list of variables declared in the template
        """

        try:
            parsed_template_str = self._env.parse(template_str)
            return meta.find_undeclared_variables(parsed_template_str)

        except TemplateError as te:
            logger.error('Could not parse template string in get_variables_from_template')
            raise SkilletValidationException(f'Error Parsing template {te}')

    def get_output_variables(self) -> list:
        """
        Returns a list of all output variables. This is used to determine if a snippet variable should be considered
        undeclared.

        :return: list of str representing output variable names
        """

        return [x['name'] for x in self.metadata.get('outputs', dict()) if 'name' in x]

    def get_snippet_variables(self) -> list:
        """
        Returns a list of variables defined in this snippet that are NOT defined as outputs

        :return: list of str representing variables found in the jinja templates
        """

        variables = list()
        for i in self.template_metadata:
            if i in self.metadata:

                # ensure we check for conditional template metadata as well as normal templated metadata
                # see pan_validation 'test' attribute as an example
                if i in self.conditional_template_metadata:
                    test_str = "{{ " + str(self.metadata[i]) + " }}"
                else:
                    test_str = self.metadata[i]
                found_vars = self.get_variables_from_template(test_str)

                for f in found_vars:
                    if f not in variables:
                        variables.append(f)

        return variables

    def sanitize_metadata(self, metadata: dict) -> dict:
        """
        method to sanitize metadata. Each snippet type can override this provide extra logic over and above
        just checking the required and optional fields

        :param metadata: snippet metadata
        :return: sanitized snippet metadata
        """
        return metadata

    def render_metadata(self, context: dict) -> dict:
        """
        Each snippet sub class can override this method to perform jinja variable interpolation on various items
        in it's snippet definition. For example, the PanosSnippet will check the 'xpath' attribute and perform
        the required interpolation.

        This handles regular strings, lists, and dictionaries such as:

        in snippet class
        template_metadata = {'render_me', 'render_all', 'render_list'}

        in metadata
        snippets:
         - name: render_me_snippet
           render_me: render_{{ this }}
         - name: render_all_snippet
           render_all:
             a_key: some_{{ value }}
             another_key: some_other_{{ value }}
         - name: render_list_snippet
           render_list:
             - here_is_a_{{ value }}
             - another_{{ value }}

        :param context: context from environment
        :return: metadata with jinja rendered variables
        """
        self.context.update(context)

        # render all template metadata fields
        for key_name in self.template_metadata:

            if key_name in self.metadata:
                key = self.metadata[key_name]

                if isinstance(key, str):
                    rendered_str = self.render(key, context)
                    self.metadata[key_name] = rendered_str

                elif isinstance(key, dict):
                    rendered_dict = dict()
                    for k, v in key.items():
                        rendered_dict[k] = self.render(v, context)

                    self.metadata[key_name] = rendered_dict

                elif isinstance(key, list):
                    rendered_list = list()
                    for v in key:
                        rendered_list.append(self.render(v, context))

                    self.metadata[key_name] = rendered_list

        return self.metadata

    def reset_metadata(self):
        """
        Reset the metadata to the original metadata. This is used during looping
        so we can render items in the metadata on each iteration.

        :return: None
        """
        self.metadata = deepcopy(self.original_metadata)

    # define functions for custom jinja filters
    @staticmethod
    def __md5_hash(txt: str) -> str:
        """
        Returns the MD5 Hashed secret for use as a password hash in the PAN-OS configuration

        :param txt: text to be hashed
        :return: password hash of the string with salt and configuration information. Suitable to place in the phash field
        in the configurations
        """

        return md5_crypt.hash(txt)

    @staticmethod
    def __json_query(obj: dict, query: str) -> Any:
        """
        JMESPath query, jmespath.org for examples

        :param query: JMESPath query string
        :param obj: object to be queried
        """
        if not isinstance(query, str):
            raise SkilletLoaderException('json_query requires an argument of type str')
        path = jmespath.search(query, obj)
        return path

    @staticmethod
    def __slugify(txt: str) -> str:

        txt = re.sub(r'\s+', '_', txt)
        txt = re.sub(r'[^\w+\-]', '', txt)
        txt = re.sub(r'-', '_', txt)
        txt = re.sub(r'__', '_', txt)
        txt = re.sub(r'^_+', '', txt)
        txt = re.sub(r'_+$', '', txt)

        return txt

    def __init_env(self) -> None:
        """
        init the jinja2 environment and add any required filters

        :return: Jinja2 environment object
        """
        self._env = Environment(loader=BaseLoader, extensions=[AnsibleCoreFiltersExtension])
        self._env.filters["md5_hash"] = self.__md5_hash
        self._env.filters["slugify"] = self.__slugify
        self._env.filters["s"] = self.__slugify
        self._env.filters['json_query'] = self.__json_query
        self.add_filters()

    def add_filters(self) -> None:
        """
        Each snippet sub-class can add additional filters. See the PanosSnippet for examples

        :return: None
        """
        pass

    def __handle_text_outputs(self, output_definition: dict, results: str) -> dict:
        """
        Parse the results string as a text blob into a single variable.

        - name: system_info
          path: /api/?type=op&cmd=<show><system><info></info></system></show>&key={{ api_key }}
          output_type: text
          outputs:
            - name: system_info_as_xml

        :param results: results string from the action
        :return: dict of outputs, in this case a single entry
        """
        outputs = dict()
        output_name = output_definition.get('name', self.name)
        outputs[output_name] = ''

        # enhancement for https://gitlab.com/panw-gse/as/skilletlib/-/issues/86
        if 'capture_value' in output_definition:
            # allow capture_value to be equivalent to capture_pattern
            output_definition['capture_pattern'] = output_definition['capture_value']

        if 'capture_object' in output_definition:
            # allow capture_object to be equivalent to capture_list
            output_definition['capture_list'] = output_definition['capture_object']

        if 'capture_pattern' in output_definition:
            # this is a regex pattern we should use for a match
            pattern = re.compile(output_definition['capture_pattern'])
            matches = pattern.findall(results)
            if matches:
                # capture pattern should only return the first match
                outputs[output_name] = matches[0]

        elif 'capture_list' in output_definition:
            # this is a regex pattern we should use for a match
            pattern = re.compile(output_definition['capture_list'])
            matches = pattern.findall(results)
            if matches:
                # capture list should return only the full list of matches unless filter_items is present
                if 'filter_items' in output_definition:
                    outputs[output_name] = self.__filter_outputs(output_definition, matches, self.context)
                else:
                    outputs[output_name] = matches
            else:
                # no matches should return an empty list
                outputs[output_name] = list()

        else:
            output_name = output_definition.get('name', self.name)
            outputs[output_name] = results

        return outputs

    def __handle_xml_outputs(self, output_definition: dict, results: str) -> dict:
        """
        Parse the results string as an XML document
        Example skillet.yaml snippets section:
        snippets:

          - name: system_info
            path: /api/?type=op&cmd=<show><system><info></info></system></show>&key={{ api_key }}
            output_type: xml
            outputs:
              - name: hostname
                capture_value: result/system/hostname
              - name: uptime
                capture_value: result/system/uptime
              - name: sw_version
                capture_value: result/system/sw-version


        :param results: string as returned from some action, to be parsed as XML document
        :return: dict containing all outputs found from the capture pattern in each output
        """

        captured_output = dict()

        def unique_tag_list(elements: list) -> bool:
            tag_list = list()
            for el in elements:
                # some xpath queries can return a list of str
                if isinstance(el, str):
                    return False

                if el.tag not in tag_list:
                    tag_list.append(el.tag)

            if len(tag_list) == 1:
                # all tags in this list are the same
                return False
            else:
                # there are unique tags in this list
                return True

        def convert_entry(el: elementTree.Element):
            # force_lists always returns a list even though in most cases, we really only want a single item
            # due to an exact xpath match. However, we might still want force_list to apply further down in the
            # the document.
            tag_name = el.tag

            res = xmltodict.parse(elementTree.tostring(el),
                                  force_list=self.xml_force_list_keys)

            if tag_name not in self.xml_force_list_keys:
                return res

            if tag_name in res and \
                    isinstance(res[tag_name], list) and \
                    len(res[tag_name]) == 1:
                # unwind unnecessary list at the top level here
                return {tag_name: res[tag_name][0]}

            return res

        try:
            xml_doc = etree.XML(results)

            # xml_doc = elementTree.fromstring(results)
            # allow jinja syntax in capture_pattern, capture_value, capture_object etc

            local_context = self.context.copy()
            output = self.__render_output_metadata(output_definition, local_context)

            var_name = output['name']
            if 'capture_pattern' in output or 'capture_value' in output:

                if 'capture_value' in output:
                    capture_pattern = output['capture_value']
                else:
                    capture_pattern = output['capture_pattern']

                # by default we will attempt to return the text of the found element
                return_type = 'text'
                entries = xml_doc.xpath(capture_pattern)
                logger.debug(f'found entries: {entries}')
                if len(entries) == 0:
                    captured_output[var_name] = ''
                elif len(entries) == 1:
                    entry = entries.pop()
                    if isinstance(entry, str):
                        captured_output[var_name] = str(entry)
                    else:
                        if len(entry) == 0:
                            # this tag has no children, so try to grab the text
                            if return_type == 'text':
                                captured_output[var_name] = str(entry.text).strip()
                            else:
                                captured_output[var_name] = entry.tag
                        else:
                            # we have 1 Element returned, so the user has a fairly specific xpath
                            # however, this element has children itself, so we can't return a text value
                            # just return the tag name of this element only
                            captured_output[var_name] = entry.tag
                else:
                    # we have a list of elements returned from the users xpath query
                    capture_list = list()
                    # are there unique tags in this list? or is this a list of the same tag names?
                    if unique_tag_list(entries):
                        return_type = 'tag'
                    for entry in entries:
                        if isinstance(entry, str):
                            capture_list.append(entry)
                        else:
                            if len(entry) == 0:
                                if return_type == 'text':
                                    if entry.text is not None:
                                        capture_list.append(entry.text.strip())
                                    else:
                                        # If there is no text, then try to grab a sensible attribute
                                        # if you need more control than this, then you should first
                                        # capture_object to convert to a python object then use a jinja filter
                                        # to get what you need
                                        if 'value' in entry.attrib:
                                            capture_list.append(entry.attrib.get('value', ''))
                                        elif 'name' in entry.attrib:
                                            capture_list.append(entry.attrib.get('name', ''))
                                        else:
                                            capture_list.append(json.dumps(dict(entry.attrib)))
                                else:
                                    capture_list.append(entry.tag)
                            else:
                                capture_list.append(entry.tag)

                    captured_output[var_name] = capture_list

            elif 'capture_object' in output:
                capture_pattern = output['capture_object']
                entries = xml_doc.xpath(capture_pattern)

                if len(entries) == 0:
                    captured_output[var_name] = None
                elif len(entries) == 1:
                    captured_output[var_name] = convert_entry(entries.pop())

                else:
                    capture_list = list()
                    for entry in entries:
                        capture_list.append(convert_entry(entry))

                    # FIXME - isn't this duplicated below?
                    captured_output[var_name] = self.__filter_outputs(output, capture_list, self.context)

            elif 'capture_list' in output:
                capture_pattern = output['capture_list']
                entries = xml_doc.xpath(capture_pattern)

                capture_list = list()
                for entry in entries:
                    if isinstance(entry, str):
                        capture_list.append(entry)
                    else:
                        capture_list.append(convert_entry(entry))

                captured_output[var_name] = capture_list

            elif 'capture_xml' in output:
                capture_pattern = output['capture_xml']
                entries = xml_doc.xpath(capture_pattern)
                if len(entries) == 0:
                    captured_output[var_name] = None
                elif len(entries) == 1:
                    captured_output[var_name] = etree.tostring(entries.pop(), encoding='unicode')
                else:
                    outer_tag = etree.fromstring('<xml/>')
                    for e in entries:
                        outer_tag.append(e)
                    found_entries_str = etree.tostring(outer_tag, encoding='unicode')
                    captured_output[var_name] = found_entries_str

                # short circuit return here as it makes no sense to do the filtering on a plain string object
                return captured_output
            # filter selected items here
            captured_output[var_name] = self.__filter_outputs(output, captured_output[var_name], local_context)

        except ParseError:
            logger.error('Could not parse XML document in output_utils')
            # just return blank captured_outputs here
            raise SkilletLoaderException(f'Could not parse output as XML in {self.name}')

        return captured_output

    def _handle_base64_outputs(self, results: str) -> dict:
        """
        Parses results and returns a dict containing base64 encoded values

        :param results: string as returned from some action, to be encoded as base64
        :return: dict containing all outputs found from the capture pattern in each output
        """

        outputs = dict()

        snippet_name = 'unknown'
        if 'name' in self.metadata:
            snippet_name = self.metadata['name']

        try:
            if 'outputs' not in self.metadata:
                logger.info(f'No output defined in this snippet {snippet_name}')
                return outputs

            for output in self.metadata['outputs']:
                if 'name' not in output:
                    continue

                results_as_bytes = bytes(results, 'utf-8')
                encoded_results = urlsafe_b64encode(results_as_bytes)
                var_name = output['name']
                outputs[var_name] = encoded_results.decode('utf-8')

        except TypeError:
            raise SkilletLoaderException(f'Could not base64 encode results {snippet_name}')

        return outputs

    def __handle_json_outputs(self, output_definition: dict, results: str) -> dict:
        """
        Parses results using jsonpath_ng query syntax
        output_type: json
        outputs:
          - name: salt_auth_token
            capture_object: '$.return[0].token'

        See here for more jsonpath examples: https://github.com/h2non/jsonpath-ng

        :param results: string as returned from some action, to be parsed as JSON
        :return: dict containing all outputs found from the capture pattern in each output
        """
        captured_output = dict()

        local_context = self.context.copy()
        output = self.__render_output_metadata(output_definition, local_context)

        try:
            for i in ('capture_pattern', 'capture_value', 'capture_object'):
                if i in output:
                    capture_pattern = output[i]
                else:
                    continue

                if 'name' not in output:
                    continue

                # some Skillet types may return us json already, check if results are actually a str like object
                # before trying to convert
                if type(results) is not str and type(results) is not bytes and type(results) is not bytearray:
                    json_object = results
                else:
                    json_object = json.loads(results)

                var_name = output['name']

                # short cut for just getting all the results
                if capture_pattern == '$' or capture_pattern == '.':
                    captured_output[var_name] = json_object
                    continue

                jsonpath_expr = parse(capture_pattern)
                result = jsonpath_expr.find(json_object)
                if len(result) == 1:
                    captured_output[var_name] = str(result[0].value)
                else:
                    # FR #81 - add ability to capture from a list
                    capture_list = list()
                    for r in result:
                        capture_list.append(r.value)

                    captured_output[var_name] = capture_list

        except ValueError as ve:
            logger.error('Caught error converting results to json')
            captured_output['fail_message'] = str(ve)
        except Exception as e:
            logger.error('Unknown exception here!')
            logger.error(e)
            captured_output['fail_message'] = str(e)

        return captured_output

    def __handle_manual_outputs(self, output_definition: dict, results: str) -> dict:
        """
        Manually set a value in the context, this could be useful with 'when' conditionals

        :param results: results from snippet execution, ignored in this method
        :return: dict containing manually defined name / value pair
        """
        outputs = dict()

        if 'name' not in output_definition or 'capture_value' not in output_definition:
            return outputs

        var_name = output_definition['name']
        value = str(self.render(output_definition['capture_value'], self.context))

        outputs[var_name] = value

        return outputs

    def _handle_manual_outputs(self, results: str) -> dict:
        """
        Manually set a value in the context, this could be useful with 'when' conditionals

        :param results: results from snippet execution, ignored in this method
        :return: dict containing manually defined name / value pair
        """
        outputs = dict()

        try:
            if 'outputs' not in self.metadata:
                logger.info('No outputs defined in this snippet')
                return outputs

            for output in self.metadata['outputs']:

                if 'name' not in output:
                    continue

                var_name = output['name']
                value = output['value']

                outputs[var_name] = value

        except KeyError as ke:
            logger.error(f'Could not locate required attributes for manual output: {ke} in snippet: {self.name}')

        return outputs
