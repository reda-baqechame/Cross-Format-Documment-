/** UI state for the single-canvas workspace. */

import { create } from "zustand";

interface WorkspaceState {
  selectedNodeId: string | null;
  panelOpen: boolean;
  select: (id: string | null) => void;
  togglePanel: () => void;
}

export const useWorkspace = create<WorkspaceState>((set) => ({
  selectedNodeId: null,
  panelOpen: true,
  select: (id) => set({ selectedNodeId: id }),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
}));
