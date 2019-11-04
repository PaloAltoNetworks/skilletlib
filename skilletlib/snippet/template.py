from .base import Snippet


class TemplateSnippet(Snippet):
    """
    BaseSnippet implements a basic template object snippet
    """
    required_metadata = {'name', 'file'}

    def __init__(self, template_str, metadata):
        self.template_str = template_str
        self.rendered_template = ""
        super().__init__(metadata)

    def template(self, context) -> str:
        return self.render(self.template_str, context)

    def render(self, template_str, context) -> str:
        if not context:
            context = {}

        t = self._env.from_string(template_str)
        return t.render(context)
