from random import randint
import struct
import sys
from rig.machine import Cores, SDRAM
from rig.machine_control import MachineController
from rig.machine_control.utils import sdram_alloc_for_vertices
from rig.netlist import Net
from rig import place_and_route

# Create a new MachineController for the SpiNNaker machine whose hostname is
# given on the command line
mc = MachineController(sys.argv[1])

# Create objects to represent the transmitters and the receiver
transmitters = [object() for _ in range(3)]
receiver = object()

# Create a dictionary mapping each object ("vertex") to the application that it
# represents.
vertices_applications = {t: "transmitter.aplx" for t in transmitters}
vertices_applications[receiver] = "receiver.aplx"

# Indicate that each application requires 1 processing. Each transmitter
# requires 2 words of SDRAM and the receiver 1 word.
vertices_resources = {t: {Cores: 1, SDRAM: 8} for t in transmitters}
vertices_resources[receiver] = {Cores: 1, SDRAM: 4}

# Construct the netlist
nets = [Net(t, receiver) for t in transmitters]

# Construct a map from nets to keys and masks
net_keys = {n: (i, 0xffffffff) for i, n in enumerate(nets)}

# Get information about the SpiNNaker machine we're using
machine = mc.get_machine()

# Place, allocate and route ensuring that the monitor processor is left
# untouched.
placements, allocations, application_map, routing_tables = \
    place_and_route.wrapper(vertices_resources,
                            vertices_applications,
                            nets,
                            net_keys,
                            machine)

# Load and run the application
with mc.application():
    # Get SDRAM for the vertices
    vertices_memory = sdram_alloc_for_vertices(mc, placements, allocations,
                                               clear=True)

    # Write in the data for the transmitters: key to use, value to send
    values = list()
    for i, t in enumerate(transmitters):
        # Generate a random number to add
        values.append(randint(1, 128))

        # Use the index as the multicast key, write to SDRAM
        vertices_memory[t].write(struct.pack("<2I", i, values[-1]))
        vertices_memory[t].seek(0)

    # Load the applications and routing tables
    mc.load_application(application_map)
    mc.load_routing_tables(routing_tables)

    # Wait for SYNC0
    mc.wait_for_cores_to_reach_state("sync0", 4)
    mc.send_signal("sync0")  # Start the application

    # Wait for the application to finish running
    mc.wait_for_cores_to_reach_state("exit", 4)

    # Read back the output from the receiver
    result_bytes = vertices_memory[receiver].read(4)
    result, = struct.unpack("<I", result_bytes)
    print("Expected {}, got {}".format(sum(values), result))
