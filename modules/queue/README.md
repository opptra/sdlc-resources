# Queue module

Recipe for one Cloud Tasks queue. `scripts/generate.py` copies this folder into an app at `infra/modules/queue/` when a component sets `queue`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

The queue name is the prefixed name from `service.yaml`. The runtime account receives `roles/cloudtasks.enqueuer` on that queue. A webhook receiver, when the component has one, is given `CLOUD_TASKS_QUEUE` as a plain environment variable by the generator.
