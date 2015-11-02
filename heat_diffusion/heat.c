/**
 * Heat diffusion model SpiNNaker application.
 */

#include <stdint.h>
#include <stdbool.h>

#include "spin1_api.h"

#define DEBUG

// XXX: Will be included as part of next version of SCAMP/SARK
// Get a pointer to a tagged allocation. If the "app_id" parameter is zero
// uses the core's app_id.
void *sark_tag_ptr (uint tag, uint app_id)
{
  if (app_id == 0)
    app_id = sark_vec->app_id;
  
  return (void *) sv->alloc_tag[(app_id << 8) + tag];
}


////////////////////////////////////////////////////////////////////////////////
// Heat diffusion model variables/constants.
////////////////////////////////////////////////////////////////////////////////

// The number of neighbouring cells to this cell
#define NUM_NEIGHBOURS 4

// The routing key to use when multicasting this cell's temperature
uint32_t temperature_key;

// The routing keys used to indicate the temperature of the four neighbouring
// cells.
uint32_t neighbour_keys[NUM_NEIGHBOURS];

// The current temperature of this cell as an s15.16 fixed point
// number.
volatile int32_t temperature;

// The last known temperature of the neighbours of this cell as s15.16 fixed
// point numbers.
volatile int32_t neighbour_temperatures[NUM_NEIGHBOURS];

// The constant of thermal diffusivity as an s15.16 fixed point number.
volatile int32_t alpha;

////////////////////////////////////////////////////////////////////////////////
// Application variables/constants
////////////////////////////////////////////////////////////////////////////////

// The core number of this chip
uint32_t core_id;

// The shared memory block where all cores report their most recent
// temperatures.
volatile uint32_t *reported_temperatures;

// The length of the reported_temperatures array or zero if this core is not
// responsible for reporting temperature.
uint32_t num_reported_temperatures;

// The index of this core's slot in the reported_temperatures array.
uint32_t reported_temperature_slot;

// The number of msec over which all temperature reports are sent to the host
// via SDP
#define REPORT_PERIOD 64

// The phase (0-(REPORT_PERIOD-1)) in msec at which this chip will report back
// to the host.
uint32_t report_phase;

// The temperature reporting message
sdp_msg_t report_msg;

////////////////////////////////////////////////////////////////////////////////
// Implementation
////////////////////////////////////////////////////////////////////////////////

/**
 * Compute temperature change and multicast it to our immediate neighbours.
 */
void update_temperature(void)
{
  // Compute temperature change (note we also scale due to fixed-point)
  int32_t mean_neighbour_difference = 0;
  for (int i = 0; i < NUM_NEIGHBOURS; i++)
  {
    mean_neighbour_difference += neighbour_temperatures[i] - temperature;
  }
  mean_neighbour_difference /= NUM_NEIGHBOURS;
  temperature += (int32_t)((((int64_t)mean_neighbour_difference) * ((int64_t)alpha)) >> 16);
  
  // Transmit the new temperature to neighbours
  spin1_send_mc_packet(temperature_key, temperature, WITH_PAYLOAD);
}

/**
 * Report the current temperature back to the host. If not the reporting core,
 * this just means placing the current temperature in shared memory.
 */
void report_temperature(uint32_t time)
{
  // Update the current temperature in shared memory
  reported_temperatures[reported_temperature_slot] = temperature;
  
  // Send the temperature back to the host
  if (num_reported_temperatures && ((time % REPORT_PERIOD) == report_phase))
  {
    // Send reports back to the host via the nearest Ethernet chip using IPTag
    // 1
    report_msg.tag = 1;
    report_msg.dest_port = PORT_ETH;
    report_msg.dest_addr = sv->eth_addr;

    // Indicate the packet's origin as this chip/core
    report_msg.flags = 0x07;
    report_msg.srce_port = spin1_get_core_id();
    report_msg.srce_addr = spin1_get_chip_id();
    
    // Append the latest temperature info to the message
    int len = num_reported_temperatures * sizeof(reported_temperatures[0]);
    spin1_memcpy(report_msg.data, (void *)reported_temperatures, len);
    report_msg.length = sizeof (sdp_hdr_t) + sizeof (cmd_hdr_t) + len;

    // and send it with a 100ms timeout
    spin1_send_sdp_msg(&report_msg, 100);
  }
}

/**
 * Timer tick callback.
 */
void on_timer_tick(uint time, uint arg2)
{
  update_temperature();
  report_temperature(time);
}


/**
 * MC packet arrived callback.
 */
void on_mc_packet(uint key, uint payload)
{
  // Handle neighbour temperature reports.
  for (int i = 0; i < NUM_NEIGHBOURS; i++)
  {
    if (key == neighbour_keys[i])
    {
      neighbour_temperatures[i] = payload;
    }
  }
}

/**
 * An SDP packet arrived from host, these simply trigger the sending of an MC
 * packet with the key and payload specified in the SDP packet.
 */
void on_sdp_from_host(uint mailbox, uint port)
{
  sdp_msg_t *msg = (sdp_msg_t *)mailbox;
  if (msg->cmd_rc == 0)  // Send MC packet command
  {
    #ifdef DEBUG
      io_printf(IO_BUF,
                "Host requested MC packet with key %08x and payload %08x\n",
                msg->arg1,
                msg->arg2);
    #endif
    spin1_send_mc_packet(msg->arg1, msg->arg2, WITH_PAYLOAD);
  }
  spin1_msg_free(msg);
}


void c_main(void)
{
  core_id = spin1_get_core_id();
  
  // SDRAM tag 0 contains the shared temperature reporting memory
  reported_temperatures = sark_tag_ptr(0xFF, 0);
  
  // SDRAM tag core_id contains the configuration options for this core.
  struct {
    // 0 if no the reporting core, an integer giving the number of temperatures
    // to record otherwise.
    uint32_t num_reported_temperatures;
    
    // The constant of thermal diffusivity
    uint32_t alpha;
    
    // The routing key to use for this node
    uint32_t temperature_key;
    
    // The routing keys used by the immediate neighbours of this node
    uint32_t neighbour_keys[NUM_NEIGHBOURS];
  } *config_data = sark_tag_ptr(core_id, 0);
  
  // Copy provided config parameters
  num_reported_temperatures = config_data->num_reported_temperatures;
  alpha = config_data->alpha;
  temperature_key = config_data->temperature_key;
  for (int i = 0; i < NUM_NEIGHBOURS; i++)
  {
    neighbour_keys[i] = config_data->neighbour_keys[i];
  }
  
  // Each core gets a slot in the reported temperatures array
  reported_temperature_slot = core_id - 1;
  
  // The reporting phase of this chip will be simply its index in its 8x8
  // segment of the machine.
  uint32_t chip_id = spin1_get_chip_id();
  report_phase = ( (((chip_id >> 8) & 0x7) << 3)
                 | (((chip_id >> 0) & 0x7) << 0));
  
  // Initialise temperatures
  temperature = 0;
  for (int i = 0; i < NUM_NEIGHBOURS; i++)
  {
    neighbour_temperatures[i] = 0;
  }
  
  #ifdef DEBUG
    io_printf(IO_BUF, "reported_temperatures: %08x\n", reported_temperatures);
    io_printf(IO_BUF, "reported_temperature_slot: %d\n", reported_temperature_slot);
    io_printf(IO_BUF, "num_reported_temperatures: %d\n", num_reported_temperatures);
    io_printf(IO_BUF, "alpha: %08x\n", alpha);
    io_printf(IO_BUF, "temperature_key: %08x\n", temperature_key);
    for (int i = 0; i < NUM_NEIGHBOURS; i++)
    {
      io_printf(IO_BUF, "neighbour_keys[%d]: %08x\n", i, neighbour_keys[i]);
    }
  #endif
  
  // Setup callbacks
  spin1_set_timer_tick(1000); // 1 ms
  spin1_callback_on(MCPL_PACKET_RECEIVED, on_mc_packet, -1);
  spin1_callback_on(TIMER_TICK, on_timer_tick, 0);
  spin1_callback_on(SDP_PACKET_RX, on_sdp_from_host, 0);
  
  // Go!
  spin1_start(SYNC_WAIT);
}
