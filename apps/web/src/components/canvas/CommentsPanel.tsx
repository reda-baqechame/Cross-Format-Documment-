"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  addComment,
  type CommentThread,
  deleteComment,
  listComments,
  replyToComment,
  resolveComment,
} from "@/lib/api";
import { useWorkspace } from "@/lib/store";

/**
 * Review sidebar: comment threads anchored to canvas nodes (or the document as a whole).
 * Every action is a reversible, versioned patch on the backend. Select text on the page
 * to anchor a new comment to it.
 */
export function CommentsPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const selectedId = useWorkspace((s) => s.selectedNodeId);
  const [draft, setDraft] = useState("");

  const threads = useQuery({
    queryKey: ["comments", docId],
    queryFn: () => listComments(docId),
  });

  const invalidate = (next: CommentThread[]) => {
    queryClient.setQueryData(["comments", docId], next);
    // Comments are nodes, so the model changed too.
    queryClient.invalidateQueries({ queryKey: ["model", docId] });
  };

  const add = useMutation({
    mutationFn: () => addComment(docId, draft, selectedId),
    onSuccess: (next) => {
      invalidate(next);
      setDraft("");
    },
  });

  const open = threads.data?.filter((t) => !t.resolved) ?? [];
  const resolved = threads.data?.filter((t) => t.resolved) ?? [];

  return (
    <aside className="w-80 shrink-0 space-y-4 overflow-auto border-l border-slate-200 bg-white p-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-800">Comments</h2>
        <p className="text-xs text-slate-500">
          {selectedId ? "Anchored to the selected text." : "Select text to anchor a comment."}
        </p>
      </div>

      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a comment…"
          rows={2}
          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
        />
        <button
          onClick={() => add.mutate()}
          disabled={add.isPending || !draft.trim()}
          className="w-full rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
        >
          {selectedId ? "Comment on selection" : "Comment on document"}
        </button>
      </div>

      {threads.isLoading && <p className="text-sm text-slate-500">Loading…</p>}

      <div className="space-y-3">
        {open.map((t) => (
          <Thread key={t.id} docId={docId} thread={t} onChange={invalidate} />
        ))}
      </div>

      {resolved.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-500">
            Resolved ({resolved.length})
          </summary>
          <div className="mt-2 space-y-3">
            {resolved.map((t) => (
              <Thread key={t.id} docId={docId} thread={t} onChange={invalidate} />
            ))}
          </div>
        </details>
      )}

      {threads.data && threads.data.length === 0 && (
        <p className="text-sm text-slate-400">No comments yet.</p>
      )}
    </aside>
  );
}

function Thread({
  docId,
  thread,
  onChange,
}: {
  docId: string;
  thread: CommentThread;
  onChange: (next: CommentThread[]) => void;
}) {
  const [reply, setReply] = useState("");
  const [replying, setReplying] = useState(false);

  const sendReply = useMutation({
    mutationFn: () => replyToComment(docId, thread.id, reply),
    onSuccess: (next) => {
      onChange(next);
      setReply("");
      setReplying(false);
    },
  });
  const toggle = useMutation({
    mutationFn: () => resolveComment(docId, thread.id, !thread.resolved),
    onSuccess: onChange,
  });
  const remove = useMutation({
    mutationFn: () => deleteComment(docId, thread.id),
    onSuccess: onChange,
  });

  return (
    <div
      className={`rounded-md border p-3 text-sm ${
        thread.resolved ? "border-slate-200 bg-slate-50 opacity-70" : "border-slate-200"
      }`}
    >
      <Bubble author={thread.author} text={thread.text} />
      {thread.replies.map((r) => (
        <div key={r.id} className="mt-2 border-l-2 border-slate-200 pl-2">
          <Bubble author={r.author} text={r.text} />
        </div>
      ))}

      {replying ? (
        <div className="mt-2 space-y-1">
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={2}
            placeholder="Reply…"
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-blue-400 focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => sendReply.mutate()}
              disabled={sendReply.isPending || !reply.trim()}
              className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-40"
            >
              Reply
            </button>
            <button onClick={() => setReplying(false)} className="text-xs text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex gap-3 text-xs text-slate-500">
          <button onClick={() => setReplying(true)} className="hover:text-slate-800">
            Reply
          </button>
          <button onClick={() => toggle.mutate()} className="hover:text-slate-800">
            {thread.resolved ? "Reopen" : "Resolve"}
          </button>
          <button onClick={() => remove.mutate()} className="hover:text-red-600">
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function Bubble({ author, text }: { author: string | null; text: string }) {
  return (
    <div>
      <span className="text-xs font-semibold text-slate-600">{author ?? "Anonymous"}</span>
      <p className="text-slate-800">{text}</p>
    </div>
  );
}
