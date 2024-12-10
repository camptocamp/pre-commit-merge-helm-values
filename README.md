# Merge HELM values

Pre-commit used to merge the HELM values to be able to pass only one file to HELM.

## Adding to your `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/camptocmap/pre-commit-merge-helm-values
    rev: <version> # Use the ref you want to point at
    hooks:
      - id: merge-helm-values
```
