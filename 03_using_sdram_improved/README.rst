Example 03: Reading and Writing SDRAM - Improved
================================================

This example is functionally identical to the previous version but changes some
of the host-side code to use some of Rig's more advanced features which help
make the program more robust and concise. The SpiNNaker application remains
unchanged.

`Example Source code on GitHub <https://github.com/project-rig/rig_examples/tree/master/03_using_sdram_improved>`_

Reliably stopping applications
------------------------------

Now that we're starting to allocate machine resources and write more complex
programs it is important to be sure that the ``stop`` signal is sent to the
machine at the end of our application's execution, especially if our host-side
application crashes and exits prematurely. To aid with this, the
:py:class:`~rig.machine_control.MachineController` class provides an
:py:meth:`~rig.machine_control.MachineController.application` context manager
which will send the ``stop`` signal however the block is exited. In our
example, we just put the main body of our application logic in a ``with``
block:

.. literalinclude:: adder.py
    :language: python
    :lines: 18

File-like memory access
-----------------------

When working with SDRAM it can also be easy to accidentally access memory
outside the range of an allocated buffer. To provide safer and more conveninent
SDRAM access, the
:py:meth:`~rig.machine_control.MachineController.sdram_alloc_as_filelike`
method produces a file-like
:py:class:`~rig.machine_control.machine_controller.MemoryIO` object. This
object can then be used just like a conventional file using
:py:meth:`~rig.machine_control.machine_controller.MemoryIO.read`,
:py:meth:`~rig.machine_control.machine_controller.MemoryIO.write` and
:py:meth:`~rig.machine_control.machine_controller.MemoryIO.seek` methods. All
writes and reads to the file will be bounded to the allocated block of SDRAM
preventing accidental corruption of memory. Additionally, users of an
allocation need not know anything about the chip or address of the allocation
and in fact may be oblivious to the fact that they're using anything other than
a normal file.

.. literalinclude:: adder.py
    :language: python
    :lines: 21,27,36

Like files, reads and writes occur immediately after the previous read and
write and :py:meth:`~rig.machine_control.machine_controller.MemoryIO.seek` must
be used to cause a read/write to occur at a different location. Note that in
this case since the result value is written immediately after the two input
values we do no need to seek before reading.
