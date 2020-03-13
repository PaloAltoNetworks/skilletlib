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

    def __init__(self, s: dict):
        super().__init__(s)
        self.snippet_list = List[DockerSnippet]

        # grab the configured 'volumes' from the skillet app_data if present
        # note, this attribute can only be injected by the application and in the skillet definition file
        if 'app_data' in s and isinstance(s['app_data'], dict):
            if 'volumes' in s['app_data']:
                self.volumes = s['app_data']['volumes']

        else:
            self.volumes = list()

    def get_snippets(self) -> List[DockerSnippet]:
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

            snippet = DockerSnippet(snippet_def)
            snippet_list.append(snippet)

        self.snippet_list = snippet_list
        return self.snippet_list

    def cleanup(self):
        for snippet in self.snippet_list:
            snippet.cleanup()
