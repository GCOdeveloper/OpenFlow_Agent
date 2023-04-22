"""
    Copyright 2023, University of Valladolid.
    
    Contributors: Carlos Manuel Sangrador, David de Pintos, Noemí Merayo,
                  Alfredo Gonzalez, Miguel Campano.
    
    User Interface for GCOdeveloper/OpenFlow_Agent.

    This file is part of GCOdeveloper/OpenFlow_Agent.

    GCOdeveloper/OpenFlow_Agent is free software: you can redistribute it and/or 
    modify it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or (at your
    option) any later version.

    GCOdeveloper/OpenFlow_Agent is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
    more details.

    You should have received a copy of the GNU General Public License along with
    GCOdeveloper/OpenFlow_Agent. If not, see <https://www.gnu.org/licenses/>.
"""

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

