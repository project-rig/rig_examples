"""
A Rig-based program which boots a SpiNNaker machine and loads the "hello world"
SpiNNaker binary onto it.
"""

import sys

from rig.machine_control import MachineController

# Create a new MachineController for the SpiNNaker machine whose hostname is
# given on the command line
mc = MachineController(sys.argv[1])

# To boot the machine, we take its network dimensions as command line
# arguments.  For a SpiNN-2 or SpiNN-3 board these dimensions are 2 and 2. For
# a SpiNN-5 board the dimensions are 8 and 8.
mc.boot(int(sys.argv[2]), int(sys.argv[3]))

# We'll load our hello world application onto core 1 of chip (0, 0).  Note that
# we can't use core 0 because that is the monitor processor. As you might guess
# from the slightly odd syntax, you can load the application onto many cores
# and chips at once (see the rig docs) using this function. When doing this,
# Rig will efficiently load all cores simultaneously (and check they all got
# loaded successfully) so this is worth doing if you have more than one core to
# load!
mc.load_application("hello.aplx", {(0, 0): {1}})

# We'll now just wait for our application to reach the exit state before
# attempting to read the value back.
mc.wait_for_cores_to_reach_state("exit", 1)

# Finally we fetch and print out the contents of the IO buffer for the core we
# ran our application on to see what it printed!
print(mc.get_iobuf(x=0, y=0, p=1))
