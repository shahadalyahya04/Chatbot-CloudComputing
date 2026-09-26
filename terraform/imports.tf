# These blocks adopt existing resources. Review the plan before applying.
# The old configuration is archived in ../terraform-retired after cleanup.
import {
  to = azurerm_postgresql_flexible_server.db
  id = "/subscriptions/743eef2c-30cc-4a0c-95a3-6107a83e7f2f/resourceGroups/chatbot-RG/providers/Microsoft.DBforPostgreSQL/flexibleServers/shahad-chatbot-pg"
}

import {
  to = azurerm_postgresql_flexible_server_database.appdb
  id = "/subscriptions/743eef2c-30cc-4a0c-95a3-6107a83e7f2f/resourceGroups/chatbot-RG/providers/Microsoft.DBforPostgreSQL/flexibleServers/shahad-chatbot-pg/databases/appdb"
}

import {
  to = azurerm_storage_account.sa
  id = "/subscriptions/743eef2c-30cc-4a0c-95a3-6107a83e7f2f/resourceGroups/chatbot-RG/providers/Microsoft.Storage/storageAccounts/chatbotdemo1"
}

import {
  to = azurerm_storage_container.sc
  id = "/subscriptions/743eef2c-30cc-4a0c-95a3-6107a83e7f2f/resourceGroups/chatbot-RG/providers/Microsoft.Storage/storageAccounts/chatbotdemo1/blobServices/default/containers/chatbot-files"
}
