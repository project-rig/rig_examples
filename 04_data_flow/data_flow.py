import sys
import time
from rig.machine_control import MachineController

# Create a new MachineController for the SpiNNaker machine whose hostname is
# given on the command line
mc = MachineController(sys.argv[1])

# To boot the machine, we take its network dimensions as command line
# arguments.  For a SpiNN-2 or SpiNN-3 board these dimensions are 2 and 2. For
# a SpiNN-5 board the dimensions are 8 and 8.
mc.boot(int(sys.argv[2]), int(sys.argv[3]))

"""
We'll load the transmitter application onto cores 1 and 2 of chip (1, 0), and
core 3 of chip (1, 1).  The receiver application will be loaded to core 1 of
(0, 1).
"""
application_map = {
    "transmitter.aplx": {
        (1, 0): {1, 2},
        (1, 1): {3},
    },
    "receiver.aplx": {(0, 1): {1}},
}

"""
We need to create 1 routing entry on each of the chips that we're using. On
chip (1, 0) we need to send all packets north to chip (1, 1).  From (1, 1) we
need to send all packets west to (0, 1). On chip (0, 1) we need to route all
the packets to core 1.

.. note::
    We can assign multiple routing table entries to each chip by adding more
    items to the lists associated with each co-ordinate.

"""
from rig.routing_table import RoutingTableEntry
from rig.routing_table import Routes

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

"""
Loading the application occurs as before. We use ``load_routing_tables`` to
load the routing tables that we specified before.

We need to ensure that all applications are ready before they start execution.
This is achieved with ``spin1_start(SYNC_WAIT)`` in the C. This causes
applications to enter one of two alternating synchronisation states: ``sync0``
or ``sync1``. We then wait to ensure that all applications are in the first of
these states before sending a signal to start them.

Before reading out the output from the receiver we wait for the application to
stop as before.
"""
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
