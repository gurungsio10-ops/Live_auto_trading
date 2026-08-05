"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiClientError } from "./api-client";
import type { ApiMeta } from "./types";

type State<T> =
  | { status: "loading"; data: null; error: null; meta: null }
  | { status: "error"; data: null; error: string; meta: null }
  | { status: "success"; data: T; error: null; meta: ApiMeta };

export function useAsyncData<T>(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
) {
  const queryKey = JSON.stringify(query ?? {});
  const [state, setState] = useState<State<T>>({
    status: "loading",
    data: null,
    error: null,
    meta: null,
  });
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", data: null, error: null, meta: null });

    (async () => {
      try {
        const res = await api.get<T>(path, query);
        if (cancelled) return;
        setState({
          status: "success",
          data: res.data,
          error: null,
          meta: res.meta,
        });
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof ApiClientError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Unknown error";
        setState({ status: "error", data: null, error: message, meta: null });
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, queryKey, tick]);

  return {
    ...state,
    reload,
    setData: (next: T | ((prev: T | null) => T)) => {
      setState((prev) => {
        const data = typeof next === "function" ? (next as (p: T | null) => T)(prev.data) : next;
        return prev.status === "success"
          ? { ...prev, data }
          : { status: "success", data, error: null, meta: prev.meta ?? { demo: true } };
      });
    },
  };
}
