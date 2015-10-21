/**
 * A probe which records the value of an incoming signal.
 */

#include "sark.h"
#include "spin1_api.h"

#include "common.h"

struct {
	uint sim_length;
	uint input_key;
	uchar recording[];
} *config;

uint last_input = 0;

void on_tick(uint ticks, uint arg1) {
	// Terminate after the specified duration
	if (ticks >= config->sim_length)
		spin1_exit(0);
	
	// Record the value near the end of the timestep (so it is more likely we saw
	// the input value after it changed in the timestep).
	spin1_delay_us(700);
	config->recording[ticks/8] |= last_input << (ticks % 8);
}

void on_mc_packet(uint key, uint arg1) {
	if ((key & 0x7FFFFFFF) == config->input_key) {
		last_input = key >> 31;
	}
}


void c_main(void) {
	// Discover the config for this core.
	// XXX: For simplicity, in this example application we (very infficiently)
	// access SDRAM directly via this pointer instead of DMAing it into local
	// memroy.
	uint core = spin1_get_core_id();
	config = sark_tag_ptr(core, 0);
	
	// Initially clear the recording area
	for (int i = 0; i < (config->sim_length + 7)/8; i++)
		config->recording[i] = 0;
	
	spin1_set_timer_tick(1000); // 1ms
	spin1_callback_on(TIMER_TICK, on_tick, 1);
	
	spin1_callback_on(MC_PACKET_RECEIVED, on_mc_packet, -1);
	
	spin1_start(SYNC_WAIT);
}
