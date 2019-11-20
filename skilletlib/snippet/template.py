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

    def render(self, template_str, context) -> str:
        if not context:
            context = {}

        t = self._env.from_string(template_str)
        return t.render(context)
