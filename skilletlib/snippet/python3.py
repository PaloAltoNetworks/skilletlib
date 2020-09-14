from .base import Snippet


class Python3Snippet(Snippet):
    """
    Basic Python3 Snippet Type
    """
    required_metadata = {'name', 'file'}

    def execute(self, context):
        """
        This is a stub function and is NOT currently implemented in skilletlib.

        :param context: The context used for python3 script execution
        :return: script output and tuple of success / failure
        """
        if 'python3_output' in context:
            # this is admittedly a hack to allow python3 skillets to be executed using other means in other tools
            # but still use output capturing, output_templates, etc from skilletlib. This is def a FIXME item
            return context['python3_output'], 'success'

        return '', 'success'
