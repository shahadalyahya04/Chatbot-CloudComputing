data "azurerm_client_config" "current" {}

data "azurerm_resource_group" "app" {
  name = var.resource_group_name
}

# Add an identity to the existing VM without recreating it.
resource "azapi_update_resource" "vm_identity" {
  type        = "Microsoft.Compute/virtualMachines@2024-07-01"
  resource_id = "${data.azurerm_resource_group.app.id}/providers/Microsoft.Compute/virtualMachines/${var.vm_name}"
  body = {
    identity = { type = "SystemAssigned" }
  }
  response_export_values = ["identity.principalId"]
}

resource "azurerm_key_vault" "app" {
  name                       = var.key_vault_name
  location                   = data.azurerm_resource_group.app.location
  resource_group_name        = data.azurerm_resource_group.app.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_role_assignment" "vm_secrets_reader" {
  scope                            = azurerm_key_vault.app.id
  role_definition_name             = "Key Vault Secrets User"
  principal_id                     = azapi_update_resource.vm_identity.output.identity.principalId
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "secrets_manager" {
  scope                = azurerm_key_vault.app.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}
