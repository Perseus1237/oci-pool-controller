data "oci_core_instance_pools" "discovery" {
  # Legacy nonempty allowlists remain authoritative, including older saved
  # stacks that have not yet set the new discovery switch explicitly.
  count          = var.auto_discover_pools && length(var.pools) == 0 ? 1 : 0
  compartment_id = var.pool_compartment_ocid
}

module "enrollment" {
  source = "./modules/enrollment"

  auto_discover_pools   = var.auto_discover_pools
  scope_id              = var.scope_id
  default_pool_max_size = var.default_pool_max_size
  pool_overrides        = var.pool_overrides
  pools                 = var.pools
  candidates = [for pool in try(data.oci_core_instance_pools.discovery[0].instance_pools, []) : {
    id             = pool.id
    display_name   = pool.display_name
    compartment_id = pool.compartment_id
    state          = pool.state
    freeform_tags  = coalesce(pool.freeform_tags, {})
  }]
}
