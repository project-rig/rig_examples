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

# Construct the placements (map vertices to chips)
placements = {
    transmitters[0]: (1, 0),
    transmitters[1]: (1, 0),
    transmitters[2]: (1, 1),
    receiver: (0, 1),
}

# Construct the allocations (map vertices to slices of resources)
allocations = {
    transmitters[0]: {Cores: slice(1, 2)},  # Core 1
    transmitters[1]: {Cores: slice(2, 3)},  # Core 2
    transmitters[2]: {Cores: slice(3, 4)},  # Core 3
    receiver: {Cores: slice(1, 2)},
}

# Get information about the SpiNNaker machine we're using
machine = mc.get_machine()

# Perform the routing
routes = place_and_route.route(vertices_resources,
                               nets,
                               machine,
                               constraints=list(),  # No constraints
                               placements=placements,
                               allocations=allocations)

# Build the application map and routing trees
application_map = place_and_route.utils.build_application_map(
    vertices_applications, placements, allocations
)
routing_tables = place_and_route.utils.build_routing_tables(routes, net_keys)
print(routing_tables)

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
    print(mc.get_iobuf(x=0, y=1, p=1))
