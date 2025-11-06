# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Pipeline 7 QC: Barcode Preprocessing Analysis
#
# Analyzes barcode library composition, calling quality, and spatial distribution
# from Pipeline 7 preprocessing outputs.
#
# Based on the original PCPIP notebook by Erin Weisbart.

# %% [markdown]
# ## Setup and Configuration

# %%
import os
from pathlib import Path
import pandas as pd
import seaborn as sns
import datetime
import matplotlib.pyplot as plt

# %matplotlib inline

# %% tags=["parameters"]
# PAPERMILL PARAMETERS
# This cell is tagged as "parameters" for Papermill injection
# When running with papermill, these values will be overridden
# When running interactively, edit these defaults directly

# Analysis parameters
numcycles = 3
imperwell = None  # Will be auto-detected from data if None

# Input/output paths (edit these for interactive use)
input_dir = "../data/Source1/images/Batch1/images_corrected/barcoding/Plate1"
output_dir = "../data/Source1/workspace/qc_reports/7_preprocessing/Plate1"
barcode_library_path = "../data/Source1/workspace/metadata/Barcodes.csv"

# Acquisition geometry for spatial plot (optional)
# For square: set both rows and columns
# For circular: set row_widths as comma-separated list
rows = 2
columns = 2
row_widths = None  # Example: [5, 11, 17, 19, 23, 25, 27, 29, ...]

# %%
# Process parameters and create output directory
Path(output_dir).mkdir(parents=True, exist_ok=True)

print("Configuration:")
print(f"  numcycles: {numcycles}")
print(f"  imperwell: {imperwell if imperwell is not None else 'auto-detect'}")
print(f"  input_dir: {input_dir}")
print(f"  output_dir: {output_dir}")
print(f"  barcode_library_path: {barcode_library_path}")
if rows and columns:
    print(f"  geometry: square {rows}x{columns}")
elif row_widths:
    print(f"  geometry: circular with {len(row_widths)} rows")

# %% [markdown]
# ## Helper Functions


# %%
def merge_csvs(csvfolder, filename, column_list=None):
    """
    Merge CSV files from multiple subdirectories.

    Original function from Erin's notebook - handles well-based directory structure.
    """
    df_dict = {}
    count = 0
    folderlist = os.listdir(csvfolder)
    print(count, datetime.datetime.ctime(datetime.datetime.now()))
    for eachfolder in folderlist:
        if os.path.isfile(os.path.join(csvfolder, eachfolder, filename)):
            if not column_list:
                df_dict[eachfolder] = pd.read_csv(
                    os.path.join(csvfolder, eachfolder, filename), index_col=False
                )
            else:
                df_dict[eachfolder] = pd.read_csv(
                    os.path.join(csvfolder, eachfolder, filename),
                    index_col=False,
                    usecols=column_list,
                )
            count += 1
            if count % 500 == 0:
                print(count, datetime.datetime.ctime(datetime.datetime.now()))
    print(count, datetime.datetime.ctime(datetime.datetime.now()))
    df_merged = pd.concat(df_dict, ignore_index=True)
    print("done concatenating at", datetime.datetime.ctime(datetime.datetime.now()))

    return df_merged


# %% [markdown]
# ## sgRNA Library Analysis

# %%
print(f"Loading barcode library from: {barcode_library_path}")
bc_df = pd.read_csv(barcode_library_path)

# Check for expected columns (handle both 'Gene' and 'gene_symbol')
if "sgRNA" not in bc_df.columns:
    raise ValueError("Barcode library must contain 'sgRNA' column")

# Normalize gene column name to 'Gene'
if "gene_symbol" in bc_df.columns:
    bc_df = bc_df.rename(columns={"gene_symbol": "Gene"})
elif "Gene" not in bc_df.columns:
    raise ValueError("Barcode library must contain 'Gene' or 'gene_symbol' column")

gene_col = "Gene"
barcode_col = "sgRNA"

print(len(bc_df), "total barcodes")
print(f"Library columns: {bc_df.columns.tolist()}")

# %% [markdown]
# ### Homopolymeric Repeat Detection

# %%
# Describe barcodes - check for homopolymeric repeats
rep5 = sum(
    [
        any(repeat in read for repeat in ["AAAAA", "CCCCC", "GGGGG", "TTTTT"])
        for read in bc_df["sgRNA"]
    ]
)
rep6 = sum(
    [
        any(repeat in read for repeat in ["AAAAAA", "CCCCCC", "GGGGGG", "TTTTTT"])
        for read in bc_df["sgRNA"]
    ]
)
rep7 = sum(
    [
        any(repeat in read for repeat in ["AAAAAAA", "CCCCCCC", "GGGGGGG", "TTTTTTT"])
        for read in bc_df["sgRNA"]
    ]
)
print("For full read")
print(rep5, "barcodes with 5 repeats", rep5 / len(bc_df), "% 5 repeats")
print(rep6, "barcodes with 6 repeats", rep6 / len(bc_df), "% 6 repeats")
print(rep7, "barcodes with 7 repeats", rep7 / len(bc_df), "% 7 repeats")

rep5_10nt = sum(
    [
        any(repeat in read[:10] for repeat in ["AAAAA", "CCCCC", "GGGGG", "TTTTT"])
        for read in bc_df["sgRNA"]
    ]
)
rep6_10nt = sum(
    [
        any(repeat in read[:10] for repeat in ["AAAAAA", "CCCCCC", "GGGGGG", "TTTTTT"])
        for read in bc_df["sgRNA"]
    ]
)
rep7_10nt = sum(
    [
        any(
            repeat in read[:10]
            for repeat in ["AAAAAAA", "CCCCCCC", "GGGGGGG", "TTTTTTT"]
        )
        for read in bc_df["sgRNA"]
    ]
)
print("For 10 nt read")
print(rep5_10nt, "barcodes with 5 repeats", rep5_10nt / len(bc_df), "% 5 repeats")
print(rep6_10nt, "barcodes with 6 repeats", rep6_10nt / len(bc_df), "% 6 repeats")
print(rep7_10nt, "barcodes with 7 repeats", rep7_10nt / len(bc_df), "% 7 repeats")

# Save repeat statistics
with open(Path(output_dir) / "library_repeat_stats.txt", "w") as f:
    f.write("Homopolymeric Repeat Analysis\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Total barcodes in library: {len(bc_df)}\n\n")
    f.write("For full read:\n")
    f.write(f"  5-mer repeats: {rep5} barcodes ({rep5 / len(bc_df) * 100:.2f}%)\n")
    f.write(f"  6-mer repeats: {rep6} barcodes ({rep6 / len(bc_df) * 100:.2f}%)\n")
    f.write(f"  7-mer repeats: {rep7} barcodes ({rep7 / len(bc_df) * 100:.2f}%)\n\n")
    f.write("For 10 nt read:\n")
    f.write(
        f"  5-mer repeats: {rep5_10nt} barcodes ({rep5_10nt / len(bc_df) * 100:.2f}%)\n"
    )
    f.write(
        f"  6-mer repeats: {rep6_10nt} barcodes ({rep6_10nt / len(bc_df) * 100:.2f}%)\n"
    )
    f.write(
        f"  7-mer repeats: {rep7_10nt} barcodes ({rep7_10nt / len(bc_df) * 100:.2f}%)\n"
    )

print(f"\nRepeat statistics saved to: {Path(output_dir) / 'library_repeat_stats.txt'}")

# %% [markdown]
# ### Nucleotide Frequency by Cycle (Library)

# %%
dflist = []
for cycle in range(1, numcycles + 1):
    bc_df["PerCycle"] = bc_df["sgRNA"].str.slice(cycle - 1, cycle)
    BarcodeCat = bc_df["PerCycle"].str.cat()
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "A",
            "Frequency": float(BarcodeCat.count("A")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "C",
            "Frequency": float(BarcodeCat.count("C")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "G",
            "Frequency": float(BarcodeCat.count("G")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "T",
            "Frequency": float(BarcodeCat.count("T")) / float(len(BarcodeCat)),
        }
    )
df_parsed = pd.DataFrame(dflist)
g = sns.lineplot(x="Cycle", y="Frequency", hue="Nucleotide", data=df_parsed)
g.set_ylim([0.1, 0.5])
handles, labels = g.get_legend_handles_labels()
g.legend(handles=handles[0:], labels=labels[0:])
g.set_xticks(list(range(1, numcycles + 1)))
plt.title("Nucleotide Frequency by Cycle in Barcode Library")
plt.tight_layout()
plt.savefig(
    Path(output_dir) / "library_nucleotide_frequency.png", dpi=150, bbox_inches="tight"
)
plt.show()

# %% [markdown]
# ## Barcode Calling

# %% [markdown]
# ### Load Barcode Calling Data from Pipeline 7

# %%
csvfolder = input_dir
filename = "BarcodePreprocessing_Foci.csv"
column_list = [
    "ImageNumber",
    "ObjectNumber",
    "Metadata_Plate",
    "Metadata_Site",
    "Metadata_Well",
    "Metadata_Well_Value",
    "Barcode_BarcodeCalled",
    "Barcode_MatchedTo_Barcode",
    "Barcode_MatchedTo_GeneCode",
    "Barcode_MatchedTo_ID",
    "Barcode_MatchedTo_Score",
]

print(f"Loading data from: {csvfolder}")
df_foci = merge_csvs(csvfolder, filename, column_list)

print(f"Loaded {len(df_foci)} barcode foci")
print(f"Columns: {df_foci.columns.tolist()}")

# Auto-detect imperwell if not set
if imperwell is None:
    imperwell = df_foci["Metadata_Site"].max() + 1
    print(f"Auto-detected imperwell: {imperwell}")

print("\nFirst few rows:")
print(df_foci.head())

# %% [markdown]
# ### Perfect Match Statistics and Score Distribution

# %%
# Useful dataframe manipulations
df_foci.sort_values(by=["Metadata_Well_Value", "Metadata_Site"], inplace=True)
df_foci["well-site"] = (
    df_foci["Metadata_Well"] + "-" + df_foci["Metadata_Site"].astype(str)
)
df_foci_well_groups = df_foci.groupby("Metadata_Well_Value")

# Calculate perfect match percentage (dividing by scores > 0)
perfect_count = sum(df_foci["Barcode_MatchedTo_Score"] == 1)
matched_count = sum(df_foci["Barcode_MatchedTo_Score"] > 0)
perfect_percent = perfect_count * 100.0 / matched_count

print(f"{perfect_percent:.2f} percent perfect overall")
print(f"{perfect_count} count perfect foci")

# Save statistics
with open(Path(output_dir) / "barcode_calling_stats.txt", "w") as f:
    f.write("Barcode Calling Quality Statistics\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Total foci with matches: {matched_count}\n")
    f.write(f"Perfect matches (score=1): {perfect_count} ({perfect_percent:.2f}%)\n")

print(f"\nStatistics saved to: {Path(output_dir) / 'barcode_calling_stats.txt'}")

# Overall score distribution
sns.displot(df_foci["Barcode_MatchedTo_Score"], kde=False)
plt.title("Barcode Match Score Distribution")
plt.tight_layout()
plt.savefig(
    Path(output_dir) / "barcode_score_distribution.png", dpi=150, bbox_inches="tight"
)
plt.show()

# %% [markdown]
# ### Per-Well Score Distribution

# %%
# Per-well score distribution using displot with col parameter
# Handle Metadata_Well_Value if it exists, otherwise use Metadata_Well
col_var = (
    "Metadata_Well_Value"
    if "Metadata_Well_Value" in df_foci.columns
    else "Metadata_Well"
)

sns_displot = sns.displot(df_foci, x="Barcode_MatchedTo_Score", col=col_var, col_wrap=3)
plt.tight_layout()
plt.savefig(
    Path(output_dir) / "barcode_score_distribution_per_well.png",
    dpi=150,
    bbox_inches="tight",
)
plt.show()

# %% [markdown]
# ### Observed Barcode Repeat Check

# %%
readlist = df_foci["Barcode_BarcodeCalled"]
print("% Reads with >4 repeat nucleotide calls")
repeat_percent = (
    100
    * pd.Series(
        [
            any(repeat in read for repeat in ["AAAAA", "CCCCC", "GGGGG", "TTTTT"])
            for read in readlist
        ]
    ).mean()
)
print(repeat_percent)

# %% [markdown]
# ### Spatial Quality Visualization
#
# Percent perfect barcodes by position

# %%
# Create position mapping if geometry is provided
pos_df = None

if rows and columns:
    # Square/rectangular acquisition
    print(f"Creating square position mapping: {rows}x{columns}")
    pos_data = []
    for site in range(rows * columns):
        row = site // columns
        col = site % columns
        pos_data.append({"Metadata_Site": site, "x_loc": col, "y_loc": row})
    pos_df = pd.DataFrame(pos_data)

elif row_widths:
    # Circular acquisition (from original notebook)
    print(f"Creating circular position mapping with {len(row_widths)} rows")
    max_width = max(row_widths)
    pos_dict = {}
    count = 0
    # creates dict of (xpos,ypos) = imnumber
    for row in range(len(row_widths)):
        row_width = row_widths[row]
        left_pos = int((max_width - row_width) / 2)
        for col in range(row_width):
            if row % 2 == 0:
                pos_dict[(int(left_pos + col), row)] = count
                count += 1
            else:
                right_pos = left_pos + row_width - 1
                pos_dict[(int(right_pos - col), row)] = count
                count += 1
    # make dict into df
    pos_df = (
        pd.DataFrame.from_dict(pos_dict, orient="index")
        .reset_index()
        .rename(columns={"index": "loc", 0: "Metadata_Site"})
    )
    pos_df[["x_loc", "y_loc"]] = pd.DataFrame(
        pos_df["loc"].tolist(), index=pos_df.index
    )
else:
    print("No geometry provided - spatial plot will be skipped")

if pos_df is not None:
    print(f"Position mapping created for {len(pos_df)} sites")

# %%
# Create spatial plot if position mapping exists
if pos_df is not None:
    # % Perfect by well
    df_foci_slice = df_foci.loc[
        :, ["Metadata_Well", "Metadata_Site", "Barcode_MatchedTo_Score"]
    ]
    df_foci_perf = df_foci_slice[df_foci_slice["Barcode_MatchedTo_Score"] == 1]
    df_foci_perf = (
        df_foci_perf.groupby(["Metadata_Well", "Metadata_Site"])
        .count()
        .reset_index()
        .rename(columns={"Barcode_MatchedTo_Score": "Num_Perf"})
    )
    df_foci_slice = (
        df_foci_slice.groupby(["Metadata_Well", "Metadata_Site"])
        .count()
        .reset_index()
        .rename(columns={"Barcode_MatchedTo_Score": "Num_Total"})
    )
    df_foci_pp = df_foci_perf.merge(
        df_foci_slice, on=["Metadata_Well", "Metadata_Site"]
    )
    df_foci_pp["PerPerf"] = (df_foci_pp["Num_Perf"] / df_foci_pp["Num_Total"]) * 100
    df_foci_pp["PerPerf"] = df_foci_pp["PerPerf"].astype("int")

    # Add the location to the foci dfs
    df_foci_pp = df_foci_pp.merge(pos_df, on="Metadata_Site").reset_index()

    g = sns.relplot(
        data=df_foci_pp,
        x="x_loc",
        y="y_loc",
        hue="PerPerf",
        col="Metadata_Well",
        col_wrap=3,
        palette="viridis",
        marker="s",
        s=200,
    )
    plt.suptitle("Spatial Distribution of Perfect Barcodes")
    plt.tight_layout()
    plt.savefig(
        Path(output_dir) / "spatial_quality_scatter.png", dpi=150, bbox_inches="tight"
    )
    plt.show()
    # note missing sites indicate that site has zero perfect barcodes
else:
    print("Skipping spatial plot - no geometry provided")

# %% [markdown]
# ### Per-Cycle Nucleotide Frequency (Observed)

# %%
dflist = []
for cycle in range(1, numcycles + 1):
    df_foci["PerCycle"] = df_foci["Barcode_BarcodeCalled"].str.slice(cycle - 1, cycle)
    BarcodeCat = df_foci["PerCycle"].str.cat()
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "A",
            "Frequency": float(BarcodeCat.count("A")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "C",
            "Frequency": float(BarcodeCat.count("C")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "G",
            "Frequency": float(BarcodeCat.count("G")) / float(len(BarcodeCat)),
        }
    )
    dflist.append(
        {
            "Cycle": int(cycle),
            "Nucleotide": "T",
            "Frequency": float(BarcodeCat.count("T")) / float(len(BarcodeCat)),
        }
    )
df_parsed = pd.DataFrame(dflist)
g = sns.lineplot(x="Cycle", y="Frequency", hue="Nucleotide", data=df_parsed)
g.set_ylim([0.1, 0.5])
handles, labels = g.get_legend_handles_labels()
g.legend(handles=handles[0:], labels=labels[0:])
g.set_xticks(list(range(1, numcycles + 1)))
plt.title("Observed Nucleotide Frequency by Cycle")
plt.tight_layout()
plt.savefig(
    Path(output_dir) / "observed_nucleotide_frequency.png", dpi=150, bbox_inches="tight"
)
plt.show()

# %% [markdown]
# ### Mismatch Cycle Analysis


# %%
def returnbadcycle(query, target):
    """Return the cycle (1-indexed) where query and target differ."""
    if pd.isna(query) or pd.isna(target):
        return None
    min_len = min(len(query), len(target))
    for x in range(min_len):
        if query[x] != target[x]:
            return x + 1
    return None


# Filter for near-perfect matches using score threshold
thresh = 1 - 1 / numcycles
df_onemismatch = df_foci.query("1 > Barcode_MatchedTo_Score > .85").reset_index(
    drop=True
)

if len(df_onemismatch) > 0:
    df_onemismatch["BadCycle"] = df_onemismatch.apply(
        lambda x: returnbadcycle(
            x["Barcode_BarcodeCalled"], x["Barcode_MatchedTo_Barcode"]
        ),
        axis=1,
    )

    # Plot mismatch cycle distribution
    # Use col parameter based on available column
    col_var = (
        "Metadata_Well"
        if "Metadata_Well" in df_onemismatch.columns
        else "Metadata_Plate"
    )
    sns.catplot(
        data=df_onemismatch, col=col_var, x="BadCycle", kind="count", col_wrap=3
    )
    plt.suptitle("Distribution of Mismatch Cycles (Near-Perfect Matches)")
    plt.tight_layout()
    plt.savefig(
        Path(output_dir) / "mismatch_cycle_distribution.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.show()

    print("\nMismatch Analysis:")
    print(f"  Total foci: {len(df_foci)}")
    print(
        f"  Near-perfect matches (score > 0.85): {len(df_onemismatch)} ({len(df_onemismatch) / len(df_foci) * 100:.2f}%)"
    )
else:
    print("No near-perfect mismatches found (all scores are either 1.0 or <= 0.85)")

# %% [markdown]
# ## Gene & Barcode Coverage Analysis

# %%
perfect_df = df_foci[df_foci["Barcode_MatchedTo_Score"] == 1]

# Handle different column naming conventions
gene_col_foci = (
    "Barcode_MatchedTo_GeneCode"
    if "Barcode_MatchedTo_GeneCode" in df_foci.columns
    else "Barcode_MatchedTo_Gene"
)

print(f"The number of unique genes in the library is {len(bc_df[gene_col].unique())}")
print(
    f"Perfect barcodes are detected for {len(df_foci.loc[df_foci['Barcode_MatchedTo_Score'] == 1][gene_col_foci].unique())} genes\n"
)
print("The 10 most detected genes are:")
gene_counts = (
    df_foci.loc[df_foci["Barcode_MatchedTo_Score"] == 1][gene_col_foci]
    .value_counts()
    .head(n=10)
)
print(gene_counts)

print(
    f"\nThe number of unique barcodes in the library is {len(bc_df[barcode_col].unique())}"
)
print(
    f"Perfect barcodes are detected for {len(df_foci.loc[df_foci['Barcode_MatchedTo_Score'] == 1]['Barcode_MatchedTo_Barcode'].unique())} of them\n"
)
print("The 10 most detected barcodes are:")
barcode_counts = (
    df_foci.loc[df_foci["Barcode_MatchedTo_Score"] == 1]["Barcode_MatchedTo_Barcode"]
    .value_counts()
    .head(n=10)
)
print(barcode_counts)

# Save coverage statistics
with open(Path(output_dir) / "coverage_stats.txt", "w") as f:
    f.write("Gene & Barcode Coverage Statistics\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Total genes in library: {len(bc_df[gene_col].unique())}\n")
    f.write(
        f"Genes detected (perfect matches): {len(df_foci.loc[df_foci['Barcode_MatchedTo_Score'] == 1][gene_col_foci].unique())}\n\n"
    )
    f.write(f"Total barcodes in library: {len(bc_df[barcode_col].unique())}\n")
    f.write(
        f"Barcodes detected (perfect matches): {len(df_foci.loc[df_foci['Barcode_MatchedTo_Score'] == 1]['Barcode_MatchedTo_Barcode'].unique())}\n\n"
    )
    f.write("\nTop 10 Most Detected Genes:\n")
    f.write(gene_counts.to_string())
    f.write("\n\nTop 10 Most Detected Barcodes:\n")
    f.write(barcode_counts.to_string())

print(f"\nCoverage statistics saved to: {Path(output_dir) / 'coverage_stats.txt'}")

# %% [markdown]
# ## Analysis Complete
#
# All plots and statistics have been saved to the output directory.
