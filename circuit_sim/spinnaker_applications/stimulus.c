/**
 * A stimulus generator which plays back a given stimulus.
 */

#include "sark.h"
#include "spin1_api.h"

#include "common.h"

struct {
	uint sim_length;
	uint output_key;
	uchar stimulus[];
} *config;

void on_tick(uint ticks, uint arg1) {
	// Terminate after the specified duration
	if (ticks >= config->sim_length) {
		spin1_exit(0);
		return;
	}
	
	// Get the next output value
	uint output = (config->stimulus[ticks / 8] >> (ticks % 8)) & 1;
	output = (output << 31) | config->output_key;
	
	// After a short (random) delay, send this value to anyone who cares...
	spin1_delay_us(128 + (spin1_rand() & 0xFF));
	spin1_send_mc_packet(output, 0, 0);
}

void c_main(void) {
	spin1_srand(spin1_get_id());
	
	// Discover the config for this core.
	// XXX: For simplicity, in this example application we (very infficiently)
	// access SDRAM directly via this pointer instead of DMAing it into local
	// memroy.
	uint core = spin1_get_core_id();
	config = sark_tag_ptr(core, 0);
	
	spin1_set_timer_tick(1000); // 1ms
	spin1_callback_on(TIMER_TICK, on_tick, 1);
	
	spin1_start(SYNC_WAIT);
}
