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

.. include:: data_flow.py
   :start-line: 14
   :end-line: 17

.. include:: data_flow.py
   :code: python
   :start-line: 18
   :end-line: 25

.. include:: data_flow.py
   :start-line: 27
   :end-line: 36

.. include:: data_flow.py
   :code: python
   :start-line: 37
   :end-line: 51

.. include:: data_flow.py
   :start-line: 53
   :end-line: 64

.. include:: data_flow.py
   :code: python
   :start-line: 65
   :end-line: 81
