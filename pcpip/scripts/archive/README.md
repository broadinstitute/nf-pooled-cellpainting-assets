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
