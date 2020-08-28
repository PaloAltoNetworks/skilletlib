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

import html
import logging
from pathlib import Path
from typing import List
from typing import Optional

import skilletlib
from skilletlib.panoply import Panoply
from skilletlib.snippet.panos import PanosSnippet
from .base import Skillet
from ..exceptions import SkilletLoaderException
from ..exceptions import SkilletValidationException

logger = logging.getLogger(__name__)


class PanosSkillet(Skillet):
    panoply = None

    snippet_required_metadata = {'name'}

    initialized = False

    allow_snippet_cache = False

    def __init__(self, metadata: dict, panoply: Panoply = None):
        """
        Initialize a new PanosSkillet class.

        :param metadata: loaded dict from the Skillet YAML file

        :param panoply: optional panoply object. This can be passed in if the outer application scope has
        already been in contact with the device for things like checking auth, etc. If not passed in,
        you can invoke it in 'online' mode by passing in 'panos_username', 'panos_password' and 'panos_hostname' in the
        context. Otherwise, 'offline' mode requires a 'config' to be passed in via the context.
        """
        if panoply is not None:
            self.panoply = panoply
        super().__init__(metadata)

    def initialize_context(self, initial_context: dict) -> dict:
        """
        In this panos case, we want to stash the current configuration of the panos device in question in the
        context, check for online mode, offline mode, or an existing panoply object

        :param initial_context: dict to use to initialize the context
        :return: context with additional initialized items
        """

        # if the panoply object was not passed in via __init__, then check for online vs offline mode here
        # which set of fields we find in the context will determine online vs offline mode
        online_required_fields = {'panos_hostname', 'panos_username', 'panos_password'}

        # deprecated legacy fields
        legacy_required_fields = {'TARGET_IP', 'TARGET_USERNAME', 'TARGET_PASSWORD'}

        # simplified version
        provider_required_fields = {'ip_address', 'username', 'password'}

        # also allow api_key auth as well
        api_key_required_fields = {'ip_address', 'api_key'}

        # support for offline mode requires at least the 'config' variable to be present
        offline_required_fields = {'config'}

        context = super().initialize_context(initial_context)

        if self.panoply is None:
            if not online_required_fields.issubset(initial_context) \
                    and not offline_required_fields.issubset(initial_context) \
                    and not legacy_required_fields.issubset(initial_context) \
                    and not provider_required_fields.issubset(initial_context) \
                    and not api_key_required_fields.issubset(initial_context):
                raise SkilletValidationException('Required fields for panos skillet not found in context!')

            if online_required_fields.issubset(initial_context):
                hostname = initial_context.get('panos_hostname', None)
                username = initial_context.get('panos_username', None)
                password = initial_context.get('panos_password', None)
                port = initial_context.get('panos_port', '443')

                self.panoply = self.__init_panoply(hostname, username, password, port)

                context['config'] = self.panoply.get_configuration()

            elif legacy_required_fields.issubset(initial_context):
                hostname = initial_context.get('TARGET_IP', None)
                username = initial_context.get('TARGET_USERNAME', None)
                password = initial_context.get('TARGET_PASSWORD', None)
                port = initial_context.get('TARGET_PORT', '443')

                self.panoply = self.__init_panoply(hostname, username, password, port)

                context['config'] = self.panoply.get_configuration()

            elif provider_required_fields.issubset(initial_context):
                hostname = initial_context['ip_address']
                username = initial_context['username']
                password = initial_context['password']
                port = initial_context.get('port', 443)

                self.panoply = self.__init_panoply(hostname, username, password, port)

                context['config'] = self.panoply.get_configuration()

            elif api_key_required_fields.issubset(initial_context):
                hostname = initial_context['hostname']
                api_key = initial_context['api_key']

                # port may or may not be defined here
                port = initial_context.get('port', 443)

                self.panoply = self.__init_panoply(hostname=hostname, api_key=api_key, port=port)

                context['config'] = self.panoply.get_configuration()

            else:
                logger.info(f'offline mode detected for {__name__}')
                # init panoply in offline mode
                self.panoply = self.__init_panoply()

        else:
            # we were passed in a panoply object already, check if we are connected and grab the configuration if so
            if self.panoply.connected:
                context['config'] = self.panoply.get_configuration()

            else:
                raise SkilletLoaderException('Could not get configuration! Not connected to PAN-OS Device')

        self.initialized = True
        return context

    @staticmethod
    def __init_panoply(hostname: Optional[str] = None,
                       username: Optional[str] = None,
                       password: Optional[str] = None,
                       port: Optional[int] = 443,
                       api_key: Optional[str] = None):

        if hostname is None or username is None:
            # allow offline mode if these items are not passed in
            return skilletlib.panoply.EphemeralPanos()
        else:
            # otherwise, throw an exception when the device isn't ready
            return skilletlib.panoply.Panos(hostname=hostname,
                                            api_username=username,
                                            api_password=password,
                                            api_port=port,
                                            api_key=api_key)

    def get_snippets(self) -> List[PanosSnippet]:
        """
        Perform Panos Skillet specific tasks while loading each snippet

        :return: a List of PanosSnippets
        """
        if hasattr(self, 'snippets'):
            if self.initialized and self.allow_snippet_cache:
                return self.snippets

        snippet_list = list()

        for snippet_def in self.snippet_stack:

            if 'cmd' not in snippet_def or snippet_def['cmd'] == 'set':
                if 'element' not in snippet_def or snippet_def['element'] == '':
                    snippet_def['element'] = self.load_template(snippet_def['file'])

            snippet = PanosSnippet(snippet_def, self.panoply)
            snippet_list.append(snippet)

        if self.initialized:
            self.allow_snippet_cache = True

        return snippet_list

    @staticmethod
    def load_element(snippet_def: dict, snippet_path: Path) -> dict:
        """
        This method will load the snippet file found on disk into the 'element' attribute if the element
        is not already populated. This allows snippets to be 'all-in-one' i.e. there is no requirement for the snippets
        to be split into separate files. The meta-cnc.yaml file can contain all the snippets 'inline' in the 'element'
        attribute if desired.
        An example snippet def:

          - name: template
            xpath: /config/devices/entry[@name='localhost.localdomain']/template
            file: ../snippets/template.xml

        :param snippet_def: the loaded snippet definition from the .meta-cnc.yaml file. Each snippet object in the
        'snippets' stanza is a snippet_def and is passed in here
        :param snippet_path: the path on the filesystem where this skillet is located. This is used to resolve
        relative paths for each snippet. This allows snippet file re-use across skillets.
        :return: snippet_def with the element populated with the resolved and loaded snippet file contents
        """

        if 'element' not in snippet_def or snippet_def['element'] == '':

            if 'file' not in snippet_def:
                raise SkilletLoaderException(
                    'YAMLError: Could not parse metadata file for snippet %s' % snippet_def['name'])

            snippet_file = snippet_path.joinpath(snippet_def['file']).resolve()

            if snippet_file.exists():
                with snippet_file.open() as sf:
                    snippet_def['element'] = sf.read()

            else:
                # raise SkilletLoaderException('Could not load "file" attribute!')
                logger.error(f'Could not load the referenced file for {snippet_def["name"]}')

        else:
            # we have an element directly defined
            snippet_def['element'] = html.unescape(snippet_def['element'])

        return snippet_def

    def get_results(self) -> dict:
        """
        PanosSkillet will return a dict containing three keys:
        result, changed, and snippets. If any snippet failed, the result will be 'failure' otherwise 'success'
        If any successful snippet may have caused a change to the device, the 'changed' attribute will be 'True'

        A skillet that contains only the following snippet, will generate the output below:

        .. code-block:: yaml

              - name: check_hostname_again
                cmd: op
                cmd_str: <show><system><info/></system></show>
                outputs:
                  - name: url-db
                    capture_pattern: ./url-db
                  - name: pa-version
                    capture_pattern: ./plugin_versions/entry[@name="cloud_services"]/@version


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


        :return: dict containing default outputs plus the overall result and changed flag
        """

        results = super()._get_snippet_results()
        results['outputs'] = self.captured_outputs

        skillet_result = 'success'

        changed = False

        snippets = results.get('snippets', {})

        for k, v in snippets.items():
            if isinstance(v, dict) and 'results' in v:

                if v.get('results', 'failure') != 'success':
                    skillet_result = 'failure'
                else:
                    if v.get('changed', False):
                        changed = True

        results['result'] = skillet_result
        results['changed'] = changed

        return self._parse_output_template(results)
