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

from typing import List

from skilletlib.skilletLoader import SkilletLoader
from skilletlib.snippet.workflow import WorkflowSnippet
from .base import Skillet


class WorkflowSkillet(Skillet):

    def __init__(self, skillet_dict: dict, skillet_loader: SkilletLoader) -> None:
        self.skillet_loader = skillet_loader
        super().__init__(skillet_dict)

    def get_snippets(self) -> List[WorkflowSnippet]:
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            skillet = self.skillet_loader.get_skillet_with_name(snippet_def['name'])
            snippet = WorkflowSnippet(snippet_def, skillet, self.skillet_loader)
            snippet_list.append(snippet)

        return snippet_list

    def get_results(self) -> dict:
        """
        format and return our outputs from this workflow. self.snippet_outputs will be the combined outputs
        from all the snippets from all the skillets that were executed. Any top level items added by each skillet
        will be added here as well.
        """
        results = dict()
        results['outputs'] = self.captured_outputs

        results['snippets'] = dict()
        for k, v in self.snippet_outputs.items():
            if k == 'skillets':
                results.update(v)
            else:
                results['snippets'][k] = v

        return results
