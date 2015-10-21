"""
A simple SpiNNaker-based circuit simulator.
"""

import time
import struct
import os

from bitarray import bitarray

from rig import place_and_route
from rig.machine_control import MachineController
from rig.machine_control.utils import sdram_alloc_for_vertices
from rig.netlist import Net
from rig.machine import Cores, SDRAM


class Signal(object):
    def __init__(self, id):
        self.id = id
        self.source = None
        self.sinks = []

class Device(object):
    
    def __init__(self, app_name):
        self.app_name = os.path.join(os.path.dirname(__file__),
                                     "spinnaker_applications",
                                     app_name)
        self._inputs = {}
        self._outputs = {}
    
    def sdram_required(self, sim_length):
        """Get the SDRAM required for configuration and logging by this device.
        
        The default implementation just reserves a word for the simulation
        length, a word per input and output to store the signal ID.
        """
        return (1 + len(self._inputs) + len(self._outputs)) * 4
    
    def write_config(self, sdram, sim_length):
        """Write the required config data for this device.
        
        This default implementation simply writes the ID of each input and
        output (writing 0xFFFFFFFF for unconnected inputs/outputs).
        """
        data = [sim_length]
        data += [self._inputs[k].id
                 if self._inputs[k] is not None
                 else 0xFFFFFFFF
                 for k in sorted(self._inputs)]
        data += [self._outputs[k].id
                 if self._outputs[k] is not None
                 else 0xFFFFFFFF
                 for k in sorted(self._outputs)]
        sdram.write(struct.pack("<{}I".format(len(data)), *data))
    
    def read_results(self, sdram, sim_length):
        """Read the required result data for this device.
        
        This default implementation is empty (reads nothing).
        """
        pass
    
    class Input(object):
        def __init__(self, name=None):
            self._name = name
        
        def __get__(self, obj, type=None):
            return obj._inputs.get(self._name)
        
        def __set__(self, obj, new_signal):
            old_signal = obj._inputs.get(self._name)
            if old_signal is not None:
                old_signal.sinks.remove(obj)
            if new_signal is not None:
                new_signal.sinks.append(obj)
            obj._inputs[self._name] = new_signal
    
    class Output(object):
        def __init__(self, name=None):
            self._name = name
        
        def __get__(self, obj, type=None):
            return obj._outputs.get(self._name)
        
        def __set__(self, obj, new_signal):
            old_signal = obj._outputs.get(self._name)
            if old_signal is not None:
                old_signal.source = None
            if new_signal is not None:
                assert new_signal.source is None
                new_signal.source = obj
            obj._outputs[self._name] = new_signal

class Stimulus(Device):
    """A device which replays a predefined stimulus."""
    output = Device.Output(0)
    
    def __init__(self, output, values):
        super(Stimulus, self).__init__("stimulus.aplx")
        
        self.output = output
        self.values = values if values is not None else {}
        
        self.waveform = None
    
    def sdram_required(self, sim_length):
        length = super(Stimulus, self).sdram_required(sim_length)
        
        # Add the space required for the stimulus data
        length += (sim_length + 7) // 8
        
        return length
    
    def write_config(self, sdram, sim_length):
        super(Stimulus, self).write_config(sdram, sim_length)
        
        self.waveform = bitarray(endian="little")
        cur_value = 0
        change_times = sorted(self.values)
        for bit in range(sim_length):
            if change_times and change_times[0] == bit:
                cur_value = self.values[bit]
                change_times.pop(0)
            self.waveform.append(cur_value)
        sdram.write(self.waveform.tobytes())

class Probe(Device):
    """A probe which records the value of a signal."""
    input = Device.Input(0)
    
    def __init__(self, input=None):
        super(Probe, self).__init__("probe.aplx")
        
        self.input = input
        self.waveform = None
    
    def sdram_required(self, sim_length):
        length = super(Probe, self).sdram_required(sim_length)
        
        # Add the space required for the recorded data
        length += (sim_length + 7) // 8
        
        return length
    
    def read_results(self, sdram, sim_length):
        super(Probe, self).read_results(sdram, sim_length)
        num_bytes = (sim_length + 7) // 8
        self.waveform = bitarray(endian="little")
        self.waveform.frombytes(sdram.read(num_bytes))
        self.waveform = self.waveform[:sim_length]

class Inv(Device):
    """An inverter."""
    input = Device.Input(0)
    output = Device.Output(0)
    
    def __init__(self, output, input=None):
        super(Inv, self).__init__("inv.aplx")
        
        self.output = output
        self.input = input

class TwoInputDevice(Device):
    """A generic 2-input gate based on a lookup table."""
    
    input_a = Device.Input(0)
    input_b = Device.Input(1)
    output = Device.Output(0)
    
    def __init__(self, lut, output, input_a=None, input_b=None):
        super(TwoInputDevice, self).__init__("two_input_gate.aplx")
        
        self.lut = lut
        
        self.output = output
        self.input_a = input_a
        self.input_b = input_b
    
    def sdram_required(self, sim_length):
        length = super(TwoInputDevice, self).sdram_required(sim_length)
        
        # Add a word for the LUT (just the bottom 4 bits...)
        length += 4
        
        return length
    
    def write_config(self, sdram, sim_length):
        super(TwoInputDevice, self).write_config(sdram, sim_length)
        
        self.waveform = bitarray(self.lut, endian="little")
        sdram.write(self.waveform.tobytes().ljust(4, b"\x00"))

class Circuit(object):
    """A circuit to be simulated."""
    
    def __init__(self):
        self._devices = []
        self._signals = []
        
        self.ticks = None
    
    def Signal(self):
        """Get a new unique signal."""
        s = Signal(len(self._signals))
        self._signals.append(s)
        return s
    
    def Stimulus(self, values):
        """A device which provides a series of one-bit stimulus values.
        
        Parameters
        ----------
        values : dict
            A dictionary where each entry gives the value of the stimulus at
            the time specified by the key.
        """
        s = Stimulus(self.Signal(), values)
        self._devices.append(s)
        return s
    
    def Probe(self, input=None):
        """A device which provides a series of one-bit stimulus values.
        
        Parameters
        ----------
        input : :py:class:`Signal`
            The signal to probe.
        """
        p = Probe(input)
        self._devices.append(p)
        return p
    
    def Inv(self, input=None):
        """An inverter.
        
        Parameters
        ----------
        input : :py:class:`Signal`
            The signal to invert.
        """
        i = Inv(self.Signal(), input)
        self._devices.append(i)
        return i
    
    def And(self, input_a=None, input_b=None):
        """An AND gate.
        
        Parameters
        ----------
        input_a : :py:class:`Signal`
        input_b : :py:class:`Signal`
            The signals to AND together.
        """
        a = TwoInputDevice("0001", self.Signal(), input_a, input_b)
        self._devices.append(a)
        return a
    
    def Or(self, input_a=None, input_b=None):
        """An OR gate.
        
        Parameters
        ----------
        input_a : :py:class:`Signal`
        input_b : :py:class:`Signal`
            The signals to OR together.
        """
        o = TwoInputDevice("0111", self.Signal(), input_a, input_b)
        self._devices.append(o)
        return o
    
    def Xor(self, input_a=None, input_b=None):
        """An XOR gate.
        
        Parameters
        ----------
        input_a : :py:class:`Signal`
        input_b : :py:class:`Signal`
            The signals to XOR together.
        """
        o = TwoInputDevice("0110", self.Signal(), input_a, input_b)
        self._devices.append(o)
        return o
    
    def simulate(self, hostname, sim_length=128):
        """Simulate the current circuit for the specified number of timer
        ticks.
        """
        # We define the set of ticks for convenience when plotting
        self.ticks = list(range(sim_length))
        
        # We define our simulation within the following "with" block which
        # causes the SpiNNaker applications and their associated resources to
        # be automatically freed at the end of simulation or in the event of
        # some failure.
        mc = MachineController(hostname)
        with mc.application():
            # Step 1: Determine what resources are available in the supplied
            # SpiNNaker machine.
            machine = mc.get_machine()
            
            # Step 2: Describe the simulation as a graph of SpiNNaker applications
            # which Rig will place in the machine
            
            # Each device uses a single core and consumes some amount of SDRAM for
            # config and result data.
            vertices_resources = {
                d: {Cores: 1, SDRAM: d.sdram_required(sim_length)}
                for d in self._devices
            }
            vertices_applications = {d: d.app_name for d in self._devices}
            
            # We'll make a net for every signal in our circuit. Packets will have
            # their bottom 31-bits be the unique signal ID and the top bit will
            # contain the state of the signal (and is thus masked off here)
            net_keys = {Net(s.source, s.sinks): (s.id, 0x7FFFFFFF)
                        for s in self._signals}
            nets = list(net_keys)
            
            # Step 3: Place and route the application graph we just described
            placements, allocations, application_map, routing_tables = \
                place_and_route.wrapper(vertices_resources, vertices_applications,
                                        nets, net_keys, machine)
            
            # Step 4: Allocate SDRAM for each device. We use the
            # `sdram_alloc_for_vertices` utility method to allocate SDRAM on
            # the chip each device has been placed on, tagging the allocation
            # with the core number so the application can discover the
            # allocation using `sark_tag_ptr`. The returned file-like objects
            # may then conveniently be used to read/write to this allocated
            # region of SDRAM.
            # A dictionary {Device: filelike} is returned.
            device_sdram_filelikes = sdram_alloc_for_vertices(mc, placements, allocations)
            
            # Step 5: Write the config data to SDRAM for all devices.
            for d in self._devices:
                d.write_config(device_sdram_filelikes[d], sim_length)
            
            # Step 6: Load application binaries and routing tables
            mc.load_application(application_map)
            mc.load_routing_tables(routing_tables)
            
            # Step 7: Wait for all applications to reach the initial sync0
            # barrier and then start the simulation.
            mc.wait_for_cores_to_reach_state("sync0", len(self._devices))
            mc.send_signal("sync0")
            
            # Step 8: Wait for the simulation to run and all cores to finish
            # executing and enter the EXIT state.
            time.sleep(0.001 * sim_length)
            mc.wait_for_cores_to_reach_state("exit", len(self._devices))
            
            # Step 9: Retrieve any results and we're done!
            for d in self._devices:
                d.read_results(device_sdram_filelikes[d], sim_length)
