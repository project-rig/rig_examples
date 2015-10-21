/**
 * A simple inverter.
 */

#include "sark.h"
#include "spin1_api.h"

#include "common.h"

struct {
	uint sim_length;
	uint input_key;
	uint output_key;
} *config;

uint last_input = 0;

void on_tick(uint ticks, uint arg1) {
	// Terminate after the specified duration
	if (ticks >= config->sim_length)
		spin1_exit(0);
	
	// Calculate the new output value
	uint output = ((!last_input) << 31) | config->output_key;
	
	// After a short (random) delay, send this value to anyone who cares...
	spin1_delay_us(128 + (spin1_rand() & 0xFF));
	spin1_send_mc_packet(output, 0, 0);
}

void on_mc_packet(uint key, uint arg1) {
	if ((key & 0x7FFFFFFF) == config->input_key) {
		last_input = key >> 31;
	}
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
	
	spin1_callback_on(MC_PACKET_RECEIVED, on_mc_packet, -1);
	
	spin1_start(SYNC_WAIT);
}
