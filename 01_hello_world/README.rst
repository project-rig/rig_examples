Example 01: Hello World
=======================

In this classic example we make a SpiNNaker application which simply prints
"Hello, world!" on one core and then exits.

`Example Source code on GitHub <https://github.com/project-rig/rig_examples/tree/master/01_hello_world>`_

SpiNNaker application
---------------------

We start by writing the SpiNNaker
application itself which consists of a single call to ``io_printf`` in
``hello.c``.

.. literalinclude:: hello.c
    :language: c
    :lines: 5,7-10

This call writes our famous message to the "IO buffer",
an area of system memory which we can later read back from the host. This is
then compiled using the usual SpiNNaker-tools makefile to produce
``hello.aplx``::

    $ cd /path/to/spinnaker_tools
    $ source ./setup
    $ cd -
    $ make APP=hello

.. note::
    
    For those who don't have the ARM cross-compiler installed a precompiled binary
    is included with this example.

Host-side application
---------------------

Now that we have our compiled binary we must boot our SpiNNaker machine, load
our application onto a core and then read back the binary. We could do this
using the `ybug` command included with the low-level software tools but since
we're building up towards a real-world application, we'll use `Rig
<http://rig.readthedocs.org/en/stable/>`_.  Rig provides a higher-level Python
interface to SpiNNaker machines which is easily used as part of a larger
program, unlike ybug which is designed for interactive use as a debugger.

Before we start we must install the Rig library. The easiest way to do this is
via `PyPI <https://pypi.python.org/pypi/rig>`_ using pip::

    $ pip install rig

The ``hello.py`` contains a Python program which uses Rig to boot a SpiNNaker
machine, load our application and then print the result. We'll go through this
line by line below.

All control of a SpiNNaker machine is achieved via a Rig
:py:class:`~rig.machine_control.MachineController` which we import like so:

.. literalinclude:: hello.py
    :language: python
    :lines: 8

We create an instance with the hostname/IP address set to our SpiNNaker board,
taken from the command-line (to avoid having to hard-code things in our
program).

.. literalinclude:: hello.py
    :language: python
    :lines: 6,11

Next to boot the machine we use the
:py:meth:`~rig.machine_control.MachineController.boot` method, taking the width
and height of the machine to boot from the next two command line arguments. For
a SpiNN-2 or SpiNN-3 board these dimensions are 2 and 2. For a SpiNN-5 board
the dimensions are 8 and 8.

.. literalinclude:: hello.py
    :language: python
    :lines: 15

Next we'll load our application using the
:py:meth:`~rig.machine_control.MachineController.load_application` method.
This method loads our application onto core 1 of chip (0, 0), checks it was
loaded successfully and then starts the program executing before returning.
Note that this method can load an application onto many cores at once, hence
the slightly unusual syntax.

.. literalinclude:: hello.py
    :language: python
    :lines: 18

When a SpiNNaker application's ``c_main`` function returns, the application
goes into the ``exit`` state. By using
:py:meth:`~rig.machine_control.MachineController.wait_for_cores_to_reach_state`
we can wait for our hello world application to finish executing.

.. literalinclude:: hello.py
    :language: python
    :lines: 21

After our application has exited we can fetch and print out the contents of the
IO buffer for the core we ran our application on to see what it printed using
the :py:meth:`~rig.machine_control.MachineController.get_iobuf` method. (By
convention Rig uses the name ``p`` -- for processor -- when identifying cores.)

.. literalinclude:: hello.py
    :language: python
    :lines: 24

As a final step we must send the "stop" signal to SpiNNaker which frees up any
resources allocated during the runing of our application. In this case that
just means the memory allocated for the IO buffer.

.. literalinclude:: hello.py
    :language: python
    :lines: 27

We can finally run our script like so (for a SpiNN-5 board)::

    $ python hello.py my-spinn-5-board 8 8
    Hello, world!

Note that this script can take a little time while the boot is carried out. If
your board is already booted, you can comment out the boot line and the script
should run almost instantaneously.

.. note::
    
    Instead of incorporating the boot process into your scripts you can use the
    ``rig-boot`` command line utility to boot your machine first like so::
    
        $ rig-boot my-spinn-5-board --spin5
    
    For help see::
    
        $ rig-boot --help
    
    In later examples we'll use this instead of including the call to
    :py:meth:`~rig.machine_control.MachineController.boot` in our scripts.
