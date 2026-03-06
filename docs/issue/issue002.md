# Issue 002: Clean Git ignore rules and stop tracking generated EMG artifacts

**Status**: Done
**Created**: 2026-03-06

## Background

The repository now contains generated fixture files, reference baseline outputs, runtime outputs,
and cache directories that should remain available locally but should no longer clutter `git status`
or stay tracked in the parent repository.

## Acceptance Criteria

- [ ] `.gitignore` ignores generated runtime outputs and cache artifacts used in this repository.
- [ ] Selected generated fixture and reference output files are removed from the Git index only and remain on disk.
- [ ] `git status` no longer reports the ignored output paths as untracked or modified tracked files.
- [ ] The handling limit for `.agents` is documented clearly because it is a tracked submodule/gitlink.

## Tasks

- [x] 1. Inspect the current ignore rules and tracked artifact set.
- [x] 2. Update `.gitignore` with repository-specific generated artifact paths.
- [x] 3. Remove generated fixture and baseline output files from the Git index only.
- [x] 4. Re-run `git status` to verify the cleanup result.
- [x] 5. Commit the cleanup with a Korean commit message.

## Notes

This task intentionally keeps the local files in place while changing only ignore rules and index tracking.
The `.agents` entry is a submodule/gitlink, so `.gitignore` cannot hide its dirty state. Verification confirmed that generated files remain on disk while Git now treats them as ignored after index removal.
