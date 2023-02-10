"""user-defined exceptions"""

class Error(Exception):
    """Base class for other exceptions"""
    pass

class NoInputError(Error):
    """Raised when there is not an input value"""
    pass

class WrongInputError(Error):
    """Raised when the input value is different from 'yes' or 'no'"""
    pass

class InputNotIntegerError(Error):
    """Raised when the input value is not in an integer"""
    pass

class ValueNotInRangeError(Error):
    """Raised when the input value is not in range"""
    pass

class PortOnuNotExistError(Error):
    """Raised when the input ONU port does not exist"""
    pass

