import logging
from collections import OrderedDict
from pathlib import Path
from typing import List

import oyaml
from yaml.constructor import ConstructorError
from yaml.error import YAMLError
from yaml.parser import ParserError
from yaml.reader import ReaderError
from yaml.scanner import ScannerError

from skilletlib import Panoply
from skilletlib.exceptions import SkilletLoaderException
from skilletlib.exceptions import SkilletNotFoundException
from skilletlib.remotes.git import Git
from skilletlib.skillet import PanValidationSkillet
from skilletlib.skillet import PanosSkillet
from skilletlib.skillet import Skillet
from skilletlib.skillet.workflow import WorkflowSkillet

logger = logging.getLogger(__name__)


class SkilletLoader:

    all_skillets = List[Skillet]

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
        if skillet_dict['type'] == 'panos' or skillet_dict['type'] == 'panorama':
            return PanosSkillet(skillet_dict)
        elif skillet_dict['type'] == 'pan_validation':
            return PanValidationSkillet(skillet_dict)
        else:
            return Skillet(skillet_dict)

    def _parse_skillet(self, path: (str, Path)) -> dict:
        if type(path) is str:
            path_str = path
            path_obj = Path(path)
        elif isinstance(path, Path):
            path_str = str(path)
            path_obj = path
        else:
            raise SkilletLoaderException(f'Invalid path type found in _parse_skillet!')

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
                skillet = self._normalize_skillet_structure(raw_service_config)
                skillet['snippet_path'] = snippet_path
                return skillet

        except IOError as ioe:
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
    def _normalize_skillet_structure(skillet: dict) -> dict:
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

        # verify snippets stanza is present and is a list
        if 'snippets' not in skillet:
            skillet['snippets'] = list()

        elif skillet['snippets'] is None:
            skillet['snippets'] = list()

        elif type(skillet['snippets']) is not list:
            skillet['snippets'] = list()

        return skillet

    def execute_panos_skillet(self, skillet: PanosSkillet, context: dict, panoply: Panoply) -> dict:
        """
        Executes the given PanosSkillet or PanValidationSkillet
        :param skillet: PanosSkillet
        :param context: dict containing all required variables for the given skillet
        :param panoply: Panoply PAN-OS object
        :return: modified context containing any captured outputs
        """

        context['config'] = panoply.get_configuration()

        for snippet in skillet.get_snippets():
            # render anything that looks like a jinja template in the snippet metadata
            # mostly useful for xpaths in the panos case
            metadata = snippet.render_metadata(context)
            # check the 'when' conditional against variables currently held in the context
            if snippet.should_execute(context):
                if snippet.cmd == 'validate':
                    logger.info(f'  Validating Snippet: {snippet.name}')
                    test = snippet.metadata['test']
                    logger.info(f'  Test is: {test}')
                    output = snippet.execute_conditional(test, context)
                    logger.info(f'  Validation results were: {output}')
                elif snippet.cmd == 'validate_xml':
                    logger.info(f'  Validating XML Snippet: {snippet.name}')
                    output = snippet.compare_element_at_xpath(context['config'], snippet.metadata['element'],
                                                              snippet.metadata['xpath'], context)
                elif snippet.cmd == 'parse':
                    logger.info(f'  Parsing Variable: {snippet.metadata["variable"]}')
                    output = context.get(snippet.metadata['variable'], '')
                else:
                    logger.info(f'  Executing Snippet: {snippet.name}')
                    # execute the command from the snippet definition and return the raw output
                    output = panoply.execute_cmd(snippet.cmd, metadata, context)
                # update the context with any captured outputs defined in the snippet metadata
                returned_output = snippet.capture_outputs(output)
                context.update(returned_output)

            else:
                # FIXME - we should possibly be able to bail out when a conditional fails
                fail_action = metadata.get('fail_action', 'skip')
                fail_message = metadata.get('fail_message', 'Aborted due to failed conditional!')
                if fail_action == 'skip':
                    logger.debug(f'  Skipping Snippet: {snippet.name}')
                else:
                    logger.debug('Conditional failed and found a fail_action')
                    logger.error(fail_message)
                    context['fail_message'] = fail_message
                    return context

        return context

    @staticmethod
    def execute_template_skillet(skillet: Skillet, context: dict) -> str:
        snippets = skillet.get_snippets()
        snippet = snippets[0]
        return snippet.template(context)

    def execute_workflow_skillet(self, skillet: WorkflowSkillet, context: dict, panoply: Panoply) -> (dict, str):
        """
        Executes a workflow skillet, executing each step in turn. If a template skillet is the last snippet step then
        return the rendered output from that template. Otherwise, return the combined context
        :param skillet: WorkflowSkillet to execute
        :param context: context containing all required variables and user-input for each snippet
        :param panoply: panoply class to access PAN-OS devices
        :return: Rendered template string or combined context if a template is not specified as the last step
        """

        snippets = skillet.get_snippets()
        num_snippets = len(snippets)
        count = 0
        for snippet in snippets:
            count += 1
            skillet_name = snippet.name
            skillet = self.get_skillet_with_name(skillet_name)

            if str(skillet.type).startswith('pan'):
                context = self.execute_panos_skillet(skillet, context, panoply)
            elif skillet.type == 'template':
                template_output = self.execute_template_skillet(skillet, context)
                if count == num_snippets:
                    return template_output
                else:
                    context[skillet_name] = template_output

            return context

    def get_skillet_with_name(self, skillet_name: str, reload=False):

        if not self.all_skillets:
            raise SkilletLoaderException('No Skillets have been loaded!')

        for skillet in self.all_skillets:
            if skillet.name == skillet_name:
                return skillet

        return None

    def load_all_skillets_from_dir(self, directory: (str, Path)) -> List[Skillet]:
        """
        Recursivly iterate through all sub-directories and locate all found skillets
        Returns a list of Loaded Skillets
        :param directory: parent directory in which to start iterating
        :return: list of skillets
        """
        if type(directory) is str:
            d = Path(directory)
        else:
            d = directory

        self.all_skillets = self._check_dir(d, list())
        return self.all_skillets

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
            except SkilletLoaderException:
                err_condition = f'Loader Error for dir {d.name}'

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

    def load_from_git(self, repo_url, repo_name, repo_branch, local_dir='~/.pan_cnc/skilletlib') -> List[Skillet]:
        g = Git(repo_url, local_dir)
        d = g.clone(repo_name)
        g.branch(repo_branch)

        self.all_skillets = self.load_all_skillets_from_dir(d)
        return self.all_skillets

