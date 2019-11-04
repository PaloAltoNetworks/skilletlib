from .template import TemplateSnippet


class RestSnippet(TemplateSnippet):
    """
    Rest Snippet
    """
    required_metadata = {'name', 'path'}
