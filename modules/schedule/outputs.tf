output "scheduler_jobs" {
  value = [for s in google_cloud_scheduler_job.job : s.name]
}
