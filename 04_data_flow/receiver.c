#include "spin1_api.h"

// XXX: Will be included as part of next version of SCAMP/SARK.
// Get a pointer to a tagged allocation. If the "app_id" parameter is zero
// uses the core's app_id.
void *sark_tag_ptr (uint tag, uint app_id)
{
  if (app_id == 0)
    app_id = sark_vec->app_id;
  
  return (void *) sv->alloc_tag[(app_id << 8) + tag];
}

// Stop execution after a period of time
void finish(uint arg0, uint arg1)
{
  spin1_delay_us(1000);
  spin1_exit(0);
}

// When we receive a packet we'll add the payload to this sum.
uint *sum;

void multicast_packet_received(uint key, uint payload)
{
  // Increase the sum
  // uint cpsr = spin1_fiq_disable();
  *sum += payload;
  // spin1_mode_restore(cpsr);

  // Prepare to stop the simulation
  spin1_schedule_callback(finish, 0, 0, 1);
}

void c_main(void)
{
  // Get the sum pointer
  sum = (uint *) sark_tag_ptr(spin1_get_core_id(), 0);

  // Set up the callback for receiving multicast packets with payloads.
  spin1_callback_on(MCPL_PACKET_RECEIVED,
                    multicast_packet_received,
                    -1);

  // Start when synchronised with other cores
  spin1_start(SYNC_WAIT);
}
