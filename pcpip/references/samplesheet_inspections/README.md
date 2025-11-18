# Samplesheet inspections

```bash
echo "====== fix-l1 ======"
sed "s|read_csv('[^']*'|read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1-output/Source1/workspace/samplesheets/samplesheet1.csv'|g" scripts/samplesheet_inspect.sql | duckdb | tee references/samplesheet_inspections/fix-l1-samplesheet-inspect-output.txt

echo "====== fix-s1 ======"
sed "s|read_csv('[^']*'|read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-s1-output/Source1/workspace/samplesheets/samplesheet1.csv'|g" scripts/samplesheet_inspect.sql | duckdb | tee references/samplesheet_inspections/fix-s1-samplesheet-inspect-output.txt

echo "====== cpg0032 ======"
sed "s|read_csv('[^']*'|read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/cpg0032-output/Source1/workspace/samplesheets/samplesheet1.csv'|g" scripts/samplesheet_inspect.sql | duckdb | tee references/samplesheet_inspections/cpg0032-samplesheet-inspect-output.txt
```
