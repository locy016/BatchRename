# Operation History and Undo Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove duplicate product and workflow headings, and consolidate all user-facing undo operations into the operation history workspace.

**Architecture:** The history Pinia store becomes the single owner of the selected operation and its undo preflight state. `OperationDetails.vue` presents both persisted details and the safe undo action, while the dedicated undo route, view, store, and panel are removed. Rust services and Tauri commands remain unchanged.

**Tech Stack:** Vue 3, Pinia, Vue Router, Element Plus, Vitest, Playwright, Tauri 2.

---

### Task 1: Simplify global and workflow navigation

**Files:**
- Modify: `src/app/AppShell.spec.ts`
- Modify: `src/app/AppShell.vue`
- Modify: `src/components/layout/WorkflowRail.spec.ts`
- Modify: `src/components/layout/WorkflowRail.vue`
- Modify: `src/router/index.ts`

1. Write assertions that the product-title element, workflow heading, `/undo` link, and `/undo` route are absent.
2. Run the focused tests and verify they fail against the current interface.
3. Remove the redundant title and workflow heading; remove the standalone undo navigation and route.
4. Run the focused tests and type checking.
5. Commit the navigation simplification in Chinese.

### Task 2: Move undo state into operation history

**Files:**
- Modify: `src/views/HistoryView.spec.ts`
- Modify: `src/stores/history.ts`
- Modify: `src/views/HistoryView.vue`
- Modify: `src/components/history/OperationDetails.vue`
- Create: `src/components/history/OperationDetails.spec.ts`

1. Write failing store tests for combined detail/preflight loading and post-undo refresh.
2. Write a failing component test for safe, completed, blocked, and unavailable undo states in the operation details workspace.
3. Implement selected-operation, undo-check, busy, and error state in the history store.
4. Connect selection and execution in `HistoryView.vue`, and add the undo section to `OperationDetails.vue`.
5. Run focused tests and type checking.
6. Commit the integrated history workflow in Chinese.

### Task 3: Remove obsolete undo frontend resources

**Files:**
- Delete: `src/views/UndoView.vue`
- Delete: `src/views/UndoView.spec.ts`
- Delete: `src/stores/undo.ts`
- Delete: `src/stores/undo.spec.ts`
- Delete: `src/components/undo/UndoCheckPanel.vue`
- Delete: `src/components/undo/UndoCheckPanel.spec.ts`
- Modify: `tests/e2e/execute-history-undo.spec.ts`

1. Replace the old navigation E2E assertion with an in-history undo assertion.
2. Run the E2E test and verify it fails before the obsolete resources are removed.
3. Delete standalone undo files and remove all remaining imports and references.
4. Run repository-wide searches to ensure no dedicated undo page resource remains.
5. Commit cleanup in Chinese.

### Task 4: Synchronize product documentation and verify

**Files:**
- Modify: `README.md`
- Modify: `src/components/help/UsageGuide.vue`
- Modify: `src/components/help/AboutPanel.vue`
- Modify: `src/components/rename/ExecutionDetails.vue`
- Modify: `docs/images/batch-rename-2.0-workspace.png`

1. Update user-facing text so recovery is described as part of operation history.
2. Refresh the workspace screenshot without the duplicate title and undo navigation.
3. Run all Vitest, Playwright, type-checking, frontend build, Rust tests, and compatibility tests.
4. Build Windows artifacts if the prior executable is not locked by a running app; never terminate a user-owned process automatically.
5. Commit documentation and generated metadata in Chinese; do not push.

