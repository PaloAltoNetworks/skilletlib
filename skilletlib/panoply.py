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


import logging
import random
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import requests
import requests_toolbelt
import xmltodict
from pan import xapi
from pan.xapi import PanXapiError
from xmldiff import main as xmldiff_main

from .exceptions import LoginException
from .exceptions import SkilletLoaderException
from .skilletLoader import SkilletLoader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)


class Panoply:
    """
    Panoply is a wrapper around pan-python PanXAPI class to provide additional, commonly used functions
    """

    def __init__(self, hostname=None, api_username=None, api_password=None,
                 api_port=None, serial_number=None, debug=False):
        """
        Initialize a new panoply object
        :param hostname: hostname or ip address of target device`
        :param api_username: username
        :param api_password: password
        :param api_port: port to use for target device
        :param serial_number: Serial number of target device if proxy through panorama
        """

        if api_port is None:
            api_port = 443

        self.hostname = hostname
        self.user = api_username
        self.pw = api_password
        self.port = api_port
        self.serial_number = serial_number
        self.key = ''
        self.debug = False
        self.serial = serial_number
        self.connected = False
        self.facts = {}
        self.last_error = ''
        self.offline_mode = False

        if debug:
            logger.setLevel(logging.DEBUG)

        if hostname is None and api_username is None and api_password is None:
            self.offline_mode = True
            return

        # try to connect...
        self.offline_mode = False
        try:
            self.xapi = xapi.PanXapi(api_username=self.user, api_password=self.pw, hostname=self.hostname,
                                     port=self.port, serial=self.serial_number)
        except PanXapiError:
            # print('Invalid Connection information')
            raise LoginException('Invalid connection parameters')
        else:
            self.connect(allow_offline=True)

    def connect(self, allow_offline=False) -> None:
        """
        Attempt to connect to this device instance
        :param allow_offline: Do not raise an exception if this device is offline
        :return: None
        """
        try:
            self.key = self.xapi.keygen()
            self.facts = self.get_facts()
        except PanXapiError as pxe:
            err_msg = str(pxe)
            if '403' in err_msg:
                raise LoginException('Invalid credentials logging into device')
            else:
                if allow_offline:
                    # print('FYI - Device is not currently available')
                    self.connected = False
                else:
                    raise SkilletLoaderException('Could not connect to device!')
        else:
            self.connected = True

    def commit(self) -> str:
        """
        Perform a commit operation on this device instance
        :return: String from the API indicating success or failure
        """
        try:
            self.xapi.commit(cmd='<commit></commit>', sync=True, timeout=600)
            results = self.xapi.xml_result()
            if results is None:
                return self.xapi.status_detail

            doc = ElementTree.XML(results)
            embedded_result = doc.find('result')
            if embedded_result is not None:
                commit_result = embedded_result.text
                if commit_result == 'FAIL':
                    raise SkilletLoaderException(self.xapi.status_detail)

            return self.xapi.status_detail

        except PanXapiError as pxe:
            raise SkilletLoaderException('Could not commit configuration')

    def set_at_path(self, name: str, xpath: str, xml_str: str) -> None:
        """
        Insert XML into the configuration tree at the specified xpath
        :param name: name of the snippet - used in logging and debugging only
        :param xpath: full xpath where the xml element will be inserted
        :param xml_str: string representation of the XML element to insert
        :return: None
        """

        try:
            self.xapi.set(xpath=xpath, element=self.sanitize_element(xml_str))
            if self.xapi.status_code == '7':
                raise SkilletLoaderException(f'xpath {xpath} was NOT found for skillet: {name}')
        except PanXapiError as pxe:
            raise SkilletLoaderException(f'Could not push skillet {name} / snippet {xpath}! {pxe}')

    def execute_op(self, cmd_str: str) -> str:
        try:
            self.xapi.op(cmd=cmd_str)
            return self.xapi.xml_result()
        except PanXapiError as pxe:
            raise SkilletLoaderException(pxe)

    def execute_cmd(self, cmd: str, params: dict, context=None) -> str:
        """
        Execute the given cmd using the xapi.
        :param cmd: Valid options are: 'op', 'show', 'get', 'delete', 'set', 'edit', 'override', 'move', 'rename',
                                       'clone', 'validate'
        :param params: valid parameters for the given cmd type
        :param context: skillet context
        :return: raw results from the cmd output, raises SkilletLoaderException
        """
        if cmd not in ('op', 'set', 'edit', 'override', 'move', 'rename', 'clone', 'show', 'get', 'delete'):
            raise SkilletLoaderException('Invalid cmd type given to execute_cmd')

        # this code happily borrowed from ansible-pan module
        # https://raw.githubusercontent.com/PaloAltoNetworks/ansible-pan/develop/library/panos_type_cmd.py
        cmd = params['cmd']
        func = getattr(self.xapi, cmd)

        # shortcut for op cmd types
        if cmd == 'op':
            cmd_str = ''.join(params['cmd_str'].strip().split('\n'))
            return self.execute_op(cmd_str)

        # in all other cases, the xpath is a required attribute
        kwargs = {
            'xpath': ''.join(params['xpath'].strip().split('\n')),
            'extra_qs': params.get('extra_qs', dict())
        }

        try:
            if cmd in ('set', 'edit', 'override'):
                kwargs['element'] = params['element'].strip()

            if cmd in ('move',):
                kwargs['where'] = params['where']
                # dst is optional
                kwargs['dst'] = params.get('dst', None)

            if cmd in ('rename', 'clone'):
                if 'new_name' in params:
                    kwargs['newname'] = params['new_name']
                else:
                    kwargs['newname'] = params['newname']

            if cmd in ('clone',):
                kwargs['xpath_from'] = params['xpath_from']

        except KeyError as ke:
            raise SkilletLoaderException(f'Invalid parameters passed to execute_cmd: {ke}')

        try:
            func(**kwargs)

        except PanXapiError as e:
            raise SkilletLoaderException(f'Could not execute command: {cmd}: {e}')

        return self.xapi.xml_result()

    @staticmethod
    def sanitize_element(element: str) -> str:
        """
        Eliminate some undeeded characters out of the XML snippet if they appear.
        :param element: element str
        :return: sanitized element str
        """
        element = re.sub(r"\n\s+", "", element)
        element = re.sub(r"\n", "", element)

        return element

    def get_facts(self) -> dict:
        """
        Gather system info and keep on self.facts
        This gets called on every connect
        :return: dict containing all system facts
        """
        facts = {}

        # FIXME - add better error handling here
        self.xapi.op(cmd='<show><system><info></info></system></show>')

        if self.xapi.status != 'success':
            raise SkilletLoaderException('Could not get facts from device!')

        results_xml_str = self.xapi.xml_result()
        results = xmltodict.parse(results_xml_str)
        if 'system' in results:
            facts.update(results['system'])

        self.xapi.show(xpath="./devices/entry[@name='localhost.localdomain']/deviceconfig/system")
        results_xml_str = self.xapi.xml_result()
        results = xmltodict.parse(results_xml_str)
        if 'system' in results:
            facts['timezone'] = results['system'].get('timezone', 'US/Pacific')
        try:
            facts['dns-primary'] = results['system']['dns-setting']['servers']['primary']
            facts['dns-secondary'] = results['system']['dns-setting']['servers']['secondary']
        except KeyError:
            # DNS is not configured on the host, but we will need it later for some noob operations
            facts['dns-primary'] = '1.1.1.1'
            facts['dns-secondary'] = '1.0.0.1'

        return facts

    def load_baseline(self) -> bool:
        """
        Load baseline config that contains ONLY connecting username / password
        use device facts to determine which baseline template to load
        see template/panos/baseline_80.xml for example
        :param self:
        :return: bool true on success
        """

        file_contents = self.generate_baseline()
        self.import_file('skillet_baseline', file_contents, 'configuration')
        return self.load_config('skillet_baseline')

    def generate_baseline(self) -> str:
        """
        Load baseline config that contains ONLY connecting username / password
        use device facts to determine which baseline template to load
        see template/panos/baseline_80.xml for example
        :param self:
        :return: string contents of baseline config
        """
        if not self.connected:
            self.connect()

        if 'sw-version' not in self.facts:
            raise SkilletLoaderException('Could not determine sw-version to load baseline configuration!')

        version = self.facts['sw-version']
        context = dict()
        context['ADMINISTRATOR_USERNAME'] = self.user
        context['ADMINISTRATOR_PASSWORD'] = self.pw

        if self.facts['model'] == 'Panorama':
            skillet_type_dir = 'panorama'
            context['PANORAMA_NAME'] = self.facts['hostname']
            # FIXME - is there a way to determine if dhcp is active via an op cmd?
            context['PANORAMA_TYPE'] = 'static'
            context['PANORAMA_IP'] = self.facts['ip-address']
            context['PANORAMA_MASK'] = self.facts['netmask']
            context['PANORAMA_DG'] = self.facts['default-gateway']
            context['DNS_1'] = self.facts['dns-primary']
            context['DNS_2'] = self.facts['dns-secondary']

        else:
            skillet_type_dir = 'panos'
            context['FW_NAME'] = self.facts['hostname']
            if self.facts['is-dhcp'] == 'no':
                context['MGMT_TYPE'] = 'static'
                context['MGMT_IP'] = self.facts['ip-address']
                context['MGMT_MASK'] = self.facts['netmask']
                context['MGMT_DG'] = self.facts['default-gateway']
                context['DNS_1'] = self.facts['dns-primary']
                context['DNS_2'] = self.facts['dns-secondary']

        if '8.0' in version:
            # load the 8.0 baseline with
            skillet_dir = 'baseline_80'
        elif '8.1' in version:
            # load the 8.1 baseline with
            skillet_dir = 'baseline_81'
        elif '9.0' in version:
            # load the 9.0 baseline with
            skillet_dir = 'baseline_90'
        else:
            raise SkilletLoaderException('Could not determine sw-version for baseline load')

        template_path = Path(__file__).parent.joinpath('assets', skillet_type_dir, skillet_dir)
        sl = SkilletLoader()
        baseline_skillet = sl.load_skillet_from_path(str(template_path.resolve()))
        snippets = baseline_skillet.get_snippets()
        snippet = snippets[0]
        output, status = snippet.execute(context)
        if status == 'success':
            return str(output)
        else:
            raise SkilletLoaderException('Could not generate baseline config!')

    def import_file(self, filename: str, file_contents: (str, bytes), category: str) -> bool:
        """
        Import the given file into this device
        :param filename:
        :param file_contents:
        :param category: 'configuration'
        :return: bool True on success
        """
        params = {
            'type': 'import',
            'category': category,
            'key': self.key
        }

        mef = requests_toolbelt.MultipartEncoder(
            fields={
                'file': (filename, file_contents, 'application/octet-stream')
            }
        )

        r = requests.post(
            f'https://{self.hostname}:{self.port}/api/',
            verify=False,
            params=params,
            headers={'Content-Type': mef.content_type},
            data=mef
        )

        # if something goes wrong just raise an exception
        r.raise_for_status()

        resp = ElementTree.fromstring(r.content)

        if resp.attrib['status'] == 'error':
            raise SkilletLoaderException(r.content)

        return True

    def load_config(self, filename: str) -> bool:
        """
        Loads the named configuration file into this device
        :param filename: name of the configuration file on the device to load. Note this filename must already exist
        on the target device
        :return: bool True on success
        """

        cmd = f'<load><config><from>{filename}</from></config></load>'
        self.xapi.op(cmd=cmd)
        if self.xapi.status == 'success':
            return True
        else:
            return False

    def wait_for_device_ready(self, interval=30, timeout=600) -> bool:
        """
        Loop and wait until device is ready or times out
        :param interval: how often to check in seconds
        :param timeout: how long to wait until we declare a timeout condition
        :return: boolean true on ready, false on timeout
        """
        mark = time.time()
        timeout_mark = mark + timeout

        while True:
            try:
                self.xapi.op(cmd='<show><chassis-ready></chassis-ready></show>')
                resp = self.xapi.xml_result()
                if self.xapi.status == 'success':
                    if resp.strip() == 'yes':
                        return True
            except PanXapiError:
                logger.info(f'{self.hostname} is not yet ready...')

            if time.time() > timeout_mark:
                return False

            logger.info(f'Waiting for {self.hostname} to become ready...')
            time.sleep(interval)

    def update_dynamic_content(self, content_type: str) -> bool:
        """
        Check for newer dynamic content and install if found
        :param content_type: type of content to check. can be either: 'content', 'anti-virus', 'wildfire'
        :return: bool True on success
        """
        try:
            version_to_install = self.check_content_updates(content_type)
            if version_to_install is None:
                logger.info('Latest content version is already installed')
                return True

            logger.info('Downloading latest and greatest')
            cmd = f'<request>' \
                  f'<{content_type}><upgrade><download><latest/></download></upgrade></{content_type}>' \
                  f'</request>'

            self.xapi.op(cmd=cmd)
            results_element = self.xapi.element_result
            job_element = results_element.find('.//job')
            if job_element is not None:
                job_id = job_element.text
                if not self.wait_for_job(job_id):
                    raise SkilletLoaderException('Could not update dynamic content')

            logger.info(f'Installing latest and greatest ')
            install_cmd = f'<request><content><upgrade><install>' \
                          f'<version>latest</version><commit>no</commit></install></upgrade></content></request>'

            self.xapi.op(cmd=install_cmd)
            results_element = self.xapi.element_result
            job_element = results_element.find('.//job')
            if job_element is not None:
                job_id = job_element.text
                if not self.wait_for_job(job_id):
                    raise SkilletLoaderException('Could not install dynamic content')
            else:
                logger.info(f'No job returned to track')

            return True

        except PanXapiError:
            logger.error('Could not check for updated dynamic content')
            return False

    def check_content_updates(self, content_type: str) -> (str, None):
        """
        Iterate through all available content of the specified type, locate and return the version with the highest
        version number. If that version is already installed, return None as no further action is necessary
        :param content_type: type of content to check
        :return: version-number to download and install or None if already at the latest
        """
        latest_version = ''
        latest_version_first = 0
        latest_version_second = 0
        latest_version_current = 'no'
        try:
            logger.info('Checking for latest content...')
            self.xapi.op(cmd=f'<request><{content_type}><upgrade><check/></upgrade></{content_type}></request>')
            er = self.xapi.element_root
            for entry in er.findall('.//entry'):
                version = entry.find('./version').text
                current = entry.find('./current').text
                # version will have the format 1234-1234
                version_parts = version.split('-')
                version_first = int(version_parts[0])
                version_second = int(version_parts[1])
                if version_first > latest_version_first and version_second > latest_version_second:
                    latest_version = version
                    latest_version_first = version_first
                    latest_version_second = version_second
                    latest_version_current = current

            if latest_version_current == 'yes':
                return None
            else:
                return latest_version

        except PanXapiError:
            return None

    def wait_for_job(self, job_id: str, interval=10, timeout=600) -> bool:
        """
        Loops until a given job id is completed. Will timeout after the timeout period if the device is
        offline or otherwise unavailable.
        :param job_id: id the job to check and wait for
        :param interval: how long to wait between checks
        :param timeout: how long to wait with no response before we give up
        :return: bool true on content updated, false otherwise
        """
        mark = time.time()
        timeout_mark = mark + timeout
        logger.debug(f'Waiting for job id: {job_id} to finish...')
        while True:
            try:
                self.xapi.op(cmd=f'<show><jobs><id>{job_id}</id></jobs></show>')
            except PanXapiError:
                logger.error(f'Could not locate job with id: {job_id}')
                return False

            if self.xapi.status == 'success':
                job_element = self.xapi.element_result
                job_status_element = job_element.find('.//status')
                if job_status_element is not None:
                    job_status = job_status_element.text
                    if job_status == 'FIN':
                        logger.debug('Job is now complete')
                        return True
                    elif job_status == 'ACT':
                        job_progress_element = job_element.find('.//progress')
                        if job_progress_element is not None:
                            job_progress = job_progress_element.text
                            logger.debug(f'Progress is currently: {job_progress}')
                else:
                    logger.error('No job status element to be found!')
                    return False
            else:
                logger.debug(f'{self.xapi.xml_result()}')
                if time.time() > timeout_mark:
                    return False
                logger.info('Waiting a bit longer')

            time.sleep(interval)

    def generate_skillet(self, from_candidate=False) -> list:
        """
        Generates a skillet from the changes detected on this device.
        This will attempt to create the xml and xpaths for everything that is found to have changed
        :param from_candidate: If your changes on in the candidate config, this will detect changes between the running
        config and the candidate config. If False, this will detect changes between the running config and a generic
        baseline configuration
        :return: list of xpaths
        """
        if from_candidate:
            self.xapi.op(cmd='show config candidate', cmd_xml=True)
            latest_config = self.xapi.xml_result()
            self.xapi.op(cmd='show config running', cmd_xml=True)
            previous_config = self.xapi.xml_result()
        else:
            previous_config = self.generate_baseline()
            self.xapi.op(cmd='show config running', cmd_xml=True)
            latest_config = self.xapi.xml_result()

        return self.generate_skillet_from_configs(previous_config, latest_config)

    def generate_skillet_from_configs(self, previous_config: str, latest_config: str) -> list:
        # convert the config string to an xml doc
        latest_doc = ElementTree.fromstring(latest_config)

        # let's grab the previous as well
        previous_doc = ElementTree.fromstring(previous_config)

        current_xpath = '.'
        not_found_xpaths = list()
        for c in latest_doc:
            o_xpath = current_xpath + '/' + c.tag
            these_not_found_xpaths = self.__check_element(c, o_xpath, previous_doc, [])
            not_found_xpaths.extend(these_not_found_xpaths)

        snippets = list()
        for xpath in not_found_xpaths:
            # keep a string of changes
            xml_string = ''

            changed_element = latest_doc.find(xpath)
            # we can't just dump out the changed element because it'll contain the 'tag' as the outermost tag
            # so, find all the children of this 'tag' and append them to the xml_string
            for child_element in changed_element.findall('./'):
                xml_string += ElementTree.tostring(child_element).decode(encoding='UTF-8')

            if xml_string == '':
                if changed_element.text:
                    xml_string = changed_element.text

            snippet = dict()
            random_name = str(int(random.random() * 1000000))
            full_tag = xpath.split('/')[-1]
            tag = re.sub(r'\[.*\]', '', full_tag)
            snippet['name'] = f'{tag}-{random_name}'
            snippet['xpath'] = xpath
            snippet['element'] = xml_string.strip()
            snippets.append(snippet)

        return self.__order_snippets(snippets)

    def __check_element(self, el: Element, xpath: str, pc: Element, not_founds: list) -> list:

        found_element = pc.find(xpath)
        if found_element is not None:
            children = el.findall('./')
            if len(children) == 0:
                # print(f'Skipping leaf node {xpath} {el.tag}')
                if found_element.text != el.text:
                    not_founds.append(xpath)
                return not_founds

            if self.__check_children_are_list(children):
                # only use
                diffs = xmldiff_main.diff_texts(ElementTree.tostring(found_element), ElementTree.tostring(el))
                if len(diffs) == 0:
                    return not_founds

            for e in el:
                if e.attrib:
                    attribs = list()
                    for k, v in e.attrib.items():
                        if k != 'uuid':
                            attribs.append(f'@{k}="{v}"')

                    attrib_str = " ".join(attribs)
                    path_entry = f'{e.tag}[{attrib_str}]'
                else:
                    path_entry = e.tag

                n_xpath = xpath + '/' + path_entry
                new_not_founds = self.__check_element(e, n_xpath, pc, list())
                not_founds.extend(new_not_founds)
            return not_founds

        not_founds.append(xpath)
        return not_founds

    @staticmethod
    def __order_snippets(snippets: list):
        # Attempt to order the snippets in a cohesive ordering. Will never be 100% perfect,
        # but at least make the attempt
        # FIXME - add some sort of logic here
        return snippets

    @staticmethod
    def __check_children_are_list(c: list) -> bool:
        # check if children are a list of items by identical tag names
        if len(c) <= 1:
            # can't be a list of identical items if there are only 0 or 1 items
            return False

        found_tag_name = ''
        for child in c:
            if found_tag_name == '':
                found_tag_name = child.tag
                continue
            if found_tag_name != child.tag:
                return False

        return True

    def generate_skillet_from_configs_old(self, previous_config: str, latest_config: str) -> list:
        # use the excellent xmldiff library to get a list of changed elements
        diffs = xmldiff_main.diff_texts(previous_config, latest_config,
                                        {'F': 0.1, 'ratio_mode': 'accurate', 'fast_match': True})
        # THIS IS BROKEN
        # diffs = xmldiff_main.diff_texts(previous_config, latest_config)
        # returned diffs have the following basic structure
        # InsertNode(target='/config/shared[1]', tag='log-settings', position=2)
        # InsertNode(target='/config/shared/log-settings[1]', tag='http', position=0)
        # keep a list of found xpaths
        fx = list()

        # also track nodes with updated text
        updated_text_snippets = list()

        snippets = list()
        # keep a dict of targets to xpaths
        xpaths = dict()

        # convert the config string to an xml doc
        latest_doc = ElementTree.fromstring(latest_config)

        # let's grab the previous as well
        previous_doc = ElementTree.fromstring(previous_config)
        for d in diffs:
            logger.debug(d)
            # step 1 - find all inserted nodes (future enhancement can consider other types of detected changes as well
            if 'InsertNode' in str(d):
                if d.target not in xpaths:
                    d_xpath = self.__normalize_xpath(latest_doc, d.target)
                    xpaths[d.target] = d_xpath
                else:
                    d_xpath = xpaths[d.target]

                # we have an inserted node, step2 determine if it's a top level element or a child of another element
                # xmldiff will return even inserted nodes in elements that have already been inserted
                # for purposes of building a skillet, we only need the top most unique element
                # d_target = re.sub(r'\[\d+\]$', '', d.target)
                # d_full = f'{d_target}/{d.tag}'
                # has this element been found to be a child of another element?
                found = False
                # iter all diffs again to verify if this element is actually a child element or a top level element
                for e in diffs:
                    # again only consider inserted nodes for now
                    if 'InsertNode' in str(e):
                        if e.target not in xpaths:
                            e_xpath = self.__normalize_xpath(latest_doc, e.target)
                            xpaths[e.target] = e_xpath
                        else:
                            e_xpath = xpaths[e.target]

                        e_target = re.sub(r'\[\d+\]$', '', e.target)
                        e_full = f'{e_target}/{e.tag}'
                        # begin checking for child / parent or equality relationship
                        if e.target == d.target and d.tag == e.tag and d.position == e.position:
                            # this is the same diff
                            pass
                        elif e.target == d.target and d.tag == e.tag and d.position != e.position:
                            # new tag under an existing one possible
                            pass
                        elif e.target == d.target and d.tag == e.tag:
                            # same target and same tag indicate another entry under the same top-level tag
                            # do not keep this as a top-level element
                            found = True
                            logger.debug('same target, same tag')
                            logger.debug(e)
                            logger.debug('---')
                            break
                        elif e.target != d.target and e_full in d.target:
                            # the targets are not the same and this diffs target is found to be 'in' the outer diff
                            # target, therefore this cannot be a top level element
                            found = True
                            logger.debug('e_full in d.target')
                            logger.debug(e_full)
                            logger.debug('---')
                            break

                if not found:
                    # we have not found this to be a child or peer of another element
                    # therefore this must be a top-level element, let's keep it for future work
                    logger.debug(f'Appending {d} to list of changes')
                    fx.append(d)
            # elif 'InsertAttr' in str(d):
            #     if d.node not in xpaths:
            #         node_target = re.sub(r'\[\d+\]$', '', d.node)
            #         xpaths[d.node] = f'{node_target}[@{d.name}="{d.value}"]'
            #         logger.debug(f'added {d.node} with value {xpaths[d.node]} ')
            elif 'UpdateTextIn' in str(d):
                snippet = dict()
                normalized_xpath = self.__normalize_xpath(latest_doc, d.node)
                xpath_parts = normalized_xpath.split('/')
                xpath = "/".join(xpath_parts[:-1])
                tag = xpath_parts[-1]
                relative_xpath = re.sub(r'^\./', '/config/', xpath)
                random_name = str(int(random.random() * 1000000))
                snippet['name'] = f'{tag}-{random_name}'
                snippet['xpath'] = relative_xpath
                snippet['element'] = f'<{tag}>{d.text}</{tag}>'
                updated_text_snippets.append(snippet)

        # we have found changes in the latest_config
        if fx:
            # now iterate only the top-level diffs (insertednodes only at this time)
            for f in fx:
                # target contains the full xpath, since we have the 'config' element already in 'latest_config'
                # we need to adjust the xpath to be relative. Also attach the 'tag' to the end of the xpath and
                # account for position if supplied
                # f_target_str = xpaths[f.target]

                f_tag = f.tag
                if hasattr(f, 'position'):
                    f_tag = f'{f.tag}[{f.position}]'

                if f.target in xpaths:
                    f_target_str = xpaths[f.target]
                else:
                    f_target_str = self.__normalize_xpath(latest_doc, f.target)
                    xpaths[f.target] = f_target_str

                f_target_str_relative = re.sub(r'^\./', '/config/', f_target_str)
                changed_short_xpath = f'{f_target_str}/{f_tag}'
                # get this element from the latest config xml document
                changed_element_dirty = latest_doc.find(changed_short_xpath)
                changed_element = self.__clean_uuid(changed_element_dirty)
                # keep a string of changes
                xml_string = ''
                # we can't just dump out the changed element because it'll contain the 'tag' as the outermost tag
                # so, find all the children of this 'tag' and append them to the xml_string
                for child_element in changed_element.findall('./'):
                    xml_string += ElementTree.tostring(child_element).decode(encoding='UTF-8')

                if xml_string == '':
                    # if changed_element.text:
                    #     xml_string = changed_element.text
                    # else:
                    # this is a text only node, we should catch this later with a updateTextIn diff
                    logger.debug('****************')
                    logger.debug(f'skipping {f_target_str_relative}/{f_tag} as this looks like a text only node')
                    logger.debug('****************')
                    continue

                snippet = dict()
                random_name = str(int(random.random() * 1000000))
                snippet['name'] = f'{f.tag}-{random_name}'
                snippet['xpath'] = f'{f_target_str_relative}/{f_tag}'
                snippet['element'] = xml_string.strip()
                snippet['from_insert'] = True
                # now print out to the end user
                snippets.append(snippet)

        text_update_snippets_to_include = list()
        if updated_text_snippets:
            for ut_snippet in updated_text_snippets:
                found = False
                for snippet in snippets:
                    if snippet['xpath'] in ut_snippet['xpath']:
                        # logger.debug('This text snippet is a child of one already included')
                        found = True
                        break
                if not found:
                    text_update_snippets_to_include.append(ut_snippet)

        snippets.extend(text_update_snippets_to_include)
        return snippets

    def get_configuration(self) -> str:
        """
        Get the running configuration from the device if connected
        :return: configuration xml as a string or a blank string if not connected
        """
        try:
            if self.connected:
                self.xapi.op(cmd='show config running', cmd_xml=True)
                return self.xapi.xml_result()
            else:
                return ''
        except PanXapiError:
            logger.error(f'Could not get configuration from device')
            raise SkilletLoaderException('Could not get configuration from the device')

    @staticmethod
    def __clean_uuid(changed_element: Element) -> Element:
        """
        Some rules and other elements contain the 'uuid' attribute. These should be removed before
        they can be applied to another device / fw. This function descends to all child nodes and removes the uuid
        attribute if found
        :param changed_element: ElementTree.Element in which to search
        :return: ElementTree.Element with all uuid attributes removed
        """
        if changed_element is None:
            return changed_element

        child_nodes = changed_element.findall('.//*[@uuid]')
        if child_nodes is None:
            return changed_element

        for child in child_nodes:
            child.attrib.pop('uuid')

        return changed_element

    @staticmethod
    def __normalize_xpath(document: Element, xpath: str) -> str:
        """
        create an xpath with all attributes included. The xpaths generated from the diffing library
        are guaranteed to be unique and valid against this configuration file, however, they are not
        guaranteed to be portable to another configuration. To avoid this, iterate over the xpath, search
        the document for each part of the xpath and grab any attributes and add them to the resulting
        xpath before returning it.
        :param document: ElementTree.Element that represents the configuration from which the diff were produced
        :param xpath: the xpath of the node in question, which may be indexed and have no attributes included
        :return: the fully normalized xpath which includes all the attributes included and the indexes removed
        """
        # Example xpath: /config/mgt-config/users/entry/phash[1]
        # the xpath will be absolute, change it here to be relative so we can search the document
        relative_xpath = re.sub('^/config/', './', xpath)
        # split the xpath into it's parts
        parts = relative_xpath.split('/')
        # xpath is now: ['.', 'mgt-config', 'users', 'entry', 'phash[1]']
        # begin constructing the new partial xpath. We will iteratively add additional parts, checking each one for
        # attributes that should be added
        path = ''
        for p in parts:
            if p == '.':
                # skip checking the root node, don't care about attributes here in the xpath
                path = p
                continue
            # add the next part to the previous, adding the '/'
            # example xpath: ./mgt-config/users/entry
            path = path + '/' + p
            logger.debug(f'Checking path: {path}')
            el = document.find(path)
            if el is None:
                # this should never happen as the xpath was found in the document we are checking
                # this would indicate a programmatic error somewhere
                raise SkilletLoaderException('Could not normalize xpath in configuration document!')

            if el.attrib != {} and type(el.attrib) is dict:
                logger.debug('Found attributes here')
                # begin assembling the attributes into a string
                # resulting xpath will be something like entry[@name='rule1']
                attrib_str = ''
                for k, v in el.attrib.items():
                    attrib_str += f'[@{k}="{v}"]'

                if re.match(r'.*\[\d+\]$', path):
                    logger.debug('replacing indexed element with attribute named')
                    path = re.sub(r'\[\d+\]$', f'{attrib_str}', path)
                else:
                    path = path + attrib_str

                # example xpath is now: ./mgt-config/users/entry[@name="admin"]/phash[1]
            else:
                path = re.sub(r'\[\d+\]', '', path)
                # now removing the index from items that do not have attributes
                # example xpath now: ./mgt-config/users/entry[@name="admin"]/phash

        logger.debug(f'returning {path}')
        return path
