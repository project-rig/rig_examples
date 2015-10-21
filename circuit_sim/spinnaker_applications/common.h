#ifndef COMMON_H
#define COMMON_H

// XXX: Will be included as part of next version of SCAMP/SARK
// Get a pointer to a tagged allocation. If the "app_id" parameter is zero
// uses the core's app_id.
void *sark_tag_ptr (uint tag, uint app_id)
{
	if (app_id == 0)
		app_id = sark_vec->app_id;
	
	return (void *) sv->alloc_tag[(app_id << 8) + tag];
}

#endif
