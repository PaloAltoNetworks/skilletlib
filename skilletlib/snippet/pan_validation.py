from .panos import PanosSnippet


class PanValidationSnippet(PanosSnippet):
    """
    Pan validation Snippet
    """
    required_metadata = {'name'}
    # optional metadata that may be overridden in the snippet definition / metadata

    optional_metadata = {
        'fail_message': 'Snippet Validation Failed',
        'pass_message': 'Snippet Validation Passed'
    }

    def handle_output_type_validation(self, results: str):
        output = dict()
        output['results'] = results
        output['label'] = self.metadata.get('label', '')
        output['severity'] = self.metadata.get('severity', 'low')
        output['documentation_link'] = self.metadata.get('documentation_link', '')
        output['test'] = self.metadata.get('test', '')

        o = dict()
        o[self.name] = output
        return o
