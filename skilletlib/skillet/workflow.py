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
    initialized = False

    snippet_required_metadata = {'name'}

    snippet_optional_metadata = {
        'include_by_tag': '',
        'include_by_name': '',
        'include_by_regex': '',
        'exclude_by_tag': '',
        'exclude_by_name': '',
        'exclude_by_regex': ''
    }

    def __init__(self, skillet_dict: dict, skillet_loader: SkilletLoader) -> None:
        self.skillet_loader = skillet_loader
        super().__init__(skillet_dict)

    def initialize_context(self, initial_context: dict) -> dict:
        self.initialized = True
        return super().initialize_context(initial_context)

    def get_snippets(self) -> List[WorkflowSnippet]:
        snippet_list = list()
        # chicken / egg avoidance
        if not self.initialized:
            return snippet_list

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
        # call get_snippet_results to flatten loop lists
        snippet_results = super()._get_snippet_results()

        # create out results dict for return
        results = dict()
        results['outputs'] = self.captured_outputs
        results['snippets'] = dict()

        # iterate through all the snippets from the called skillets
        for k, v in snippet_results['snippets'].items():
            # add them to the results dict
            results['snippets'][k] = v
            for ik, iv in snippet_results['snippets'][k]['raw'].items():
                if ik == 'snippets':
                    continue

                if isinstance(iv, dict):
                    if ik not in results:
                        results[ik] = dict()
                    results[ik].update(iv)
                else:
                    # this will overwrite non dict values ?
                    results[ik] = iv

        return self._parse_output_template(results)
