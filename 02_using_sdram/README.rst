Example 02: Reading and Writing SDRAM
=====================================

Most interesting SpiNNaker applications require some sort of configuration data
to be loaded onto the machine or produce result data which must be read back
from the machine. Typically this is done by allocating and writing/reading
to/from the shared SDRAM on each SpiNNaker chip. In this example we'll write a
simple SpiNNaker application which, using a single core, adds two numbers
loaded in SDRAM and writes the answer back to SDRAM.

Much of the code in this example is unchanged from the previous example so we
will only discuss the cahnges.

`Example Source code on GitHub <https://github.com/project-rig/rig_examples/tree/master/02_hello_world>`_

Allocating SDRAM
----------------

When both the host and SpiNNaker need to access the same block of SDRAM, such
as when loading configuration data or reading back results, the SDRAM is
typically allocated by the host.  In this example we'll allocate some SDRAM on
chip (0, 0). We'll allocate a total of 12 bytes: 4 bytes (32 bits) for the two
values we want to be added and another 4 bytes for the result using
:py:meth:`~rig.machine_control.MachineController.sdram_alloc`:

.. literalinclude:: adder.py
    :language: python
    :lines: 18

The :py:meth:`~rig.machine_control.MachineController.sdram_alloc` method simply
returns the address of a block of SDRAM on chip 0, 0 which was allocated.

We also need to somehow inform the SpiNNaker application of this address. To do
this we can use the 'tag' using the argument to give an identifier to the
allocated memory block. The SpiNNaker application then uses the ``sark_tag_ptr`` function to look up the
address of an SDRAM block with a specified tag.

.. literalinclude:: adder.c
    :language: c
    :lines: 24

A tag is a user-defined identifier which must be unique to the SpiNNaker chip
and application. By convention the SDRAM allocated for applications running on
core 1 are given tag 1, those on core 2 given tag 2 and so on. This
conveninently means the same application binary can be loaded onto multiple
cores which can simply look up their core number to discover their unique SDRAM
allocation's address.

Reading and writing to SDRAM
----------------------------

We pick two random numbers to add together and write them to the SDRAM we just
allocated. Note that we must pack our values into bytes using Python's
:py:mod:`struct` module. Since SpiNNaker is little-endian we must be careful
to use the '<' format string.

.. literalinclude:: adder.py
    :language: python
    :lines: 21-23

Next we simply write the bytes to the allocated block of SDRAM using
:py:meth:`~rig.machine_control.MachineController.write`.

.. literalinclude:: adder.py
    :language: python
    :lines: 24

After we've allocated and writen our config data to SDRAM we can load our
application as usual. On the C side of our application, the SDRAM can be
accessed like any other memory.

.. literalinclude:: adder.c
    :language: c
    :lines: 27

.. warning::

    Though SpiNNaker's SDRAM *can* be accessed just like normal memory within a
    SpiNNaker application, this comes with a significant performance penalty.
    'Real' applications should use DMA to access SDRAM.

Once the application has exited, the host can read back using
:py:meth:`~rig.machine_control.MachineController.read` the answer and the
result unpacked and printed.

.. literalinclude:: adder.py
    :language: python
    :lines: 33-35

Finally, as in our last example we must send the ``stop`` signal using
:py:meth:`~rig.machine_control.MachineController.send_signal` to free up all
SpiNNaker resources. This is particularly important for this example since
until this is called, the SDRAM and tag number will remain allocated and
prevent this application running again.

.. literalinclude:: adder.py
    :language: python
    :lines: 38
