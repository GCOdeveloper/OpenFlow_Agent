from pyof.v0x04.symmetric.hello import *
from pyof.v0x04.symmetric.echo_reply import *
from pyof.v0x04.asynchronous.packet_in import *
from pyof.v0x04.asynchronous.error_msg import ErrorMsg
from pyof.v0x04.asynchronous.error_msg import *
from pyof.v0x04.asynchronous.port_status import *
from pyof.v0x04.controller2switch import features_reply
from pyof.foundation.base import *
from pyof.foundation.basic_types import *
from pyof.v0x04.common.header import Header, Type
from pyof.v0x04.common.flow_match import *
from pyof.v0x04.common.flow_instructions import *
from pyof.v0x04.common.action import *
from pyof.v0x04.common.port import *
from pyof.v0x04.controller2switch.get_config_reply import *
from pyof.v0x04.controller2switch.features_reply import *
from pyof.v0x04.controller2switch.barrier_reply import *
from pyof.v0x04.controller2switch.role_reply import *
from pyof.v0x04.controller2switch.common import *
from pyof.v0x04.controller2switch.multipart_reply import *
from pyof.v0x04.controller2switch.multipart_request import *
from pyof.v0x04.controller2switch.flow_mod import *
from pyof.v0x04.controller2switch.meter_mod import *
import struct
import random
import string
import threading
import hashlib
import logging
import json
import os.path

from src.oltAdaptor import OLTadaptor
from external.omci.omci_entities import *
from external.omci.omci_defs import *
from src.onosAdaptor import ONOSAdaptor
from src.oltServices import InternetService, MulticastService, VoipService

from voltha_protos import tech_profile_pb2
from voltha_protos import openolt_pb2

class OLTDevice(OLTadaptor):

    def __init__(self, ip_address = "0.0.0.0", port = 9191, voip_extensions_start = 1111, voip_extensions_end = 9999):
        super().__init__(ip_address, port)

        self.n_buffers = 256
        self.n_tables = 2
        self.auxiliary_id = 0
        self.cap_flow_stats = True
        self.cap_table_stats = True
        self.cap_port_stats = False
        self.cap_group_stats = True
        self.cap_ip_reasm = False
        self.cap_queue_stats = False
        self.cap_port_blocked = False
        self.voip_extensions_start = voip_extensions_start
        self.voip_extensions_end = voip_extensions_end
        self.voip_netmask = "255.255.255.0"

        #self.ports = []
        self.onus = {}

        self.net_gemports = {} # dict(key(intf_id), value(gemport_id))
        self.olt_services = {} # dict(key(intf_id, onu_id, uni_id, service_type), values(dw_flow_id, up_flow_id, service))

        self.flow_ids_to_hash = {} # dict(key(hash_flow_id), values(list(flow_ids)))

    def generate(self):
        if (super().olt_connect()):
            self.datapath_id = "00:00:" + self.device_id
        else:
            self.datapath_id = ""

        return self.datapath_id

    def enable_olt(self):
        th = threading.Thread(target = super().enable_indications, args=(self.datapath_id,), daemon = True)
        th.start()

    def generate_capabilities(self):
        capabilities = 0

        if self.cap_port_blocked: capabilities = capabilities | 1 << 8

        if self.cap_queue_stats: capabilities = capabilities | 1 << 6

        if self.cap_ip_reasm: capabilities = capabilities | 1 << 5

        if self.cap_group_stats: capabilities = capabilities | 1 << 3

        if self.cap_port_stats: capabilities = capabilities | 1 << 2

        if self.cap_table_stats: capabilities = capabilities | 1 << 1

        if self.cap_flow_stats: capabilities = capabilities | 1

        return capabilities

    def enable_controller(self, ipONOS, portONOS):
        self.controller = ONOSAdaptor(ipONOS, portONOS)
        self.controller.connect()
        self.controller.OFPT_HELLO_msg()
        capabilities = self.generate_capabilities()

        th = threading.Thread(target = self.controller.recieve_packets, args=(self.datapath_id, self.n_buffers, self.n_tables, self.auxiliary_id, capabilities, self.hw_version, self.fw_version, self.serial_num), daemon = True)
        th.start()

    def initialize_onu(self, intf_id, vendor_id, vendor_specific):
        onu_sn = vendor_id.decode("utf-8") + vendor_specific.hex()[:8]
        onu_id = self.get_onu_id(intf_id, onu_sn)

        super().activate_onu(onu_id, intf_id, vendor_id, vendor_specific)
        #if success:
        #    port = DevicePort(onu_id, onu_sn)
        #    ports.append(port)

    def check_priorities(self, priorities, flowType, port_no = 0):
        if flowType == "multicast":
            intf_id = onu_id = uni_id = 0
            sr_type = flowType
        else:
            intf_id, onu_id, uni_id, POTS = self.portNo_to_onu(port_no)
            sr_type = "internet" if not POTS else "voip"

        service_key = (intf_id, onu_id, uni_id, sr_type)

        if service_key not in self.olt_services.keys():
            return True

        cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]

        if (flowType == "downstream" or flowType == "multicast") and cf_dw_flow is None:
            return True
        elif flowType == "upstream" and cf_up_flow is None:
            return True

        logging.warning("The ONU has already istalled a %s Service: ONU ID %d, interface %d, UNI ID %d",
                        flowType, onu_id, intf_id, uni_id)

        if flowType == "multicast":
            check = service.compare_priorities(priorities)
        else:
            check = service.compare_priorities(priorities, flowType)

        if check:
            # Remove previous service
            if flowType == "multicast":
                self.uninstall_MulticastService(service_key = service_key)
            elif flowType == "voip":
                self.uninstall_VoipService(service_key = service_key, direction = flowType)
            else:
                self.uninstall_InternetService(service_key = service_key, direction = flowType)
        else:
            return False

        return True

    #def check_InternetService_priorities(self, port_no, priorities, direction):
    #    intf_id, onu_id, uni_id = self.portNo_to_onu(port_no)
    #    service_key = (intf_id, onu_id, uni_id, "internet")

    #    if service_key not in self.olt_services.keys():
    #        return True

    #    cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]

    #    if direction == "downstream" and cf_dw_flow is None:
    #        return True
    #    elif direction == "upstream" and cf_up_flow is None:
    #        return True

    #    logging.warning("The ONU has already istalled a %s Internet Service: ONU ID %d, interface %d, UNI ID %d",
    #                    direction, onu_id, intf_id, uni_id)

    #    if service.compare_priorities(priorities, direction):
    #        # Remove previous service
    #        self.uninstall_InternetService(service_key = service_key, direction = direction)
    #    else:
    #        return False

    #    return True

    def generate_VoipService(self, port_no, priorities, s_tag = None, c_tag = None,
                             dw_meters_id = None, up_meters_id = None, voipConfig = {}):
        logging.info("PORT NO: %d", port_no)
        intf_id, onu_id, uni_id,_ = self.portNo_to_onu(port_no)
        service_key = (intf_id, onu_id, uni_id, "voip")
        cf_dw_flow = cf_up_flow = None

        if service_key in self.olt_services.keys():
            cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]
        else:
            service = VoipService(intf_id, onu_id, uni_id, port_no)
            service.add_voipServer(ipAddress = voipConfig["sipServer"], port = voipConfig["sipPort"])

        ext, passw = self.get_voipExtension(intf_id, onu_id, uni_id)


        if not service.extension_exists(ext, passw):
            userAddr = voipConfig["ipAddress"] if "ipAddress" in voipConfig else None
            userPort = voipConfig["rtpPort"] if "rtpPort" in voipConfig else None
            service.add_extension(ext, passw, ipAddress = userAddr, mask = self.voip_netmask,
                                  gateway = voipConfig["sipServer"], rtpPort = userPort)

        logging.info("PORT NO: %d", port_no)
        if s_tag is None:
            tag_type = "single_tag"
            dw_cmds = []
            up_cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None
        elif s_tag < 4096 and s_tag > 0:
            tag_type = "double_tag"
            dw_cmds = ["remove_outer_tag"]
            up_cmds = ["add_outer_tag"]
            classifier_o_vid = s_tag
            classifier_i_vid = c_tag
        else:
            tag_type = "single_tag"
            dw_cmds = []
            up_cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None

        if service.gemport_id is not None:
            GemPort = AllocID = service.gemport_id
        else:
            GemPort = AllocID = self.get_gemport_unicast(intf_id)

        if dw_meters_id is not None:
            dw_bw = self.controller.meterIds_to_bandwidth(dw_meters_id)
            if len(dw_bw) != 3:
                logging.error("Bandwidth meters don't found: ONU ID %d, interface %d, UNI ID %d", onu_id, intf_id, uni_id)
                return None

            service.update_servicePriorities(priorities, "downstream")

            service.add_traffic_sched(direction = tech_profile_pb2.Direction.DOWNSTREAM, priority = 0, cir = dw_bw["cir"], pir = dw_bw["pir"], pbs = dw_bw["pbs"])
            service.add_traffic_queue(direction = tech_profile_pb2.Direction.DOWNSTREAM, gemport_id = GemPort, priority = 0)

            service.generate_downstream_classifier(o_vid = classifier_o_vid, i_vid = classifier_i_vid, tag_type = tag_type)
            service.generate_downstream_action(cmds = dw_cmds)

        if up_meters_id is not None:
            up_bw = self.controller.meterIds_to_bandwidth(up_meters_id)
            if len(up_bw) != 3:
                logging.error("Bandwidth meters don't found: ONU ID %d, interface %d, UNI ID %d", onu_id, intf_id, uni_id)
                return None

            service.update_servicePriorities(priorities, "upstream")

            service.add_traffic_sched(direction = tech_profile_pb2.Direction.UPSTREAM, alloc_id = AllocID,
                                      additionalBW = tech_profile_pb2.AdditionalBW.AdditionalBW_BestEffort,
                                      priority = 0, cir = up_bw["cir"], pir = up_bw["pir"], pbs = up_bw["pbs"])
            service.add_traffic_queue(direction = tech_profile_pb2.Direction.UPSTREAM, gemport_id = GemPort, priority = 0)

            service.generate_upstream_classifier(o_vid = c_tag, tag_type = "single_tag")
            service.generate_upstream_action(o_vid = s_tag, cmds = up_cmds)

        self.olt_services[service_key] = (cf_dw_flow, cf_up_flow, service)

        return service_key

    def install_VoipService (self, service_key, up_flow_id = None, dw_flow_id = None):
        cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]
        direction = ""

        # Downstream Service
        if dw_flow_id is not None:
            if cf_dw_flow is not None:
                return False
            direction = "downstream"

            # Install TrafficSchedulers
            schedulers = service.get_downstream_trafficSchedulers()
            check = super().create_traffic_schedulers(schedulers)
            if not check:
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Queues
            dwQueues = service.get_downstream_trafficQueues()
            check = super().create_traffic_queues(dwQueues)
            if not check:
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False
            # Install Flows
            dw_flow = service.generate_downstream_flow(dw_flow_id)
            check = super().flow_add(dw_flow)
            if not check:
                super().flow_remove(dw_flow)
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

        # Upstream Service
        if up_flow_id is not None:
            if cf_up_flow is not None:
                return False
            direction = "upstream" if direction == "" else "bidirectional"

            # Install TrafficSchedulers
            schedulers = service.get_upstream_trafficSchedulers()
            check = super().create_traffic_schedulers(schedulers)
            if not check:
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Queues
            upQueues = service.get_upstream_trafficQueues()
            check = super().create_traffic_queues(upQueues)
            if not check:
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Flows
            up_flow = service.generate_upstream_flow(up_flow_id)
            check = super().flow_add(up_flow)
            if not check:
                super().flow_remove(up_flow)
                super().remove_traffic_queues(upQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

        if not cf_dw_flow and not cf_up_flow:
            install = True
        else:
            install = False

        check = self.omci_configure_VoipService(service_key, direction, install)

        if not dw_flow_id:
            dw_flow_id = cf_dw_flow

        if not up_flow_id:
            up_flow_id = cf_up_flow

        self.olt_services[service_key] = (dw_flow_id, up_flow_id, service)

        return True

    def uninstall_VoipService (self, service_key, direction):
        cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]

        if direction == "downstream":  # Downstream Service
            if cf_dw_flow is None:
                return True

            # Uninstall Flows
            dw_flow = service.generate_downstream_flow(cf_dw_flow)
            check = super().flow_remove(dw_flow)
            if not check:
                return False
            cf_dw_flow = None
            service.clean_downstream_flow()

            # Uninstall Queues
            dwQueues = service.get_downstream_trafficQueues()
            check = super().remove_traffic_queues(dwQueues)
            if not check:
                return False
            service.remove_traffic_queues(tech_profile_pb2.Direction.DOWNSTREAM)

            # Uninstall TrafficSchedulers
            schedulers = service.get_downstream_trafficSchedulers()
            check = super().remove_traffic_schedulers(schedulers)
            if not check:
                return False
            service.remove_traffic_schedulers(tech_profile_pb2.Direction.DOWNSTREAM)

        elif direction == "upstream":  # Upstream Service
            if cf_up_flow is None:
                return True
            # Uninstall Flows
            up_flow = service.generate_upstream_flow(cf_up_flow)
            check = super().flow_remove(up_flow)
            if not check:
                return False
            cf_up_flow = None
            service.clean_upstream_flow()

            # Uninstall Queues
            upQueues = service.get_upstream_trafficQueues()
            check = super().remove_traffic_queues(upQueues)
            if not check:
                return False
            service.remove_traffic_queues(tech_profile_pb2.Direction.UPSTREAM)

            # Uninstall TrafficSchedulers
            schedulers = service.get_upstream_trafficSchedulers()
            check = super().remove_traffic_schedulers(schedulers)
            if not check:
                return False
            service.remove_traffic_schedulers(tech_profile_pb2.Direction.UPSTREAM)

        if not cf_dw_flow and not cf_up_flow:
            delete = True
        else:
            delete = False
            self.olt_services[service_key] = (cf_dw_flow, cf_up_flow, service)

        check = self.omci_remove_VoipService(service_key, direction, delete)

        if not cf_dw_flow and not cf_up_flow:
            self.free_gemport(service.gemport_id, service.intf_id)
            self.olt_services.pop(service_key)

        return True

    def omci_configure_VoipService (self, service_key, direction, install = True):
        intf_id, onu_id, uni_id, service_type = service_key
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        alloc_id = gemport_id = service.gemport_id
        dw_cTag, up_cTag, _, _ = service.get_c_tags_configuration()
        if direction == "downstream":
            c_tag = dw_cTag
            x_cTag = up_cTag
        else:
            c_tag = up_cTag
            x_cTag = dw_cTag

        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        # GETTING IP HOST CONFIG DATA ID
        ip_hosts_ids = super().omci_get_entity_ids (intf_id, onu_id, IpHostConfigData.class_id)
        if len(ip_hosts_ids) == 0:
            logging.error("The ONU %d doesn't accept VoIP services", onu_id)
            return False

        ip_host_id = ip_hosts_ids[0]

        logging.debug("Configure OMCI entities: ONU ID %d, interface %d", onu_id, intf_id)
        # Configure OMCI
        if install:
            tcont_id, msg = super().configure_onu_allocID(intf_id, onu_id, alloc_id)
            if not tcont_id:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_gemPortNetworkCTP(intf_id, onu_id, gemport_id, tcont_id, 0)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_gemInterworkingTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_macBridgePortConfigurationData(intf_id, onu_id, gemport_id, "GEM_IW_TP")
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            # VOIP POTS CONFIGURATION
            check, msg = super().set_VoipConfigData (intf_id, onu_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().set_ipHostConfigData(intf_id, onu_id, ip_host_id,
                                                      ipAddress = service.extension.ipAddress,
                                                      mask = service.extension.mask,
                                                      gateway = service.extension.gateway,
                                                      primaryDNS = service.extension.primaryDNS,
                                                      secondaryDNS = service.extension.secondaryDNS)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_tcpUdpConfigData (intf_id, onu_id, entity_id = service.extension.rtpPort,
                                                          port = service.extension.rtpPort, ip_host_pointer = ip_host_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_extendedVlanTaggingOperationConfigurationData (intf_id, onu_id, ip_host_id, association_type = 3)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_VoiceServiceProfile (intf_id, onu_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_RtpProfileData (intf_id, onu_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_VoipMediaProfile (intf_id, onu_id, uni_id, uni_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_SipConfiguration (intf_id, onu_id, uni_id,
                                                          ipAddress = service.voipServer.ipAddress,
                                                          username = service.extension.extension,
                                                          password = service.extension.password,
                                                          primaryDNS = service.extension.primaryDNS,
                                                          secondaryDNS = service.extension.secondaryDNS,
                                                          tcp_udp_pointer = service.extension.rtpPort)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().configure_PotsUni (intf_id, onu_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_VoipVoiceCtp (intf_id, onu_id, uni_id,
                                                      sip_user_pointer = uni_id,
                                                      pptp_pointer = uni_id,
                                                      voip_profile_pointer = uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

        elif not install:
            check, msg = super().delete_vlanTaggingFilterData(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("****Deleted VLAN TAGGING FILTER DATA ID = %d", gemport_id)

        vlans = [(8, c_tag)]
        if x_cTag is not None and x_cTag > 0 and x_cTag != c_tag:
            vlans.append((8, x_cTag))

        check, msg = super().create_vlanTaggingFilterData(intf_id, onu_id, gemport_id, vlans)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug(msg)

        check, msg = super().update_extendedVlanTaggingOperationConfigurationData(intf_id, onu_id, ip_host_id, "single_tag",
                                                                                          tags_to_remove = 0,
                                                                                          inner_priority = 8,
                                                                                          inner_vid = c_tag)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug(msg)

        return True

    def omci_remove_VoipService (self, service_key, direction, delete = True):
        intf_id, onu_id, uni_id, service_type = service_key
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        alloc_id = gemport_id = service.gemport_id
        dw_cTag, up_cTag, _, _ = service.get_c_tags_configuration()
        if direction == "downstream":
            c_tag = dw_cTag
            x_cTag = up_cTag
        else:
            c_tag = up_cTag
            x_cTag = dw_cTag

        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        # GETTING IP HOST CONFIG DATA ID
        ip_hosts_ids = super().omci_get_entity_ids (intf_id, onu_id, IpHostConfigData.class_id)
        if len(ip_hosts_ids) == 0:
            logging.error("The ONU %d doesn't accept VoIP services", onu_id)
            return False

        ip_host_id = ip_hosts_ids[0]

        # Deconfiguring OMCI
        if delete or c_tag != x_cTag:
            check, msg = super().update_extendedVlanTaggingOperationConfigurationData(intf_id, onu_id, ip_host_id, "single_tag",
                                                                                              tags_to_remove = 0,
                                                                                              inner_priority = 8,
                                                                                              inner_vid = c_tag, delete = True)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: C TAG = %d", onu_id, intf_id, c_tag)

        check, msg = super().delete_vlanTaggingFilterData(intf_id, onu_id, gemport_id)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug("Deleted ONU ID %d, interface %d: VLAN TAGGING FILTER DATA ID = %d", onu_id, intf_id, gemport_id)

        if delete:
            ## VOIP ENTITIES
            check, msg = super().delete_omciEntity (intf_id, onu_id, ExtendedVlanTaggingOperationConfigurationData.class_id, ip_host_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: EXTENDED VLAN TAGGING OPER CONFIG DATA ID = %d", onu_id, intf_id, ip_host_id)

            check, msg = super().delete_omciEntity (intf_id, onu_id, VoipVoiceCtp.class_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: VOIP VOICE CTP ID = %d", onu_id, intf_id, uni_id)

            check, msg = super().delete_SipConfiguration (intf_id, onu_id, uni_id, service.extension.extension)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: SIP CONFIGURATION ID = %d", onu_id, intf_id, uni_id)

            check, msg = super().delete_omciEntity (intf_id, onu_id, VoipMediaProfile.class_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: VOIP MEDIA PROFILE ID = %d", onu_id, intf_id, uni_id)

            check, msg = super().delete_omciEntity (intf_id, onu_id, RtpProfileData.class_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: RTP PROFILE DATA ID = %d", onu_id, intf_id, uni_id)

            check, msg = super().delete_omciEntity (intf_id, onu_id, VoiceServiceProfile.class_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: VOICE SERVICE PROFILE ID = %d", onu_id, intf_id, uni_id)

            check, msg = super().delete_omciEntity (intf_id, onu_id, TcpUdpConfigData.class_id, service.extension.rtpPort)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: TCP/UDP CONFIG DATA ID = %d", onu_id, intf_id, service.extension.rtpPort)

            check, msg = super().set_ipHostConfigData(intf_id, onu_id, ip_host_id, delete = True)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            ## INTERNET ENTITIES
            check, msg = super().delete_macBridgePortConfigurationData(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: MAC BRIDGE PORT CONFIGURATION DATA ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemInterworkingTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM INTERWORKING TP ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemPortNetworkCTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM PORT NETWORK ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().deconfigure_onu_allocID(intf_id, onu_id, alloc_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: Alloc ID = %d", onu_id, intf_id, alloc_id)
        elif x_cTag is not None:
            check, msg = super().create_vlanTaggingFilterData(intf_id, onu_id, gemport_id, [(8, x_cTag)])
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("ONU ID %d, interface %d: VLAN TAGGING FILTER DATA ID = %d", onu_id, intf_id, gemport_id)

        return True

    def generate_InternetService(self, port_no, priorities, s_tag = None, c_tag = None, dw_meters_id = None, up_meters_id = None):
        logging.info("PORT NO: %d", port_no)
        intf_id, onu_id, uni_id,_ = self.portNo_to_onu(port_no)
        service_key = (intf_id, onu_id, uni_id, "internet")
        cf_dw_flow = cf_up_flow = None

        if service_key in self.olt_services.keys():
            cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]
        else:
            service = InternetService(intf_id, onu_id, uni_id, port_no)

        logging.info("PORT NO: %d", port_no)
        if s_tag is None:
            tag_type = "single_tag"
            dw_cmds = []
            up_cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None
        elif s_tag < 4096 and s_tag > 0:
            tag_type = "double_tag"
            dw_cmds = ["remove_outer_tag"]
            up_cmds = ["add_outer_tag"]
            classifier_o_vid = s_tag
            classifier_i_vid = c_tag
        else:
            tag_type = "single_tag"
            dw_cmds = []
            up_cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None

        if service.gemport_id is not None:
            GemPort = AllocID = service.gemport_id
        else:
            GemPort = AllocID = self.get_gemport_unicast(intf_id)

        if dw_meters_id is not None:
            dw_bw = self.controller.meterIds_to_bandwidth(dw_meters_id)
            if len(dw_bw) != 3:
                logging.error("Bandwidth meters don't found: ONU ID %d, interface %d, UNI ID %d", onu_id, intf_id, uni_id)
                return None

            service.update_servicePriorities(priorities, "downstream")

            service.add_traffic_sched(direction = tech_profile_pb2.Direction.DOWNSTREAM, priority = 0, cir = dw_bw["cir"], pir = dw_bw["pir"], pbs = dw_bw["pbs"])
            service.add_traffic_queue(direction = tech_profile_pb2.Direction.DOWNSTREAM, gemport_id = GemPort, priority = 0)

            service.generate_downstream_classifier(o_vid = classifier_o_vid, i_vid = classifier_i_vid, tag_type = tag_type)
            service.generate_downstream_action(cmds = dw_cmds)

        if up_meters_id is not None:
            up_bw = self.controller.meterIds_to_bandwidth(up_meters_id)
            if len(up_bw) != 3:
                logging.error("Bandwidth meters don't found: ONU ID %d, interface %d, UNI ID %d", onu_id, intf_id, uni_id)
                return None

            service.update_servicePriorities(priorities, "upstream")

            service.add_traffic_sched(direction = tech_profile_pb2.Direction.UPSTREAM, alloc_id = AllocID,
                                      additionalBW = tech_profile_pb2.AdditionalBW.AdditionalBW_BestEffort,
                                      priority = 0, cir = up_bw["cir"], pir = up_bw["pir"], pbs = up_bw["pbs"])
            service.add_traffic_queue(direction = tech_profile_pb2.Direction.UPSTREAM, gemport_id = GemPort, priority = 0)

            service.generate_upstream_classifier(o_vid = c_tag, tag_type = "single_tag")
            service.generate_upstream_action(o_vid = s_tag, cmds = up_cmds)

        self.olt_services[service_key] = (cf_dw_flow, cf_up_flow, service)

        return service_key

    def install_InternetService (self, service_key, up_flow_id = None, dw_flow_id = None):
        cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]
        direction = ""

        # Downstream Service
        if dw_flow_id is not None:
            if cf_dw_flow is not None:
                return False
            direction = "downstream"

            # Install TrafficSchedulers
            schedulers = service.get_downstream_trafficSchedulers()
            check = super().create_traffic_schedulers(schedulers)
            if not check:
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Queues
            dwQueues = service.get_downstream_trafficQueues()
            check = super().create_traffic_queues(dwQueues)
            if not check:
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False
            # Install Flows
            dw_flow = service.generate_downstream_flow(dw_flow_id)
            check = super().flow_add(dw_flow)
            if not check:
                super().flow_remove(dw_flow)
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

        # Upstream Service
        if up_flow_id is not None:
            if cf_up_flow is not None:
                return False
            direction = "upstream" if direction == "" else "bidirectional"

            # Install TrafficSchedulers
            schedulers = service.get_upstream_trafficSchedulers()
            check = super().create_traffic_schedulers(schedulers)
            if not check:
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Queues
            upQueues = service.get_upstream_trafficQueues()
            check = super().create_traffic_queues(upQueues)
            if not check:
                super().remove_traffic_queues(dwQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

            # Install Flows
            up_flow = service.generate_upstream_flow(up_flow_id)
            check = super().flow_add(up_flow)
            if not check:
                super().flow_remove(up_flow)
                super().remove_traffic_queues(upQueues)
                super().remove_traffic_schedulers(schedulers)
                return False

        if not cf_dw_flow and not cf_up_flow:
            install = True
        else:
            install = False

        check = self.omci_configure_InternetService(service_key, direction, install)

        if not dw_flow_id:
            dw_flow_id = cf_dw_flow

        if not up_flow_id:
            up_flow_id = cf_up_flow

        self.olt_services[service_key] = (dw_flow_id, up_flow_id, service)

        return True

    def uninstall_InternetService (self, service_key, direction):
        cf_dw_flow, cf_up_flow, service = self.olt_services[service_key]

        if direction == "downstream":  # Downstream Service
            if cf_dw_flow is None:
                return True

            # Uninstall Flows
            dw_flow = service.generate_downstream_flow(cf_dw_flow)
            check = super().flow_remove(dw_flow)
            if not check:
                return False
            cf_dw_flow = None
            service.clean_downstream_flow()

            # Uninstall Queues
            dwQueues = service.get_downstream_trafficQueues()
            check = super().remove_traffic_queues(dwQueues)
            if not check:
                return False
            service.remove_traffic_queues(tech_profile_pb2.Direction.DOWNSTREAM)

            # Uninstall TrafficSchedulers
            schedulers = service.get_downstream_trafficSchedulers()
            check = super().remove_traffic_schedulers(schedulers)
            if not check:
                return False
            service.remove_traffic_schedulers(tech_profile_pb2.Direction.DOWNSTREAM)

        elif direction == "upstream":  # Upstream Service
            if cf_up_flow is None:
                return True
            # Uninstall Flows
            up_flow = service.generate_upstream_flow(cf_up_flow)
            check = super().flow_remove(up_flow)
            if not check:
                return False
            cf_up_flow = None
            service.clean_upstream_flow()

            # Uninstall Queues
            upQueues = service.get_upstream_trafficQueues()
            check = super().remove_traffic_queues(upQueues)
            if not check:
                return False
            service.remove_traffic_queues(tech_profile_pb2.Direction.UPSTREAM)

            # Uninstall TrafficSchedulers
            schedulers = service.get_upstream_trafficSchedulers()
            check = super().remove_traffic_schedulers(schedulers)
            if not check:
                return False
            service.remove_traffic_schedulers(tech_profile_pb2.Direction.UPSTREAM)

        if not cf_dw_flow and not cf_up_flow:
            delete = True
        else:
            delete = False
            self.olt_services[service_key] = (cf_dw_flow, cf_up_flow, service)

        check = self.omci_remove_InternetService(service_key, direction, delete)

        if not cf_dw_flow and not cf_up_flow:
            self.free_gemport(service.gemport_id, service.intf_id)
            self.olt_services.pop(service_key)

        return True

    def omci_configure_InternetService (self, service_key, direction, install = True):
        intf_id, onu_id, uni_id, service_type = service_key
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        alloc_id = gemport_id = service.gemport_id
        dw_cTag, up_cTag, _, _ = service.get_c_tags_configuration()
        if direction == "downstream":
            c_tag = dw_cTag
            x_cTag = up_cTag
        else:
            c_tag = up_cTag
            x_cTag = dw_cTag

        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        logging.debug("Configure OMCI entities: ONU ID %d, interface %d", onu_id, intf_id)
        # Configure OMCI
        if install:
            tcont_id, msg = super().configure_onu_allocID(intf_id, onu_id, alloc_id)
            if not tcont_id:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_gemPortNetworkCTP(intf_id, onu_id, gemport_id, tcont_id, 0)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_gemInterworkingTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_macBridgePortConfigurationData(intf_id, onu_id, gemport_id, "GEM_IW_TP")
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)
        elif not install:
            check, msg = super().delete_vlanTaggingFilterData(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("****Deleted VLAN TAGGING FILTER DATA ID = %d", gemport_id)

        vlans = [(8, c_tag)]
        if x_cTag is not None and x_cTag > 0 and x_cTag != c_tag:
            vlans.append((8, x_cTag))

        check, msg = super().create_vlanTaggingFilterData(intf_id, onu_id, gemport_id, vlans)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug(msg)

        check, msg = super().update_extendedVlanTaggingOperationConfigurationData(intf_id, onu_id, uni_id, "single_tag",
                                                                                          tags_to_remove = 0,
                                                                                          inner_priority = 8,
                                                                                          inner_vid = c_tag)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug(msg)

        return True

    def omci_remove_InternetService (self, service_key, direction, delete = True):
        intf_id, onu_id, uni_id, service_type = service_key
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        alloc_id = gemport_id = service.gemport_id
        dw_cTag, up_cTag, _, _ = service.get_c_tags_configuration()
        if direction == "downstream":
            c_tag = dw_cTag
            x_cTag = up_cTag
        else:
            c_tag = up_cTag
            x_cTag = dw_cTag

        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        # Deconfiguring OMCI
        if delete or c_tag != x_cTag:
            check, msg = super().update_extendedVlanTaggingOperationConfigurationData(intf_id, onu_id, uni_id, "single_tag",
                                                                                              tags_to_remove = 0,
                                                                                              inner_priority = 8,
                                                                                              inner_vid = c_tag, delete = True)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: C TAG = %d", onu_id, intf_id, c_tag)

        check, msg = super().delete_vlanTaggingFilterData(intf_id, onu_id, gemport_id)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
            return False
        else:
            logging.debug("Deleted ONU ID %d, interface %d: VLAN TAGGING FILTER DATA ID = %d", onu_id, intf_id, gemport_id)

        if delete:
            check, msg = super().delete_macBridgePortConfigurationData(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: MAC BRIDGE PORT CONFIGURATION DATA ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemInterworkingTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM INTERWORKING TP ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemPortNetworkCTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM PORT NETWORK ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().deconfigure_onu_allocID(intf_id, onu_id, alloc_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: Alloc ID = %d", onu_id, intf_id, alloc_id)
        elif x_cTag is not None:
            check, msg = super().create_vlanTaggingFilterData(intf_id, onu_id, gemport_id, [(8, x_cTag)])
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("ONU ID %d, interface %d: VLAN TAGGING FILTER DATA ID = %d", onu_id, intf_id, gemport_id)

        return True

    def generate_MulticastService(self, group_id, priorities, meters_id, s_tag = None, c_tag = None):
        #intf_id, onu_id, uni_id = self.portNo_to_onu(port_no)
        service_key = (0, 0, 0, "multicast")
        cf_flow = None

        if service_key in self.olt_services.keys():
            cf_flow, _, service = self.olt_services[service_key]
        else:
            GemPort = self.get_gemport_multicast()
            service = MulticastService(group_id, GemPort)

        if s_tag is None:
            tag_type = "single_tag"
            cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None
        elif s_tag < 4096 and s_tag > 0:
            tag_type = "double_tag"
            cmds = ["remove_outer_tag"]
            classifier_o_vid = s_tag
            classifier_i_vid = c_tag
        else:
            tag_type = "single_tag"
            cmds = []
            classifier_o_vid = c_tag
            classifier_i_vid = None

        bw = self.controller.meterIds_to_bandwidth(meters_id)
        if len(bw) != 3:
            logging.error("Multicast bandwidth meters don't found: Group ID %d", group_id)
            return None

        service.update_servicePriorities(priorities)

        ports = self.controller.groupId_to_ports(group_id)

        for port_no in ports:
            intf_id, onu_id, uni_id,_ = self.portNo_to_onu(port_no)
            service.add_member(intf_id, onu_id, uni_id, port_no)

        service.add_traffic_sched(priority = 0, cir = bw["cir"], pir = bw["pir"], pbs = bw["pbs"])
        service.add_traffic_queue(priority = 0)

        service.generate_classifiers(o_vid = classifier_o_vid, i_vid = classifier_i_vid, tag_type = tag_type)
        service.generate_action(cmds = cmds)

        self.olt_services[service_key] = (cf_flow, None, service)

        return service_key

    def install_MulticastService (self, service_key, flow_id):
        cf_flow, _, service = self.olt_services[service_key]
        direction = "downstream"

        # Downstream Service
        if cf_flow is not None:
            return False

        # Creating groups
        group = service.get_Group()
        check = super().group_perform(group)
        if not check:
            super().group_remove(group)
            return False

        # Install TrafficSchedulers
        schedulers = service.get_traffic_schedulers()
        for sched in schedulers:
            check = super().create_traffic_schedulers(sched)
            if not check:
                super().remove_traffic_schedulers(sched)
                return False

        # Install Queues
        Queues = service.get_traffic_queues()
        for queue in Queues:
            check = super().create_traffic_queues(queue)
            if not check:
                super().remove_traffic_queues(queue)
                for sched in schedulers:
                    super().remove_traffic_schedulers(sched)
                return False

        # Install Flows
        flows = service.generate_flows(flow_id)
        for flow in flows:
            check = super().flow_add(flow)
            if not check:
                super().flow_remove(flow)
                for queue in Queues:
                    super().remove_traffic_queues(queue)
                for sched in schedulers:
                    super().remove_traffic_schedulers(sched)
                return False

        # Updating Group
        groupMembers = service.get_Group_members()
        check = super().group_perform(groupMembers)
        if not check:
            super().group_remove(group)
            return False

        #if not cf_flow:
        #    install = True
        #else:
        #    install = False

        check = self.omci_configure_MulticastService(service_key)

        self.olt_services[service_key] = (flow_id, None, service)

        return True

    def uninstall_MulticastService (self, service_key):
        cf_flow, _, service = self.olt_services[service_key]

        if cf_flow is None:
            return True

        # Uninstall Flows
        flows = service.generate_flows(cf_flow)
        for flow in flows:
            check = super().flow_remove(flow)
            if not check:
                return False
        cf_flow = None
        service.clean_flows()

        # Deleting Group
        group = service.get_Group_members()
        check = super().group_remove(group)
        if not check:
            return False
        service.remove_Group_members()

        # Uninstall Queues
        Queues = service.get_traffic_queues()
        for queue in Queues:
            check = super().remove_traffic_queues(queue)
            if not check:
                return False
        service.remove_traffic_queues()

        # Uninstall TrafficSchedulers
        schedulers = service.get_traffic_schedulers()
        for sched in schedulers:
            check = super().remove_traffic_schedulers(sched)
            if not check:
                return False
        service.remove_traffic_schedulers()

        check = self.omci_remove_MulticastService(service_key)

        self.free_gemport(service.gemport_id)
        self.olt_services.pop(service_key)

        return True

    def omci_configure_MulticastService (self, service_key):
        #intf_id, onu_id, uni_id, service_type = service_key
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        gemport_id = service.gemport_id
        c_tag,_ = service.get_tags_configuration()
        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        # Configure OMCI
        # Getting all the ports to configure
        ports = self.controller.groupId_to_ports(service.group_id)

        for port_no in ports:
            intf_id, onu_id, uni_id,_ = self.portNo_to_onu(port_no)

            logging.debug("Configure Multicast OMCI entities: ONU ID %d, interface %d", onu_id, intf_id)

            check, msg = super().create_gemPortNetworkCTP(intf_id, onu_id, gemport_id, 0, 0, 2)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_gemInterworkingTP(intf_id = intf_id, onu_id = onu_id, gemport_id = gemport_id, multicast = True)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_macBridgePortConfigurationData(intf_id, onu_id, gemport_id, "MC_GEM_IW_TP")
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            # MULTICAST ENTITIES
            check, msg = super().create_multicastOperationsProfile(intf_id, onu_id, gemport_id, (8, c_tag))
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

            check, msg = super().create_multicastSubscriberConfigInfo(intf_id, onu_id, uni_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug(msg)

        return True

    def omci_remove_MulticastService (self, service_key):
        service = self.olt_services[service_key][2]

        # Get OMCI parameters
        gemport_id = service.gemport_id
        c_tag,_ = service.get_tags_configuration()
        if c_tag is None:
            logging.error("Wrong VLAN on %s service", direction)
            return False

        # Deconfigure OMCI
        # Getting all the ports to remove
        ports = self.controller.groupId_to_ports(service.group_id)

        for port_no in ports:
            intf_id, onu_id, uni_id,_ = self.portNo_to_onu(port_no)

            check, msg = super().delete_multicastSubscriberConfigInfo(intf_id, onu_id, uni_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: MULTICAST SUBSCRIBER CONFIG INFO ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_multicastOperationsProfile(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: MULTICAST OPERATIONS PROFILE ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_macBridgePortConfigurationData(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: MAC BRIDGE PORT CONFIGURATION DATA ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemInterworkingTP(intf_id, onu_id, gemport_id, True)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM INTERWORKING TP ID = %d", onu_id, intf_id, gemport_id)

            check, msg = super().delete_gemPortNetworkCTP(intf_id, onu_id, gemport_id)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, msg)
                return False
            else:
                logging.debug("Deleted ONU ID %d, interface %d: GEM PORT NETWORK ID = %d", onu_id, intf_id, gemport_id)

        return True

    def create_ports (self, intf_id, onu_id, oper_state, admin_state):

        if (oper_state == "down" or admin_state == "down"):
            logging.error("ONU ID %d on interface %d in bad state.", onu_id, intf_id)
            return

        if not self.onu_exists(intf_id, onu_id):
            logging.error("ONU ID %d on interface %d not found.", onu_id, intf_id)
            return

        onu_sn = self.get_onu_sn(intf_id, onu_id)

        check = super().omci_onu_initialize(intf_id, onu_id)
        if not check:
            return

        logging.info("ONU ID %d on interface %d successfully activated", onu_id, intf_id)

        PyPath_TP_UNI_ids = super().omci_get_entity_ids(intf_id, onu_id, PptpEthernetUni.class_id)

        for PPTP in PyPath_TP_UNI_ids:
            TP_data = super().omci_update_entity_values(intf_id, onu_id, PptpEthernetUni, PPTP,
                                                     ("sensed_type", "operational_state", "config_ind"))
            MAC_data = super().omci_update_entity_values(intf_id, onu_id, MacBridgePortConfigurationData, PPTP, ("port_mac_address",))

            # Getting data for the Port creation
            port_no = self.onu_to_portNo(intf_id, onu_id, PPTP)
            hw_addr = MAC_data["port_mac_address"]
            name = onu_sn + "-" + str(PPTP & 0xff)
            config = 0
            state = PortState.OFPPS_LIVE if TP_data["operational_state"] == 0 else PortState.OFPPS_LINK_DOWN
            link_mode, curr_speed = self.configInd_to_OFPPF(TP_data["config_ind"])
            max_speed = self.sensedType_to_maxSpeed(TP_data["sensed_type"])

            devicePort = Port(port_no=port_no, hw_addr=hw_addr, name=name, config=config, state=state, curr=link_mode, advertised=link_mode,
                              supported=link_mode, peer=link_mode, curr_speed=curr_speed, max_speed=max_speed)

            self.controller.send_OFPT_PORT_STATUS(devicePort)

        PyPath_TP_POTS_ids = super().omci_get_entity_ids(intf_id, onu_id, PptpPotsUni.class_id)

        for PPTP in PyPath_TP_POTS_ids:
            TP_data = super().omci_update_entity_values(intf_id, onu_id, PptpPotsUni, PPTP,
                                                     ("operational_state", "hook_state"))

            # Getting data for the Port creation
            port_no = self.onu_to_portNo(intf_id, onu_id, PPTP, POTS = True)
            hw_addr = "00:00:00:00:00:00"
            name = onu_sn + "-" + str(PPTP & 0xff) + "P"
            config = 0
            state = PortState.OFPPS_LIVE if TP_data["operational_state"] == 0 else PortState.OFPPS_LINK_DOWN
            link_mode = curr_speed = 10000 if TP_data["hook_state"] == 0 else 0
            max_speed = 10000

            devicePort = Port(port_no=port_no, hw_addr=hw_addr, name=name, config=config, state=state, curr=link_mode, advertised=link_mode,
                              supported=link_mode, peer=link_mode, curr_speed=curr_speed, max_speed=max_speed)

            self.controller.send_OFPT_PORT_STATUS(devicePort)

        #onu_sn = self.get_onu_sn(intf_id, onu_id)
        #if onu_sn == "AZRS6f47f15e":
        #    port_no = self.onu_to_portNo(intf_id, onu_id, PyPath_TP_UNI_ids[3])
        #    self.testing_services (port_no = port_no)

    def sensedType_to_maxSpeed(self, sensed_type):
        if sensed_type == PluginUnitTypes.LAN_10BASE_T:
            return 10000
        elif sensed_type in (PluginUnitTypes.LAN_100BASE_T, PluginUnitTypes.LAN_10_100BASE_T):
            return 100000
        elif sensed_type == PluginUnitTypes.LAN_10_100_1000BASE_T:
            return 1000000
        elif sensed_type == PluginUnitTypes.LAN_10G_GBASE_T:
            return 10000000
        elif sensed_type == PluginUnitTypes.LAN_2_5GBASE_T:
            return 2500000
        elif sensed_type == PluginUnitTypes.LAN_5GBASE_T:
            return 5000000
        elif sensed_type == PluginUnitTypes.LAN_25GBASE_T:
            return 25000000
        elif sensed_type == PluginUnitTypes.LAN_40GBASE_T:
            return 40000000
        else:
            return 0

    def configInd_to_OFPPF(self, config_ind):

        if config_ind == PPTP_UNI_ConfigIndication.FD_10BASE_T:
            return (PortFeatures.OFPPF_10MB_FD | PortFeatures.OFPPF_COPPER), 10000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_100BASE_T:
            return (PortFeatures.OFPPF_100MB_FD | PortFeatures.OFPPF_COPPER), 100000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_GBIT_ETH:
            return (PortFeatures.OFPPF_1GB_FD | PortFeatures.OFPPF_COPPER), 1000000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_10GBIT_ETH:
            return (PortFeatures.OFPPF_10GB_FD | PortFeatures.OFPPF_COPPER), 10000000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_2_5GBIT_ETH:
            return (PortFeatures.OFPPF_OTHER | PortFeatures.OFPPF_COPPER), 2500000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_5GBIT_ETH:
            return (PortFeatures.OFPPF_OTHER | PortFeatures.OFPPF_COPPER), 5000000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_25GBIT_ETH:
            return (PortFeatures.OFPPF_OTHER | PortFeatures.OFPPF_COPPER), 25000000

        elif config_ind == PPTP_UNI_ConfigIndication.FD_40GBIT_ETH:
            return (PortFeatures.OFPPF_40GB_FD | PortFeatures.OFPPF_COPPER), 40000000

        elif config_ind == PPTP_UNI_ConfigIndication.HD_10BASE_T:
            return (PortFeatures.OFPPF_10MB_HD | PortFeatures.OFPPF_COPPER), 10000

        elif config_ind == PPTP_UNI_ConfigIndication.HD_100BASE_T:
            return (PortFeatures.OFPPF_100MB_HD | PortFeatures.OFPPF_COPPER), 100000

        elif config_ind == PPTP_UNI_ConfigIndication.HD_GBIT_ETH:
            return (PortFeatures.OFPPF_1GB_HD | PortFeatures.OFPPF_COPPER), 1000000

        else:
            return (PortFeatures.OFPPF_OTHER | PortFeatures.OFPPF_COPPER), 0

    def get_onu_id(self, intf_id, onu_sn):
        file = "subscribers.info"

        if (len(self.onus) == 0) and (os.path.exists(file)):
            with open(file) as fp:
                self.onus = json.load(fp)

        if onu_sn in self.onus:
            return self.onus[onu_sn][1]
        else:
            i = 1
            for onuId in sorted(self.onus.values()):
                if (onuId[0] != intf_id):
                    continue
                if onuId[1] > i:
                    break
                else:
                    i += 1
                    continue

            onu = [intf_id, i]
            self.onus[onu_sn] = onu
            
            with open(file, "w") as fp:
                json.dump(self.onus, fp, indent=4)

            return i

    def get_configured_voipExtensions(self):
        extensions = []

        for onu in self.onus.values():
            if len(onu) < 3:
                continue
            for port in onu[2].values():
                extensions.append(port[0])

        return extensions

    def generate_voipExtension(self, intf_id, onu_id, pots_id):
        file = "subscribers.info"
        onu_sn = self.get_onu_sn(intf_id, onu_id)

        ext = self.voip_extensions_start
        passw = ''
        for i in range(4):
            passw += random.choice(string.ascii_lowercase + string.digits)

        for extension in sorted(self.get_configured_voipExtensions()):
            if extension > ext:
                break
            ext += 1

        if ext > self.voip_extensions_end:
            return None, None

        block = [ext, passw]

        if len(self.onus[onu_sn]) < 3:
            self.onus[onu_sn].append({pots_id: block})
        else:
            self.onus[onu_sn][2].update({pots_id: block})

        with open(file, "w") as fp:
            json.dump(self.onus, fp, indent=4)

        return block


    def get_voipExtension(self, intf_id, onu_id, pots_id):
        ext = None
        passw = None

        for onu in self.onus.values():
            if onu[0] != intf_id or onu[1] != onu_id:
                continue
            if len(onu) < 3:
                break
            if str(pots_id) not in onu[2]:
                break

            return onu[2][str(pots_id)][0], onu[2][str(pots_id)][1]

        ext, passw = self.generate_voipExtension(intf_id, onu_id, pots_id)

        return ext, passw

    def get_onu_sn(self, intf_id, onu_id):
        for onu_item in self.onus.items():
            if onu_item[1][0] == intf_id and onu_item[1][1] == onu_id:
                return onu_item[0]

        return ""

    def onu_exists(self, intf_id, onu_id):
        for onu in self.onus.values():
            if onu[0] == intf_id and onu[1] == onu_id:
                return True

        return False

    def onu_to_portNo(self, intf_id, onu_id, PPTP, POTS = False):
        port_no = ((intf_id << 28) & 0xf0000000) | ((onu_id << 16) & 0x07ff0000) | (PPTP & 0x0000ffff)
        if POTS:
            port_no = port_no | 0x08000000

        return port_no

    def portNo_to_onu(self, port_no):
        intf_id = (port_no >> 28) & 0x0f
        onu_id = (port_no >> 16) & 0x07ff
        PPTP = port_no & 0xffff
        POTS = True if (port_no >> 27) & 0x01 == 1 else False

        return intf_id, onu_id, PPTP, POTS

    def get_gemport_unicast(self, intf_id):

        if intf_id not in self.net_gemports:
            self.net_gemports[intf_id] = [self.gemport_id_start]
            return self.gemport_id_start

        for Gport in range(self.gemport_id_start, self.alloc_id_end):
            if Gport not in self.net_gemports[intf_id]:
                self.net_gemports[intf_id].append(Gport)
                return Gport

        return None

    def get_gemport_multicast(self):
        if 0 not in self.net_gemports:
            self.net_gemports[0] = [self.gemport_id_mc_start]
            return self.gemport_id_mc_start

        for Gport in range(self.gemport_id_mc_start, self.gemport_id_end):
            if Gport not in self.net_gemports[0]:
                self.net_gemports[0].append(Gport)
                return Gport

        return None

    def free_gemport(self, gemport_id, intf_id = 0):
        if intf_id not in self.net_gemports:
            return

        if gemport_id not in self.net_gemports[intf_id]:
            return

        self.net_gemports[intf_id].remove(gemport_id)

    def get_Service_from_flow(self, flow_id):
        for key, value in self.olt_services.items():
            if value[0] == flow_id:
                return key, ("multicast" if key[3] == "multicast" else "downstream")
            elif  value[1] == flow_id:
                return key, "upstream"

        return None, None

    def remove_gemport_unicast(self, intf_id, gemport):
        if intf_id not in self.net_gemports:
            return

        self.net_gemports[intf_id].remove(gemport)

    def get_flowHash (self, flow_id):
        hash_list = []
        for ha in self.flow_ids_to_hash.items():
            if flow_id in ha[1]:
                hash_list.append(ha[0])

        return hash_list

    def configureFlows(self, flow_id, flow_action):

        if flow_action == FlowModCommand.OFPFC_ADD:
            serviceList = self.controller.matchFlows(flow_id)

            for service in serviceList:
                check = self.install_received_service(service)
                if not check:
                    self.controller.send_OFPT_ERROR_FLOW_MOD_FAILED(flow_id = flow_id)
                    self.controller.delete_flow(flow_id = flow_id)
                    self.controller.free_flowMod(flow_id = flow_id)
                    continue
                else:
                    self.controller.free_flowMod(flow_id = flow_id)

        elif flow_action == FlowModCommand.OFPFC_DELETE or flow_action == FlowModCommand.OFPFC_DELETE_STRICT:
            hash_flow_list = self.get_flowHash(flow_id)
            deleted = True
            deletedPorts = []

            for hashFlow in hash_flow_list:
                service_key, flowType = self.get_Service_from_flow(hashFlow)
                if service_key is None:
                    continue

                _,_,_,serType = service_key

                if serType == "multicast":
                    _, _, service = self.olt_services[service_key]
                    cf_ports = self.controller.groupId_to_ports(service.group_id)
                    check = self.uninstall_MulticastService(service_key = service_key)
                    if not check:
                        deleted = False
                        continue
                    for port_no in cf_ports:
                        deletedPorts.append({"port_no": port_no, "flowType": "downstream"})
                elif serType == "voip":
                    port_no = self.onu_to_portNo(service_key[0], service_key[1], service_key[2])

                    check = self.uninstall_VoipService(service_key = service_key, direction = flowType)
                    if not check:
                        deleted = False
                        continue
                    deletedPorts.append({"port_no": port_no, "flowType": flowType})
                else:
                    port_no = self.onu_to_portNo(service_key[0], service_key[1], service_key[2])

                    check = self.uninstall_InternetService(service_key = service_key, direction = flowType)
                    if not check:
                        deleted = False
                        continue
                    deletedPorts.append({"port_no": port_no, "flowType": flowType})

                self.flow_ids_to_hash.pop(hashFlow)

            if deleted:
                self.controller.delete_flow(flow_id = flow_id)

            serviceList = self.controller.matchPorts(deletedPorts)

            for service in serviceList:
                check = self.install_received_service(service)
                if not check:
                    self.controller.delete_flow(flow_id = flow_id)
                    continue

    def get_vlan_tags(self, vlanList, flowType):
        c_tag = None
        s_tag = None

        if len(vlanList) > 1:
            if flowType == "upstream":
                vlanList.reverse()

            for vl in vlanList:
                if vlanList[0] != vl and vl > 0:
                    c_tag = vl
                    break
            if c_tag is None:
                c_tag = vlanList[0]
                s_tag = None
            else:
                s_tag = vlanList[0]

        elif len(vlanList) == 1:
            s_tag = None
            c_tag = vlanList[0]
        else:
            return None, None

        return c_tag, s_tag

    def install_received_service(self, service):
        fmt = ""
        for i in service["flowIds"]:
            fmt += "L"

        flow_bytes = struct.pack(fmt, *(service["flowIds"]))
        hash_flow_id = int.from_bytes(hashlib.sha256(flow_bytes).digest()[:4], 'big')

        if len(service["meterIds"]) <= 0:
            logging.error("At least one Meter must be included")
            return False

        # VLAN management
        c_tag, s_tag = self.get_vlan_tags(service["vlans"], service["flowType"])
        if c_tag is None:
            logging.error("No VLANs found")
            return False

        flowType = "multicast" if service["serviceType"] == "multicast" else service["flowType"]
        port_no = 0 if service["serviceType"] == "multicast" else service["ONUport"]

        check = self.check_priorities(priorities = service["priorities"], flowType = flowType, port_no = port_no)
        if not check:
            logging.warning("The %s service to port %d flow ID %d, is not going to be installed.",
                            flowType, port_no, hash_flow_id)
            return True

        if service["serviceType"] == "unicast":
            check = self.installReceived_Internet(service, hash_flow_id, c_tag, s_tag)
            return check
        elif service["serviceType"] == "voip":
            check = self.installReceived_VoIP(service, hash_flow_id, c_tag, s_tag)
            return check
        elif service["serviceType"] == "multicast":
            check = self.installReceived_Multicast(service, hash_flow_id, c_tag, s_tag)
            return check

        return False

    def installReceived_Internet(self, service, hash_flow_id, c_tag, s_tag = None):
        port_no = service["ONUport"]

        logging.info("Internet Service found:")
        logging.info("****ONU port: %d", port_no)
        logging.info("****Priorities:")
        for i in service["priorities"]:
            logging.info("********Priority: %d", i)
        logging.info("****Type service: %s", service["flowType"])
        logging.info("****C_TAG: %d", c_tag)
        logging.info("****S_TAG: %d", s_tag or 0)
        logging.info("****Flows Hash: %d", hash_flow_id)
        logging.info("****Flow IDs:")
        for i in service["flowIds"]:
            logging.info("********Flow ID: %d", i)
        logging.info("****Meter IDs:")
        for i in service["meterIds"]:
            logging.info("********Meter ID: %d", i)

        if service["flowType"] == "downstream":
            upMeters = None
            upFlowHash = None
            downMeters = service["meterIds"]
            downFlowHash = hash_flow_id
        else:
            upMeters = service["meterIds"]
            upFlowHash = hash_flow_id
            downMeters = None
            downFlowHash = None

        service_key = self.generate_InternetService(port_no = port_no,
                                                    priorities = service["priorities"],
                                                    s_tag = s_tag,
                                                    c_tag = c_tag,
                                                    dw_meters_id = downMeters,
                                                    up_meters_id = upMeters)
        if service_key is None:
            logging.error("Wrong service received")
            return False

        check = self.install_InternetService (service_key = service_key,
                                      up_flow_id = upFlowHash,
                                      dw_flow_id = downFlowHash)
        if not check:
            logging.error("Failed to install %s service to port %d from flow %d.", service["flowType"], port_no, hash_flow_id)
            return False

        self.flow_ids_to_hash[hash_flow_id] = service["flowIds"]

        return True

    def installReceived_VoIP(self, service, hash_flow_id, c_tag, s_tag = None):
        port_no = service["ONUport"]

        logging.info("VoIP Service found:")
        logging.info("****ONU port: %d", port_no)
        logging.info("****Priorities:")
        for i in service["priorities"]:
            logging.info("********Priority: %d", i)
        logging.info("****Type service: %s", service["flowType"])
        logging.info("****C_TAG: %d", c_tag)
        logging.info("****S_TAG: %d", s_tag or 0)
        logging.info("****Flows Hash: %d", hash_flow_id)
        logging.info("****Flow IDs:")
        for i in service["flowIds"]:
            logging.info("********Flow ID: %d", i)
        logging.info("****Meter IDs:")
        for i in service["meterIds"]:
            logging.info("********Meter ID: %d", i)
        logging.info("****VoIP config:")
        logging.info("********SIP IP %s", service["voipConfig"]["sipServer"])
        logging.info("********SIP Port %d", service["voipConfig"]["sipPort"])
        if "rtpPort" in service["voipConfig"]:
            logging.info("********RTP Port %d", service["voipConfig"]["rtpPort"])

        if service["flowType"] == "downstream":
            upMeters = None
            upFlowHash = None
            downMeters = service["meterIds"]
            downFlowHash = hash_flow_id
        else:
            upMeters = service["meterIds"]
            upFlowHash = hash_flow_id
            downMeters = None
            downFlowHash = None

        service_key = self.generate_VoipService(port_no = port_no,
                                                priorities = service["priorities"],
                                                s_tag = s_tag,
                                                c_tag = c_tag,
                                                dw_meters_id = downMeters,
                                                up_meters_id = upMeters,
                                                voipConfig = service["voipConfig"])
        if service_key is None:
            logging.error("Wrong service received")
            return False

        check = self.install_VoipService (service_key = service_key,
                                      up_flow_id = upFlowHash,
                                      dw_flow_id = downFlowHash)
        if not check:
            logging.error("Failed to install %s service to port %d from flow %d.", service["flowType"], port_no, hash_flow_id)
            return False

        self.flow_ids_to_hash[hash_flow_id] = service["flowIds"]

        return True

    def installReceived_Multicast(self, service, hash_flow_id, c_tag, s_tag = None):
        group_id = service["groupId"]

        logging.info("Multicast Service found:")
        logging.info("****Group ID: %d", service["groupId"])
        logging.info("****Priorities:")
        for i in service["priorities"]:
            logging.info("********Priority: %d", i)
        logging.info("****Type service: multicast")
        logging.info("****C_TAG: %d", c_tag)
        logging.info("****S_TAG: %d", s_tag or 0)
        logging.info("****Flows Hash: %d", hash_flow_id)
        logging.info("****Flow IDs:")
        for i in service["flowIds"]:
            logging.info("********Flow ID: %d", i)
        logging.info("****Meter IDs:")
        for i in service["meterIds"]:
            logging.info("********Meter ID: %d", i)

        if service["flowType"] != "downstream":
            return False

        downMeters = service["meterIds"]
        downFlowHash = hash_flow_id

        service_key = self.generate_MulticastService(group_id = group_id,
                                                    priorities = service["priorities"],
                                                    meters_id = service["meterIds"],
                                                    s_tag = s_tag,
                                                    c_tag = c_tag)
        if service_key is None:
            logging.error("Wrong service received")
            return False

        check = self.install_MulticastService (service_key = service_key,
                                      flow_id = hash_flow_id)
        if not check:
            logging.error("Failed to install %s service to group %d from flow %d.", service["flowType"], group_id, hash_flow_id)
            return False

        self.flow_ids_to_hash[hash_flow_id] = service["flowIds"]

        return True

    def update_Flow_statistics(self, hash_flow_id, rx_bytes, rx_packets, tx_bytes, tx_packets, timestamp):

        for flow_id in self.flow_ids_to_hash[hash_flow_id]:
            self.controller.update_Flow_statistics(flow_id, tx_packets, tx_bytes, timestamp)
