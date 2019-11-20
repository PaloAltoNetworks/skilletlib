from .base import Snippet


class Python3Snippet(Snippet):
    """
    Basic Python3 Snippet Type
    """
    required_metadata = {'name', 'file'}

    def execute(self, context):
        pass
