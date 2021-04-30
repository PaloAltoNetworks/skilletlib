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

import datetime
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional
from typing import Tuple
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

import requests
import requests_toolbelt
import xmltodict
from lxml import etree
from lxml.etree import Element
from pan import xapi
from pan.config import PanConfig
from pan.xapi import PanXapiError
from xmldiff import main as xmldiff_main

from .exceptions import LoginException
from .exceptions import PanoplyException
from .exceptions import SkilletLoaderException
from .exceptions import TargetConnectionException
from .exceptions import TargetGenericException
from .exceptions import TargetLoginException
from .skilletLoader import SkilletLoader

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not len(logger.handlers):
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


class Panoply:
    """
    Panoply is a wrapper around pan-python PanXAPI class to provide additional, commonly used functions
    """

    def __init__(self, hostname: Optional[str] = None, api_username: Optional[str] = None,
                 api_password: Optional[str] = None, api_port: Optional[int] = 443,
                 serial_number: Optional[str] = None, debug: Optional[bool] = False, api_key: Optional[str] = None):
        """
        Initialize a new panoply object. Passing in the authentication information will cause this class to attempt
        to connect to the device and set offline_mode to False. Otherwise, offline mode will be set to True

        :param hostname: hostname or ip address of target device`
        :param api_username: username
        :param api_password: password
        :param api_port: port to use for target device
        :param serial_number: Serial number of target device if proxy through panorama
        :param debug: Optional flag to log additional debug messages
        :param api_key: Optional api key to use instead of username / password auth
        """

        if api_port is None:
            api_port = 443

        self.hostname = hostname
        self.user = api_username
        self.pw = api_password
        self.port = api_port
        self.serial_number = serial_number
        self.key = api_key
        self.debug = debug

        self.serial = serial_number
        self.connected = False
        self.connected_message = 'no connection attempted'
        self.facts = {}
        self.last_error = ''
        self.offline_mode = False
        self.xapi = None

        if debug:
            logger.setLevel(logging.DEBUG)

        elif os.environ.get('SKILLET_DEBUG', False):
            logger.setLevel(logging.DEBUG)

        if hostname is None and api_username is None and api_password is None:
            self.offline_mode = True
            return

        # try to connect...
        self.offline_mode = False

        try:
            self.xapi = xapi.PanXapi(api_username=self.user, api_password=self.pw, hostname=self.hostname,
                                     port=self.port, serial=self.serial_number, api_key=self.key)

        except xapi.PanXapiError as pxe:
            err_msg = str(pxe)

            if '403' in err_msg:
                raise TargetLoginException('Invalid credentials logging into device')

            elif 'Errno 111' in err_msg:
                raise TargetConnectionException('Error contacting the device at the given IP / hostname')

            elif 'Errno 60' in err_msg:
                raise TargetConnectionException('Error contacting the device at the given IP / hostname')

            else:
                raise TargetGenericException(pxe)

        else:
            self.connect(allow_offline=True)

    def connect(self, allow_offline: Optional[bool] = False) -> None:
        """
        Attempt to connect to this device instance

        :param allow_offline: Do not raise an exception if this device is offline unless there is an authentication
        error
        :return: None
        """
        try:

            if self.xapi is None:
                self.xapi = xapi.PanXapi(api_username=self.user, api_password=self.pw, hostname=self.hostname,
                                         port=self.port, serial=self.serial_number)

            self.key = self.xapi.keygen()
            self.facts = self.get_facts()

        except PanXapiError as pxe:
            err_msg = str(pxe)

            if '403' in err_msg:
                raise LoginException('Invalid credentials logging into device')

            else:

                if allow_offline:
                    logger.debug('FYI - Device is not currently available')
                    self.connected = False
                    self.connected_message = 'device is not currently available'
                    return None

                else:
                    raise PanoplyException('Could not connect to device!')

        else:
            self.connected = True

    def commit(self, force_sync=True) -> str:
        """
        Perform a commit operation on this device instance -

        :raises PanoplyException: if commit failed
        :param force_sync: Flag to enable sync commit or async
        :return: String from the API indicating success or failure
        """

        try:
            self.xapi.commit(cmd='<commit></commit>', sync=force_sync, timeout=600)
            results = self.xapi.xml_result()

            if not self.__check_commit_return(results, force_sync):
                raise PanoplyException(self.xapi.status_detail)

            return self.xapi.status_detail

        except PanXapiError as pxe:
            logger.error(pxe)
            raise PanoplyException('Could not commit configuration')

    def commit_gpcs(self, force_sync=True) -> str:
        """
        Perform a commit operation on this device instance specifically for gpcs remote networks
        Note - you must do a full commit to panorama before you invoke this commit!

        :raises PanoplyException: if commit failed
        :param force_sync: Flag to enable sync commit or async
        :return: String from the API indicating success or failure
        """
        try:

            running_config = self.get_configuration(config_source='running')
            config_doc = etree.fromstring(running_config)

            sc = config_doc.xpath("/config/devices/entry[@name='localhost.localdomain']/"
                                  "device-group/entry[@name='Service_Conn_Device_Group']")
            rn = config_doc.xpath("/config/devices/entry[@name='localhost.localdomain']/"
                                  "device-group/entry[@name='Remote_Network_Device_Group']")
            mu = config_doc.xpath("/config/devices/entry[@name='localhost.localdomain']/"
                                  "device-group/entry[@name='Mobile_User_Device_Groupp']")

            if sc:
                self.xapi.commit(action='all',
                                 cmd='<commit-all><shared-policy><device-group>'
                                     '<entry name="Service_Conn_Device_Group"/>'
                                     '</device-group></shared-policy></commit-all>')

                results = self.xapi.xml_result()

                if not self.__check_commit_return(results, force_sync):
                    raise PanoplyException(self.xapi.status_detail)

            if rn:
                self.xapi.commit(action='all',
                                 cmd='<commit-all><shared-policy><device-group>'
                                     '<entry name="Remote_Network_Device_Group"/>'
                                     '</device-group></shared-policy></commit-all>')

                results = self.xapi.xml_result()

                if not self.__check_commit_return(results, force_sync):
                    raise PanoplyException(self.xapi.status_detail)

            if mu:
                self.xapi.commit(action='all',
                                 cmd='<commit-all><shared-policy><device-group>'
                                     '<entry name="Mobile_User_Device_Group"/>'
                                     '</device-group></shared-policy></commit-all>')

                results = self.xapi.xml_result()

                if not self.__check_commit_return(results, force_sync):
                    raise PanoplyException(self.xapi.status_detail)

            return 'Prisma Access Committed Successfully'

        except PanXapiError as pxe:
            logger.error(pxe)
            raise PanoplyException('Could not commit configuration')

    @staticmethod
    def __check_commit_return(results: str, force_sync: bool) -> bool:
        """
        Check xml result from a panos device and check for a failure condition

        :param results: str returned from xapi.xml_result
        :param force_sync: if force_sync is true, then verify the commit actually succeeded
        :return: boolean
        """

        if results is None:
            return False

        if force_sync:
            embedded_result = None
            try:
                doc = ElementTree.XML(results)
                embedded_result = doc.find('result')

            except ParseError:
                # results can be malformed xml from gpcs
                if 'jobid' in results:
                    return True

            if embedded_result is not None:
                commit_result = embedded_result.text

                if commit_result == 'FAIL':
                    return False

                else:
                    return True
        else:
            # fixme - is there something else we can check here?
            return True

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
            raise PanoplyException(f'Could not push skillet {name} / snippet {xpath}! {pxe}')

    def execute_op(self, cmd_str: str, cmd_xml=False, parse_result=True) -> str:
        """
        Executes an 'op' command on the NGFW

        :param cmd_str: op command to send
        :param cmd_xml: Flag to determine if op command requires XML encoding
        :param parse_result: Optional flag to indicate whether to return parsed xml results (xml_result) from xapi - not
        all commands return valid XML. Setting this to 'false' will return the raw string from the API.
        :return: raw output from the device
        """

        try:
            self.xapi.op(cmd=cmd_str, cmd_xml=cmd_xml)
            if parse_result:
                return self.xapi.xml_result()
            else:
                return self.xapi.xml_document

        except PanXapiError as pxe:
            if 'ParseError' in str(pxe):
                # some op commands do not properly wrap data in CDATA tags, so let's try to
                # replace some chars manually and re-parse...
                x = self.xapi.xml_document

                # show config audit version will return an embedded xml document which breaks everything
                # just remove the invalid embedded xml tags if present
                cx = x.replace('&', '&amp;').replace('<?xml version="1.0"?>', '').replace('</xml>', '')

                try:
                    # make sure our little 'fix' didn't completely ruin the xml structure and return what we got
                    s = ElementTree.fromstring(cx)
                    return ElementTree.tostring(s).decode(encoding='UTF-8')

                except Exception as e:
                    logger.error(e)
                    raise PanoplyException(pxe)

            raise PanoplyException(pxe)

    def execute_cli(self, cmd_str: str) -> str:
        """
        Short-cut to execute a simple CLI op cmd

        :param cmd_str: CLI command to send to the NGFW
        :return: raw output from the command
        """
        return self.execute_op(cmd_str, cmd_xml=True)

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
            raise PanoplyException('Invalid cmd type given to execute_cmd')

        # this code happily borrowed from ansible-pan module
        # https://raw.githubusercontent.com/PaloAltoNetworks/ansible-pan/develop/library/panos_type_cmd.py

        func = getattr(self.xapi, cmd)

        # shortcut for op cmd types
        if cmd == 'op':
            cmd_str = ''.join(params['cmd_str'].strip().split('\n'))

            # fix for GL #79
            parse_result = params.get('parse_result', True)

            return self.execute_op(cmd_str, cmd_xml=False, parse_result=parse_result)

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
            raise PanoplyException(f'Invalid parameters passed to execute_cmd: {ke}')

        try:
            func(**kwargs)

        except PanXapiError as e:
            raise PanoplyException(f'Could not execute command: {cmd}: {e}')

        return self.xapi.xml_result()

    def fetch_license(self, auth_code: str) -> bool:
        """
        Fetch and install licenses for PAN-OS NGFW

        :param auth_code: Authorization code to use to license the NGFW
        :return: True when license installation succeeds / False otherwise
        """

        if self.facts.get('family', '') == 'vm':

            if self.facts.get('vm-license', 'none') != 'none':
                logger.debug('This VM is already licensed')
                return True

        try:
            cmd = f'<request><license><fetch><auth-code>{auth_code}</auth-code></fetch></license></request>'
            logger.debug(f'Using request cmd: {cmd}')
            self.xapi.op(cmd=cmd)
            results = self.xapi.xml_result()
            logger.debug(f'fetch_license results: {results}')

            if 'License installed' in results:
                return True

            else:
                logger.warning('Unexpected Results from fetch_license')
                logger.warning(results)
                return False

        except PanXapiError as pxe:
            # bug present in 9.0.4 that returns content-type of xml but the content is only text.
            # this causes a ParseError to be thrown, however, the operation was actually successful

            if 'ParseError' in str(pxe):

                if self.xapi.xml_document is not None and 'License installed' in self.xapi.xml_document:
                    return True

            logger.error(f'Caught Exception in fetch_license: {pxe}')

            if self.xapi.status_detail:
                logger.error(self.xapi.status_detail)

            return False

    def set_license_api_key(self, api_key: str) -> bool:
        """
        Set's the Palo Alto Networks Support API Key in the firewall. This is required to deactivate a VM-Series NGFW.

        :param api_key: Your support account API Key found on the support.paloaltonetworks.com site
        :return: boolean True on success / False otherwise
        """

        try:

            try:
                verify_cmd = '<request><license><api-key><show></show></api-key></license></request>'
                verify_results = self.execute_op(verify_cmd)
                logger.debug(verify_results)
                current_api_key = verify_results.split(': ')[1]

                if current_api_key == api_key:
                    logger.debug('API Key is already set')
                    return True

            except PanoplyException as pxe:
                # will raise an error if there is no key already set, just log it and continue
                logger.debug(pxe)

            cmd = f'<request><license><api-key><set><key>{api_key}</key></set></api-key></license></request>'
            logger.debug(f'Using request cmd: {cmd}')
            results = self.execute_op(cmd)
            logger.debug(f'set_license_api_key results: {results}')

            if 'successfully set' in results:
                return True

            else:
                logger.warning('Unexpected Results from set_license_api_key')
                logger.warning(results)
                return False

        except PanoplyException as pxe:
            logger.error(f'Caught Exception in set_license_api_key: {pxe}')

            if self.xapi.status_detail:
                logger.error(self.xapi.status_detail)

            return False

    def deactivate_vm_license(self, api_key: str = None) -> bool:
        """
        Deactivate VM-Series Licenses. Will set the API Key is not already set.

        :param api_key: Optional api_key.
        :return: boolean True on success / False otherwise
        """

        if self.facts.get('family', '') != 'vm':
            logger.warning('Attempting to deactivate license on a NGFW that is not a VM!')
            return False

        if self.facts.get('vm-license', 'none') == 'none':
            logger.debug('This VM is already de-licensed')
            return True

        if api_key is not None:

            if not self.set_license_api_key(api_key):
                return False

        try:
            cmd = '<request><license><deactivate><VM-Capacity><mode>auto</mode>' \
                  '</VM-Capacity></deactivate></license></request>'
            logger.debug(f'Using request cmd: {cmd}')
            results = self.execute_op(cmd)
            logger.debug(f'deactivate_vm_license results: {results}')

            if 'Successfully deactivated' in results:
                return True

            else:
                logger.warning('Unexpected Results from deactivate_vm_license')
                logger.warning(results)
                return False

        except PanoplyException as pxe:
            logger.error(f'Caught Exception in deactivate_vm_license: {pxe}')

            if self.xapi.status_detail:
                logger.error(self.xapi.status_detail)

            return False

    @staticmethod
    def sanitize_element(element: str) -> str:
        """
        Eliminate some unneeded characters from the XML snippet if they appear.

        :param element: element str
        :return: sanitized element str
        """
        element = re.sub(r"\n\s+", "", element)
        element = re.sub(r"\n", "", element)

        return element

    def backup_config(self):
        """
        Saves a named backup on the PAN-OS device. The format for the backup is 'config-backup-20190424000000.xml'

        :return:  xml results from the op command sequence
        """

        d = datetime.datetime.today()
        tstamp = d.strftime('%Y%m%d%H%M%S')
        cmd = f'<save><config><to>config-backup-{tstamp}.xml</to></config></save>'
        try:
            self.xapi.op(cmd=cmd)

            if self.xapi.status != 'success':
                raise PanoplyException('Could not perform config backup on device!')

            return self.xapi.xml_result()

        except xapi.PanXapiError as pxe:
            raise PanoplyException(f'Could not perform backup: {pxe}')

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
            raise PanoplyException('Could not get facts from device!')

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

        try:
            facts['panorama-server'] = results['system']['panorama']['local-panorama']['panorama-server']
        except (KeyError, TypeError):
            facts['panorama-server'] = None

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
        self.import_file('skillet_baseline.xml', file_contents, 'configuration')

        return self.load_config('skillet_baseline.xml')

    def generate_baseline(self, reset_hostname=False) -> str:
        """
        Load baseline config that contains ONLY connecting username / password
        use device facts to determine which baseline template to load
        see template/panos/baseline_80.xml for example

        :param self:
        :param reset_hostname: Flag to reset hostname back to a default value (baseline in this case)
        :return: string contents of baseline config
        """

        if not self.connected:
            self.connect()

        if 'sw-version' not in self.facts:
            raise PanoplyException('Could not determine sw-version to load baseline configuration!')

        version = self.facts['sw-version']
        context = dict()
        context['ADMINISTRATOR_USERNAME'] = self.user
        context['ADMINISTRATOR_PASSWORD'] = self.pw
        # fix for #50 - always set DNS values
        context['DNS_1'] = self.facts['dns-primary']
        context['DNS_2'] = self.facts['dns-secondary']

        if self.facts['model'] == 'Panorama':
            skillet_type_dir = 'panorama'

            if not reset_hostname:
                context['PANORAMA_NAME'] = self.facts['hostname']
            else:
                context['PANORAMA_NAME'] = 'baseline'

            # FIXME - is there a way to determine if dhcp is active via an op cmd?
            context['PANORAMA_TYPE'] = 'static'
            context['PANORAMA_IP'] = self.facts['ip-address']
            context['PANORAMA_MASK'] = self.facts['netmask']
            context['PANORAMA_DG'] = self.facts['default-gateway']

        else:
            skillet_type_dir = 'panos'

            if not reset_hostname:
                context['FW_NAME'] = self.facts['hostname']
            else:
                context['FW_NAME'] = 'baseline'

            if self.facts['is-dhcp'] == 'no':
                context['MGMT_TYPE'] = 'static'
                context['MGMT_IP'] = self.facts['ip-address']
                context['MGMT_MASK'] = self.facts['netmask']
                context['MGMT_DG'] = self.facts['default-gateway']

        if '8.0' in version:
            # load the 8.0 baseline with
            skillet_dir = 'baseline_80'

        elif '8.1' in version:
            # load the 8.1 baseline with
            skillet_dir = 'baseline_81'

        elif '9.0' in version:
            # load the 9.0 baseline with
            skillet_dir = 'baseline_90'

        elif '9.1' in version:
            # load the 9.1 baseline with
            skillet_dir = 'baseline_91'

        # Support 9.2 Beta and 10.0 for GL #80
        elif '9.2' in version:
            # load the 9.1 baseline with
            skillet_dir = 'baseline_91'

        elif '10.0' in version:
            # load the 9.1 baseline with
            skillet_dir = 'baseline_91'

        else:
            raise PanoplyException('Could not determine sw-version for baseline load')

        template_path = Path(__file__).parent.joinpath('assets', skillet_type_dir, skillet_dir)
        sl = SkilletLoader()
        baseline_skillet = sl.load_skillet_from_path(str(template_path.resolve()))
        snippets = baseline_skillet.get_snippets()
        snippet = snippets[0]
        output, status = snippet.execute(context)

        if status == 'success':
            return str(output)

        else:
            raise PanoplyException('Could not generate baseline config!')

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
            raise PanoplyException(r.content)

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

    def has_running_jobs(self) -> bool:
        """
        Simple check to determine if there are any running jobs on this device

        :return: bool True if there is currently a running job
        """

        self.execute_cli('show jobs all')
        jobs = self.xapi.xml_document
        jobs_element = etree.fromstring(jobs)

        running_jobs_list = jobs_element.xpath(".//jobs/status[text() != 'FIN']")

        return True if running_jobs_list else False

    def wait_for_device_ready(self, interval=30, timeout=600) -> bool:
        """
        Loop and wait until device is ready or times out

        .. note::

            This currently only supports PAN-OS devices and not Panorama

        :param interval: how often to check in seconds
        :param timeout: how long to wait until we declare a timeout condition
        :return: boolean true on ready, false on timeout
        """
        mark = time.time()
        timeout_mark = mark + timeout

        while True:
            try:

                # fix for #60 - show chassis ready is not available on panorama
                if self.facts.get('model', 'Panorama') == 'Panorama':
                    cmd = "<show><system><info></info></system></show>"
                    is_panorama = True
                else:
                    cmd = '<show><chassis-ready></chassis-ready></show>'
                    is_panorama = False

                self.xapi.op(cmd=cmd)
                resp = self.xapi.xml_result()

                if self.xapi.status == 'success':
                    # in the case of panorama, we may be up but the auto-commit job may still be running
                    # continue to wait until there are no more jobs
                    # FIXME - should probably enhance this to only check for auto-commit job, it's possible there
                    # can be other jobs running with a busy / heavily used panorama instance
                    if is_panorama:
                        if not self.has_running_jobs():
                            return True

                    if resp.strip() == 'yes':
                        return True

            except TargetLoginException:
                logger.error('Could not log in to device...')
                return False

            except PanXapiError:
                logger.info(f'{self.hostname} is not yet ready...')

            if time.time() > timeout_mark:
                return False

            logger.info(f'Waiting for {self.hostname} to become ready...')
            time.sleep(interval)

    def filter_connected_devices(self, filter_terms=None) -> list:
        """
        Returns the list of connected devices filtered according to the given terms.

        Filter terms are based on keys in the device facts. Matches are done using simple regex match

        :param filter_terms: dict containing key value pairs. Keys match keys from the return device facts and values
        are regex expressions used to match those keys
        :return: list of devices that match ALL filter terms
        """

        if filter_terms is None:
            filter_terms = {}

        if self.facts.get('model', '') != 'Panorama':
            logger.info('Method only supported on Panorama Devices')
            return list()

        connected_devices_xml = self.execute_cli('show devices connected')
        connected_devices_dict = xmltodict.parse(connected_devices_xml)

        if 'devices' in connected_devices_xml and 'entry' in connected_devices_dict['devices']:
            connected_devices = connected_devices_dict['devices']['entry']

        else:
            return list()

        if not filter_terms:
            # no terms given, return all devices
            return connected_devices

        filtered_devices = list()

        for device in connected_devices:
            match = False

            for term in filter_terms:
                if term in device:

                    if re.match(filter_terms[term], device[term]):
                        match = True
                    else:
                        match = False

            if match:
                filtered_devices.append(device)

        return filtered_devices

    def update_dynamic_content(self, content_type: str) -> bool:
        """
        Check for newer dynamic content and install if found

        :param content_type: type of content to check. can be either: 'content', 'anti-virus', 'wildfire'
        :return: bool True on success
        """
        try:
            version_to_install = self.check_content_updates(content_type)

            if version_to_install is None:
                logger.info(f'Latest {content_type} version is already installed')
                return True

            logger.info(f'Downloading Dynamic Content of type: {content_type}')
            cmd = f'<request>' \
                  f'<{content_type}><upgrade><download><latest/></download></upgrade></{content_type}>' \
                  f'</request>'

            self.xapi.op(cmd=cmd)
            results_element = self.xapi.element_result
            job_element = results_element.find('.//job')

            if job_element is not None:
                job_id = job_element.text

                if not self.wait_for_job(job_id):
                    raise PanoplyException('Could not update dynamic content')

            logger.info(f'Installing newer {content_type}')
            install_cmd = f'<request><{content_type}><upgrade><install>' \
                          f'<version>latest</version><commit>no</commit></install></upgrade></{content_type}></request>'

            self.xapi.op(cmd=install_cmd)
            results_element = self.xapi.element_result
            job_element = results_element.find('.//job')

            if job_element is not None:
                job_id = job_element.text

                if not self.wait_for_job(job_id):
                    raise PanoplyException('Could not install dynamic content')

            else:
                logger.info('No job returned to track')

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
            logger.info(f'Checking for newer {content_type}...')
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

            except PanXapiError as pxe:
                logger.error(f'Exception checking job: {pxe}')
                logger.error(f'Could not locate job with id: {job_id}')
                return False

            if self.xapi.status == 'success':
                job_element = self.xapi.element_result
                job_status_element = job_element.find('.//status')

                if job_status_element is not None:
                    job_status = job_status_element.text

                    if job_status == 'FIN':
                        logger.debug(f'Job: {job_id} is now complete')
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

    def get_configuration(self, config_source='running') -> str:
        """
        Get the configuration from the device.

        :param config_source: Configuration source. This can be either 'candidate, running, baseline, or an
        audit version number. Candidate is the candidate config, running is the running config, baseline is an
        autogenerated bare configuration, and version number is the previously saved running configuration. A positive
        version number will get the configuration version matching that id. A negative version number will get the
        most recent to least recent configuration versions where (-1) is the most recent previous running config.
        :return: configuration xml as a string or a blank string if not connected
        """

        if config_source == 'baseline':
            return self.generate_baseline()

        elif config_source == 'candidate':
            cmd = 'show config candidate'

        elif re.match(r'^-\d+$', str(config_source)):
            # this is an inverted configuration version number (-1, -2, -3, etc)
            return self.__get_inverted_configuration_version(config_source)

        elif re.match(r'^\d+$', str(config_source)):
            # normal configuration version id (13, 12, 10, etc)
            return self.get_configuration_version(config_source)

        else:
            if self.facts.get('panorama-server', None) is not None:
                cmd = 'show config merged'
            else:
                cmd = 'show config running'

        try:

            if self.connected:
                self.xapi.op(cmd=cmd, cmd_xml=True)
                return self.xapi.xml_result()

            else:
                return ''

        except PanXapiError:
            logger.error('Could not get configuration from device')
            raise PanoplyException('Could not get configuration from the device')

    def get_saved_configuration(self, configuration_name: str) -> str:
        """
        Returns a saved configuration on the device. Use 'list_saved_configuration' to get a list of available options

        :param configuration_name: name of the saved configuration to export
        :return: configuration as an XML encoded string
        """

        try:

            if self.connected:
                self.xapi.op(f'<show><config><saved>{configuration_name}</saved></config></show>', cmd_xml=False)

                if self.xapi.status != 'success':
                    raise PanoplyException('Could not get saved configuration from the device')

                doc_str = self.xapi.xml_result()

                doc = etree.fromstring(doc_str)
                return etree.tostring(doc, pretty_print=True).decode(encoding='UTF-8')

            else:
                return ''

        except PanXapiError:
            logger.error('Could not get saved configuration from device')
            raise PanoplyException('Could not get saved configuration from the device')

    def list_saved_configurations(self) -> list:
        """
        Returns a list of saved configuration files on this device

        :return: list of saved configurations
        """

        saved_configurations = list()
        try:
            if not self.connected:
                return saved_configurations

            self.xapi.ad_hoc(qs='type=op&action=complete&xpath=/operations/load/config/from', modify_qs=True)

            if self.xapi.status != 'success':
                raise PanoplyException('Could not list saved configurations from the device')

            response_root = self.xapi.element_root
            config_items = response_root.findall('.//completion')
            for config in config_items:
                if 'value' in config.attrib:
                    saved_configurations.append(config.attrib['value'])

            return saved_configurations

        except PanXapiError as pe:
            logger.error('Could not list configurations from device')
            logger.error(pe)
            raise PanoplyException('Could not list saved configuration from the device')

    def get_configuration_version(self, version: str) -> str:
        """
        Returns a configuration version on the device. Use 'list_configuration_versions' to get a list of available
        options

        :param version: version number of the configuration version to export
        :return: configuration as an XML encoded string
        """

        try:

            if self.connected:
                self.xapi.op(f'<show><config><audit><base-version>{version}</base-version></audit></config></show>',
                             cmd_xml=False
                             )

                if self.xapi.status != 'success':
                    raise PanoplyException('Could not get configuration version from the device')

                doc_str = self.xapi.xml_result()

                doc = etree.fromstring(doc_str)
                return etree.tostring(doc, pretty_print=True).decode(encoding='UTF-8')

            else:
                return ''

        except PanXapiError:
            logger.error('Could not get configuration version from device')
            raise PanoplyException('Could not get configuration version from the device')

    def __get_inverted_configuration_version(self, inverted_version: str):
        """
        Utility method to get the configuration version in an inverted sequence. I.e. this allows you to get the most
        recent configuration version by using '-1', or '-2' to get the second most recent and so on

        :param inverted_version: negative number indicating the most recent version to grab. -1 is the most recent
        :return: XML configuration as a string
        """

        # get all versions
        versions = self.get_configuration_versions()

        # convert this list of str into list of int and sort it
        sorted_versions = sorted(list(map(int, [x["version"] for x in versions])))

        try:
            # get the actual desired version id, note the highest numbered config id is actually the running
            # config, so we want to allow the user to specify -1 as the 'previous' config, not the current config...
            desired_version = sorted_versions[int(inverted_version) - 1]
            # return the configuration
            return self.get_configuration_version(str(desired_version))

        except IndexError:
            raise PanoplyException(f'Inverted Configuration value is out of range! Max is {len(versions)}')

    def get_configuration_versions(self):

        versions = list()
        try:
            if not self.connected:
                return versions

            self.xapi.ad_hoc(qs='type=op&action=complete&xpath=/operations/show/config/audit/version', modify_qs=True)

            if self.xapi.status != 'success':
                raise PanoplyException('Could not list configuration versions from the device')

            response_root = self.xapi.element_root
            config_items = response_root.findall('.//completion')
            for config in config_items:
                if 'value' in config.attrib and config.attrib['value'] != '':
                    v = {
                        'version': config.attrib["value"],
                        'date': config.attrib["help-string"]
                    }
                    versions.append(v)

            return versions

        except PanXapiError as pe:
            logger.error('Could not list configuration versions from device')
            logger.error(pe)
            raise PanoplyException('Could not list saved configuration from the device')

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
            previous_config = self.generate_baseline(reset_hostname=True)
            self.xapi.op(cmd='show config running', cmd_xml=True)
            latest_config = self.xapi.xml_result()

        return self.generate_skillet_from_configs(previous_config, latest_config)

    def generate_skillet_from_configs(self, previous_config: str, latest_config: str) -> list:
        """
        Generates a skillet from the diffs between two XML configuration files

        :param previous_config: Configuration backup taken before desired changes are made to the device
        :param latest_config: Configuration backup taken after desired changes are made

        :return: list of dictionaries that contain the following keys:
            * name
            * element
            * xpath
            * full_xpath
        """
        # convert the config string to an xml doc
        latest_doc = etree.fromstring(latest_config)

        # let's grab the previous as well
        previous_doc = etree.fromstring(previous_config)

        current_xpath = '.'
        not_found_xpaths = list()

        for c in latest_doc:
            o_xpath = current_xpath + '/' + c.tag
            these_not_found_xpaths = self.__check_element(c, o_xpath, previous_doc, [])
            not_found_xpaths.extend(these_not_found_xpaths)

        snippets = list()

        for xpath in not_found_xpaths:

            # xpath comes as a relative full xpath like './mgt-config/password-complexity'
            # make it /config/mgt-config/password-complexity
            full_xpath = re.sub(r'^\./', r'/config/', xpath)
            # force full xpath for #52 - split off last bit like password-complexity
            set_xpath, entry = self.__split_xpath(full_xpath)
            # remove any attribute for tag name
            tag = re.sub(r'\[.*\]', '', entry)

            # check if this xpath is actually user configurable
            if self.__is_ignored_xpath(set_xpath):
                continue

            # in some cases we need to ignore xpath + element for example
            # /config/shared/content-preview
            if self.__is_ignored_xpath(full_xpath):
                continue

            changed_elements = latest_doc.xpath(xpath)

            if not changed_elements:
                print('Something is broken here')
                continue

            changed_element = changed_elements[0]

            cleaned_element = self.__clean_uuid(changed_element)
            xml_string = etree.tostring(cleaned_element, pretty_print=True).decode(encoding='UTF-8')

            random_name = str(int(random.random() * 1000000))

            snippet = dict()
            snippet['name'] = f'{tag}-{random_name}'
            snippet['xpath'] = set_xpath
            snippet['element'] = xml_string.strip()
            snippet['full_xpath'] = xpath
            snippets.append(snippet)

        return self.__order_snippets(snippets)

    @staticmethod
    def __is_ignored_xpath(set_xpath: str) -> bool:
        """
        Determines if the given set_xpath should be used for skillet generation purposes. Certain xpaths will be
        changed, however, they are not user configurable, and therefore should not be included

        :param set_xpath: xpath string to check
        :return: boolean true if the xpath should be skipped
        """
        ignored_xpaths = (
            '/config/mgt-config/users/entry[@name="admin"]',
            '/config/shared/content-preview',
            '/config/readonly'
        )

        for ignored_xpath in ignored_xpaths:
            if ignored_xpath in set_xpath:
                logger.debug(f'Skipping ignored xpath: {set_xpath}')
                return True

        return False

    @staticmethod
    def __is_ignored_set_cli(set_cli: str) -> bool:
        """
        Determines if the generated set cli can be used to recreate this configuration. Some generated
        set clis are simply remnants of the XML structure and are not actually valid set cli commands

        :param set_cli: set command to check
        :return: bool True if this cli should be excluded
        """

        # ignore any set clis that start with this commands
        ignored_set_prefix = (
            'set mgt-config users admin phash',
            'set shared content-preview',
            'set read-only'
        )

        # ignore any set cli that match these commands
        ignored_set_cli = (
            'set shared application',
            'set shared application-group',
            'set shared service',
            'set shared service-group'
        )

        # ignore any set cli that contain these strings
        ignored_set_cli_parts = (
            'deviceconfig setting management initcfg',
            'deviceconfig setting management disable-predefined-reports'

        )

        for prefix in ignored_set_prefix:
            if set_cli.startswith(prefix):
                logger.debug(f'Skipping ignore set cli prefix: {set_cli}')
                return True

        for ignorned_set in ignored_set_cli:
            if set_cli == ignorned_set:
                logger.debug(f'Skipping ignore set cli: {set_cli}')
                return True

        for part in ignored_set_cli_parts:
            if part in set_cli:
                logger.debug(f'Skipping ignored set cli with part: {set_cli}')
                return True

        return False

    def generate_set_cli_from_configs(self, previous_config: str, latest_config: str) -> list:
        """
        Takes two configuration files, converts them to set commands, then returns only the commands found
        in the 'latest_config' vs the 'previous_config'. This allows the user to quickly configure one firewall,
        generate a 'set cli' diff and move those configs to another firewall

        :param previous_config: Starting config
        :param latest_config: Ending config
        :return: list of set cli commands required to convert previous to latest
        """

        p_config = PanConfig(previous_config)
        l_config = PanConfig(latest_config)

        p_set = p_config.set_cli('set ', xpath='./')
        l_set = l_config.set_cli('set ', xpath='./')

        # diffs = [item for item in l_set if item not in p_set]
        diffs = list()

        for cmd in l_set:

            if cmd not in p_set:

                if self.__is_ignored_set_cli(cmd):
                    continue

                cmd_cleaned = cmd.replace('\n', ' ')
                diffs.append(cmd_cleaned)

        return self.__order_set_commands(diffs)

    def __check_element(self, el: etree.Element, xpath: str, pc: etree.Element, not_founds: list) -> list:
        """
        recursive function to determine if the 'el' Element found at 'xpath' can also be found at the same
        xpath in the 'pc' previous_config. Keep tabs on what has not been found using the 'not_founds' list

        :param el: The element in question from the latest_config
        :param xpath: the xpath to the element in question
        :param pc:  the previous config Element
        :param not_founds: list of xpaths that have not been found
        :return: a list of xpaths that have not been found in the previous_config at this level
        """

        # first, check the previous_config to see if this xpath exists there
        found_elements = pc.xpath(xpath)

        if found_elements:
            found_element = found_elements[0]
            # this xpath exists in the previous_config, now iterate through all the children
            children = el.findall('./')

            if len(children) == 0:
                # there are no children at this level, so check if the 'text' is different

                if found_element.text != el.text:
                    # this xpath contains a text node that has been modified <port>6666</port> != <port>0000</port>
                    not_founds.append(xpath)
                # no need to go further as we have no children to descend into
                return not_founds

            # we have children elements, first check if they are a list of identical elements
            is_list = False

            if self.__check_children_are_list(children):
                # use the xmldiff library to check the list of elements
                diffs = xmldiff_main.diff_trees(found_element, el,
                                                {'F': 0.1, 'ratio_mode': 'accurate', 'fast_match': True})

                # all children are a list and there are no differences in them, so return up the stack
                if len(diffs) == 0:
                    return not_founds

                else:
                    # we have a list and there ARE differences
                    is_list = True

            # continue checking each child, either they are not a list or they are a list and there are diffs
            # track the child index in case we find a diff in the list case
            index = 1
            # check each child now
            for e in el:

                if e.attrib:
                    attribs = list()

                    for k, v in e.attrib.items():

                        if k != 'uuid':
                            attribs.append(f'@{k}="{v}"')

                    # fix for #71
                    attrib_str = " and ".join(attribs)
                    # track the attributes in the xpath by virtue of the 'path_entry' which will be appended to the
                    # xpath later
                    path_entry = f'{e.tag}[{attrib_str}]'

                else:
                    # no attributes but this is a list, so include the index value in the xpath to check
                    # this will be used to grab the changed element later, but will be removed from the xpath
                    # as it is not necessary in PAN-OS (double check this please)

                    if is_list:

                        if e.text.strip() != '':
                            path_entry = f'{e.tag}[text()="{e.text.strip()}"]'

                        else:
                            path_entry = f'{e.tag}[{index}]'

                    else:
                        # just append the tag to the xpath and move on
                        path_entry = e.tag

                # craft our new xpath to check
                n_xpath = xpath + '/' + path_entry
                # do it all over again
                new_not_founds = self.__check_element(e, n_xpath, pc, list())
                # add any child xpaths that weren't found with any found here for return up the stack
                not_founds.extend(new_not_founds)
                # increase our index for the next iteration
                index = index + 1

            # return our findings up the stack
            return not_founds

        # check this element to determine if it's 'blank'
        if len(el.findall('./')) == 0 and not el.attrib and (not el.text or not el.text.strip()):
            return not_founds

        not_founds.append(xpath)
        return not_founds

    @staticmethod
    def __split_xpath(xpath: str) -> Tuple[str, str]:
        xpath_parts = re.split(r'/(?=(?:[^"]*"[^"]*")*[^"]*$)', xpath)
        new_xpath = "/".join(xpath_parts[:-1])
        entry = xpath_parts[-1]

        return new_xpath, entry

    def __order_snippets(self, snippets: list) -> list:
        """
        Orders a set of snippets according to PAN-OS rules. This is an evolving list, which will almost certainly
        be 100% correct. Please file issues if you find an ordering issue in auto-generated snippets or set commands

        :param snippets: list of snippet dictionaries to order
        :return:  list of a snippet dictionary in the order in which they need to be applied to a NGFW or Panorama
        """
        # Attempt to order the snippets in a cohesive ordering. Will never be 100% perfect,
        # but at least make the attempt

        xpaths, post_xpaths = self.get_ordered_xpaths()

        ordered_snippets = list()
        for x in xpaths:
            found_snippets = self.__filter_snippets_by_xpath(snippets, x)
            for s in found_snippets:
                if s not in ordered_snippets:
                    ordered_snippets.append(s)

        post_snippets = list()
        for p in post_xpaths:
            filtered_snippets = self.__filter_snippets_by_xpath(snippets, p)
            for f in filtered_snippets:
                if f not in post_snippets:
                    post_snippets.append(f)

        for s in snippets:
            if s not in ordered_snippets and s not in post_snippets:
                ordered_snippets.append(s)

        for ps in post_snippets:
            if ps not in ordered_snippets:
                ordered_snippets.append(ps)

        return ordered_snippets

    def __order_set_commands(self, set_commands: list) -> list:
        """
        This will attempt to order a list of set commands using the same logic as ordering snippets.
        This is done by converting the set command into a 'fake' xpath, creating a fake snippet dictionary
        and sending those through the order_snippets method

        :param set_commands: list of set commands to order
        :return: a list of ordered set commands
        """

        ordered_set_commands = list()

        fake_snippets = list()

        # little bit of a hack here
        # our set commands can contain slashes like `set mgmt-config ip-address 10.10.10.1/24` and we ultimately
        # need to convert this to xpath format for ordering purposes `set/mgt-confg/ip-address/10.10.10.1/24`
        # so, let's do a simple replacement of any valid forward slashes before hand
        slash_marker = '****'

        for set_cmd in set_commands:
            snippet = dict()
            snippet['full_xpath'] = set_cmd.replace('/', slash_marker).replace(' ', '/')
            fake_snippets.append(snippet)

        ordered_fake_snippets = self.__order_snippets(fake_snippets)

        for fake_snippet in ordered_fake_snippets:
            new_set_command = fake_snippet['full_xpath'].replace('/', ' ').replace(slash_marker, '/')
            ordered_set_commands.append(new_set_command)

        return ordered_set_commands

    @staticmethod
    def __filter_snippets_by_xpath(snippets: list, xpath: str) -> list:
        """
        Check each snippet in the list and return those that have a full_xpath matching the xpath param. This is
        done by finding the specific leaf node of the xpath by using only the xpath portions after any template, device,
        or vsys entries. So an xpath pattern like 'network/interface' will match even within templates, across vsys,
        etc

        :param snippets: list of snippets
        :param xpath: xpath to check
        :return: list of only those that contain the xpath in their full_xpath attribute
        """
        filtered_snippets = list()

        split_pattern = re.compile(r'/devices/.*?/|vsys/.*?/')

        for s in snippets:
            full_xpath = s.get('full_xpath', '')

            split_xpath = split_pattern.split(full_xpath)
            leaf_xpath_initial = split_xpath[-1]

            # handle cases like ./mgt-config/password-complexity - remove the leading './'
            leaf_xpath = re.sub(r'^\./', '', leaf_xpath_initial)
            if leaf_xpath.startswith(xpath):
                # note we do not remove found snippets from the source snippets list, which may result
                # in duplicates. The calling code will need to ensure it does not append the results of this method
                # which out checking for dups first
                filtered_snippets.append(s)

        return filtered_snippets

    @staticmethod
    def __check_children_are_list(c: list) -> bool:
        """
        Check if this list possibly contains identical children. I.E. a list of members or simple entries.
        If this is the case, then we'll use xmldiff to find diffs in there to keep this logic simple. Otherwise,
        we'll continue to iterate through the document

        :param c: list of elements
        :return: True if all elements have the same tag name and have no children
        """
        # check if children are a list of items by identical tag names

        if len(c) <= 1:
            # can't be a list of identical items if there are only 0 or 1 items
            return False

        found_tag_name = ''

        for child in c:

            # if any child itself has children, then this is not a list of identical items. Return False here
            if len(child):
                return False

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

    @staticmethod
    def __clean_uuid(changed_element: Element) -> Element:
        """
        Some rules and other elements contain the 'uuid' attribute. These should be removed before
        they can be applied to another device / fw. This function descends to all child nodes and removes the uuid
        attribute if found
        :param changed_element: Element in which to search
        :return: Element with all uuid attributes removed
        """
        if changed_element is None:
            return changed_element

        # check if 'uuid' is an attribute on this element
        if 'uuid' in changed_element.attrib:
            changed_element.attrib.pop('uuid')

        # this will find all child nodes with a 'uuid' attribute
        child_nodes = changed_element.findall('.//*[@uuid]')

        if child_nodes is None or len(child_nodes) == 0:
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
                raise PanoplyException('Could not normalize xpath in configuration document!')

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

    @staticmethod
    def get_ordered_xpaths() -> tuple:
        """
        Returns a list of ordered xpaths for use in ordering snippets and set commands

        Will be enhanced one day with version and model specific information if necessary

        :return: tuple of two lists, xpaths and post_xpaths
        """
        xpaths = [
            'shared/certificate',
            'shared/ssl-tls-service-profile',
            'shared/tag',
            'shared/profiles',
            'shared/reports',
            'shared/',  # catch the rest of the shared items here
            'tag/',
            'deviceconfig/system',
            'network/profiles',
            'network/interface',
            'network/virtual-wire',
            'network/vlan',
            'network/ike',
            'network/tunnel',
            'import/network/interface',  # for use with panorama plugin import (SD-WAN)
            'network/virtual-router',
            'network/profiles/zone-protection-profile',
            'routing-table/ip/static-route/entry/next-hop',  # try to keep next-hop before path-monitor for set cli
            'routing-table/ip/static-route/entry/path-monitor',  # #70
            'dynamic-ip-and-port/interface-address',  # GH #70
            'dynamic-ip-and-port/interface',  # GH #70
            'dynamic-ip-and-port/ip',  # GH #70
            'zone/',
            'profiles/custom-url-category',  # should come before profiles/url-filtering
            'address/'  # should come before rules or address-group
        ]

        post_xpaths = ['rulebase']

        return xpaths, post_xpaths


class EphemeralPanos(Panoply):
    """
    EphemeralPanos is used when a Panos instance may or may not be online and available at all times. This is useful
    when instantiating instances via a CI/CD pipeline or other automation tool.
    """
    pass


class Panos(Panoply):
    """
    Panos is used to connect to PAN-OS devices that are expected to be currently and always online! Exceptions
    will be raised in any event that we cannot connect!
    """

    def __init__(self, hostname: Optional[str], api_username: Optional[str], api_password: Optional[str],
                 api_port: Optional[int] = 443, serial_number: Optional[str] = None,
                 debug: Optional[bool] = False, api_key: Optional[str] = None):

        super().__init__(hostname, api_username, api_password, api_port, serial_number, debug, api_key)

        if self.connected:
            return

        if self.xapi and 'URLError' in self.xapi.status_detail:
            raise TargetConnectionException(self.xapi.status_detail)
