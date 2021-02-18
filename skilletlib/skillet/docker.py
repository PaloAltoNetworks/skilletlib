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

from typing import List

from skilletlib.snippet.docker import DockerSnippet
from .base import Skillet


class DockerSkillet(Skillet):
    snippet_required_metadata = {'name', 'image', 'cmd'}

    # optional parameters that may be set in the snippet metadata
    snippet_optional_metadata = {
        'tag': 'latest',
        'volumes': dict(),
        'async': True
    }

    def __init__(self, s: dict):
        # grab the configured 'volumes' from the skillet app_data if present
        # note, this attribute can only be injected by the application and in the skillet definition file
        # also grab the working dir that should be used in the app, this will depend on any volumes that may be
        # passed in as well
        if 'app_data' in s and isinstance(s['app_data'], dict):
            self.volumes = s['app_data'].get('volumes', list())
            self.working_dir = s['app_data'].get('working_dir', '/app')
        else:
            self.volumes = list()
            self.working_dir = None

        super().__init__(s)

    def get_snippets(self) -> List[DockerSnippet]:

        if hasattr(self, 'snippets'):
            return self.snippets

        snippet_list = list()

        for snippet_def in self.snippet_stack:
            # self.path is set automatically in skillet/base.py
            # set skillet_path here for each skillet to have access to current path
            # this is needed for host directory mapping for volume mounts
            snippet_def['skillet_path'] = self.path

            if self.volumes:
                snippet_def['volumes'] = self.volumes
            else:
                snippet_def['volumes'] = list()

            # ensure working dir gets passed in as well...
            # prefer working set on the snippet metadata
            # then prefer
            working_dir = snippet_def.get('working_dir', None)

            if self.working_dir is not None:
                snippet_def['working_dir'] = self.working_dir

            elif working_dir is not None:
                snippet_def['working_dir'] = working_dir

            else:
                snippet_def['working_dir'] = '/app'

            snippet = DockerSnippet(snippet_def)
            snippet_list.append(snippet)

        return snippet_list

    def cleanup(self):
        for snippet in self.snippets:
            snippet.cleanup()
