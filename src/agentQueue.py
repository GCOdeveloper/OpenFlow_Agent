"""
    Copyright 2023, University of Valladolid.
    
    Contributors: David de Pintos, Carlos Manuel Sangrador, Noemí Merayo

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

import queue

oltQueue = queue.Queue()

class OnuDisc:
    def __init__(self, intf_id, vendor_id, vendor_specific):
        self.intf_id = intf_id
        self.vendor_id = vendor_id
        self.vendor_specific = vendor_specific

class OnuInd:
    def __init__(self, intf_id, onu_id, oper_state, admin_state, fail_reason):
        self.intf_id = intf_id
        self.onu_id = onu_id
        self.oper_state = oper_state
        self.admin_state = admin_state
        self.fail_reason = fail_reason

class FlowStatsInd:
    def __init__(self, flow_id, rx_bytes, rx_packets, tx_bytes, tx_packets, timestamp):
        self.flow_id = flow_id
        self.rx_bytes = rx_bytes
        self.rx_packets = rx_packets
        self.tx_bytes = tx_bytes
        self.tx_packets = tx_packets
        self.timestamp = timestamp

class Flow:
    def __init__(self, cookie, command):
        self.flow_id = cookie
        self.flow_action = command

class QueueItem:
    def __init__(self, datapath_id, source, data):
        self.datapath_id = datapath_id
        self.source = source
        self.data = data

    def isClass(self, dataType):
        return dataType == self.data.__class__.__name__
