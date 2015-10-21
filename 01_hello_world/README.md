Hello World
===========

In this classic example we make a SpiNNaker application which simply prints
"Hello, world!" on one core and then exits. We start by writing the SpiNNaker
application itself which consists of a single call to `io_printf` in
[`hello.c`](hello.c):

    #include "sark.h"
    void c_main(void) {
        io_printf(IO_BUF, "Hello, world!\n");
    }

This call writes our famous message to the "IO buffer",
an area of system memory which we can later read back from the host. This is
then compiled using the usual SpiNNaker-tools makefile to produce
[`hello.aplx`](hello.aplx):

    $ make APP=hello

(For those who don't have the ARM cross-compiler installed a precompiled binary
is included with this example.)

Now that we have our compiled binary we must boot our SpiNNaker machine, load
our application onto a core and then read back the binary. We could do this
using the `ybug` command included with the low-level software tools but since
we're building up towards a real-world application, we'll use
[Rig](http://rig.readthedocs.org/). Rig provides a higher-level Python
interface to SpiNNaker machines which is easily used as part of a larger
program, unlike ybug which is designed for interactive use as a debugger.

Before we start we must install the Rig library. The easiest way to do this is
via [PyPI](https://pypi.python.org/pypi/rig) using pip:

    $ pip install rig

The [`hello.py`](hello.py) contains a Python program which uses Rig to boot a
SpiNNaker machine, load our application and then print the result. We'll go
through this line by line below.

All control of a SpiNNaker machine is achieved via a Rig
[`MachineController`](http://rig.readthedocs.org/en/stable/control.html#machinecontroller-spinnaker-control-api)
object so the first job is to import this and create an instance with the
hostname/IP address set to our SpiNNaker board. We take the hostname as an
argument from the command line to avoid the need for a hard-coded value in our
program.

    import sys
    from rig.machine_control import MachineController
    mc = MachineController(sys.argv[1])

Next to boot the machine we use the
[`boot`](http://rig.readthedocs.org/en/stable/control.html#rig.machine_control.MachineController.boot)
method, taking the width and height of the machine to boot from the next two
command line arguments:

    mc.boot(int(sys.argv[2]), int(sys.argv[3]))

If the machine couldn't be booted, this method will raise an exception,
otherwise it just quietly returns. Next we'll load our application using the
[`load_application`](http://rig.readthedocs.org/en/stable/control.html#rig.machine_control.MachineController.load_application)
method. This method loads our application onto core 1 of chip (0, 0), checks it
was loaded successfully and then starts the program executing before returning.
Note that this method can load an application onto many cores at once, hence
the slightly unusual syntax.

    mc.load_application("hello.aplx", {(0, 0): {1}})

Next we use
[`wait_for_cores_to_reach_state`](http://rig.readthedocs.org/en/stable/control.html#rig.machine_control.MachineController.wait_for_cores_to_reach_state)
to wait for our application to finish executing before we attempt to read the
IO buffer and see what message it wrote.

    mc.wait_for_cores_to_reach_state("exit", 1)

Finally we fetch and print out the contents of the IO buffer for the core we
ran our application on to see what it printed using the
[`get_iobuf`](http://rig.readthedocs.org/en/stable/control.html#rig.machine_control.MachineController.get_iobuf)
method. (By convention Rig uses the name `p` -- for processor -- when
identifying cores.)

    print(mc.get_iobuf(x=0, y=0, p=1))

We can finally run our script like so:

    $ python hello.py my-spinn-5-board 8 8
    Hello, world!

Note that this script can take a little time while the boot is carried out. If
your board is already booted, you can comment out the boot line and the script
should run almost instantaneously.
