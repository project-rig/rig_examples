#include "spin1_api.h"

void timer_tick(uint n_ticks, uint arg1)
{
  // If we've transmitted ten packets already then stop transmitting.
  if (n_ticks >= 9)
  {
    spin1_exit(0);
  }

  // Transmit a packet including the timer tick number as the payload.
  spin1_send_mc_packet(0x0000ffff, n_ticks, WITH_PAYLOAD);
}

void c_main(void)
{
  // Set up the timer tick
  spin1_set_timer_tick(1000);  // Tick every millisecond
  spin1_callback_on(TIMER_TICK, timer_tick, 0);

  // Start when synchronised with other cores
  spin1_start(SYNC_WAIT);
}
