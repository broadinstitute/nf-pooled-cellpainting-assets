# nf-pooled-cellpainting-assets

Supporting assets and resources for the pooled cell painting Nextflow pipeline.

## Contents

Configuration files, reference data, and supporting materials for the [nf-pooled-cellpainting](https://github.com/nf-core/nf-pooled-cellpainting) pipeline.

## Test Data

**FIX-S1** test dataset is available for pipeline testing:

```bash
# Download FIX-S1 (small dataset - 3 wells, 4 sites, 3 cycles, ~36MB)
wget https://github.com/shntnu/starrynight/releases/download/v0.0.1/fix_s1_input.tar.gz
tar -xzf fix_s1_input.tar.gz
```

**Fixture Creation**: These datasets were created using scripts in the [StarryNight repository](https://github.com/broadinstitute/starrynight/tree/main/starrynight/tests/fixtures/integration/utils) that extract representative subsets from full pooled Cell Painting experiments.

**Related repositories:**
- [nf-pooled-cellpainting-infra](../nf-pooled-cellpainting-infra) - AWS CDK infrastructure
- [nf-pooled-cellpainting](https://github.com/nf-core/nf-pooled-cellpainting) - Main nf-core pipeline
