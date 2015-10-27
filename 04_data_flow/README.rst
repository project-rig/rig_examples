============================
Simple Data Flow Application
============================

SpiNNaker applications
----------------------

.. include:: transmitter.c
   :code: c

.. include:: receiver.c
   :code: c

Running the application
-----------------------

We now need to specify where on our SpiNNaker system these applications should
be loaded, *and* the routing table entries which will ensure that the packets
sent by our transmitters arrive at our receiver.  The applications will be
manually placed as shown below, with the routes shown by bold arrows:

IMAGE TO GO HERE

We'll load the transmitter application onto cores 1 and 2 of chip (1, 0), and
core 3 of chip (1, 1).  The receiver application will be loaded to core 1 of
(0, 1).

.. literalinclude:: data_flow.py
   :highlight: python
   :lines: 15-21

We need to create 1 routing entry on each of the chips that we're using. On
chip (1, 0) we need to send all packets north to chip (1, 1).  From (1, 1) we
need to send all packets west to (0, 1). On chip (0, 1) we need to route all
the packets to core 1.

.. note::
    We can assign multiple routing table entries to each chip by adding more
    items to the lists associated with each co-ordinate.

.. literalinclude:: data_flow.py
   :highlight: python
   :lines: 24-34

Loading the application occurs as before. We use ``load_routing_tables`` to
load the routing tables that we specified before.

We need to ensure that all applications are ready before they start execution.
This is achieved with ``spin1_start(SYNC_WAIT)`` in the C. This causes
applications to enter one of two alternating synchronisation states: ``sync0``
or ``sync1``. We then wait to ensure that all applications are in the first of
these states before sending a signal to start them.

Before reading out the output from the receiver we wait for the application to
stop as before.

.. literalinclude:: data_flow.py
   :highlight: python
   :lines: 37-
