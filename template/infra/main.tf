module "service" {
  # After copying this template into its own repository, replace this path with:
  # source = "git::https://github.com/opptra/sdlc.git//modules/cloud-run-service?ref=v1"
  source = "../../modules/cloud-run-service"

  project_id  = var.project_id
  region      = var.region
  name        = var.name
  environment = var.environment
  auth        = var.auth
  image       = var.image
}
