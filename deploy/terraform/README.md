# Cloud Run deployment as Terraform

Infrastructure-as-Code companion to `deploy/deploy_cloud_run.sh`. Use either:
the shell script for a one-shot deploy, this module when you want the state
declarative and reviewable.

## Layout

- `main.tf` — Artifact Registry repo + Cloud Run v2 service + optional public invoker binding
- `variables.tf` — inputs (project, region, image URI, resource limits, scaling)

## Usage

Build and push the image first (the module deploys an existing tag, it does
not build):

```bash
../deploy_cloud_run.sh    # or your own build + push
```

Then apply:

```bash
cd deploy/terraform
terraform init
terraform apply \
  -var project_id=YOUR_PROJECT \
  -var image_uri=europe-west2-docker.pkg.dev/YOUR_PROJECT/griddemand/grid-demand-api:SHA
```

The service URL is exposed as an output:

```bash
terraform output service_url
```

## Why Cloud Run + scale-to-zero

Day-ahead forecasting is a low-QPS workload — a few requests per hour from a
scheduled caller, not a user-facing site. Scale-to-zero gets the hosting cost
to essentially free at idle, and the 10–15s cold start is inside the SLA of
the downstream consumer (schedulers, not humans). If a warm-path SLA is ever
needed, set `min_instances = 1` and everything else stays the same.
