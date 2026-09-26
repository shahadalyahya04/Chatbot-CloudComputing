output "db_endpoint" {
  value = azurerm_postgresql_flexible_server.db.fqdn
}

output "key_vault_name" {
  value = azurerm_key_vault.app.name
}

output "vm_identity_principal_id" {
  value = azapi_update_resource.vm_identity.output.identity.principalId
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.appdb.name
}

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
}

output "storage_blob_endpoint" {
  value = azurerm_storage_account.sa.primary_blob_endpoint
}

output "storage_container_name" {
  value = azurerm_storage_container.sc.name
}
