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

from skilletlib.snippet.base import Snippet
from skilletlib.snippet.python3 import Python3Snippet
from .base import Skillet


class Python3Skillet(Skillet):
    snippet_required_metadata = {'name', 'file'}

    def get_snippets(self) -> List[Snippet]:
        if hasattr(self, 'snippets'):
            return self.snippets

        snippet_list = list()
        for snippet_def in self.snippet_stack:
            snippet = Python3Snippet(snippet_def)
            snippet_list.append(snippet)

        return snippet_list
