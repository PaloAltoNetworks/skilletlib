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


import xml.etree.ElementTree as elementTree
from xml.etree.ElementTree import ParseError

from skilletlib.exceptions import SkilletLoaderException
from .base import Snippet


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
            self._env.filters['has_config'] = self.__has_configuration
            self._env.filters['missing_config'] = self.__missing_configuration
        else:
            print('NO FILTERS TO APPEND TO')

    def sanitize_metadata(self, metadata: dict) -> dict:
        """
        Ensure all required keys are present in the snippet definition
        :param metadata: dict
        :return: dict
        """
        if self.cmd in ('set', 'edit', 'override'):
            if {'xpath', 'file', 'element'}.issubset(metadata):
                return metadata
            err = 'xpath and file attributes are required for set, edit, or override cmds'
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
            print(f'Could not render metadata for snippet: {self.name}: {te}')

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
            print(pe)
            print('Could not parse element for cherry picking!')
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
    def __has_configuration(obj, child_key) -> (str, None):

        print(obj)
        print(child_key)
        if obj is None:
            print('Object was None')
            return None

        if child_key in obj:
            print('key was found on object')
            return 'True'

        for child in obj:
            print(f'checkkng {child}')
            if child_key in obj[child]:
                print('key was found on child object')
                return 'True'

        print('No key was found here')
        return None

    @staticmethod
    def __missing_configuration(obj, child_key) -> (str, None):

        if obj is None:
            print('Object was None, missing config')
            return 'True'

        if child_key in obj:
            print('key was found on object')
            return None

        for child in obj:
            print(f'checkng {child}')
            if child_key in obj[child]:
                print('key was found on child object')
                return None

        print('No key was found here')
        return 'True'