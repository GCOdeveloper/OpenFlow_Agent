# System imports
import logging
import random
from voltha_protos import openolt_pb2_grpc
from voltha_protos import openolt_pb2
from voltha_protos import tech_profile_pb2_grpc
from voltha_protos import tech_profile_pb2

class GenericService:
    nni_if = 0

    def __init__(self, intf_id, onu_id, uni_id, port_no, tech_profile_id = None):
        self.intf_id = intf_id
        self.onu_id = onu_id
        self.uni_id = uni_id
        self.port_no = port_no

        if tech_profile_id is not None:
            self.tech_profile_id = tech_profile_id
        else:
            self.tech_profile_id = random.randint(0, 32767)

        self._trafficSchedulers = tech_profile_pb2.TrafficSchedulers(intf_id=intf_id, onu_id=onu_id, uni_id=uni_id, port_no=port_no)
        self._trafficQueues = tech_profile_pb2.TrafficQueues(intf_id=intf_id, onu_id=onu_id, uni_id=uni_id, port_no=port_no, tech_profile_id = self.tech_profile_id)

        #self._flows = []

        self.gemport_id = None

    def add_traffic_sched(self, direction, alloc_id = None, additionalBW = 2, priority = None, weight = None, cir = None, pir = None, pbs = None):
        scheduler_config = tech_profile_pb2.SchedulerConfig(direction=direction, additional_bw=additionalBW, priority=priority, weight=weight)
        traffic_shaping = tech_profile_pb2.TrafficShapingInfo(cir=cir, pir=pir, pbs=pbs)

        sched = tech_profile_pb2.TrafficScheduler(
            direction=direction,
            alloc_id=alloc_id,
            scheduler=scheduler_config,
            traffic_shaping_info=traffic_shaping,
            tech_profile_id=self.tech_profile_id
        )

        self._trafficSchedulers.traffic_scheds.append(sched)

    def remove_traffic_schedulers(self, direction = tech_profile_pb2.Direction.BIDIRECTIONAL):
        for sched in iter(self._trafficSchedulers.traffic_scheds):
            if direction == tech_profile_pb2.Direction.BIDIRECTIONAL or sched.direction == direction:
                self._trafficSchedulers.traffic_scheds.remove(sched)

    def add_traffic_queue(self, direction, gemport_id = None, priority = None, weight = None):
        traffic_queue = tech_profile_pb2.TrafficQueue(
            direction = direction,
            gemport_id = gemport_id,
            priority = priority,
            weight = weight
        )

        self._trafficQueues.traffic_queues.append(traffic_queue)

        if gemport_id is not None:
            self.gemport_id = gemport_id

    def remove_traffic_queues(self, direction = tech_profile_pb2.Direction.BIDIRECTIONAL):
        for queue in iter(self._trafficQueues.traffic_queues):
            if direction == tech_profile_pb2.Direction.BIDIRECTIONAL or queue.direction == direction:
                self._trafficQueues.traffic_queues.remove(queue)

    def get_traffic_schedulers(self):
        if len(self._trafficSchedulers.traffic_scheds) == 0:
            return None

        return self._trafficSchedulers

    def get_downstream_trafficSchedulers(self):
        downScheds = tech_profile_pb2.TrafficSchedulers(intf_id=self.intf_id,
                                                        onu_id=self.onu_id,
                                                        uni_id=self.uni_id,
                                                        port_no=self.port_no)

        for s in iter(self._trafficSchedulers.traffic_scheds):
            if s.direction == tech_profile_pb2.Direction.DOWNSTREAM:
                downScheds.traffic_scheds.append(s)

        return downScheds

    def get_upstream_trafficSchedulers(self):
        upScheds = tech_profile_pb2.TrafficSchedulers(intf_id=self.intf_id,
                                                        onu_id=self.onu_id,
                                                        uni_id=self.uni_id,
                                                        port_no=self.port_no)

        for s in iter(self._trafficSchedulers.traffic_scheds):
            if s.direction == tech_profile_pb2.Direction.UPSTREAM:
                upScheds.traffic_scheds.append(s)

        return upScheds

    def get_traffic_queues(self):
        if len(self._trafficQueues.traffic_queues) == 0:
            return None

        return self._trafficQueues

    def get_downstream_trafficQueues(self):
        downQueues = tech_profile_pb2.TrafficQueues(intf_id=self.intf_id,
                                                    onu_id=self.onu_id,
                                                    uni_id=self.uni_id,
                                                    port_no=self.port_no,
                                                    tech_profile_id = self.tech_profile_id)

        for q in iter(self._trafficQueues.traffic_queues):
            if q.direction == tech_profile_pb2.Direction.DOWNSTREAM:
                downQueues.traffic_queues.append(q)

        return downQueues

    def get_upstream_trafficQueues(self):
        upQueues = tech_profile_pb2.TrafficQueues(intf_id=self.intf_id,
                                                  onu_id=self.onu_id,
                                                  uni_id=self.uni_id,
                                                  port_no=self.port_no,
                                                  tech_profile_id = self.tech_profile_id)

        for q in iter(self._trafficQueues.traffic_queues):
            if q.direction == tech_profile_pb2.Direction.UPSTREAM:
                upQueues.traffic_queues.append(q)

        return upQueues

    #def _direction_to_rpcDirection(self, direction):
    #    if direction == "upstream":
    #        return tech_profile_pb2.Direction.UPSTREAM
    #    elif direction == "downstream":
    #        return tech_profile_pb2.Direction.DOWNSTREAM
    #    else:
    #        return tech_profile_pb2.Direction.BIDIRECTIONAL

class InternetService(GenericService):

    def __init__(self, intf_id, onu_id, uni_id, port_no):
        super().__init__(intf_id, onu_id, uni_id, port_no)

        self.dwClassifier = openolt_pb2.Classifier()
        self.dwAction = openolt_pb2.Action()

        self.upClassifier = openolt_pb2.Classifier()
        self.upAction = openolt_pb2.Action()

        self.downstream_flow_id = 0
        self.upstream_flow_id = 0

        self.dwPriorities = []
        self.upPriorities = []

    def update_servicePriorities (self, priorities, p_type = "bidirectional"):
        if p_type == "downstream":
            self.dwPriorities = priorities
        elif p_type == "upstream":
            self.upPriorities = priorities
        else:
            self.dwPriorities = priorities
            self.upPriorities = priorities

    def compare_priorities(self, priorities, p_type = "bidirectional"):
        if p_type == "downstream":
            for i in range(0, min(len(priorities), len(self.dwPriorities))):
                if priorities[i] > self.dwPriorities[i]:
                    return True
                elif priorities[i] < self.dwPriorities[i]:
                    return False
        if p_type == "upstream":
            for i in range(0, min(len(priorities), len(self.upPriorities))):
                if priorities[i] > self.upPriorities[i]:
                    return True
                elif priorities[i] < self.upPriorities[i]:
                    return False
        else:
            for i in range(0, min(len(priorities), len(self.dwPriorities), len(self.upPriorities))):
                if priorities[i] > self.upPriorities[i] and priorities[i] > self.dwPriorities[i]:
                    return True
                elif priorities[i] < self.upPriorities[i] and priorities[i] < self.dwPriorities[i]:
                    return False

        return False

    def generate_downstream_classifier(self, o_vid = None, i_vid = None, o_pbits = None, eth_type = None,
                                       dst_mac = None, ip_proto = None, src_port = None, dst_port = None, tag_type = None):
        self.dwClassifier = openolt_pb2.Classifier(
            o_vid = o_vid,
            i_vid = i_vid,
            o_pbits = o_pbits,
            eth_type = eth_type,
            dst_mac = dst_mac,
            ip_proto = ip_proto,
            src_port = src_port,
            dst_port = dst_port,
            pkt_tag_type = tag_type
        )

    def generate_upstream_classifier(self, o_vid = None, i_vid = None, o_pbits = None, eth_type = None,
                                       dst_mac = None, ip_proto = None, src_port = None, dst_port = None, tag_type = None):
        self.upClassifier = openolt_pb2.Classifier(
            o_vid = o_vid,
            i_vid = i_vid,
            o_pbits = o_pbits,
            eth_type = eth_type,
            dst_mac = dst_mac,
            ip_proto = ip_proto,
            src_port = src_port,
            dst_port = dst_port,
            pkt_tag_type = tag_type
        )

    def generate_downstream_action(self, o_vid = None, o_pbits = None, i_vid = None, i_pbits = None, cmds = []):
        self.dwAction = openolt_pb2.Action(
            o_vid = o_vid,
            o_pbits = o_pbits,
            i_vid = i_vid,
            i_pbits = i_pbits
        )

        if "add_outer_tag" in cmds:
            self.dwAction.cmd.add_outer_tag = True

        if "remove_outer_tag" in cmds:
            self.dwAction.cmd.remove_outer_tag = True

        if "add_inner_tag" in cmds:
            self.dwAction.cmd.add_inner_tag = True

        if "remove_inner_tag" in cmds:
            self.dwAction.cmd.remove_inner_tag = True

        if "translate_outer_tag" in cmds:
            self.dwAction.cmd.translate_outer_tag = True

        if "translate_inner_tag" in cmds:
            self.dwAction.cmd.translate_inner_tag = True

    def generate_upstream_action(self, o_vid = None, o_pbits = None, i_vid = None, i_pbits = None, cmds = []):
        self.upAction = openolt_pb2.Action(
            o_vid = o_vid,
            o_pbits = o_pbits,
            i_vid = i_vid,
            i_pbits = i_pbits
        )

        if "add_outer_tag" in cmds:
            self.upAction.cmd.add_outer_tag = True

        if "remove_outer_tag" in cmds:
            self.upAction.cmd.remove_outer_tag = True

        if "add_inner_tag" in cmds:
            self.upAction.cmd.add_inner_tag = True

        if "remove_inner_tag" in cmds:
            self.upAction.cmd.remove_inner_tag = True

        if "translate_outer_tag" in cmds:
            self.upAction.cmd.translate_outer_tag = True

        if "translate_inner_tag" in cmds:
            self.upAction.cmd.translate_inner_tag = True


    def generate_downstream_flow(self, flow_id):
        if len(self.dwPriorities) == 0:
            return None

        dw_Cvlan, up_Cvlan, dw_Svlan, up_Svlan = self.get_c_tags_configuration()
        logging.info("VLANS Downstream: C_tag: %d, S_tag: %d", dw_Cvlan, dw_Svlan)
        logging.info("VLANS Upstream: C_tag: %d, S_tag: %d", up_Cvlan, up_Svlan)
        if dw_Cvlan == up_Cvlan and ((dw_Svlan is None and up_Svlan is None) or dw_Svlan == up_Svlan):
            symetricFlow = self.upstream_flow_id
        else:
            symetricFlow = 0

        logging.info("Symetric Flow ID: %d", symetricFlow)
        logging.info("Port NO: %d", self.port_no)

        dwFlow = openolt_pb2.Flow(
            access_intf_id = self.intf_id,
            onu_id = self.onu_id,
            uni_id = self.uni_id,
            flow_id = flow_id,
            symmetric_flow_id = symetricFlow,
            flow_type = "downstream",
            network_intf_id = self.nni_if,
            gemport_id = self.gemport_id,
            classifier = self.dwClassifier,
            action = self.dwAction,
            priority = self.dwPriorities[0],
            cookie = flow_id,
            port_no = self.port_no,
            tech_profile_id = self.tech_profile_id
        )

        self.downstream_flow_id = flow_id

        return dwFlow

    def clean_downstream_flow(self):
        self.downstream_flow_id = 0

    def generate_upstream_flow(self, flow_id):
        if len(self.upPriorities) == 0:
            return None

        dw_Cvlan, up_Cvlan, dw_Svlan, up_Svlan = self.get_c_tags_configuration()
        logging.info("VLANS Downstream: C_tag: %d, S_tag: %d", dw_Cvlan, dw_Svlan)
        logging.info("VLANS Upstream: C_tag: %d, S_tag: %d", up_Cvlan, up_Svlan)
        if dw_Cvlan == up_Cvlan and ((dw_Svlan is None and up_Svlan is None) or dw_Svlan == up_Svlan):
            symetricFlow = self.downstream_flow_id
        else:
            symetricFlow = 0

        logging.info("Symetric Flow ID: %d", symetricFlow)
        logging.info("Port NO: %d", self.port_no)

        upFlow = openolt_pb2.Flow(
            access_intf_id = self.intf_id,
            onu_id = self.onu_id,
            uni_id = self.uni_id,
            flow_id = flow_id,
            symmetric_flow_id = symetricFlow,
            flow_type = "upstream",
            network_intf_id = self.nni_if,
            gemport_id = self.gemport_id,
            classifier = self.upClassifier,
            action = self.upAction,
            priority = self.upPriorities[0],
            cookie = flow_id,
            port_no = self.port_no,
            tech_profile_id = self.tech_profile_id
        )

        self.upstream_flow_id = flow_id

        return upFlow

    def clean_upstream_flow(self):
        self.upstream_flow_id = 0

    def get_c_tags_configuration(self):
        dw_s_tag = self.dwClassifier.o_vid if self.dwClassifier.i_vid > 0 else 0
        up_s_tag = self.upAction.o_vid

        dw_c_tag = self.dwClassifier.i_vid if dw_s_tag > 0 else self.dwClassifier.o_vid
        up_c_tag = self.upClassifier.o_vid

        return dw_c_tag, up_c_tag, dw_s_tag, up_s_tag

class MulticastMember(GenericService):
    def __init__(self, intf_id, group_id):
        super().__init__(intf_id, 0, 0, 0, group_id)

        self.Classifier = openolt_pb2.Classifier()

        self.flow_id = 0
        self.group_id = group_id

    def generate_classifier(self, o_vid = None, i_vid = None, o_pbits = None, eth_type = None,
                                       dst_mac = None, ip_proto = None, src_port = None, dst_port = None, tag_type = None):
        self.Classifier = openolt_pb2.Classifier(
            o_vid = o_vid,
            i_vid = i_vid,
            o_pbits = o_pbits,
            eth_type = eth_type,
            dst_mac = dst_mac,
            ip_proto = ip_proto,
            src_port = src_port,
            dst_port = dst_port,
            pkt_tag_type = tag_type
        )

    def generate_flow(self, flow_id, priority, gem_port):
        Flow = openolt_pb2.Flow(
            access_intf_id = self.intf_id,
            onu_id = 0,
            uni_id = 0,
            flow_id = flow_id,
            symmetric_flow_id = 0,
            flow_type = "multicast",
            network_intf_id = self.nni_if,
            gemport_id = gem_port,
            classifier = self.Classifier,
            priority = priority,
            cookie = flow_id,
            port_no = 0,
            group_id = self.group_id,
            tech_profile_id = self.tech_profile_id
        )

        self.flow_id = flow_id

        return Flow

    def clean_flow(self):
        self.flow_id = 0

    def get_tags_configuration(self):
        s_tag = self.Classifier.o_vid if self.Classifier.i_vid > 0 else 0
        c_tag = self.Classifier.i_vid if s_tag > 0 else self.Classifier.o_vid

        return c_tag, s_tag

class MulticastGroup(list):
    def __init__(self, group_id, gemport_id):
        super().__init__()
        self.group_id = group_id
        self.gemport_id = gemport_id

        self.Action = openolt_pb2.Action()

    def add_member(self, intf_id):
        if not self.exists_GroupMember(intf_id):
            member = openolt_pb2.GroupMember(interface_id = intf_id, interface_type = openolt_pb2.GroupMember.InterfaceType.PON,
                                             gem_port_id = self.gemport_id, priority = 0)
            self.append(member)

    def remove_Group_members(self):
        self.clear()

    def generate_action(self, o_vid = None, o_pbits = None, i_vid = None, i_pbits = None, cmds = []):
        self.Action = openolt_pb2.Action(
            o_vid = o_vid,
            o_pbits = o_pbits,
            i_vid = i_vid,
            i_pbits = i_pbits
        )

        if "add_outer_tag" in cmds:
            self.Action.cmd.add_outer_tag = True

        if "remove_outer_tag" in cmds:
            self.Action.cmd.remove_outer_tag = True

        if "add_inner_tag" in cmds:
            self.Action.cmd.add_inner_tag = True

        if "remove_inner_tag" in cmds:
            self.Action.cmd.remove_inner_tag = True

        if "translate_outer_tag" in cmds:
            self.Action.cmd.translate_outer_tag = True

        if "translate_inner_tag" in cmds:
            self.Action.cmd.translate_inner_tag = True

    def exists_GroupMember(self, intf_id):
        for member in self.copy():
            if member.intf_id == intf_id:
                return True
        return False

    def get_Group(self):
        return openolt_pb2.Group(group_id = self.group_id, command = openolt_pb2.Group.GroupMembersCommand.ADD_MEMBERS,
                                 action = self.Action)

    def get_Group_members(self):
        return openolt_pb2.Group(group_id = self.group_id, command = openolt_pb2.Group.GroupMembersCommand.ADD_MEMBERS,
                                 members = self.copy(), action = self.Action)

class MulticastService(MulticastGroup):

    def __init__(self, group_id, gemport_id):
        super().__init__(group_id, gemport_id)
        self.intf_service = dict()
        self.members = dict()

        self.priorities = []

    def update_servicePriorities (self, priorities):
        self.priorities = priorities

    def compare_priorities(self, priorities):
        for i in range(0, min(len(priorities), len(self.priorities))):
            if priorities[i] > self.priorities[i]:
                return True
            elif priorities[i] < self.priorities[i]:
                return False

        return False

    # TODO each time a new member is added, search for
    #   traffic_scheds and queues and update this members
    def add_member(self, intf_id, onu_id, uni_id, port_no):
        entry = (onu_id, uni_id, port_no)

        if intf_id in self.members:
            if entry not in self.members[intf_id][0]:
                self.members[intf_id][0].append(entry)
        else:
            super().add_member(intf_id = intf_id)
            service = MulticastMember(intf_id = intf_id, group_id = self.group_id)
            self.members.update({intf_id : ([entry,], service)})

    def get_members(self):
        return self.members

    def add_traffic_sched(self, priority = None, weight = None, cir = None, pir = None, pbs = None):
        for member in self.members.values():
            member[1].add_traffic_sched(direction = tech_profile_pb2.Direction.DOWNSTREAM,
                                        priority = priority, weight = weight, cir = cir, pir = pir, pbs = pbs)

    def remove_traffic_schedulers(self):
        for member in self.members.values():
            member[1].remove_traffic_schedulers()

    def add_traffic_queue(self, priority = None, weight = None):
        for member in self.members.values():
            member[1].add_traffic_queue(direction = tech_profile_pb2.Direction.DOWNSTREAM,
                                        gemport_id = self.gemport_id, priority = priority, weight = weight)


    def remove_traffic_queues(self):
        for member in self.members.values():
            member[1].remove_traffic_queues()


    def get_traffic_schedulers(self, intf_id = None):
        if intf_id is None:
            scheds = list()
            for member in self.members.values():
                scheds.append(member[1].get_traffic_schedulers())

            return scheds

        if intf_id in self.members:
            return (self.members[intf_id][1]).get_traffic_schedulers()

        return None

    def get_traffic_queues(self, intf_id = None):
        if intf_id is None:
            scheds = list()
            for member in self.members.values():
                scheds.append(member[1].get_traffic_queues())

            return scheds

        if intf_id in self.members:
            return (self.members[intf_id][1]).get_traffic_queues()

        return None

    def generate_classifiers(self, o_vid = None, i_vid = None, o_pbits = None, eth_type = None,
                            dst_mac = None, ip_proto = None, src_port = None, dst_port = None, tag_type = None):
        for member in self.members.values():
            member[1].generate_classifier(o_vid = o_vid, i_vid = i_vid, o_pbits = o_pbits, eth_type = eth_type,
                                          dst_mac = dst_mac, ip_proto = ip_proto, src_port = src_port, dst_port = dst_port, tag_type = tag_type)

    def generate_flows(self, flow_id):
        flows_arr = []
        if len(self.priorities) == 0:
            return []

        for member in self.members.values():
            flows_arr.append(member[1].generate_flow(flow_id, self.priorities[0], self.gemport_id))

        return flows_arr

    def clean_flows(self):
        for member in self.members.values():
            member[1].clean_flow()

    def get_tags_configuration(self):
        return list(self.members.values())[0][1].get_tags_configuration()

class voipServer:
    def __init__(self, ipAddress, port = 5060):
        self.ipAddress = ipAddress
        self.port = port

class voipExtension:
    def __init__(self, extension, password, ipAddress = None, mask = None, gateway = None, primaryDNS = None, secondaryDNS = None, rtpPort = None):
        self.extension = extension
        self.password = password
        self.ipAddress = ipAddress
        self.mask = mask
        self.gateway = gateway
        self.primaryDNS = primaryDNS
        self.secondaryDNS = secondaryDNS
        self.rtpPort = rtpPort

class VoipService(InternetService):
    def __init__(self, intf_id, onu_id, uni_id, port_no):
        super().__init__(intf_id, onu_id, uni_id, port_no)
        self.voipServer = None
        self.extension = None

    def add_voipServer(self, ipAddress, port):
        self.voipServer = voipServer(ipAddress, port)

    def add_extension(self, extension, password, ipAddress = None, mask = None, gateway = None, primaryDNS = None, secondaryDNS = None, rtpPort = None):
        self.extension = voipExtension(extension, password, ipAddress, mask, gateway, primaryDNS, secondaryDNS, rtpPort)

    def extension_exists(self, extension, password):
        if self.extension is None:
            return False

        if self.extension.extension == extension and self.extension.password == password:
            return True

        return False

