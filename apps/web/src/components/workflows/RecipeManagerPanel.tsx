"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Clock3,
  Edit3,
  Loader2,
  Play,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";

import {
  createRecipe,
  deleteRecipe,
  listRecipeRuns,
  listRecipes,
  listRecipeTools,
  runRecipe,
  updateRecipe,
  type RecipeRunResult,
  type WorkflowRecipe,
} from "@/lib/api";
import { friendlyApiError } from "@/lib/upload";

export function RecipeManagerPanel({ docId }: { docId: string }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [historyRecipeId, setHistoryRecipeId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<RecipeRunResult | null>(null);

  const recipes = useQuery({ queryKey: ["recipes"], queryFn: listRecipes });
  const tools = useQuery({ queryKey: ["recipe-tools"], queryFn: listRecipeTools });
  const history = useQuery({
    queryKey: ["recipe-runs", historyRecipeId],
    queryFn: () => listRecipeRuns(historyRecipeId!),
    enabled: historyRecipeId !== null,
  });

  const save = useMutation({
    mutationFn: () => {
      const body = { name, steps: steps.map((tool) => ({ tool, params: {} })) };
      return editingId ? updateRecipe(editingId, body) : createRecipe(body);
    },
    onSuccess: (recipe) => {
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      resetEditor();
      setHistoryRecipeId(recipe.id);
    },
  });

  const remove = useMutation({
    mutationFn: deleteRecipe,
    onSuccess: (_data, recipeId) => {
      if (historyRecipeId === recipeId) setHistoryRecipeId(null);
      if (editingId === recipeId) resetEditor();
      setLastRun(null);
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      void queryClient.removeQueries({ queryKey: ["recipe-runs", recipeId] });
    },
  });

  const run = useMutation({
    mutationFn: (recipeId: string) => runRecipe(recipeId, docId),
    onSuccess: (result, recipeId) => {
      setLastRun(result);
      setHistoryRecipeId(recipeId);
      void queryClient.invalidateQueries({ queryKey: ["recipe-runs", recipeId] });
    },
  });

  function resetEditor() {
    setName("");
    setSteps([]);
    setEditingId(null);
  }

  function startEditing(recipe: WorkflowRecipe) {
    setEditingId(recipe.id);
    setName(recipe.name);
    setSteps(recipe.steps.map((step) => step.tool));
  }

  function moveStep(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    setSteps((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  const error = save.error ?? remove.error ?? run.error;

  return (
    <div className="space-y-5 overflow-auto p-5">
      <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              {editingId ? "Edit recipe" : "Build a recipe"}
            </h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Runs are manual. Read steps execute now; edits and actions only produce an approval
              request.
            </p>
          </div>
          {editingId && (
            <button
              type="button"
              onClick={resetEditor}
              aria-label="Cancel recipe editing"
              className="rounded-md p-2 text-slate-500 hover:bg-white hover:text-slate-800"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Recipe name
          <input
            value={name}
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            className="studio-input mt-1 normal-case tracking-normal"
            placeholder="Invoice intake checks"
          />
        </label>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tool palette</p>
          {tools.isLoading && <p className="mt-2 text-xs text-slate-500">Loading tools...</p>}
          {tools.isError && (
            <p role="alert" className="mt-2 text-xs text-red-700">
              {friendlyApiError(tools.error, "Could not load the validated recipe tools.")}
            </p>
          )}
          <div className="mt-2 grid grid-cols-1 gap-2">
            {tools.data?.map((tool) => (
              <button
                type="button"
                key={tool.name}
                onClick={() => setSteps((current) => [...current, tool.name])}
                className="flex min-h-[42px] items-start gap-2 rounded-md border border-slate-200 bg-white p-2 text-left hover:border-blue-300 hover:bg-blue-50"
              >
                {tool.requires_approval ? (
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                ) : (
                  <Plus className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
                )}
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-slate-800">{tool.label}</span>
                  <span className="block text-xs leading-4 text-slate-500">{tool.description}</span>
                  {tool.requires_approval && (
                    <span className="mt-1 block text-[11px] font-medium text-amber-700">
                      Approval-gated
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </div>

        {steps.length > 0 && (
          <ol className="space-y-2" aria-label="Recipe steps">
            {steps.map((toolName, index) => {
              const tool = tools.data?.find((item) => item.name === toolName);
              return (
                <li
                  key={`${toolName}-${index}`}
                  className="flex items-center gap-2 rounded-md border border-slate-200 bg-white p-2"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-800">
                    {tool?.label ?? toolName}
                  </span>
                  <button
                    type="button"
                    onClick={() => moveStep(index, -1)}
                    disabled={index === 0}
                    aria-label={`Move ${toolName} up`}
                    className="p-1 text-slate-500 disabled:opacity-25"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => moveStep(index, 1)}
                    disabled={index === steps.length - 1}
                    aria-label={`Move ${toolName} down`}
                    className="p-1 text-slate-500 disabled:opacity-25"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}
                    aria-label={`Remove ${toolName}`}
                    className="p-1 text-slate-500 hover:text-red-600"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
          </ol>
        )}

        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={!name.trim() || steps.length === 0 || save.isPending}
          className="flex min-h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {editingId ? "Save recipe changes" : "Save manual recipe"}
        </button>
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {friendlyApiError(error, "The recipe action failed.")}
        </p>
      )}

      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Saved recipes</h3>
          <span className="text-xs text-slate-400">{recipes.data?.length ?? 0}</span>
        </div>
        {recipes.isLoading && <p className="mt-3 text-sm text-slate-500">Loading recipes...</p>}
        {recipes.isError && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {friendlyApiError(recipes.error, "Could not load saved recipes.")}
          </p>
        )}
        {recipes.data?.length === 0 && (
          <p className="mt-3 rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
            No recipes yet. Add validated tools above to create one.
          </p>
        )}
        <div className="mt-3 space-y-3">
          {recipes.data?.map((recipe) => (
            <article key={recipe.id} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h4 className="truncate text-sm font-semibold text-slate-900">{recipe.name}</h4>
                  <p className="mt-1 text-xs text-slate-500">
                    {recipe.steps.length} step{recipe.steps.length === 1 ? "" : "s"} · Manual only
                  </p>
                </div>
                <span className="rounded-full bg-teal-50 px-2 py-1 text-[11px] font-medium text-teal-700">
                  Guarded
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => run.mutate(recipe.id)}
                  disabled={run.isPending}
                  className="flex min-h-[36px] items-center justify-center gap-1.5 rounded-md bg-blue-600 px-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" /> Run on this file
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryRecipeId(recipe.id)}
                  className="flex min-h-[36px] items-center justify-center gap-1.5 rounded-md border border-slate-200 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <Clock3 className="h-3.5 w-3.5" /> Run history
                </button>
                <button
                  type="button"
                  onClick={() => startEditing(recipe)}
                  className="flex min-h-[36px] items-center justify-center gap-1.5 rounded-md border border-slate-200 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <Edit3 className="h-3.5 w-3.5" /> Edit
                </button>
                <button
                  type="button"
                  onClick={() => remove.mutate(recipe.id)}
                  disabled={remove.isPending}
                  className="flex min-h-[36px] items-center justify-center gap-1.5 rounded-md border border-red-200 px-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {lastRun && (
        <section className="rounded-lg border border-teal-200 bg-teal-50 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-teal-900">
            <CheckCircle2 className="h-4 w-4" /> Latest run
          </div>
          <p className="mt-1 text-xs leading-5 text-teal-800">{lastRun.summary}</p>
          <RunSteps steps={lastRun.steps} />
        </section>
      )}

      {historyRecipeId && (
        <section className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Run history</h3>
            <button
              type="button"
              onClick={() => setHistoryRecipeId(null)}
              aria-label="Close run history"
              className="p-1 text-slate-500 hover:text-slate-800"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {history.isLoading && <p className="mt-3 text-xs text-slate-500">Loading run history...</p>}
          {history.data?.length === 0 && (
            <p className="mt-3 text-xs text-slate-500">This recipe has not run yet.</p>
          )}
          <ol className="mt-3 space-y-3">
            {history.data?.map((item) => (
              <li key={item.id} className="border-t border-slate-100 pt-3 first:border-0 first:pt-0">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-slate-700">
                    {new Date(item.created_at).toLocaleString()}
                  </span>
                  <span className="text-slate-500">{item.status}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-500">{item.summary}</p>
                <RunSteps steps={item.steps} />
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function RunSteps({ steps }: { steps: RecipeRunResult["steps"] }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {steps.map((step, index) => (
        <li key={`${step.tool}-${index}`} className="rounded-md bg-white/80 p-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-800">{step.tool}</span>
          <span className="ml-1 text-slate-500">· {step.status}</span>
          <p className="mt-1 leading-4">{step.summary}</p>
        </li>
      ))}
    </ul>
  );
}
