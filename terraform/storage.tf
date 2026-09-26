resource "azurerm_storage_account" "sa" {
  name                            = "chatbotdemo1"
  resource_group_name             = "chatbot-RG"
  location                        = "eastus"
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "sc" {
  name                  = "chatbot-files"
  storage_account_id    = azurerm_storage_account.sa.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}
