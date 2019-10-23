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
import xml.etree.ElementTree as elementTree
from collections import OrderedDict
from typing import Any
from xml.etree.ElementTree import ParseError

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.exceptions import NodeNotFoundException
from .base import Snippet

logger = logging.getLogger(__name__)


class PanosSnippet(Snippet):
    required_metadata = {'name'}

    def __init__(self, metadata: dict):
        if 'cmd' not in metadata:
            self.cmd = 'set'
            metadata['cmd'] = 'set'
        elif metadata['cmd'] == 'op':
            self.cmd = metadata['cmd']
        else:
            self.cmd = metadata['cmd']

        # element should be the 'file' attribute read in as a str
        self.element = metadata.get('element', '')
        super().__init__(self.element, metadata)
        self.add_filters()

    def add_filters(self):
        if hasattr(self._env, 'filters'):
            self._env.filters['has_config'] = self.__node_present
            self._env.filters['missing_config'] = self.__node_absent
            self._env.filters['node_present'] = self.__node_present
            self._env.filters['node_absent'] = self.__node_absent
            self._env.filters['node_value'] = self.__node_value
            self._env.filters['node_attribute_present'] = self.__node_attribute_present

        else:
            logger.info('NO FILTERS TO APPEND TO')

    def sanitize_metadata(self, metadata: dict) -> dict:
        """
        Ensure all required keys are present in the snippet definition
        :param metadata: dict
        :return: dict
        """
        err = f'Unknown cmd {self.cmd}'
        if self.cmd in ('set', 'edit', 'override'):
            if {'xpath', 'element'}.issubset(metadata):
                return metadata
            elif {'xpath', 'file'}.issubset(metadata):
                return metadata
            err = 'xpath and either file or element attributes are required for set, edit, or override cmds'
        elif self.cmd in ('show', 'get'):
            if {'xpath'}.issubset(metadata):
                return metadata
            err = 'xpath attribute is required for show or get cmds'
        elif self.cmd == 'move':
            if 'where' in metadata:
                return metadata
            err = 'where attribute is required for move cmd'
        elif self.cmd in ('rename', 'clone'):
            if 'new_name' in metadata or 'newname' in metadata:
                return metadata
            err = 'new_name attribute is required for rename or move cmd'
        elif self.cmd == 'clone':
            if 'xpath_from' in metadata:
                return metadata
            err = 'xpath_from attribute is required for clone cmd'
        elif self.cmd == 'op':
            if 'cmd_str' in metadata:
                return metadata
            err = 'cmd_str attribute is required for op cmd'
        elif self.cmd == 'validate':
            if {'test', 'label', 'documentation_link'}.issubset(metadata):
                # configure validation outputs manually if necessary
                # for validation we only need the output_type set to 'validation'
                metadata['output_type'] = 'validation'
                return metadata
            err = 'test, label, and documentation_link are required attributes for validate cmd'
        elif self.cmd == 'parse':
            if {'variable', 'outputs'}.issubset(metadata):
                return metadata
            err = 'variable and outputs are required attributes for parse cmd'

        raise SkilletLoaderException(f'Invalid metadata configuration: {err}')

    def render_metadata(self, context: dict) -> dict:
        """
        Renders each item in the metadata using the provided context.
        Currently renders the xpath and element for PANOS type skillets
        :param context: dict containing key value pairs to
        :return: dict containing the snippet definition metadata with the attribute values rendered accordingly
        """
        meta = self.metadata
        try:
            if 'cherry_pick' in self.metadata:
                meta['element'] = self.cherry_pick_element(self.metadata['element'], context)
                meta['xpath'] = self.cherry_pick_xpath(self.metadata['xpath'], self.metadata['cherry_pick'], context)
            else:
                if 'xpath' in self.metadata:
                    meta['xpath'] = self.render(self.metadata['xpath'], context)

                if 'element' in self.metadata:
                    meta['element'] = self.render(self.metadata['element'], context)

        except TypeError as te:
            logger.info(f'Could not render metadata for snippet: {self.name}: {te}')

        return meta

    def cherry_pick_element(self, element, context) -> str:
        """
        Cherry picking allows the skillet builder to pull out specific bits of a larger configuration
        and load only the smaller chunks. This is especially useful when combined with 'when' conditionals
        :param element: string containing the jinja templated xml fragment
        :param context: jinja context used to interpolate any variables that may be present in the template
        :return: rendered and cherry_picked element
        """

        # first, we need to render the entire element so we can parse it with xpath
        rendered_element = self.render(element, context).strip()
        # convert this string into an xml doc we can search for the cherry_pick path
        try:
            element_doc = elementTree.fromstring(f'<xml>{rendered_element}</xml>')
            cherry_pick_path = self.metadata['cherry_pick']
            cherry_picked_element = element_doc.find(cherry_pick_path)
            if cherry_picked_element is None:
                raise SkilletLoaderException('Could not locate cherry_pick path in source xml! '
                                             'Check the cherry_pick xpath!')
            new_element = elementTree.tostring(cherry_picked_element).strip()
            return new_element

        except ParseError as pe:
            raise SkilletLoaderException(f'Could not parse element for cherry picking for snippet: {self.name}')

    def cherry_pick_xpath(self, base_xpath: str, cherry_picked_xpath: str, context: dict) -> str:
        """
        When cherry picking is active, we are only going to push a smaller portion of the xml fragment. As such,
        we need to combine the base xpath for the xml file and the xpath to the cherry_picked node.

        Ensure we can combine the base xpath and the cherry_picked xpath cleanly
        ideally, we end up with something like
        base_xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system
        cherry_picked: update-schedule/statistics-service/application-reports
        Because the cherry_pick xpath will return the named element, we need to strip the last node from the xpath
        in this case, in order to push the cherry_picked element back to the device, we need to
        set the xpath to
        /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule/statistics-service

        :param base_xpath: base xpath for the xml fragment
        :param cherry_picked_xpath: relative xpath for cherry picking a portion of the xml fragment
        :param context: jinja context
        :return: combined and rendered xpath
        """

        if base_xpath.endswith('/'):
            base_xpath = base_xpath[:-1]

        if cherry_picked_xpath.startswith('./'):
            cherry_picked_xpath = cherry_picked_xpath[2:]
        elif cherry_picked_xpath.startswith('/'):
            cherry_picked_xpath = cherry_picked_xpath[1:]

        xpath = f'{base_xpath}/{cherry_picked_xpath}'
        rendered_xpath = self.render(xpath, context)
        # remove the last node from the resulting xpath
        xpath_parts = rendered_xpath.split('/')
        return '/'.join(xpath_parts[:-1])

    @staticmethod
    def __has_child_node(obj, node_name) -> bool:
        if obj is None:
            return False

        if type(obj) is not dict and type(obj) is not OrderedDict:
            return False

        if node_name in obj:
            return True

        return False

    def __node_attribute_present(self, obj: dict, config_path: str, attribute_name: str, attribute_value: str) -> bool:

        if not attribute_name.startswith('@'):
            attribute_name = f'@{attribute_name}'

        parent_obj = self.__get_value_from_path(obj, config_path)

        if type(parent_obj) is OrderedDict or type(parent_obj) is dict:
            if attribute_name in parent_obj:
                if attribute_value == parent_obj[attribute_name]:
                    return True
        elif type(parent_obj) is list:
            for p in parent_obj:
                if attribute_name in p:
                    if attribute_value == p[attribute_name]:
                        return True

        return False

    def __node_present(self, obj: dict, config_path: str) -> bool:
        try:
            self.__get_value_from_path(obj, config_path)
            return True
        except NodeNotFoundException:
            return False

    def __node_value(self, obj: dict, config_path: str) -> Any:
        try:
            return self.__get_value_from_path(obj, config_path)
        except NodeNotFoundException:
            return None
        except SkilletLoaderException:
            return None

    def __get_value_from_path(self, obj: dict, config_path: str) -> Any:

        if type(obj) is not dict and type(obj) is not OrderedDict:
            logger.error("Supplied object is not an Object")
            logger.error('Ensure you are passing an object here and not a string as from capture_pattern')
            raise SkilletLoaderException('Incorrect object format for get_value_from_path')

        if '.' in config_path:
            path_elements = config_path.split('.')
            first_path_element = path_elements[0]
            p0 = self.__check_inner_object(obj, first_path_element)
            for p in path_elements:
                if self.__has_child_node(p0, p):
                    new_p0 = p0[p]
                    p0 = new_p0
                else:
                    raise NodeNotFoundException(f'{config_path} not found!')

            return p0

        p0 = self.__check_inner_object(obj, config_path)

        if self.__has_child_node(p0, config_path):
            return p0[config_path]
        else:
            raise NodeNotFoundException(f'{config_path} not found!')

    def __node_absent(self, obj, child_key) -> bool:

        out = self.__node_present(obj, child_key)
        if out:
            return False

        return True

    @staticmethod
    def __check_inner_object(obj: dict, child: str) -> dict:
        """
        Check inner object for named child dict key
        We often get a dict object which contains a single key. The value of this key is itself a dict
        and we need to know if the child key name exists on either the outer dict or the inner dict
        return the inner dict if the child key name is found there, or punt and return the outer dict
        otherwise
        :param obj: dict to check for child key name
        :param child: name of a key we want to find
        :return: inner dict if it contains the child key, outer dict otherwise
        """
        if child in obj:
            return obj

        if len(obj.keys()) == 1:
            inner_obj = obj[list(obj)[0]]
            if child in inner_obj:
                return inner_obj

        return obj

    def handle_output_type_validation(self, results: str):

        output = dict()
        output['results'] = results
        output['label'] = self.metadata.get('label', '')
        output['severity'] = self.metadata.get('severity', 'low')
        output['documentation_link'] = self.metadata.get('documentation_link', '')

        o = dict()
        o[self.name] = output
        return o
