#!/usr/bin/env python

"""
A SpiNNaker-based heat diffusion demo application.

After booting your SpiNNaker machine::

    $ python run.py hostname

To specify an alternative constant of diffusivity::

    $ python run.py hostname 0.5
"""

from collections import namedtuple

import socket

import struct

import threading

from functools import partial

from six import itervalues, iteritems

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

from rig.type_casts import float_to_fix, NumpyFixToFloatConverter
from rig.geometry import spinn5_eth_coords
from rig.machine_control import MachineController
from rig.machine_control.packets import SCPPacket
from rig.machine_control.consts import SCP_PORT
from rig.machine import Cores
from rig.netlist import Net
from rig.place_and_route import route
from rig.place_and_route.utils import build_routing_tables


# Conversion to signed 15.16 fixed-point
float_to_s_15_16 = float_to_fix(signed=True, n_bits=32, n_frac=16)

# Conversion from a Numpy array of signed 15.16 fixed-point numbers to a Numpy
# array of floating point equivalents.
np_s_15_16_to_np_float = NumpyFixToFloatConverter(16)

# The UDP port to use for receiving temperature reports from the machine.
REPORT_PORT = 50007

# The (dx, dy) to each immediate neighbour of a cell.
NEIGHBOUR_DIRECTIONS = {
    (1, 0): "East",
    (-1, 0): "West",
    (0, 1): "North",
    (0, -1): "South",
}

Cell = namedtuple("Cell", "x,y,chip,core")
"""An object which represents a Cell.

Simply contains the coordinates of the cell in the heat map and the chip/core
it is simulated by.
"""

def init_cells(machine):
    """Create a Cell object for each cell in the simulation.
    
    Returns
    -------
    (cells, chip_cell_lookup)
        cells is a dictionary {(x, y): cell, ...} giving the Cell object at
        each coordinate in the heatmap.
        
        chip_cell_lookup is a dictionary {chip: [cell, ...], ...} giving the
        cells on each core of a SpiNNaker chip (identified as an (x, y) tuple).
        Element 0 in the list of cells corresponds with core 1 in a SpiNNaker
        machine.
    """
    cells = {}
    chip_cell_lookup = {}
    for chip in machine:
        chip_cell_lookup[chip] = []
        # Each chip will hosts a 4x4 set of cells, if possible. If 16
        # application cores are unavailable, just make as many as possible.
        for core in range(min(16, machine[chip][Cores] - 1)):
            x = (chip[0] * 4) + (core % 4)
            y = (chip[1] * 4) + (core // 4)
            cell = Cell(x, y, chip, core + 1)
            
            cells[(x, y)] = cell
            chip_cell_lookup[chip].append(cell)
    
    return cells, chip_cell_lookup


def cell_neighbours(cell):
    """Iterate over the coordinates of a cell's neighbours."""
    for dx, dy in NEIGHBOUR_DIRECTIONS:
        yield (cell.x + dx, cell.y + dy)


def create_nets(cells):
    """Create nets between the cells over which temperature updates will be
    sent.
    
    Returns
    -------
    cell_nets : {cell: net, ...}
        For each cell, gives the net used to multicast its temperature to its
        neighbours.
    edge_nets : {edge: net, ...}
        For each edge direction in NEIGHBOUR_DIRECTIONS, gives the net which
        connects from the cell (0, 0) to any disconnected edges in that
        direction. This net is used for setting the edge temperatures.
    cell_neighbour_net_lookup : {(x, y): {(dx, dy): net, ...}, ...}
        For each cell, gives the net connecting to each of its neighbours used
        to receive temperature updates.
    """
    cell_nets = {}
    
    # Connect each cell to its neighbours
    for cell in itervalues(cells):
        cell_nets[cell] = Net(cell, [cells[n]
                                     for n in cell_neighbours(cell)
                                     if n in cells])
    
    # For cells with no neighbour available in each of the directions, we
    # connect them to (0, 0) which can then be used to allow the host to set
    # border temperatures.
    edge_nets = {
        (dx, dy): Net(cells[(0, 0)],
                      [c for (x, y), c in iteritems(cells)
                       if (x + dx, y + dy) not in cells])
        for (dx, dy) in NEIGHBOUR_DIRECTIONS
    }
    
    # A lookup {(x, y): {(dx, dy): net}, ...} giving the nets connected to each
    # neighbour of a cell
    cell_neighbour_net_lookup = {
        (x, y): {
            (dx, dy): (cell_nets[cells[(x + dx, y + dy)]]
                       if (x + dx, y + dy) in cells
                       else edge_nets[(dx, dy)])
            for (dx, dy) in NEIGHBOUR_DIRECTIONS
        } for (x, y) in cells
    }
    
    return cell_nets, edge_nets, cell_neighbour_net_lookup


def generate_routing_tables(cells, cell_nets, edge_nets, machine):
    """Generate routing tables for the application.
    
    Returns
    -------
    net_keys, routing_tables
        `net_keys` is a dict {net: (key, mask), ...} giving the unique key and
        mask given to each net.
        
        `routing_tables` gives the automatically generated routing tables in
        the standard structure used by rig.
    """
    # Assign each net a unique routing key sequentially
    nets = list(itervalues(cell_nets)) + list(itervalues(edge_nets))
    net_keys = {n: (i, 0xFFFFFFFF) for i, n in enumerate(nets)}
    
    # Perform manual placement of each cell
    vertices_resources = {c: {Cores: 1} for c in itervalues(cells)}
    placements = {c: c.chip for c in itervalues(cells)}
    allocations = {c: {Cores: slice(c.core, c.core + 1)}
                   for c in itervalues(cells)}
    
    # Since placement/allocation has been done manually already there's no need
    # for a ReserveResourceConstraint to reserve a core for the monitor (which
    # only affects placement and allocation)
    constraints = []
    
    # Perform automatic routing
    routes = route(vertices_resources, nets, machine, constraints,
                   placements, allocations)
    routing_tables = build_routing_tables(routes, net_keys)
    
    return net_keys, routing_tables


def setup_iptags(mc, machine, addr, port):
    """Set up an IP tag on each Ethernet connected chip to point packets back
    to this machine.
    """
    # Configure the IP tag on all Ethernet connected chips
    for x, y in spinn5_eth_coords(machine.width, machine.height):
        mc.iptag_set(1, addr, port, x, y)


def load_sdram(mc, chip_cell_lookup, alpha,
               net_keys, cell_nets, cell_neighbour_net_lookup):
    """Allocate and initialise all shared memory and configuration data."""
    for chip, chip_cells in iteritems(chip_cell_lookup):
        # Allocate space for the shared memory for communicating cell
        # temperatures on chip
        mc.sdram_alloc(4 * len(chip_cells),
                       x=chip[0], y=chip[1], tag=0xFF,
                       clear=True)
        
        # Generate and write configuration data for each cell
        for num, cell in enumerate(chip_cells):
            sdram = mc.sdram_alloc_as_filelike(
                4 * (3 + len(NEIGHBOUR_DIRECTIONS)),
                x=chip[0], y=chip[1], tag=cell.core)
            sdram.write(struct.pack(
                "<III{}I".format(len(NEIGHBOUR_DIRECTIONS)),
                # num_reported_temperatures
                len(chip_cells) if num == 0 else 0,
                # alpha
                float_to_s_15_16(alpha),
                # temperature_key
                net_keys[cell_nets[cell]][0],
                # neighbour_keys
                *(net_keys[n][0] for n in
                  itervalues(cell_neighbour_net_lookup[(cell.x, cell.y)]))
            ))


class Visualiser(threading.Thread):
    """An interactive GUI which displays the temperatures reported by each cell
    and allows the temperatures around the periphery to be controlled.
    
    This visualiser uses two threads. In the main thread matplotlib is used to
    display a window containing the heatmap and sliders for controlling the
    temperatures around the periphery. In the background thread, incoming
    temperature reports from SpiNNaker are processed ready for the main thread
    to display when it next refreshes.
    """
    
    def __init__(self, width, height, in_sock, out_sock,
                 edge_keys, chip_cell_lookup,
                 initial_temp=50.0, max_temp=100.0, update_fps=20):
        """An interactive visualiser for the heatmap.
        
        An interactive GUI is displayed when the `main` method is called.
        
        Parameters
        ----------
        width : int
        height : int
            Dimensions of the heat map (not of the SpiNNaker machine).
        in_sock : :py:class:`socket.Socket`
            A socket on which temperature reports from SpiNNaker may be
            received.
        out_sock : :py:class:`socket.Socket`
            A socket out of which edge temperature commands may be sent to
            SpiNNaker.
        edge_keys : {(dx, dy): key, ...}
            For each direction in NEIGHBOUR_DIRECTIONS, gives the routing key
            used for setting the edge temperatures in that direction.
        chip_cell_lookup : {(x, y): [cell, ...], ...}
            For each SpiNNaker chip coordinate (x, y), gives a list of the
            cells on each core on that chip (starting with core 1).
        initial_temp : float
            The initial edge temperature.
        max_temp : float
            The maximum temperature available on the sliders (and the
            temperature scale).
        update_fps : int
            Target number of frames-per-second to redraw the heatmap.
        """
        super(Visualiser, self).__init__()
        
        self.in_sock = in_sock
        self.out_sock = out_sock
        
        self.edge_keys = edge_keys
        self.chip_cell_lookup = chip_cell_lookup
        
        # Convert FPS to frame-time in ms
        self.update_interval = int(1000.0 / update_fps)
        
        # Lock to be held when accessing self.heatmap
        self.heatmap_lock = threading.Lock()
        
        # The last known state of each pixel
        self.heatmap = np.zeros((height, width))
        self.heatmap_changed = False
        
        # Place the heatmap plot above the sliders with the Y-axis increasing from the bottom left.
        self.fig, self.heatmap_ax = plt.subplots()
        plt.subplots_adjust(bottom=0.05 * (len(NEIGHBOUR_DIRECTIONS) + 3))
        self.heatmap_artist = self.heatmap_ax.imshow(self.heatmap,
                                                     interpolation="none",
                                                     origin='lower')
        self.heatmap_artist.set_clim(0.0, max_temp)
        plt.colorbar(self.heatmap_artist)
        
        # Set up a timer to redraw the plot at the desired frame-rate
        self.timer = self.fig.canvas.new_timer(interval=self.update_interval)
        self.timer.add_callback(self.on_timer_tick)
        self.timer.start()
        
        # Create sliders for adjusting the temperature
        self.sliders = {}
        for num, (edge, name) \
                in enumerate(sorted(iteritems(NEIGHBOUR_DIRECTIONS))):
            ax = plt.axes([0.1, 0.05 * (num + 1), 0.8, 0.04])
            self.sliders[edge] = Slider(ax, name, 0.0, max_temp,
                                        valinit=initial_temp)
            self.sliders[edge].on_changed(
                partial(self.on_slider_changed, edge))
            self.set_temperature(edge, initial_temp)

    def on_timer_tick(self):
        """Callback for timer tick: redraw display"""
        with self.heatmap_lock:
            if self.heatmap_changed:
                self.heatmap_artist.set_data(self.heatmap)
                self.fig.canvas.draw_idle()
                self.heatmap_changed = False
    
    def on_slider_changed(self, edge, value):
        """Callback when a slider is changed: send new temperature."""
        self.set_temperature(edge, value)
        self.fig.canvas.draw_idle()

    def set_temperature(self, edge, temperature):
        """Send a temperature change command."""
        packet = SCPPacket(
            reply_expected=False, tag=0xff,
            dest_port=1, dest_cpu=1,
            src_port=7, src_cpu=31,
            dest_x=0, dest_y=0,
            src_x=0, src_y=0,
            cmd_rc=0, seq=0,
            arg1=self.edge_keys[edge],
            arg2=float_to_s_15_16(temperature),
            arg3=0,
            data=b""
        )
        self.out_sock.send(packet.bytestring)

    def run(self):
        """Background thread.
        
        The background thread is killed when the in_sock socket fails to
        receive a packet. This can occur if there is some sort of error and
        also if the socket is closed in another thread (the signal of choice
        for killing this thread).
        """
        while True:
            # Die if no data arrives or an error occurs.
            try:
                data = self.in_sock.recv(512)
            except OSError:
                return
            if not data:
                return
            
            # Unpack the temperature report and convert the fixed point values
            # to floating point.
            sdp = SCPPacket.from_bytestring(data)
            values = np_s_15_16_to_np_float(np.frombuffer(sdp.data, dtype=np.int32))
            chip = (sdp.src_x, sdp.src_y)
            
            # Update the heatmap with the newly received temperature.
            with self.heatmap_lock:
                for cell, value in zip(self.chip_cell_lookup[chip], values):
                    self.heatmap[cell.y, cell.x] = value
                self.heatmap_changed = True
    
    def main(self):
        """Start the Visualiser GUI."""
        try:
            # Start processing temperature reports
            self.start()
            
            # Set initial temperatures
            for edge, slider in iteritems(self.sliders):
                self.set_temperature(edge, slider.val)
            
            # Show the window and enter the GUI main loop
            plt.show()
        finally:
            # Close the sockets (also kills the background thread)
            self.in_sock.close()
            self.out_sock.close()


def main(hostname, alpha=0.04):
    """Load the heat diffusion program onto the supplied machine.
    
    Parameters
    ----------
    hostname : string
        The hostname or IP of the SpiNNaker machine to control.
    alpha : float
        The constant of diffusivity to use in the simulation.
    """
    mc = MachineController(hostname)
    machine = mc.get_machine()
    
    # Create an object for each cell in the simulation, allocating each to a
    # specific chip/core.
    cells, chip_cell_lookup = init_cells(machine)
    
    # Enumerate the nets (connections) between cells
    cell_nets, edge_nets, cell_neighbour_net_lookup = create_nets(cells)
    
    # Automatically generate routing tables
    net_keys, routing_tables = generate_routing_tables(cells, cell_nets,
                                                       edge_nets, machine)
    
    with mc.application():
        # Load routing entries
        mc.load_routing_tables(routing_tables)
        
        # Open a socket to send out edge temperatures on
        out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        out_sock.connect((hostname, SCP_PORT))
        
        # Open a socket to receive temperature reports on
        in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        in_sock.bind(("", REPORT_PORT))
        
        # Configure IP tags on all Ethernet connected chips to send packets to
        # this machine.
        setup_iptags(mc, machine, *in_sock.getsockname())
        
        # Allocate/load SDRAM with config data
        load_sdram(mc, chip_cell_lookup, alpha,
                   net_keys, cell_nets, cell_neighbour_net_lookup)
        
        # Load the application on to the machine and start it
        mc.load_application("heat.aplx", {chip: set(c.core for c in cores)
                                          for chip, cores in
                                          iteritems(chip_cell_lookup)})
        mc.wait_for_cores_to_reach_state("sync0", len(cells))
        mc.send_signal("sync0")
        
        # Show the visualiser.
        edge_keys = {edge: net_keys[edge_nets[edge]][0]
                     for edge in NEIGHBOUR_DIRECTIONS}
        
        vis = Visualiser(machine.width * 4, machine.height * 4,
                         in_sock, out_sock, edge_keys, chip_cell_lookup)
        vis.main()


if __name__=="__main__":
    # Run the example taking the hostname and (optionally) the constant of
    # diffusivity from the command-line.
    import sys
    main(sys.argv[1], *(map(float, sys.argv[2:])))
