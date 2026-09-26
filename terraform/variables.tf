variable "subscription_id" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "vm_name" {
  type    = string
  default = "chatbot-vm"
}

variable "key_vault_name" {
  type    = string
  default = "shahad-chatbot-kv"
}
