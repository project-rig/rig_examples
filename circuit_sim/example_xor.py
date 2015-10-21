"""
An example usage of the circuit_sim library. We describe an XOR function using
a simple sum-of-products.
"""

from circuit_sim import Circuit

circuit = Circuit()

# Two inputs which go through all possible combinations of 0 and 1.
a = circuit.Stimulus({0: 0,
                      10: 1,
                      20: 0,
                      30: 1})
b = circuit.Stimulus({0: 0,
                      20: 1})

# Define XOR as a sum-of-products
neg_a = circuit.Inv(a.output)
neg_b = circuit.Inv(b.output)

just_a = circuit.And(a.output, neg_b.output)
just_b = circuit.And(neg_a.output, b.output)

a_xor_b = circuit.Or(just_a.output, just_b.output)

output = circuit.Probe(a_xor_b.output)

# Simulate the circuit for 40 time steps
import sys
circuit.simulate(sys.argv[1], 40)

# Plot the waveform
import numpy as np
import matplotlib.pyplot as plt
plt.step(circuit.ticks, np.array(a.waveform) + 4)
plt.step(circuit.ticks, np.array(b.waveform) + 2)
plt.step(circuit.ticks, np.array(output.waveform))
plt.margins(y=0.1)
plt.show()

