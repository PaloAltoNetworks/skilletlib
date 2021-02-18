from typing import Tuple

from jinja2.exceptions import TemplateError

from .base import Snippet


class TemplateSnippet(Snippet):
    """
    TemplateSnippet implements a basic template object snippet
    """
    required_metadata = {'name', 'file'}

    output_type = 'text'

    template_metadata = {'element'}
    optional_metadata = {
        'file': '',
        'element': '',
        'template_title': ''
    }

    def __init__(self, template_str, metadata):
        self.template_str = template_str
        self.rendered_template = ""
        super().__init__(metadata)

    def execute(self, context: dict) -> Tuple[str, str]:
        try:
            return self.render(self.template_str, context), 'success'

        except TemplateError as te:
            return str(te), 'failure'

    def template(self, context) -> str:
        try:
            o = self.execute(context)
            return o[0]
        except TemplateError as te:
            return str(te)


class SimpleTemplateSnippet(TemplateSnippet):
    """
    SimpleTemplate implements a snippet that requires only the template as a string to use
    """
    required_metadata = {'name'}

    def __init__(self, template_str):
        self.template_str = template_str
        self.rendered_template = ""

        metadata = {
            'name': 'SimpleTemplateSnippet',
        }

        super().__init__(template_str, metadata)
