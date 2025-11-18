-- Set the CSV source path (change URL below with find/replace)
-- URL: https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv

SELECT
    'Total rows' as metric,
    COUNT(*) as count
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
UNION
ALL
SELECT
    'Unique wells',
    COUNT(DISTINCT well)
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
UNION
ALL
SELECT
    'Unique plates',
    COUNT(DISTINCT plate)
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
UNION
ALL
SELECT
    'Unique batches',
    COUNT(DISTINCT batch)
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE);

SELECT
    arm,
    COUNT(*) as total_rows,
    COUNT(DISTINCT well) as unique_wells,
    COUNT(DISTINCT cycle) as unique_cycles,
    MIN(site) as min_site,
    MAX(site) as max_site
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
GROUP BY
    arm
ORDER BY
    arm;

SELECT
    well,
    COUNT(*) as total_rows,
    SUM(
        CASE
            WHEN arm = 'painting' THEN 1
            ELSE 0
        END
    ) as painting_rows,
    SUM(
        CASE
            WHEN arm = 'barcoding' THEN 1
            ELSE 0
        END
    ) as barcoding_rows
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
GROUP BY
    well
ORDER BY
    well;

SELECT
    cycle,
    COUNT(*) as total_rows,
    COUNT(DISTINCT well) as unique_wells,
    COUNT(DISTINCT site) as unique_sites
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
WHERE
    arm = 'barcoding'
GROUP BY
    cycle
ORDER BY
    cycle;

SELECT
    'Painting' as arm,
    well,
    COUNT(DISTINCT site) as unique_sites
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
WHERE
    arm = 'painting'
GROUP BY
    well
ORDER BY
    well
LIMIT
    4;

SELECT
    'Barcoding' as arm,
    well,
    cycle,
    COUNT(DISTINCT site) as unique_sites
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
WHERE
    arm = 'barcoding'
    AND well IN ('A1', 'A2')
GROUP BY
    well,
    cycle
ORDER BY
    well,
    cycle;

SELECT
    arm,
    channels,
    n_frames,
    COUNT(*) as row_count
FROM
    read_csv('https://nf-pooled-cellpainting-sandbox.s3.amazonaws.com/data/test-data/fix-l1/Source1/workspace/samplesheets/samplesheet1.csv', AUTO_DETECT=TRUE)
GROUP BY
    arm,
    channels,
    n_frames
ORDER BY
    arm,
    channels;
