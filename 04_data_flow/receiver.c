#include "spin1_api.h"

// Every time we receive a packet we'll add the payload to this sum, on every
// timestep we'll write the sum to IOBUF and reset it to zero.
uint sum;

void multicast_packet_received(uint key, uint payload)
{
  sum += payload;
}

void timer_tick(uint n_ticks, uint arg1)
{
  // If we've already run for ten ticks stop
  if (n_ticks >= 9)
  {
    spin1_exit(0);
  }

  // Print the sum to IOBUF then reset the value
  io_printf(IO_BUF, "Sum = %u\n", sum);
  sum = 0;
}

void c_main(void)
{
  // Initialise the sum
  sum = 0;

  // Set up the timer tick
  spin1_set_timer_tick(1000);
  spin1_callback_on(TIMER_TICK, timer_tick, 0);

  // Set up the callback for receiving multicast packets with payloads.
  spin1_callback_on(MCPL_PACKET_RECEIVED,
                    multicast_packet_received,
                    -1);

  // Start when synchronised with other cores
  spin1_start(SYNC_WAIT);
}
