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
import copy
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

    SkilletLoader is used to find and load Skillets from their metadata files, either from the local filesystem
    or from a git repository URL

    :param path: local relative path to search for all Skillet meta-data files
    """

    # list loaded and compiled skillet objects
    skillets = List[Skillet]

    # list of loaded and compiled skillets from resolved git repositories
    resolved_skillets = List[Skillet]

    # list of errors encountered while loading all skillets
    skillet_errors = list()

    # tmp_dir where resolved git repositories will be cloned
    tmp_dir = '~./.skilletlib'

    # list of directories to skip and not recurse into
    skip_dirs = ['.terraform', '.git', '.venv', '.idea', '.tox', '.eggs']

    def __init__(self, path=None):

        self.skillets = list()
        self.resolved_skillets = list()

        debug = os.environ.get('SKILLET_DEBUG', False)

        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug('Debugging output enabled')

        if path is not None:
            self.load_all_skillets_from_dir(path)

    def load_skillet_dict_from_path(self, skillet_path: (str, Path)) -> dict:
        """
        Loads the skillet metadata file into a skillet_dict dictionary

        :param skillet_path: path in which to look for a metadata file
        :return: skillet dictionary
        """
        return self._parse_skillet(skillet_path)

    def load_skillet(self, skillet_path: str) -> Skillet:
        """
        Returns a Skillet object from the given path

        :param skillet_path: full path to the skillet YAML file
        :return: Skillet object
        """

        return self.load_skillet_from_path(skillet_path)

    def load_skillet_from_path(self, skillet_path: (str, Path)) -> Skillet:
        """
        Returns a Skillet object from the given path.

        :param skillet_path: path in which to search for a skillet
        :return: Skillet object of the correct type
        """
        skillet_dict = self._parse_skillet(skillet_path)

        skillet_path_object = Path(skillet_path)

        if self.__skillet_has_includes(skillet_dict):
            self.__resolve_submodule_skillets(skillet_path_object)
            self.__resolve_neighbor_skillets(skillet_dict['name'], skillet_path_object)

        compiled_skillet_dict = self.compile_skillet_dict(skillet_dict)
        return self.create_skillet(compiled_skillet_dict)

    def create_skillet(self, skillet_dict: dict) -> Skillet:
        """
        Creates a Skillet object from the given skillet definition

        :param skillet_dict: Dictionary loaded from the skillet.yaml definition file
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
            raise SkilletLoaderException(f'Unknown Skillet Type: {skillet_type}!')

    def _parse_skillet(self, path: (str, Path)) -> dict:
        """
        Parse the skillet metadata file from the Path and return a valid skillet definition dictionary

        :param path: relative PosixPath of a file to load and validate
        :return: skillet definition dictionary
        """

        if type(path) is str:
            path_str = path
            path_obj = Path(path)

        elif isinstance(path, Path):
            path_str = str(path)
            path_obj = path

        else:
            raise SkilletLoaderException('Invalid path type found in _parse_skillet!')

        if 'meta-cnc' in path_str or 'skillet.y' in path_str:
            meta_cnc_file = path_obj

            if not path_obj.exists():
                raise SkilletNotFoundException(f'Could not find skillet.yaml file as this location: {path}')

        else:
            # we were only passed a directory like '.' or something, try to find a skillet.yaml or .meta-cnc.yml
            directory = path_obj
            logger.debug(f'using directory {directory}')

            found_files = list()
            found_files.extend(directory.glob('.meta-cnc.y*'))
            found_files.extend(directory.glob('*skillet.y*'))

            if not found_files:
                raise SkilletNotFoundException('Could not find skillet definition file at this location')

            if len(found_files) > 1:
                logger.warning('Found more than 1 skillet file at this location! Using first file found!')

            meta_cnc_file = found_files[0]

        if meta_cnc_file is None:
            raise SkilletNotFoundException('Could not find skillet definition file at this location')

        snippet_path = str(meta_cnc_file.parent.absolute())
        skillet_file = str(meta_cnc_file.name)

        try:

            with meta_cnc_file.open(mode='r', encoding='utf-8') as sc:
                raw_service_config = oyaml.safe_load(sc.read())
                skillet = self.normalize_skillet_dict(raw_service_config)
                skillet['snippet_path'] = snippet_path
                skillet['skillet_path'] = snippet_path
                skillet['skillet_filename'] = skillet_file
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

    def __resolve_neighbor_skillets(self, skillet_name: str, skillet_path: Path) -> None:
        """
        Resolve all skillets in this directory that do not have the same name as skillet_name. This is useful
        when a user calls load_skillet_from_path and that skillet depends on another one in the same directory

        :param skillet_name: name of skillet to ignore
        :param skillet_path: directory to glob for all skillet definition files
        :return: None
        """

        if skillet_path.is_file():
            skillet_path = skillet_path.parent

        skillet_definitions = list()
        skillet_definitions.extend(skillet_path.glob('*.skillet.y*ml'))
        skillet_definitions.extend(skillet_path.glob('.meta-cnc.y*ml'))

        neighbor_skillets = list()

        for d in skillet_definitions:

            try:
                skillet = self.load_skillet_dict_from_path(d)
                if skillet['name'] != skillet_name:
                    neighbor_skillets.append(skillet)

            except SkilletLoaderException as sle:
                err_dict = dict()
                err_dict['path'] = str(d.absolute())
                err_dict['error'] = str(sle)
                self.skillet_errors.append(err_dict)
                logger.warning(f'Loader Error for dir {d.absolute()} - {sle}')

            except OSError as oe:
                err_dict = dict()
                err_dict['path'] = str(d.absolute())
                err_dict['error'] = str(oe)
                self.skillet_errors.append(err_dict)
                logger.warning(f'OS Error for dir {d.absolute()} - {oe}')

        for skillet_dict in neighbor_skillets:
            if not self.__skillet_has_includes(skillet_dict):
                # add found skillets to the resolved skillets list
                self.resolved_skillets.append(self.create_skillet(skillet_dict))

    def __resolve_submodule_skillets(self, path: Path) -> None:
        """
        Private method to find any submodule directories and load all found skillets
        into the resolved skillets list. This ensures that applications that call SkilletLoader.skillets
        will only get a list of skillets in the given repository and not all skillets from submodules as well.

        :param path: PosixPath to the path to check for submodules
        :return: None
        """

        git_root = None

        if path.is_file():
            path = path.parent

        all_parents = [path]
        all_parents.extend(path.parents)

        for p in all_parents:
            git_dir = p.joinpath('.git')
            if git_dir.exists():
                git_root = p
                break

        if not git_root:
            return

        is_subdir = True
        if git_root == path:
            is_subdir = False

        # create out git repo management object
        g = Git(repo_url=None)

        # get a list of all the submodule directories
        sm_dirs = g.get_submodule_dirs(git_root.absolute())
        for sm in sm_dirs:
            sm_path = git_root.joinpath(sm)
            if not sm_path.exists():
                continue

            # iterate each one and get a list of all found skillet definitions
            skillet_definitions = self._check_dir(sm_path, list())

            for skillet_dict in skillet_definitions:
                if not self.__skillet_has_includes(skillet_dict):
                    # add found skillets to the resolved skillets list
                    self.resolved_skillets.append(self.create_skillet(skillet_dict))

            if not is_subdir and sm not in self.skip_dirs:
                # now ensure our subsequent runs for check_dir skip this dir and NOT add these skillets to the
                # skillets list, note only do this if submodules exist at this directory level. Do not do this if
                # they were found in a parent
                self.skip_dirs.append(sm)

    def __resolve_git_dependencies(self, skillet: dict) -> None:
        """
        Private method to clone dependent git repository into the local temporary directory.
        All skillets found in these repositories will be created and added to the resolved_skillets list

        :param skillet: skillet definition dictionary
        :return: None
        """

        if 'depends' not in skillet:
            return None

        depends_list = skillet.get('depends', [])
        for depends in depends_list:
            cloned_skillets = self.load_skillet_dicts_from_git(depends['url'], depends['name'], depends['branch'],
                                                               self.tmp_dir)
            for cs in cloned_skillets:
                found_include = False
                for css in cs['snippets']:
                    if 'include' in css:
                        found_include = True

                if not found_include and 'depends' not in cs:
                    # we do not do recursive dependency resolution. Only index skillets with no dependencies
                    self.resolved_skillets.append(self.create_skillet(cs))

    @staticmethod
    def __skillet_has_includes(skillet_dict: dict) -> bool:
        """
        Simple utility method to check if a skillet has a snippet that includes another skillet. This is used
        as we do not do recursive dependency resolution. Only 1 level of dependencies are allowed, so this is
        used to determrine which set of skillets to load first. I.E. load only skillets with no dependencies first,
        then load the others.

        :param skillet_dict: Skillet definition dictionary object
        :return: boolean True if a snippet with an included skillet is found
        """

        for snippet in skillet_dict.get('snippets', []):
            if 'include' in snippet:
                return True

        return False

    @staticmethod
    def __propagate_snippet_metadata(parent: dict, child: dict) -> dict:
        """
        Propagate metadata attributes form a parent snippet to an included / child snippet.

        :param parent: snippet dict
        :param child: included snippet dict
        :return: copy of included snippet dict with metadata propagated.
        """

        # fix for #163 - ensure we use deepcopy to avoid modifying the origin snippet definition
        child_copy = copy.deepcopy(child)

        if 'tags' in parent:
            if 'tags' not in child_copy:
                child_copy['tags'] = list()

            child_copy['tags'].extend(parent['tags'])

        elif 'tag' in parent:
            if 'tag' not in child_copy:
                child_copy['tag'] = list()

            child_copy['tag'].extend(parent['tag'])

        attributes = ('when', 'label', 'documentation_link', 'description', 'pass_message', 'fail_message')
        for a in attributes:
            if a in parent:
                child_copy[a] = parent[a]

        return child_copy

    def compile_skillet_dict(self, skillet: dict) -> dict:
        """
        Compile the skillet dictionary including any included snippets from other skillets. Included snippets and
        variables will be inserted into the skillet dictionary and any replacements / updates to those snippets /
        variables will be made before hand.

        :param skillet: skillet definition dictionary
        :return: full compiled skillet definition dictionary
        """
        snippets = list()
        variables: list = skillet['variables']

        for snippet in skillet.get('snippets', []):

            if 'include' not in snippet:
                snippets.append(snippet)
                continue

            included_skillet: Skillet = self.get_skillet_with_name(snippet['include'], include_resolved_skillets=True)
            if included_skillet is None:
                raise SkilletLoaderException(f'Could not find included Skillet with name: {snippet["include"]}')

            if 'include_snippets' not in snippet and 'include_variables' not in snippet:
                # include all snippets by default
                for included_snippet in included_skillet.snippet_stack:
                    include_snippet_name = included_snippet['name']
                    propagated_snippet = self.__propagate_snippet_metadata(snippet, included_snippet)

                    # ensure the name is set properly
                    propagated_snippet['name'] = f'{included_skillet.name}.{include_snippet_name}'
                    snippets.append(propagated_snippet)

                for v in included_skillet.variables:
                    found_variable = False
                    for tv in skillet['variables']:
                        if tv['name'] == v['name']:
                            # do not add variable if one with the same name already exists
                            found_variable = True

                    if not found_variable:
                        # this variable does not exist in the skillet_dict variables, so add it here
                        variables.append(v)

            elif 'include_snippets' not in snippet:
                # include all snippets by default
                for included_snippet in included_skillet.snippet_stack:
                    include_snippet_name = included_snippet['name']
                    included_meta = self.__propagate_snippet_metadata(snippet, included_snippet)
                    included_meta['name'] = f'{included_skillet.name}.{include_snippet_name}'
                    snippets.append(included_meta)

            else:
                for include_snippet in snippet['include_snippets']:
                    include_snippet_name = include_snippet['name']
                    include_snippet_object = included_skillet.get_snippet_by_name(include_snippet_name)
                    include_meta = include_snippet_object.metadata
                    # the meta attribute in the metadata is a dict that we do not want to completely overwrite
                    if 'meta' in include_snippet:
                        include_snippet_object_meta = include_meta.get('meta', {})
                        if isinstance(include_snippet_object_meta, dict) and \
                                isinstance(include_snippet.get('meta', {}), dict):
                            new_meta = include_snippet_object_meta.copy()
                            new_meta.update(include_snippet.get('meta', {}))
                            include_snippet['meta'] = new_meta

                    # propagate everything form the parent if it's there
                    include_meta = self.__propagate_snippet_metadata(snippet, include_meta)

                    # update with locally defined options as well, if anyu
                    include_meta.update(include_snippet)

                    # ensure the name is set properly
                    include_meta['name'] = f'{included_skillet.name}.{include_snippet_name}'

                    snippets.append(include_meta)

            if 'include_variables' in snippet:
                if isinstance(snippet['include_variables'], str) and snippet['include_variables'] == 'all':
                    for v in included_skillet.variables:
                        found_variable = False
                        for tv in skillet['variables']:
                            if tv['name'] == v['name']:
                                # do not add variable if one with the same name already exists
                                found_variable = True

                        if not found_variable:
                            # this variable does not exist in the skillet_dict variables, so add it here
                            variables.append(v)
                elif isinstance(snippet['include_variables'], list):
                    for v in snippet['include_variables']:
                        # we need to include only the variables listed here and possibly update them with any
                        # new / modified attributes
                        included_variable_orig = included_skillet.get_variable_by_name(v['name'])

                        # #163 - always uses deepcopy when using includes / overrides
                        included_variable = copy.deepcopy(included_variable_orig)
                        # update this variable definition accordingly if necessary
                        included_variable.update(v)

                        # now check to see if this skillet has this variable already defined
                        found_variable = False
                        for ev in variables:
                            if ev['name'] == v['name']:
                                found_variable = True
                                # it is nonsensical to update the variable definition here from the included skillet
                                # just use what is defined locally, otherwise the builder should not have defined it
                                # here!
                                logger.info('not updating existing variable definition from '
                                            'the resolved skillet definition')

                        if not found_variable:
                            # this included variable was not defined locally, so go ahead and append the updated version
                            variables.append(included_variable)

        skillet['snippets'] = snippets
        skillet['variables'] = variables

        return skillet

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

        for snippet in skillet['snippets']:
            if not isinstance(snippet, dict):
                skillet['snippets'].remove(snippet)

            if 'include' in snippet:
                include_def = snippet['include']

                if not isinstance(include_def, str):
                    skillet['snippets'].remove(snippet)
                    logger.error(f'{skillet["name"]}: '
                                 'Removing invalid snippet definition: include is not a str')
                    continue

                if 'include_snippets' in snippet:
                    include_snippets_def = snippet['include_snippets']
                    if not isinstance(include_snippets_def, list):
                        skillet['snippets'].remove(snippet)
                        logger.error(f'{skillet["name"]}: Removing invalid snippet definition: include_snippets '
                                     'is not a list')
                        continue

                    for isd in include_snippets_def:
                        if not isinstance(isd, dict):
                            include_snippets_def.remove(isd)
                            logger.error(f'{skillet["name"]}: Removing invalid include_snippets definition: '
                                         'include_snippets item is not a dict')
                            continue

                        if 'name' not in isd:
                            include_snippets_def.remove(isd)
                            logger.error(f'{skillet["name"]}: Removing invalid include_snippets definition: '
                                         'include_snippets item requires a name attribute')
                            continue

                if 'include_variables' in snippet:
                    include_variables_def = snippet['include_variables']
                    if isinstance(include_variables_def, str):
                        if not include_variables_def == 'all':
                            skillet['snippets'].remove(snippet)
                            logger.error(f'{skillet["name"]}: Removing invalid snippet definition: '
                                         'include_variables must be all or list')
                            continue

                    elif isinstance(include_variables_def, list):
                        for ivd in include_variables_def:
                            if not isinstance(ivd, dict):
                                include_variables_def.remove(ivd)
                                logger.error(f'{skillet["name"]}: Removing invalid include_variables definition: '
                                             'include_variables item is not a dict')
                                continue

                            if 'name' not in ivd:
                                include_variables_def.remove(ivd)
                                logger.error(f'{skillet["name"]}: Removing invalid include_variables definition: '
                                             'include_variables item requires a name')
                                continue
                    else:
                        skillet['snippets'].remove(snippet)
                        logger.error(f'{skillet["name"]}: '
                                     'Removing invalid snippet definition: include_variables is not a list or all')
                        continue

            else:

                if 'include_snippets' in snippet:
                    skillet['snippets'].remove(snippet)
                    logger.error(f'{skillet["name"]}: '
                                 f'Removing invalid snippet definition: include_snippets requires an include attribute')
                    continue

                if 'include_variables' in snippet:
                    skillet['snippets'].remove(snippet)
                    logger.error(f'{skillet["name"]}: '
                                 'Removing invalid snippet definition: include_variables requires an include attribute')
                    continue

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

    def get_skillet_with_name(self, skillet_name: str, include_resolved_skillets=False) -> (Skillet, None):
        """
        Returns a single skillet from the loaded skillets list that has the matching 'name' attribute

        :param skillet_name: Name of the skillet to return
        :param include_resolved_skillets: boolean of whether to also check the resolved skillet list
        :return: Skillet or None
        """

        if not self.skillets and not self.resolved_skillets:
            raise SkilletLoaderException('No Skillets have been loaded!')

        for skillet in self.skillets:
            if skillet.name == skillet_name:
                return skillet

        # also check the resolved skillet list, which are skillets that are included from snippet includes
        if include_resolved_skillets:

            for skillet in self.resolved_skillets:
                if skillet.name == skillet_name:
                    return skillet

        return None

    def load_all_skillets_from_dir(self, directory: (str, Path)) -> List[Skillet]:
        """
        Recursively iterate through all sub-directories and locate all found skillets
        Returns a list of Loaded Skillets

        :param directory: parent directory in which to start iterating
        :return: list of Skillet objects
        """
        if type(directory) is str:
            d = Path(directory)

        else:
            d = directory

        # load skillets from submodules first into the resolved_skillets list
        # this will also add submodule directories to the 'skip_dirs' list so _check_dir will NOT
        # recurse into them and load them into the skillets list
        self.__resolve_submodule_skillets(d)

        # reset skillet errors list here
        self.skillet_errors = list()

        # keep a local list of all found skillet definitions as loaded from this directory
        skillet_definitions = self._check_dir(d, list())

        # keep a list of skillets that have been processed already to avoid duplicates
        processed_skillets = list()

        # go ahead and create Skillet Objects for any definition that does not have a dependency / includes
        for skillet_dict in skillet_definitions:
            found_include = False

            for snippet in skillet_dict.get('snippets', []):
                if 'include' in snippet:
                    found_include = True

            if not found_include:
                try:
                    self.skillets.append(self.create_skillet(skillet_dict))
                    processed_skillets.append(skillet_dict['name'])

                except SkilletLoaderException as sle:
                    err_dict = dict()
                    err_dict['path'] = skillet_dict.get('name', '')
                    err_dict['error'] = str(sle)
                    self.skillet_errors.append(err_dict)

        # now resolve deps for those that do inclusions
        for skillet_dict in skillet_definitions:
            if skillet_dict['name'] in processed_skillets:
                continue

            # do not yet pull down deps automatically. FIXME - need to signal to skilletlib that this operation is OK
            # self.__resolve_git_dependencies(skillet_dict)
            try:

                compiled_skillet = self.compile_skillet_dict(skillet_dict)
                self.skillets.append(self.create_skillet(compiled_skillet))

            except SkilletLoaderException as sle:
                err_dict = dict()
                err_dict['path'] = skillet_dict.get('name', '')
                err_dict['error'] = str(sle)
                self.skillet_errors.append(err_dict)

        return self.skillets

    def _check_dir(self, directory: Path, skillet_list: list) -> list:
        """
        Recursive method to look for all files in the current directory with a name matching '*skillet.yaml'
        or '.meta-cnc.y*' otherwise, iterate through all sub-dirs and skip dirs from the self.skip_dirs list
        will descend into all other dirs and call itself again.
        Returns a list of compiled skillets

        :param directory: PosixPath of directory to begin searching
        :param skillet_list: combined list of all skillet_dicts
        :return: list of Skillets
        """
        logger.debug(f'Checking dir: {directory}')
        err_condition = False

        skillet_definitions = list()
        skillet_definitions.extend(directory.glob('*.skillet.y*ml'))
        skillet_definitions.extend(directory.glob('.meta-cnc.y*ml'))

        for d in skillet_definitions:

            try:
                skillet = self.load_skillet_dict_from_path(d)
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

        if err_condition:
            logger.warning(err_condition)
            return skillet_list

        for d in directory.iterdir():

            if d.is_file():
                continue

            found_pattern = False
            for pattern in self.skip_dirs:
                # check if skip_dirs pattern == this directory name or if the pattern is a subdir type
                # like submodules/panos-config-elements, catch that here as well
                if pattern == d.name or str(d.absolute()).endswith(pattern):
                    found_pattern = True
                    break

            if found_pattern:
                continue

            if d.is_dir() and not d.is_symlink():
                skillet_list.extend(self._check_dir(d, list()))

        return skillet_list

    def load_skillets_from_git(self, repo_url, repo_name, repo_branch,
                               local_dir=None) -> List[Skillet]:
        """
        Performs a local clone of the given Git repository URL and returns a list of all found skillets defined
        therein.

        :param repo_url: Repository URL
        :param repo_name: name given to the repository
        :param repo_branch: branch to checkout
        :param local_dir: local directory where to clone the git repository into
        :return: List of Skillets
        """

        if local_dir is None:
            local_dir = self.tmp_dir

        return self.load_from_git(repo_url, repo_name, repo_branch, local_dir)

    def load_from_git(self, repo_url, repo_name, repo_branch, local_dir=None) -> List[Skillet]:
        """
        Performs a local clone of the given Git repository URL and returns a list of all found skillets defined
        therein.

        :param repo_url: Repository URL
        :param repo_name: name given to the repository
        :param repo_branch: branch to checkout
        :param local_dir: local directory where to clone the git repository into
        :return: List of Skillets
        """

        if local_dir is None:
            local_dir = self.tmp_dir

        skillet_definitions = self.load_skillet_dicts_from_git(repo_url, repo_name, repo_branch,
                                                               local_dir)

        skillets = list()
        for skillet_dict in skillet_definitions:
            skillets.append(self.create_skillet(skillet_dict))

        return skillets

    def load_skillet_dicts_from_git(self, repo_url, repo_name, repo_branch,
                                    local_dir=None) -> List[dict]:
        """
        Performs a local clone of the given Git repository URL and returns a list of all found skillet definition
        dictionaries defined therein.

        :param repo_url: Repository URL
        :param repo_name: name given to the repository
        :param repo_branch: branch to checkout
        :param local_dir: local directory where to clone the git repository into
        :return: List of Skillets
        """
        if local_dir is None:
            local_dir = self.tmp_dir

        g = Git(repo_url, local_dir)
        d = g.clone(repo_name)
        g.branch(repo_branch)

        return self._check_dir(Path(d), list())

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
