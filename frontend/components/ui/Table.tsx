import { ReactNode } from "react";

export function Table({
  headers,
  children,
  dense = true,
}: {
  headers: ReactNode[];
  children: ReactNode;
  dense?: boolean;
}) {
  return (
    <div className="max-w-full overflow-x-auto border border-terminal-border">
      <table className="w-full min-w-[640px] border-collapse text-left text-xs">
        <thead className="bg-terminal-elevated/80 text-terminal-dim">
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                className={[
                  "font-display font-medium tracking-[0.06em] uppercase border-b border-terminal-border",
                  dense ? "px-3 py-2" : "px-4 py-3",
                ].join(" ")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-terminal-border/80">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({
  children,
  className = "",
  mono = true,
  title,
}: {
  children: ReactNode;
  className?: string;
  mono?: boolean;
  title?: string;
}) {
  return (
    <td
      title={title}
      className={[
        "px-3 py-2 align-middle",
        mono ? "font-mono tabular-nums" : "font-display",
        className,
      ].join(" ")}
    >
      {children}
    </td>
  );
}
