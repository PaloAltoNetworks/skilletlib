class SkilletLoaderException(BaseException):
    pass


class SkilletNotFoundException(SkilletLoaderException):
    pass


class SkilletValidationException(BaseException):
    pass


class LoginException(BaseException):
    pass


class TargetLoginException(BaseException):
    pass


class TargetConnectionException(BaseException):
    pass


class TargetGenericException(BaseException):
    pass


class PanoplyException(BaseException):
    pass


class NodeNotFoundException(BaseException):
    pass


class SkilletExecutionException(BaseException):
    pass

