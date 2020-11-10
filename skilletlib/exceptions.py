class PanoplyException(BaseException):
    pass


class SkilletLoaderException(PanoplyException):
    pass


class SkilletNotFoundException(SkilletLoaderException):
    pass


class SnippetNotFoundException(SkilletLoaderException):
    pass


class VariableNotFoundException(SkilletLoaderException):
    pass


class SkilletValidationException(SkilletLoaderException):
    pass


class LoginException(PanoplyException):
    pass


class TargetLoginException(LoginException):
    pass


class TargetConnectionException(PanoplyException):
    pass


class TargetGenericException(PanoplyException):
    pass


class NodeNotFoundException(PanoplyException):
    pass


class SkilletExecutionException(PanoplyException):
    pass
