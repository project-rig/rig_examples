"""
py.test tests for the circuit_sim library.
"""

import pytest

from mock import Mock, call

from bitarray import bitarray

from rig.machine_control.machine_controller import SystemInfo, ChipInfo
from rig.machine_control.consts import AppState
from rig.links import Links

import circuit_sim
from circuit_sim import \
    Circuit, Signal, Device, Stimulus, Probe, Inv, TwoInputDevice

def test_device_input_output():
    # Tests that the Device object's input and output descriptors
    
    class TestDevice(Device):
        input_a = Device.Input(0)
        input_b = Device.Input(1)
        output_a = Device.Output(0)
        output_b = Device.Output(1)
        output_c = Device.Output(2)
    
    d = TestDevice("test_device.aplx")
    
    s0 = Signal(0)
    s1 = Signal(1)
    
    # Test that inputs can be set
    d.input_a = s0
    assert d.input_a is s0
    assert s0.source is None
    assert s0.sinks == [d]
    
    # Test that inputs can be changed
    d.input_a = s1
    assert d.input_a is s1
    assert s0.sinks == []
    assert s1.sinks == [d]
    
    # Test that inputs can be cleared
    d.input_a = None
    assert d.input_a is None
    assert s1.sinks == []
    
    # Test that signals can be inputs to multiple places
    d.input_a = s0
    d.input_b = s0
    assert s0.sinks == [d, d]
    d.input_a = None
    assert s0.sinks == [d]
    d.input_b = None
    assert s0.sinks == []
    
    # Test that outputs can be set
    d.output_a = s0
    assert s0.source is d
    assert s0.sinks == []
    
    # Test that outputs can be and changed
    d.output_a = s1
    assert s0.source is None
    assert s1.source is d
    
    # A signal cannot have multiple sources
    with pytest.raises(Exception):
        d.output_b = s1
    assert s1.source is d
    assert d.output_a is s1
    assert d.output_b is None
    
    # Test that outputs can be and cleared
    d.output_a = None
    assert s1.source is None

@pytest.mark.parametrize("length", [0, 100])
def test_device_sdram_required(length):
    # Tests that the sdram_required function of the device base class.
    
    class TestDevice(Device):
        input_a = Device.Input(0)
        input_b = Device.Input(1)
        output_a = Device.Output(0)
        output_b = Device.Output(1)
        output_c = Device.Output(2)
    
    d = TestDevice("test_device.aplx")
    d.input_a = None
    d.input_b = None
    d.output_a = None
    d.output_b = None
    d.output_c = None
    
    assert d.sdram_required(length) == 6 * 4

@pytest.mark.parametrize("length, length_packed",
                         [(0, b"\x00\x00\x00\x00"),
                          (128, b"\x80\x00\x00\x00")])
def test_device_write_config(length, length_packed):
    # Tests that the write_config function of the device base class.
    
    class TestDevice(Device):
        input_a = Device.Input(0)
        input_b = Device.Input(1)
        output_a = Device.Output(0)
    
    d = TestDevice("test_device.aplx")
    s0 = Signal(1)
    s1 = Signal(2)
    s2 = Signal(3)
    d.input_a = s0
    d.input_b = s1
    d.output_a = s2
    
    sdram = Mock()
    d.write_config(sdram, length)
    sdram.write.assert_called_once_with(length_packed +
                                        b"\x01\x00\x00\x00" +
                                        b"\x02\x00\x00\x00" +
                                        b"\x03\x00\x00\x00")


@pytest.mark.parametrize("values,packed_bits,bits",
                         [({}, b"\x00\x00", "000000000000000"),
                          ({0: 0}, b"\x00\x00", "000000000000000"),
                          ({0: 1}, b"\xFF\x7F", "111111111111111"),
                          ({8: 0}, b"\x00\x00", "000000000000000"),
                          ({8: 1}, b"\x00\x7F", "000000001111111"),
                          ({0: 1, 8: 0}, b"\xFF\x00", "111111110000000")])
def test_stimulus(values, packed_bits, bits):
    # Make sure the Stimulus device works as expected
    sig = Signal(1)
    stim = Stimulus(sig, values)
    
    # For a 15-step simulation only two bytes are required to hold all 15 bits
    # of step data.
    assert stim.sdram_required(15) == 4 + 4 + 2
    
    sdram = Mock()
    stim.write_config(sdram, 15)
    
    written_data = b""
    for call in sdram.write.mock_calls:
        written_data += call[1][0]
    
    assert written_data == (b"\x0F\x00\x00\x00" +
                            b"\x01\x00\x00\x00" +
                            packed_bits)
    
    assert stim.waveform == bitarray(bits)


def test_stimulus():
    # Make sure the Probe device works as expected
    sig = Signal(1)
    probe = Probe(sig)
    
    # For a 15-step simulation only two bytes are required to hold all 15 bits
    # of step data.
    assert probe.sdram_required(15) == 4 + 4 + 2
    
    sdram = Mock()
    sdram.read.return_value = b"\x7F\x3F"
    probe.read_results(sdram, 15)
    assert probe.waveform == bitarray("111111101111110")


def test_circuit_signal():
    c = Circuit()
    s0 = c.Signal()
    s1 = c.Signal()
    assert s0 is not s1
    assert s0.id != s1.id
    
    assert s0.id >= 0
    assert s1.id >= 0


def test_circuit_stimulus():
    c = Circuit()
    stim = c.Stimulus({0: 1, 1: 0})
    assert isinstance(stim, Stimulus)
    assert isinstance(stim.output, Signal)
    assert stim.values == {0: 1, 1: 0}

def test_circuit_probe():
    c = Circuit()
    s0 = c.Signal()
    probe = c.Probe(s0)
    assert isinstance(probe, Probe)
    assert probe.input is s0

def test_circuit_inv():
    c = Circuit()
    s0 = c.Signal()
    inv = c.Inv(s0)
    assert isinstance(inv, Inv)
    assert inv.input is s0
    assert isinstance(inv.output, Signal)

@pytest.mark.parametrize("name,lut,lut_word",
                         [("And", "0001", b"\x08\x00\x00\x00"),
                          ("Or", "0111", b"\x0E\x00\x00\x00"),
                          ("Xor", "0110", b"\x06\x00\x00\x00")])
def test_circuit_two_input_gate(name, lut, lut_word):
    c = Circuit()
    s0 = c.Signal()
    s1 = c.Signal()
    g = getattr(c, name)(s0, s1)
    assert isinstance(g, TwoInputDevice)
    assert g.lut == lut
    assert g.input_a is s0
    assert g.input_b is s1
    assert isinstance(g.output, Signal)
    assert g.sdram_required(0) == 4 + 4 + 4 + 4 + 4
    
    sdram = Mock()
    g.write_config(sdram, 0)
    assert sdram.write.mock_calls[-1] == call(lut_word)


def test_circuit_simulate(monkeypatch):
    
    mock_mc = Mock()
    
    class CtxtMgr(object):
        def __enter__(self):
            pass
        
        def __exit__(self, type, value, traceback):
            pass
    mock_mc.application.side_effect = CtxtMgr
    
    mock_mc.get_system_info.return_value = SystemInfo(1, 1, {
        (0, 0): ChipInfo(num_cores=18,
                         core_states=[AppState.run] + [AppState.idle]*17,
                         working_links=set(Links),
                         largest_free_sdram_block=110*1024*1024,
                         largest_free_sram_block=1024*1024)
    })
    
    mock_filelike = Mock()
    mock_mc.sdram_alloc_as_filelike.return_value = mock_filelike
    
    mock_mc_constructor = Mock(return_value=mock_mc)
    monkeypatch.setattr(circuit_sim, "MachineController", mock_mc_constructor)
    
    # A simple ring oscillator
    c = Circuit()
    osc = c.Inv()
    osc.input = osc.output
    
    c.simulate("test-machine", 64)
    
    # The simulation time tick attribute should be set up.
    assert c.ticks == list(range(64))
    
    # Correct hostname should have been used
    mock_mc_constructor.assert_called_once_with("test-machine")
    
    # Should have used context manager
    mock_mc.application.assert_called_once_with()
    
    # Should have fetched the machine
    mock_mc.get_system_info.assert_called_once_with()
    
    # Should have allocated SDRAM for the one and only device on chip (0, 0),
    # the only one, and on core 1.
    mock_mc.sdram_alloc_as_filelike.assert_called_once_with(
        osc.sdram_required(64), 1, buffer_size=0, clear=False, x=0, y=0)
    
    # Should have loaded only one application
    mock_mc.load_application.assert_called_once_with({
        osc.app_name: {(0, 0): set([1])}})
    
    # Should have written the config accordingly
    mock_filelike.write.assert_called_once_with(
        b"\x40\x00\x00\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00")
    
    # Should have loaded the routing tables
    assert mock_mc.load_routing_tables.called
    
    # Should have waited first for sync0 then exit
    mock_mc.wait_for_cores_to_reach_state.assert_has_calls([
        call("sync0", 1),
        call("exit", 1),
    ])
    
    # Should have sent a sync0 signal.
    mock_mc.send_signal.assert_called_once_with("sync0")
