# Copyright (C) 2014 Daniel Lintott.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
from configobj import ConfigObj, flatten_errors
from validate import Validator
import os
import sys
from ipaddress import ip_address
import re
from pkg_resources import resource_stream
from .ports import MODEL_MATRIX, PORT_TYPES, ADAPTER_MATRIX

# Globals
# Regex matching interfaces (e.g. "f0/0")
interface_re = re.compile(r"""^(g|gi|f|fa|a|at|s|se|e|et|p|po|i|id|IDS-Sensor
|an|Analysis-Module)([0-9]+)/([0-9]+)""", re.IGNORECASE)
# Regex matching interfaces with out a port (e.g. "f0")
interface_noport_re = re.compile(r"""^(g|gi|f|fa|a|at|s|se|e|et|p|po)
([0-9]+)""", re.IGNORECASE)
# Regex matching a number (means an Ethernet switch port config)
ethswint_re = re.compile(r"""^([0-9]+)""")


class Converter():
    """
    GNS3 Topology Converter Class
    :param topology: Filename of the ini-style topology
    """
    def __init__(self, topology, debug=False):
        self._topology = topology
        self._debug = debug

        self.port_id = 1
        self.links = []
        self.configs = []

        self.model_transform = {'2691': 'c2691',
                                '3725': 'c3725',
                                '3745': 'c3745',
                                '7200': 'c7200'}
        for chassis in ('1720', '1721', '1750', '1751', '1760'):
            self.model_transform[chassis] = 'c1700'
        for chassis in ('2620', '2621', '2610XM', '2611XM', '2620XM',
                        '2621XM', '2650XM', '2651XM'):
            self.model_transform[chassis] = 'c2600'
        for chassis in ('3620', '3640', '3660'):
            self.model_transform[chassis] = 'c3600'

    def read_topology(self):
        """
        Read the ini-style topology file using ConfigObj
        :return: config
        """
        configspec = resource_stream(__name__, 'configspec')
        config = None
        try:
            handle = open(self._topology)
            handle.close()
            try:
                config = ConfigObj(self._topology,
                                   configspec=configspec,
                                   raise_errors=True,
                                   list_values=False,
                                   encoding='utf-8')
            except SyntaxError:
                print('Error loading .net file')
                exit()
        except IOError:
            print('Can\'t open topology file')
            exit()

        vtor = Validator()
        res = config.validate(vtor, preserve_errors=True)
        if res and self._debug:
            print('Validation Passed')
        else:
            for entry in flatten_errors(config, res):
                # each entry is a tuple
                (section_list, key, error) = entry
                if key is not None:
                    section_list.append(key)
                else:
                    section_list.append('[missing section]')
                section_string = ', '.join(section_list)

                if error is False:
                    error = 'Missing value or section'
                print(section_string, ' = ', error)
                input('Press ENTER to continue')
                sys.exit(1)

        configspec.close()
        return config

    def process_topology(self, sections, old_top):
        """
        Processes the sections returned by get_instances
        :param sections: A list of sections as generated by get_instances()
        :param old_top: The old topology as processed by read_topology()
        :return: devices, conf
        """
        devices = {}
        conf = {}
        hv_id = 0
        nid = 1

        for instance in sorted(sections):
            for item in sorted(old_top[instance]):
                if isinstance(old_top[instance][item], dict):
                    if item in self.model_transform:
                        # A configuration item
                        conf[hv_id] = {}
                        conf[hv_id]['model'] = self.model_transform[item]
                        for s_item in sorted(old_top[instance][item]):
                            if old_top[instance][item][s_item] is not None:
                                conf[hv_id][s_item] = \
                                    old_top[instance][item][s_item]
                    else:
                        # It must be a physical item
                        (device_name, device_type) = self.device_typename(item)
                        devices[device_name] = {}
                        if instance != 'GNS3-DATA':
                            devices[device_name]['hv_id'] = hv_id
                        devices[device_name]['node_id'] = nid
                        devices[device_name]['type'] = device_type['type']
                        for s_item in sorted(old_top[instance][item]):
                            if old_top[instance][item][s_item] is not None:
                                devices[device_name][s_item] = \
                                    old_top[instance][item][s_item]
                        if instance != 'GNS3-DATA' and \
                                devices[device_name]['type'] == 'Router':
                            if 'model' not in devices[device_name]:
                                devices[device_name]['model'] = \
                                    conf[hv_id]['model']
                            else:
                                devices[device_name]['model'] = \
                                    self.model_transform[
                                        devices[device_name]['model']]
                        nid += 1
            hv_id += 1
        return devices, conf

    @staticmethod
    def get_instances(config):
        """
        Get a list of Hypervisor instances
        :param config: Configuration from read_topology()
        :return: instances
        """
        instances = []
        for item in sorted(config):
            if ':' in item:
                delim_pos = item.index(':')
                addr = item[0:delim_pos]
                try:
                    ip_address(addr)
                    instances.append(item)
                except ValueError:
                    pass
        return instances

    @staticmethod
    def device_typename(item):
        """
        Convert the old names to new-style names and types
        :param item:
        :return: device
        """
        if item.startswith('ROUTER'):
            dev_type = {'from': 'ROUTER',
                        'desc': 'Router',
                        'type': 'Router'}
        elif item.startswith('QEMU'):
            dev_type = {'from': 'QEMU',
                        'desc': 'QEMU',
                        'type': 'QEMU'}
        elif item.startswith('VBOX'):
            dev_type = {'from': 'VBOX',
                        'desc': 'VBOX',
                        'type': 'VBOX'}
        elif item.startswith('FRSW'):
            dev_type = {'from': 'FRSW',
                        'desc': 'Frame Relay switch',
                        'type': 'FrameRelaySwitch'}
        elif item.startswith('ETHSW'):
            dev_type = {'from': 'ETHSW',
                        'desc': 'Ethernet switch',
                        'type': 'EthernetSwitch'}
        elif item.startswith('Hub'):
            dev_type = {'from': 'Hub',
                        'desc': 'Ethernet hub',
                        'type': 'EthernetHub'}
        elif item.startswith('ATMSW'):
            dev_type = {'from': 'ATMSW',
                        'desc': 'ATM switch',
                        'type': 'ATMSwitch'}
        elif item.startswith('ATMBR'):
            dev_type = {'from': 'ATMBR',
                        'desc': 'ATMBR',
                        'type': 'ATMBR'}
        elif item.startswith('Cloud'):
            dev_type = {'from': 'Cloud',
                        'desc': 'Cloud',
                        'type': 'Cloud'}
        else:
            dev_type = None

        name = item.replace('%s ' % dev_type['from'], '')
        device = [name, dev_type]
        return device

    def generate_nodes(self, devices, hypervisors):
        """
        Generate a list of nodes for the new topology
        :param devices:
        :param hypervisors:
        :return: nodes
        """
        nodes = []

        for device in sorted(devices):
            # Clear out the temporary structures
            node_temp = {}
            node_temp_label = {}
            # Start building the structure
            node_temp_props = {'name': device}
            node_temp_label['text'] = device
            node_temp['id'] = devices[device]['node_id']
            node_temp['server_id'] = 1
            node_temp_label['x'] = 15
            node_temp_label['y'] = -25
            node_temp['x'] = devices[device]['x']
            node_temp['y'] = devices[device]['y']
            device_info = {'type': devices[device]['type'],
                           'chassis': '',
                           'model': ''}
            connections = None
            interfaces = []

            if device_info['type'] == 'EthernetSwitch':
                node_temp['ports'] = []

            if 'model' in devices[device]:
                device_info['model'] = devices[device]['model']
            else:
                device_info['model'] = ''
            npe = None

            for item in sorted(devices[device]):
                if item == 'hv_id' and devices[device]['type'] == 'Router':
                    hv_id = devices[device][item]
                    node_temp_props['image'] = os.path.basename(
                        hypervisors[hv_id]['image'])

                    # IDLE-PC
                    if 'idlepc' in hypervisors[hv_id]:
                        node_temp_props['idlepc'] = \
                            hypervisors[hv_id]['idlepc']
                    # Router RAM
                    if 'ram' in hypervisors[hv_id]:
                        node_temp_props['ram'] = hypervisors[hv_id]['ram']
                    # 7200 NPE
                    if 'npe' in hypervisors[hv_id]:
                        npe = hypervisors[hv_id]['npe']
                    # Device Chassis
                    if 'chassis' in hypervisors[hv_id]:
                        device_info['chassis'] = hypervisors[hv_id]['chassis']

                elif item == 'type' and devices[device][item] == 'Router':
                    node_temp['router_id'] = devices[device]['node_id']
                elif item == 'aux':
                    node_temp_props['aux'] = devices[device][item]
                elif item == 'console':
                    node_temp_props['console'] = devices[device][item]
                elif item.startswith('slot'):
                    if device_info['model'] == 'c7200':
                        if item != 'slot0':
                            node_temp_props[item] = devices[device][item]
                    else:
                        node_temp_props[item] = devices[device][item]
                elif item == 'connections':
                    connections = devices[device][item]
                elif interface_re.search(item):
                    interfaces.append({'from': item,
                                       'to': devices[device][item]})
                elif ethswint_re.search(item):
                    (port_def, destination) = self.calc_ethsw_port(
                        item, devices[device][item])
                    node_temp['ports'].append(port_def)
                    self.links.append(self.calc_link(node_temp['id'],
                                                     port_def['id'],
                                                     destination))
                elif item == 'cnfg':
                    new_config = 'i%s_startup-config.cfg' % node_temp['id']
                    node_temp_props['startup_config'] = new_config

                    self.configs.append({'old': devices[device][item],
                                         'new': new_config})

            if device_info['type'] == 'Router':
                node_temp['description'] = device_info['type'] + ' ' + \
                    device_info['model']
                node_temp['type'] = device_info['model'].upper()

                node_temp['ports'] = self.calc_mb_ports(device_info['model'],
                                                        device_info['chassis'])
                for item in sorted(node_temp_props):
                    if item.startswith('slot'):
                        slot = item[4]
                        node_temp['ports'].extend(self.calc_slot_ports(
                            node_temp_props[item], slot))

                # Add default ports to 7200 and 3660
                if device_info['model'] == 'c7200' and npe == 'npe-g2':
                    node_temp['ports'].extend(
                        self.calc_slot_ports('C7200-IO-GE-E', 0))
                elif device_info['model'] == 'c7200':
                    node_temp['ports'].extend(
                        self.calc_slot_ports('C7200-IO-2FE', 0))
                elif device_info['model'] == 'c3600':
                    node_temp_props['chassis'] = device_info['chassis']
                    if device_info['chassis'] == '3660':
                        node_temp_props['slot0'] = 'Leopard-2FE'

                # Calculate the router links
                for connection in sorted(interfaces):
                    self.links.append(self.calc_router_links(connection,
                                                             node_temp))

            elif device_info['type'] == 'Cloud':
                node_temp['description'] = device_info['type']
                node_temp['type'] = device_info['type']
                node_temp['ports'] = []
                node_temp_props['nios'] = []

                # Calculate the cloud ports and NIOs
                connections = connections.split(' ')
                for connection in sorted(connections):
                    (port, nio) = self.calc_cloud_connection(connection)
                    node_temp['ports'].append(port)
                    node_temp_props['nios'].append(nio)
            else:
                node_temp['description'] = device_info['type']
                node_temp['type'] = device_info['type']

            node_temp['label'] = node_temp_label
            node_temp['properties'] = node_temp_props

            nodes.append(node_temp)

        return nodes

    def generate_links(self, nodes):
        """
        Generate a list of links
        :param nodes
        :return: links
        """
        links = []

        for link in self.links:
            # Expand port name if required
            if interface_re.search(link['dest_port']):
                int_type = link['dest_port'][0]
                dest_port = link['dest_port'].replace(
                    int_type, PORT_TYPES[int_type.upper()])
            else:
                dest_port = link['dest_port']

            #Convert dest_dev to destination_node_id
            (dest_node_id, dest_port_id) = self.convert_destination_to_id(
                link['dest_dev'], dest_port, nodes)

            links.append({'destination_node_id': dest_node_id,
                          'destination_port_id': dest_port_id,
                          'source_port_id': link['source_port_id'],
                          'source_node_id': link['source_node_id']})

        # Remove duplicate links and add link_id
        link_id = 1
        for link in links:
            t_link = str(link['source_node_id']) + ':' + \
                str(link['source_port_id'])
            for link2 in links:
                d_link = str(link2['destination_node_id']) + ':' + \
                    str(link2['destination_port_id'])
                if t_link == d_link:
                    links.remove(link2)
                    break
            link['id'] = link_id
            link_id += 1

            self.add_node_connections(link, nodes)
        return links

    def calc_mb_ports(self, model, device_chassis=''):
        """
        Calculate the default ports to add to a router
        :param model:
        :param device_chassis:
        :return: ports
        """
        num_ports = MODEL_MATRIX[model][device_chassis]['ports']
        ports = []

        if num_ports > 0:
            port_type = MODEL_MATRIX[model][device_chassis]['type']

            # Create the ports dict
            for i in range(num_ports):
                port_temp = {'name': PORT_TYPES[port_type] + '0/' + str(i),
                             'id': self.port_id,
                             'port_number': i,
                             'slot_number': 0}
                ports.append(port_temp)
                self.port_id += 1
        return ports

    def calc_slot_ports(self, adapter, slot):
        """
        Calculate the ports to be added for a adapter card
        :param adapter:
        :param slot:
        :return: ports
        """
        num_ports = ADAPTER_MATRIX[adapter]['ports']
        port_type = ADAPTER_MATRIX[adapter]['type']
        ports = []

        for i in range(num_ports):
            port_name = PORT_TYPES[port_type] + '%s/%s' % (slot, i)
            port_temp = {'name': port_name,
                         'id': self.port_id,
                         'port_number': i,
                         'slot_number': slot}
            ports.append(port_temp)
            self.port_id += 1
        return ports

    def calc_cloud_connection(self, connection):
        """
        Split and create the port for a cloud connection
        :param connection:
        :return: port, nio
        """
        # Connection String - SW1:1:nio_gen_eth:eth0
        # 0: Destination device 1: Destination port
        # 2: NIO 3: NIO Destination
        connection = connection.split(':')
        #destination = connection[0] + ':' + connection[1]
        nio = connection[2] + ':' + connection[3]
        #port entry
        port = {'id': self.port_id,
                'name': nio,
                'stub': True}
        self.port_id += 1
        return port, nio

    def calc_ethsw_port(self, port_num, port_def):
        """
        Split and create the port entry for an Ethernet Switch
        :param port_num:
        :param port_def:
        :return: port, destination
        """
        # Port String - access 1 SW2 1
        # 0: type 1: vlan 2: destination device 3: destination port
        port_def = port_def.split(' ')
        if len(port_def) == 4:
            destination = {'device': port_def[2],
                           'port': port_def[3]}
        else:
            destination = {'device': 'NIO',
                           'port': port_def[2]}
        #port entry
        port = {'id': self.port_id,
                'name': port_num,
                'port_number': int(port_num),
                'type': port_def[0],
                'vlan': int(port_def[1])}
        self.port_id += 1
        return port, destination

    @staticmethod
    def calc_link(src_id, src_port, destination):
        """
        Calculate the link entry
        :param src_id:
        :param src_port:
        :param destination:
        :return: link
        """
        link = {'source_node_id': src_id,
                'source_port_id': src_port,
                'dest_dev': destination['device'],
                'dest_port': destination['port']}
        return link

    @staticmethod
    def device_id_from_name(device_name, nodes):
        """
        Get the device ID when given a device name
        :param device_name:
        :param nodes:
        :return: device_id
        """
        device_id = None
        for node in nodes:
            if device_name == node['properties']['name']:
                device_id = node['id']
                break
        return device_id

    @staticmethod
    def port_id_from_name(port_name, device_id, nodes):
        """
        Get the port ID when given a port name
        :param port_name:
        :param device_id:
        :param nodes:
        :return: port_id
        """
        port_id = None
        for node in nodes:
            if device_id == node['id']:
                for port in node['ports']:
                    if port_name == port['name']:
                        port_id = port['id']
                        break
                break
        return port_id

    @staticmethod
    def convert_destination_to_id(destination_node, destination_port, nodes):
        """
        Convert a destination to device and port ID
        :param destination_node:
        :param destination_port:
        :param nodes:
        :return: device_id, port_id
        """
        device_id = None
        port_id = None
        if destination_node != 'NIO':
            for node in nodes:
                if destination_node == node['properties']['name']:
                    device_id = node['id']
                    for port in node['ports']:
                        if destination_port == port['name']:
                            port_id = port['id']
                            break
                    break
        else:
            for node in nodes:
                if node['type'] == 'Cloud':
                    for port in node['ports']:
                        if destination_port == port['name']:
                            device_id = node['id']
                            port_id = port['id']
                            break
                    break
        return device_id, port_id

    @staticmethod
    def add_node_connections(link, nodes):
        """
        Add connections to the node items
        :param link:
        :param nodes:
        """
        # Add source connections
        for node in nodes:
            if node['id'] == link['source_node_id']:
                for port in node['ports']:
                    if port['id'] == link['source_port_id']:
                        port['link_id'] = link['id']
                        break
            elif node['id'] == link['destination_node_id']:
                for port in node['ports']:
                    if port['id'] == link['destination_port_id']:
                        port['link_id'] = link['id']
                        break

    def calc_router_links(self, connection, node_temp):
        """
        Calculate a router link
        :param connection:
        :param node_temp:
        :return:
        """
        int_type = connection['from'][0]
        int_name = connection['from'].replace(int_type,
                                              PORT_TYPES[int_type.upper()])
        # Get the source port id
        src_port = 0
        for port in node_temp['ports']:
            if int_name == port['name']:
                src_port = port['id']
                break
        dest_temp = connection['to'].split(' ')

        if len(dest_temp) == 2:
            conn_to = {'device': dest_temp[0],
                       'port': dest_temp[1]}
        else:
            conn_to = {'device': 'NIO',
                       'port': dest_temp[0]}

        link = self.calc_link(node_temp['id'], src_port, conn_to)
        return link
