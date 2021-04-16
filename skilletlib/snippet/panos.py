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
from typing import Tuple
from xml.etree.ElementTree import ParseError

from xmldiff import main as xmldiff_main

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.panoply import Panoply
from .template import TemplateSnippet

logger = logging.getLogger(__name__)


class PanosSnippet(TemplateSnippet):
    # fields that are required in the metadata definition
    required_metadata = {'name'}

    # attribute fields that should be rendered during render_metadata
    template_metadata = {'xpath', 'element', 'cmd_str', 'where', 'dst'}

    # default output_type for each snippet of this type
    output_type = 'xml'

    # keep the xml results between output capture
    xml_results = ''

    xml_force_list_keys = ['member', 'entry']

    def __init__(self, metadata: dict, panoply: Panoply):
        self.panoply = panoply

        # can this snippet make changes to the PAN-OS Device?
        self.destructive = False

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
        # self.add_filters()

    def execute(self, context: dict) -> Tuple[str, str]:
        if self.cmd == 'validate':
            logger.info(f'  Validating Snippet: {self.name}')
            test = self.metadata['test']
            logger.info(f'  Test is: {test}')
            output = self.execute_conditional(test, context)
            logger.info(f'  Validation results were: {output}')

        elif self.cmd == 'validate_xml':
            logger.info(f'  Validating XML Snippet: {self.name}')
            output = self.compare_element_at_xpath(context['config'], self.metadata['element'],
                                                   self.metadata['xpath'], context)

        elif self.cmd == 'parse':
            logger.info(f'  Parsing Variable: {self.metadata["variable"]}')
            output = context.get(self.metadata['variable'], '')

        elif self.cmd in ('op', 'set', 'edit', 'override', 'move', 'rename', 'clone', 'delete'):
            logger.info(f'  Executing Snippet: {self.name}')

            # These cmds may modify the configuration
            self.destructive = True

            output = self.panoply.execute_cmd(self.cmd, self.metadata, context)

        elif self.cmd in ('show', 'get'):
            logger.info(f'  Executing Snippet: {self.name}')

            output = self.panoply.execute_cmd(self.cmd, self.metadata, context)

        elif self.cmd == 'cli':
            logger.info(f'  Executing CLI cmd: {self.name}')
            cmd_str = self.metadata['cmd_str']
            output = self.panoply.execute_cli(cmd_str)

        elif self.cmd == 'noop':
            output = ''

        else:
            # no-op or unknown op!
            logger.warning(f'Skipping unknown cmd type: {self.cmd}')
            output = ''

        return output, 'success'

    def add_filters(self) -> None:
        if hasattr(self._env, 'filters'):
            self._env.filters['has_config'] = self._node_present
            self._env.filters['missing_config'] = self._node_absent

        else:
            logger.info('NO FILTERS TO APPEND TO')

    def sanitize_metadata(self, metadata: dict) -> dict:
        """
        Ensure all required keys are present in the snippet definition

        :param metadata: dict
        :return: dict
        """
        metadata = super().sanitize_metadata(metadata)

        name = metadata.get('name', 'n/a')

        if 'xpath' in metadata:
            metadata['xpath'] = str(metadata['xpath']).strip().replace('\n', '')

        err = f'Unknown cmd {self.cmd}'
        if self.cmd in ('set', 'edit', 'override'):
            if {'xpath', 'element'}.issubset(metadata):
                return metadata
            elif {'xpath', 'file'}.issubset(metadata):
                return metadata
            err = 'xpath and either file or element attributes are required for set, edit, or override cmds'
        elif self.cmd in ('show', 'get', 'delete'):
            if {'xpath'}.issubset(metadata):
                return metadata
            err = 'xpath attribute is required for show, get, or delete cmds'
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
        elif self.cmd == 'op' or self.cmd == 'cli':
            if 'cmd_str' in metadata:
                return metadata
            err = 'cmd_str attribute is required for op or cli cmd'
        elif self.cmd == 'validate':
            if {'test', 'label'}.issubset(metadata):
                # configure validation outputs manually if necessary
                # for validation we only need the output_type set to 'validation'
                metadata['output_type'] = 'validation'
                return metadata
            err = 'test and label are required attributes for validate cmd'
        elif self.cmd == 'parse':
            if {'variable', 'outputs'}.issubset(metadata):
                return metadata
            err = 'variable and outputs are required attributes for parse cmd'
        elif self.cmd == 'validate_xml':
            if {'xpath'}.issubset(metadata):
                if 'file' in metadata or 'element' in metadata:
                    metadata['output_type'] = 'validation'
                    return metadata
            err = 'xpath and file or element are required attributes for validate_xml cmd'
        elif self.cmd == 'noop':
            if 'output_type' not in metadata:
                metadata['output_type'] = 'manual'
            return metadata

        raise SkilletLoaderException(f'Invalid metadata configuration for snippet {name}: {err}')

    def render_metadata(self, context: dict) -> dict:
        """
        Renders each item in the metadata using the provided context.
        Currently renders the xpath and element for PANOS type skillets

        :param context: dict containing key value pairs to
        :return: dict containing the snippet definition metadata with the attribute values rendered accordingly
        """

        # execute super render_metadata
        # this will set the passed context onto self.context
        meta = super().render_metadata(context)

        try:
            if 'cherry_pick' in self.metadata:
                meta['element'] = self.cherry_pick_element(self.metadata['element'],
                                                           self.metadata['cherry_pick'])
                meta['xpath'] = self.cherry_pick_xpath(self.metadata['xpath'],
                                                       self.metadata['cherry_pick'])

        except TypeError as te:
            logger.info(f'Could not render metadata for snippet: {self.name}: {te}')

        return meta

    @staticmethod
    def compare_element_at_xpath(config: str, element: str, xpath: str, context: dict) -> bool:
        """
        Grab an xml fragment from the config given at xpath and compare it to this element

        :param config: XML document string from which to pull the XML element to compare

        :param element: element to check against
        :param xpath: xpath to grab an xml fragment from the config for comparison
        :param context: jinja context used to interpolate any variables that may be present in the template
        :return: bool true if they match
        """
        # render metadata will combine the xpath with the cherry_pick attribute to give us the full xpath
        # to the element in question. It will also load the element from our source element or source file into the
        # element attribute

        if element == '' or element is None:
            logger.warning('Element was blank for validate_xml test!')
            return False

        config_doc = elementTree.fromstring(config)
        relative_xpath = xpath.replace('/config/', './')
        config_element = config_doc.find(relative_xpath)

        config_element_str = elementTree.tostring(config_element).strip()
        diffs = xmldiff_main.diff_texts(config_element_str, element)
        if len(diffs) == 0:
            return True

        return False

    def cherry_pick_element(self, element: str, cherry_pick_path: str) -> str:
        """
        Cherry picking allows the skillet builder to pull out specific bits of a larger configuration
        and load only the smaller chunks. This is especially useful when combined with 'when' conditionals

        :param element: string containing the jinja templated xml fragment
        :param cherry_pick_path: string describing the relative xpath to use to cherry pick an xml node from the
            element given as a parameter
        :return: rendered and cherry_picked element
        """

        # first, we need to render the entire element so we can parse it with xpath
        rendered_element = self.render(element, self.context).strip()
        # convert this string into an xml doc we can search for the cherry_pick path
        try:
            element_doc = elementTree.fromstring(f'<xml>{rendered_element}</xml>')
            cherry_picked_element = element_doc.find(cherry_pick_path)
            if cherry_picked_element is None:
                raise SkilletLoaderException('Could not locate cherry_pick path in source xml! '
                                             'Check the cherry_pick xpath!')
            new_element = elementTree.tostring(cherry_picked_element).strip()
            return new_element

        except ParseError:
            raise SkilletLoaderException(f'Could not parse element for cherry picking for snippet: {self.name}')

    def cherry_pick_xpath(self, base_xpath: str, cherry_picked_xpath: str) -> str:
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
        :return: combined and rendered xpath
        """

        if base_xpath.endswith('/'):
            base_xpath = base_xpath[:-1]

        if cherry_picked_xpath.startswith('./'):
            cherry_picked_xpath = cherry_picked_xpath[2:]
        elif cherry_picked_xpath.startswith('/'):
            cherry_picked_xpath = cherry_picked_xpath[1:]

        # in some cases we can get the cherry_picked xpath and the base_xpath with an overlap of the ending
        # element for example:
        #     xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/update-schedule
        #     cherry_pick: update-schedule/statistics-service
        cherry_picked_xpath_parts = cherry_picked_xpath.split('/')
        base_xpath_parts = base_xpath.split('/')

        cherry_picked_xpath_first = cherry_picked_xpath_parts[0]
        base_xpath_last = base_xpath_parts[-1]

        # check if we have an overlap between first and last bits
        if cherry_picked_xpath_first == base_xpath_last:
            full_path_parts = base_xpath_parts + cherry_picked_xpath_parts[1:]
            xpath = "/".join(full_path_parts)
        # allow the user to specify the full xpath directly instead of manually breaking it up
        elif base_xpath.endswith(f'/{cherry_picked_xpath}'):
            xpath = base_xpath
        else:
            xpath = f'{base_xpath}/{cherry_picked_xpath}'

        rendered_xpath = self.render(xpath, self.context)
        # remove the last node from the resulting xpath
        if self.cmd == 'set':
            xpath_parts = rendered_xpath.split('/')
            return '/'.join(xpath_parts[:-1])
        else:
            logger.debug('Returning full xpath due to cmd != set')
            return rendered_xpath

    def get_default_output(self, results: str, status: str) -> dict:
        """
        Override the default snippet get_default_output to not include raw results

        :param results: raw output from snippet execution
        :param status: status of the snippet.execute method
        :return: dict of default outputs
        """

        r = {
            self.name: {
                'results': status,
                'changed': self.destructive
            }
        }
        return r
