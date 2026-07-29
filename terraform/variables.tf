variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix/tag all resources"
  type        = string
  default     = "spc"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "prod"
}

variable "github_owner" {
  description = "GitHub org/user that owns the repo (for OIDC trust policy)"
  type        = string
  default     = "M-Arslan-Bhatti"
}

variable "github_repo" {
  description = "GitHub repository name (for OIDC trust policy)"
  type        = string
  default     = "scientific-paper-comparison-engine"
}

variable "bedrock_llm_model" {
  description = "Bedrock LLM model ID used by the app (must match .env BEDROCK_LLM_MODEL)"
  type        = string
  default     = "global.anthropic.claude-sonnet-4-6"
}

variable "bedrock_embed_model" {
  description = "Bedrock embedding model ID used by the app (must match .env BEDROCK_EMBED_MODEL)"
  type        = string
  default     = "amazon.titan-embed-image-v1"
}

variable "pinecone_api_key" {
  description = "Pinecone API key, stored in Secrets Manager. Pass via TF_VAR_pinecone_api_key env var, never commit."
  type        = string
  sensitive   = true
}

variable "pinecone_index_name" {
  description = "Pinecone index name"
  type        = string
  default     = "paper-comparison-engine"
}

variable "pinecone_environment" {
  description = "Pinecone environment/region"
  type        = string
  default     = "us-east-1"
}

variable "app_runner_cpu" {
  description = "App Runner instance vCPU"
  type        = string
  default     = "1 vCPU"
}

variable "app_runner_memory" {
  description = "App Runner instance memory"
  type        = string
  default     = "2 GB"
}
