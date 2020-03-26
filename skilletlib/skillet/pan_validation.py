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

from pathlib import Path
from typing import List

from skilletlib.snippet.pan_validation import PanValidationSnippet
from .panos import PanosSkillet


# from .base import Skillet


class PanValidationSkillet(PanosSkillet):

    snippet_list = list()

    def get_snippets(self) -> List[PanValidationSnippet]:

        if len(self.snippet_list) > 0:
            return self.snippet_list

        snippet_path_str = self.skillet_dict['snippet_path']
        snippet_path = Path(snippet_path_str)
        snippet_list = list()
        for snippet_def in self.snippet_stack:
            if 'cmd' not in snippet_def:
                snippet_def['cmd'] = 'validate'
            elif snippet_def['cmd'] == 'validate_xml':
                snippet_def = self.load_element(snippet_def, snippet_path)
            elif snippet_def['cmd'] == 'set':
                snippet_def = self.load_element(snippet_def, snippet_path)

            if 'severity' not in snippet_def:
                snippet_def['severity'] = 'low'

            snippet = PanValidationSnippet(snippet_def, self.panoply)
            snippet_list.append(snippet)

        self.snippet_list = snippet_list
        return snippet_list

    def get_results(self) -> dict:
        # do not call super() as this subclasses panos and not base directly
        results = dict()
        results['snippets'] = dict()
        results['pan_validation'] = dict()
        context = self.context

        for s in self.get_snippets():
            snippet_name = s.name
            cmd = s.cmd
            # handle both validate and validate_xml here
            if snippet_name in context and 'validate' in cmd:
                if 'results' in context[snippet_name]:
                    result = context[snippet_name]['results']
                    label_template = context[snippet_name].get('label', '')
                    # attempt to render the label using supplied context
                    context[snippet_name]['label'] = s.render(label_template, context)
                    if not result:
                        fail_message = s.metadata.get('fail_message', 'Snippet Validation results were {{ result }}')
                        context[snippet_name]['output_message'] = s.render(fail_message, context)
                    elif result:
                        pass_message = s.metadata.get('pass_message', 'Snippet Validation results were {{ result }}')
                        context[snippet_name]['output_message'] = s.render(pass_message, context)
                    else:
                        context[snippet_name]['output_message'] = 'Unknown results from Snippet Validation'

                    results['snippets'][snippet_name] = result

                results['pan_validation'][snippet_name] = context[snippet_name]

        return results

