# Summary of Issues Encountered During SSINS Memory Optimization Attempts

## Goal

To reduce the peak memory consumption of the `demo/04_ssins.py` script when processing large interferometric datasets (UVFITS format in testing).

## Initial State

The original script (`demo/04_ssins.py`) functions correctly but exhibits high peak memory usage:

* ~1.9 GB for a small test dataset (~660MB file).
* ~13.9 GB for a medium test dataset (~4.9GB file).
* Likely OOM for larger datasets on memory-constrained systems.

## Optimization Attempts & Issues

Several strategies were attempted in `demo/04_ssins_memopt_fix.py`, primarily involving reading and processing data in chunks using `pyuvdata` and `SSINS` objects.

### 1. Chunked Read + Combine (`pyuvdata.__add__`)

* **Approach:** Read data in time chunks (using `UVData.read(times=...)`). Combine chunks into the main `UVData` (or `SSINS.SS`) object using `obj.__add__(chunk_obj, inplace=True)` or `obj = obj + chunk_obj`. Differencing (`diff=True`) was initially applied during chunk reads, later disabled for debugging.
* **Issue:** **Mysterious Object Corruption.** The combined `UVData`/`SS` object appeared valid immediately after the chunk reading/combination loop and even after a final `ss.select()` call within the `read_select_memopt` function. However, upon returning from this function to `main()`, the object's core attributes (`Nblts`, `Nfreqs`, `Npols`, `polarization_array`, `data_array` etc.) were consistently found to be `None` right before being passed to the plotting function. This occurred with both `SS()` and base `UVData()` objects, with both `inplace=True` and out-of-place addition, and regardless of whether differencing was performed during the chunk reads. Skipping the final `select` call did not resolve it. The corruption manifested specifically between the function return and subsequent use, suggesting a potential issue with object state management, garbage collection, or C-extension interaction after repeated `__add__` operations on large, incrementally built objects. Attempts to perform manual differencing after the read also failed because methods like `reorder_blts` encountered the `None` attributes internally.

### 2. Chunked Read + Combine (`pyuvdata.fast_concat`)

* **Approach:** Similar to attempt 1, but using `obj.fast_concat(chunk_obj, axis=..., inplace=True)` instead of `__add__`.
* **Issue:** Led to `ValueError` exceptions during plotting, indicating metadata inconsistencies (e.g., polarization errors). `fast_concat` skips the thorough checks performed by `__add__`, making it unsafe when metadata between chunks might not perfectly align without manual verification, which wasn't implemented.

### 3. Hybrid Approach (Metadata Read + Per-Polarization Data Read)

* **Approach:** Read only metadata initially using `read_data=False`. Then, within the plotting function loop for each polarization, read the full dataset for *only that polarization*, applying differencing during this read. Process frequency chunks in memory for the single-polarization data.
* **Issues:**
  * **Slow Performance:** This approach was extremely slow ("timed out") for the medium dataset due to reading the entire large data file multiple times (once per polarization).
  * **Initial `ValueError`:** An initial attempt failed with a `ValueError` because the selections applied to the metadata object (like `antenna_nums`) were incorrectly passed to the subsequent per-polarization `read` calls.
  * **Premature Exit:** After correcting the selection issue, the script still sometimes exited prematurely after the metadata selection step without clear Python errors, possibly due to OS-level memory pressure or other instability.

## Conclusion

Attempts to optimize memory usage by chunking data reads and combining `UVData`/`SS` objects were unsuccessful due to either:

* An apparent object corruption bug occurring after chunk combination using `__add__`, manifesting between function return and subsequent object use.
* The `fast_concat` method being unsafe without additional metadata checks.
* The Hybrid (metadata + per-pol read) approach being unacceptably slow and potentially unstable.

The most reliable option currently is the original script, despite its high memory usage. Further progress likely requires debugging the object corruption issue within `pyuvdata`/`SSINS` when using `__add__` on chunked reads, or implementing a completely different approach (e.g., direct HDF5/FITS access).
