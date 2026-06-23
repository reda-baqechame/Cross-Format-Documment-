/** UI state for the single-canvas workspace. */

import { create } from "zustand";

interface WorkspaceState {
  selectedNodeId: string | null;
  editingNodeId: string | null;
  panelOpen: boolean;
  commentsOpen: boolean;
  approvalsOpen: boolean;
  /** When on, clicking a PDF page drops a new positioned text box at that spot. */
  addTextMode: boolean;
  select: (id: string | null) => void;
  setEditing: (id: string | null) => void;
  togglePanel: () => void;
  toggleComments: () => void;
  toggleApprovals: () => void;
  toggleAddText: () => void;
  setAddText: (on: boolean) => void;
}

export const useWorkspace = create<WorkspaceState>((set) => ({
  selectedNodeId: null,
  editingNodeId: null,
  panelOpen: false,
  commentsOpen: false,
  approvalsOpen: false,
  addTextMode: false,
  select: (id) => set({ selectedNodeId: id }),
  setEditing: (id) => set({ editingNodeId: id }),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  toggleComments: () => set((s) => ({ commentsOpen: !s.commentsOpen })),
  toggleApprovals: () => set((s) => ({ approvalsOpen: !s.approvalsOpen })),
  toggleAddText: () => set((s) => ({ addTextMode: !s.addTextMode })),
  setAddText: (on) => set({ addTextMode: on }),
}));
