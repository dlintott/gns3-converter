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
import json
import os
import sys
import shutil
import argparse
import logging
from gns3converter import Converter, __version__

LOG_MSG_FMT = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] ' \
              '%(message)s'
LOG_DATE_FMT = '%y%m%d %H:%M:%S'


def main():
    """
    Entry point for gns3-converter
    """
    print('GNS3 Topology Converter')

    arg_parse = setup_argparse()
    args = arg_parse.parse_args()

    if args.debug:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.WARNING

    logging.basicConfig(level=logging_level,
                        format=LOG_MSG_FMT, datefmt=LOG_DATE_FMT)

    logging.getLogger(__name__)

    # Create a new instance of the the Converter
    gns3_conv = Converter(topology_abspath(args.topology), args.debug)
    # Read the old topology
    old_top = gns3_conv.read_topology()

    # Process the sections
    (devices, conf, artwork) = gns3_conv.process_topology(old_top)

    # Generate the nodes
    topology_nodes = gns3_conv.generate_nodes(devices, conf)
    # Generate the links
    topology_links = gns3_conv.generate_links(topology_nodes)

    topology_notes = gns3_conv.generate_notes(artwork['NOTE'])
    topology_shapes = gns3_conv.generate_shapes(artwork['SHAPE'])
    topology_images = gns3_conv.generate_images(artwork['PIXMAP'])

    # Enter topology name
    topology_name = name(args)

    # Build the topology servers data
    topology_servers = [{'host': '127.0.0.1',
                         'id': 1,
                         'local': True,
                         'port': 8000}]
    # Compile all the sections ready for output
    assembled = {'name': topology_name,
                 'resources_type': 'local',
                 'topology': {'links': topology_links,
                              'nodes': topology_nodes,
                              'servers': topology_servers},
                 'type': 'topology',
                 'version': '1.0'}

    if len(topology_notes) > 0:
        assembled['topology']['notes'] = topology_notes

    if len(topology_shapes['ellipse']) > 0:
        assembled['topology']['ellipses'] = topology_shapes['ellipse']
    if len(topology_shapes['rectangle']) > 0:
        assembled['topology']['rectangles'] = topology_shapes['rectangle']
    if len(topology_images) > 0:
        assembled['topology']['images'] = topology_images

    # Save the new topology
    save(args, topology_name, gns3_conv, assembled)


def setup_argparse():
    """
    Setup the argparse argument parser

    :return: instance of argparse
    :rtype: ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Convert old ini-style GNS3 topologies (<=0.8.7) to '
                    'the newer version 1+ JSON format')
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('-n', '--name', help='Topology name (default uses the '
                                             'name of the old project '
                                             'directory)')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('topology', nargs='?', default='topology.net',
                        help='GNS3 .net topology file (default: topology.net)')
    parser.add_argument('--debug',
                        help='Enable debugging output',
                        action='store_true')
    return parser


def topology_abspath(topology):
    """
    Get the absolute path of the topology file

    :param str topology: Topology file
    :return: Absolute path of topology file
    :rtype: str
    """
    return os.path.abspath(topology)


def topology_dirname(topology):
    """
    Get the directory containing the topology file

    :param str topology: topology file
    :return: directory which contains the topology file
    :rtype: str
    """
    return os.path.dirname(topology_abspath(topology))


def name(args):
    """
    Calculate the name to save the converted topology as

    :return: new topology name
    :rtype: str
    """
    if args.name is not None:
        logging.debug('topology name supplied')
        topo_name = args.name
    else:
        logging.debug('topology name not supplied')
        topo_name = os.path.basename(topology_dirname(args.topology))
    return topo_name


def save(args, topology_name, converter, conv_topology):
    """
    Save the converted topology

    :param args: Program arguments
    :param topology_name: Name to save topology as
    :param converter: Converter instance
    :param conv_topology: The converted topology
    """
    try:
        config_err = False
        image_err = False
        if args.output:
            output_dir = os.path.abspath(args.output)
        else:
            output_dir = os.getcwd()

        topology_dir = os.path.join(output_dir, topology_name)
        old_topology_dir = os.path.dirname(topology_abspath(args.topology))
        topology_files_dir = os.path.join(topology_dir, topology_name +
                                          '-files')

        # Prepare the directory structure
        if not os.path.exists(topology_dir):
            os.makedirs(topology_files_dir)
        else:
            logging.error('Topology folder for %s already exists, please '
                          'specify a different name (using -n or --name)'
                          % topology_name)
            sys.exit(1)
        # Move the dynamips config files to the new topology folder
        if len(converter.configs) > 0:
            dynamips_config_dir = os.path.join(topology_files_dir, 'dynamips',
                                               'configs')
            os.makedirs(dynamips_config_dir)
            for config in converter.configs:
                old_config_file = os.path.join(old_topology_dir, config['old'])
                new_config_file = os.path.join(dynamips_config_dir,
                                               config['new'])
                if os.path.isfile(old_config_file):
                    # Copy and rename the config
                    shutil.copy(old_config_file, new_config_file)
                else:
                    config_err = True
                    logging.error('Unable to find %s' % config['old'])

        # Move the image files to the new topology folder if applicable
        if len(converter.images) > 0:
            images_dir = os.path.join(topology_dir, topology_name + '-files',
                                      'images')
            os.makedirs(images_dir)
            for image in converter.images:
                old_image_file = os.path.abspath(image)
                new_image_file = os.path.join(images_dir,
                                              os.path.basename(image))
                if os.path.isfile(os.path.abspath(old_image_file)):
                    shutil.copy(old_image_file, new_image_file)
                else:
                    image_err = True
                    logging.error('Unable to find %s' % old_image_file)

        if config_err:
            logging.warning('Some router startup configurations could not be '
                            'found to be copied to the new topology')

        if image_err:
            logging.warning('Some images could not be found to be copied to '
                            'the new topology')

        filename = '%s.gns3' % topology_name
        file_path = os.path.join(topology_dir, filename)
        with open(file_path, 'w') as file:
            json.dump(conv_topology, file, indent=4, sort_keys=True)
            print('Your topology has been converted and can found in:\n'
                  '     %s' % topology_dir)
    except OSError as error:
        logging.error(error)


if __name__ == '__main__':
    main()
