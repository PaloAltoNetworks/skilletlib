from typing import Tuple

from .base import Snippet


class TemplateSnippet(Snippet):
    """
    BaseSnippet implements a basic template object snippet
    """
    required_metadata = {'name', 'file'}

    output_type = 'text'

    def __init__(self, template_str, metadata):
        self.template_str = template_str
        self.rendered_template = ""
        super().__init__(metadata)

    def execute(self, context: dict) -> Tuple[str, str]:
        return self.render(self.template_str, context), 'success'

    def template(self, context) -> str:
        return self.execute(context)[0]

    def handle_output_type_text(self, results):
        r = dict()
        r[self.name] = results
        return r


