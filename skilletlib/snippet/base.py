import json
import xml.etree.ElementTree as elementTree
from base64 import urlsafe_b64encode
from xml.etree.ElementTree import ParseError

import xmltodict
from jinja2 import BaseLoader
from jinja2 import Environment
from jsonpath_ng import parse
from passlib.hash import md5_crypt

from utils.exceptions import SkilletLoaderException


class Snippet:
    """
    BaseSnippet implements a basic template object snippet
    """
    required_metadata = {'name', 'file'}

    def __init__(self, template_str, metadata):

        self.metadata = self.sanitize_metadata(metadata)
        self.name = self.metadata['name']

        self.template_str = template_str
        self.rendered_template = ""
        self._env = self.__init_env()

    def template(self, context) -> str:
        return self.render(self.template_str, context)

    def render(self, template_str, context) -> str:

        if not context:
            context = {}

        t = self._env.from_string(template_str)
        return t.render(context)

    def should_execute(self, context: dict) -> bool:
        """
        Evaluate 'when' conditionals and return a bool if this snippet should be executed
        :param context: jinja context containing previous outputs and user supplied variables
        :return: boolean
        """

        print(f'Checking snippet: {self.name}')

        if 'when' not in self.metadata:
            # always execute when no when conditional is present
            print(f'No conditional present, proceeding with skillet: {self.name}')
            return True

        when = self.metadata['when']
        when_str = '{{%- if {0} -%}} True {{%- else -%}} False {{%- endif -%}}'.format(when)
        when_template = self._env.from_string(when_str)
        results = when_template.render(context)
        print(f'  Conditional Evaluation results: {results} ')
        if str(results).strip() == 'True':
            return True
        else:
            return False

    def capture_outputs(self, results: str) -> dict:
        outputs = dict()
        if 'outputs' not in self.metadata:
            return outputs

        # default output type is 'xml' if not defined
        output_type = self.metadata.get('output_type', 'xml')

        if output_type == 'xml':
            outputs = self._handle_xml_outputs(results)
        elif output_type == 'base64':
            outputs = self._handle_base64_outputs(results)
        elif output_type == 'json':
            outputs = self._handle_json_outputs(results)
        elif output_type == 'manual':
            outputs = self._handle_manual_outputs(results)

        return outputs

    def sanitize_metadata(self, metadata):
        """
        Ensure the configured metadata is valid for this snippet type
        :param metadata: dict
        :return: validated metadata dict
        """
        name = metadata.get('name', '')
        if not self.required_metadata.issubset(metadata):
            for attr_name in metadata:
                if attr_name not in self.required_metadata:
                    raise SkilletLoaderException(f'Invalid snippet metadata configuration: attribute: {attr_name} '
                                                 f'is required for snippet: {name}')

        return metadata

    # define functions for custom jinja filters
    @staticmethod
    def __md5_hash(txt) -> str:
        """
        Returns the MD5 Hashed secret for use as a password hash in the PAN-OS configuration
        :param txt: text to be hashed
        :return: password hash of the string with salt and configuration information. Suitable to place in the phash field
        in the configurations
        """

        return md5_crypt.hash(txt)

    def __init_env(self) -> Environment:
        e = Environment(loader=BaseLoader)
        e.filters["md5_hash"] = self.__md5_hash
        return e

    def _handle_xml_outputs(self, results: str) -> dict:
        """
        Parse the results string as an XML document
        Example .meta-cnc snippets section:
        snippets:

          - name: system_info
            path: /api/?type=op&cmd=<show><system><info></info></system></show>&key={{ api_key }}
            output_type: xml
            outputs:
              - name: hostname
                capture_pattern: result/system/hostname
              - name: uptime
                capture_pattern: result/system/uptime
              - name: sw_version
                capture_pattern: result/system/sw-version

        :param results: string as returned from some action, to be parsed as XML document
        :return: dict containing all outputs found from the capture pattern in each output
        """

        def unique_tag_list(elements: list) -> bool:
            tag_list = list()
            for el in elements:
                if el.tag not in tag_list:
                    tag_list.append(el.tag)

            if len(tag_list) == 1:
                # all tags in this list are the same
                return False
            else:
                # there are unique tags in this list
                return True

        outputs = dict()

        snippet_name = 'unknown'
        if 'name' in self.metadata:
            snippet_name = self.metadata['name']

        print(f'found results: {results}')
        try:
            xml_doc = elementTree.fromstring(results)
            if 'outputs' not in self.metadata:
                print('No outputs defined in this snippet')
                return outputs

            for output in self.metadata['outputs']:

                if 'name' not in output:
                    continue

                var_name = output['name']
                if 'capture_pattern' in output or 'capture_value' in output:
                    capture_pattern = output['capture_pattern']

                    # by default we will attempt to return the text of the found element
                    return_type = 'text'
                    entries = xml_doc.findall(capture_pattern)
                    print(f'found entries: {entries}')
                    if len(entries) == 0:
                        outputs[var_name] = ''
                    elif len(entries) == 1:
                        entry = entries.pop()
                        if len(entry) == 0:
                            # this tag has no children, so try to grab the text
                            if return_type == 'text':
                                outputs[var_name] = str(entry.text).strip()
                            else:
                                outputs[var_name] = entry.tag
                        else:
                            # we have 1 Element returned, so the user has a fairly specific xpath
                            # however, this element has children itself, so we can't return a text value
                            # just return the tag name of this element only
                            outputs[var_name] = entry.tag
                    else:
                        # we have a list of elements returned from the users xpath query
                        capture_list = list()
                        # are there unique tags in this list? or is this a list of the same tag names?
                        if unique_tag_list(entries):
                            return_type = 'tag'
                        for entry in entries:
                            if len(entry) == 0:
                                if return_type == 'text':
                                    capture_list.append(str(entry.text).strip())
                                else:
                                    capture_list.append(entry.tag)
                            else:
                                capture_list.append(entry.tag)

                        outputs[var_name] = capture_list

                elif 'capture_object' in output:
                    capture_pattern = output['capture_object']
                    entries = xml_doc.findall(capture_pattern)
                    if len(entries) == 0:
                        outputs[var_name] = None
                    elif len(entries) == 1:
                        outputs[var_name] = xmltodict.parse(elementTree.tostring(entries.pop()))
                    else:
                        capture_list = list()
                        for entry in entries:
                            capture_list.append(xmltodict.parse(elementTree.tostring(entry)))
                        outputs[var_name] = capture_list

        except ParseError:
            print('Could not parse XML document in output_utils')
            # just return blank outputs here
            raise SkilletLoaderException(f'Could not parse output as XML in {snippet_name}')

        return outputs

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
                print(f'No output defined in this snippet {snippet_name}')
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

    def _handle_json_outputs(self, results: str) -> dict:
        outputs = dict()

        snippet_name = 'unknown'
        if 'name' in self.metadata:
            snippet_name = self.metadata['name']

        try:
            if 'outputs' not in self.metadata:
                print('No outputs defined in this snippet')
                return outputs

            for output in self.metadata['outputs']:

                if 'name' not in output:
                    continue

                json_object = json.loads(results)
                var_name = output['name']
                capture_pattern = output['capture_pattern']
                jsonpath_expr = parse(capture_pattern)
                result = jsonpath_expr.find(json_object)
                if len(result) == 1:
                    outputs[var_name] = str(result[0].value)
                else:
                    # FR #81 - add ability to capture from a list
                    capture_list = list()
                    for r in result:
                        capture_list.append(r.value)

                    outputs[var_name] = capture_list

        except ValueError as ve:
            print('Caught error converting results to json')
            outputs['system'] = str(ve)
        except Exception as e:
            print('Unknown exception here!')
            print(e)
            outputs['system'] = str(e)

        return outputs

    def _handle_manual_outputs(self, results: str) -> dict:
        outputs = dict()

        snippet_name = 'unknown'
        if 'name' in self.metadata:
            snippet_name = self.metadata['name']

        try:
            if 'outputs' not in self.metadata:
                print('No outputs defined in this snippet')
                return outputs

            for output in self.metadata['outputs']:

                if 'name' not in output:
                    continue

                var_name = output['name']
                value = output['value']

                outputs[var_name] = value

        except KeyError as ke:
            print(f'Could not locate required attributes for manual output: {ke} in snippet: {snippet_name}')

        return outputs
