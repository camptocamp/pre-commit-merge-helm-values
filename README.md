# Merge HELM values

Pre-commit used to merge the HELM values to be able to pass only one file to HELM.

Available options:

- `--helmfile` Unix style pathname pattern expansion used to find the Helmfile files, default is `**/helmfile-base.yaml`
- `--pre-commit` Run pre-commit hooks to call on the modified files (comma separated)
- `--pre-commit-skip` Skip the pre-commit hooks, default is `merge-helm-values`
- `--no-pre-commit` Do not run pre-commit hooks

If you use the `--no-pre-commit` option, be sure that the files are not modified by the pre-commit hooks.

The hook will not override the `values.yaml` file, if there is no content change (ignoring the comments), this is disable when the `--no-pre-commit` option is used.

## Adding to your `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/camptocamp/pre-commit-merge-helm-values
    rev: <version> # Use the ref you want to point at
    hooks:
      - id: merge-helm-values
```
