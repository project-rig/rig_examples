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

# Create a constraint that ensures that we don't try to load applications to
# the monitor processor.
constraints = [
    place_and_route.constraints.ReserveResourceConstraint(Cores, slice(0, 1))
]

# Place the applications
placements = place_and_route.place(vertices_resources,
                                   nets,
                                   machine,
                                   constraints)

# Allocate resources
allocations = place_and_route.allocate(vertices_resources,
                                       nets,
                                       machine,
                                       constraints,
                                       placements)

# Perform the routing
routes = place_and_route.route(vertices_resources,
                               nets,
                               machine,
                               constraints,
                               placements,
                               allocations)

# Build the application map and routing trees
application_map = place_and_route.utils.build_application_map(
    vertices_applications, placements, allocations
)
routing_tables = place_and_route.utils.build_routing_tables(routes, net_keys)

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
