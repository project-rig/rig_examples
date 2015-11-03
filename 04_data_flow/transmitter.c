#include "sark.h"
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

void c_main(void)
{
  // Get the multicast key and value to transmit from SDRAM
  uint* data = (uint *) sark_tag_ptr(spin1_get_core_id(), 0);
  uint key = data[0];
  uint value = data[1];

  // Start when synchronised with other cores
  event_wait();

  // Transmit a packet using the key and value loaded from SDRAM
  spin1_send_mc_packet(key, value, WITH_PAYLOAD);
}
