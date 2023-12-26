import subprocess
from .base import Snippet


class Python3Snippet(Snippet):
    """
    Basic Python3 Snippet Type
    """
    required_metadata = {'name', 'file'}

    def execute(self, context):
        """
        Execute a python3 snippet.

        :param context: The context used for python3 script execution
        :return: script output and tuple of success / failure
        """
        try:
            p3_exec = subprocess.run(['/usr/bin/env', 'python3', f'{self.skillet.path}/{self.file}'], check=True, capture_output=True)
            context['python3_output'] = p3_exec.stdout.decode('utf-8')
            return context['python3_output'], 'success'
        except subprocess.CalledProcessError:
            return '', 'failure'
