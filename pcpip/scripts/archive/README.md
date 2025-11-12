# Archive: Legacy CSV Maintenance Scripts

**Note**: These scripts are no longer used in the standard pipeline workflow. They were used for maintaining reference LoadData CSVs in S3 fixtures.

## Scripts

- `load_data_transform_p{3,7,9}.py` - Transform CSV paths to match pipeline output structure
- `load_data_check.py` - Validate file existence in LoadData CSVs
- `load_data_filter.py` - Filter CSVs by well/site

## Usage Examples

### Transform CSVs

```bash
BASE_DIR="data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed"
uv run scripts/archive/load_data_transform_p3.py \
    ${BASE_DIR}/input.csv ${BASE_DIR}/output.csv
```

### Check File Existence

```bash
uv run scripts/archive/load_data_check.py ${BASE_DIR}/load_data_pipeline9.csv
```

### Validate Generated CSVs Against Reference

Reference LoadData CSVs exist in S3 fixtures as validation artifacts for regression testing:

```bash
# Download fixture with reference CSVs
FIXTURE=fix-s1
aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/${FIXTURE}/ data/ --no-sign-request

# Generate samplesheet and LoadData CSVs
uv run scripts/samplesheet_generate.py data/Source1/images/Batch1/images \
  --output data/Source1/workspace/samplesheets/samplesheet1.csv \
  --wells "A1"

# Validate generated CSVs against reference CSVs
uv run scripts/load_data_generate.py data/Source1/workspace/samplesheets/samplesheet1.csv --validate
```
