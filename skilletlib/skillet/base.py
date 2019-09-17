from collections import OrderedDict
from pathlib import Path
from typing import List

import oyaml
from yaml.error import YAMLError

from skilletlib.exceptions import SkilletLoaderException
from skilletlib.snippet.base import Snippet
import logging

logger = logging.getLogger(__name__)


class Skillet:

    def __init__(self, skillet_path):
        self.skillet_dict = self._parse_skillet(skillet_path)
        self.name = self.skillet_dict['name']
        self.snippet_stack = self.skillet_dict['snippets']
        self.type = self.skillet_dict['type']
        self.supported_versions = 'not implemented'
        self.variables = self.skillet_dict['variables']
        self.context = dict()

    def _parse_skillet(self, path: str) -> dict:
        if '.meta-cnc' in path:
            meta_cnc_file = Path(path)
            if not meta_cnc_file.exists():
                raise SkilletLoaderException('Could not find .meta-cnc file as this location')
        else:
            # we were only passed a directory like '.' or something, try to find a .meta-cnc.yaml or .meta-cnc.yml
            directory = Path(path).absolute()
            logger.debug(f'using directory {directory}')
            found_meta = False
            for filename in ['.meta-cnc.yaml', '.meta-cnc.yml', 'meta-cnc.yaml', 'meta-cnc.yml']:
                meta_cnc_file = directory.joinpath(filename)
                logger.debug(f'checking now {meta_cnc_file}')
                if meta_cnc_file.exists():
                    found_meta = True
                    break

            if not found_meta:
                raise SkilletLoaderException('Could not find .meta-cnc file at this location')

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

    def get_snippets(self) -> List[Snippet]:
        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet_file = snippet_path.joinpath(snippet_def['file'])
            if snippet_file.exists():
                with open(snippet_file, 'r') as sf:
                    snippet = Snippet(sf.read(), snippet_def)
                    snippet_list.append(snippet)

        return snippet_list

    def update_context(self, d: dict) -> dict:
        for var in self.variables:
            if var['name'] in d:
                self.context[var['name']] = d[var['name']]
            else:
                self.context[var['name']] = var['default']

        return self.context
