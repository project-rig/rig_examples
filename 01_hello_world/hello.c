/**
 * A program which prints Hello world into the "IO buffer" and exits.
 */

// The io_printf function we use below comes from the sark low-level SpiNNaker
// API and so we must include its header.
#include "sark.h"

void c_main(void) {
    // This nearly-standard printf function prints its message to one of many
    // locations. In this case we're printing to the "IO buffer" which is an
    // area of on-chip memory automatically allocated by the system software.
    // We will later read the contents of the IO buffer back from the host in
    // order to display it to the user.
    io_printf(IO_BUF, "Hello, world!\n");
}
