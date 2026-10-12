variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-central-1"
}

variable "instance_type" {
  description = "EC2 instance type. k3s, Postgres and the app need about 1.5 GB of RAM."
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key" {
  description = "Public SSH key (contents, not a path) for the ubuntu user."
  type        = string
}

variable "admin_cidr" {
  description = "CIDR allowed to reach SSH, e.g. your own IP as 203.0.113.7/32."
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be a valid CIDR and must not open SSH to the whole internet."
  }
}

variable "budget_alert_email" {
  description = "If set, a monthly AWS budget mails this address at 80% of budget_limit_usd."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  description = "Monthly budget in USD for the budget alert."
  type        = number
  default     = 20
}
