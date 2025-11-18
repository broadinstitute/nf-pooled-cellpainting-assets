# Dataset-Specific Pipelines

Sample production dataset pipelines, tracked here to document any changes needed for Nextflow pipeline compatibility.

## Download Example

```bash
# cpg0032 Batch3
aws s3 sync \
  s3://cellpainting-gallery/cpg0032-pooled-rare/broad/workspace/pipelines/2025_06_23_Batch3/ \
  pipelines-datasets/cpg0032/2025_06_23_Batch3/ \
  --no-sign-request
```

Browse datasets: https://cellpainting-gallery.s3.amazonaws.com/index.html
