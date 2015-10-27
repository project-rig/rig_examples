import sys
import time
from rig.machine_control import MachineController
from rig.routing_table import RoutingTableEntry
from rig.routing_table import Routes

# Create a new MachineController for the SpiNNaker machine whose hostname is
# given on the command line
mc = MachineController(sys.argv[1])

# Boot the machine given the width and height arguments from the command line
mc.boot(int(sys.argv[2]), int(sys.argv[3]))

# Create the application map
application_map = {
    "transmitter.aplx": {
        (1, 0): {1, 2},
        (1, 1): {3},
    },
    "receiver.aplx": {(0, 1): {1}},
}

# Create the routing tables
routing_tables = {
    (1, 0): [
        RoutingTableEntry({Routes.north}, 0x0000ffff, 0xffffffff),
    ],
    (1, 1): [
        RoutingTableEntry({Routes.west}, 0x0000ffff, 0xffffffff),
    ],
    (0, 1): [
        RoutingTableEntry({Routes.core(1)}, 0x0000ffff, 0xffffffff),
    ],
}

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
