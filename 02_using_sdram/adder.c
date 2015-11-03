/**
 * A program which simply adds together two numbers in SDRAM and writes the
 * result striaght afterwards.
 */

#include <stdint.h>

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
  // Get the address of the allocated SDRAM block
  uint32_t *numbers = sark_tag_ptr(spin1_get_core_id(), 0);
  
  // Add the two numbers together and store the result back into SDRAM.
  numbers[2] = numbers[0] + numbers[1];
}
