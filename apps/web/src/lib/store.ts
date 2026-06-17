/** UI state for the single-canvas workspace. */

import { create } from "zustand";

interface WorkspaceState {
  selectedNodeId: string | null;
  editingNodeId: string | null;
  panelOpen: boolean;
  commentsOpen: boolean;
  select: (id: string | null) => void;
  setEditing: (id: string | null) => void;
  togglePanel: () => void;
  toggleComments: () => void;
}

export const useWorkspace = create<WorkspaceState>((set) => ({
  selectedNodeId: null,
  editingNodeId: null,
  panelOpen: true,
  commentsOpen: false,
  select: (id) => set({ selectedNodeId: id }),
  setEditing: (id) => set({ editingNodeId: id }),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  toggleComments: () => set((s) => ({ commentsOpen: !s.commentsOpen })),
}));
