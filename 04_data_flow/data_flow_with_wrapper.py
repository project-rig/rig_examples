import sys
import time
from rig.machine import Cores
from rig.machine_control import MachineController
from rig.netlist import Net
from rig import place_and_route

# Create a new MachineController for the SpiNNaker machine whose hostname is
# given on the command line
mc = MachineController(sys.argv[1])

# Boot the machine given the width and height arguments from the command line
mc.boot(int(sys.argv[2]), int(sys.argv[3]))

# Create objects to represent the transmitters and the receiver
transmitters = [object() for _ in range(3)]
receiver = object()

# Create a dictionary mapping each object ("vertex") to the application that it
# represents.
vertices_applications = {t: "transmitter.aplx" for t in transmitters}
vertices_applications[receiver] = "receiver.aplx"

# Indicate that each application requires 1 processing core
vertices_resources = {t: {Cores: 1} for t in transmitters}
vertices_resources[receiver] = {Cores: 1}

# Construct the netlist
nets = [Net(t, receiver) for t in transmitters]

# Construct a map from nets to keys and masks
net_keys = {n: (0x0000ffff, 0xffffffff) for n in nets}

# Get information about the SpiNNaker machine we're using
machine = mc.get_machine()

# Place, allocate and route ensuring that the monitor processor is left
# untouched.
placements, allocations, application_map, routing_tables = \
    place_and_route.wrapper(vertices_resources,
                            vertices_applications,
                            nets,
                            net_keys,
                            machine,
                            reserve_monitor=True)

# Load and run the application
with mc.application():
    # Load the applications and routing tables
    mc.load_application(application_map)
    mc.load_routing_tables(routing_tables)

    # Wait for SYNC0
    mc.wait_for_cores_to_reach_state("sync0", 4)
    mc.send_signal("sync0")  # Start the application

    # Wait for the application to finish running
    time.sleep(0.01)
    mc.wait_for_cores_to_reach_state("exit", 4)

    # Read back the output from the receiver
    x, y = placements[receiver]
    p = allocations[receiver][Cores].start
    print(mc.get_iobuf(x=x, y=y, p=p))
