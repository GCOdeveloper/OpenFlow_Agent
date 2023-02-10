#
# Copyright 2017 the original author or authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Omci message generator and parser implementation using scapy
"""

from external.omci.omci_frame import OmciFrame
from external.omci.omci_messages import *
from external.omci.omci_entities import *
from external.omci.omci_defs import ReasonCodes

def hexify(buffer):
    """
    Return a hexadecimal string encoding of input buffer
    """
    return ''.join('%02x' % ord(c) for c in buffer)

def omciError_to_str(omci_success):
    if omci_success == ReasonCodes.Success:
        return "Success"
    elif omci_success == ReasonCodes.ProcessingError:
        return "ProcessingError"
    elif omci_success == ReasonCodes.NotSupported:
        return "NotSupported"
    elif omci_success == ReasonCodes.ParameterError:
        return "ParameterError"
    elif omci_success == ReasonCodes.UnknownEntity:
        return "UnknownEntity"
    elif omci_success == ReasonCodes.UnknownInstance:
        return "UnknownInstance"
    elif omci_success == ReasonCodes.DeviceBusy:
        return "DeviceBusy"
    elif omci_success == ReasonCodes.InstanceExists:
        return "InstanceExists"
    elif omci_success == ReasonCodes.AttributeFailure:
        return "AttributeFailure"
    else:
        return "OperationCancelled"

