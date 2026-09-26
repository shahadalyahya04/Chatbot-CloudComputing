# Adopt the existing server. Do not reset its administrator password.
resource "azurerm_postgresql_flexible_server" "db" {
  name                          = "shahad-chatbot-pg"
  resource_group_name           = "chatbot-RG"
  location                      = "westus"
  version                       = "18"
  administrator_login           = "chatbotadmin"
  public_network_access_enabled = true
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  storage_tier                  = "P4"
  auto_grow_enabled             = false
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_postgresql_flexible_server_database" "appdb" {
  name      = "appdb"
  server_id = azurerm_postgresql_flexible_server.db.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    prevent_destroy = true
  }
}
