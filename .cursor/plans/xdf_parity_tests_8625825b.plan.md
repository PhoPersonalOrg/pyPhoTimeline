---
name: xdf parity tests
overview: Add writer-level and `LabRecorder` integration tests that simulate recording, fetch known-good XDF fixtures from `xdf-modules/example-files`, and compare normalized decoded contents rather than raw bytes.
todos:
  - id: inspect-fixtures
    content: Identify the first example XDF fixture(s) to target, starting with `minimal.xdf`, and define a normalized comparison contract.
    status: completed
  - id: add-test-helpers
    content: Add shared test helpers for downloading fixture files and comparing decoded XDF contents via `pyxdf`.
    status: completed
  - id: upgrade-writer-tests
    content: Strengthen writer-level tests to assert stream payloads and compare against normalized reference data.
    status: completed
  - id: add-recorder-integration
    content: Add an end-to-end simulated `LabRecorder` test that exercises the real recording flow and compares output to the same normalized fixture.
    status: completed
  - id: validate-test-flow
    content: Run the focused test suite and confirm network-dependent skips and comparison behavior are clear and stable.
    status: completed
isProject: false
---

# XDF Parity Test Plan

## Goal
Extend the `lab-recorder-python` test suite so it exercises both the low-level XDF writer and the end-to-end `LabRecorder` recording path, then compares those generated files against known-good XDF example files fetched from `xdf-modules/example-files`.

## Why Normalize Instead Of Byte-Comparing
The repository explicitly states that output is intended to be functionally compatible, not byte-for-byte identical, and live chunk interleaving may differ. The new tests should therefore compare decoded XDF structure and stream payloads after loading with `pyxdf`, while ignoring unstable fields such as file header `datetime`, assigned stream IDs, and exact chunk ordering.

Relevant code and docs:
- [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\README.md`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\README.md): notes that exact chunk interleaving may differ even for valid files.
- [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\xdf\writer.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\xdf\writer.py): `SimpleXDFWriter.open()`, `add_stream()`, `write_samples()`, `write_clock_offset()`, `write_boundary_chunk()`, `write_stream_footer()`.
- [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\recorder.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\recorder.py): `LabRecorder.start_recording()` wires `SimpleXDFWriter`, inlets, acquisition, and background threads.
- [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_xdf_roundtrip.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_xdf_roundtrip.py): current single round-trip smoke test.

## Planned Changes

### 1. Add Shared XDF Comparison Helpers
Create a small test helper module under [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests) that:
- Downloads selected fixture files from raw GitHub URLs at test time, starting with `minimal.xdf` because `pyxdf` itself documents it as a canonical example fixture.
- Loads both reference and generated files through `pyxdf.load_xdf(...)`.
- Normalizes each stream into a deterministic structure keyed by stable metadata such as `name`, `type`, `channel_count`, `nominal_srate`, and payload content.
- Compares numeric streams by shape and values, marker streams by ordered string payloads and timestamps, and optionally checks footer-derived counts when they are stable.
- Ignores volatile fields such as header datetime, stream IDs, and implementation-specific chunk boundaries.

Essential comparison seam from the current test surface:
- `streams, header = pyxdf.load_xdf(str(output_path))`

### 2. Strengthen Writer-Level Golden Tests
Expand or split [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_xdf_roundtrip.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_xdf_roundtrip.py) so it does more than assert stream counts.

Planned writer assertions:
- Produce a deterministic file with `SimpleXDFWriter` using fixed sample values and timestamps.
- Compare the decoded result against the downloaded example fixture when the fixture shape matches.
- Add stronger semantic assertions for `time_series`, `time_stamps`, and stream metadata, not just stream names and counts.
- Keep the test resilient by using fixture-specific expectations rather than assuming the Python writer will match raw binary layout.

### 3. Add End-to-End `LabRecorder` Simulation Test
Add a new integration-style test file, likely [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_labrecorder_example_parity.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\tests\test_labrecorder_example_parity.py), that simulates recording through `LabRecorder` rather than calling `SimpleXDFWriter` directly.

Planned approach:
- Patch `pylsl.StreamInlet`, `pylsl.local_clock`, and recorder collaborators so the test does not require a real LSL network.
- Feed deterministic samples through the same paths used by `LabRecorder._setup_single_stream()`, `_on_data_received()`, and `_writer_thread_func()`.
- Start and stop recording via `LabRecorder.start_recording()` / `stop_recording()` so clock offsets, footers, and background writing are exercised.
- Compare the produced `.xdf` file against the normalized representation of the downloaded reference fixture.

Most important seam to exercise:
- In [`c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\recorder.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\lab-recorder-python\labrecorder\recorder.py), `start_recording()` creates the writer and `_writer_thread_func()` flushes `_data_buffers` into `self.xdf_writer.write_samples(...)`.

### 4. Keep Network-Dependent Fixtures Predictable
Because you chose download-at-test-time, the tests should make that explicit and stable:
- Fetch raw fixture URLs directly from GitHub.
- Cache per-test-run in a temp directory so multiple tests do not redownload the same file.
- Skip cleanly with a clear message if the fixture download fails due to network unavailability, rather than causing misleading recorder failures.

### 5. Verify Test Runner Compatibility
Preserve the repository’s current `unittest` style unless a clear mismatch appears while implementing. The existing suite already uses `unittest` and conditional `pyxdf` skips, so the safest path is to extend that style rather than introducing a new test framework.

## Expected Outcome
After implementation, the repo should have:
- Stronger semantic coverage for `SimpleXDFWriter` output.
- An actual simulated-recording test around `LabRecorder`.
- A reusable normalized XDF comparator based on `pyxdf`.
- Reference-backed regression tests tied to the public `xdf-modules/example-files` fixtures, starting with `minimal.xdf` and leaving room to add more examples later.