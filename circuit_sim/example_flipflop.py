"""
An example usage of the circuit_sim library. We describe an RS-flip-flop.
"""

from circuit_sim import Circuit

circuit = Circuit()

# Two inputs which go through all possible combinations of 0 and 1.
r = circuit.Stimulus({0: 0,
                      10: 1,
                      20: 0,
                      50: 1,
                      60: 0})
s = circuit.Stimulus({0: 0,
                      30: 1,
                      40: 0,
                      70: 1,
                      80: 0})

o0 = circuit.Or()
o1 = circuit.Or()

o0_inv = circuit.Inv(o0.output)
o1_inv = circuit.Inv(o1.output)

o0.input_a = r.output
o1.input_a = s.output

o0.input_b = o1_inv.output
o1.input_b = o0_inv.output

q = circuit.Probe(o0_inv.output)
q_inv = circuit.Probe(o1_inv.output)

# Simulate the circuit for 90 time steps
import sys
circuit.simulate(sys.argv[1], 90)

# Plot the waveform
import numpy as np
import matplotlib.pyplot as plt
plt.step(circuit.ticks, np.array(r.waveform) + 6)
plt.step(circuit.ticks, np.array(s.waveform) + 4)
plt.step(circuit.ticks, np.array(q_inv.waveform) + 2)
plt.step(circuit.ticks, np.array(q.waveform))
plt.margins(y=0.1)
plt.show()


