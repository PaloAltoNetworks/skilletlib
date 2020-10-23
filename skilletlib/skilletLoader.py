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
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import List

import oyaml
from yaml.error import YAMLError

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.exceptions import SkilletNotFoundException
from skilletlib.remotes.git import Git
from skilletlib.skillet.base import Skillet

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not len(logger.handlers):
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


class SkilletLoader:
    """

    SkilletLoader is used to find and load Skillets from their metadata files, either from on filesystem path
    or from a git repository URL

    :param path: local relative path to search for all Skillet meta-data files
    """
    skillets = List[Skillet]
    skillet_errors = list()

    def __init__(self, path=None):
        debug = os.environ.get('SKILLET_DEBUG', False)

        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug('Debugging output enabled')

        if path is not None:
            self.load_all_skillets_from_dir(path)

    def load_skillet_dict_from_path(self, skillet_path: str) -> dict:
        """
        Loads the skillet metadata file into a skillet_dict dictionary

        :param skillet_path: path in which to look for a metadata file
        :return: skillet dictionary
        """
        return self._parse_skillet(skillet_path)

    def load_skillet_from_path(self, skillet_path: (str, Path)) -> Skillet:
        """
        Returns a Skillet object from the given path.

        :param skillet_path: path in which to search for a skillet
        :return: Skillet object of the correct type
        """
        skillet_dict = self._parse_skillet(skillet_path)
        return self.create_skillet(skillet_dict)

    def create_skillet(self, skillet_dict: dict) -> Skillet:
        """
        Creates a Skillet object from the given skillet definition

        :param skillet_dict: Dictionary loaded from the .meta-cnc.yaml skillet definition file
        :return: Skillet Object
        """
        skillet_type = skillet_dict['type']

        if skillet_type == 'panos' or skillet_type == 'panorama' or skillet_type == 'panorama-gpcs':
            from skilletlib.skillet.panos import PanosSkillet
            return PanosSkillet(skillet_dict)

        elif skillet_type == 'pan_validation':
            from skilletlib.skillet.pan_validation import PanValidationSkillet
            return PanValidationSkillet(skillet_dict)

        elif skillet_type == 'python3':
            from skilletlib.skillet.python3 import Python3Skillet
            return Python3Skillet(skillet_dict)

        elif skillet_type == 'template':
            from skilletlib.skillet.template import TemplateSkillet
            return TemplateSkillet(skillet_dict)

        elif skillet_type == 'docker':
            from skilletlib.skillet.docker import DockerSkillet
            return DockerSkillet(skillet_dict)

        elif skillet_type == 'rest':
            from skilletlib.skillet.rest import RestSkillet
            return RestSkillet(skillet_dict)

        elif skillet_type == 'workflow':
            from skilletlib.skillet.workflow import WorkflowSkillet
            return WorkflowSkillet(skillet_dict, self)

        elif skillet_type == 'terraform':
            from skilletlib.skillet.terraform import TerraformSkillet
            return TerraformSkillet(skillet_dict)

        elif skillet_type == 'app':
            from skilletlib.skillet.app import AppSkillet
            return AppSkillet(skillet_dict)

        else:
            raise SkilletLoaderException('Unknown Skillet Type!')

    def _parse_skillet(self, path: (str, Path)) -> dict:

        if type(path) is str:
            path_str = path
            path_obj = Path(path)

        elif isinstance(path, Path):
            path_str = str(path)
            path_obj = path

        else:
            raise SkilletLoaderException('Invalid path type found in _parse_skillet!')

        if 'meta-cnc' in path_str:
            meta_cnc_file = path_obj

            if not path_obj.exists():
                raise SkilletNotFoundException(f'Could not find .meta-cnc file as this location: {path}')

        else:
            # we were only passed a directory like '.' or something, try to find a .meta-cnc.yaml or .meta-cnc.yml
            directory = path_obj
            logger.debug(f'using directory {directory}')
            found_meta = False

            for filename in ['.meta-cnc.yaml', '.meta-cnc.yml', 'meta-cnc.yaml', 'meta-cnc.yml']:
                meta_cnc_file = directory.joinpath(filename)
                logger.debug(f'checking now {meta_cnc_file}')

                if meta_cnc_file.exists():
                    found_meta = True
                    break

            if not found_meta:
                raise SkilletNotFoundException('Could not find .meta-cnc file at this location')

        snippet_path = str(meta_cnc_file.parent.absolute())
        try:

            with meta_cnc_file.open(mode='r') as sc:
                raw_service_config = oyaml.safe_load(sc.read())
                skillet = self.normalize_skillet_dict(raw_service_config)
                skillet['snippet_path'] = snippet_path
                return skillet

        except IOError:
            logger.error('Could not open metadata file in dir %s' % meta_cnc_file.parent)
            raise SkilletLoaderException('IOError: Could not parse metadata file in dir %s' % meta_cnc_file.parent)

        except YAMLError as ye:
            logger.error(ye)
            raise SkilletLoaderException(
                'YAMLError: Could not parse metadata file in dir %s' % meta_cnc_file.parent)

        except Exception as ex:
            logger.error(ex)
            raise SkilletLoaderException(
                'Exception: Could not parse metadata file in dir %s' % meta_cnc_file.parent)

    @staticmethod
    def normalize_skillet_dict(skillet: dict) -> dict:
        """
        Attempt to resolve common configuration file format errors

        :param skillet: a loaded skillet/snippet
        :return: skillet/snippet that has been 'fixed'
        """

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
            skillet['description'] = 'template skillet'

        # first verify the variables stanza is present and is a list
        if 'variables' not in skillet:
            skillet['variables'] = list()

        elif skillet['variables'] is None:
            skillet['variables'] = list()

        elif type(skillet['variables']) is not list:
            skillet['variables'] = list()

        elif type(skillet['variables']) is list:

            for variable in skillet['variables']:

                if type(variable) is not dict:
                    logger.debug('Removing Invalid Variable Definition')
                    skillet['variables'].remove(variable)

                else:

                    if 'name' not in variable:
                        variable['name'] = 'Unknown variable'

                    if 'type_hint' not in variable:
                        variable['type_hint'] = 'text'

                    if 'default' not in variable:
                        variable['default'] = ''

        if 'depends' not in skillet:
            skillet['depends'] = list()

        elif not isinstance(skillet['depends'], list):
            skillet['depends'] = list()

        elif isinstance(skillet['depends'], list):
            for depends in skillet['depends']:

                if not isinstance(depends, dict):
                    print('Removing Invalid Depends Definition')
                    print(type(depends))
                    skillet['depends'].remove(depends)

                else:
                    if not {'url', 'name'}.issubset(depends):
                        print('Removing Invalid Depends Definition - incorrect attributes')
                        print('Required "url" and "name" to be present. "branch" is optional')
                        print(depends)

                    else:
                        if depends['url'] is None or depends['url'] == '' \
                                or depends['name'] is None or depends['name'] == '':
                            print('Removing Invalid Depends Definition - incorrect attribute values')
                            print('Required "url" and "name" to be not be blank or None')
                            print(depends)

        # verify labels stanza is present and is a OrderedDict
        if 'labels' not in skillet:
            skillet['labels'] = OrderedDict()

        elif skillet['labels'] is None:
            skillet['labels'] = OrderedDict()

        elif type(skillet['labels']) is not OrderedDict and type(skillet['labels']) is not dict:
            skillet['labels'] = OrderedDict()

        # ensure we have a collection label
        if 'collection' not in skillet['labels'] or type(skillet['labels']['collection']) is None:
            # do not force a collection for 'app' type skillets as these aren't meant to be shown to the end user

            if skillet['type'] != 'app':
                skillet['labels']['collection'] = list()
                skillet['labels']['collection'].append('Unknown')

        elif type(skillet['labels']['collection']) is str:
            new_collection = list()
            old_value = skillet['labels']['collection']
            new_collection.append(old_value)
            skillet['labels']['collection'] = new_collection

        # ensure no app_data attribute is present in the skillet definition
        if 'app_data' in skillet:
            skillet.pop('app_data')

        # verify snippets stanza is present and is a list
        if 'snippets' not in skillet:
            skillet['snippets'] = list()

        elif skillet['snippets'] is None:
            skillet['snippets'] = list()

        elif type(skillet['snippets']) is not list:
            skillet['snippets'] = list()

        return skillet

    @staticmethod
    def debug_skillet_structure(skillet: dict) -> list:
        """
        Verifies the structure of a skillet and returns a list of errors or warning if found

        :param skillet: Skillet Definition Dictionary
        :return: list of errors or warnings if found
        """

        errs = list()

        if skillet is None:
            errs.append('Skillet is blank or could not be loaded')
            return errs

        if not isinstance(skillet, dict):
            errs.append('Skillet is malformed')
            return errs

        # verify labels stanza is present
        if 'labels' not in skillet:
            errs.append('No labels attribute present in skillet')
        else:
            if 'collection' not in skillet['labels']:
                errs.append('No collection defined in skillet')

        if 'label' not in skillet:
            errs.append('No label attribute in skillet')

        if 'type' not in skillet:
            errs.append('No type attribute in skillet')
        else:
            valid_types = ['panos', 'panorama', 'panorama-gpcs', 'pan_validation',
                           'python3', 'rest', 'terraform', 'template', 'workflow', 'docker', 'app']
            if skillet['type'] not in valid_types:
                errs.append(f'Unknown type {skillet["type"]} in skillet')

        return errs

    def get_skillet_with_name(self, skillet_name: str) -> (Skillet, None):
        """
        Returns a single skillet from the loaded skillets list that has the matching 'name' attribute

        :param skillet_name: Name of the skillet to return
        :return: Skillet
        """

        if not self.skillets:
            raise SkilletLoaderException('No Skillets have been loaded!')

        for skillet in self.skillets:
            if skillet.name == skillet_name:
                return skillet

        return None

    def load_all_skillets_from_dir(self, directory: (str, Path)) -> List[Skillet]:
        """
        Recursively iterate through all sub-directories and locate all found skillets
        Returns a list of Loaded Skillets

        :param directory: parent directory in which to start iterating
        :return: list of skillets
        """
        if type(directory) is str:
            d = Path(directory)

        else:
            d = directory

        # reset skillet errors list here
        self.skillet_errors = list()
        self.skillets = self._check_dir(d, list())

        return self.skillets

    def _check_dir(self, directory: Path, skillet_list: list) -> list:
        """
        Recursive function to look for all files in the current directory with a name matching '.meta-cnc.yaml'
        otherwise, iterate through all sub-dirs and skip dirs with name that match '.git', '.venv', and '.terraform'
        will descend into all other dirs and call itself again.
        Returns a list of compiled skillets

        :param directory: PosixPath of directory to begin searching
        :param skillet_list: combined list of all loaded skillets
        :return: list of Skillets
        """
        logger.debug(f'Checking dir: {directory}')
        err_condition = False

        for d in directory.glob('.meta-cnc.y*'):

            try:
                skillet = self.load_skillet_from_path(d)
                skillet_list.append(skillet)

            except SkilletNotFoundException:
                err_condition = f'Skillet not found in dir {d.name}'

            except SkilletLoaderException as sle:
                # for panhandler gl #19 - keep track of loader errors and associated directory
                err_dict = dict()
                err_dict['path'] = str(d.absolute())
                err_dict['error'] = str(sle)
                self.skillet_errors.append(err_dict)
                err_condition = f'Loader Error for dir {d.absolute()} - {sle}'

            except OSError as oe:
                # catch all OSErrors for #117
                err_dict = dict()
                err_dict['path'] = str(d.absolute())
                err_dict['error'] = str(oe)
                self.skillet_errors.append(err_dict)
                err_condition = f'OS Error for dir {d.absolute()} - {oe}'

        # Do not descend into sub dirs after a .meta-cnc file has already been found
        if skillet_list:
            return skillet_list

        if err_condition:
            logger.warning(err_condition)
            return skillet_list

        for d in directory.iterdir():

            if d.is_file():
                continue

            if '.git' in d.name:
                continue

            if '.venv' in d.name:
                continue

            if '.terraform' in d.name:
                continue

            if d.is_dir():
                skillet_list.extend(self._check_dir(d, list()))

        return skillet_list

    def load_skillets_from_git(self, repo_url, repo_name, repo_branch,
                               local_dir='~/.pan_cnc/skilletlib') -> List[Skillet]:

        return self.load_from_git(repo_url, repo_name, repo_branch, local_dir)

    def load_from_git(self, repo_url, repo_name, repo_branch, local_dir='~/.pan_cnc/skilletlib') -> List[Skillet]:
        """
        Performs a local clone of the given Git repository URL and returns a list of all found skillets defined
        therein.

        :param repo_url: Repository URL
        :param repo_name: name given to the repository
        :param repo_branch: branch to checkout
        :param local_dir: local directory where to clone the git repository into
        :return: List of Skillets
        """
        g = Git(repo_url, local_dir)
        d = g.clone(repo_name)
        g.branch(repo_branch)

        self.skillets = self.load_all_skillets_from_dir(d)
        return self.skillets

    def load_all_label_values(self, label_name: str) -> list:
        """
        Returns a list of label values defined across all snippets with a given label
        for example:

        labels:
            label_name: label_value

        will add 'label_value' to the list

        :param label_name: name of the label to search for
        :return: list of strings representing all found label values for given key
        """
        labels_list = list()
        for skillet in self.skillets:

            for label_key in skillet.labels:

                if label_key == label_name:

                    for label_list_value in skillet.labels[label_name]:

                        if label_list_value not in labels_list:
                            labels_list.append(label_list_value)

        return labels_list
